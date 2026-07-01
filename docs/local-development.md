# 🧑‍💻 Local Development

Use `scripts/dev/run` as the normal entrypoint for local-source or image-based development.

## ✅ Prerequisites

- **Docker Compose v5.1.4 or newer** Required

  ```bash
  docker compose version   # expect v5.1.4 or greater
  ```
  
- A `.env` file in the repo root. See [configuration.md](configuration.md).
- `uv` installed for API-related helpers such as `scripts/dev/load-data`.
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

`bluecore-models` is included because the local API and workflows import it 
directly. See [bluecore-models.md](bluecore-models.md) for model-code reload 
behavior and migrations.

If your layout differs, set the shared local repository path variables before 
running `scripts/dev/run` or `scripts/dev/update-stack`:

Default values live in `scripts/dev/local-repo-paths`.
```bash
export LOCAL_BLUECORE_API_DIR=/path/to/bluecore_api
export LOCAL_BLUECORE_WORKFLOWS_DIR=/path/to/bluecore-workflows
export LOCAL_BLUECORE_MODELS_DIR=/path/to/bluecore-models
export LOCAL_MARVA_DIR=/path/to/marva_editor
export LOCAL_SINOPIA_DIR=/path/to/sinopia_editor
```
`scripts/dev/run`, `scripts/dev/update-stack`, and `scripts/dev/load-data` use 
the `local-repo-paths`.

## 🔄 Keep Blue Core Repositories Current

Use `scripts/dev/update-stack` to rapidly install, check, and update the 
repositories used by local source mode.

The script knows the default repository paths and base branches:

| Repository | Path variable | Base branch |
|---|---|---|
| `bluecore_api` | `LOCAL_BLUECORE_API_DIR` | `main` |
| `bluecore-models` | `LOCAL_BLUECORE_MODELS_DIR` | `main` |
| `bluecore-workflows` | `LOCAL_BLUECORE_WORKFLOWS_DIR` | `main` |
| `sinopia_editor` | `LOCAL_SINOPIA_DIR` | `main` |
| `marva_editor` | `LOCAL_MARVA_DIR` | `bluecore-dev-mvp` |

```bash
./scripts/dev/update-stack --install  # clone missing repos into configured paths
./scripts/dev/update-stack --check    # fetch and report current/ahead/behind/diverged
./scripts/dev/update-stack            # pull base branches; merge into feature branches
./scripts/dev/update-stack --rebase   # rebase feature branches instead of merging
```

Repositories with tracked uncommitted changes are skipped. Untracked files do 
not block updates. Add `--dry-run` to see the Git commands that would run.

## 🚀 Run the Stack

No flag starts all local-source services. Subset flags are local-source only; 
`--image` always runs the full published-image stack.

```bash
./scripts/dev/run                    # everything
./scripts/dev/run --api              # core + API only
./scripts/dev/run --marva            # core + Marva + middleware
./scripts/dev/run --sinopia          # core + Sinopia
./scripts/dev/run --airflow          # core + Airflow + Milvus
./scripts/dev/run --marva --sinopia  # combine flags
./scripts/dev/run --image            # published images via compose-dev.yaml
```

The first local-source run builds images and installs frontend dependencies, so 
it can take a few minutes. Postgres, Keycloak, Nginx, and the Blue Core API 
always start because the API runs database migrations. API and frontend-only 
subset modes skip Milvus, so embedding endpoints need `--milvus`. Nginx tolerates 
absent services; disabled routes return `502`, and the landing page greys them out.

## 🔁 Live Reload Behavior

| Service | URL | Live reload behavior |
|---|---|---|
| Blue Core API | `http://localhost/api` | `fastapi dev` autoreload with `src/` mounted |
| Workflows / Airflow | `http://localhost/workflows` | DAG and task code mounted into Airflow services |
| Marva | `http://localhost/marva/` | Vite HMR |
| Marva middleware | internal | `node --watch` |
| Sinopia | `http://localhost/sinopia/` | webpack dev server through Nginx |

## 🛑 Bring the Stack Down

Use `scripts/dev/down` to tear everything down.

```bash
./scripts/dev/down            # stop & remove all containers + the network
./scripts/dev/down --volumes  # also delete named volumes (Postgres/Milvus data)
```

Prefer it over a bare `docker compose down`. A plain `down` defaults to 
`compose.yaml` (not `compose-local-dev.yaml`). It also skips profile-gated services 
(`flower`, `airflow-cli`, `Milvus`, …), leaving them running and holding the 
network open (`Resource is still in use`). The wrapper ensures whole stack and 
its network come down cleanly.

## 🔄 Recreate Containers After Compose or Nginx Changes

If you change compose files or Nginx configuration, recreate the stack:

```bash
./scripts/dev/down
./scripts/dev/run <flags>
```

## 📥 Load Data

`scripts/dev/load-data` ingests a Bibframe JSON-LD document into the running 
local stack. It runs the `bluecore` CLI from the sibling `bluecore_api` project 
and points it at the Nginx-fronted local stack.

```bash
./scripts/dev/load-data https://example.org/some/batch.jsonld
./scripts/dev/load-data  # prompt for bundled sample dev data
```

If `bluecore_api` is not in the default sibling location, set `LOCAL_BLUECORE_API_DIR` 
or the legacy `BLUECORE_API_DIR` override:

```bash
LOCAL_BLUECORE_API_DIR=/path/to/bluecore_api ./scripts/dev/load-data
```

## 🧩 Load Resource Templates

`scripts/dev/load-templates` loads Sinopia Resource Templates into the running 
local stack by pulling them from a remote bluecore instance. 

```bash
./scripts/dev/load-templates                        # prompt, then pull from the default remote
./scripts/dev/load-templates https://dev.bcld.info  # pull from a specific remote
```
