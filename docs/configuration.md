# ⚙️ Configuration

Create a `.env` file in the `bluecore-stack` repository root before starting the stack.

The values below are local development defaults. Do not reuse these credentials for deployed environments.

```dotenv
###############################
## GitHub Container Registry ##
###############################
# Create a classic GitHub token with read:packages if you need access to private GHCR images.
CR_PAT=YOUR_GITHUB_TOKEN

##############
## Database ##
##############
# The compose files build every service's DB connection (bc_api, Airflow, and Keycloak) from these four vars. They 
# default to airflow/airflow/postgres/5432, so local dev works as-is; change them for an external DB (see docs/deploy.md).
DATABASE_USERNAME=airflow
DATABASE_PASSWORD=airflow
DATABASE_HOSTNAME=postgres
DATABASE_PORT=5432

###########################
## Airflow Configuration ##
###########################
AIRFLOW_WWW_USER_USERNAME=developer
AIRFLOW_WWW_USER_PASSWORD=123456
AIRFLOW_EXTERNAL_URL=http://localhost/workflows/
AIRFLOW_INTERNAL_URL=http://airflow-apiserver:8080/workflows/
AIRFLOW_PROJ_DIR=.

######################
## Keycloak Clients ##
######################
# Client 1: bluecore_api
API_KEYCLOAK_CLIENT_ID=bluecore_api
BLUECORE_URL=http://localhost

# Client 2: airflow_client
AIRFLOW_KEYCLOAK_CLIENT_ID=bluecore_workflows
AIRFLOW_KEYCLOAK_CLIENT_SECRET=KIu8gWa8rtjlT0Zl7zkNzsObFZGJ2IsJ
KEYCLOAK_INTERNAL_URL=http://keycloak:8080/keycloak/
KEYCLOAK_EXTERNAL_URL=http://localhost/keycloak/

############################
## Keycloak Configuration ##
############################
KC_HOSTNAME_STRICT=false
KEYCLOAK_REALM=bluecore

# Master realm admin credentials
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=gracious-professed

# Keycloak database connection
KC_DB=postgres
KC_DB_URL_HOST=postgres
KC_DB_URL_PORT=5432
KC_DB_URL_DATABASE=keycloak
KC_DB_SCHEMA=public
# Keycloak's DB credentials are derived from DATABASE_USERNAME / DATABASE_PASSWORD
#KC_DB_USERNAME=airflow
#KC_DB_PASSWORD=airflow

# Keycloak health check
KC_HEALTH_ENABLED=true

# Keycloak HTTP and proxy access settings
KC_PROXY_HEADERS=xforwarded
KC_PROXY=edge
KC_HTTP_ENABLED=true
KC_HTTP_RELATIVE_PATH=/keycloak/
KC_LOG_LEVEL=INFO
# KC_HOSTNAME=https://dev.bcld.info/keycloak

####################################
## Marva Middleware Configuration ##
####################################
MARVA_MW_PORT=9401
MARVA_REDIRECT_BASE=http://localhost/marva/
BLUECORE_STACK_KEYCLOAK_REDIRECT_URI=http://localhost/marva/util/auth/callback
KEYCLOAK_MIDDLEWARE_BASE=http://marva-keycloak-middleware:9401/marva/util
CORS_ORIGIN=*
MARVA_UTIL_PATH=https://bibframe.org

##############################################
## Blue Core API HTML Redirect Configuration ##
##############################################
# "Load to Marva/Sinopia" links in local Blue Core API HTML views.
# Production paths are used when these are not present.
MARVA_BASE_URL=http://localhost/marva/
SINOPIA_BASE_URL=http://localhost/sinopia/
```

## 🗄️ Airflow Database Connection

Some DAGs require a `bluecore_db` Postgres connection. The compose files set `AIRFLOW_CONN_BLUECORE_DB` (built from `DATABASE_*`), which Airflow auto-registers as the `bluecore_db` connection;  you don't need to add it to `.env`.

If you need to create it manually in the Airflow UI, use **Admin -> Connections**:

| Field | Value |
|---|---|
| Connection Id | `bluecore_db` |
| Connection Type | `Postgres` |
| Host | `postgres` |
| Database | `bluecore` |
| Login | `airflow` |
| Password | `airflow` |

## 📦 Container Image Access

The compose files use published images from GitHub Container Registry by default. If Docker cannot pull a private image, log in to GHCR with a token that has `read:packages`:

```bash
docker login ghcr.io
```
