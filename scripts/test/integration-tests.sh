#!/usr/bin/env bash
set -euo pipefail

###########################
##  PATHS & BASE FILES   ##
###########################
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-compose-dev.yaml}"
LOCAL_OVERRIDE_FILE="${LOCAL_OVERRIDE_FILE:-compose-integration-test.yaml}"
ARM64_OVERRIDE_FILE="${ARM64_OVERRIDE_FILE:-compose-arm64-workflows.yaml}"
DEV_LIVE_CODE_OVERRIDE_FILE="${DEV_LIVE_CODE_OVERRIDE_FILE:-compose-integration-test-dev-mode.yaml}"
USE_ARM64_WORKFLOWS_OVERRIDE="${USE_ARM64_WORKFLOWS_OVERRIDE:-1}"

###########################
## USER ENV OVERRIDE MAP ##
###########################
user_set_pull_before_up="${PULL_BEFORE_UP+x}"
user_set_keep_stack_up="${KEEP_STACK_UP+x}"
user_set_remove_volumes_on_exit="${REMOVE_VOLUMES_ON_EXIT+x}"
user_set_reset_stack_before_up="${RESET_STACK_BEFORE_UP+x}"
user_set_clean_bind_mount_artifacts_on_exit="${CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT+x}"
user_set_compose_project_name="${COMPOSE_PROJECT_NAME+x}"
user_set_build_local_dev_images="${BUILD_LOCAL_DEV_IMAGES+x}"
user_set_build_local_bc_api_image="${BUILD_LOCAL_BC_API_IMAGE+x}"
user_set_build_local_workflows_image="${BUILD_LOCAL_WORKFLOWS_IMAGE+x}"
user_set_build_local_marva_image="${BUILD_LOCAL_MARVA_IMAGE+x}"
user_set_build_local_marva_middleware_image="${BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE+x}"
user_set_auto_start_stack="${AUTO_START_STACK+x}"
user_set_apply_models_migrations="${APPLY_MODELS_MIGRATIONS+x}"
user_set_models_dir="${MODELS_DIR+x}"

###########################
## RUNNER BEHAVIOR FLAGS ##
###########################
AUTO_START_STACK="${AUTO_START_STACK:-1}"
PULL_BEFORE_UP="${PULL_BEFORE_UP:-1}"
KEEP_STACK_UP="${KEEP_STACK_UP:-0}"
REMOVE_VOLUMES_ON_EXIT="${REMOVE_VOLUMES_ON_EXIT:-1}"
RESET_STACK_BEFORE_UP="${RESET_STACK_BEFORE_UP:-1}"
CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT="${CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT:-1}"
INTEGRATION_FULL_STACK="1"
INTEGRATION_DEV_MODE="${INTEGRATION_DEV_MODE:-0}"
INTEGRATION_DEV_MODE_STOP="${INTEGRATION_DEV_MODE_STOP:-0}"
APPLY_MODELS_MIGRATIONS="${APPLY_MODELS_MIGRATIONS:-1}"
COMPACT_LOG_OUTPUT="${COMPACT_LOG_OUTPUT:-1}"

if [[ "${GITHUB_ACTIONS:-}" == "true" && -z "$user_set_clean_bind_mount_artifacts_on_exit" ]]; then
  CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT="0"
fi

###########################
##   TOOLING & OUTPUT    ##
###########################
DEFAULT_TERRAFORM_VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_TERRAFORM_VENV_PYTHON}"

###########################
##  PROJECT DB & MODELS  ##
###########################
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-terraform_integration}"
INTEGRATION_DB_NAME="${INTEGRATION_DB_NAME:-bluecore_integration_test}"

# Pin the DB credentials for test runs so they are independent of whatever DATABASE_* a developer has in their local .env.
export DATABASE_USERNAME="${DATABASE_USERNAME_TEST_OVERRIDE:-airflow}"
export DATABASE_PASSWORD="${DATABASE_PASSWORD_TEST_OVERRIDE:-airflow}"
export DATABASE_HOSTNAME="${DATABASE_HOSTNAME_TEST_OVERRIDE:-postgres}"
export DATABASE_PORT="${DATABASE_PORT_TEST_OVERRIDE:-5432}"
# Pin Keycloak credentials for tests
export KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN_TEST_OVERRIDE:-admin}"
export KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_TEST_PASSWORD_OVERRIDE:-gracious-professed}"
# Pin the Airflow admin user for tests.
export AIRFLOW_WWW_USER_USERNAME="${AIRFLOW_WWW_USER_USERNAME_TEST_OVERRIDE:-developer}"
export AIRFLOW_WWW_USER_PASSWORD="${AIRFLOW_WWW_USER_PASSWORD_TEST_OVERRIDE:-123456}"

MODELS_DIR="${MODELS_DIR:-$ROOT_DIR/../bluecore-models}"
MODELS_SOURCE_LABEL="${MODELS_SOURCE_LABEL:-bluecore-models@auto}"
POSTGRES_READY_TIMEOUT_SECONDS="${POSTGRES_READY_TIMEOUT_SECONDS:-120}"

###########################
##   LOCAL BUILD INPUTS  ##
###########################
BUILD_LOCAL_DEV_IMAGES="${BUILD_LOCAL_DEV_IMAGES:-0}"
LOCAL_BLUECORE_API_DIR="${LOCAL_BLUECORE_API_DIR:-$ROOT_DIR/../bluecore_api}"
LOCAL_BLUECORE_WORKFLOWS_DIR="${LOCAL_BLUECORE_WORKFLOWS_DIR:-$ROOT_DIR/../bluecore-workflows}"
LOCAL_MARVA_DIR="${LOCAL_MARVA_DIR:-$ROOT_DIR/../marva_editor}"
LOCAL_SINOPIA_DIR="${LOCAL_SINOPIA_DIR:-$ROOT_DIR/../sinopia_editor}"
LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG:-integration-test-local}"
LOCAL_BUILD_PLATFORM="${LOCAL_BUILD_PLATFORM:-}"
BUILD_LOCAL_BC_API_IMAGE="${BUILD_LOCAL_BC_API_IMAGE:-0}"
BUILD_LOCAL_WORKFLOWS_IMAGE="${BUILD_LOCAL_WORKFLOWS_IMAGE:-0}"
BUILD_LOCAL_MARVA_IMAGE="${BUILD_LOCAL_MARVA_IMAGE:-0}"
BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE="${BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE:-0}"
EXTERNAL_CHECKOUT_ROOT="${EXTERNAL_CHECKOUT_ROOT:-$ROOT_DIR/external}"

