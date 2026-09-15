#!/bin/bash
# Verify the declarative bluecore realm config against a throwaway Keycloak.
#
#   ./scripts/keycloak/verify-realm.sh [equivalence|convergence|user-safety|dev-users|tamper|all]
#
# equivalence  - applying keycloak/realm/ reproduces the committed export
# convergence  - applying twice is idempotent (proves safe re-apply)
# user-safety  - a user absent from the config survives an apply
# dev-users    - the dev/CI seed users overlay applies additively
# tamper       - proves equivalence actually fails on a broken role binding,
#                then that it passes again once reverted. Not part of `all`:
#                it is insurance that the oracle itself works, not a config
#                check, so it is invoked separately (see CI).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=./lib.sh
source "$ROOT_DIR/scripts/keycloak/lib.sh"

# WORK happens to equal lib.sh's VERIFY_WORK; this script uses WORK directly
# for its own baseline/candidate/second/tampered/reverted output directories,
# while the shared functions in lib.sh address the throwaway stack's fixed
# scratch space via VERIFY_WORK. Kept as one literal, not derived, so it is
# obvious the two must never disagree.
WORK="tmp/kc-verify"
COMMITTED_EXPORT="tests/fixtures/keycloak/bluecore-realm-pre-migration.json"

trap 'compose down --volumes >/dev/null 2>&1 || true' EXIT

