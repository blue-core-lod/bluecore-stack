# Blue Core Stack

`bluecore-stack` is the Docker Compose orchestration layer for local Blue Core 
development and integration testing. It wires together the Blue Core API, Blue Core 
Workflows/Airflow, Keycloak, Nginx, Postgres, Marva, Sinopia, and supporting services.

Application source code lives in sibling repositories such as `bluecore_api`, 
`bluecore-workflows`, `marva_editor`, and `sinopia_editor`. This repository starts 
those services either from published container images or from local checkouts 
with live reload.

## 🚀 New Developer Quick Start

> ⚠️ Requires **Docker Compose v5.1.4 or newer** (`docker compose version`).
> See [docs/local-development.md](docs/local-development.md#-prerequisites).

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

   For normal application development and integration testing, keep repos organized in this structure:

   ```text
   <bluecore-repos-directory>
     |-- bluecore-stack/
     |-- bluecore_api/
     |-- bluecore-workflows/
     |-- bluecore-models/
     |-- marva_editor/
     |-- sinopia_editor/
   ```
   > 📝 Tip: You can run `./scripts/dev/update-stack --install` to quickly clone 
   > any missing sibling repositories into the required default paths and seed each 
   > one's local `.env` from `scripts/dev/env-templates/`. See [docs/env-templates.md ](docs/env-templates.md)

   Then start the local-source stack:

   ```bash
   ./scripts/dev/run
   ```

   To run the full stack from published images instead:

   ```bash
   ./scripts/dev/run --image
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

## 🛠️ Common Tasks

| Task | Command or doc                                                                                                    |
|---|-------------------------------------------------------------------------------------------------------------------|
| Run local development stack | `./scripts/dev/run`                                                                                               |
| Bring the stack down | `./scripts/dev/down` ([Local development](docs/local-development.md#-bring-the-stack-down))                       |
| Run a subset | `./scripts/dev/run --sinopia` ([Local development](docs/local-development.md#run-the-stack))                      |
| Keep sibling repos current | `./scripts/dev/update-stack` ([Local development](docs/local-development.md#keep-blue-core-repositories-current)) |
| Load sample or remote JSON-LD data | `./scripts/dev/load-data` (**Airflow running required**)                                                          |
| Load Sinopia resource templates | `./scripts/dev/load-templates` ([Local development](docs/local-development.md#-load-resource-templates))            |
| Run integration tests | `./scripts/test/integration-tests.sh`                                                                             |
| Export local Keycloak realm config | `./scripts/export-keycloak-realm.sh`                                                                              |

## 📚 Documentation

- ⚙️ [Configuration](docs/configuration.md): required `.env` values and local defaults.
- 🚀 [Deployment](docs/deploy.md): env values to change before a public-facing deploy.
- 🧑‍💻 [Local development](docs/local-development.md): local-source mode, image mode, subset starts, live reload, and data loading.
- 🧱 [Developing bluecore-models](docs/bluecore-models.md): local model-code reload behavior and migrations.
- 🔐 [Keycloak](docs/keycloak.md): local users, admin login, realm import/export, and Airflow auth.
- 🧪 [Integration testing](docs/integration-testing.md): local test runner, dev mode, branch refs, local sources, and workflow parity.
- 🖥️ [UI testing](docs/ui-testing.md): browser-driven tests and Playwright debugging.
- 🏗️ [Architecture](docs/architecture.md): compose files, service topology, and Nginx routing.

## 📝 Notes

- The first local-source run builds images and installs frontend dependencies, so it can take a few minutes.
- If a service is disabled in subset mode, the landing page greys it out and refreshes its status periodically.
