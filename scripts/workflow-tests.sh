#!/usr/bin/env bash
set -euo pipefail

###########################
##    PATHS & ROOT DIR   ##
###########################
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

###########################
##  ACT RUNTIME DEFAULTS ##
###########################
event_name="${ACT_EVENT:-push}"
job_name="${ACT_JOB:-integration}"
container_arch="${ACT_CONTAINER_ARCH:-linux/amd64}"
ubuntu_image="${ACT_UBUNTU_IMAGE:-ghcr.io/catthehacker/ubuntu:act-24.04}"
secret_file="${ACT_SECRET_FILE:-.secrets}"
act_rm_on_failure="${ACT_RM_ON_FAILURE:-1}"

###########################
##   EXECUTION MODES     ##
###########################
use_workflow_dispatch=0
local_sources_mode=0
local_api_mode=0
local_workflows_mode=0
local_models_mode=0

###########################
##   BUILD/REF INPUTS    ##
###########################
build_api_image="false"
build_workflows_image="false"
api_ref=""
workflows_ref=""
models_ref=""

###########################
##   LOCAL SOURCE DIRS   ##
###########################
local_api_dir="${LOCAL_BLUECORE_API_DIR:-$ROOT_DIR/../bluecore_api}"
local_workflows_dir="${LOCAL_BLUECORE_WORKFLOWS_DIR:-$ROOT_DIR/../bluecore-workflows}"
local_models_dir="${MODELS_DIR:-$ROOT_DIR/../bluecore-models}"

###########################
## PROJECT/EXTRA ARGS    ##
###########################
compose_project_name="${COMPOSE_PROJECT_NAME:-}"
act_extra_args=()

# ====================================================================
# Build a Docker-safe tag fragment from refs/branch names.
# Normalizes case and characters, trims separators, and limits length.
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

# ===================================================================
# Build a Compose-compatible project name.
# Keeps only supported characters and enforces Compose length limits.
# -------------------------------------------------------------------
sanitize_compose_project_name() {
  local raw="$1"
  local cleaned

  cleaned="$(printf '%s' "$raw" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's#[^a-z0-9_-]+#-#g; s#(^[-_]+|[-_]+$)##g; s#[-_]{2,}#-#g')"

  if [[ -z "$cleaned" ]]; then
    cleaned="terraform_integration_ci"
  fi

  printf '%.63s' "$cleaned"
}

if [[ -z "$compose_project_name" ]]; then
  compose_project_name="terraform_integration_ci-$(date +%Y%m%d%H%M%S)-$$"
fi
compose_project_name="$(sanitize_compose_project_name "$compose_project_name")"

