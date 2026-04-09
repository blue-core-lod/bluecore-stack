from __future__ import annotations

import json
from uuid import uuid4

import pytest
from playwright.sync_api import APIRequestContext

from tests.integration.support.sample_data import build_instance_jsonld, build_work_jsonld
from tests.integration.support.http import get, post, send_request
from tests.integration.support.keycloak import (
    decode_jwt_payload_without_verification,
    get_password_grant_access_token,
    request_password_grant_token,
)
from tests.integration.support.logging import log_expected_actual, log_header, log_json


# ========================================================================
# Verify API write endpoints require authentication.
# ------------------------------------------------------------------------
def test_api_write_endpoint_requires_auth(
    config,
    request_context: APIRequestContext,
):
    log_header("API write requires auth")
    response = post(
        request_context,
        f"{config.base_url}/batches/",
        json_payload={"uri": "file:///opt/airflow/uploads/integration-test.jsonld"},
        timeout_seconds=config.request_timeout,
    )
    log_expected_actual("status code", 401, response.status)
    log_expected_actual("request URL", f"{config.base_url}/batches/", f"{config.base_url}/batches/")
    assert response.status == 401, response.text()


# ========================================================================
# Verify Keycloak password grant returns a valid bearer token payload.
# ------------------------------------------------------------------------
def test_keycloak_password_grant_returns_expected_token_payload(
    config,
    request_context: APIRequestContext,
) -> None:
    log_header("Keycloak password grant token payload")
    response = request_password_grant_token(request_context, config)
    log_expected_actual("token endpoint status", 200, response.status)
    assert response.status == 200, response.text()

    payload = response.json()
    log_json(
        "Keycloak token response summary",
        {
            "token_type": payload.get("token_type"),
            "expires_in": payload.get("expires_in"),
            "has_access_token": bool(payload.get("access_token")),
            "has_refresh_token": bool(payload.get("refresh_token")),
        },
    )
    assert payload.get("token_type") == "Bearer"
    assert isinstance(payload.get("expires_in"), int) and payload["expires_in"] > 0
    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    assert isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]

    decoded = decode_jwt_payload_without_verification(payload["access_token"])
    log_json(
        "Decoded access token claims summary",
        {
            "preferred_username": decoded.get("preferred_username"),
            "iss": decoded.get("iss"),
            "aud": decoded.get("aud"),
            "exp": decoded.get("exp"),
        },
    )
    assert decoded.get("preferred_username") == config.keycloak_username
    assert decoded.get("iss")
    assert decoded.get("exp")


# ========================================================================
# Verify invalid Keycloak client identifiers are rejected by token endpoint.
# ------------------------------------------------------------------------
def test_keycloak_password_grant_rejects_invalid_client_id(
    config,
    request_context: APIRequestContext,
) -> None:
    log_header("Keycloak password grant rejects invalid client")
    response = request_password_grant_token(
        request_context,
        config,
        client_id="not-a-real-client-id",
    )
    log_expected_actual("token endpoint status", "400 or 401", response.status)
    assert response.status in {400, 401}, response.text()


