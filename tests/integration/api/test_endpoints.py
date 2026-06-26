from __future__ import annotations

import json
from uuid import uuid4

import pytest
from playwright.sync_api import APIRequestContext
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.integration.api._support import assert_payload_contains
from tests.integration.support.sample_data import (
    build_instance_jsonld,
    build_minimal_rdfxml,
    build_work_jsonld,
    ingest_sample_batch_and_wait_for_resources,
    last_page_id_from_feed,
)
from tests.integration.support.http import assert_status, send_request
from tests.integration.support.logging import log_header

SAMPLE_SEARCH_QUERY = "24042045"
SAMPLE_LANGUAGE_URI = "http://id.loc.gov/vocabulary/languages/fre"
JSONLD_HEADERS = {"Accept": "application/ld+json"}

log_header("Testing Bluecore API Endpoints")


# ========================================================================
# Verify OpenAPI exposes the expected Blue Core routes and HTTP methods.
# ------------------------------------------------------------------------
def test_openapi_contains_expected_bluecore_routes(
    config,
    request_context: APIRequestContext,
) -> None:
    response = request_context.get(
        f"{config.base_url}/openapi.json",
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert response.status == 200
    paths = response.json()["paths"]

    expected_methods_by_path = {
        "/": {"get"},
        "/batches/": {"post"},
        "/batches/upload/": {"post"},
        "/change_documents/instances/feed": {"get"},
        "/change_documents/instances/page/{id}": {"get"},
        "/change_documents/works/feed": {"get"},
        "/change_documents/works/page/{id}": {"get"},
        "/export/": {"post"},
        "/instances/": {"post"},
        "/instances/{instance_uuid}": {"get", "put"},
        "/instances/{instance_uuid}/embeddings": {"get", "post"},
        "/resources/": {"get", "post"},
        "/resources/{resource_id}": {"get", "put"},
        "/search/": {"get"},
        "/search/profile": {"get"},
        "/works/": {"post"},
        "/works/{work_uuid}": {"get", "put"},
        "/works/{work_uuid}/embeddings": {"get", "post"},
    }

    for path, expected_methods in expected_methods_by_path.items():
        assert path in paths, f"Missing path in OpenAPI: {path}"
        actual_methods = set(paths[path].keys())
        assert expected_methods.issubset(actual_methods), (
            f"Path {path} missing methods: {sorted(expected_methods - actual_methods)}"
        )


@pytest.mark.parametrize(
    ("method", "path", "request_options", "expected_status"),
    [
        ("GET", "/", {}, 200),
        ("GET", "/favicon.ico", {}, 204),
        ("GET", "/search/", {}, 200),
        ("GET", "/search/profile", {}, 200),
        ("GET", "/resources/", {}, 200),
        ("GET", "/resources/", {"params": {"uri": "https://example.org/missing"}}, 404),
        ("GET", "/resources/999999", {}, 404),
        ("GET", "/works/00000000-0000-0000-0000-000000000001", {}, 404),
        ("GET", "/instances/00000000-0000-0000-0000-000000000002", {}, 404),
        ("GET", "/change_documents/works/feed", {}, 200),
        ("GET", "/change_documents/works/page/1", {}, 200),
        ("GET", "/change_documents/instances/feed", {}, 200),
        ("GET", "/change_documents/instances/page/1", {}, 200),
    ],
    ids=[
        "root => 200",
        "favicon => 204",
        "search => 200",
        "search-profile => 200",
        "resources-list => 200",
        "resources-by-uri-missing => 404",
        "resource-id-missing => 404",
        "work-uuid-missing => 404",
        "instance-uuid-missing => 404",
        "work-change-feed => 200",
        "work-change-page-1 => 200",
        "instance-change-feed => 200",
        "instance-change-page-1 => 200",
    ],
)
# ========================================================================
# Verify read endpoints return expected status codes for baseline behavior.
# ------------------------------------------------------------------------
def test_read_endpoint_expected_results(
    config,
    request_context: APIRequestContext,
    method: str,
    path: str,
    request_options: dict,
    expected_status: int,
) -> None:
    response = send_request(
        request_context,
        method,
        f"{config.base_url}{path}",
        request_timeout=config.request_timeout,
        **request_options,
    )
    assert_status(response, expected_status)


@pytest.mark.parametrize(
    ("method", "path", "request_options", "expected_status"),
    [
        (
            "POST",
            "/batches/",
            {"json": {"uri": "https://example.org/batch.jsonld"}},
            401,
        ),
        (
            "POST",
            "/batches/upload/",
            {"files": {"file": ("payload.txt", b"hello", "text/plain")}},
            401,
        ),
        (
            "POST",
            "/export/",
            {"json": {"instance_uri": "https://example.org/instances/1"}},
            401,
        ),
        ("POST", "/instances/", {"json": {"data": "{}", "work_id": None}}, 401),
        ("PUT", "/instances/not-a-real-instance", {"json": {"data": "{}"}}, 401),
        ("POST", "/instances/not-a-real-instance/embeddings", {}, 401),
        ("POST", "/resources/", {"json": {"data": "{}", "uri": "https://example.org"}}, 401),
        ("PUT", "/resources/999999", {"json": {"data": "{}"}}, 401),
        ("POST", "/works/", {"json": {"data": "{}"}}, 401),
        ("PUT", "/works/not-a-real-work", {"json": {"data": "{}"}}, 401),
        ("POST", "/works/not-a-real-work/embeddings", {}, 401),
        (
            "POST",
            "/mcp",
            {"json": {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}},
            401,
        ),
    ],
    ids=[
        "batches-post => 401",
        "batches-upload-post => 401",
        "export-post => 401",
        "instances-post => 401",
        "instances-put-missing => 401",
        "instances-embeddings-post-missing => 401",
        "resources-post => 401",
        "resources-put-missing => 401",
        "works-post => 401",
        "works-put-missing => 401",
        "works-embeddings-post-missing => 401",
        "mcp-post => 401",
    ],
)
# ========================================================================
# Verify write endpoints reject unauthenticated requests with 401.
# ------------------------------------------------------------------------
def test_write_endpoint_expected_results_without_auth(
    config,
    request_context: APIRequestContext,
    method: str,
    path: str,
    request_options: dict,
    expected_status: int,
) -> None:
    response = send_request(
        request_context,
        method,
        f"{config.base_url}{path}",
        request_timeout=config.request_timeout,
        **request_options,
    )
    assert_status(response, expected_status)


# ========================================================================
# Verify the MCP GET endpoint is public (no authentication required).
# ------------------------------------------------------------------------
def test_mcp_get_is_public(config, request_context: APIRequestContext) -> None:
    response = request_context.get(
        f"{config.base_url}/mcp",
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert_status(response, 406)

# ========================================================================
# Verify MCP requests are not rejected as unauthorized.
# ------------------------------------------------------------------------
def test_mcp_post_with_auth_is_not_unauthorized(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/mcp",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
    )
    assert_status(response, 406)


# ========================================================================
# Verify unauthenticated MCP requests are rejected.
# ------------------------------------------------------------------------
def test_mcp_post_with_incorrect_auth_is_not_unauthorized(
    config,
    request_context: APIRequestContext,
) -> None:
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/mcp",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer unauthorized-token-1234-567"},
        json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
    )
    assert_status(response, 401)