###########################
##   GIT REF INPUTS      ##
###########################
api_ref=""
workflows_ref=""
marva_ref=""
models_ref=""
BLUECORE_API_REPO_URL="${BLUECORE_API_REPO_URL:-https://github.com/blue-core-lod/bluecore_api.git}"
BLUECORE_WORKFLOWS_REPO_URL="${BLUECORE_WORKFLOWS_REPO_URL:-https://github.com/blue-core-lod/bluecore-workflows.git}"
MARVA_REPO_URL="${MARVA_REPO_URL:-https://github.com/blue-core-lod/marva_editor.git}"
BLUECORE_MODELS_REPO_URL="${BLUECORE_MODELS_REPO_URL:-https://github.com/blue-core-lod/bluecore-models.git}"

###########################
##   KEYCLOAK SETTINGS   ##
###########################
KEYCLOAK_SSL_REQUIRED_OVERRIDE="${KEYCLOAK_SSL_REQUIRED_OVERRIDE:-NONE}"
INTEGRATION_KEYCLOAK_ADMIN_USER="${INTEGRATION_KEYCLOAK_ADMIN_USER:-${KEYCLOAK_ADMIN:-admin}}"
INTEGRATION_KEYCLOAK_ADMIN_PASSWORD="${INTEGRATION_KEYCLOAK_ADMIN_PASSWORD:-${KEYCLOAK_ADMIN_PASSWORD:-gracious-professed}}"

###########################
##  EFFECTIVE OVERRIDES  ##
###########################
user_bluecore_api_image="${BLUECORE_API_IMAGE:-}"
user_bluecore_workflows_image="${BLUECORE_WORKFLOWS_IMAGE:-}"
user_marva_image="${MARVA_IMAGE:-}"
user_marva_middleware_image="${MARVA_KEYCLOAK_MIDDLEWARE_IMAGE:-}"
effective_bluecore_api_image="${user_bluecore_api_image:-ghcr.io/blue-core-lod/bluecore_api:latest}"
effective_bluecore_workflows_image="${user_bluecore_workflows_image:-ghcr.io/blue-core-lod/bluecore-workflows:latest}"
effective_marva_image="${user_marva_image:-}"
effective_marva_middleware_image="${user_marva_middleware_image:-}"

usage() {
  cat <<'EOF'
Usage: ./scripts/test/integration-tests.sh [runner options] [pytest args]

Runner options:
  --dev-mode             Keep stack up, skip reset/pull, default local images project name.
                          If stack is already running, reuse it and skip migrations by default.
  --dev-mode-stop        Stop dev-mode stack, remove containers/images/volumes, then exit.
  --api-ref <ref>        Build API image from a Git ref into terraform/external/bluecore_api
  --workflows-ref <ref>  Build Workflows image from a Git ref into terraform/external/bluecore-workflows
  --marva-ref <ref>      Build Marva + Marva middleware images from a Git ref into terraform/external/marva_editor
  --models-ref <ref>     Run migrations from a Git ref into terraform/external/bluecore-models
  -h, --help             Show this help text

All other args are forwarded to pytest.
Example:
  ./scripts/test/integration-tests.sh --api-ref 76-expand-other-resources
  ./scripts/test/integration-tests.sh --dev-mode tests/integration/test_service_health.py -k airflow
EOF
}

for arg in "$@"; do
  if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
    usage
    exit 0
  fi
  if [[ "$arg" == "--dev-mode-stop" ]]; then
    INTEGRATION_DEV_MODE_STOP="1"
  fi
done

if [[ -z "${AIRFLOW_UID:-}" ]]; then
  AIRFLOW_UID="50000"
fi

# ====================================================================
# Ensure a usable Python runtime exists for local integration tests.
# Prefers terraform/.venv and bootstraps it when missing.
# --------------------------------------------------------------------
ensure_test_python_runtime() {
  if [[ -x "$PYTHON_BIN" ]]; then
    return 0
  fi

  if [[ "$PYTHON_BIN" == "$DEFAULT_TERRAFORM_VENV_PYTHON" ]]; then
    echo "Test venv not found at $DEFAULT_TERRAFORM_VENV_PYTHON"
    echo "Attempting to create terraform test venv..."
    if command -v uv >/dev/null 2>&1; then
      if (cd "$ROOT_DIR" && uv venv .venv); then
        if [[ -x "$DEFAULT_TERRAFORM_VENV_PYTHON" ]]; then
          PYTHON_BIN="$DEFAULT_TERRAFORM_VENV_PYTHON"
          return 0
        fi
      else
        echo "uv venv failed while bootstrapping terraform test venv."
      fi
    fi

    if command -v python3 >/dev/null 2>&1; then
      if python3 -m venv "$ROOT_DIR/.venv"; then
        if [[ -x "$DEFAULT_TERRAFORM_VENV_PYTHON" ]]; then
          PYTHON_BIN="$DEFAULT_TERRAFORM_VENV_PYTHON"
          return 0
        fi
      else
        echo "python3 -m venv failed while bootstrapping terraform test venv."
      fi
    fi

    echo "Unable to create terraform test venv automatically."
    echo "Install uv or ensure python3 venv support is available, then rerun."
    return 1
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    return 0
  fi

  echo "No usable Python interpreter found."
  echo "Checked: $PYTHON_BIN"
  echo "Create a venv in $ROOT_DIR/.venv or set PYTHON_BIN explicitly."
  return 1
}

# ====================================================================
# Ensure Python test dependencies exist in the test interpreter.
# Auto-installs missing packages for local runner convenience.
# --------------------------------------------------------------------
ensure_integration_test_python_deps() {
  if "$PYTHON_BIN" -c "import pytest, playwright, anyio" >/dev/null 2>&1; then
    return 0
  fi

  echo "Integration test Python packages not found in test runtime: $PYTHON_BIN"
  echo "Attempting install: pytest anyio pytest-base-url playwright pytest-playwright"

  if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    if ! "$PYTHON_BIN" -m pip install pytest anyio pytest-base-url playwright pytest-playwright; then
      echo "Failed to install integration test Python dependencies with pip."
      return 1
    fi
  elif command -v uv >/dev/null 2>&1; then
    if ! uv pip install --python "$PYTHON_BIN" pytest anyio pytest-base-url playwright pytest-playwright; then
      echo "Failed to install integration test Python dependencies with uv pip."
      return 1
    fi
  else
    echo "pip is not available in $PYTHON_BIN and uv is not installed."
    echo "Trying to bootstrap pip with ensurepip..."
    if ! "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1; then
      echo "Failed to bootstrap pip with ensurepip."
      echo "Install them manually in the test runtime environment, for example:"
      echo "  uv pip install --python \"$PYTHON_BIN\" pytest anyio pytest-base-url playwright pytest-playwright"
      echo "  # or"
      echo "  $PYTHON_BIN -m ensurepip --upgrade && $PYTHON_BIN -m pip install pytest anyio pytest-base-url playwright pytest-playwright"
      return 1
    fi
    if ! "$PYTHON_BIN" -m pip install pytest anyio pytest-base-url playwright pytest-playwright; then
      echo "Failed to install integration test Python dependencies after ensurepip."
      return 1
    fi
  fi

  if ! "$PYTHON_BIN" -c "import pytest, playwright, anyio" >/dev/null 2>&1; then
    echo "Integration test imports still failing after install attempt."
    return 1
  fi
}

