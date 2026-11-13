from __future__ import annotations

import os
import re
from urllib.parse import urlencode

import pytest
from playwright.sync_api import APIRequestContext

from tests.integration.dancer._support import (
    DANCER_CLIENT_ID,
    SEEDED_WORKSPACE,
    SYNCED_WORKSPACE,
    auth_headers,
    dancer_api_url,
    dancer_url,
    keycloak_url,
    slugify,
    temp_workspace_name,
)
from tests.integration.support.http import get, get_with_retry, send_request
from tests.integration.support.logging import log_expected_actual, log_header

# HTTP checks for the DCTap Dancer (Marva's template editor) through Nginx.
# The dancer only runs in the full-stack integration profile, next to Marva;
# skip cleanly when a lightweight run omits it. Browser flows live in
# tests/ui/dancer and tests/ui/marva/test_dancer.py.
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_FULL_STACK", "1") != "1",
    reason="The DCTap Dancer and Nginx only run in full-stack integration mode",
)


# ==============================================================================
# Wait once for the dancer: on a fresh stack it seeds the default workspace
# from LC's profiles before it starts listening.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def dancer_ready(request_context: APIRequestContext, config) -> None:
    response = get_with_retry(
        request_context=request_context,
        url=f"{dancer_api_url()}/health",
        request_timeout=config.request_timeout,
        timeout_seconds=config.ready_timeout,
        poll_interval_seconds=config.ready_poll_interval,
    )
    assert response.status == 200, (
        f"DCTap Dancer never became healthy ({response.status})"
    )


def _get(request_context: APIRequestContext, config, url: str, **kwargs):
    return get(
        request_context=request_context,
        url=url,
        timeout_seconds=config.request_timeout,
        fail_on_status_code=False,
        **kwargs,
    )


def _serve_workspaces(request_context: APIRequestContext, config) -> list[dict]:
    response = _get(request_context, config, f"{dancer_api_url()}/serve/workspaces")
    assert response.status == 200
    return response.json()["data"]


# ========================================================================
# The editor is served under /marva/dancer/ as a single-page app whose
# scripts load from that same path (not the site root).
# ------------------------------------------------------------------------
def test_dancer_route_serves_the_editor(request_context: APIRequestContext, config):
    log_header("DCTap Dancer route serves the editor")
    response = _get(request_context, config, f"{dancer_url()}/")
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    assert "text/html" in response.headers.get("content-type", "").lower()

    body = response.text()
    assert '<div id="app"' in body
    script_sources = re.findall(r'<script[^>]+src="([^"]+)"', body)
    log_expected_actual("script sources under /marva/dancer/", True, script_sources)
    assert script_sources, "The editor page loads no scripts"
    assert all(src.startswith("/marva/dancer/") for src in script_sources), (
        script_sources
    )


# ========================================================================
# /marva/dancer (no trailing slash) redirects to /marva/dancer/.
# ------------------------------------------------------------------------
def test_dancer_route_without_slash_redirects(
    request_context: APIRequestContext, config
):
    log_header("DCTap Dancer adds the trailing slash")
    response = _get(request_context, config, dancer_url(), max_redirects=0)
    location = response.headers.get("location", "")
    log_expected_actual(
        "status, location", (301, "…/marva/dancer/"), (response.status, location)
    )
    assert response.status == 301
    assert location.endswith("/marva/dancer/")


# ========================================================================
# A deep link (e.g. a bookmarked workspace) is served the app, which then
# routes client-side, instead of a 404.
# ------------------------------------------------------------------------
def test_dancer_deep_link_serves_the_app(request_context: APIRequestContext, config):
    log_header("DCTap Dancer deep link")
    response = _get(request_context, config, f"{dancer_url()}/workspace/not-a-real-id")
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    assert '<div id="app"' in response.text()


# ========================================================================
# Health is public and reports ok.
# ------------------------------------------------------------------------
def test_dancer_health(request_context: APIRequestContext, config):
    log_header("DCTap Dancer health")
    response = _get(request_context, config, f"{dancer_api_url()}/health")
    assert response.status == 200
    assert response.json()["status"] == "ok"