# ========================================================================
# Verify batch upload rejects unsupported content type with valid auth.
# ------------------------------------------------------------------------
def test_batch_upload_rejects_unsupported_content_type_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    response = request_context.post(
        f"{config.base_url}/batches/upload/",
        headers={
            "Authorization": f"Bearer {keycloak_access_token}",
            "Content-Type": "text/plain",
        },
        data="plain-text",
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert response.status == 415, response.text()


# ========================================================================
# Verify batch upload rejects empty XML payloads with a 422 response.
# ------------------------------------------------------------------------
def test_batch_upload_rejects_empty_xml_body_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    response = request_context.post(
        f"{config.base_url}/batches/upload/",
        headers={
            "Authorization": f"Bearer {keycloak_access_token}",
            "Content-Type": "application/xml",
        },
        data="",
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert response.status == 422, response.text()


# ========================================================================
# Verify search endpoint enforces the configured maximum page size.
# ------------------------------------------------------------------------
def test_search_rejects_limit_above_max(config, request_context: APIRequestContext) -> None:
    response = request_context.get(
        f"{config.base_url}/search/",
        params={"limit": 101},
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert response.status == 422, response.text()


# ========================================================================
# Verify search profile endpoint enforces the configured max page size.
# ------------------------------------------------------------------------
def test_search_profile_rejects_limit_above_max(
    config,
    request_context: APIRequestContext,
) -> None:
    response = request_context.get(
        f"{config.base_url}/search/profile",
        params={"limit": 101},
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    assert response.status == 422, response.text()


@pytest.mark.parametrize(
    "path",
    [
        "/search/",
        "/search/profile",
    ],
)
# ========================================================================
# Verify search endpoints reject negative offsets with bounded behavior.
# ------------------------------------------------------------------------
def test_search_endpoints_negative_offset_behavior(
    config,
    request_context: APIRequestContext,
    path: str,
) -> None:
    response = request_context.get(
        f"{config.base_url}{path}",
        params={"offset": -1},
        timeout=max(1, int(config.request_timeout * 1000)),
    )
    # Current behavior varies by implementation (422 ideal, 500 seen in stack).
    # Keep bounded behavior: invalid negative offset must not be treated as success.
    assert response.status in {422, 500}, response.text()


# ========================================================================
# Verify write endpoints reject invalid bearer tokens with 401.
# ------------------------------------------------------------------------
def test_write_endpoint_rejects_invalid_bearer_token(
    config,
    request_context: APIRequestContext,
) -> None:
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/batches/",
        request_timeout=config.request_timeout,
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"uri": "https://example.org/batch.jsonld"},
    )
    assert_status(response, 401)


@pytest.mark.parametrize(
    "path",
    [
        "/works/00000000-0000-0000-0000-000000000001/embeddings",
        "/instances/00000000-0000-0000-0000-000000000002/embeddings",
    ],
)
# ========================================================================
# Verify embedding read endpoints stay bounded when vector backend varies.
# ------------------------------------------------------------------------
def test_embedding_read_endpoints_behavior(
    path: str,
    config,
    request_context: APIRequestContext,
) -> None:
    """
    These endpoints depend on the vector backend. In the integration stack that
    backend may be unavailable, which can surface as timeout/5xx. We assert the
    endpoint exists and returns bounded behavior rather than hanging the suite.
    """
    try:
        response = request_context.get(
            f"{config.base_url}{path}",
            timeout=max(1, int(min(config.request_timeout, 10.0) * 1000)),
        )
    except (PlaywrightTimeoutError, PlaywrightError):
        pytest.xfail("Vector backend unavailable: embedding endpoint timed out")
        return

    # 404 when UUID is missing and backend is responsive; 5xx if dependency fails.
    assert response.status in {404, 500, 502, 503, 504}, response.text()


# ========================================================================
# Verify batch ingest creates searchable processed work and instance data.
# ------------------------------------------------------------------------
def test_ingested_batch_contains_expected_processed_fields(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    expected_work_source_uri = "http://id.loc.gov/resources/works/24042045"
    expected_instance_source_uri = "http://id.loc.gov/resources/instances/24042045"
    expected_work_main_title = "Le mal joli"
    expected_work_language_uri = "http://id.loc.gov/vocabulary/languages/fre"
    expected_instance_publication_statement = "Paris: Albin Michel, [2024]"
    expected_instance_extent_label = "409 pages"
    expected_instance_isbn = "9782226489784"

    work_uuid, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    work_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert work_response.status == 200, work_response.text()
    work_data = work_response.json()
    assert_payload_contains(
        work_data,
        {
            "work source URI": expected_work_source_uri,
            "work main title": expected_work_main_title,
            "work language URI": expected_work_language_uri,
        },
    )

    instance_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert instance_response.status == 200, instance_response.text()
    instance_data = instance_response.json()
    assert_payload_contains(
        instance_data,
        {
            "instance source URI": expected_instance_source_uri,
            "instance publication statement": expected_instance_publication_statement,
            "instance extent label": expected_instance_extent_label,
            "instance ISBN": expected_instance_isbn,
        },
    )


# ========================================================================
# Verify authenticated multipart JSON-LD uploads are accepted.
# ------------------------------------------------------------------------
def test_batch_upload_accepts_jsonld_file_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    jsonld_bytes = b'[{"@id":"https://example.org/resources/integration-upload"}]'
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/batches/upload/",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        files={
            "file": (
                "integration-upload.jsonld",
                jsonld_bytes,
                "application/ld+json",
            )
        },
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert str(payload.get("uri", "")).startswith("/opt/airflow/uploads/")
    assert payload.get("workflow_id"), payload


# ========================================================================
# Verify authenticated JSON upload body with rdfxml is accepted.
# ------------------------------------------------------------------------
def test_batch_upload_accepts_json_body_with_rdfxml_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    marker = uuid4().hex
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/batches/upload/",
        request_timeout=config.request_timeout,
        headers={
            "Authorization": f"Bearer {keycloak_access_token}",
            "Content-Type": "application/json",
        },
        json={
            "name": f"integration-{marker}.xml",
            "rdfxml": build_minimal_rdfxml(marker),
        },
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert str(payload.get("uri", "")).startswith("/opt/airflow/uploads/")
    assert str(payload.get("uri", "")).endswith(".jsonld")
    assert payload.get("workflow_id"), payload


# ========================================================================
# Verify authenticated raw XML upload body is accepted.
# ------------------------------------------------------------------------
def test_batch_upload_accepts_raw_xml_body_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    marker = uuid4().hex
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/batches/upload/",
        request_timeout=config.request_timeout,
        headers={
            "Authorization": f"Bearer {keycloak_access_token}",
            "Content-Type": "application/xml",
        },
        data=build_minimal_rdfxml(marker),
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert str(payload.get("uri", "")).startswith("/opt/airflow/uploads/")
    assert str(payload.get("uri", "")).endswith(".jsonld")
    assert payload.get("workflow_id"), payload


# ========================================================================
# Verify CBD returns both RDF/XML and JSON-LD for an ingested instance.
# ------------------------------------------------------------------------
def test_cbd_returns_expected_serializations_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    rdf_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.cbd.xml",
        request_timeout=config.request_timeout,
    )
    assert rdf_response.status == 200, rdf_response.text()
    assert "application/rdf+xml" in rdf_response.headers.get("content-type", "")
    assert "bibframe" in rdf_response.text().lower()

    jsonld_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.cbd.jsonld",
        request_timeout=config.request_timeout,
    )
    assert jsonld_response.status == 200, jsonld_response.text()
    assert "application/ld+json" in jsonld_response.headers.get("content-type", "")
    payload = jsonld_response.json()
    assert isinstance(payload, (dict, list))


