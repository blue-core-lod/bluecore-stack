from __future__ import annotations

from playwright.sync_api import APIRequestContext

from tests.integration.support.logging import log_expected_actual, log_header


# ========================================================================
# Verify Keycloak token endpoint is reachable and rejects bad credentials.
# ------------------------------------------------------------------------
def test_keycloak_token_endpoint_is_reachable(
    config,
    request_context: APIRequestContext,
):
    log_header("Keycloak token endpoint")
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
    log_expected_actual("status code", "400 or 401", response.status)
    assert response.status in {400, 401}
