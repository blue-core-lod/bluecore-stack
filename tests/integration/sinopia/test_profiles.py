from __future__ import annotations

import time
from uuid import uuid4

from playwright.sync_api import APIRequestContext

from tests.integration.sinopia._support import (
    RESOURCE_TEMPLATE_TYPE,
    build_expanded_resource_template_jsonld,
    build_resource_template_jsonld,
    find_resource_template_node,
    interop_nonce,
    profile_create_body,
)
from tests.integration.support.http import assert_status, send_request
from tests.integration.support.logging import (
    log_expected_actual,
    log_header,
    log_json,
)

# The profiles API is the interoperability surface Sinopia uses for Resource
# Templates. These tests hit the API directly (always up in both lightweight and
# full-stack integration runs), so they guard the contract regardless of mode.

JSON_HEADERS = {"Content-Type": "application/json"}


# ========================================================================
# Create a profile via the API and return the parsed 201 response body.
# ------------------------------------------------------------------------
def _create_profile(request_context, config, token, jsonld) -> dict:
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
        headers={**JSON_HEADERS, "Authorization": f"Bearer {token}"},
        json=profile_create_body(jsonld),
    )
    assert_status(response, 201)
    return response.json()


# ========================================================================
# Poll /search/profile until a minted profile URI appears (synchronous index).
# ------------------------------------------------------------------------
def _search_for_uri(request_context, config, query, uri, attempts=5) -> bool:
    for _ in range(attempts):
        response = send_request(
            request_context,
            "GET",
            f"{config.base_url}/search/profile",
            request_timeout=config.request_timeout,
            params={"q": query},
        )
        if response.status == 200:
            results = response.json().get("results", [])
            if any(item.get("uri") == uri for item in results):
                return True
        time.sleep(config.ready_poll_interval)
    return False


# ========================================================================
# OpenAPI advertises the profile routes Sinopia depends on.
# ------------------------------------------------------------------------
def test_openapi_exposes_profile_routes(config, request_context: APIRequestContext):
    log_header("Profiles routes are exposed")
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/openapi.json",
        request_timeout=config.request_timeout,
    )
    assert_status(response, 200)
    paths = response.json().get("paths", {})
    for path, method in (
        ("/profiles/", "post"),
        ("/profiles/", "get"),
        ("/profiles/{profile_uuid}", "get"),
        ("/profiles/{profile_uuid}", "put"),
        ("/search/profile", "get"),
    ):
        present = path in paths and method in paths.get(path, {})
        log_expected_actual(f"{method.upper()} {path}", "present", present)
        assert present, f"OpenAPI missing {method.upper()} {path}"


# ========================================================================
# GET /profiles/ is public and returns the expected list envelope.
# ------------------------------------------------------------------------
def test_profiles_list_is_public_and_shaped(config, request_context: APIRequestContext):
    log_header("Profiles list envelope")
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
    )
    assert_status(response, 200)
    payload = response.json()
    assert isinstance(payload.get("profiles"), list)
    assert isinstance(payload.get("total"), int)
    assert "first" in payload.get("links", {})


# ========================================================================
# GET /search/profile is public and returns the expected search envelope.
# ------------------------------------------------------------------------
def test_search_profile_is_public_and_shaped(config, request_context: APIRequestContext):
    log_header("Search profile envelope")
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/profile",
        request_timeout=config.request_timeout,
    )
    assert_status(response, 200)
    payload = response.json()
    assert isinstance(payload.get("results"), list)
    assert isinstance(payload.get("total"), int)
    assert "links" in payload


# ========================================================================
# Unauthenticated writes to the profiles API are rejected.
# ------------------------------------------------------------------------
def test_create_profile_requires_auth(config, request_context: APIRequestContext):
    log_header("Create profile requires auth")
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
        headers=JSON_HEADERS,
        json=profile_create_body(build_resource_template_jsonld(interop_nonce())),
    )
    log_expected_actual("status", 401, response.status)
    assert_status(response, 401)


# ========================================================================
# An invalid bearer token is rejected on profile writes.
# ------------------------------------------------------------------------
def test_create_profile_rejects_invalid_bearer(config, request_context: APIRequestContext):
    log_header("Create profile rejects invalid bearer")
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
        headers={**JSON_HEADERS, "Authorization": "Bearer not-a-real-token"},
        json=profile_create_body(build_resource_template_jsonld(interop_nonce())),
    )
    assert_status(response, 401)


def test_update_profile_requires_auth(config, request_context: APIRequestContext):
    log_header("Update profile requires auth")
    response = send_request(
        request_context,
        "PUT",
        f"{config.base_url}/profiles/{uuid4()}",
        request_timeout=config.request_timeout,
        headers=JSON_HEADERS,
        json={"data": "{}"},
    )
    assert_status(response, 401)


