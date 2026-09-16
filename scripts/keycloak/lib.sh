# Shared machinery for scripts/keycloak/verify-realm.sh and
# scripts/keycloak/drift-check.sh.
#
# Both scripts answer the same underlying question -- "does keycloak/realm/
# reproduce a specific real Keycloak export?" -- for two different baselines
# (verify-realm.sh: the committed pre-migration fixture; drift-check.sh: a
# live environment's export). They MUST run that comparison through the exact
# same pipeline, or the two checks can silently disagree about what counts as
# drift. This file is that one pipeline: the legacy-default pruner, the
# canonicalizer, and the throwaway-Keycloak apply/export helpers.
#
# Not shared here (kept local to verify-realm.sh, since drift-check.sh has no
# use for them): the kcadm helpers, the dev-users apply, and the tamper case.
#
# Callers must set ROOT_DIR and cd there, and set -euo pipefail, before
# sourcing this file.

CONFIG_CLI_IMAGE="${KEYCLOAK_CONFIG_CLI_IMAGE:-adorsys/keycloak-config-cli:6.5.1-26.1.0}"
# Only used to turn normalized YAML into JSON so python3's stdlib can canonicalize
# it; the host is not assumed to have PyYAML.
YQ_IMAGE="${YQ_IMAGE:-mikefarah/yq:4.44.3}"

# Entities Keycloak creates by itself on every realm. keycloak/realm/bluecore.yaml
# deliberately declares none of them, so assert_defaults_present checks that an
# apply never removes them. Their contents ARE still compared -- see prune_legacy_defaults.
export DEFAULT_CLIENTS="${DEFAULT_CLIENTS:-account account-console admin-cli broker realm-management security-admin-console}"
export DEFAULT_CLIENT_SCOPES="${DEFAULT_CLIENT_SCOPES:-acr address basic email microprofile-jwt offline_access organization phone profile role_list roles saml_organization service_account web-origins}"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[1;34m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; exit 1; }
info() { echo -e "${BLUE}==>${NC} $1"; }

# The throwaway Keycloak+Postgres both scripts apply keycloak/realm/ to and
# read back what config-cli actually produced. compose-keycloak-verify.yaml
# itself declares a bind mount of ./tmp/kc-verify to /data inside
# verify-keycloak, so VERIFY_WORK below must keep matching that path
# literally -- it is not a free choice per caller. Callers are free to use
# their own $WORK for baseline/expected output directories; VERIFY_WORK is
# only the throwaway stack's own scratch space.
VERIFY_COMPOSE="compose-keycloak-verify.yaml"
VERIFY_WORK="tmp/kc-verify"

compose() { docker compose -f "$VERIFY_COMPOSE" "$@"; }

reset_stack() {
  info "Resetting throwaway Keycloak"
  compose down --volumes >/dev/null 2>&1 || true
  rm -rf "$VERIFY_WORK/export" "$VERIFY_WORK/candidate" "$VERIFY_WORK/second"
  mkdir -p "$VERIFY_WORK"
  compose up -d --wait
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
#
# KEYCLOAK_SSL_REQUIRED, KEYCLOAK_PUBLIC_BASE_URL and AIRFLOW_KEYCLOAK_CLIENT_SECRET
# default to verify-realm.sh's fixed throwaway values. drift-check.sh exports
# the target environment's real values before calling this, so the realm it
# applies renders the same $(env:...) substitutions the live realm actually
# has -- otherwise a real difference in, say, KEYCLOAK_PUBLIC_BASE_URL would
# show up as false drift on every redirect URI.
apply_config() {
  local extra_files="${1:-}"
  local realm_dir="${2:-$ROOT_DIR/keycloak/realm}"
  local locations="/config/bluecore.yaml"
  if [[ -n "$extra_files" ]]; then
    locations="$locations,$extra_files"
  fi

  docker run --rm \
    --network bluecore-kc-verify_default \
    -v "$realm_dir:/config:ro" \
    -e KEYCLOAK_URL=http://verify-keycloak:8080 \
    -e KEYCLOAK_USER=admin \
    -e KEYCLOAK_PASSWORD=admin \
    -e KEYCLOAK_AVAILABILITYCHECK_ENABLED=true \
    -e KEYCLOAK_AVAILABILITYCHECK_TIMEOUT=120s \
    -e IMPORT_VAR_SUBSTITUTION_ENABLED=true \
    -e IMPORT_FILES_LOCATIONS="$locations" \
    -e KEYCLOAK_SSL_REQUIRED="${KEYCLOAK_SSL_REQUIRED:-external}" \
    -e KEYCLOAK_PUBLIC_BASE_URL="${KEYCLOAK_PUBLIC_BASE_URL:-http://localhost}" \
    -e AIRFLOW_KEYCLOAK_CLIENT_SECRET="${AIRFLOW_KEYCLOAK_CLIENT_SECRET:-verify-only-secret}" \
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
  local pruned="$VERIFY_WORK/$(basename "$outdir").pruned.json"
  mkdir -p "$VERIFY_WORK" "$outdir"
  python3 -c "$PRUNE_LEGACY_PY" "$raw" "$pruned"
  ./scripts/keycloak/normalize.sh "$pruned" "$outdir" >/dev/null
}

# Export the live bluecore realm from the throwaway Keycloak, then normalize it.
export_and_normalize() {
  local outdir="$1"
  rm -rf "$VERIFY_WORK/export"
  mkdir -p "$VERIFY_WORK/export" "$outdir"

  compose stop verify-keycloak >/dev/null
  compose run --rm --user root verify-keycloak \
    export --dir=/data/export --realm=bluecore --users=realm_file >/dev/null
  compose start verify-keycloak >/dev/null
  compose up -d --wait >/dev/null

  prune_and_normalize "$VERIFY_WORK/export/bluecore-realm.json" "$outdir"
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
