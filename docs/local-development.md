# 🧑‍💻 Local Development

Use `scripts/start-dev.sh` as the normal entrypoint for local development. It supports two modes:

| Mode | Command | Best for |
|---|---|---|
| Local source mode | `./scripts/start-dev.sh` | Daily development with live reload |
| Image mode | `./scripts/start-dev.sh --image` | Running the published stack without editing service code |

## ✅ Prerequisites

- Docker with Compose support.
- A `.env` file in the repo root. See [configuration.md](configuration.md).
- `uv` installed for API-related helpers such as `scripts/load-data`.
- Local checkouts of the services you want to edit when using local source mode.

By default, local source mode expects sibling repositories:

```text
<bluecore-repos-directory>
  |-- bluecore-stack/
  |-- bluecore_api/
  |-- bluecore-workflows/
  |-- bluecore-models/
  |-- marva_editor/
  |-- sinopia_editor/
```

`bluecore-models` is included because the local API and workflows import it directly. 
See [bluecore-models.md](bluecore-models.md) for model-code reload behavior and migrations.

If your layout differs, edit the path exports at the top of `scripts/start-dev.sh`:

```bash
export LOCAL_BLUECORE_API_DIR="$ROOT_DIR/../bluecore_api"
export LOCAL_BLUECORE_WORKFLOWS_DIR="$ROOT_DIR/../bluecore-workflows"
export LOCAL_BLUECORE_MODELS_DIR="$ROOT_DIR/../bluecore-models"
export LOCAL_MARVA_DIR="$ROOT_DIR/../marva_editor"
export LOCAL_SINOPIA_DIR="$ROOT_DIR/../sinopia_editor"
```

## 🚀 Start the Stack

Start all local-source services:

```bash
./scripts/start-dev.sh
```

The first run builds images and runs `npm install` for frontends. Later runs are faster.

Start all services from published images:

```bash
./scripts/start-dev.sh --image
```

Image mode runs `compose-dev.yaml`. Local source mode runs `compose-local-dev.yaml`, which extends the same dev stack with local builds and bind mounts.

## 🎚️ Run a Subset

Subset mode is available only in local source mode. Postgres, Keycloak, Nginx, and the Blue Core API always start because the API runs database migrations on startup.

```bash
./scripts/start-dev.sh                    # everything
./scripts/start-dev.sh --api              # core + API only
./scripts/start-dev.sh --marva            # core + Marva + middleware
./scripts/start-dev.sh --sinopia          # core + Sinopia
./scripts/start-dev.sh --airflow          # core + Airflow + Milvus
./scripts/start-dev.sh --marva --sinopia  # combine flags
```

Notes:

- No subset flag means everything starts.
- `--image` always runs the full stack.
- API and frontend-only subset modes skip Milvus, so API embedding endpoints will not work unless you add `--milvus`.
- Nginx tolerates absent services. Routes for disabled services return `502` instead of preventing Nginx from starting.
- The landing page at `http://localhost/` greys out services that are not running and refreshes status periodically.

## 🔁 Live Reload Behavior

| Service | URL | Live reload behavior |
|---|---|---|
| Blue Core API | `http://localhost/api` | `fastapi dev` autoreload with `src/` mounted |
| Workflows / Airflow | `http://localhost/workflows` | DAG and task code mounted into Airflow services |
| Marva | `http://localhost/marva/` | Vite HMR |
| Marva middleware | internal | `node --watch` |
| Sinopia | `http://localhost/sinopia/` | webpack dev server through Nginx |

## 🔄 Recreate Containers After Compose or Nginx Changes

If you change compose files or Nginx configuration, recreate the stack:

```bash
docker compose -f compose-local-dev.yaml down
./scripts/start-dev.sh <flags>
```

## 📥 Load Data

`scripts/load-data` ingests a Bibframe JSON-LD document into the running local stack. It runs the `bluecore` CLI from the sibling `bluecore_api` project and points it at the Nginx-fronted local stack.

Start the stack first, then run:

```bash
# Load a specific JSON-LD URL
./scripts/load-data https://example.org/some/batch.jsonld

# Prompt to load the bundled sample dev dataset
./scripts/load-data
```

If `bluecore_api` is not in the default sibling location, set `BLUECORE_API_DIR`:

```bash
BLUECORE_API_DIR=/path/to/bluecore_api ./scripts/load-data
```
