from __future__ import annotations

import os

import pytest
from playwright.sync_api import APIRequestContext

from tests.integration.support.http import get, get_with_retry
from tests.integration.support.logging import log_expected_actual, log_header

# Sinopia and Nginx only run in the full-stack integration profile
# (compose-integration-test.yaml puts them under "integration-full", which the
# runner enables by default via INTEGRATION_FULL_STACK=1). Skip cleanly when a
# lightweight run omits them.
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_FULL_STACK", "1") != "1",
    reason="Sinopia and Nginx only run in full-stack integration mode",
)


def _sinopia_base_url() -> str:
    return os.getenv("INTEGRATION_SINOPIA_BASE_URL", "http://localhost/sinopia").rstrip("/")


def _bluecore_base_url() -> str:
    # The origin Sinopia is configured to call its backend through
    # (SINOPIA_API_BASE_URL=http://localhost/api).
    return os.getenv("INTEGRATION_BLUECORE_URL", "http://localhost").rstrip("/")


# ========================================================================
# The Sinopia editor route is reachable through Nginx.
# ------------------------------------------------------------------------
def test_sinopia_route_is_reachable(request_context: APIRequestContext, config):
    log_header("Sinopia route reachability")
    response = get_with_retry(
        request_context=request_context,
        url=f"{_sinopia_base_url()}/",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200


# ========================================================================
# The Sinopia route serves the editor's HTML shell.
# ------------------------------------------------------------------------
def test_sinopia_route_serves_html(request_context: APIRequestContext, config):
    log_header("Sinopia serves HTML")
    response = get(
        request_context=request_context,
        url=f"{_sinopia_base_url()}/",
        timeout_seconds=config.request_timeout,
        fail_on_status_code=False,
    )
    assert response.status == 200
    content_type = response.headers.get("content-type", "").lower()
    body = response.text().lower()
    log_expected_actual("content-type contains text/html", True, "text/html" in content_type)
    assert "text/html" in content_type
    assert "<html" in body or "<!doctype html" in body


# ========================================================================
# The profiles backend Sinopia relies on is reachable through Nginx at the
# same origin Sinopia is configured with (/api). Guards the editor->API wiring.
# ------------------------------------------------------------------------
def test_sinopia_backend_search_profile_reachable_via_nginx(
    request_context: APIRequestContext, config
):
    log_header("Sinopia backend /api/search/profile via Nginx")
    response = get_with_retry(
        request_context=request_context,
        url=f"{_bluecore_base_url()}/api/search/profile",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    payload = response.json()
    assert "results" in payload and "total" in payload


def test_sinopia_backend_profiles_reachable_via_nginx(
    request_context: APIRequestContext, config
):
    log_header("Sinopia backend /api/profiles/ via Nginx")
    response = get_with_retry(
        request_context=request_context,
        url=f"{_bluecore_base_url()}/api/profiles/",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    assert "profiles" in response.json()
