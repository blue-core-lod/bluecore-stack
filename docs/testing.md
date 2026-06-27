# 🧪 Integration Testing

Use the integration suite to validate API, Workflows/Airflow, and Keycloak behavior before merging changes.

Tests use Playwright's `APIRequestContext` for HTTP-only checks. They do not drive a browser UI.

## ✅ What Is Covered

- API and Airflow endpoint reachability.
- Auth behavior for API write endpoints.
- Keycloak-authenticated DAG triggers, including `resource_loader` and `monitor_institutions_exports`.
- Ingest and processed readback checks.
- Embedding create/read behavior when the vector backend is enabled.

## 🏃 Local Runner

Run from the `bluecore-stack` repository root:

```bash
./scripts/integration-tests.sh
```

Forward pytest arguments after script options:

```bash
./scripts/integration-tests.sh tests/integration/workflows/test_health.py -k airflow
```

The script creates or reuses a local test Python environment at `.venv` when needed.

## ⚡ Dev Mode for Fast Reruns

Use dev mode when iterating locally. It keeps the stack running between runs and bind-mounts local API and workflow source into containers.

```bash
# Start or reuse the dev-mode test stack and run the full suite
./scripts/integration-tests.sh --dev-mode

# Run a targeted test selection against the same stack
./scripts/integration-tests.sh --dev-mode tests/integration/workflows/test_health.py -k airflow

# Stop and remove the dev-mode test stack
./scripts/integration-tests.sh --dev-mode-stop
```

Dev mode behavior:

- Uses `COMPOSE_PROJECT_NAME=terraform_integration_test`.
- Keeps containers up between runs.
- Skips pull/reset by default.
- Skips migrations by default when the stack is already running.
- Adds `compose-integration-test-dev-mode.yaml`.
- Runs the API with `fastapi dev` autoreload.
- Bind-mounts workflows code into Airflow services.

If an older dev-mode stack was already running before a compose behavior change, run `./scripts/integration-tests.sh --dev-mode-stop` once, then restart dev mode.

## 🌿 Test Git Branch Refs

`integration-tests.sh` can fetch and build branch references into `external/`.

```bash
# API ref only
./scripts/integration-tests.sh --api-ref <bluecore_api branch>

# API + workflows + models refs together
./scripts/integration-tests.sh \
  --api-ref <bluecore_api branch> \
  --workflows-ref <bluecore-workflows branch> \
  --models-ref <bluecore-models branch>
```

Ref behavior:

- `--api-ref` builds an API image from that ref and tags it as `bluecore_api:<ref>`.
- `--workflows-ref` builds a workflows image from that ref and tags it as `bluecore_workflows:<ref>`.
- `--models-ref` uses that models ref for migrations.

## 🧩 Local Source Test Mode

Build API and workflows from sibling repositories:

```bash
BUILD_LOCAL_DEV_IMAGES=1 ./scripts/integration-tests.sh
```

Apple Silicon uses `compose-arm64-workflows.yaml` automatically.

## 🔁 Workflow Parity Runner

Use `scripts/workflow-tests.sh` when you want local execution that mirrors `.github/workflows/bluecore-integration-test.yml`. It uses `act`.

```bash
# Default parity run
./scripts/workflow-tests.sh

# Build refs through workflow-style inputs
./scripts/workflow-tests.sh \
  --api-ref <bluecore_api branch> \
  --workflows-ref <bluecore-workflows branch> \
  --models-ref <bluecore-models branch>

# Use local checkouts for API, workflows, and models
./scripts/workflow-tests.sh --local-sources
```

Local-source options:

```bash
./scripts/workflow-tests.sh --local-api
./scripts/workflow-tests.sh --local-workflows
./scripts/workflow-tests.sh --local-models

./scripts/workflow-tests.sh \
  --local-api-dir ../my-bluecore_api \
  --local-workflows-dir ../my-bluecore-workflows \
  --local-models-dir ../my-bluecore-models
```

Create `.secrets` in the repo root for `act`:

```dotenv
GITHUB_TOKEN=ghp_or_github_pat
BLUECORE_REPO_READ_TOKEN=ghp_or_github_pat
```

Token guidance:

- `GITHUB_TOKEN` and `BLUECORE_REPO_READ_TOKEN` must be able to read required repos and images.
- For private GHCR images, run `docker login ghcr.io` with a token that has `read:packages`.
