# ========================================================================
# Summarize DAG run payload to stable fields used by assertions/logging.
# ------------------------------------------------------------------------
def summarize_dag_payload(payload: dict) -> dict:
    return {
        "dag_id": payload.get("dag_id"),
        "dag_run_id": payload.get("dag_run_id"),
        "state": payload.get("state"),
        "run_type": payload.get("run_type"),
        "triggered_by": payload.get("triggered_by"),
        "queued_at": payload.get("queued_at"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "conf": payload.get("conf", {}),
    }
