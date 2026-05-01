# Blue Core Stack with Docker

## Set-up
To clone the repository with git, `git clone --recurse-submodules .`.

## ⚙️ Configuration
The development Keycloak Container requires a local `.env` with the following variables:

```
###############################----------------------------
## GitHub Container Registry ##
###############################
# create a "classic" GitHub token and ensure it grants permission to read:packages
CR_PAT=YOUR_GITHUB_TOKEN

###########################--------------------------------
## Airflow Configuration ##
###########################
DATABASE_URL=postgresql+psycopg2://airflow:airflow@postgres/bluecore
AIRFLOW_WWW_USER_USERNAME=airflow
AIRFLOW_WWW_USER_PASSWORD=airflow
AIRFLOW_EXTERNAL_URL=http://localhost/workflows/
AIRFLOW_INTERNAL_URL=http://airflow-apiserver:8080/workflows/
AIRFLOW_PROJ_DIR=.
AIRFLOW_CONN_BLUECORE_DB='postgresql://airflow:airflow@postgres:5432/bluecore'

######################-------------------------------------
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

############################-------------------------------
## Keycloak Configuration ##
############################
# Bluecore realm and keycloak path
KC_HOSTNAME_STRICT=false
KEYCLOAK_REALM=bluecore

# Master realm Admin credentials
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=gracious-professed

# Keycloak database connection
KC_DB=postgres
KC_DB_URL_HOST=postgres
KC_DB_URL_PORT=5432
KC_DB_URL_DATABASE=keycloak
KC_DB_SCHEMA=public
KC_DB_USERNAME=airflow
KC_DB_PASSWORD=airflow

# Keycloak health check enabled
KC_HEALTH_ENABLED=true 

# Keycloak HTTP and proxy access settings
KC_PROXY_HEADERS=xforwarded
KC_PROXY=edge
KC_HTTP_ENABLED=true
KC_HTTP_RELATIVE_PATH=/keycloak/
KC_LOG_LEVEL=INFO
# KC_HOSTNAME=https://dev.bcld.info/keycloak

####################################-----------------------
## Marva Middleware Configuration ##
####################################
MARVA_MW_PORT=9401
MARVA_REDIRECT_BASE=http://localhost/marva/
BLUECORE_STACK_KEYCLOAK_REDIRECT_URI=http://localhost/marva/util/auth/callback
KEYCLOAK_MIDDLEWARE_BASE=http://marva-keycloak-middleware:9401/marva/util
CORS_ORIGIN=*
# MARVA_UTIL_PATH= #TODO: will need to be configured with marva backend for additional Marva features

# ---------------------------------------------------------
# Env Values already assigned in "Keycloak Clients" section
# ---------------------------------------------------------
# KEYCLOAK_INTERNAL_URL=http://keycloak:8080/keycloak/
# KEYCLOAK_EXTERNAL_URL=http://localhost/keycloak/
```

## 🛠️ Setup Airflow (Blue Core Workflows)
### Blue Core Database Connection
Some DAGs require a `bluecore_db` Postgres Connection (In the UI from the **Admin -> Connection** menu) 
with the following variables:

- **Connection Id**: bluecore_db
- **Connection Type**: Postgres
- **Host**: postgres
- **Database**: bluecore
- **Login**: airflow
- **Password**: airflow

Setting AIRFLOW_CONN_BLUECORE_DB environment variable will achieve similar goal.

## 🔐 Keycloak local development and credentials
Keycloak will automatically import realm config located at: `keycloak-export/bluecore-realm.json` \
when the Keycloak container starts. 
### 🔑 Logging into Airflow using Keycloak with developer credentials
Airflow local development URL:
>  - http://localhost/workflows

This realm config contains the following:
> - Realm: `bluecore`
> - Client: `bluecore_workflows`
> - Username: `developer` #admin account
> - password: `123456`
> 
>⚠️ **Note**: Other account names that can be used are: `dev_op`,`dev_public`,`dev_user`, and `dev_viewer` with the same password. 
> These accounts reflect the roles associated in their name.
### 🔑 Logging into Keycloak master realm
You can also create a new realm and client in Keycloak by going to:
> - http://localhost/keycloak 
> - username: `admin` 
> - password: `gracious-professed`

###  💾 Exporting Keycloak realm config
To export any changes of the bluecore realm config, you can use the following commands
depending on the environment you are working in:
###### 🚧 Local Development
```bash
   ./scripts/export-keycloak-realm.sh
````
###### 🚀 Deployed Production in EC2
```bash
   ./scripts/export-keycloak-realm.sh --env=production
```

This will export the realm config to the `keycloak-export` directory.


## 📐 Blue Core Technical Stack
```mermaid
graph LR;
    sinopia["Sinopia"] --> keycloak["Keycloak"]
    marva["Marva"] --> keycloak
    graph_toolkit["Graph Toolkit"] --> keycloak
    notebooks@{ shape: docs, label: "Jupyter Notebooks"} --> keycloak

    keycloak <--> api["Blue Core API"]
    keycloak <--> workflows["Blue Core Workflows (Airflow)"]
    api <--> db[("Blue Core Database")]
    api --> workflows
    workflows <--> db
    db <--> vector_db[("Triples Vector Datastore")]
    api <--> vector_db
    workflows <--> vector_db
    api <--> ai_agents@{ shape: procs, label: "LLM AI Agents"}
    ai_agents <--> workflows
    ai_agents <--> vector_db