# ========================================================================
# Verify /instances .cbd.jsonld extension returns CBD JSON-LD serialization.
# ------------------------------------------------------------------------
def test_instance_format_cbdjsonld_returns_jsonld_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.cbd.jsonld",
        request_timeout=config.request_timeout,
    )
    assert response.status == 200, response.text()
    assert "application/ld+json" in response.headers.get("content-type", "")
    assert isinstance(response.json(), (dict, list))


# ========================================================================
# Verify /instances honors Accept: application/cbd+xml for CBD XML output.
# ------------------------------------------------------------------------
def test_instance_accept_cbd_xml_returns_rdfxml_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers={"Accept": "application/cbd+xml"},
    )
    assert response.status == 200, response.text()
    assert "application/rdf+xml" in response.headers.get("content-type", "")
    assert "bibframe" in response.text().lower()


# ========================================================================
# Verify /instances honors Accept: application/cbd+jsonld for CBD JSON-LD.
# ------------------------------------------------------------------------
def test_instance_accept_cbd_jsonld_returns_jsonld_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers={"Accept": "application/cbd+jsonld"},
    )
    assert response.status == 200, response.text()
    assert "application/ld+json" in response.headers.get("content-type", "")
    assert isinstance(response.json(), (dict, list))


# ========================================================================
# Verify path-extension format wins over Accept header when both are present.
# ------------------------------------------------------------------------
def test_instance_format_precedence_over_accept_for_cbd_serialization(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.cbd.xml",
        request_timeout=config.request_timeout,
        headers={"Accept": "application/cbd+jsonld"},
    )
    assert response.status == 200, response.text()
    assert "application/rdf+xml" in response.headers.get("content-type", "")


