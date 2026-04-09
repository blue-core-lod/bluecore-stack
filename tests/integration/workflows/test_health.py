from __future__ import annotations

from playwright.sync_api import APIRequestContext

from tests.integration.support.http import get_with_retry
from tests.integration.support.logging import log_expected_actual, log_header, log_json


# ========================================================================
# Verify Airflow version endpoint is reachable through workflow gateway.
# ------------------------------------------------------------------------
def test_airflow_version_endpoint_is_reachable(
    config,
    request_context: APIRequestContext,
):
    log_header("Airflow version endpoint")
    response = get_with_retry(
        request_context=request_context,
        url=f"{config.airflow_base_url}/workflows/api/v2/version",
        request_timeout=config.request_timeout,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    payload = response.json()
    log_json("Airflow version payload", payload)
    log_expected_actual("payload.version", "present", payload.get("version"))
    assert "version" in payload
