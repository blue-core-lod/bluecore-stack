from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pytest
from playwright.sync_api import APIRequestContext
from playwright.sync_api import APIResponse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

TERRAFORM_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_BATCH_SOURCE_CANDIDATES: tuple[Path, ...] = (
    TERRAFORM_ROOT.parent / "bluecore_api" / "sample" / "batch-small.jsonld",
    TERRAFORM_ROOT / "external" / "bluecore_api" / "sample" / "batch-small.jsonld",
)
UPLOADS_DIR = TERRAFORM_ROOT / "uploads"
LOCAL_BATCH_UPLOAD = UPLOADS_DIR / "integration-test.jsonld"


@dataclass(frozen=True)
class IntegrationConfig:
    base_url: str
    airflow_base_url: str
    request_timeout: float
    ready_timeout: int
    ready_poll_interval: float
    keycloak_client_id: str
    keycloak_client_secret: str | None
    keycloak_username: str
    keycloak_password: str
    airflow_username: str
    airflow_password: str
    keycloak_token_url: str
    airflow_token_url: str


# ==============================================================================
# Generic poll helper used by readiness checks (API/Airflow/Keycloak).
# ------------------------------------------------------------------------------
def _wait_for_status(
    request_context: APIRequestContext,
    url: str,
    acceptable_statuses: Iterable[int],
    timeout_seconds: int,
    poll_interval_seconds: float,
    request_timeout: float,
) -> APIResponse:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    last_response: APIResponse | None = None

    while time.time() < deadline:
        try:
            response = request_context.get(
                url,
                timeout=max(1, int(request_timeout * 1000)),
                max_redirects=0,
            )
            last_response = response
            if response.status in acceptable_statuses:
                return response
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(poll_interval_seconds)

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for {url}. Last HTTP status was {last_response.status}."
        )
    raise AssertionError(f"Timed out waiting for {url}. Last error: {last_error!r}.")


# ==============================================================================
# Poll Airflow auth until it returns a usable access token.
# ------------------------------------------------------------------------------
def _wait_for_airflow_token(
    request_context: APIRequestContext,
    config: IntegrationConfig,
) -> str:
    deadline = time.time() + config.ready_timeout
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = request_context.post(
                config.airflow_token_url,
                data={
                    "username": config.airflow_username,
                    "password": config.airflow_password,
                },
                timeout=max(1, int(config.request_timeout * 1000)),
            )
            last_response = response
            if response.status == 201:
                payload = response.json()
                token = payload.get("access_token")
                if token:
                    return token
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(config.ready_poll_interval)

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for Airflow token endpoint. Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out waiting for Airflow token endpoint. Last error: {last_error!r}."
    )


# ==============================================================================
# Wait for Keycloak token endpoint readiness (invalid creds should return 400/401).
# ------------------------------------------------------------------------------
def _wait_for_keycloak_token_endpoint(
    request_context: APIRequestContext,
    config: IntegrationConfig,
) -> None:
    deadline = time.time() + config.ready_timeout
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = request_context.post(
                config.keycloak_token_url,
                form={
                    "grant_type": "password",
                    "client_id": config.keycloak_client_id,
                    "username": "__invalid__",
                    "password": "__invalid__",
                },
                headers={"X-Forwarded-Proto": "https", "X-Forwarded-Port": "443"},
                timeout=max(1, int(config.request_timeout * 1000)),
            )
            last_response = response
            if response.status in {400, 401}:
                return
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(config.ready_poll_interval)

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for Keycloak token endpoint. Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out waiting for Keycloak token endpoint. Last error: {last_error!r}."
    )


