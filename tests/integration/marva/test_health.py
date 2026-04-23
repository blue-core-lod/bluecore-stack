from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import APIRequestContext

from tests.integration.support.http import get, get_with_retry
from tests.integration.support.logging import log_expected_actual, log_header

def _marva_base_url() -> str:
    return os.getenv("INTEGRATION_MARVA_BASE_URL", "http://localhost/marva").rstrip("/")

def _middleware_base_url() -> str:
    return os.getenv(
        "INTEGRATION_MARVA_MIDDLEWARE_BASE_URL",
        "http://localhost/marva/util",
    ).rstrip("/")


def _expected_callback_url() -> str:
    return os.getenv(
        "BLUECORE_STACK_KEYCLOAK_REDIRECT_URI",
        "http://localhost/marva/util/auth/callback",
    ).rstrip("/")


def _expected_status(env_name: str, default: int) -> int:
    return int(os.getenv(env_name, str(default)))


# Confirms the primary /marva route responds successfully in full-stack mode.
def test_marva_route_is_reachable(request_context: APIRequestContext, config):
    log_header("Marva route reachability")
    marva_url = _marva_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_EXPECT_STATUS", 200)
    response = get_with_retry(
        request_context=request_context,
        url=f"{marva_url}/",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    log_expected_actual("status code", expected_status, response.status)
    assert response.status == expected_status


# Verifies /marva serves HTML content.
def test_marva_route_serves_html(request_context: APIRequestContext, config):
    log_header("Marva response semantics")
    marva_url = _marva_base_url()
    response = get(
        request_context=request_context,
        url=f"{marva_url}/",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert response.status == _expected_status("INTEGRATION_MARVA_EXPECT_STATUS", 200)
    content_type = response.headers.get("content-type", "")
    body = response.text().lower()
    log_expected_actual("content-type contains text/html", True, "text/html" in content_type.lower())
    assert "text/html" in content_type.lower()
    assert "<html" in body or "<!doctype html" in body


# Confirms the middleware base path is reachable and not failing with 5xx.
def test_marva_middleware_route_is_reachable(request_context: APIRequestContext, config):
    log_header("Marva middleware route reachability")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_MIDDLEWARE_EXPECT_STATUS", 404)
    response = get_with_retry(
        request_context=request_context,
        url=f"{middleware_url}/",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    log_expected_actual("status code", expected_status, response.status)
    assert response.status == expected_status


# Validates SSO login redirect contains required OAuth parameters and callback URI.
def test_marva_login_redirect_contract(request_context: APIRequestContext, config):
    log_header("Marva login redirect contract")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_LOGIN_EXPECT_STATUS", 302)
    response = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/login",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    log_expected_actual("status code", expected_status, response.status)
    assert response.status == expected_status

    location = response.headers.get("location", "")
    log_expected_actual("redirect location header", "present", bool(location))
    assert location

    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    redirect_uri = query.get("redirect_uri", [""])[0].rstrip("/")
    client_id = query.get("client_id", [""])[0]
    response_type = query.get("response_type", [""])[0]
    state = query.get("state", [""])[0]

    assert client_id
    assert redirect_uri == _expected_callback_url()
    assert response_type in {"code", "id_token token", "code id_token"}
    assert state


# Ensures callback rejects missing OAuth params with the expected status code.
def test_marva_callback_rejects_missing_params(request_context: APIRequestContext, config):
    log_header("Marva callback missing params")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_CALLBACK_MISSING_EXPECT_STATUS", 400)
    missing_params = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/callback",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    log_expected_actual("callback status (missing params)", expected_status, missing_params.status)
    assert missing_params.status == expected_status


# Ensures callback rejects invalid OAuth params with the expected status code.
def test_marva_callback_rejects_invalid_params(request_context: APIRequestContext, config):
    log_header("Marva callback invalid params")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_CALLBACK_INVALID_EXPECT_STATUS", 400)
    invalid_params = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/callback?code=invalid-code&state=invalid-state",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    log_expected_actual("callback status (invalid params)", expected_status, invalid_params.status)
    assert invalid_params.status == expected_status


# Checks that login initiation emits an explicit OAuth state parameter.
def test_marva_login_sets_oauth_state_param(request_context: APIRequestContext, config):
    log_header("Marva middleware oauth state")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_LOGIN_EXPECT_STATUS", 302)
    response = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/login",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert response.status == expected_status

    location = response.headers.get("location", "")
    location_state = parse_qs(urlparse(location).query).get("state", [""])[0]
    log_expected_actual("oauth state query param", "present", bool(location_state))
    assert location_state


# Confirms proxy-generated redirect URI uses public localhost origin, not internal hosts.
def test_marva_proxy_origin_contract_on_login_redirect(
    request_context: APIRequestContext, config
):
    log_header("Marva proxy/header contract")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_LOGIN_EXPECT_STATUS", 302)
    response = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/login",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert response.status == expected_status
    location = response.headers.get("location", "")
    assert location

    redirect_uri = parse_qs(urlparse(location).query).get("redirect_uri", [""])[0]
    log_expected_actual("redirect_uri", "present", bool(redirect_uri))
    assert redirect_uri
    assert redirect_uri.startswith("http://localhost/")
    assert "marva-keycloak-middleware" not in redirect_uri
    assert "keycloak:8080" not in redirect_uri


# Verifies unauthenticated logout is guarded (redirect to auth or explicit denial).
def test_marva_middleware_logout_requires_auth_or_redirects(
    request_context: APIRequestContext, config
):
    log_header("Marva auth guard behavior")
    middleware_url = _middleware_base_url()
    expected_status = _expected_status("INTEGRATION_MARVA_LOGOUT_EXPECT_STATUS", 302)
    response = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/logout",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    log_expected_actual("status code", expected_status, response.status)
    assert response.status == expected_status


# Middleware CORS preflight
def test_marva_middleware_cors_preflight(request_context: APIRequestContext, config):
    log_header("Marva Middleware CORS check")
    middleware_url = _middleware_base_url()
    resp = request_context.fetch(
        f"{middleware_url}/auth/login",
        method="OPTIONS",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "GET",
        },
        timeout=config.request_timeout * 1000,
        fail_on_status_code=False,
    )
    assert resp.status in {200, 204}
    h = {k.lower(): v for k, v in resp.headers.items()}
    assert "access-control-allow-origin" in h
    assert "access-control-allow-methods" in h


# Unknown util endpoint returns controlled JSON warning/error (not HTML/500)
def test_marva_middleware_unknown_util_endpoint_shape(
        request_context: APIRequestContext, config
):
    log_header("Marva Middleware Unknown util endpoint")
    middleware_url = _middleware_base_url()
    resp = get(
        request_context=request_context,
        url=f"{middleware_url}/definitely-not-real-endpoint",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert resp.status in {404, 502}
    content_type = resp.headers.get("content-type", "").lower()
    assert "application/json" in content_type
    body = resp.json()
    assert "warning" in body or "error" in body


# Auth refresh without bearer token is rejected
def test_marva_refresh_requires_bearer(request_context: APIRequestContext, config):
    log_header("Marva bearer token refresh")
    middleware_url = _middleware_base_url()
    resp = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/refresh",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert resp.status in {401, 400}
    data = resp.json()
    assert "error" in data


# Login redirect points to expected Keycloak realm/endpoint
def test_marva_login_redirect_targets_keycloak_realm(
        request_context: APIRequestContext, config
):
    log_header("Marva login redirect points to expected Keycloak endpoint")
    middleware_url = _middleware_base_url()
    resp = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/login",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert resp.status == _expected_status("INTEGRATION_MARVA_LOGIN_EXPECT_STATUS", 302)
    location = resp.headers.get("location", "")
    assert "/realms/bluecore/protocol/openid-connect/auth" in location


# Wrong credentials should produce OAuth callback error and never mint token
def test_marva_callback_oauth_error_does_not_authenticate(
        request_context: APIRequestContext, config
):
    log_header("Marva wrong credentials produce OAuth error")
    middleware_url = _middleware_base_url()
    resp = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/callback?error=access_denied&state=fake-state",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    assert resp.status in {302, 400}

    location = resp.headers.get("location", "")
    if location:
        parsed = urlparse(location)
        query = parse_qs(parsed.query)
        assert query.get("auth_error", [""])[0] == "access_denied"
        assert "token" not in query


# Wrong credentials scenario should never return successful callback payload
def test_marva_callback_invalid_grant_path_is_not_success(
        request_context: APIRequestContext, config
):
    log_header("Marva Wrong credentials should never be successful")
    middleware_url = _middleware_base_url()
    resp = get(
        request_context=request_context,
        url=f"{middleware_url}/auth/callback?code=bad-code&state=bad-state",
        timeout_seconds=config.request_timeout,
        max_redirects=0,
        fail_on_status_code=False,
    )
    # Contract can be 400 (invalid state/code) or 502 (upstream token exchange failure)
    assert resp.status in {400, 502}
    text = resp.text().lower()
    assert "token exchange failed" in text or "invalid oauth callback" in text or "error" in text
