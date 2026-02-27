from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

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


# ========================================================================
# Resolve bluecore_api checkout directory for CLI-based integration tests.
# ------------------------------------------------------------------------
def resolve_bluecore_api_root(terraform_root: Path) -> Path:
    candidates: list[Path] = []
    env_root = os.environ.get("BLUECORE_API_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend(
        [
            terraform_root.parent / "bluecore_api",
            terraform_root / "external" / "bluecore_api",
            terraform_root.parent / "external" / "bluecore_api",
        ]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    tried_paths = "\n - ".join(str(path.resolve()) for path in candidates)
    raise AssertionError(f"bluecore_api directory not found. Checked:\n - {tried_paths}")


# ========================================================================
# Execute `bluecore load-url` CLI and parse workflow_id from output.
# ------------------------------------------------------------------------
def run_bluecore_load_url_cli(
    *,
    url: str,
    api_base_url: str,
    keycloak_base_url: str,
    terraform_root: Path,
) -> str:
    bluecore_api_root = resolve_bluecore_api_root(terraform_root)
    env = os.environ.copy()
    env.update(
        {
            "BLUECORE_URL": f"{api_base_url.rstrip('/')}/",
            "API_URL": f"{api_base_url.rstrip('/')}/",
            "KEYCLOAK_EXTERNAL_URL": f"{keycloak_base_url.rstrip('/')}/keycloak/",
            "API_KEYCLOAK_USER": "developer",
            "API_KEYCLOAK_PASSWORD": "123456",
            "NO_COLOR": "1",
        }
    )
    command = ["uv", "run", "bluecore", "--verbose", "load-url", url]
    result = subprocess.run(
        command,
        cwd=bluecore_api_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".strip()
    if result.returncode != 0:
        raise AssertionError(
            "bluecore load-url command failed.\n"
            f"Command: {' '.join(command)}\n"
            f"Exit code: {result.returncode}\n"
            f"Output:\n{output}"
        )
    match = re.search(r"workflow_id['\"]?\s*[:=]\s*['\"]([^'\"\\s]+)", output)
    if not match:
        raise AssertionError(
            "Could not parse workflow_id from bluecore load-url output.\n"
            f"Output:\n{output}"
        )
    return match.group(1)