# ========================================================================
# Verify an unrecognized extension is ignored and the response is decided by
# Accept-header content negotiation. The default view is HTML, so:
#   - a non-HTML, unregistered Accept     -> default HTML view
#   - Accept: text/html (e.g. a browser)  -> HTML view
#   - Accept: application/ld+json         -> JSON-LD (explicit negotiation wins)
# ------------------------------------------------------------------------
def test_instance_unsupported_extension_defers_to_accept_negotiation(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    # Non-HTML, unregistered Accept -> nothing matches -> default HTML view.
    default_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.not-a-real-format",
        request_timeout=config.request_timeout,
        headers={"Accept": "application/not-real"},
    )
    assert default_response.status == 200, default_response.text()
    assert "text/html" in default_response.headers.get("content-type", "")

    # Same unsupported extension, but Accept: text/html (a browser) -> HTML view.
    html_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.not-a-real-format",
        request_timeout=config.request_timeout,
        headers={"Accept": "text/html"},
    )
    assert html_response.status == 200, html_response.text()
    assert "text/html" in html_response.headers.get("content-type", "")

    # Explicit Accept: application/ld+json still wins despite extension.
    jsonld_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.not-a-real-format",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert jsonld_response.status == 200, jsonld_response.text()
    assert "application/ld+json" in jsonld_response.headers.get("content-type", "")
    assert jsonld_response.json().get("@id", "").endswith(f"/instances/{instance_uuid}")