# --------------------------------------------------------------------
# Ensure the Playwright Chromium browser is installed.
# Required by the real-browser UI tests under tests/ui/*. Idempotent (a fast
# no-op once the browser is present). API tests use APIRequestContext and do
# not need a browser, so a failure here only warns rather than aborting.
# --------------------------------------------------------------------
ensure_playwright_browser() {
  if "$PYTHON_BIN" -m playwright install chromium; then
    return 0
  fi
  echo "Warning: could not install the Playwright Chromium browser."
  echo "Browser-based UI tests under tests/ui will fail until it is installed:"
  echo "  $PYTHON_BIN -m playwright install chromium"
}

if [[ "$INTEGRATION_DEV_MODE_STOP" != "1" ]]; then
  if ! ensure_test_python_runtime; then
    exit 1
  fi
  if ! ensure_integration_test_python_deps; then
    exit 1
  fi
  ensure_playwright_browser
fi

log_banner() {
  echo ""
  echo "##############################"
  echo "$1"
  echo "##############################"
}

# ====================================================================
# Build Docker-safe tag fragments from refs by normalizing characters.
# --------------------------------------------------------------------
sanitize_tag_component() {
  local raw="$1"
  local cleaned

  raw="${raw#refs/heads/}"
  raw="${raw#refs/tags/}"
  raw="${raw#refs/}"

  cleaned="$(printf '%s' "$raw" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's#[^a-z0-9._-]+#-#g; s#(^[-._]+|[-._]+$)##g; s#[-._]{2,}#-#g')"

  if [[ -z "$cleaned" ]]; then
    cleaned="local"
  fi

  printf '%.40s' "$cleaned"
}

# ====================================================================
# Ensure a repo exists at target dir and checkout requested ref safely.
# --------------------------------------------------------------------
checkout_repo_ref() {
  local repo_label="$1"
  local repo_url="$2"
  local repo_ref="$3"
  local target_dir="$4"
  local local_branch
  local checkout_source="existing clone"
  local resolved_ref_kind="branch"
  local_branch="integration-$(sanitize_tag_component "$repo_ref")"

  echo ""
  echo "Ref checkout request: $repo_label"
  echo "  remote: $repo_url"
  echo "  ref:    $repo_ref"
  echo "  target: $target_dir"

  mkdir -p "$(dirname "$target_dir")"

  if [[ -d "$target_dir/.git" ]]; then
    if [[ -n "$(git -C "$target_dir" status --porcelain 2>/dev/null)" ]]; then
      echo "Ref checkout blocked for $repo_label; local changes found in $target_dir."
      echo "Commit/stash changes or remove the directory, then rerun."
      return 1
    fi
    git -C "$target_dir" fetch --prune --tags origin >/dev/null
  elif [[ -d "$target_dir" ]]; then
    echo "Ref checkout target exists but is not a git repo: $target_dir"
    return 1
  else
    checkout_source="new clone"
    git clone "$repo_url" "$target_dir" >/dev/null
    git -C "$target_dir" fetch --prune --tags origin >/dev/null
  fi

  if git -C "$target_dir" rev-parse --verify --quiet "refs/remotes/origin/$repo_ref" >/dev/null; then
    resolved_ref_kind="origin branch"
    git -C "$target_dir" checkout -q -B "$local_branch" "refs/remotes/origin/$repo_ref"
  elif git -C "$target_dir" rev-parse --verify --quiet "refs/tags/$repo_ref" >/dev/null; then
    resolved_ref_kind="tag"
    git -C "$target_dir" checkout -q "refs/tags/$repo_ref"
  elif git -C "$target_dir" fetch --prune --tags origin "$repo_ref" >/dev/null 2>&1; then
    resolved_ref_kind="fetched ref"
    git -C "$target_dir" checkout -q FETCH_HEAD
  else
    echo "Unable to resolve ref '$repo_ref' for $repo_label from $repo_url"
    return 1
  fi

  echo "  source: $checkout_source"
  echo "  kind:   $resolved_ref_kind"
  echo "  commit: $(git -C "$target_dir" rev-parse --short HEAD)"
}

# Resolve the latest stable (vX.Y.Z) release tag from a repository.
resolve_latest_release_tag() {
  local repo_url="$1"

  git ls-remote --tags --refs "$repo_url" "v*" 2>/dev/null \
    | sed -E 's#^.*refs/tags/##' \
    | rg '^v[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -V \
    | tail -n 1
}

compose_args=(-f "$COMPOSE_FILE")
if [[ -f "$ROOT_DIR/$LOCAL_OVERRIDE_FILE" ]]; then
  compose_args+=(-f "$LOCAL_OVERRIDE_FILE")
fi

# Only emulate amd64 where needed (workflows services) on Apple Silicon.
if [[ "$(uname -m)" == "arm64" && -f "$ROOT_DIR/$ARM64_OVERRIDE_FILE" && "$USE_ARM64_WORKFLOWS_OVERRIDE" != "0" ]]; then
  compose_args+=(-f "$ARM64_OVERRIDE_FILE")
  log_banner "⚠️  Using arm64 override file: $ARM64_OVERRIDE_FILE"
elif [[ "$(uname -m)" == "arm64" && "$USE_ARM64_WORKFLOWS_OVERRIDE" == "0" ]]; then
  log_banner "ℹ️  Skipping arm64 override file by request"
fi

run_compose() {
  (cd "$ROOT_DIR" && env "${compose_env[@]}" docker compose "${compose_args[@]}" "$@")
}

run_compose_compact() {
  if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
    local output
    if ! output="$(run_compose "$@" 2>&1)"; then
      echo "$output"
      return 1
    fi
    return 0
  fi
  run_compose "$@"
}

ensure_ci_bind_mount_permissions() {
  if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
    return 0
  fi

  mkdir -p "$ROOT_DIR/logs" "$ROOT_DIR/uploads" "$ROOT_DIR/outputs" "$ROOT_DIR/config"
  chmod -R a+rwX "$ROOT_DIR/logs" "$ROOT_DIR/uploads" "$ROOT_DIR/outputs" "$ROOT_DIR/config" || true
}

