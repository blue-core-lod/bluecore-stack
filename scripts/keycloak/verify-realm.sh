#!/bin/bash
# Verify the declarative bluecore realm config against a throwaway Keycloak.
#
#   ./scripts/keycloak/verify-realm.sh [equivalence|convergence|user-safety|all]
#
# equivalence  - applying keycloak/realm/ reproduces the committed export
# convergence  - applying twice is idempotent (proves safe re-apply)
# user-safety  - a user absent from the config survives an apply
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

VERIFY_COMPOSE="compose-keycloak-verify.yaml"
CONFIG_CLI_IMAGE="${KEYCLOAK_CONFIG_CLI_IMAGE:-adorsys/keycloak-config-cli:6.5.1-26.1.0}"
WORK="tmp/kc-verify"
COMMITTED_EXPORT="keycloak-export/development/bluecore-realm.json"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[1;34m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; exit 1; }
info() { echo -e "${BLUE}==>${NC} $1"; }

compose() { docker compose -f "$VERIFY_COMPOSE" "$@"; }

reset_stack() {
  info "Resetting throwaway Keycloak"
  compose down --volumes >/dev/null 2>&1 || true
  rm -rf "$WORK/export" "$WORK/candidate" "$WORK/second"
  mkdir -p "$WORK"
  compose up -d --wait
}

kcadm() {
  compose exec -T verify-keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

kcadm_login() {
  kcadm config credentials --server http://localhost:8080 \
    --realm master --user admin --password admin >/dev/null
}

# Apply keycloak/realm/ to the throwaway Keycloak. Echoes config-cli output.
apply_config() {
  local extra_files="${1:-}"
  local locations="/config/bluecore.yaml"
  if [[ -n "$extra_files" ]]; then
    locations="$locations,$extra_files"
  fi

  docker run --rm \
    --network bluecore-kc-verify_default \
    -v "$ROOT_DIR/keycloak/realm:/config:ro" \
    -e KEYCLOAK_URL=http://verify-keycloak:8080 \
    -e KEYCLOAK_USER=admin \
    -e KEYCLOAK_PASSWORD=admin \
    -e KEYCLOAK_AVAILABILITYCHECK_ENABLED=true \
    -e KEYCLOAK_AVAILABILITYCHECK_TIMEOUT=120s \
    -e IMPORT_VAR_SUBSTITUTION_ENABLED=true \
    -e IMPORT_FILES_LOCATIONS="$locations" \
    -e KEYCLOAK_SSL_REQUIRED=external \
    -e KEYCLOAK_PUBLIC_BASE_URL=http://localhost \
    -e AIRFLOW_KEYCLOAK_CLIENT_SECRET=verify-only-secret \
    "$CONFIG_CLI_IMAGE"
}

# Export the live bluecore realm from the throwaway Keycloak, then normalize it.
export_and_normalize() {
  local outdir="$1"
  mkdir -p "$WORK/export" "$outdir"

  compose stop verify-keycloak >/dev/null
  compose run --rm --user root verify-keycloak \
    export --dir=/data/export --realm=bluecore --users=realm_file >/dev/null
  compose start verify-keycloak >/dev/null
  compose up -d --wait >/dev/null

  ./scripts/keycloak/normalize.sh "$WORK/export/bluecore-realm.json" "$outdir" >/dev/null
}

check_equivalence() {
  info "Equivalence: does keycloak/realm/ reproduce the committed export?"
  [[ -f keycloak/realm/bluecore.yaml ]] || fail "keycloak/realm/bluecore.yaml does not exist"

  mkdir -p "$WORK/baseline"
  ./scripts/keycloak/normalize.sh "$COMMITTED_EXPORT" "$WORK/baseline" >/dev/null

  reset_stack
  apply_config || fail "config-cli apply failed"
  export_and_normalize "$WORK/candidate"

  if diff -u "$WORK/baseline"/*.yaml "$WORK/candidate"/*.yaml > "$WORK/equivalence.diff"; then
    pass "candidate realm is identical to the normalized committed export"
  else
    echo "--- differences (see $WORK/equivalence.diff) ---"
    cat "$WORK/equivalence.diff"
    fail "candidate realm differs from the committed export; classify each entry as intended or a gap"
  fi
}

check_convergence() {
  info "Convergence: is a second apply idempotent?"
  reset_stack
  apply_config || fail "first apply failed"
  export_and_normalize "$WORK/candidate"
  apply_config || fail "second apply failed"
  export_and_normalize "$WORK/second"

  if diff -u "$WORK/candidate"/*.yaml "$WORK/second"/*.yaml > "$WORK/convergence.diff"; then
    pass "second apply changed nothing"
  else
    cat "$WORK/convergence.diff"
    fail "second apply mutated the realm; config is not idempotent"
  fi
}

check_user_safety() {
  info "User safety: does an undeclared user survive an apply?"
  reset_stack
  apply_config || fail "initial apply failed"

  kcadm_login
  kcadm create users -r bluecore -s username=drift_probe -s enabled=true >/dev/null
  kcadm get users -r bluecore -q username=drift_probe --fields username \
    | grep -q drift_probe || fail "could not create probe user"

  apply_config || fail "re-apply failed"

  if kcadm get users -r bluecore -q username=drift_probe --fields username \
      | grep -q drift_probe; then
    pass "undeclared user drift_probe survived the apply"
  else
    fail "undeclared user was deleted — upsert-only behaviour has regressed"
  fi
}

case "${1:-all}" in
  equivalence) check_equivalence ;;
  convergence) check_convergence ;;
  user-safety) check_user_safety ;;
  all) check_equivalence; check_convergence; check_user_safety ;;
  *) echo "usage: $0 [equivalence|convergence|user-safety|all]" >&2; exit 2 ;;
esac

info "Cleaning up"
compose down --volumes >/dev/null 2>&1 || true
