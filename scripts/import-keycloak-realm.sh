#!/bin/bash

# ==============================================================================
# Imports the Keycloak realm configuration for the bluecore realm
# Chooses development, staging, or production behavior via ENV var or --env flag
# (defaults to development).
#
# Counterpart to export-keycloak-realm.sh. Keycloak only auto-imports a realm on
# startup when it does NOT already exist, so an updated realm JSON is ignored by
# an environment whose `bluecore` realm is already in the database. This script
# forces the update by running Keycloak's offline `import --override true`, which
# overwrites the existing realm from the JSON without dropping the database.
#
#   ./scripts/import-keycloak-realm.sh                 # development (compose-dev.yaml)
#   ./scripts/import-keycloak-realm.sh --env=staging   # staging     (compose.yaml)
#   ./scripts/import-keycloak-realm.sh --env=production # production  (compose.yaml)
#
# ⚠️  --override true replaces the `bluecore` realm with exactly what is in the
#     JSON. Users created live after the last export are NOT in the file and can
#     be removed. If the target realm has real end-users you can't lose, use the
#     admin console's Partial Import instead. Other realms (e.g. master) are
#     untouched.
# ------------------------------------------------------------------------------

# Color codes
GREEN='\033[0;32m'
BLUE='\033[1;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT="${ENV:-development}"

# Check for CLI override
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env=*)
      ENVIRONMENT="${1#*=}"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Common logging
echo -e "${BLUE}===========================================================${NC}"
echo -e "${BLUE}🔄 Starting import of 'bluecore' Keycloak realm...${NC}"

# Each environment imports from its own folder under keycloak-export/:
#   development -> compose-dev.yaml, committed   keycloak-export/development/
#   staging     -> compose.yaml,     git-ignored keycloak-export/staging/
#   production  -> compose.yaml,     git-ignored keycloak-export/production/
case "$ENVIRONMENT" in
  development)
    COMPOSE_FILE="compose-dev.yaml"
    ;;
  staging|production)
    COMPOSE_FILE="compose.yaml"
    ;;
  *)
    echo -e "${RED}❌ Unknown environment: '${ENVIRONMENT}'. Use development, staging, or production.${NC}"
    exit 1
    ;;
esac

IMPORT_DIR="keycloak-export/${ENVIRONMENT}"
REALM_FILE="${IMPORT_DIR}/bluecore-realm.json"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Source path: ${REALM_FILE}${NC}"

# The realm JSON must already exist for this environment.
if [ ! -f "${REALM_FILE}" ]; then
  echo -e "${RED}❌ Realm file not found: ${REALM_FILE}${NC}"
  echo -e "${RED}   Seed it first (see docs/updating-keycloak-credentials.md) or run the export script.${NC}"
  exit 1
fi

# Stop the running Keycloak so the one-off import container isn't fighting it for
# the database lock, then start it again once the import finishes.
echo -e "${BLUE}Stopping Keycloak before import...${NC}"
docker compose -f "${COMPOSE_FILE}" stop keycloak

# Force the update: --override true overwrites the existing realm from the JSON
# mounted at /opt/keycloak/data/import via KEYCLOAK_REALM_DIR.
KEYCLOAK_REALM_DIR="./${IMPORT_DIR}" \
  docker compose -f "${COMPOSE_FILE}" run --rm \
  keycloak import --dir=/opt/keycloak/data/import --override true
IMPORT_STATUS=$?

# Bring Keycloak back up regardless of import outcome.
echo -e "${BLUE}Starting Keycloak...${NC}"
docker compose -f "${COMPOSE_FILE}" start keycloak

# Check result
if [ ${IMPORT_STATUS} -eq 0 ]; then
  echo -e "${GREEN}===========================================================${NC}"
  echo -e "${GREEN}✅ Import completed successfully.${NC}"
  echo -e "${GREEN}===========================================================${NC}"
else
  echo -e "${RED}===========================================================${NC}"
  echo -e "${RED}❌ Import failed. Check logs above for details.${NC}"
  echo -e "${RED}===========================================================${NC}"
  exit ${IMPORT_STATUS}
fi
