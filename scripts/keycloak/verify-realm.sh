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
# Only used to turn normalized YAML into JSON so python3's stdlib can canonicalize
# it; the host is not assumed to have PyYAML.
YQ_IMAGE="${YQ_IMAGE:-mikefarah/yq:4.44.3}"
WORK="tmp/kc-verify"
COMMITTED_EXPORT="keycloak-export/development/bluecore-realm.json"

# Entities Keycloak creates by itself on every realm. keycloak/realm/bluecore.yaml
# deliberately declares none of them. Their *contents* are excluded from the
# equivalence comparison (see strip_intended) and their *existence* is asserted
# separately (see assert_defaults_present).
export DEFAULT_CLIENTS="account account-console admin-cli broker realm-management security-admin-console"
export DEFAULT_CLIENT_SCOPES="acr address basic email microprofile-jwt offline_access organization phone profile role_list roles saml_organization service_account web-origins"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[1;34m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; exit 1; }
info() { echo -e "${BLUE}==>${NC} $1"; }

compose() { docker compose -f "$VERIFY_COMPOSE" "$@"; }

trap 'compose down --volumes >/dev/null 2>&1 || true' EXIT

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
#
# IMPORT_MANAGED_* are deliberately left at their upstream defaults (`full`).
# keycloak/realm/bluecore.yaml declares only bluecore_api and bluecore_workflows
# and none of the default client scopes, so `full` raises the obvious worry that
# config-cli would read "not declared" as "delete". It does not: config-cli
# protects Keycloak's own default clients and client scopes. assert_defaults_present
# below is what keeps that honest, so do not weaken it to no-delete without
# first making that check fail.
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
  rm -rf "$WORK/export"
  mkdir -p "$WORK/export" "$outdir"

  compose stop verify-keycloak >/dev/null
  compose run --rm --user root verify-keycloak \
    export --dir=/data/export --realm=bluecore --users=realm_file >/dev/null
  compose start verify-keycloak >/dev/null
  compose up -d --wait >/dev/null

  ./scripts/keycloak/normalize.sh "$WORK/export/bluecore-realm.json" "$outdir" >/dev/null
}

# Reduce a normalized realm YAML to a canonical JSON form so that the only
# differences left are ones that actually matter. Every rule here is an
# *intended* difference, justified below; nothing is dropped just to silence a
# diff. Keep this list short and keep the justifications honest -- a lenient
# filter here is a verification that proves nothing.
#
# Dropped:
#   id, containerId - Keycloak-generated UUIDs (the realm's own id and the
#     realm/client id each role hangs off). A fresh realm always gets new ones,
#     so they can never match, and committing them would make the config
#     unusable against any other realm.
#   secret, attributes."client.secret.creation.time" - the secret is injected by
#     this script (verify-only-secret) and the creation time is an export
#     timestamp; both are deliberately absent from the committed config.
#   attributes."de.adorsys.keycloak.config.*" - config-cli's own bookkeeping
#     (import checksum and its record of which entities it manages). Present
#     only because config-cli did the import; not realm configuration.
#   components - normalize ignores this section; it holds only Keycloak defaults
#     and per-realm generated keys, which must never be committed.
#
# Canonicalized rather than dropped (content is still compared, only the
# representation is normalized):
#   map key order and list order - Keycloak serializes these from unordered
#     sets, so the same realm exports in different orders run to run. Ordered
#     collections in a realm export (authentication executions, required
#     actions) carry an explicit `priority` field, which is compared.
#   JSON-array-valued strings inside authorization policy `config` blocks
#     (roles/scopes/resources/applyPolicies) - these are sets encoded as JSON
#     text, and Keycloak emits them in arbitrary order.
#
# Also dropped: the six default clients and the 14 default client scopes
# ($DEFAULT_CLIENTS / $DEFAULT_CLIENT_SCOPES). Keycloak owns these and this
# config does not declare them, but the long-lived realm's copies are not
# byte-identical to the ones a 26.1.2 realm creates today: the old realm carries
# attributes."post.logout.redirect.uris"="+" on admin-cli/broker/realm-management
# and config."userinfo.token.claim"="true" on seven default scope mappers, both of
# which newer Keycloak simply omits (the omitted value is the effective default).
# Those are Keycloak version artifacts, not configuration -- pinning them would
# mean declaring Keycloak's defaults, which is what this migration exists to stop.
# Dropping their contents would hide them being *deleted*, so
# assert_defaults_present checks their existence against the raw export instead.
read -r -d '' CANONICALIZE_PY <<'PY' || true
import json, os, sys

