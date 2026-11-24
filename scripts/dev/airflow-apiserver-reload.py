"""LOCAL DEV ONLY: run the Airflow API server with hot reload for plugin code.

`airflow api-server` loads plugins once at startup and never reloads them.
Its `--dev` mode only watches .py files under /opt/airflow, which misses the
Graph Toolbox and bluecore-airflow-common checkouts mounted elsewhere, and their
templates/CSS/JS. compose-local-dev.yaml runs this instead: the same uvicorn
setup `airflow api-server` uses by default, plus a restart whenever a watched
file changes, including switching branches in one of those checkouts.
"""

import uvicorn

# Plugin source mounted by compose-local-dev.yaml. DAG/task code is not watched
# here (the dag-processor picks that up), so editing a DAG doesn't restart
# the API server.
WATCH_DIRS = [
    "/bluecore_graph_toolbox/src",
    "/bluecore_airflow_common/src",
    "/opt/airflow/ils_middleware/plugins",
]
WATCH_FILES = ["*.py", "*.html", "*.jinja", "*.css", "*.js", "*.svg", "*.json"]

# The reloader starts the server in a spawned process that re-imports this
# file, so only start it from the top-level run.
if __name__ == "__main__":
    uvicorn.run(
        "airflow.api_fastapi.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=WATCH_DIRS,
        reload_includes=WATCH_FILES,
        # As in `airflow api-server`: Airflow's middleware writes the access log,
        # and log_config=None keeps uvicorn from replacing Airflow's logging setup.
        access_log=False,
        log_config=None,
        proxy_headers=False,
    )