# ========================================================================
# Verify malformed authorization headers are rejected for API writes.
# ------------------------------------------------------------------------
def test_api_write_rejects_malformed_authorization_header(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    log_header("API write rejects malformed auth header")
    response = post(
        request_context,
        f"{config.base_url}/batches/",
        json_payload={"uri": "file:///opt/airflow/uploads/integration-test.jsonld"},
        headers={"Authorization": f"Token {keycloak_access_token}"},
        timeout_seconds=config.request_timeout,
    )
    log_expected_actual("status code", 401, response.status)
    assert response.status == 401, response.text()


# ========================================================================
# Verify airflow auth tokens cannot be used as API write bearer tokens.
# ------------------------------------------------------------------------
def test_api_write_rejects_airflow_token_as_bearer(
    config,
    request_context: APIRequestContext,
    airflow_access_token,
) -> None:
    log_header("API write rejects airflow bearer token")
    response = post(
        request_context,
        f"{config.base_url}/batches/",
        json_payload={"uri": "file:///opt/airflow/uploads/integration-test.jsonld"},
        headers={"Authorization": f"Bearer {airflow_access_token}"},
        timeout_seconds=config.request_timeout,
    )
    log_expected_actual("status code", 401, response.status)
    assert response.status == 401, response.text()


# ========================================================================
# Verify key public GET endpoints stay accessible without auth headers.
# ------------------------------------------------------------------------
def test_public_get_endpoints_accessible_without_auth(
    config,
    request_context: APIRequestContext,
) -> None:
    log_header("Public GET endpoints accessible without auth")
    urls = [
        f"{config.base_url}/",
        f"{config.base_url}/search/",
        f"{config.base_url}/resources/",
    ]
    for url in urls:
        response = get(
            request_context,
            url,
            timeout_seconds=config.request_timeout,
        )
        log_expected_actual(f"GET {url} status", 200, response.status)
        assert response.status == 200, response.text()


@pytest.mark.parametrize(
    ("username", "endpoint_key", "expected_status"),
    [
        ("developer", "batches", 200),
        ("developer", "works", 201),
        ("developer", "instances", 201),
        ("developer", "resources", 201),
        ("developer", "export", 200),
        ("dev_op", "batches", 403),
        ("dev_op", "works", 403),
        ("dev_op", "instances", 403),
        ("dev_op", "resources", 403),
        ("dev_op", "export", 403),
        ("dev_public", "batches", 403),
        ("dev_public", "works", 403),
        ("dev_public", "instances", 403),
        ("dev_public", "resources", 403),
        ("dev_public", "export", 403),
        ("dev_user", "batches", 403),
        ("dev_user", "works", 403),
        ("dev_user", "instances", 403),
        ("dev_user", "resources", 403),
        ("dev_user", "export", 403),
        ("dev_viewer", "batches", 403),
        ("dev_viewer", "works", 403),
        ("dev_viewer", "instances", 403),
        ("dev_viewer", "resources", 403),
        ("dev_viewer", "export", 403),
    ],
)
# ========================================================================
# Verify Keycloak role matrix for API write endpoints.
# ------------------------------------------------------------------------
def test_keycloak_role_matrix_on_api_write_endpoints(
    config,
    request_context: APIRequestContext,
    username: str,
    endpoint_key: str,
    expected_status: int,
) -> None:
    token = get_password_grant_access_token(
        request_context,
        config,
        username=username,
        password="123456",
    )
    decoded = decode_jwt_payload_without_verification(token)
    realm_roles = sorted(decoded.get("realm_access", {}).get("roles", []))

    marker = uuid4().hex
    if endpoint_key == "batches":
        method = "POST"
        path = "/batches/"
        request_kwargs = {"json": {"uri": "file:///opt/airflow/uploads/integration-test.jsonld"}}
    elif endpoint_key == "works":
        method = "POST"
        path = "/works/"
        request_kwargs = {"json": {"data": build_work_jsonld(marker)}}
    elif endpoint_key == "instances":
        method = "POST"
        path = "/instances/"
        request_kwargs = {"json": {"data": build_instance_jsonld(marker), "work_id": None}}
    elif endpoint_key == "resources":
        method = "POST"
        path = "/resources/"
        request_kwargs = {
            "json": {
                "uri": f"https://example.org/resources/{marker}",
                "is_profile": True,
                "data": json.dumps({"label": f"role-matrix-{marker}"}),
            }
        }
    elif endpoint_key == "export":
        method = "POST"
        path = "/export/"
        request_kwargs = {"json": {"instance_uri": f"https://example.org/instances/{marker}"}}
    else:
        raise AssertionError(f"Unknown endpoint key: {endpoint_key}")

    response = send_request(
        request_context,
        method,
        f"{config.base_url}{path}",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {token}"},
        **request_kwargs,
    )

    log_header(f"Role matrix: {username} -> {endpoint_key}")
    log_json(
        "Role matrix subject summary",
        {
            "username": decoded.get("preferred_username"),
            "realm_roles": realm_roles,
            "endpoint": endpoint_key,
            "expected_status": expected_status,
            "actual_status": response.status,
        },
    )
    log_expected_actual("status code", expected_status, response.status)
    assert response.status == expected_status, response.text()
