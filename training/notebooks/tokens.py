import os
from functools import wraps

import httpx

ENV = os.environ.get("BLUECORE_URL", "http://localhost")

AIRFLOW_BASE_URL = f"{ENV}/workflows"

def keycloak(func):
    @wraps(func)
    def wrapper(*args, username="developer", password="123456", **kwargs):
        # Inside JupyterHub, KEYCLOAK_INTERNAL_URL points straight at Keycloak on
        # the shared Docker network (bypassing nginx, whose external listen
        # port/scheme varies by deployment). Outside JupyterHub, fall back to the
        # locally published nginx route.
        url = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://localhost/keycloak")
        realm = os.environ.get("KEYCLOAK_REALM", "bluecore")
        resp = httpx.post(
            f"{url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token",
            data={
                "client_id": "bluecore_api",
                "username": username,
                "password": password,
                "grant_type": "password",
            },
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        return func(*args, token=token, **kwargs)
    return wrapper

def airflow(func):
    """Fetch an Airflow token and pass it to the wrapped function as `token`."""
    @wraps(func)
    def wrapper(*args, username="developer", password="123456", **kwargs):
        # Airflow's own /auth/token endpoint, not Keycloak directly: a raw
        # Keycloak access token is not a valid Airflow API bearer token, so
        # credentials must be exchanged here instead.
        resp = httpx.post(
            f"{AIRFLOW_BASE_URL}/auth/token",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        return func(*args, token=token, **kwargs)
    return wrapper