# ========================================================================
# The public auth config points the frontend at Blue Core's Keycloak realm
# and client, through the public (browser-facing) Keycloak URL.
# ------------------------------------------------------------------------
def test_dancer_auth_config_points_at_bluecore_keycloak(
    request_context: APIRequestContext, config
):
    log_header("DCTap Dancer auth config")
    response = _get(request_context, config, f"{dancer_api_url()}/auth/config")
    assert response.status == 200
    settings = response.json()["data"]
    log_expected_actual("auth settings", "enabled, bluecore, bluecore_api", settings)
    assert settings["enabled"] is True
    assert settings["realm"] == "bluecore"
    assert settings["clientId"] == DANCER_CLIENT_ID
    assert settings["url"].rstrip("/") == keycloak_url()
    assert "keycloak:8080" not in settings["url"], (
        "Browser would get an internal Keycloak URL"
    )


# ========================================================================
# Keycloak accepts the dancer as a login redirect (the realm's bluecore_api
# client lists /marva/dancer/*), and still rejects unlisted redirects.
# ------------------------------------------------------------------------
def test_keycloak_allows_dancer_login_redirect(
    request_context: APIRequestContext, config
):
    log_header("Keycloak allows the dancer login redirect")
    auth_url = f"{keycloak_url()}/realms/bluecore/protocol/openid-connect/auth"

    def _login_page(redirect_uri: str):
        query = urlencode(
            {
                "client_id": DANCER_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid",
            }
        )
        return _get(request_context, config, f"{auth_url}?{query}")

    allowed = _login_page(f"{dancer_url()}/")
    log_expected_actual("dancer redirect -> login page", 200, allowed.status)
    assert allowed.status == 200
    assert "Invalid parameter: redirect_uri" not in allowed.text()

    rejected = _login_page(f"{dancer_url().rsplit('/marva/', 1)[0]}/not-an-app/")
    log_expected_actual("unlisted redirect rejected", 400, rejected.status)
    assert rejected.status == 400


# ========================================================================
# The editor API needs a login: reads and writes without a token are 401.
# ------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_dancer_api_requires_login(
    request_context: APIRequestContext, config, method: str
):
    log_header(f"DCTap Dancer API requires login ({method})")
    response = send_request(
        request_context,
        method,
        f"{dancer_api_url()}/workspaces",
        config.request_timeout,
        json={"name": temp_workspace_name()},
    )
    log_expected_actual("status code", 401, response.status)
    assert response.status == 401
    assert response.json()["code"] == "UNAUTHORIZED"


# ========================================================================
# A made-up bearer token is rejected.
# ------------------------------------------------------------------------
def test_dancer_api_rejects_an_invalid_token(
    request_context: APIRequestContext, config
):
    log_header("DCTap Dancer API rejects an invalid token")
    response = _get(
        request_context,
        config,
        f"{dancer_api_url()}/workspaces",
        headers=auth_headers("not.a.real-token"),
    )
    log_expected_actual("status code", 401, response.status)
    assert response.status == 401


# ========================================================================
# A real Keycloak token opens the API, and the seeded workspace is listed.
# ------------------------------------------------------------------------
def test_dancer_api_accepts_a_keycloak_token(
    request_context: APIRequestContext, config, keycloak_access_token: str
):
    log_header("DCTap Dancer API accepts a Keycloak token")
    response = _get(
        request_context,
        config,
        f"{dancer_api_url()}/workspaces",
        headers=auth_headers(keycloak_access_token),
    )
    log_expected_actual("status code", 200, response.status)
    assert response.status == 200
    names = [workspace["name"] for workspace in response.json()["data"]]
    log_expected_actual(f"'{SEEDED_WORKSPACE}' listed", True, names)
    assert SEEDED_WORKSPACE in names