kcadm() {
  compose exec -T verify-keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

kcadm_login() {
  kcadm config credentials --server http://localhost:8080 \
    --realm master --user admin --password admin >/dev/null
}

check_equivalence() {
  info "Equivalence: does keycloak/realm/ reproduce the committed export?"
  [[ -f keycloak/realm/bluecore.yaml ]] || fail "keycloak/realm/bluecore.yaml does not exist"

  prune_and_normalize "$COMMITTED_EXPORT" "$WORK/baseline"

  reset_stack
  apply_config || fail "config-cli apply failed"
  export_and_normalize "$WORK/candidate"
  assert_defaults_present "$WORK/export/bluecore-realm.json"
  assert_browser_security_headers "$WORK/export/bluecore-realm.json"

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

# Proves the equivalence check is actually looking, not just green by accident.
# Copies keycloak/realm/bluecore.yaml, rebinds the Allow-Viewer authorization
# policy from Viewer to SuperAdmin (the exact shape of Task 4's critical bug --
# a role binding silently pointed at the wrong role), applies the tampered copy,
# and asserts equivalence FAILS against the committed export. Then reverts and
# re-applies the real, untouched keycloak/realm/ and asserts equivalence PASSES
# again. A verification oracle that is never itself tested is the real risk here,
# not the tamper itself.
check_tamper() {
  info "Tamper case: does the harness actually catch a broken role binding?"

  local tamper_dir="$ROOT_DIR/$WORK/tamper-realm"
  rm -rf "$tamper_dir"
  mkdir -p "$tamper_dir"
  cp keycloak/realm/bluecore.yaml "$tamper_dir/bluecore.yaml"

  grep -q '\\"id\\":\\"bluecore_workflows/Viewer\\"' "$tamper_dir/bluecore.yaml" \
    || fail "tamper target (Allow-Viewer -> bluecore_workflows/Viewer) not found; update check_tamper"

  # bluecore_workflows/Viewer is unique in this file (checked above via grep),
  # so a plain substitution only touches the Allow-Viewer policy's role binding.
  sed -i.bak 's#bluecore_workflows/Viewer#bluecore_workflows/SuperAdmin#' "$tamper_dir/bluecore.yaml"
  rm -f "$tamper_dir/bluecore.yaml.bak"

  prune_and_normalize "$COMMITTED_EXPORT" "$WORK/baseline"

  reset_stack
  apply_config "" "$tamper_dir" || fail "tampered config-cli apply failed"
  export_and_normalize "$WORK/tampered"
  assert_defaults_present "$WORK/export/bluecore-realm.json"
  assert_browser_security_headers "$WORK/export/bluecore-realm.json"

  strip_intended "$WORK/baseline"/*.yaml > "$WORK/baseline.canonical.json"
  strip_intended "$WORK/tampered"/*.yaml > "$WORK/tampered.canonical.json"
  if diff -u "$WORK/baseline.canonical.json" "$WORK/tampered.canonical.json" \
      > "$WORK/tamper.diff"; then
    fail "tampering the Allow-Viewer role binding produced no diff -- the harness cannot see this class of drift"
  fi
  pass "tampered role binding was detected (equivalence correctly FAILED)"

  info "Reverting the tamper and confirming equivalence PASSES again"
  reset_stack
  apply_config || fail "reverted config-cli apply failed"
  export_and_normalize "$WORK/reverted"
  assert_defaults_present "$WORK/export/bluecore-realm.json"
  assert_browser_security_headers "$WORK/export/bluecore-realm.json"

  strip_intended "$WORK/reverted"/*.yaml > "$WORK/reverted.canonical.json"
  if diff -u "$WORK/baseline.canonical.json" "$WORK/reverted.canonical.json" \
      > "$WORK/reverted.diff"; then
    pass "equivalence passes again once the tamper is reverted"
  else
    echo "--- differences (see $WORK/reverted.diff) ---"
    cat "$WORK/reverted.diff"
    fail "equivalence did not pass after reverting the tamper"
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
  # against an already-existing realm. It is also the one that can silently
  # empty browserSecurityHeaders (no IMPORT_MANAGED_REALM policy exists to
  # guard it the way assert_defaults_present's entities are guarded), so check
  # both here.
  assert_defaults_present "$WORK/export/bluecore-realm.json"
  assert_browser_security_headers "$WORK/export/bluecore-realm.json"

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

# The exact realm-role and bluecore_workflows client-role sets each seed user
# is declared with in bluecore-dev-users.yaml. Kept here (not derived from the
# YAML) so this check is an independent read of what SHOULD be true, not an
# echo of the file it is checking. Role reconciliation is on by default (see
# Step 5 of the task-5 brief), so the config is authoritative: these are
# equality checks, not "at least contains" checks -- an extra undeclared role
# is exactly as wrong here as a missing one.
expected_realm_roles() {
  case "$1" in
    developer) echo "create default-roles-bluecore export update" ;;
    dev_op|dev_user|dev_viewer|dev_public) echo "default-roles-bluecore" ;;
  esac
}

expected_client_roles() {
  case "$1" in
    developer) echo "Admin create update" ;;
    dev_op) echo "Op" ;;
    dev_user) echo "User" ;;
    dev_viewer) echo "Viewer" ;;
    dev_public) echo "Public" ;;
  esac
}

# Read back a user's actual realm roles and bluecore_workflows client roles
# and compare against expected_realm_roles/expected_client_roles above. This
# is what would have caught developer losing its Admin/create/update client
# roles, or a dev_op<->dev_viewer role swap -- existence alone proves neither.
assert_user_roles() {
  local u="$1" expected_realm expected_client actual_realm actual_client
  expected_realm="$(expected_realm_roles "$u" | tr ' ' '\n' | sort | tr '\n' ' ' | xargs)"
  expected_client="$(expected_client_roles "$u" | tr ' ' '\n' | sort | tr '\n' ' ' | xargs)"

  actual_realm="$(kcadm get-roles -r bluecore --uusername "$u" --fields name \
    | python3 -c 'import json,sys; print(" ".join(sorted(r["name"] for r in json.load(sys.stdin))))')"
  actual_client="$(kcadm get-roles -r bluecore --uusername "$u" --cclientid bluecore_workflows --fields name \
    | python3 -c 'import json,sys; print(" ".join(sorted(r["name"] for r in json.load(sys.stdin))))')"

  [[ "$actual_realm" == "$expected_realm" ]] \
    || fail "user $u realm roles are [$actual_realm], expected [$expected_realm]"
  [[ "$actual_client" == "$expected_client" ]] \
    || fail "user $u bluecore_workflows client roles are [$actual_client], expected [$expected_client]"
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

  for u in developer dev_op dev_user dev_viewer dev_public; do
    assert_user_roles "$u"
  done
  pass "all five seed users hold exactly their declared realm and client roles"

  # Realm settings must have survived the second, minimal file.
  kcadm get realms/bluecore --fields sslRequired | grep -q external \
    || fail "sslRequired was blanked by the users pass"
  kcadm get clients -r bluecore --fields clientId | grep -q bluecore_workflows \
    || fail "clients were removed by the users pass"
  pass "realm settings and clients survived the users pass"

  # This exact two-apply sequence (apply_config then apply_dev_users) is what
  # silently emptied browserSecurityHeaders before bluecore.yaml declared it
  # explicitly -- kcadm's --fields flag does not reliably project this nested
  # map (verified empirically), so read the realm whole and parse it, the
  # same way assert_browser_security_headers does.
  kcadm get realms/bluecore > "$WORK/dev-users-realm.json"
  assert_browser_security_headers "$WORK/dev-users-realm.json"
}

case "${1:-all}" in
  equivalence) check_equivalence ;;
  convergence) check_convergence ;;
  user-safety) check_user_safety ;;
  dev-users) check_dev_users ;;
  tamper) check_tamper ;;
  all) check_equivalence; check_convergence; check_user_safety; check_dev_users ;;
  *) echo "usage: $0 [equivalence|convergence|user-safety|dev-users|tamper|all]" >&2; exit 2 ;;
esac