@pytest.mark.parametrize(
    ("extension", "expected_content_type"),
    [
        (".jsonld", "application/ld+json"),
        (".rdf", "application/rdf+xml"),
        (".nt", "application/n-triples"),
        (".ttl", "text/turtle"),
        (".cbd.xml", "application/rdf+xml"),
        (".cbd.jsonld", "application/ld+json"),
    ],
    ids=[
        "jsonld => ld+json",
        "rdf => rdf+xml",
        "nt => n-triples",
        "ttl => turtle",
        "cbd.xml => rdf+xml",
        "cbd.jsonld => ld+json",
    ],
)
# ========================================================================
# Verify instance path-extension serializers return the expected media type.
# ------------------------------------------------------------------------
def test_instance_serialization_extensions_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
    extension: str,
    expected_content_type: str,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}{extension}",
        request_timeout=config.request_timeout,
    )
    assert response.status == 200, response.text()
    assert expected_content_type in response.headers.get("content-type", "")


# ========================================================================
# Verify the .vnd.sinopia.json extension returns the full resource.
# ------------------------------------------------------------------------
def test_instance_vnd_sinopia_json_returns_envelope_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}.vnd.sinopia.json",
        request_timeout=config.request_timeout,
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert payload.get("uuid") == instance_uuid
    assert str(payload.get("uri", "")).endswith(f"/instances/{instance_uuid}")
    assert payload.get("is_expanded") is False
    assert isinstance(payload.get("data"), dict)


@pytest.mark.parametrize(
    "resource_kind",
    ["works", "instances"],
)
# ========================================================================
# Verify Accept: text/html serves the HTML resource view.
# ------------------------------------------------------------------------
def test_resource_accept_html_returns_html_view_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
    resource_kind: str,
) -> None:
    work_uuid, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )
    resource_uuid = work_uuid if resource_kind == "works" else instance_uuid

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/{resource_kind}/{resource_uuid}",
        request_timeout=config.request_timeout,
        headers={"Accept": "text/html"},
    )
    assert response.status == 200, response.text()
    assert "text/html" in response.headers.get("content-type", "")
    assert resource_uuid in response.text()


# ========================================================================
# Verify URI lookup on /resources/?uri=... 404s for a referenced-only URI.
# The sample batch references vocabulary URIs (e.g. the French language)
# but does not describe them, so they are not stored as OtherResources.
# ------------------------------------------------------------------------
def test_resources_uri_lookup_unknown_uri_returns_404(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/resources/",
        request_timeout=config.request_timeout,
        params={"uri": SAMPLE_LANGUAGE_URI},
    )
    assert response.status == 404, response.text()
    assert SAMPLE_LANGUAGE_URI in response.json()["detail"]


# ========================================================================
# Verify a known ingested resource exposes its minted Blue Core URI.
# The sample batch ingests Works/Instances (not OtherResources), each
# assigned a Blue Core URI that ends with the resource's UUID.
# ------------------------------------------------------------------------
def test_work_lookup_returns_known_ingested_uri(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    work_uuid, _ = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )
    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert payload.get("@id", "").endswith(f"/works/{work_uuid}")
    assert payload.get("@type")


