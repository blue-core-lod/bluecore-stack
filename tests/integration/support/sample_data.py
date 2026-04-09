from __future__ import annotations

import json

from playwright.sync_api import APIRequestContext

from tests.integration.support import waits
from tests.integration.support.http import send_request

SAMPLE_BATCH_JSONLD_URL = (
    "https://raw.githubusercontent.com/blue-core-lod/bluecore_api/refs/heads/main/sample/batch-small.jsonld"
)
SAMPLE_SEARCH_QUERY = "24042045"


# ========================================================================
# Ingest sample batch, wait for workflow success, then return work/instance.
# ------------------------------------------------------------------------
def ingest_sample_batch_and_wait_for_resources(
    *,
    config,
    request_context: APIRequestContext,
    keycloak_access_token: str,
    airflow_access_token: str,
    query: str = SAMPLE_SEARCH_QUERY,
    batch_url: str = SAMPLE_BATCH_JSONLD_URL,
) -> tuple[str, str]:
    ingest_response = send_request(
        request_context,
        "POST",
        f"{config.base_url}/batches/",
        request_timeout=config.request_timeout,
        headers={"Authorization": f"Bearer {keycloak_access_token}"},
        json={"uri": batch_url},
    )
    assert ingest_response.status == 200, ingest_response.text()
    dag_run_id = ingest_response.json().get("workflow_id")
    assert dag_run_id, f"Missing workflow_id in payload: {ingest_response.json()}"

    waits.wait_for_resource_loader_dag_run_success(
        request_context=request_context,
        airflow_base_url=config.airflow_base_url,
        dag_run_id=dag_run_id,
        airflow_access_token=airflow_access_token,
        request_timeout=config.request_timeout,
    )

    return waits.wait_for_loaded_resource_uuids(
        request_context=request_context,
        base_url=config.base_url,
        request_timeout=config.request_timeout,
        query=query,
    )


# ========================================================================
# Parse change-documents feed payload and return its final page id.
# ------------------------------------------------------------------------
def last_page_id_from_feed(payload: dict) -> int:
    page_url = payload["last"]["id"]
    return int(str(page_url).rstrip("/").split("/")[-1])


# ========================================================================
# Build minimal RDF/XML payload accepted by /batches/upload/ XML paths.
# ------------------------------------------------------------------------
def build_minimal_rdfxml(marker: str) -> str:
    return (
        '<?xml version="1.0"?>'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        f'<rdf:Description rdf:about="https://example.org/thing/{marker}">'
        '<rdf:type rdf:resource="https://example.org/Type"/>'
        "</rdf:Description>"
        "</rdf:RDF>"
    )


# ========================================================================
# Build minimal JSON-LD work payload string for /works/ create requests.
# ------------------------------------------------------------------------
def build_work_jsonld(marker: str) -> str:
    payload = {
        "@context": {
            "bf": "http://id.loc.gov/ontologies/bibframe/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@id": f"https://example.org/external/work/{marker}",
        "@type": "bf:Work",
        "rdfs:label": f"Integration work {marker}",
    }
    return json.dumps(payload)


# ========================================================================
# Build minimal JSON-LD instance payload string for /instances/ creates.
# ------------------------------------------------------------------------
def build_instance_jsonld(marker: str) -> str:
    payload = {
        "@context": {
            "bf": "http://id.loc.gov/ontologies/bibframe/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@id": f"https://example.org/external/instance/{marker}",
        "@type": "bf:Instance",
        "rdfs:label": f"Integration instance {marker}",
    }
    return json.dumps(payload)
