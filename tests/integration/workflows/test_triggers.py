from __future__ import annotations

from playwright.sync_api import APIRequestContext

from tests.integration.support.http import post, post_with_retry
from tests.integration.support.keycloak import get_password_grant_access_token
from tests.integration.support import waits, workflow
from tests.integration.support.logging import log_expected_actual, log_header, log_json


# ========================================================================
# Verify Keycloak-authenticated ingest triggers a resource_loader DAG run.
# ------------------------------------------------------------------------
def test_keycloak_token_can_trigger_resource_loader_dag(
    config,
    request_context: APIRequestContext,
    airflow_access_token,
):
    log_header("Keycloak token triggers resource_loader DAG")
    payload = {"uri": "file:///opt/airflow/uploads/integration-test.jsonld"}
    api_response = post_with_retry(
        request_context=request_context,
        url=f"{config.base_url}/batches/",
        json_payload=payload,
        headers={"Authorization": f"Bearer {get_password_grant_access_token(request_context, config)}"},
        request_timeout=config.request_timeout,
    )
    log_expected_actual("POST /batches status code", 200, api_response.status)
    assert api_response.status == 200, api_response.text()

    body = api_response.json()
    log_json("API response payload", body)
    dag_run_id = body.get("workflow_id")
    log_expected_actual("workflow_id present", "non-empty", dag_run_id)
    assert dag_run_id, f"Missing workflow_id in API response: {body}"

    dag_payload = waits.wait_for_dag_run_exists(
        request_context=request_context,
        base_url=config.airflow_base_url,
        dag_id="resource_loader",
        dag_run_id=dag_run_id,
        access_token=airflow_access_token,
        timeout_seconds=60,
        poll_interval_seconds=2,
        request_timeout=config.request_timeout,
    )

    log_json("Airflow DAG run summary", workflow.summarize_dag_payload(dag_payload))
    assert dag_payload["dag_id"] == "resource_loader"
    assert dag_payload["dag_run_id"] == dag_run_id
    conf = dag_payload.get("conf", {})
    log_expected_actual("DAG conf.file", payload["uri"], conf.get("file"))
    log_expected_actual("DAG conf.user_uid", "not null/blank/anonymous", conf.get("user_uid"))
    assert conf.get("file") == payload["uri"]
    assert conf.get("user_uid") not in {None, "", "anonymous"}


# ========================================================================
# Verify export endpoint triggers monitor_institutions_exports DAG run.
# ------------------------------------------------------------------------
def test_export_endpoint_triggers_export_dag(
    config,
    request_context: APIRequestContext,
    airflow_access_token,
):
    log_header("Export endpoint triggers monitor_institutions_exports DAG")
    payload = {"instance_uri": "https://example.org/instances/integration-test"}
    api_response = post(
        request_context,
        f"{config.base_url}/export/",
        json_payload=payload,
        headers={"Authorization": f"Bearer {get_password_grant_access_token(request_context, config)}"},
        timeout_seconds=config.request_timeout,
    )
    log_expected_actual("POST /export status code", 200, api_response.status)
    assert api_response.status == 200, api_response.text()

    body = api_response.json()
    log_json("API response payload", body)
    dag_run_id = body.get("workflow_id")
    log_expected_actual("workflow_id present", "non-empty", dag_run_id)
    assert dag_run_id, f"Missing workflow_id in API response: {body}"

    dag_payload = waits.wait_for_dag_run_completion(
        request_context=request_context,
        base_url=config.airflow_base_url,
        dag_id="monitor_institutions_exports",
        dag_run_id=dag_run_id,
        access_token=airflow_access_token,
        timeout_seconds=180,
        poll_interval_seconds=2,
        request_timeout=config.request_timeout,
    )

    log_json("Airflow DAG run summary", workflow.summarize_dag_payload(dag_payload))
    assert dag_payload["dag_id"] == "monitor_institutions_exports"
    assert dag_payload["dag_run_id"] == dag_run_id
    conf = dag_payload.get("conf", {})
    log_expected_actual("DAG conf.resource", payload["instance_uri"], conf.get("resource"))
    log_expected_actual("DAG conf.user", "not null/blank/anonymous", conf.get("user"))
    assert conf.get("resource") == payload["instance_uri"]
    assert conf.get("user") not in {None, "", "anonymous"}
