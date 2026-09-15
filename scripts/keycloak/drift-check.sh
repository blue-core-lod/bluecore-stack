#!/bin/bash
# Read-only drift check: compares the live bluecore realm in a target
# environment against keycloak/realm/, through the exact same pipeline
# scripts/keycloak/verify-realm.sh uses to prove equivalence against the
# committed pre-migration fixture (shared machinery lives in
# scripts/keycloak/lib.sh, sourced by both -- two independent comparison
# implementations would let this check and that one silently disagree about
# what counts as drift).
#
# Both sides go through prune_and_normalize -> normalize -> strip_intended:
#
#   baseline = the live realm, exported read-only from the target
#              environment's own Keycloak.
#   expected = keycloak/realm/ applied to a throwaway Keycloak
#              (compose-keycloak-verify.yaml), using the target
#              environment's own $(env:...) variable values, then exported.
#
# Rendering "expected" with the target's real KEYCLOAK_PUBLIC_BASE_URL /
# KEYCLOAK_SSL_REQUIRED matters: those values show up verbatim in redirect
# URIs and sslRequired, so using the wrong ones would manufacture drift that
# isn't there. AIRFLOW_KEYCLOAK_CLIENT_SECRET does NOT need to match --
# strip_intended's canonicalizer drops the client secret on both sides
# unconditionally, so a per-environment secret can never register as drift.
#
# This check is READ-ONLY with respect to the target environment: it never
# writes to, imports into, or mutates the live realm. It stops the target's
# keycloak container only long enough to take the read-only export above,
# and restores it to whatever running state it was in before, even on error
# (see the EXIT trap).
#
#   ./scripts/keycloak/drift-check.sh                    # development
#   ./scripts/keycloak/drift-check.sh --env=staging
#   ./scripts/keycloak/drift-check.sh --env=production
#
# Exits 0 when the live realm matches the repo, 1 when it has drifted.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=./lib.sh
source "$ROOT_DIR/scripts/keycloak/lib.sh"

ENVIRONMENT="${ENV:-development}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env=*) ENVIRONMENT="${1#*=}"; shift ;;
    -h|--help)
      echo "usage: $0 [--env=development|staging|production]" >&2
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$ENVIRONMENT" in
  development) COMPOSE_FILE="compose-dev.yaml" ;;
  staging|production) COMPOSE_FILE="compose.yaml" ;;
  *) echo "Unknown environment: $ENVIRONMENT" >&2; exit 2 ;;
esac

# KEYCLOAK_SSL_REQUIRED, KEYCLOAK_PUBLIC_BASE_URL and AIRFLOW_KEYCLOAK_CLIENT_SECRET
# are read by apply_config (see lib.sh) to render the same $(env:...)
# substitutions the target environment's own keycloak-config service
# renders. .env is the file every compose file here already consumes via
# env_file for exactly these variables, so source it rather than
# re-deriving values that must, by construction, already agree with it.
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

WORK="tmp/kc-drift/${ENVIRONMENT}"
rm -rf "$WORK"
mkdir -p "$WORK/export" "$WORK/baseline" "$WORK/expected"

# ---------------------------------------------------------------------------
# Read-only export of the live realm, then tear down / restore the throwaway
# verify stack no matter how this script exits.
# ---------------------------------------------------------------------------
LIVE_KEYCLOAK_WAS_RUNNING=""
LIVE_KEYCLOAK_RESTORED="0"

restore_live_keycloak() {
  if [[ "$LIVE_KEYCLOAK_WAS_RUNNING" == "1" && "$LIVE_KEYCLOAK_RESTORED" == "0" ]]; then
    info "Restoring '${ENVIRONMENT}' keycloak to its running state"
    docker compose -f "$COMPOSE_FILE" start keycloak >/dev/null 2>&1 || true
    LIVE_KEYCLOAK_RESTORED="1"
  fi
}

cleanup() {
  compose down --volumes >/dev/null 2>&1 || true
  restore_live_keycloak
}
trap cleanup EXIT

info "Exporting live '${ENVIRONMENT}' realm (read-only)"

KC_CID="$(docker compose -f "$COMPOSE_FILE" ps -q keycloak 2>/dev/null || true)"
if [[ -n "$KC_CID" ]] \
    && [[ "$(docker inspect -f '{{.State.Running}}' "$KC_CID" 2>/dev/null)" == "true" ]]; then
  LIVE_KEYCLOAK_WAS_RUNNING="1"
fi

docker compose -f "$COMPOSE_FILE" stop keycloak

# Task 6 removed compose-dev.yaml's KEYCLOAK_REALM_DIR volume from the
# keycloak service entirely, so relying on it here would write the export
# inside the throwaway `run` container and lose it. Bind-mount the export
# directory explicitly instead of relying on any volume the target
# environment's own compose file may or may not declare for this service --
# compose.yaml (staging/production) still mounts KEYCLOAK_REALM_DIR at this
# same in-container path for its own --import-realm use, so a container path
# that nothing else claims (/tmp/kc-drift-export) avoids colliding with it.
docker compose -f "$COMPOSE_FILE" run --user root --rm \
  -v "$ROOT_DIR/$WORK/export:/tmp/kc-drift-export" \
  keycloak export --dir=/tmp/kc-drift-export --realm=bluecore --users=realm_file

restore_live_keycloak

prune_and_normalize "$WORK/export/bluecore-realm.json" "$WORK/baseline"

# ---------------------------------------------------------------------------
# keycloak/realm/ applied to a throwaway Keycloak, rendered with this
# environment's own variable values.
# ---------------------------------------------------------------------------
info "Applying keycloak/realm/ to a throwaway Keycloak with '${ENVIRONMENT}' values"
reset_stack
apply_config || { echo "config-cli apply failed" >&2; exit 1; }

# development's real stack runs keycloak-config-users (compose-dev.yaml)
# immediately after keycloak-config on every boot, so it is tempting to
# reproduce that second apply here "for parity". It is not needed: a
# one-apply throwaway and a real two-apply development realm produce
# byte-identical canonical state, verified by diffing export_and_normalize
# output with and without a following apply_dev_users -- zero diff.
#
# It WAS added here once, to silence a `browserSecurityHeaders: {}` diff.
# That diagnosis was wrong on two counts: the realm's headers were never
# actually emptied (Keycloak refuses to clear that map), and the `{}` came
# from normalize's handling of the field rather than realm state. The call
# is removed because it was compensating for a misread, not because the
# sequencing question was settled -- if a genuine one-apply/two-apply
# difference ever appears, reproducing the second apply here is the right
# answer, but prove the difference first rather than assuming it.
export_and_normalize "$WORK/expected"
assert_defaults_present "$VERIFY_WORK/export/bluecore-realm.json"
assert_browser_security_headers "$VERIFY_WORK/export/bluecore-realm.json"

# ---------------------------------------------------------------------------
# Diff the two canonical forms.
# ---------------------------------------------------------------------------
strip_intended "$WORK/baseline"/*.yaml > "$WORK/baseline.canonical.json"
strip_intended "$WORK/expected"/*.yaml > "$WORK/expected.canonical.json"

if diff -u "$WORK/baseline.canonical.json" "$WORK/expected.canonical.json" > "$WORK/drift.diff"; then
  echo "No drift: live '${ENVIRONMENT}' realm matches the repo."
  exit 0
fi

echo "DRIFT DETECTED in '${ENVIRONMENT}':"
cat "$WORK/drift.diff"
echo
echo "The repo is the source of truth. Either revert the console change, or"
echo "reproduce it in keycloak/realm/bluecore.yaml via a pull request."
exit 1