# ========================================================================
# Core interop contract: POST mints a local URI and re-homes the Resource
# Template node onto it, returning expanded JSON-LD (what Sinopia consumes).
# ------------------------------------------------------------------------
def test_create_profile_mints_uri_and_rehomes_resource_template(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Create profile mints URI and re-homes template")
    nonce = interop_nonce()
    body = _create_profile(
        request_context, config, keycloak_access_token, build_resource_template_jsonld(nonce)
    )
    log_json("created profile", body)

    uuid = body.get("uuid")
    uri = body.get("uri")
    data = body.get("data")
    assert uuid, "response missing uuid"
    assert uri and uri.endswith(f"/profiles/{uuid}"), f"unexpected minted uri: {uri}"

    # Sinopia parses profiles by full-URI predicate, so data must be expanded
    # JSON-LD (a list of nodes), not a compacted @context document.
    assert isinstance(data, list), f"expected expanded JSON-LD list, got {type(data).__name__}"

    node = find_resource_template_node(data)
    assert node is not None, "no sinopia:ResourceTemplate node in stored profile"
    log_expected_actual("template node @id", uri, node.get("@id"))
    assert node.get("@id") == uri, "ResourceTemplate node was not re-homed to the minted URI"


# ========================================================================
# The same contract holds for the expanded-list payload the remote pull sends.
# ------------------------------------------------------------------------
def test_create_profile_accepts_expanded_jsonld_payload(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Create profile accepts expanded JSON-LD payload")
    nonce = interop_nonce()
    body = _create_profile(
        request_context,
        config,
        keycloak_access_token,
        build_expanded_resource_template_jsonld(nonce),
    )
    uri = body.get("uri")
    node = find_resource_template_node(body.get("data"))
    assert node is not None
    assert node.get("@id") == uri


# ========================================================================
# Stored profile data is expanded JSON-LD with no compacting @context.
# ------------------------------------------------------------------------
def test_created_profile_data_is_expanded_without_context(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Stored profile is expanded (no @context)")
    body = _create_profile(
        request_context,
        config,
        keycloak_access_token,
        build_resource_template_jsonld(interop_nonce()),
    )
    data = body.get("data")
    assert isinstance(data, list)
    assert all("@context" not in node for node in data if isinstance(node, dict))


# ========================================================================
# A created profile is retrievable by its minted UUID.
# ------------------------------------------------------------------------
def test_created_profile_is_retrievable_by_uuid(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Profile retrievable by UUID")
    created = _create_profile(
        request_context,
        config,
        keycloak_access_token,
        build_resource_template_jsonld(interop_nonce()),
    )
    uuid = created["uuid"]
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/{uuid}",
        request_timeout=config.request_timeout,
    )
    assert_status(response, 200)
    fetched = response.json()
    assert str(fetched.get("uuid")) == str(uuid)
    assert fetched.get("uri") == created["uri"]
    assert find_resource_template_node(fetched.get("data")) is not None


# ========================================================================
# A created profile is findable by its minted URI via GET /profiles/?uri=.
# ------------------------------------------------------------------------
def test_created_profile_is_findable_by_uri(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Profile findable by URI")
    created = _create_profile(
        request_context,
        config,
        keycloak_access_token,
        build_resource_template_jsonld(interop_nonce()),
    )
    uri = created["uri"]
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
        params={"uri": uri},
    )
    assert_status(response, 200)
    assert response.json().get("uri") == uri


# ========================================================================
# A created profile is discoverable via full-text search (what Sinopia uses).
# ------------------------------------------------------------------------
def test_created_profile_is_searchable(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Profile searchable via /search/profile")
    nonce = interop_nonce()
    created = _create_profile(
        request_context, config, keycloak_access_token, build_resource_template_jsonld(nonce)
    )
    found = _search_for_uri(request_context, config, nonce, created["uri"])
    log_expected_actual("profile in search results", True, found)
    assert found, f"profile {created['uri']} not found searching for '{nonce}'"


# ========================================================================
# Updating a profile persists new template data (Sinopia edit round-trip).
# ------------------------------------------------------------------------
def test_update_profile_persists_new_data(
    config, request_context: APIRequestContext, keycloak_access_token
):
    log_header("Update profile persists new data")
    created = _create_profile(
        request_context,
        config,
        keycloak_access_token,
        build_resource_template_jsonld(interop_nonce()),
    )
    uuid = created["uuid"]
    new_nonce = interop_nonce()
    update = send_request(
        request_context,
        "PUT",
        f"{config.base_url}/profiles/{uuid}",
        request_timeout=config.request_timeout,
        headers={**JSON_HEADERS, "Authorization": f"Bearer {keycloak_access_token}"},
        json={"data": profile_create_body(build_expanded_resource_template_jsonld(new_nonce))["data"]},
    )
    assert_status(update, 200)

    fetched = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/{uuid}",
        request_timeout=config.request_timeout,
    )
    assert_status(fetched, 200)
    import json as _json

    assert new_nonce in _json.dumps(fetched.json().get("data"))


# ========================================================================
# Unknown profile UUID / URI lookups return 404 (not 500).
# ------------------------------------------------------------------------
def test_unknown_profile_uuid_returns_404(config, request_context: APIRequestContext):
    log_header("Unknown profile UUID is 404")
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/{uuid4()}",
        request_timeout=config.request_timeout,
    )
    assert_status(response, 404)


def test_unknown_profile_uri_returns_404(config, request_context: APIRequestContext):
    log_header("Unknown profile URI is 404")
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/profiles/",
        request_timeout=config.request_timeout,
        params={"uri": "http://example.org/profiles/does-not-exist"},
    )
    assert_status(response, 404)