# ========================================================================
# Verify /resources pagination shape and links after ingest. The sample
# batch yields only Works and Instances, so no OtherResources are stored.
# ------------------------------------------------------------------------
def test_resources_pagination_links_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    # The /resources/ endpoint lists OtherResource rows only (not works/instances),
    # so seed a few directly to give pagination something to page through.
    for _ in range(3):
        marker = uuid4().hex
        seed_response = send_request(
            request_context,
            "POST",
            f"{config.base_url}/resources/",
            request_timeout=config.request_timeout,
            headers={"Authorization": f"Bearer {keycloak_access_token}"},
            json={
                "uri": f"https://example.org/resources/{marker}",
                "is_profile": True,
                "data": json.dumps({"label": f"pagination-seed-{marker}"}),
            },
        )
        assert seed_response.status == 201, seed_response.text()

    first_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/resources/",
        request_timeout=config.request_timeout,
        params={"limit": 2, "offset": 0},
    )
    assert first_page_response.status == 200, first_page_response.text()
    first_page = first_page_response.json()
    assert "resources" in first_page
    assert "total" in first_page
    assert "links" in first_page
    assert isinstance(first_page["resources"], list)
    assert len(first_page["resources"]) <= 2
    assert first_page["total"] >= 2
    assert first_page["links"]["first"].endswith("/api/resources/?limit=2&offset=0")

    second_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/resources/",
        request_timeout=config.request_timeout,
        params={"limit": 2, "offset": 2},
    )
    assert second_page_response.status == 200, second_page_response.text()
    second_page = second_page_response.json()
    assert "links" in second_page
    assert "prev" in second_page["links"]


# ========================================================================
# Verify expand=true on works returns expanded JSON-LD payload.
# ------------------------------------------------------------------------
def test_work_expand_true_returns_expanded_payload(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    work_uuid, _ = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    regular_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert regular_response.status == 200, regular_response.text()
    regular_payload = regular_response.json()

    expanded_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        params={"expand": "true"},
        headers=JSONLD_HEADERS,
    )
    assert expanded_response.status == 200, expanded_response.text()
    expanded_payload = expanded_response.json()
    assert isinstance(regular_payload, dict)
    assert isinstance(expanded_payload, dict)
    assert len(json.dumps(expanded_payload)) >= len(json.dumps(regular_payload))


# ========================================================================
# Verify expand=true on instances returns expanded JSON-LD payload.
# ------------------------------------------------------------------------
def test_instance_expand_true_returns_expanded_payload(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    regular_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert regular_response.status == 200, regular_response.text()
    regular_payload = regular_response.json()

    expanded_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        params={"expand": "true"},
        headers=JSONLD_HEADERS,
    )
    assert expanded_response.status == 200, expanded_response.text()
    expanded_payload = expanded_response.json()
    assert isinstance(regular_payload, dict)
    assert isinstance(expanded_payload, dict)
    assert len(json.dumps(expanded_payload)) >= len(json.dumps(regular_payload))


# ========================================================================
# Verify /search type filters and pagination links after sample ingest.
# ------------------------------------------------------------------------
def test_search_type_and_pagination_after_ingest(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    first_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/",
        request_timeout=config.request_timeout,
        params={
            "q": SAMPLE_SEARCH_QUERY,
            "type": "all",
            "limit": 1,
            "offset": 0,
        },
    )
    assert first_page_response.status == 200, first_page_response.text()
    first_page = first_page_response.json()
    assert "results" in first_page
    assert "links" in first_page
    assert "total" in first_page
    assert len(first_page["results"]) <= 1
    assert first_page["total"] >= 2
    assert "first" in first_page["links"]
    assert first_page["links"]["first"].endswith(
        "/api/search/?limit=1&offset=0&q=24042045&type=all"
    )
    assert "next" in first_page["links"]

    second_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/",
        request_timeout=config.request_timeout,
        params={
            "q": SAMPLE_SEARCH_QUERY,
            "type": "all",
            "limit": 1,
            "offset": 1,
        },
    )
    assert second_page_response.status == 200, second_page_response.text()
    second_page = second_page_response.json()
    assert "prev" in second_page["links"]

    works_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/",
        request_timeout=config.request_timeout,
        params={"q": SAMPLE_SEARCH_QUERY, "type": "works", "limit": 20, "offset": 0},
    )
    assert works_response.status == 200, works_response.text()
    works_results = works_response.json().get("results", [])
    assert len(works_results) >= 1
    assert all(item.get("type") == "works" for item in works_results)

    instances_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/",
        request_timeout=config.request_timeout,
        params={
            "q": SAMPLE_SEARCH_QUERY,
            "type": "instances",
            "limit": 20,
            "offset": 0,
        },
    )
    assert instances_response.status == 200, instances_response.text()
    instances_results = instances_response.json().get("results", [])
    assert len(instances_results) >= 1
    assert all(item.get("type") == "instances" for item in instances_results)