# ========================================================================
# Downloads the browser opens directly authenticate with the token cookie,
# which the API honors for GET only. Tokens in the URL are never accepted.
# ------------------------------------------------------------------------
def test_dancer_token_cookie_is_read_only_and_url_tokens_are_ignored(
    request_context: APIRequestContext, config, keycloak_access_token: str
):
    log_header("DCTap Dancer token cookie and URL tokens")
    cookie = {"Cookie": f"dancer_access_token={keycloak_access_token}"}

    read = _get(
        request_context, config, f"{dancer_api_url()}/workspaces", headers=cookie
    )
    log_expected_actual("GET with cookie", 200, read.status)
    assert read.status == 200

    write = send_request(
        request_context,
        "POST",
        f"{dancer_api_url()}/workspaces",
        config.request_timeout,
        headers=cookie,
        json={"name": temp_workspace_name()},
    )
    log_expected_actual("POST with cookie only", 401, write.status)
    assert write.status == 401

    in_url = _get(
        request_context,
        config,
        f"{dancer_api_url()}/workspaces?access_token={keycloak_access_token}",
    )
    log_expected_actual("?access_token= in the URL", 401, in_url.status)
    assert in_url.status == 401


# ========================================================================
# The serve routes Marva reads are public and list the seeded workspace,
# with name-based alias URLs.
# ------------------------------------------------------------------------
def test_dancer_serve_routes_are_public_and_list_the_seeded_workspace(
    request_context: APIRequestContext, config
):
    log_header("DCTap Dancer serve routes list the seeded workspace")
    workspaces = _serve_workspaces(request_context, config)
    seeded = next((ws for ws in workspaces if ws["name"] == SEEDED_WORKSPACE), None)
    log_expected_actual(f"'{SEEDED_WORKSPACE}' served", True, seeded is not None)
    assert seeded is not None, f"No '{SEEDED_WORKSPACE}' workspace; did seeding fail?"

    slug = slugify(SEEDED_WORKSPACE)
    assert seeded["profileUrl"] == f"/api/serve/{seeded['id']}/profile"
    assert seeded["profileUrlAlias"] == f"/api/serve/{slug}/profile"
    assert seeded["startingPointsUrlAlias"] == f"/api/serve/{slug}/starting-points"


# ========================================================================
# The seeded workspace serves Marva profiles and starting points in the
# shapes Marva expects (by name alias, like Marva's static profile URLs).
# ------------------------------------------------------------------------
def test_seeded_workspace_serves_marva_profiles(
    request_context: APIRequestContext, config
):
    log_header("Seeded workspace serves Marva profiles")
    slug = slugify(SEEDED_WORKSPACE)

    profiles = _get(request_context, config, f"{dancer_api_url()}/serve/{slug}/profile")
    assert profiles.status == 200
    documents = profiles.json()
    log_expected_actual("profile documents", "> 0", len(documents))
    assert isinstance(documents, list) and documents
    assert all("Profile" in document.get("json", {}) for document in documents)

    starting = _get(
        request_context, config, f"{dancer_api_url()}/serve/{slug}/starting-points"
    )
    assert starting.status == 200
    configs = starting.json()
    starting_config = next(
        (c for c in configs if c.get("configType") == "startingPoints"), None
    )
    log_expected_actual("startingPoints config", "present", starting_config is not None)
    assert starting_config is not None
    assert starting_config["json"], "Starting points have no menu groups"