```
## 🐳 Running Locally with Docker
Dev Docker compose file needs to be specified when starting the container service.
```bash
docker compose -f compose-dev.yaml up
```

### 🚧 Using Local code in Blue Stack
📝 Note: Blue Stack deploys locally with images pulled from GitHub. 
<br/>
In order to `deploy from your local code` to see any development changes [See This Guide](https://github.com/blue-core-lod/bluecore_info/wiki/Building-and-using-local-images-inside-Terraform-and-Blue%E2%80%90stack).


## 🧪 Integration Test Suite
Use this suite to validate API + Workflows + Keycloak behavior before merging.
Tests use Playwright's `APIRequestContext` (HTTP-only, no browser UI).

### What is covered
- API and Airflow endpoint reachability.
- Auth contract for API write endpoints.
- Keycloak-authenticated DAG triggers (`resource_loader`, `monitor_institutions_exports`).
- Ingest + processed readback checks.
- Embedding create/read behavior when vector backend is enabled.

### Which script to use
- `./scripts/integration-tests.sh`: normal local test runner (recommended for daily dev).
- `./scripts/workflow-tests.sh`: GitHub Actions parity runner via `act`.

### Quick start (recommended)
From `terraform/`:
```bash
./scripts/integration-tests.sh
```


### Dev mode (fast reruns)
Use this for iterative local development where code changes are reflected in tests.

```bash
# Start/reuse dev stack and run full integration suite (containers remain active)
./scripts/integration-tests.sh --dev-mode

# Run a targeted selection against the same stack
./scripts/integration-tests.sh --dev-mode tests/integration/workflows/test_health.py -k airflow

# Stop the dev stack and exit
./scripts/integration-tests.sh --dev-mode-stop
```

Dev mode behavior:
- Uses `COMPOSE_PROJECT_NAME=terraform_integration_test`.
- Keeps stack up between runs.
- Skips pull/reset by default.
- If stack is already running, model migrations are skipped by default.
- Adds a dev-only compose override that bind-mounts local API/workflows source into containers.
- API runs in autoreload mode (`fastapi dev`) so local API code edits are reflected without rebuilding images.
- Workflows code (`ils_middleware`) is bind-mounted into Airflow services so DAG/task code edits are visible without rebuilding images.

Note:
- If you already had a dev-mode stack running before this behavior was added, run `./scripts/integration-tests.sh --dev-mode-stop` once, then start dev mode again so containers are recreated with the new mounts/command.

### Test Git branch refs directly (no manual checkout)
`integration-tests.sh` can fetch/build branches into `terraform/external/`.

```bash
# API ref only (other services pulled from images generated from main branches)
./scripts/integration-tests.sh --api-ref <bluecore_api branch>

# API + workflows + models refs together
./scripts/integration-tests.sh \
  --api-ref <bluecore_api branch> \
  --workflows-ref <bluecore-workflow branch> \
  --models-ref <bluecore-models branch>
```

Branch ref behavior:
- `--api-ref`: builds API image from that branch reference and tags it as `bluecore_api:<ref>`.
- `--workflows-ref`: builds workflows image from that branch reference and tags it as `bluecore_workflows:<ref>`.
- `--models-ref`: uses that models branch reference for migrations.

### Local source mode (your local checkouts)
```bash
# Build API/workflows from sibling repos (../bluecore_api and ../bluecore-workflows)
BUILD_LOCAL_DEV_IMAGES=1 ./scripts/integration-tests.sh
```

CI Notes:
- Apple Silicon: `compose-arm64-workflows.yaml` is added automatically.
- GitHub Actions: Milvus bind-mount cleanup is skipped by default to avoid container file permission noise.

## 🧪 Workflow Parity Runner (`workflow-tests.sh`)
Use this when you want local execution that matches `.github/workflows/manual-integration-test.yml`.

### Quick commands
```bash
# Default parity run
./scripts/workflow-tests.sh

# Build refs through workflow-style inputs
./scripts/workflow-tests.sh \
  --api-ref <bluecore_api branch>  \
  --workflows-ref <bluecore-workflow branch> \
  --models-ref <bluecore-models branch>

# Use local checkouts for api/workflows/models
./scripts/workflow-tests.sh --local-sources
```

### Local-source options (default path set to "../\<bluecore app\>")
```bash
# Use only local API checkout
./scripts/workflow-tests.sh --local-api

# Use only local workflows checkout
./scripts/workflow-tests.sh --local-workflows

# Use only local models checkout for migrations
./scripts/workflow-tests.sh --local-models

# Custom local checkout paths
./scripts/workflow-tests.sh \
  --local-api-dir ../my-bluecore_api \
  --local-workflows-dir ../my-bluecore-workflows \
  --local-models-dir ../my-bluecore-models
```

### Required secrets for `act`
Create `terraform/.secrets`:
```bash
GITHUB_TOKEN=ghp_or_github_pat
BLUECORE_REPO_READ_TOKEN=ghp_or_github_pat
```

Token guidance:
- `GITHUB_TOKEN` and `BLUECORE_REPO_READ_TOKEN` must be able to read required repos/images.
- For private GHCR images, run `docker login ghcr.io` with a token that has `read:packages`.