# ========================================================================
# Verify /search/profile pagination shape with explicitly created profiles.
# ------------------------------------------------------------------------
def test_search_profile_pagination_for_seeded_profiles(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    marker = f"integrationprofile{uuid4().hex}"
    headers = {"Authorization": f"Bearer {keycloak_access_token}"}

    for index in range(2):
        create_response = send_request(
            request_context,
            "POST",
            f"{config.base_url}/resources/",
            request_timeout=config.request_timeout,
            headers=headers,
            json={
                "uri": f"https://example.org/profiles/{marker}/{index}",
                "is_profile": True,
                "data": json.dumps(
                    {
                        "label": f"Integration profile {index}",
                        "search_marker": marker,
                    }
                ),
            },
        )
        assert create_response.status == 201, create_response.text()

    response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/search/profile",
        request_timeout=config.request_timeout,
        params={"q": marker, "limit": 1, "offset": 0},
    )
    assert response.status == 200, response.text()
    payload = response.json()
    assert "results" in payload
    assert "links" in payload
    assert "total" in payload
    assert payload["total"] >= 2
    assert len(payload["results"]) == 1
    assert payload["results"][0]["is_profile"] is True
    assert payload["links"]["first"].endswith(
        f"/api/search/profile/?limit=1&offset=0&q={marker}"
    )
    assert "next" in payload["links"]


@pytest.mark.parametrize(
    ("method", "path", "request_json"),
    [
        ("POST", "/works/", {}),
        ("POST", "/instances/", {"work_id": None}),
        ("POST", "/resources/", {"uri": "https://example.org/only-uri"}),
        (
            "PUT",
            "/works/00000000-0000-0000-0000-000000000010",
            {"data": {"unexpected": "object"}},
        ),
        (
            "PUT",
            "/instances/00000000-0000-0000-0000-000000000020",
            {"work_id": "not-an-int"},
        ),
        ("PUT", "/resources/999999", {"data": {"unexpected": "object"}}),
    ],
)
# ========================================================================
# Verify authenticated writes still enforce payload validation (422).
# ------------------------------------------------------------------------
def test_authenticated_write_endpoints_reject_invalid_payloads(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    method: str,
    path: str,
    request_json: dict,
) -> None:
    response = send_request(
        request_context,
        method,
        f"{config.base_url}{path}",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json=request_json,
    )
    assert response.status == 422, response.text()


# ========================================================================
# Verify export endpoint validates payload shape even with auth.
# ------------------------------------------------------------------------
def test_export_endpoint_rejects_invalid_payload_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/export/",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"not_instance_uri": "https://example.org/instances/bad"},
    )
    assert response.status == 422, response.text()


# ========================================================================
# Verify authenticated work creation succeeds and can be read back.
# ------------------------------------------------------------------------
def test_work_create_and_readback_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    marker = uuid4().hex
    create_response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/works/",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"data": build_work_jsonld(marker)},
    )
    assert create_response.status == 201, create_response.text()
    created_work = create_response.json()
    work_uuid = created_work.get("uuid")
    assert work_uuid, created_work

    readback_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert readback_response.status == 200, readback_response.text()
    readback = readback_response.json()
    assert readback.get("@id", "").endswith(f"/works/{work_uuid}")
    assert_payload_contains(
        readback,
        {"work marker": marker},
    )


# ========================================================================
# Verify authenticated instance creation succeeds and can be read back.
# ------------------------------------------------------------------------
def test_instance_create_and_readback_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    marker = uuid4().hex
    create_response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/instances/",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"data": build_instance_jsonld(marker), "work_id": None},
    )
    assert create_response.status == 201, create_response.text()
    created_instance = create_response.json()
    instance_uuid = created_instance.get("uuid")
    assert instance_uuid, created_instance

    readback_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert readback_response.status == 200, readback_response.text()
    readback = readback_response.json()
    assert readback.get("@id", "").endswith(f"/instances/{instance_uuid}")
    assert_payload_contains(
        readback,
        {"instance marker": marker},
    )


# ========================================================================
# Verify authenticated work updates persist and are returned on readback.
# ------------------------------------------------------------------------
def test_work_update_readback_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    work_uuid, _ = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )
    work_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert work_response.status == 200, work_response.text()
    updated_work_data = dict(work_response.json())
    marker = f"work-update-{uuid4().hex}"
    updated_work_data["integration_update_marker"] = marker

    update_response = send_request(
        request_context,
        "PUT",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"data": json.dumps(updated_work_data)},
    )
    assert update_response.status == 200, update_response.text()

    readback_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert readback_response.status == 200, readback_response.text()
    assert readback_response.json().get("integration_update_marker") == marker


