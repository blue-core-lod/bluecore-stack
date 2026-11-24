"""Local dev only: runs the Airflow API server and restarts it when plugin files change.
Plain `airflow api-server` never reloads plugins, so edits and branch switches wouldn't show.
"""

import uvicorn

# Plugin code to watch. DAGs aren't here, so editing a DAG won't restart the server.
WATCH_DIRS = [
    "/bluecore_graph_toolbox/src",
    "/bluecore_airflow_common/src",
    "/opt/airflow/ils_middleware/plugins",
]
WATCH_FILES = ["*.py", "*.html", "*.jinja", "*.css", "*.js", "*.svg", "*.json"]

# The reloader re-imports this file, so only start the server when run directly.
if __name__ == "__main__":
    uvicorn.run(
        "airflow.api_fastapi.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=WATCH_DIRS,
        reload_includes=WATCH_FILES,
        # Same logging setup as `airflow api-server`.
        access_log=False,
        log_config=None,
        proxy_headers=False,
    )
