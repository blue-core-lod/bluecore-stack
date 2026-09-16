#!/bin/bash
# Verify the declarative bluecore realm config against a throwaway Keycloak.
#
#   ./scripts/keycloak/verify-realm.sh [equivalence|convergence|user-safety|all]
#
# equivalence  - applying keycloak/realm/ reproduces the committed export
# convergence  - applying twice is idempotent (proves safe re-apply)
# user-safety  - a user absent from the config survives an apply
# dev-users    - the dev/CI seed users overlay applies additively
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
# deliberately declares none of them, so assert_defaults_present checks that an
# apply never removes them. Their contents ARE still compared -- see prune_legacy_defaults.
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

# Apply the dev-only users overlay with every managed policy set to no-delete,
# so this pass can only add. Unlike apply_config, this file declares only
# `realm` + `users` -- its own two custom clients (bluecore_api,
# bluecore_workflows) ARE in config-cli's tracked state for this file, so
# leaving IMPORT_MANAGED_* at the upstream `full` default here (as apply_config
# does) would let this pass delete them. Every policy below must stay no-delete.
apply_dev_users() {
  docker run --rm \
    --network bluecore-kc-verify_default \
    -v "$ROOT_DIR/keycloak/realm:/config:ro" \
    -e KEYCLOAK_URL=http://verify-keycloak:8080 \
    -e KEYCLOAK_USER=admin \
    -e KEYCLOAK_PASSWORD=admin \
    -e IMPORT_VAR_SUBSTITUTION_ENABLED=true \
    -e IMPORT_FILES_LOCATIONS=/config/bluecore-dev-users.yaml \
    -e KEYCLOAK_DEV_USER_PASSWORD=123456 \
    -e IMPORT_MANAGED_CLIENT=no-delete \
    -e IMPORT_MANAGED_ROLE=no-delete \
    -e IMPORT_MANAGED_CLIENT_SCOPE=no-delete \
    -e IMPORT_MANAGED_SCOPE_MAPPING=no-delete \
    -e IMPORT_MANAGED_CLIENT_SCOPE_MAPPING=no-delete \
    -e IMPORT_MANAGED_COMPONENT=no-delete \
    -e IMPORT_MANAGED_SUB_COMPONENT=no-delete \
    -e IMPORT_MANAGED_AUTHENTICATION_FLOW=no-delete \
    -e IMPORT_MANAGED_REQUIRED_ACTION=no-delete \
    -e IMPORT_MANAGED_IDENTITY_PROVIDER=no-delete \
    -e IMPORT_MANAGED_IDENTITY_PROVIDER_MAPPER=no-delete \
    -e IMPORT_MANAGED_GROUP=no-delete \
    -e IMPORT_MANAGED_SUB_GROUP=no-delete \
    -e IMPORT_MANAGED_CLIENT_AUTHORIZATION_RESOURCES=no-delete \
    "$CONFIG_CLI_IMAGE"
}

# Keycloak version drift *inside Keycloak's own default clients and client scopes*.
#
# The dev realm was created by an older Keycloak and migrated forward. That older
# version wrote two keys explicitly when it created the default entities, and
# 26.1.2 no longer does -- in both cases the omitted value is the effective
# default, so this is a version artifact and not configuration:
#
#   attributes."post.logout.redirect.uris" = "+"   on admin-cli, broker, realm-management
#   config."userinfo.token.claim"          = "true" on 7 named default-scope mappers
#
# Those 10 keys are the *complete* set of differences between this realm's
# default entities and the ones a 26.1.2 realm creates today (established by a
# field-by-field diff of the two raw exports; account, account-console and
# security-admin-console differ in nothing at all).
#
# They are pruned here, from the raw export of BOTH sides, rather than excluded
# later in the canonicalizer. That is deliberate and it is the only stage where
# a narrow fix works: normalize's granularity is the whole entity -- it emits an
# entity in full if any field differs from its reference realm and omits it
# entirely otherwise. Dropping these keys post-normalize would leave a fully
# populated entity on the baseline side and nothing at all on the candidate
# side. Pruning pre-normalize makes normalize omit admin-cli, broker and the
# client scopes from both sides symmetrically, and -- the point of doing it this
# way -- leaves every other field of every default entity under comparison. An
# added redirectUri on account-console or a changed default-scope mapper still
# makes normalize emit the entity on one side only, and still fails the diff.
read -r -d '' PRUNE_LEGACY_PY <<'PY' || true
import json, sys