# ===============================================================
# Remove stale act Manual Integration containers from prior runs.
# Helps avoid accidental reuse/conflicts and disk buildup.
# ---------------------------------------------------------------
cleanup_stale_act_manual_integration_containers() {
  if [[ "${CLEANUP_STALE_ACT_CONTAINERS:-1}" != "1" ]]; then
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local docker_ps_output
  if ! docker_ps_output="$(docker ps -a --format '{{.ID}} {{.Names}}' 2>/dev/null)"; then
    echo "Warning: unable to inspect Docker containers for stale act jobs; continuing."
    return 0
  fi

  local stale_names=()
  local stale_ids=()
  while IFS='|' read -r id name; do
    [[ -z "$id" || -z "$name" ]] && continue
    stale_ids+=("$id")
    stale_names+=("$name")
  done < <(printf '%s\n' "$docker_ps_output" | awk '$2 ~ /^act-Bluecore-Integration-Test-/ {print $1 "|" $2}')

  if [[ ${#stale_ids[@]} -eq 0 ]]; then
    return 0
  fi

  echo "Removing stale act Bluecore Integration Test containers:"
  for name in "${stale_names[@]}"; do
    echo " - $name"
  done

  if ! docker rm -f "${stale_ids[@]}" >/dev/null 2>&1; then
    echo "Warning: failed to remove some stale act containers; continuing."
  fi
}

# ================================================================
# Detect the current branch (or short SHA) for a local repository.
# Falls back to "local" when repo metadata is unavailable.
# ----------------------------------------------------------------
detect_repo_ref() {
  local repo_dir="$1"
  local ref=""

  if git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    ref="$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ -z "$ref" || "$ref" == "HEAD" ]]; then
      ref="$(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || true)"
    fi
  fi

  if [[ -z "$ref" ]]; then
    ref="local"
  fi

  printf '%s' "$ref"
}

# ===============================================================
# Print CLI usage and examples for workflow-tests runner options.
# ---------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: ./scripts/workflow-tests.sh [options] [extra act args]

Options:
  --local-sources               Use local api/workflows/models repos directly
  --local-api                   Use local bluecore_api (others from registry)
  --local-workflows             Use local bluecore-workflows (others from registry)
  --local-models                Use local bluecore-models for migrations
  --local-api-dir <path>        Path to local bluecore_api checkout
  --local-workflows-dir <path>  Path to local bluecore-workflows checkout
  --local-models-dir <path>     Path to local bluecore-models checkout
  --api-ref <ref>               Build bluecore_api image from git ref/branch before tests
  --workflows-ref <ref>         Build bluecore-workflows image from git ref/branch before tests
  --models-ref <ref>            Use bluecore-models git ref/branch for migrations
  -h, --help                    Show this help text

Examples:
  ./scripts/workflow-tests.sh
  ./scripts/workflow-tests.sh --local-sources
  ./scripts/workflow-tests.sh --local-api
  ./scripts/workflow-tests.sh --local-workflows
  ./scripts/workflow-tests.sh --local-api --local-workflows
  ./scripts/workflow-tests.sh --local-api --local-models
  ./scripts/workflow-tests.sh --local-sources --local-api-dir ../bluecore_api
  ./scripts/workflow-tests.sh --api-ref my-feature-branch
  ./scripts/workflow-tests.sh --workflows-ref workflows-feature-branch
  ./scripts/workflow-tests.sh --models-ref models-feature-branch
  ./scripts/workflow-tests.sh --api-ref my-feature-branch --models-ref my-models-branch
  ./scripts/workflow-tests.sh --api-ref my-feature-branch --workflows-ref workflows-feature-branch --models-ref my-models-branch
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-sources)
      local_sources_mode=1
      shift
      ;;
    --local-api)
      local_api_mode=1
      shift
      ;;
    --local-workflows)
      local_workflows_mode=1
      shift
      ;;
    --local-models)
      local_models_mode=1
      shift
      ;;
    --local-api-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --local-api-dir"
        exit 1
      fi
      local_api_dir="$2"
      shift 2
      ;;
    --local-workflows-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --local-workflows-dir"
        exit 1
      fi
      local_workflows_dir="$2"
      shift 2
      ;;
    --local-models-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --local-models-dir"
        exit 1
      fi
      local_models_dir="$2"
      shift 2
      ;;
    --api-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --api-ref"
        exit 1
      fi
      api_ref="$2"
      build_api_image="true"
      use_workflow_dispatch=1
      shift 2
      ;;
    --workflows-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --workflows-ref"
        exit 1
      fi
      workflows_ref="$2"
      build_workflows_image="true"
      use_workflow_dispatch=1
      shift 2
      ;;
    --models-ref)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --models-ref"
        exit 1
      fi
      models_ref="$2"
      use_workflow_dispatch=1
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      act_extra_args+=("$1")
      shift
      ;;
  esac
done

if [[ "$local_sources_mode" == "1" ]]; then
  local_api_mode=1
  local_workflows_mode=1
  local_models_mode=1
fi

