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
  |     `-- nginx/toolbox/   <- graph-toolbox (Git submodule)
  |-- bluecore_api/
  |-- bluecore-workflows/
  |-- bluecore-models/
  |-- marva_editor/
  |-- sinopia_editor/
```

`bluecore-models` is included because the local API and workflows import it 
directly. See [bluecore-models.md](bluecore-models.md) for model-code reload 
behavior and migrations.

`graph-toolbox` is the one dependency that is *not* a sibling checkout: it is a 
Git submodule pinned inside this repo at `nginx/toolbox`. See 
[graph-toolbox is a submodule, not a sibling](#-graph-toolbox-is-a-submodule-not-a-sibling).

If your layout differs, set the shared local repository path variables before 
running `scripts/dev/run` or `scripts/dev/update-stack`:

Default values live in `scripts/dev/local-repo-paths`.
```bash
export LOCAL_BLUECORE_API_DIR=/path/to/bluecore_api
export LOCAL_BLUECORE_WORKFLOWS_DIR=/path/to/bluecore-workflows
export LOCAL_BLUECORE_MODELS_DIR=/path/to/bluecore-models
export LOCAL_MARVA_DIR=/path/to/marva_editor
export LOCAL_SINOPIA_DIR=/path/to/sinopia_editor
export LOCAL_GRAPH_TOOLBOX_DIR=/path/to/graph-toolbox  # defaults to nginx/toolbox (submodule)
```
`scripts/dev/run`, `scripts/dev/update-stack`, and `scripts/dev/load-data` use 
the `local-repo-paths`.

## 🔄 Keep Blue Core Repositories Current

Use `scripts/dev/update-stack` to rapidly install, check, and update the 
repositories used by local source mode.

The script knows the default repository paths and base branches:

| Repository | Path variable | Default location | Base branch |
|---|---|---|---|
| `bluecore_api` | `LOCAL_BLUECORE_API_DIR` | sibling `../bluecore_api` | `main` |
| `bluecore-models` | `LOCAL_BLUECORE_MODELS_DIR` | sibling `../bluecore-models` | `main` |
| `bluecore-workflows` | `LOCAL_BLUECORE_WORKFLOWS_DIR` | sibling `../bluecore-workflows` | `main` |
| `sinopia_editor` | `LOCAL_SINOPIA_DIR` | sibling `../sinopia_editor` | `main` |
| `marva_editor` | `LOCAL_MARVA_DIR` | sibling `../marva_editor` | `bluecore-dev-mvp` |
| `graph-toolbox` | `LOCAL_GRAPH_TOOLBOX_DIR` | **submodule** `nginx/toolbox` | `main` |

```bash
./scripts/dev/update-stack --install  # clone missing repos, init the submodule, seed .env files
./scripts/dev/update-stack --check    # fetch and report current/ahead/behind/diverged
./scripts/dev/update-stack            # pull base branches; merge into feature branches
./scripts/dev/update-stack --rebase   # rebase feature branches instead of merging
```

### What `--install` does

`--install` only installs; it never pulls, merges, or rebases a repo that is 
already present. For each repository it:

- clones the repo at its base branch if the checkout is missing (or, for 
  `graph-toolbox`, initializes the submodule... see below);
- generates the repo's `.env` from `scripts/dev/env-templates/<repo>.env` when 
  the repo has no `.env` yet. Existing `.env` files are never overwritten, and 
  repos without a template (`bluecore-models`) are left alone. See 
  [env-templates.md](env-templates.md);
- seeds `bluecore-stack`'s own `.env` from 
  `scripts/dev/env-templates/bluecore-stack.env` when it is missing.


### 🧩 graph-toolbox is a submodule, not a sibling

`graph-toolbox` supplies the Nginx landing page and graph tooling served at 
`nginx/toolbox`, and it is wired into `bluecore-stack` as a Git submodule 
(see `.gitmodules`) rather than as a sibling checkout. That changes how 
`update-stack` treats it:

- **Install**: `--install` runs `git submodule update --init --recursive` 
  instead of cloning. (This is the same thing `git clone --recurse-submodules` 
  or a manual `git submodule update --init --recursive` does; running 
  `--install` after a plain clone is enough to populate it.)

- **Check**: `--check` compares the pinned commit against `origin/main` and reports how far 
  behind it is, and an update checks out `main` before pulling.
  
- **Updating**: `update-stack` (no flags) checks out `main` and pulls all the latest updates.
  `bluecore-stack` shows an unstaged change to `nginx/toolbox`. That change *is* the new pointer. Commit it to bump the stack to the newer `graph-toolbox`:

  If you leave it unstaged, the next `git submodule update` (or a fresh clone) 
  resets `nginx/toolbox` back to the old pinned commit and your update is 
  discarded.

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
