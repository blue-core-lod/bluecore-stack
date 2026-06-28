#!/usr/bin/env bash
set -euo pipefail
################################################################################
## Bring up the dev stack. Default: build every Blue Core service from the LOCAL
## repo checkouts below, with live-reload source mounts.
##
##   ./scripts/start-dev.sh                 # full local stack (everything)
##   ./scripts/start-dev.sh --image         # GHCR-published images instead
##
## Run a SUBSET (local mode only). postgres, keycloak, nginx and the bluecore
## API (which runs DB migrations on start) are ALWAYS up; pick what else runs:
##
##   ./scripts/start-dev.sh --api           # core + API only (no airflow)
##   ./scripts/start-dev.sh --marva         # core + Marva (+ middleware)
##   ./scripts/start-dev.sh --sinopia       # core + Sinopia
##   ./scripts/start-dev.sh --airflow       # core + Airflow (+ Milvus)
##   ./scripts/start-dev.sh --marva --sinopia   # combine as needed
##
## No subset flag = everything. Subset flags are ignored in --image mode.
## bluecore-models is mounted into the local API and Airflow services automatically.
################################################################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ==============================================================================
# ################  LOAD LOCAL REPO PATHS  #####################################
# ==============================================================================
. "$ROOT_DIR/scripts/local-repo-paths.sh"
export AIRFLOW_UID=50000

mode="local"
selected=0          # 1 once any subset flag is seen (so no flag = everything)
profiles=()
for arg in "$@"; do
  case "$arg" in
    --image)   mode="image" ;;
    --api)     selected=1 ;;                                  # core only
    --marva)   selected=1; profiles+=("marva") ;;
    --sinopia) selected=1; profiles+=("sinopia") ;;
    --airflow) selected=1; profiles+=("airflow" "milvus") ;;  # workers need Milvus
    --milvus)  selected=1; profiles+=("milvus") ;;
    -h|--help) sed -n '3,21p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if [[ "$mode" == "image" ]]; then
  echo "🐳 Image mode: GHCR images via compose-dev.yaml (full stack)"
  docker compose -f compose-dev.yaml pull
  docker compose -f compose-dev.yaml up
  exit $?
fi

# Local mode: select profiles. No subset flag => run everything.
if [[ "$selected" == "0" ]]; then
  export COMPOSE_PROFILES="airflow,milvus,sinopia,marva"
else
  export COMPOSE_PROFILES="$(IFS=,; echo "${profiles[*]:-}")"
fi

echo "🏗️  Local mode (compose-local-dev.yaml)"
echo "   always: postgres, keycloak, nginx, bc_api"
echo "   profiles: ${COMPOSE_PROFILES:-<none — core only>}"
docker compose -f compose-local-dev.yaml up --build
