#!/bin/bash

# ==============================================================================
# Exports the Keycloak realm configuration for the bluecore realm
# Chooses development, staging, or production behavior via ENV var or --env flag
# (defaults to development).
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
echo -e "${BLUE}🔄 Starting export of 'bluecore' Keycloak realm...${NC}"

# Each environment exports to its own folder under keycloak-export/:
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

EXPORT_DIR="keycloak-export/${ENVIRONMENT}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Target path: ${EXPORT_DIR}/bluecore-realm.json${NC}"

# Ensure the env folder exists, then tell compose which dir to mount for the
# import/export volume via KEYCLOAK_REALM_DIR.
mkdir -p "${EXPORT_DIR}"

KEYCLOAK_REALM_DIR="./${EXPORT_DIR}" \
  docker compose -f "${COMPOSE_FILE}" run --user root --rm \
  keycloak export --dir=/opt/keycloak/data/export --realm=bluecore --users=realm_file

# Check result
if [ $? -eq 0 ]; then
  echo -e "${GREEN}===========================================================${NC}"
  echo -e "${GREEN}✅ Export completed successfully.${NC}"
  echo -e "${GREEN}===========================================================${NC}"
else
  echo -e "${RED}===========================================================${NC}"
  echo -e "${RED}❌ Export failed. Check logs above for details.${NC}"
  echo -e "${RED}===========================================================${NC}"
fi