# ==============================================================================
# Obtain a Keycloak access token for authenticated API requests in tests.
# ------------------------------------------------------------------------------
def _wait_for_keycloak_access_token(
    request_context: APIRequestContext,
    config: IntegrationConfig,
) -> str:
    deadline = time.time() + config.ready_timeout
    last_response: APIResponse | None = None
    last_error: Exception | None = None
    form_data = {
        "grant_type": "password",
        "client_id": config.keycloak_client_id,
        "username": config.keycloak_username,
        "password": config.keycloak_password,
    }
    if config.keycloak_client_secret:
        form_data["client_secret"] = config.keycloak_client_secret

    while time.time() < deadline:
        try:
            response = request_context.post(
                config.keycloak_token_url,
                form=form_data,
                headers={"X-Forwarded-Proto": "https", "X-Forwarded-Port": "443"},
                timeout=max(1, int(config.request_timeout * 1000)),
            )
            last_response = response
            if response.status == 200:
                payload = response.json()
                token = payload.get("access_token")
                if token:
                    return token
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(config.ready_poll_interval)

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for Keycloak access token. Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out waiting for Keycloak access token. Last error: {last_error!r}."
    )


# ==============================================================================
# Wait until a specific Airflow DAG endpoint is available.
# ------------------------------------------------------------------------------
def _wait_for_airflow_dag(
    request_context: APIRequestContext,
    config: IntegrationConfig,
    access_token: str,
    dag_id: str,
) -> None:
    deadline = time.time() + config.ready_timeout
    url = f"{config.airflow_base_url}/workflows/api/v2/dags/{dag_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = request_context.get(
                url,
                headers=headers,
                timeout=max(1, int(config.request_timeout * 1000)),
            )
            last_response = response
            if response.status == 200:
                return
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(config.ready_poll_interval)

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for DAG '{dag_id}'. Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out waiting for DAG '{dag_id}'. Last error: {last_error!r}."
    )


# ==============================================================================
# Ensure a target Airflow DAG is unpaused before integration tests run.
# ------------------------------------------------------------------------------
def _ensure_airflow_dag_unpaused(
    request_context: APIRequestContext,
    config: IntegrationConfig,
    access_token: str,
    dag_id: str,
) -> None:
    deadline = time.time() + config.ready_timeout
    url = f"{config.airflow_base_url}/workflows/api/v2/dags/{dag_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = request_context.get(
                url,
                headers=headers,
                timeout=max(1, int(config.request_timeout * 1000)),
            )
            last_response = response
            if response.status != 200:
                time.sleep(config.ready_poll_interval)
                continue

            payload = response.json()
            if not bool(payload.get("is_paused", False)):
                return

            patch_response = request_context.fetch(
                url,
                method="PATCH",
                headers=headers,
                data={"is_paused": False},
                timeout=max(1, int(config.request_timeout * 1000)),
                fail_on_status_code=False,
            )
            last_response = patch_response
            if patch_response.status == 200:
                time.sleep(config.ready_poll_interval)
                continue
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
        time.sleep(config.ready_poll_interval)

    if last_response is not None:
        raise AssertionError(
            f"Timed out unpausing DAG '{dag_id}'. Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out unpausing DAG '{dag_id}'. Last error: {last_error!r}."
    )


# ==============================================================================
# Copy the sample batch fixture into terraform/uploads for file:// ingest tests.
# ------------------------------------------------------------------------------
def _prepare_local_batch_upload() -> None:
    sample_batch_source = next(
        (candidate for candidate in SAMPLE_BATCH_SOURCE_CANDIDATES if candidate.exists()),
        None,
    )
    if sample_batch_source is None:
        checked_paths = ", ".join(str(path) for path in SAMPLE_BATCH_SOURCE_CANDIDATES)
        raise AssertionError(
            f"Missing batch fixture source file. Checked: {checked_paths}"
        )
    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sample_batch_source, LOCAL_BATCH_UPLOAD)
    except PermissionError as exc:
        # In some CI environments the uploads bind mount may be owned by a
        # container user. The file:// test asserts DAG-trigger wiring only.
        print(
            f"Warning: could not prepare local upload fixture at "
            f"{LOCAL_BATCH_UPLOAD}: {exc}. Continuing without local file copy."
        )