LEGACY_LOGOUT_CLIENTS = {"admin-cli", "broker", "realm-management"}
LEGACY_USERINFO_MAPPERS = {
    "acr": {"acr loa level"},
    "basic": {"auth_time"},
    "microprofile-jwt": {"groups"},
    "organization": {"organization"},
    "service_account": {"Client Host", "Client ID", "Client IP Address"},
}

realm = json.load(open(sys.argv[1]))

for client in realm.get("clients") or []:
    if client.get("clientId") in LEGACY_LOGOUT_CLIENTS:
        attributes = client.get("attributes")
        if isinstance(attributes, dict):
            attributes.pop("post.logout.redirect.uris", None)

for scope in realm.get("clientScopes") or []:
    mapper_names = LEGACY_USERINFO_MAPPERS.get(scope.get("name"))
    if not mapper_names:
        continue
    for mapper in scope.get("protocolMappers") or []:
        if mapper.get("name") in mapper_names:
            config = mapper.get("config")
            if isinstance(config, dict):
                config.pop("userinfo.token.claim", None)

with open(sys.argv[2], "w") as out:
    json.dump(realm, out)
PY

# Prune the legacy default-entity keys from a raw realm export, then normalize it.
prune_and_normalize() {
  local raw="$1" outdir="$2"
  local pruned="$WORK/$(basename "$outdir").pruned.json"
  mkdir -p "$outdir"
  python3 -c "$PRUNE_LEGACY_PY" "$raw" "$pruned"
  ./scripts/keycloak/normalize.sh "$pruned" "$outdir" >/dev/null
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

  prune_and_normalize "$WORK/export/bluecore-realm.json" "$outdir"
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
# Two modes, selected by CANONICALIZE_MODE:
#   full       - drop the intended differences above, then canonicalize ordering.
#                Used by equivalence, which compares two *different* realms.
#   order-only - canonicalize ordering and drop NOTHING. Used by convergence,
#                which compares one realm to itself across a re-apply: the UUIDs,
#                the secret and config-cli's own state attributes must all match
#                there, and dropping them would hide real apply-to-apply churn.
read -r -d '' CANONICALIZE_PY <<'PY' || true
import json, os, sys

DROPPING = os.environ.get("CANONICALIZE_MODE", "full") == "full"

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


def clean(node, parent_key=None, dropping=None):
    if dropping is None:
        dropping = DROPPING
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if dropping and key in DROP_KEYS:
                continue
            if (
                dropping
                and parent_key == "attributes"
                and (key in DROP_ATTRS or key.startswith(DROP_ATTR_PREFIX))
            ):
                continue
            cleaned = clean(value, key, dropping)
            # normalize omits these keys altogether when it has nothing to say,
            # so treat an empty list as absent rather than as a difference.
            if dropping and key in ("clients", "clientScopes") and cleaned == []:
                continue
            out[key] = cleaned
        return out
    if isinstance(node, list):
        return sorted(
            (clean(item, parent_key, dropping) for item in node), key=sort_key
        )
    if isinstance(node, str):
        text = node.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except ValueError:
                return node
            if isinstance(parsed, list):
                # Ordering is normalized here but NOTHING is dropped, hence the
                # explicit dropping=False. These strings carry the authorization
                # role bindings:
                #   config.roles = [{"id":"bluecore_workflows/Viewer","required":false}]
                # Letting DROP_KEYS reach inside would delete that `id` and erase
                # the binding under test -- every Allow-* policy would collapse to
                # [{"required": false}] and rebinding Allow-Viewer to SuperAdmin,
                # or pointing a policy at a nonexistent role, would pass silently.
                return json.dumps(clean(parsed, None, dropping=False))
        return node
    return node


json.dump(clean(json.load(sys.stdin)), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY

_canonicalize() {
  docker run --rm -i "$YQ_IMAGE" -o=json -I=0 '.' < "$1" \
    | python3 -c "$CANONICALIZE_PY"
}

# Drop the intended differences, then canonicalize ordering. For equivalence.
strip_intended() {
  CANONICALIZE_MODE=full _canonicalize "$1"
}

# Canonicalize ordering only, dropping nothing. For convergence.
#
# Java's String.hashCode is unsalted, so HashSet iteration order is stable run to
# run, but collections assembled from JPA queries without a total ORDER BY can
# still shift row order after the second apply's UPDATEs. Comparing ordered JSON
# instead of raw YAML text removes that latent flake without weakening the check:
# convergence still compares every field equivalence drops, which is what makes
# it the stronger of the two.
canonicalize_order_only() {
  CANONICALIZE_MODE=order-only _canonicalize "$1"
}

# Prove that Keycloak's default clients and client scopes all still exist. This is
# what would catch config-cli treating "absent from the config" as "delete" -- the
# real hazard of declaring only bluecore_api and bluecore_workflows under
# IMPORT_MANAGED_*=full. Reads the raw export rather than the normalized one,
# because normalize omits any entity matching its reference realm, so a default
# entity being deleted and a default entity being pristine look identical there.
#
# Must be called after EVERY apply, not just the first. Delete-missing logic only
# engages against an already-existing realm, so the second apply is the path where
# deletion can actually happen -- checking only the first would guard the wrong one.
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

  prune_and_normalize "$COMMITTED_EXPORT" "$WORK/baseline"

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
  # The second apply is the one that can delete: delete-missing logic only runs
  # against an already-existing realm.
  assert_defaults_present "$WORK/export/bluecore-realm.json"

  canonicalize_order_only "$WORK/candidate"/*.yaml > "$WORK/candidate.ordered.json"
  canonicalize_order_only "$WORK/second"/*.yaml > "$WORK/second.ordered.json"
  if diff -u "$WORK/candidate.ordered.json" "$WORK/second.ordered.json" \
      > "$WORK/convergence.diff"; then
    pass "second apply changed nothing"
  else
    echo "--- differences (see $WORK/convergence.diff) ---"
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

check_dev_users() {
  info "Dev users: are the five seed accounts created with their roles?"
  reset_stack
  apply_config || fail "realm apply failed"
  apply_dev_users || fail "dev users apply failed"

  kcadm_login
  for u in developer dev_op dev_user dev_viewer dev_public; do
    kcadm get users -r bluecore -q "username=$u" --fields username \
      | grep -q "$u" || fail "seed user $u was not created"
  done
  pass "all five seed users exist"

  # Realm settings must have survived the second, minimal file.
  kcadm get realms/bluecore --fields sslRequired | grep -q external \
    || fail "sslRequired was blanked by the users pass"
  kcadm get clients -r bluecore --fields clientId | grep -q bluecore_workflows \
    || fail "clients were removed by the users pass"
  pass "realm settings and clients survived the users pass"
}

case "${1:-all}" in
  equivalence) check_equivalence ;;
  convergence) check_convergence ;;
  user-safety) check_user_safety ;;
  dev-users) check_dev_users ;;
  all) check_equivalence; check_convergence; check_user_safety; check_dev_users ;;
  *) echo "usage: $0 [equivalence|convergence|user-safety|dev-users|all]" >&2; exit 2 ;;
esac
