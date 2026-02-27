from __future__ import annotations

import base64
import json

from playwright.sync_api import APIRequestContext
from playwright.sync_api import APIResponse

from tests.integration.support.http import post


# ========================================================================
# Request a Keycloak password-grant token with configurable credentials.
# ------------------------------------------------------------------------
def request_password_grant_token(
    request_context: APIRequestContext,
    config,
    *,
    username: str | None = None,
    password: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> APIResponse:
    form_data: dict[str, str] = {
        "grant_type": "password",
        "client_id": client_id or config.keycloak_client_id,
        "username": username or config.keycloak_username,
        "password": password or config.keycloak_password,
    }
    if client_secret is not None:
        form_data["client_secret"] = client_secret
    elif config.keycloak_client_secret:
        form_data["client_secret"] = config.keycloak_client_secret

    return post(
        request_context,
        config.keycloak_token_url,
        form_payload=form_data,
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Port": "443"},
        timeout_seconds=config.request_timeout,
    )


# ========================================================================
# Request and return only the access_token for a Keycloak password grant.
# ------------------------------------------------------------------------
def get_password_grant_access_token(
    request_context: APIRequestContext,
    config,
    *,
    username: str | None = None,
    password: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> str:
    response = request_password_grant_token(
        request_context,
        config,
        username=username,
        password=password,
        client_id=client_id,
        client_secret=client_secret,
    )
    assert response.status == 200, response.text()
    payload = response.json()
    token = payload.get("access_token")
    assert isinstance(token, str) and token, f"Missing access_token: {payload}"
    return token


# ========================================================================
# Decode JWT payload locally (no signature verification) for assertions.
# ------------------------------------------------------------------------
def decode_jwt_payload_without_verification(token: str) -> dict:
    token_parts = token.split(".")
    assert len(token_parts) >= 2, "Token must have at least header and payload"

    payload = token_parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
    return json.loads(decoded)