if [[ "$local_api_mode" == "1" || "$local_workflows_mode" == "1" || "$local_models_mode" == "1" ]]; then
  if [[ "$local_api_mode" == "1" && -n "$api_ref" ]]; then
    echo "Cannot combine --local-api/--local-sources with --api-ref."
    exit 1
  fi
  if [[ "$local_workflows_mode" == "1" && -n "$workflows_ref" ]]; then
    echo "Cannot combine --local-workflows/--local-sources with --workflows-ref."
    exit 1
  fi
  if [[ "$local_models_mode" == "1" && -n "$models_ref" ]]; then
    echo "Cannot combine --local-models/--local-sources with --models-ref."
    exit 1
  fi

  if [[ "$local_api_mode" == "1" && ! -d "$local_api_dir" ]]; then
    echo "Local API directory not found: $local_api_dir"
    exit 1
  fi
  if [[ "$local_workflows_mode" == "1" && ! -d "$local_workflows_dir" ]]; then
    echo "Local Workflows directory not found: $local_workflows_dir"
    exit 1
  fi
  if [[ "$local_models_mode" == "1" && ! -d "$local_models_dir" ]]; then
    echo "Local Models directory not found: $local_models_dir"
    exit 1
  fi

  cmd=(
    ./scripts/integration-tests.sh
  )

  if [[ ${#act_extra_args[@]} -gt 0 ]]; then
    cmd+=("${act_extra_args[@]}")
  fi

  if [[ "$local_api_mode" == "1" || "$local_workflows_mode" == "1" ]]; then
    env_args=(
      "BUILD_LOCAL_DEV_IMAGES=1"
    )
  else
    env_args=(
      "BUILD_LOCAL_DEV_IMAGES=0"
    )
  fi
  env_args+=(
    "BUILD_LOCAL_BC_API_IMAGE=$local_api_mode"
    "BUILD_LOCAL_WORKFLOWS_IMAGE=$local_workflows_mode"
    "COMPOSE_PROJECT_NAME=$compose_project_name"
  )

  if [[ "$local_api_mode" == "1" ]]; then
    local_api_ref="$(detect_repo_ref "$local_api_dir")"
    local_api_tag="$(sanitize_tag_component "$local_api_ref")"
    env_args+=(
      "LOCAL_BLUECORE_API_DIR=$local_api_dir"
      "BLUECORE_API_IMAGE=bluecore_api:${local_api_tag}-local"
    )
  fi

  if [[ "$local_workflows_mode" == "1" ]]; then
    local_workflows_ref="$(detect_repo_ref "$local_workflows_dir")"
    local_workflows_tag="$(sanitize_tag_component "$local_workflows_ref")"
    env_args+=(
      "LOCAL_BLUECORE_WORKFLOWS_DIR=$local_workflows_dir"
      "BLUECORE_WORKFLOWS_IMAGE=bluecore_workflows:${local_workflows_tag}-local"
    )
  fi

  if [[ "$local_models_mode" == "1" ]]; then
    local_models_ref="$(detect_repo_ref "$local_models_dir")"
    env_args+=(
      "MODELS_DIR=$local_models_dir"
      "MODELS_SOURCE_LABEL=bluecore-models@$local_models_ref"
    )
  fi

  env_args+=(
    "INTEGRATION_FULL_STACK=1"
    "COMPOSE_PROFILES=integration-full"
    "INTEGRATION_BASE_URL=http://localhost/api"
    "INTEGRATION_AIRFLOW_BASE_URL=http://localhost"
    "INTEGRATION_KEYCLOAK_TOKEN_URL=http://localhost/keycloak/realms/bluecore/protocol/openid-connect/token"
    "INTEGRATION_REQUIRE_VECTOR_BACKEND=1"
  )

  printf 'Running (local sources): '
  printf '%q ' env "${env_args[@]}" "${cmd[@]}"
  echo
  echo "Compose project name: $compose_project_name"
  cleanup_stale_act_manual_integration_containers

  env "${env_args[@]}" "${cmd[@]}"
  exit $?
fi

if [[ "$use_workflow_dispatch" == "1" ]]; then
  event_name="workflow_dispatch"
fi

if ! command -v act >/dev/null 2>&1; then
  echo "act is not installed. Install it first: https://github.com/nektos/act"
  exit 1
fi

if [[ ! -f "$secret_file" ]]; then
  echo "Missing secret file: $secret_file"
  echo "Create it in terraform/ with at least:"
  echo "  GITHUB_TOKEN=<Github Token>"
  echo "  BLUECORE_REPO_READ_TOKEN=<Github Token>"
  echo "  Create token at: https://github.com/settings/tokens"
  exit 1
fi

cmd=(
  act "$event_name"
  -j "$job_name"
  -b
  --container-architecture "$container_arch"
  -P "ubuntu-latest=$ubuntu_image"
  --secret-file "$secret_file"
)
cmd+=(--env "COMPOSE_PROJECT_NAME=$compose_project_name")
if [[ "$act_rm_on_failure" == "1" ]]; then
  cmd+=(--rm)
fi

if [[ "$use_workflow_dispatch" == "1" ]]; then
  cmd+=(--input "full_stack_profile=true")

  cmd+=(--input "build_api_image=$build_api_image")
  cmd+=(--input "build_workflows_image=$build_workflows_image")
  cmd+=(--input "compose_project_name=$compose_project_name")

  if [[ -n "$api_ref" ]]; then
    cmd+=(--input "api_ref=$api_ref")
  fi

  if [[ -n "$workflows_ref" ]]; then
    cmd+=(--input "workflows_ref=$workflows_ref")
  fi

  if [[ -n "$models_ref" ]]; then
    cmd+=(--input "models_ref=$models_ref")
  fi
else
  cmd+=(
    --env "INTEGRATION_FULL_STACK=1"
    --env "COMPOSE_PROFILES=integration-full"
    --env "INTEGRATION_BASE_URL=http://localhost/api"
    --env "INTEGRATION_AIRFLOW_BASE_URL=http://localhost"
    --env "INTEGRATION_KEYCLOAK_TOKEN_URL=http://localhost/keycloak/realms/bluecore/protocol/openid-connect/token"
    --env "INTEGRATION_REQUIRE_VECTOR_BACKEND=1"
  )
fi

if [[ ${#act_extra_args[@]} -gt 0 ]]; then
  cmd+=("${act_extra_args[@]}")
fi

printf 'Running: '
printf '%q ' "${cmd[@]}"
echo
echo "Compose project name: $compose_project_name"
cleanup_stale_act_manual_integration_containers

"${cmd[@]}"
