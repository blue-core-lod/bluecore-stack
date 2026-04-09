from __future__ import annotations

from playwright.sync_api import APIRequestContext

from tests.integration.support.http import get_with_retry
from tests.integration.support.logging import log_expected_actual, log_header, log_json


# ========================================================================
# Verify API root endpoint responds with expected service banner payload.
# ------------------------------------------------------------------------
def test_api_root_healthcheck(config, request_context: APIRequestContext):
    log_header("API root healthcheck")
    response = get_with_retry(
        request_context=request_context,
        url=f"{config.base_url}/",
        request_timeout=config.request_timeout,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    payload = response.json()
    log_json("API root payload", payload)
    log_expected_actual("payload.message", "Blue Core API", payload.get("message"))
    assert payload.get("message") == "Blue Core API"


# ========================================================================
# Verify OpenAPI document is reachable and exposes required route groups.
# ------------------------------------------------------------------------
def test_api_openapi_is_exposed(config, request_context: APIRequestContext):
    log_header("OpenAPI is exposed")
    response = get_with_retry(
        request_context=request_context,
        url=f"{config.base_url}/openapi.json",
        request_timeout=config.request_timeout,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    payload = response.json()
    log_expected_actual("paths include /batches/", "present", "/batches/" in payload.get("paths", {}))
    log_expected_actual("paths include /export/", "present", "/export/" in payload.get("paths", {}))
    assert "paths" in payload
    assert "/batches/" in payload["paths"]
    assert "/export/" in payload["paths"]