# ==============================================================================
# Build session-level integration config from CLI flags and environment values.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def config(pytestconfig: pytest.Config) -> IntegrationConfig:
    base_url = pytestconfig.getoption("--integration-base-url").rstrip("/")
    airflow_base_url = os.getenv(
        "INTEGRATION_AIRFLOW_BASE_URL",
        f"http://localhost:{os.getenv('INTEGRATION_AIRFLOW_PORT', '18090')}",
    ).rstrip("/")
    request_timeout = float(os.getenv("INTEGRATION_REQUEST_TIMEOUT", "10"))
    keycloak_base_url = os.getenv(
        "INTEGRATION_KEYCLOAK_BASE_URL",
        f"http://localhost:{os.getenv('INTEGRATION_KEYCLOAK_PORT', '18080')}",
    ).rstrip("/")

    keycloak_token_url = os.getenv(
        "INTEGRATION_KEYCLOAK_TOKEN_URL",
        f"{keycloak_base_url}/keycloak/realms/bluecore/protocol/openid-connect/token",
    )
    airflow_token_url = os.getenv(
        "INTEGRATION_AIRFLOW_TOKEN_URL",
        f"{airflow_base_url}/workflows/auth/token",
    )

    keycloak_client_secret = os.getenv("INTEGRATION_KEYCLOAK_CLIENT_SECRET")
    if keycloak_client_secret == "":
        keycloak_client_secret = None

    return IntegrationConfig(
        base_url=base_url,
        airflow_base_url=airflow_base_url,
        request_timeout=request_timeout,
        ready_timeout=pytestconfig.getoption("--integration-ready-timeout"),
        ready_poll_interval=float(os.getenv("INTEGRATION_READY_POLL_INTERVAL", "3")),
        keycloak_client_id=os.getenv("INTEGRATION_KEYCLOAK_CLIENT_ID", "bluecore_api"),
        keycloak_client_secret=keycloak_client_secret,
        keycloak_username=os.getenv("INTEGRATION_KEYCLOAK_USERNAME", "developer"),
        keycloak_password=os.getenv("INTEGRATION_KEYCLOAK_PASSWORD", "123456"),
        airflow_username=os.getenv("INTEGRATION_AIRFLOW_USERNAME", "airflow"),
        airflow_password=os.getenv("INTEGRATION_AIRFLOW_PASSWORD", "airflow"),
        keycloak_token_url=keycloak_token_url,
        airflow_token_url=airflow_token_url,
    )


# ==============================================================================
# Provide a shared Playwright API request context for HTTP calls in tests.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def request_context(playwright: Playwright) -> APIRequestContext:
    context = playwright.request.new_context(ignore_https_errors=True)
    try:
        yield context
    finally:
        context.dispose()


# ==============================================================================
# Block test start until API, Airflow, and Keycloak are reachable and ready.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def wait_for_stack(
    config: IntegrationConfig,
    request_context: APIRequestContext,
) -> None:
    _prepare_local_batch_upload()

    checks: list[tuple[str, set[int]]] = [
        (f"{config.base_url}/", {200}),
        (f"{config.base_url}/openapi.json", {200}),
        (f"{config.airflow_base_url}/workflows/api/v2/version", {200}),
    ]

    for url, statuses in checks:
        _wait_for_status(
            request_context=request_context,
            url=url,
            acceptable_statuses=statuses,
            timeout_seconds=config.ready_timeout,
            poll_interval_seconds=config.ready_poll_interval,
            request_timeout=config.request_timeout,
        )

    _wait_for_keycloak_token_endpoint(request_context, config)
    airflow_token = _wait_for_airflow_token(request_context, config)
    _wait_for_airflow_dag(request_context, config, airflow_token, "resource_loader")
    _wait_for_airflow_dag(request_context, config, airflow_token, "monitor_institutions_exports")
    _ensure_airflow_dag_unpaused(request_context, config, airflow_token, "resource_loader")
    _ensure_airflow_dag_unpaused(request_context, config, airflow_token, "monitor_institutions_exports")


# ==============================================================================
# Provide a fresh Keycloak bearer token for tests that require auth.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="function")
def keycloak_access_token(
    config: IntegrationConfig,
    request_context: APIRequestContext,
) -> str:
    return _wait_for_keycloak_access_token(request_context, config)


# ==============================================================================
# Provide a fresh Airflow bearer token for tests that call Airflow APIs.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="function")
def airflow_access_token(
    config: IntegrationConfig,
    request_context: APIRequestContext,
) -> str:
    return _wait_for_airflow_token(request_context, config)
