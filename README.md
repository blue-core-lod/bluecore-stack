# Blue Core Stack

`bluecore-stack` is the Docker Compose orchestration layer for local Blue Core 
development and integration testing. It wires together the Blue Core API, Blue Core 
Workflows/Airflow, Keycloak, Nginx, Postgres, Marva, Sinopia, and supporting services.

Application source code lives in sibling repositories such as `bluecore_api`, 
`bluecore-workflows`, `marva_editor`, and `sinopia_editor`. This repository starts 
those services either from published container images or from local checkouts 
with live reload.

## New Developer Quick Start

1. Clone this repository with submodules:

   ```bash
   git clone --recurse-submodules https://github.com/blue-core-lod/bluecore-stack.git
   cd bluecore-stack
   ```

   If you already cloned without submodules, run:

   ```bash
   git submodule update --init --recursive
   ```

2. Create `.env` in the repository root.

   Use the local development values in [docs/configuration.md](docs/configuration.md). These settings provide local Airflow, Keycloak, database, Marva, and redirect configuration.

3. Decide how you want to run the stack.

   For normal application development with live reload, keep repos organized in this structure:

   ```text
   <bluecore-repos-directory>/
      |-- bluecore-stack/
      |-- bluecore_api/
      |-- bluecore-workflows/
      |-- marva_editor/
      |-- sinopia_editor/
   ```

   Then start the local-source stack:

   ```bash
   ./scripts/start-dev.sh
   ```

   To run the full stack from published images instead:

   ```bash
   ./scripts/start-dev.sh --image
   ```

4. Open the local landing page:

   ```text
   http://localhost/
   ```

   Nginx routes the main services under this host:

   | Service | URL |
   |---|---|
   | Blue Core API | `http://localhost/api` |
   | Airflow / Workflows | `http://localhost/workflows` |
   | Keycloak | `http://localhost/keycloak` |
   | Marva | `http://localhost/marva/` |
   | Sinopia | `http://localhost/sinopia/` |

5. Sign in with local development credentials.

   Airflow uses the imported Keycloak realm. Use username `developer` and password `123456`. See [docs/keycloak.md](docs/keycloak.md) for all local accounts and realm export steps.

## Common Tasks

| Task | Command or doc |
|---|---|
| Start everything from local source with live reload | `./scripts/start-dev.sh` |
| Start only core services and API | `./scripts/start-dev.sh --api` |
| Start core services plus Marva | `./scripts/start-dev.sh --marva` |
| Start core services plus Sinopia | `./scripts/start-dev.sh --sinopia` |
| Start core services plus Airflow and Milvus | `./scripts/start-dev.sh --airflow` |
| Start from published images | `./scripts/start-dev.sh --image` |
| Load sample or remote JSON-LD data | `./scripts/load-data` |
| Run integration tests | `./scripts/integration-tests.sh` |
| Export local Keycloak realm config | `./scripts/export-keycloak-realm.sh` |

## Documentation

- [Configuration](docs/configuration.md): required `.env` values and local defaults.
- [Local development](docs/local-development.md): local-source mode, image mode, subset starts, live reload, and data loading.
- [Keycloak](docs/keycloak.md): local users, admin login, realm import/export, and Airflow auth.
- [Integration testing](docs/testing.md): local test runner, dev mode, branch refs, local sources, and workflow parity.
- [Architecture](docs/architecture.md): compose files, service topology, and Nginx routing.

## Notes

- The first local-source run builds images and installs frontend dependencies, so it can take a few minutes.
- If a service is disabled in subset mode, the landing page greys it out and refreshes its status periodically.