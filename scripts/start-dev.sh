#!/usr/bin/env bash
set -euo pipefail
################################################################################
## Bring up the dev stack. Default: build every Blue Core service from the LOCAL
## repo checkouts below, with live-reload source mounts.
## Pass --image to run the GHCR-published images instead.
##
##   ./scripts/start-dev.sh            # local build + up
##   ./scripts/start-dev.sh --image    # GHCR images: pull + up
################################################################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ==============================================================================
# ################  SET YOUR LOCAL REPO PATHS HERE  ############################
# ==============================================================================
export LOCAL_BLUECORE_API_DIR="$ROOT_DIR/../bluecore_api"
export LOCAL_BLUECORE_WORKFLOWS_DIR="$ROOT_DIR/../bluecore-workflows"
export LOCAL_MARVA_DIR="$ROOT_DIR/../marva_editor"
export LOCAL_SINOPIA_DIR="$ROOT_DIR/../sinopia_editor"
export AIRFLOW_UID=50000

#######################################
## RUN with released Github images:  ##
## "./script/start-dev.sh --image"   ##
## --------------------------------- ##
## RUN with local mounted code:      ##
## "./script/start-dev.sh"           ##
#######################################
if [[ "${1:-}" == "--image" ]]; then
  echo "🐳 Image mode: GHCR images via compose-dev.yaml"
  docker compose -f compose-dev.yaml pull
  docker compose -f compose-dev.yaml up
else
  echo "🏗️  Local mode: building from local checkouts via compose-local-dev.yaml"
  docker compose -f compose-local-dev.yaml up --build
fi
