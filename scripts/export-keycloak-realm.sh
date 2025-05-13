#!/bin/bash

# ==============================================================================
# Exports the Keycloak realm configuration for the bluecore realm
# Chooses dev or prod behavior based on ENV variable or --env flag
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

# Choose command based on environment
if [[ "$ENVIRONMENT" == "production" ]]; then
  echo -e "${BLUE}Target path: /home/ubuntu/keycloak-export/bluecore-realm.json${NC}"
  echo -e "${BLUE}Environment: production${NC}"

  docker compose -f compose.yaml run --rm \
    -v /home/ubuntu/keycloak-export:/opt/keycloak/data/export \
    keycloak export --dir=/opt/keycloak/data/export --realm=bluecore --users=realm_file

else
  echo -e "${BLUE}Target path: keycloak-export/bluecore-realm.json${NC}"
  echo -e "${BLUE}Environment: development${NC}"

  docker compose -f compose-dev.yaml run --rm keycloak \
    export --dir=/opt/keycloak/data/export --realm=bluecore --users=realm_file
fi

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
