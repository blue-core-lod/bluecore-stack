from __future__ import annotations

import time

from playwright.sync_api import APIRequestContext
from playwright.sync_api import APIResponse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.integration.support.http import get


# ========================================================================
# Poll search endpoint until both work and instance UUIDs exist.
# ------------------------------------------------------------------------
def wait_for_loaded_resource_uuids(
    *,
    request_context: APIRequestContext,
    base_url: str,
    request_timeout: float,
    query: str,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> tuple[str, str]:
    deadline = time.time() + timeout_seconds
    last_results: list[dict] = []

    while time.time() < deadline:
        response = get(
            request_context,
            f"{base_url}/search/",
            timeout_seconds=request_timeout,
            params={"q": query, "type": "all", "limit": 20, "offset": 0},
        )
        assert response.status == 200, response.text()
        payload = response.json()
        results = payload.get("results", [])
        last_results = results if isinstance(results, list) else []

        works = [item for item in last_results if item.get("type") == "works" and item.get("uuid")]
        instances = [item for item in last_results if item.get("type") == "instances" and item.get("uuid")]
        if works and instances:
            return str(works[0]["uuid"]), str(instances[0]["uuid"])

        time.sleep(poll_interval_seconds)

    raise AssertionError(
        f"Could not find both work and instance UUIDs in search results for query '{query}'. "
        f"Last results: {last_results[:3]}"
    )


# ========================================================================
# Poll Airflow until resource_loader DAG run reaches success.
# ------------------------------------------------------------------------
def wait_for_resource_loader_dag_run_success(
    *,
    request_context: APIRequestContext,
    airflow_base_url: str,
    dag_run_id: str,
    airflow_access_token: str,
    request_timeout: float,
    timeout_seconds: float = 480.0,
    poll_interval_seconds: float = 2.0,
) -> None:
    deadline = time.time() + timeout_seconds
    dag_run_url = (
        f"{airflow_base_url}/workflows/api/v2/dags/resource_loader/dagRuns/{dag_run_id}"
    )
    headers = {"Authorization": f"Bearer {airflow_access_token}"}
    terminal_failure_states = {"failed", "upstream_failed", "removed"}
    last_state = "unknown"

    while time.time() < deadline:
        response = get(
            request_context,
            dag_run_url,
            headers=headers,
            timeout_seconds=request_timeout,
            fail_on_status_code=False,
        )
        if response.status in {404, 429, 500, 502, 503, 504}:
            time.sleep(poll_interval_seconds)
            continue
        assert response.status == 200, response.text()

        payload = response.json()
        state = str(payload.get("state", "")).lower()
        last_state = state or "unknown"
        if state == "success":
            return
        if state in terminal_failure_states:
            raise AssertionError(
                f"resource_loader DAG run {dag_run_id} finished in failure state '{state}'. "
                f"Payload: {payload}"
            )
        time.sleep(poll_interval_seconds)

    raise AssertionError(
        f"Timed out waiting for resource_loader DAG run {dag_run_id} to succeed. "
        f"Last state: {last_state}"
    )


# ========================================================================
# Wait for DAG run to complete in expected state or fail fast.
# ------------------------------------------------------------------------
def wait_for_dag_run_completion(
    *,
    request_context: APIRequestContext,
    base_url: str,
    dag_id: str,
    dag_run_id: str,
    access_token: str,
    expected_state: str = "success",
    timeout_seconds: int,
    poll_interval_seconds: float,
    request_timeout: float,
) -> dict:
    deadline = time.time() + timeout_seconds
    url = f"{base_url}/workflows/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    last_state = "unknown"
    last_error: Exception | None = None
    terminal_failure_states = {"failed", "upstream_failed", "removed"}

    def _fetch_task_instance_states() -> list[dict]:
        task_instances_url = f"{base_url}/workflows/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances"
        try:
            task_response = get(
                request_context,
                task_instances_url,
                headers=headers,
                timeout_seconds=request_timeout,
            )
        except (PlaywrightError, PlaywrightTimeoutError):
            return []
        if task_response.status != 200:
            return []
        payload = task_response.json()
        task_instances = payload.get("task_instances", [])
        if not isinstance(task_instances, list):
            return []
        return [
            {
                "task_id": item.get("task_id"),
                "state": item.get("state"),
                "try_number": item.get("try_number"),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
            }
            for item in task_instances
        ]

    while time.time() < deadline:
        try:
            response = get(
                request_context,
                url,
                headers=headers,
                timeout_seconds=request_timeout,
            )
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)
            continue

        if response.status == 200:
            payload = response.json()
            state = str(payload.get("state", "")).lower()
            last_state = state or "unknown"
            if state == expected_state:
                return payload
            if state in terminal_failure_states:
                task_states = _fetch_task_instance_states()
                raise AssertionError(
                    f"DAG run {dag_run_id} for {dag_id} ended in state '{state}'. "
                    f"Payload: {payload}. Task instances: {task_states}"
                )
            time.sleep(poll_interval_seconds)
            continue

        if response.status in {404, 429, 500, 502, 503, 504}:
            time.sleep(poll_interval_seconds)
            continue

        raise AssertionError(f"Unexpected status while fetching DAG run: {response.text()}")

    raise AssertionError(
        f"Timed out waiting for DAG run {dag_run_id} on {dag_id}. Last state: {last_state}. Last error: {last_error!r}."
    )


# ========================================================================
# Wait until DAG run record is visible in Airflow API.
# ------------------------------------------------------------------------
def wait_for_dag_run_exists(
    *,
    request_context: APIRequestContext,
    base_url: str,
    dag_id: str,
    dag_run_id: str,
    access_token: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
    request_timeout: float,
) -> dict:
    deadline = time.time() + timeout_seconds
    url = f"{base_url}/workflows/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = get(
                request_context,
                url,
                headers=headers,
                timeout_seconds=request_timeout,
            )
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)
            continue
        if response.status == 200:
            return response.json()
        if response.status in {404, 429, 500, 502, 503, 504}:
            time.sleep(poll_interval_seconds)
            continue
        raise AssertionError(f"Unexpected status while fetching DAG run: {response.text()}")

    raise AssertionError(
        f"Timed out waiting for DAG run {dag_run_id} on {dag_id} to exist. Last error: {last_error!r}."
    )


# ========================================================================
# Poll embeddings endpoint until at least one vector is available.
# ------------------------------------------------------------------------
def wait_for_non_empty_embeddings(
    *,
    request_context: APIRequestContext,
    url: str,
    request_timeout: float,
    timeout_seconds: int = 120,
    poll_interval_seconds: float = 2.0,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = get(
                request_context,
                url,
                timeout_seconds=request_timeout,
            )
            last_response = response
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)
            continue

        if response.status == 200:
            payload = response.json()
            if len(payload.get("embedding", [])) >= 1:
                return payload
            time.sleep(poll_interval_seconds)
            continue

        if response.status in {429, 500, 502, 503, 504}:
            time.sleep(poll_interval_seconds)
            continue

        raise AssertionError(
            f"Unexpected status while waiting for embeddings at {url}: "
            f"{response.status} {response.text()}"
        )

    if last_response is not None:
        raise AssertionError(
            f"Timed out waiting for non-empty embeddings at {url}. "
            f"Last status: {last_response.status}. Body: {last_response.text()}"
        )
    raise AssertionError(
        f"Timed out waiting for non-empty embeddings at {url}. Last error: {last_error!r}."
    )