DEFAULT_CLIENTS = set(os.environ["DEFAULT_CLIENTS"].split())
DEFAULT_CLIENT_SCOPES = set(os.environ["DEFAULT_CLIENT_SCOPES"].split())
DROP_KEYS = {"id", "containerId", "secret", "components"}
DROP_ATTRS = {"client.secret.creation.time"}
DROP_ATTR_PREFIX = "de.adorsys.keycloak.config."


def sort_key(value):
    if isinstance(value, dict):
        for field in ("name", "clientId", "alias", "username"):
            if isinstance(value.get(field), str):
                return (0, value[field], json.dumps(value, sort_keys=True))
        return (1, "", json.dumps(value, sort_keys=True))
    return (2, "", json.dumps(value, sort_keys=True))


def clean(node, parent_key=None):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in DROP_KEYS:
                continue
            if parent_key == "attributes" and (
                key in DROP_ATTRS or key.startswith(DROP_ATTR_PREFIX)
            ):
                continue
            cleaned = clean(value, key)
            # Filtering out the default clients/client scopes can empty these
            # lists entirely; normalize omits the key altogether when it has
            # nothing to say, so treat empty-after-filtering as absent.
            if key in ("clients", "clientScopes") and cleaned == []:
                continue
            out[key] = cleaned
        return out
    if isinstance(node, list):
        items = node
        if parent_key == "clients":
            items = [
                c for c in items
                if not (isinstance(c, dict) and c.get("clientId") in DEFAULT_CLIENTS)
            ]
        elif parent_key == "clientScopes":
            items = [
                s for s in items
                if not (isinstance(s, dict) and s.get("name") in DEFAULT_CLIENT_SCOPES)
            ]
        return sorted((clean(item, parent_key) for item in items), key=sort_key)
    if isinstance(node, str):
        text = node.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except ValueError:
                return node
            if isinstance(parsed, list):
                return json.dumps(sorted(clean(parsed), key=sort_key))
        return node
    return node


json.dump(clean(json.load(sys.stdin)), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY

strip_intended() {
  docker run --rm -i "$YQ_IMAGE" -o=json -I=0 '.' < "$1" \
    | python3 -c "$CANONICALIZE_PY"
}

# strip_intended ignores the *contents* of Keycloak's default clients and client
# scopes, so prove separately that they all still exist. This is what would catch
# config-cli treating "absent from the config" as "delete" -- the real hazard of
# declaring only bluecore_api and bluecore_workflows under IMPORT_MANAGED_*=full.
# Reads the raw export rather than the normalized one, because normalize drops
# entities that match its reference realm and would hide them either way.
read -r -d '' ASSERT_DEFAULTS_PY <<'PY' || true
import json, os, sys

realm = json.load(open(sys.argv[1]))
clients = {c.get("clientId") for c in realm.get("clients") or []}
scopes = {s.get("name") for s in realm.get("clientScopes") or []}
missing = [f"client {c}" for c in sorted(os.environ["DEFAULT_CLIENTS"].split()) if c not in clients]
missing += [f"client-scope {s}" for s in sorted(os.environ["DEFAULT_CLIENT_SCOPES"].split()) if s not in scopes]
print(", ".join(missing))
PY

assert_defaults_present() {
  local raw="$1" missing
  missing="$(python3 -c "$ASSERT_DEFAULTS_PY" "$raw")"
  if [[ -n "$missing" ]]; then
    fail "the apply removed Keycloak default entities: $missing"
  fi
  pass "every Keycloak default client and client scope survived the apply"
}

check_equivalence() {
  info "Equivalence: does keycloak/realm/ reproduce the committed export?"
  [[ -f keycloak/realm/bluecore.yaml ]] || fail "keycloak/realm/bluecore.yaml does not exist"

  mkdir -p "$WORK/baseline"
  ./scripts/keycloak/normalize.sh "$COMMITTED_EXPORT" "$WORK/baseline" >/dev/null

  reset_stack
  apply_config || fail "config-cli apply failed"
  export_and_normalize "$WORK/candidate"
  assert_defaults_present "$WORK/export/bluecore-realm.json"

  strip_intended "$WORK/baseline"/*.yaml > "$WORK/baseline.canonical.json"
  strip_intended "$WORK/candidate"/*.yaml > "$WORK/candidate.canonical.json"
  if diff -u "$WORK/baseline.canonical.json" "$WORK/candidate.canonical.json" \
      > "$WORK/equivalence.diff"; then
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