# ========================================================================
# Full round trip: a workspace created through the API is served publicly
# (so Marva can pick it), and disappears again once deleted.
# ------------------------------------------------------------------------
def test_workspace_lifecycle_round_trip(
    request_context: APIRequestContext, config, keycloak_access_token: str
):
    log_header("DCTap Dancer workspace lifecycle")
    name = temp_workspace_name()
    headers = auth_headers(keycloak_access_token)

    created = send_request(
        request_context,
        "POST",
        f"{dancer_api_url()}/workspaces",
        config.request_timeout,
        headers=headers,
        json={"name": name},
    )
    log_expected_actual("create status", 201, created.status)
    assert created.status == 201
    workspace_id = created.json()["data"]["id"]

    try:
        served = [ws["id"] for ws in _serve_workspaces(request_context, config)]
        log_expected_actual(
            "new workspace served publicly", True, workspace_id in served
        )
        assert workspace_id in served

        profile = _get(
            request_context, config, f"{dancer_api_url()}/serve/{workspace_id}/profile"
        )
        assert profile.status == 200
        assert profile.json() == [], "A brand-new workspace should have no profiles"
    finally:
        deleted = send_request(
            request_context,
            "DELETE",
            f"{dancer_api_url()}/workspaces/{workspace_id}",
            config.request_timeout,
            headers=headers,
        )
        log_expected_actual("delete status", {200, 204}, deleted.status)
        assert deleted.status in {200, 204}

    gone = _get(
        request_context, config, f"{dancer_api_url()}/serve/{workspace_id}/profile"
    )
    log_expected_actual("deleted workspace served", 404, gone.status)
    assert gone.status == 404
    assert workspace_id not in [
        ws["id"] for ws in _serve_workspaces(request_context, config)
    ]


# ========================================================================
# "LC Latest" mirrors LC's profiles: it is served to Marva like any other
# workspace, its card shows when LC last changed it (with a link), and it
# is locked, so it can't be renamed, deleted or edited (each
# sync would replace those changes). Duplicating it gives an editable copy.
# Needs a dancer image with the Blue Core sync (newer than v0.1.00).
# ------------------------------------------------------------------------
def test_synced_lc_workspace_is_served_locked_and_can_be_duplicated(
    request_context: APIRequestContext, config, keycloak_access_token: str
):
    log_header("DCTap Dancer 'LC Latest' workspace")
    headers = auth_headers(keycloak_access_token)
    served = next(
        (
            ws
            for ws in _serve_workspaces(request_context, config)
            if ws["name"] == SYNCED_WORKSPACE
        ),
        None,
    )
    log_expected_actual(f"'{SYNCED_WORKSPACE}' served", True, served is not None)
    assert served is not None, (
        f"No '{SYNCED_WORKSPACE}' workspace; is the dancer image older than the "
        "Blue Core sync, or did the sync fail (see the dancer's logs)?"
    )
    workspace_id = served["id"]

    profiles = _get(
        request_context, config, f"{dancer_api_url()}/serve/{workspace_id}/profile"
    )
    assert profiles.status == 200
    assert profiles.json(), f"'{SYNCED_WORKSPACE}' has no profiles"

    details = _get(
        request_context,
        config,
        f"{dancer_api_url()}/workspaces/{workspace_id}",
        headers=headers,
    )
    log_expected_actual("isLocked", True, details.json()["data"].get("isLocked"))
    assert details.json()["data"].get("isLocked") is True

    for method, kwargs in (("PUT", {"json": {"name": "renamed"}}), ("DELETE", {})):
        blocked = send_request(
            request_context,
            method,
            f"{dancer_api_url()}/workspaces/{workspace_id}",
            config.request_timeout,
            headers=headers,
            **kwargs,
        )
        log_expected_actual(f"{method} status", 403, blocked.status)
        assert blocked.status == 403

    copy_name = temp_workspace_name()
    copy = send_request(
        request_context,
        "POST",
        f"{dancer_api_url()}/workspaces/{workspace_id}/duplicate",
        config.request_timeout,
        headers=headers,
        json={"name": copy_name},
    )
    log_expected_actual("duplicate status", 201, copy.status)
    assert copy.status == 201
    copy_id = copy.json()["data"]["id"]
    try:
        copy_details = _get(
            request_context,
            config,
            f"{dancer_api_url()}/workspaces/{copy_id}",
            headers=headers,
        )
        log_expected_actual(
            "copy isLocked", False, copy_details.json()["data"].get("isLocked")
        )
        assert copy_details.json()["data"].get("isLocked") is False
    finally:
        send_request(
            request_context,
            "DELETE",
            f"{dancer_api_url()}/workspaces/{copy_id}",
            config.request_timeout,
            headers=headers,
        )
