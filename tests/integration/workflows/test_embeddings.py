from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import APIRequestContext

from tests.integration.support.http import post_with_retry
from tests.integration.support.keycloak import get_password_grant_access_token
from tests.integration.support.logging import log_expected_actual, log_header
from tests.integration.support.sample_data import SAMPLE_BATCH_JSONLD_URL, SAMPLE_SEARCH_QUERY
from tests.integration.support import waits, workflow

TERRAFORM_ROOT = Path(__file__).resolve().parents[3]
REQUIRE_VECTOR_BACKEND = (
    os.getenv("INTEGRATION_REQUIRE_VECTOR_BACKEND", "0").lower() in {"1", "true", "yes"}
)


# ========================================================================
# Verify embeddings can be created and read when vector backend is enabled.
# ------------------------------------------------------------------------
def test_vector_embeddings_can_be_created_and_read_when_vector_backend_is_required(
    config,
    request_context: APIRequestContext,
    airflow_access_token,
):
    if not REQUIRE_VECTOR_BACKEND:
        pytest.skip(
            "Set INTEGRATION_REQUIRE_VECTOR_BACKEND=1 to run Milvus embedding assertions."
        )

    log_header("Vector backend embeddings can be created and read")

    dag_run_id = workflow.run_bluecore_load_url_cli(
        url=SAMPLE_BATCH_JSONLD_URL,
        api_base_url=config.base_url,
        keycloak_base_url=config.keycloak_token_url.split("/keycloak/realms/")[0],
        terraform_root=TERRAFORM_ROOT,
    )
    waits.wait_for_dag_run_completion(
        request_context=request_context,
        base_url=config.airflow_base_url,
        dag_id="resource_loader",
        dag_run_id=dag_run_id,
        access_token=airflow_access_token,
        timeout_seconds=480,
        poll_interval_seconds=2,
        request_timeout=config.request_timeout,
    )

    work_uuid, instance_uuid = waits.wait_for_loaded_resource_uuids(
        request_context=request_context,
        base_url=config.base_url,
        request_timeout=config.request_timeout,
        query=SAMPLE_SEARCH_QUERY,
    )
    log_expected_actual("sample work uuid", "non-empty", work_uuid)
    log_expected_actual("sample instance uuid", "non-empty", instance_uuid)

    headers = {"Authorization": f"Bearer {get_password_grant_access_token(request_context, config)}"}
    embedding_timeout = max(config.request_timeout, 120.0)

    work_create_response = post_with_retry(
        request_context=request_context,
        url=f"{config.base_url}/works/{work_uuid}/embeddings",
        json_payload=None,
        headers=headers,
        request_timeout=embedding_timeout,
        max_attempts=6,
        retry_delay_seconds=3.0,
    )
    log_expected_actual("POST /works/{uuid}/embeddings status code", 201, work_create_response.status)
    assert work_create_response.status == 201, work_create_response.text()

    instance_create_response = post_with_retry(
        request_context=request_context,
        url=f"{config.base_url}/instances/{instance_uuid}/embeddings",
        json_payload=None,
        headers=headers,
        request_timeout=embedding_timeout,
        max_attempts=6,
        retry_delay_seconds=3.0,
    )
    log_expected_actual(
        "POST /instances/{uuid}/embeddings status code",
        201,
        instance_create_response.status,
    )
    assert instance_create_response.status == 201, instance_create_response.text()

    work_embeddings_payload = waits.wait_for_non_empty_embeddings(
        request_context=request_context,
        url=f"{config.base_url}/works/{work_uuid}/embeddings",
        request_timeout=config.request_timeout,
        timeout_seconds=180,
        poll_interval_seconds=2.0,
    )
    log_expected_actual(
        "GET /works/{uuid}/embeddings embedding count",
        ">= 1",
        len(work_embeddings_payload.get("embedding", [])),
    )
    assert len(work_embeddings_payload.get("embedding", [])) >= 1
    assert len(work_embeddings_payload["embedding"][0].get("vector", [])) == 768

    instance_embeddings_payload = waits.wait_for_non_empty_embeddings(
        request_context=request_context,
        url=f"{config.base_url}/instances/{instance_uuid}/embeddings",
        request_timeout=config.request_timeout,
        timeout_seconds=180,
        poll_interval_seconds=2.0,
    )
    log_expected_actual(
        "GET /instances/{uuid}/embeddings embedding count",
        ">= 1",
        len(instance_embeddings_payload.get("embedding", [])),
    )
    assert len(instance_embeddings_payload.get("embedding", [])) >= 1
    assert len(instance_embeddings_payload["embedding"][0].get("vector", [])) == 768
