"""Version endpoint for bluecore-workflows, served by the Airflow API server.

The API, Sinopia and Marva each answer a health URL with {"version": "…"}; this
gives Workflows the same, at /workflows/health (nginx rewrites it to this app's
prefix). The version comes from the bluecore-workflows package installed in the
image, so it always matches the image that's running. No login is needed: it
reports only version numbers.

Mounted into /opt/airflow/plugins by compose-base.yaml; Airflow loads every module
in that folder.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from airflow import __version__ as airflow_version
from airflow.plugins_manager import AirflowPlugin
from fastapi import FastAPI

URL_PREFIX = "/bluecore-health"

app = FastAPI(title="Blue Core Workflows health")


@app.get("/")
def health() -> dict:
    try:
        workflows_version = version("bluecore-workflows")
    except PackageNotFoundError:
        workflows_version = None
    return {"status": "ok", "version": workflows_version, "airflow": airflow_version}


class BluecoreHealthPlugin(AirflowPlugin):
    name = "bluecore_health"

    fastapi_apps = [  # noqa: RUF012
        {
            "app": app,
            "url_prefix": URL_PREFIX,
            "name": "Blue Core Workflows health",
        }
    ]