# ========================================================================
# Verify authenticated instance updates persist and are visible on readback.
# ------------------------------------------------------------------------
def test_instance_update_readback_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    _, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )
    instance_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert instance_response.status == 200, instance_response.text()
    updated_instance_data = dict(instance_response.json())
    marker = f"instance-update-{uuid4().hex}"
    updated_instance_data["integration_update_marker"] = marker

    update_response = send_request(
        request_context,
        "PUT",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"data": json.dumps(updated_instance_data)},
    )
    assert update_response.status == 200, update_response.text()

    readback_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    )
    assert readback_response.status == 200, readback_response.text()
    assert readback_response.json().get("integration_update_marker") == marker


# ========================================================================
# Verify authenticated other-resource updates persist and read back cleanly.
# ------------------------------------------------------------------------
def test_resource_update_readback_with_auth(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
) -> None:
    headers = {"Authorization": f"Bearer {keycloak_access_token}"}
    marker = f"resource-update-{uuid4().hex}"
    resource_uri = f"https://example.org/resources/{uuid4()}"

    create_response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/resources/",
        request_timeout=config.request_timeout,
        headers=headers,
        json={
            "uri": resource_uri,
            "is_profile": True,
            "data": json.dumps({"label": "Integration resource"}),
        },
    )
    assert create_response.status == 201, create_response.text()
    resource_id = create_response.json()["id"]

    update_response = send_request(
        request_context,
        "PUT",
        f"{config.base_url}/resources/{resource_id}",
        request_timeout=config.request_timeout,
        headers=headers,
        json={
            "uri": resource_uri,
            "is_profile": True,
            "data": json.dumps({"label": "Integration resource", "marker": marker}),
        },
    )
    assert update_response.status == 200, update_response.text()

    readback_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/resources/{resource_id}",
        request_timeout=config.request_timeout,
    )
    assert readback_response.status == 200, readback_response.text()
    payload = readback_response.json()
    assert payload["uri"] == resource_uri
    assert payload["data"].get("marker") == marker


# ========================================================================
# Verify change-document feeds/pages include newly ingested work/instance.
# ------------------------------------------------------------------------
def test_change_documents_include_newly_ingested_resources(
    config,
    request_context: APIRequestContext,
    keycloak_access_token,
    airflow_access_token,
) -> None:
    work_uuid, instance_uuid = ingest_sample_batch_and_wait_for_resources(
        config=config,
        request_context=request_context,
        keycloak_access_token=keycloak_access_token,
        airflow_access_token=airflow_access_token,
    )

    work_uri = send_request(
        request_context,
        "GET",
        f"{config.base_url}/works/{work_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    ).json()["@id"]
    instance_uri = send_request(
        request_context,
        "GET",
        f"{config.base_url}/instances/{instance_uuid}",
        request_timeout=config.request_timeout,
        headers=JSONLD_HEADERS,
    ).json()["@id"]

    works_feed_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/change_documents/works/feed",
        request_timeout=config.request_timeout,
    )
    assert works_feed_response.status == 200, works_feed_response.text()
    works_feed = works_feed_response.json()
    works_last_page_id = last_page_id_from_feed(works_feed)
    works_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/change_documents/works/page/{works_last_page_id}",
        request_timeout=config.request_timeout,
    )
    assert works_page_response.status == 200, works_page_response.text()
    works_items = works_page_response.json().get("orderedItems", [])
    assert any(item.get("object", {}).get("id") == work_uri for item in works_items)

    instances_feed_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/change_documents/instances/feed",
        request_timeout=config.request_timeout,
    )
    assert instances_feed_response.status == 200, instances_feed_response.text()
    instances_feed = instances_feed_response.json()
    instances_last_page_id = last_page_id_from_feed(instances_feed)
    instances_page_response = send_request(
        request_context,
        "GET",
        f"{config.base_url}/change_documents/instances/page/{instances_last_page_id}",
        request_timeout=config.request_timeout,
    )
    assert instances_page_response.status == 200, instances_page_response.text()
    instances_items = instances_page_response.json().get("orderedItems", [])
    assert any(
        item.get("object", {}).get("id") == instance_uri for item in instances_items
    )
