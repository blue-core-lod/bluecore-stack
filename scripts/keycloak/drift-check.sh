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

# ---------------------------------------------------------------------------
# Mirror the target environment's server-level KC_* settings onto the
# throwaway verify-keycloak. Two differently-configured Keycloak SERVERS
# derive different realm-level defaults (e.g. browserSecurityHeaders) from
# identical declarative config, so without this the diff below manufactures
# drift that is a server-config difference, not a realm-config one.
#
# Reading these off the live container is more faithful than trusting .env:
# .env is what compose-dev.yaml/compose.yaml are TOLD to run with, but the
# container's own Config.Env is what is actually running. .env (already
# sourced above) is kept only as a fallback for a target container that does
# not exist yet (a truly fresh environment, nothing to inspect).
KC_SERVER_VARS="KC_PROXY KC_PROXY_HEADERS KC_HTTP_RELATIVE_PATH KC_HOSTNAME KC_HOSTNAME_STRICT KC_HTTP_ENABLED"
if [[ -n "$KC_CID" ]]; then
  LIVE_KC_ENV="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$KC_CID" 2>/dev/null || true)"
  for kc_var in $KC_SERVER_VARS; do
    kc_val="$(printf '%s\n' "$LIVE_KC_ENV" | sed -n "s/^${kc_var}=//p" | tail -1)"
    if [[ -n "$kc_val" ]]; then
      export "$kc_var=$kc_val"
    fi
  done
fi

# Only the keys that actually have a value (live container, or .env as
# fallback) go into the override, so any key neither source provides is left
# out entirely -- verify-keycloak then falls back to its own upstream
# default for it, exactly as it does today when this override is absent (as
# it is for verify-realm.sh).
SERVER_CONFIG_OVERRIDE="$ROOT_DIR/$WORK/verify-server-config.yaml"
python3 - "$SERVER_CONFIG_OVERRIDE" $KC_SERVER_VARS <<'PY'
import json, os, sys

out = sys.argv[1]
keys = sys.argv[2:]
env = {k: os.environ[k] for k in keys if os.environ.get(k)}
doc = {"services": {"verify-keycloak": {"environment": env}}}
with open(out, "w") as f:
    json.dump(doc, f)
PY
VERIFY_COMPOSE_EXTRA="$SERVER_CONFIG_OVERRIDE"
info "Mirroring target server config on the throwaway Keycloak ($(basename "$SERVER_CONFIG_OVERRIDE"))"

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
# immediately after keycloak-config on every boot; this second apply is not
# optional to reproduce here. Reapplying a realm-scoped import resets any
# realm attribute the first apply's file doesn't declare (e.g.
# browserSecurityHeaders) to config-cli's own default, regardless of what the
# first apply alone left there -- so a throwaway that only ever runs the
# first apply is not comparable to a real development realm, independent of
# server config. staging/production have no keycloak-config-users
# equivalent (compose.yaml never runs it), so skip this there.
if [[ "$ENVIRONMENT" == "development" ]]; then
  apply_dev_users || { echo "dev-users config-cli apply failed" >&2; exit 1; }
fi

export_and_normalize "$WORK/expected"
assert_defaults_present "$VERIFY_WORK/export/bluecore-realm.json"

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
