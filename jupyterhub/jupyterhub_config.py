# Configuration file for JupyterHub.
#
# Everything here is driven by environment variables (set in the repo's .env
# and wired through by the `jupyterhub` service in compose-base.yaml) so the
# image never needs to be rebuilt to change an environment's settings.
import os

c = get_config()  # noqa: F821

# --------------------------------------------------------------------------
# Networking
# --------------------------------------------------------------------------
# Reachable through nginx at /jupyter/ (see nginx/base.conf).
c.JupyterHub.base_url = os.environ.get("JUPYTERHUB_BASE_URL", "/jupyter/")

# Single-user containers reach the Hub API by this container's name on the
# shared Docker network (set via `container_name: jupyterhub` in compose).
c.JupyterHub.hub_ip = "jupyterhub"
c.JupyterHub.hub_port = 8080

# --------------------------------------------------------------------------
# Database (shared Postgres instance, "jupyterhub" database)
# --------------------------------------------------------------------------
db_user = os.environ.get("DATABASE_USERNAME", "airflow")
db_password = os.environ.get("DATABASE_PASSWORD", "airflow")
db_host = os.environ.get("DATABASE_HOSTNAME", "postgres")
db_port = os.environ.get("DATABASE_PORT", "5432")
c.JupyterHub.db_url = (
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/jupyterhub"
)

# Postgres (not a local file) holds all Hub state, so the cookie secret can
# come straight from the env instead of a secret file on a persistent volume
# -- the jupyterhub container itself stays disposable.
c.JupyterHub.cookie_secret = bytes.fromhex(os.environ["JUPYTERHUB_COOKIE_SECRET"])

# --------------------------------------------------------------------------
# Authentication: Keycloak via OpenID Connect
# --------------------------------------------------------------------------
keycloak_internal_url = os.environ["KEYCLOAK_INTERNAL_URL"].rstrip("/")
keycloak_external_url = os.environ["KEYCLOAK_EXTERNAL_URL"].rstrip("/")
keycloak_realm = os.environ.get("KEYCLOAK_REALM", "bluecore")
jupyterhub_external_url = os.environ.get(
    "JUPYTERHUB_EXTERNAL_URL", "http://localhost/jupyter/"
).rstrip("/")

c.JupyterHub.authenticator_class = "generic-oauth"

c.GenericOAuthenticator.client_id = os.environ["JUPYTERHUB_KEYCLOAK_CLIENT_ID"]
c.GenericOAuthenticator.client_secret = os.environ["JUPYTERHUB_KEYCLOAK_CLIENT_SECRET"]

# authorize_url is a browser redirect, so it must be an externally reachable
# address (through nginx); token/userdata calls are Hub-to-Keycloak and use
# the internal Docker network address, same split as the other Keycloak
# clients in this stack.
c.GenericOAuthenticator.authorize_url = (
    f"{keycloak_external_url}/realms/{keycloak_realm}/protocol/openid-connect/auth"
)
c.GenericOAuthenticator.token_url = (
    f"{keycloak_internal_url}/realms/{keycloak_realm}/protocol/openid-connect/token"
)
c.GenericOAuthenticator.userdata_url = (
    f"{keycloak_internal_url}/realms/{keycloak_realm}/protocol/openid-connect/userinfo"
)
c.GenericOAuthenticator.oauth_callback_url = (
    f"{jupyterhub_external_url}/hub/oauth_callback"
)
c.GenericOAuthenticator.scope = ["openid", "profile", "email"]
c.GenericOAuthenticator.username_claim = "preferred_username"

# Any authenticated Keycloak user in the realm may log in. Restricting this
# to a specific role/group is an open follow-up (see docs/keycloak.md).
c.Authenticator.allow_all = True

admin_users = os.environ.get("JUPYTERHUB_ADMIN_USERS", "")
c.Authenticator.admin_users = {
    user.strip() for user in admin_users.split(",") if user.strip()
}

# --------------------------------------------------------------------------
# Spawner: one Docker container per user
# --------------------------------------------------------------------------
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = os.environ.get(
    "JUPYTERHUB_SINGLEUSER_IMAGE", "bluecore-singleuser:latest"
)

# NOTE: this must match the Docker network this compose project actually
# creates (`docker network ls`), which depends on the Compose project name.
# See docs/architecture.md for why this is a fragile, environment-specific
# value rather than something hardcoded here.
c.DockerSpawner.network_name = os.environ["JUPYTERHUB_DOCKER_NETWORK"]
c.DockerSpawner.use_internal_ip = True

# jupyter/docker-stacks single-user images run as `jovyan` with a home/work
# directory of /home/jovyan/work; a named volume per user persists notebooks
# across container restarts and is seeded from the image's baked-in content
# (training notebooks) on first spawn.
notebook_dir = "/home/jovyan/work"
c.DockerSpawner.notebook_dir = notebook_dir
c.DockerSpawner.volumes = {"jupyterhub-user-{username}": notebook_dir}

c.DockerSpawner.remove = True

# Training notebooks need to reach Keycloak directly (same address the Hub
# itself uses above) rather than through nginx, whose external-facing listen
# port/scheme is environment-specific (e.g. TLS-only on some deployments).
c.DockerSpawner.environment = {
    "KEYCLOAK_INTERNAL_URL": keycloak_internal_url,
    "KEYCLOAK_REALM": keycloak_realm,
}