cleanup_milvus_bind_mount_data() {
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    return 0
  fi

  if [[ "$CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT" != "1" ]]; then
    return 0
  fi

  local milvus_root="$ROOT_DIR/milvus"
  local path
  local removed_any="0"
  local cleanup_paths=(
    "$milvus_root/etcd"
    "$milvus_root/minio"
    "$milvus_root/milvus"
  )

  for path in "${cleanup_paths[@]}"; do
    if [[ "$path" != "$milvus_root/"* ]]; then
      echo "Skipping unsafe cleanup path: $path"
      continue
    fi
    if [[ -L "$path" ]]; then
      echo "Skipping symlink during cleanup: $path"
      continue
    fi
    if [[ -e "$path" ]]; then
      rm -rf "$path" || true
      removed_any="1"
    fi
  done

  if [[ "$removed_any" == "1" && "$COMPACT_LOG_OUTPUT" == "1" ]]; then
    echo "Removed Milvus bind-mount artifacts under $milvus_root."
  fi
}

is_workflows_service() {
  local service="$1"
  case "$service" in
    airflow-*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

compose_service_images() {
  run_compose config | awk '
    $1=="services:" { in_services=1; next }
    in_services && /^[^ ]/ { in_services=0 }
    in_services && /^  [A-Za-z0-9_.-]+:/ {
      service=$1
      sub(":", "", service)
      next
    }
    in_services && /^    image:[[:space:]]+/ {
      image=$2
      gsub(/"/, "", image)
      if (service != "" && image != "") {
        print service "|" image
      }
    }
  '
}

service_should_pull() {
  local service="$1"
  local image="$2"

  if [[ "$BUILD_LOCAL_DEV_IMAGES" == "1" ]]; then
    if [[ "$BUILD_LOCAL_BC_API_IMAGE" == "1" && "$service" == "bc_api" && "$image" == "$effective_bluecore_api_image" ]]; then
      return 1
    fi
    if [[ "$BUILD_LOCAL_WORKFLOWS_IMAGE" == "1" && "$image" == "$effective_bluecore_workflows_image" ]] && is_workflows_service "$service"; then
      return 1
    fi
    if [[ "$BUILD_LOCAL_MARVA_IMAGE" == "1" && "$service" == "marva" && "$image" == "$effective_marva_image" ]]; then
      return 1
    fi
    if [[ "$BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE" == "1" && "$service" == "marva-keycloak-middleware" && "$image" == "$effective_marva_middleware_image" ]]; then
      return 1
    fi
  fi

  return 0
}

compose_services_to_pull() {
  local row service image
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    service="${row%%|*}"
    image="${row#*|}"
    if service_should_pull "$service" "$image"; then
      printf '%s\n' "$service"
    fi
  done < <(compose_service_images)
}

image_registry_source() {
  local image="$1"
  local ref="$image"
  local first

  ref="${ref%@*}"
  first="${ref%%/*}"

  if [[ "$ref" != */* ]]; then
    echo "docker.io/library (default)"
    return
  fi

  if [[ "$first" == "localhost" || "$first" == *.* || "$first" == *:* ]]; then
    echo "$first"
    return
  fi

  echo "docker.io (default)"
}

image_origin_for_service() {
  local service="$1"
  local image="$2"

  if [[ "$BUILD_LOCAL_DEV_IMAGES" == "1" ]]; then
    if [[ "$service" == "bc_api" && "$BUILD_LOCAL_BC_API_IMAGE" == "1" && "$image" == "$effective_bluecore_api_image" ]]; then
      echo "local build ($LOCAL_BLUECORE_API_DIR)"
      return
    fi
    if is_workflows_service "$service" && [[ "$BUILD_LOCAL_WORKFLOWS_IMAGE" == "1" && "$image" == "$effective_bluecore_workflows_image" ]]; then
      echo "local build ($LOCAL_BLUECORE_WORKFLOWS_DIR)"
      return
    fi
    if [[ "$service" == "marva" && "$BUILD_LOCAL_MARVA_IMAGE" == "1" && "$image" == "$effective_marva_image" ]]; then
      echo "local build ($LOCAL_MARVA_DIR)"
      return
    fi
    if [[ "$service" == "marva-keycloak-middleware" && "$BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE" == "1" && "$image" == "$effective_marva_middleware_image" ]]; then
      echo "local build ($LOCAL_MARVA_DIR)"
      return
    fi
  fi

  echo "registry $(image_registry_source "$image")"
}

print_service_image_plan() {
  local row service image origin
  local has_rows=0
  echo "Service image plan:"
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    has_rows=1
    service="${row%%|*}"
    image="${row#*|}"
    origin="$(image_origin_for_service "$service" "$image")"
    printf ' - %-24s -> %-70s [%s]\n' "$service" "$image" "$origin"
  done < <(compose_service_images)

  if [[ "$has_rows" == "0" ]]; then
    echo "No compose images resolved."
  fi
}

build_local_dev_images() {
  local build_platform="$LOCAL_BUILD_PLATFORM"
  local build_args=()

  if [[ -z "$build_platform" && "$(uname -m)" == "arm64" && "$USE_ARM64_WORKFLOWS_OVERRIDE" != "0" ]]; then
    build_platform="linux/amd64"
    echo "Auto-selected LOCAL_BUILD_PLATFORM=$build_platform to match arm64 override."
  else
    build_platform="linux/arm64"
  fi

  if [[ -n "$build_platform" ]]; then
    build_args=(--platform "$build_platform")
  fi

  if [[ "$(uname -m)" == "arm64" && "$USE_ARM64_WORKFLOWS_OVERRIDE" != "0" && -n "$build_platform" && "$build_platform" != "linux/amd64" ]]; then
    echo "Warning: arm64 override is enabled but LOCAL_BUILD_PLATFORM=$build_platform (expected linux/amd64)."
  fi

  if [[ "$BUILD_LOCAL_BC_API_IMAGE" == "1" ]]; then
    if [[ ! -d "$LOCAL_BLUECORE_API_DIR" ]]; then
      echo "Local API directory not found: $LOCAL_BLUECORE_API_DIR"
      return 1
    fi
    echo "Building API image: $effective_bluecore_api_image"
    docker build "${build_args[@]}" -t "$effective_bluecore_api_image" "$LOCAL_BLUECORE_API_DIR"
  fi

  if [[ "$BUILD_LOCAL_WORKFLOWS_IMAGE" == "1" ]]; then
    if [[ ! -d "$LOCAL_BLUECORE_WORKFLOWS_DIR" ]]; then
      echo "Local Workflows directory not found: $LOCAL_BLUECORE_WORKFLOWS_DIR"
      return 1
    fi
    echo "Building Workflows image: $effective_bluecore_workflows_image"
    docker build "${build_args[@]}" -t "$effective_bluecore_workflows_image" "$LOCAL_BLUECORE_WORKFLOWS_DIR"
  fi

  if [[ "$BUILD_LOCAL_MARVA_IMAGE" == "1" || "$BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE" == "1" ]]; then
    if [[ ! -d "$LOCAL_MARVA_DIR" ]]; then
      echo "Local Marva directory not found: $LOCAL_MARVA_DIR"
      return 1
    fi
    if [[ "$BUILD_LOCAL_MARVA_IMAGE" == "1" ]]; then
      echo "Building Marva image: $effective_marva_image"
      if [[ "$INTEGRATION_DEV_MODE" == "1" ]]; then
        docker build "${build_args[@]}" --target builder -t "$effective_marva_image" "$LOCAL_MARVA_DIR"
      else
        docker build "${build_args[@]}" -t "$effective_marva_image" "$LOCAL_MARVA_DIR"
      fi
    fi
    if [[ "$BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE" == "1" ]]; then
      echo "Building Marva middleware image: $effective_marva_middleware_image"
      docker build "${build_args[@]}" -f "$LOCAL_MARVA_DIR/Dockerfile.middleware" -t "$effective_marva_middleware_image" "$LOCAL_MARVA_DIR"
    fi
  fi
}

wait_for_postgres() {
  local deadline
  deadline=$((SECONDS + POSTGRES_READY_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if run_compose exec -T postgres pg_isready -U airflow -d postgres >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for postgres service to become ready."
  return 1
}

ensure_integration_database() {
  if [[ ! "$INTEGRATION_DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Invalid INTEGRATION_DB_NAME: '$INTEGRATION_DB_NAME'. Use only letters, numbers, and underscores."
    return 1
  fi

  run_compose exec -T postgres psql -v ON_ERROR_STOP=1 --username airflow --dbname postgres <<SQL
SELECT 'CREATE DATABASE ${INTEGRATION_DB_NAME}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${INTEGRATION_DB_NAME}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${INTEGRATION_DB_NAME} TO airflow;
SQL
}

apply_bluecore_models_migrations() {
  if [[ ! -d "$MODELS_DIR" ]]; then
    echo "bluecore-models directory not found at '$MODELS_DIR'. Set MODELS_DIR or disable with APPLY_MODELS_MIGRATIONS=0."
    return 1
  fi
  if [[ ! -f "$MODELS_DIR/alembic.ini" ]]; then
    echo "Missing alembic config at '$MODELS_DIR/alembic.ini'."
    return 1
  fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "'uv' is required to run bluecore-models migrations."
    return 1
  fi

  local temp_alembic_config
  temp_alembic_config="$(mktemp "${TMPDIR:-/tmp}/bluecore-models-alembic.XXXXXX.ini")"

  awk -v db_url="$integration_database_url" '
    BEGIN { replaced = 0 }
    /^sqlalchemy[.]url[[:space:]]*=/ {
      print "sqlalchemy.url = " db_url
      replaced = 1
      next
    }
    { print }
    END {
      if (replaced == 0) {
        print "sqlalchemy.url = " db_url
      }
    }
  ' "$MODELS_DIR/alembic.ini" > "$temp_alembic_config"

  if ! (cd "$MODELS_DIR" && UV_LINK_MODE="${UV_LINK_MODE:-copy}" uv run alembic -c "$temp_alembic_config" upgrade head); then
    rm -f "$temp_alembic_config"
    return 1
  fi

  rm -f "$temp_alembic_config"
}

configure_keycloak_ssl_requirement() {
  if [[ -z "$KEYCLOAK_SSL_REQUIRED_OVERRIDE" ]]; then
    return 0
  fi

  local deadline
  deadline=$((SECONDS + POSTGRES_READY_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if run_compose exec -T keycloak /opt/keycloak/bin/kcadm.sh config credentials \
      --server http://localhost:8080/keycloak \
      --realm master \
      --user "$INTEGRATION_KEYCLOAK_ADMIN_USER" \
      --password "$INTEGRATION_KEYCLOAK_ADMIN_PASSWORD" >/dev/null 2>&1 &&
      run_compose exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/bluecore -s "sslRequired=$KEYCLOAK_SSL_REQUIRED_OVERRIDE" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out configuring Keycloak sslRequired to '$KEYCLOAK_SSL_REQUIRED_OVERRIDE'."
  return 1
}

pytest_passthrough_args=()
pytest_passthrough_count=0
base_url_arg_already_set="0"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev-mode)
      INTEGRATION_DEV_MODE="1"
      shift
      ;;
    --dev-mode-stop)
      INTEGRATION_DEV_MODE="1"
      INTEGRATION_DEV_MODE_STOP="1"
      shift
      ;;
    --api-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --api-ref"
        exit 1
      fi
      api_ref="$2"
      shift 2
      ;;
    --workflows-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --workflows-ref"
        exit 1
      fi
      workflows_ref="$2"
      shift 2
      ;;
    --marva-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --marva-ref"
        exit 1
      fi
      marva_ref="$2"
      shift 2
      ;;
    --models-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --models-ref"
        exit 1
      fi
      models_ref="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        pytest_passthrough_args+=("$1")
        pytest_passthrough_count=$((pytest_passthrough_count + 1))
        if [[ "$1" == "--integration-base-url" || "$1" == --integration-base-url=* ]]; then
          base_url_arg_already_set="1"
        fi
        shift
      done
      ;;
    *)
      pytest_passthrough_args+=("$1")
      pytest_passthrough_count=$((pytest_passthrough_count + 1))
      if [[ "$1" == "--integration-base-url" || "$1" == --integration-base-url=* ]]; then
        base_url_arg_already_set="1"
      fi
      shift
      ;;
  esac
done

if [[ "$INTEGRATION_DEV_MODE" == "1" ]]; then
  if [[ -z "$user_set_compose_project_name" ]]; then
    COMPOSE_PROJECT_NAME="terraform_integration_test"
  fi
  if [[ -z "$user_set_build_local_dev_images" ]]; then
    BUILD_LOCAL_DEV_IMAGES="1"
  fi
  if [[ -z "$user_set_build_local_bc_api_image" ]]; then
    BUILD_LOCAL_BC_API_IMAGE="1"
  fi
  if [[ -z "$user_set_build_local_workflows_image" ]]; then
    BUILD_LOCAL_WORKFLOWS_IMAGE="1"
  fi
  if [[ -z "$user_set_build_local_marva_image" ]]; then
    BUILD_LOCAL_MARVA_IMAGE="1"
  fi
  if [[ -z "$user_set_build_local_marva_middleware_image" ]]; then
    BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE="1"
  fi
  if [[ -z "$user_set_keep_stack_up" ]]; then
    KEEP_STACK_UP="1"
  fi
  if [[ -z "$user_set_reset_stack_before_up" ]]; then
    RESET_STACK_BEFORE_UP="0"
  fi
  if [[ -z "$user_set_pull_before_up" ]]; then
    PULL_BEFORE_UP="0"
  fi
  if [[ -z "$user_set_remove_volumes_on_exit" ]]; then
    REMOVE_VOLUMES_ON_EXIT="0"
  fi
  if [[ -z "$user_set_clean_bind_mount_artifacts_on_exit" ]]; then
    CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT="0"
  fi
fi

if [[ "$INTEGRATION_DEV_MODE" == "1" && "$BUILD_LOCAL_DEV_IMAGES" == "1" && -f "$ROOT_DIR/$DEV_LIVE_CODE_OVERRIDE_FILE" ]]; then
  compose_args+=(-f "$DEV_LIVE_CODE_OVERRIDE_FILE")
  if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
    echo "Dev mode live-code mounts enabled via $DEV_LIVE_CODE_OVERRIDE_FILE"
  fi
fi

if [[ -n "$api_ref" || -n "$workflows_ref" || -n "$marva_ref" || -n "$models_ref" ]]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required when using --api-ref/--workflows-ref/--marva-ref/--models-ref."
    exit 1
  fi

  # In ref-driven mode, only build components explicitly selected by --*-ref
  # unless the developer explicitly forced a build flag via environment vars.
  if [[ -z "$user_set_build_local_bc_api_image" ]]; then
    BUILD_LOCAL_BC_API_IMAGE="0"
  fi
  if [[ -z "$user_set_build_local_workflows_image" ]]; then
    BUILD_LOCAL_WORKFLOWS_IMAGE="0"
  fi
  if [[ -z "$user_set_build_local_marva_image" ]]; then
    BUILD_LOCAL_MARVA_IMAGE="0"
  fi
  if [[ -z "$user_set_build_local_marva_middleware_image" ]]; then
    BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE="0"
  fi

  log_banner "📥 Preparing external ref checkouts"
  echo "External checkout root: $EXTERNAL_CHECKOUT_ROOT"

  if [[ -n "$api_ref" ]]; then
    checkout_repo_ref "bluecore_api" "$BLUECORE_API_REPO_URL" "$api_ref" "$EXTERNAL_CHECKOUT_ROOT/bluecore_api"
    BUILD_LOCAL_DEV_IMAGES="1"
    BUILD_LOCAL_BC_API_IMAGE="1"
    LOCAL_BLUECORE_API_DIR="$EXTERNAL_CHECKOUT_ROOT/bluecore_api"
    if [[ -z "$user_bluecore_api_image" ]]; then
      effective_bluecore_api_image="bluecore_api:$(sanitize_tag_component "$api_ref")"
    fi
  fi

  if [[ -n "$workflows_ref" ]]; then
    checkout_repo_ref "bluecore-workflows" "$BLUECORE_WORKFLOWS_REPO_URL" "$workflows_ref" "$EXTERNAL_CHECKOUT_ROOT/bluecore-workflows"
    BUILD_LOCAL_DEV_IMAGES="1"
    BUILD_LOCAL_WORKFLOWS_IMAGE="1"
    LOCAL_BLUECORE_WORKFLOWS_DIR="$EXTERNAL_CHECKOUT_ROOT/bluecore-workflows"
    if [[ -z "$user_bluecore_workflows_image" ]]; then
      effective_bluecore_workflows_image="bluecore_workflows:$(sanitize_tag_component "$workflows_ref")"
    fi
  fi

  if [[ -n "$marva_ref" ]]; then
    checkout_repo_ref "marva_editor" "$MARVA_REPO_URL" "$marva_ref" "$EXTERNAL_CHECKOUT_ROOT/marva_editor"
    BUILD_LOCAL_DEV_IMAGES="1"
    BUILD_LOCAL_MARVA_IMAGE="1"
    BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE="1"
    LOCAL_MARVA_DIR="$EXTERNAL_CHECKOUT_ROOT/marva_editor"
    if [[ -z "$user_marva_image" ]]; then
      effective_marva_image="marva:$(sanitize_tag_component "$marva_ref")"
    fi
    if [[ -z "$user_marva_middleware_image" ]]; then
      effective_marva_middleware_image="marva-keycloak-middleware:$(sanitize_tag_component "$marva_ref")"
    fi
  fi

  if [[ -n "$api_ref" && -z "$workflows_ref" && -z "$user_set_build_local_workflows_image" ]]; then
    BUILD_LOCAL_WORKFLOWS_IMAGE="0"
  fi
  if [[ -z "$api_ref" && -n "$workflows_ref" && -z "$user_set_build_local_bc_api_image" ]]; then
    BUILD_LOCAL_BC_API_IMAGE="0"
  fi

  auto_models_ref=""
  if [[ "$APPLY_MODELS_MIGRATIONS" == "1" && -z "$user_set_models_dir" && -z "$models_ref" ]]; then
    if [[ -n "${INTEGRATION_MODELS_REF:-}" ]]; then
      auto_models_ref="$INTEGRATION_MODELS_REF"
    else
      auto_models_ref="$(resolve_latest_release_tag "$BLUECORE_MODELS_REPO_URL")"
    fi
    if [[ -z "$auto_models_ref" ]]; then
      auto_models_ref="main"
    fi
  fi

  selected_models_ref="${models_ref:-$auto_models_ref}"
  if [[ -n "$selected_models_ref" && -z "$user_set_models_dir" ]]; then
    checkout_repo_ref "bluecore-models" "$BLUECORE_MODELS_REPO_URL" "$selected_models_ref" "$EXTERNAL_CHECKOUT_ROOT/bluecore-models"
    MODELS_DIR="$EXTERNAL_CHECKOUT_ROOT/bluecore-models"
    MODELS_SOURCE_LABEL="bluecore-models@$selected_models_ref"
    models_ref="$selected_models_ref"
  fi
fi

effective_api_ref="${api_ref:-${INTEGRATION_API_REF:-}}"
effective_workflows_ref="${workflows_ref:-${INTEGRATION_WORKFLOWS_REF:-}}"
effective_marva_ref="${marva_ref:-${INTEGRATION_MARVA_REF:-}}"
effective_models_ref="${models_ref:-${INTEGRATION_MODELS_REF:-}}"
if [[ -z "$effective_models_ref" && "$MODELS_SOURCE_LABEL" == bluecore-models@* ]]; then
  effective_models_ref="${MODELS_SOURCE_LABEL#bluecore-models@}"
fi

compose_profiles_value="${COMPOSE_PROFILES:-}"
if [[ "$INTEGRATION_FULL_STACK" == "1" && -z "$compose_profiles_value" ]]; then
  compose_profiles_value="integration-full"
fi

if [[ "$INTEGRATION_FULL_STACK" == "1" ]]; then
  default_api_base_url="${INTEGRATION_BASE_URL:-${INTEGRATION_API_BASE_URL:-http://localhost/api}}"
  default_airflow_base_url="${INTEGRATION_AIRFLOW_BASE_URL:-http://localhost}"
  default_keycloak_token_url="${INTEGRATION_KEYCLOAK_TOKEN_URL:-http://localhost/keycloak/realms/bluecore/protocol/openid-connect/token}"
  default_require_vector_backend="${INTEGRATION_REQUIRE_VECTOR_BACKEND:-1}"
else
  default_api_base_url="${INTEGRATION_BASE_URL:-${INTEGRATION_API_BASE_URL:-http://localhost:${INTEGRATION_API_PORT:-18100}}}"
  default_airflow_base_url="${INTEGRATION_AIRFLOW_BASE_URL:-http://localhost:${INTEGRATION_AIRFLOW_PORT:-18090}}"
  default_keycloak_token_url="${INTEGRATION_KEYCLOAK_TOKEN_URL:-http://localhost:${INTEGRATION_KEYCLOAK_PORT:-18080}/keycloak/realms/bluecore/protocol/openid-connect/token}"
  default_require_vector_backend="${INTEGRATION_REQUIRE_VECTOR_BACKEND:-0}"
fi
default_postgres_port="${POSTGRES_HOST_PORT:-15432}"
integration_database_url="${INTEGRATION_DATABASE_URL:-postgresql+psycopg2://airflow:airflow@localhost:${default_postgres_port}/${INTEGRATION_DB_NAME}}"

compose_env=(
  "COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME"
  "POSTGRES_HOST_PORT=$default_postgres_port"
  "INTEGRATION_DB_NAME=$INTEGRATION_DB_NAME"
  "AIRFLOW_UID=$AIRFLOW_UID"
  "COMPOSE_PROGRESS=plain"
  "COMPOSE_ANSI=auto"
  "BLUECORE_API_IMAGE=$effective_bluecore_api_image"
  "BLUECORE_WORKFLOWS_IMAGE=$effective_bluecore_workflows_image"
  "_PIP_ADDITIONAL_REQUIREMENTS=redis==5.2.1"
)

if [[ "$INTEGRATION_DEV_MODE" == "1" ]]; then
  compose_env+=(
    "LOCAL_BLUECORE_API_DIR=$LOCAL_BLUECORE_API_DIR"
    "LOCAL_BLUECORE_WORKFLOWS_DIR=$LOCAL_BLUECORE_WORKFLOWS_DIR"
    "LOCAL_MARVA_DIR=$LOCAL_MARVA_DIR"
    "LOCAL_SINOPIA_DIR=$LOCAL_SINOPIA_DIR"
  )
fi

if [[ -n "$compose_profiles_value" ]]; then
  compose_env+=("COMPOSE_PROFILES=$compose_profiles_value")
fi

if [[ "$INTEGRATION_DEV_MODE_STOP" == "1" ]]; then
  log_banner "🧹 Stopping dev-mode stack and removing resources..."
  echo "Compose project name: $COMPOSE_PROJECT_NAME"
  echo "Compose files: $COMPOSE_FILE, $LOCAL_OVERRIDE_FILE${ARM64_OVERRIDE_FILE:+, $ARM64_OVERRIDE_FILE}"
  run_compose_compact down -v --remove-orphans --rmi all || true
  CLEAN_BIND_MOUNT_ARTIFACTS_ON_EXIT="1"
  cleanup_milvus_bind_mount_data
  if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
    echo "Dev-mode stack cleanup complete."
  fi
  exit 0
fi

dev_stack_is_running() {
  local running_ids
  running_ids="$(run_compose ps -q 2>/dev/null || true)"
  [[ -n "$running_ids" ]]
}

if [[ "$INTEGRATION_DEV_MODE" == "1" && -z "$user_set_auto_start_stack" && -z "$user_set_apply_models_migrations" ]]; then
  if dev_stack_is_running; then
    AUTO_START_STACK="0"
    APPLY_MODELS_MIGRATIONS="0"
    if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
      echo "Dev mode detected running stack. Reusing services and skipping migrations."
    fi
  fi
fi

if [[ "$base_url_arg_already_set" == "0" ]]; then
  if (( pytest_passthrough_count > 0 )); then
    pytest_args=(--integration-base-url "$default_api_base_url" "${pytest_passthrough_args[@]}")
  else
    pytest_args=(--integration-base-url "$default_api_base_url")
  fi
else
  if (( pytest_passthrough_count > 0 )); then
    pytest_args=("${pytest_passthrough_args[@]}")
  else
    pytest_args=()
  fi
fi

# If developer passed explicit pytest targets (file/dir/nodeid), run only those.
# The default suite runs the HTTP integration tests plus the browser UI tests.
pytest_targets=(tests/integration tests/ui)
if (( pytest_passthrough_count > 0 )); then
  for arg in "${pytest_passthrough_args[@]}"; do
    if [[ "$arg" == *"/"* || "$arg" == *.py || "$arg" == *"::"* ]]; then
      pytest_targets=("$arg")
      break
    fi
  done
fi

if [[ "$AUTO_START_STACK" == "1" ]]; then
  if [[ "$RESET_STACK_BEFORE_UP" == "1" ]]; then
    log_banner "🧹  Resetting integration stack state..."
    run_compose_compact down -v --remove-orphans >/dev/null 2>&1 || true
    cleanup_milvus_bind_mount_data
  fi
  ensure_ci_bind_mount_permissions
  if [[ "$BUILD_LOCAL_DEV_IMAGES" == "1" ]]; then
    if [[ "$BUILD_LOCAL_BC_API_IMAGE" == "1" && -z "$user_bluecore_api_image" && -z "$effective_api_ref" ]]; then
      effective_bluecore_api_image="bluecore_api:${LOCAL_IMAGE_TAG}"
    fi
    if [[ "$BUILD_LOCAL_WORKFLOWS_IMAGE" == "1" && -z "$user_bluecore_workflows_image" && -z "$effective_workflows_ref" ]]; then
      effective_bluecore_workflows_image="bluecore_workflows:${LOCAL_IMAGE_TAG}"
    fi
    if [[ "$BUILD_LOCAL_MARVA_IMAGE" == "1" && -z "$user_marva_image" && -z "$effective_marva_ref" ]]; then
      effective_marva_image="marva:${LOCAL_IMAGE_TAG}"
    fi
    if [[ "$BUILD_LOCAL_MARVA_MIDDLEWARE_IMAGE" == "1" && -z "$user_marva_middleware_image" && -z "$effective_marva_ref" ]]; then
      effective_marva_middleware_image="marva-keycloak-middleware:${LOCAL_IMAGE_TAG}"
    fi
    compose_env+=(
      "BLUECORE_API_IMAGE=$effective_bluecore_api_image"
      "BLUECORE_WORKFLOWS_IMAGE=$effective_bluecore_workflows_image"
      "MARVA_IMAGE=$effective_marva_image"
      "MARVA_KEYCLOAK_MIDDLEWARE_IMAGE=$effective_marva_middleware_image"
    )
    log_banner "🏗️  Building local development images..."
    echo "API source dir: $LOCAL_BLUECORE_API_DIR"
    echo "Workflows source dir: $LOCAL_BLUECORE_WORKFLOWS_DIR"
    echo "Marva source dir: $LOCAL_MARVA_DIR"
    echo "API image: $effective_bluecore_api_image"
    echo "Workflows image: $effective_bluecore_workflows_image"
    echo "Marva image: $effective_marva_image"
    echo "Marva middleware image: $effective_marva_middleware_image"
    if [[ -n "$LOCAL_BUILD_PLATFORM" ]]; then
      echo "Build platform: $LOCAL_BUILD_PLATFORM"
    fi
    build_local_dev_images
  fi
  if [[ "$PULL_BEFORE_UP" == "1" ]]; then
    log_banner "🐳 Pulling images..."
    print_service_image_plan
    if [[ "$BUILD_LOCAL_DEV_IMAGES" == "1" ]]; then
      pull_services=()
      if command -v mapfile >/dev/null 2>&1; then
        mapfile -t pull_services < <(compose_services_to_pull)
      else
        while IFS= read -r service; do
          [[ -n "$service" ]] && pull_services+=("$service")
        done < <(compose_services_to_pull)
      fi
      if [[ ${#pull_services[@]} -gt 0 ]]; then
        run_compose_compact pull "${pull_services[@]}"
      else
        echo "No remote services selected for pull."
      fi
    else
      run_compose_compact pull
    fi
    if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
      echo "Images pulled."
    fi
  fi
  log_banner "🚀 Starting stack with docker compose ($COMPOSE_FILE)..."
  print_service_image_plan
  run_compose_compact up -d
  if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
    echo "Stack started."
    run_compose ps
  fi
fi

log_banner "🩺 Waiting for postgres readiness..."
wait_for_postgres
log_banner "🗄️  Ensuring integration database exists: $INTEGRATION_DB_NAME"
ensure_integration_database

if [[ "$APPLY_MODELS_MIGRATIONS" == "1" ]]; then
  log_banner "🧱 Applying bluecore-models migrations"
  echo "Models source: $MODELS_SOURCE_LABEL"
  echo "Models dir: $MODELS_DIR"
  echo "Migration DB URL: $integration_database_url"
  apply_bluecore_models_migrations
fi

log_banner "🔐 Configuring Keycloak realm sslRequired"
echo "sslRequired: $KEYCLOAK_SSL_REQUIRED_OVERRIDE"
configure_keycloak_ssl_requirement

cleanup() {
  if [[ "$AUTO_START_STACK" == "1" && "$KEEP_STACK_UP" != "1" ]]; then
    log_banner "🧹 Stopping stack..."
    if [[ "$REMOVE_VOLUMES_ON_EXIT" == "1" ]]; then
      run_compose_compact down -v --remove-orphans
      cleanup_milvus_bind_mount_data
    else
      run_compose_compact down
    fi
    if [[ "$COMPACT_LOG_OUTPUT" == "1" ]]; then
      echo "Stack stopped."
    fi
  fi
}
trap cleanup EXIT

log_banner "🧪 Running integration tests..."
echo "Full stack mode: $INTEGRATION_FULL_STACK"
echo "Dev mode: $INTEGRATION_DEV_MODE"
echo "Compose profiles: ${compose_profiles_value:-<none>}"
echo "Integration API base URL: $default_api_base_url"
echo "Integration Airflow base URL: $default_airflow_base_url"
echo "Postgres host port: $default_postgres_port"
echo "Compose project name: $COMPOSE_PROJECT_NAME"
echo "Integration DB name: $INTEGRATION_DB_NAME"
echo "Integration DB URL: $integration_database_url"
echo "Models source: $MODELS_SOURCE_LABEL"
echo "Models dir: $MODELS_DIR"
echo "API ref: ${effective_api_ref:-<none>}"
echo "Workflows ref: ${effective_workflows_ref:-<none>}"
echo "Marva ref: ${effective_marva_ref:-<none>}"
echo "Models ref: ${effective_models_ref:-<none>}"
echo "Airflow UID: $AIRFLOW_UID"
echo "Keycloak token URL: $default_keycloak_token_url"
echo "Bluecore API image: $effective_bluecore_api_image"
echo "Bluecore Workflows image: $effective_bluecore_workflows_image"
echo "Vector backend required: $default_require_vector_backend"
echo "------------------------------"
set +e
(cd "$ROOT_DIR" && INTEGRATION_FULL_STACK="$INTEGRATION_FULL_STACK" COMPOSE_PROFILES="${compose_profiles_value:-}" INTEGRATION_KEYCLOAK_TOKEN_URL="$default_keycloak_token_url" INTEGRATION_AIRFLOW_BASE_URL="$default_airflow_base_url" INTEGRATION_REQUIRE_VECTOR_BACKEND="$default_require_vector_backend" "$PYTHON_BIN" -m pytest "${pytest_targets[@]}" --ignore=external -v -s --color=yes "${pytest_args[@]}")
test_exit_code=$?
set -e

if [[ $test_exit_code -ne 0 ]]; then
  log_banner "❌ Integration tests failed. Showing recent container statuses and logs..."
  run_compose ps
  for service in airflow-scheduler airflow-worker airflow-apiserver; do
    echo ""
    echo "--- Python redis module diagnostics (${service}) ---"
    run_compose exec -T "$service" python -c "import redis,sys; print('redis_file=', getattr(redis, '__file__', None)); print('redis_version=', getattr(redis, '__version__', 'n/a')); print('has_redis_client_attr=', hasattr(redis, 'client')); print('sys_path_head=', sys.path[:4])" || true
    run_compose exec -T "$service" python -m pip show redis || true
  done
  run_compose logs --tail=200
fi

exit $test_exit_code
