# 🔐 Keycloak

The `bluecore` realm is defined declaratively in
[`keycloak/realm/bluecore.yaml`](../keycloak/realm/bluecore.yaml). A one-shot
`keycloak-config` compose service applies that file over the Keycloak Admin
REST API (via [keycloak-config-cli](https://github.com/adorsys/keycloak-config-cli))
every time you run `up`, currently in development and CI only (it is defined
in `compose-dev.yaml`, not `compose-base.yaml`). Services that need the realm
to exist (Airflow, Blue Core API, …) gate on
`keycloak-config: service_completed_successfully` in those environments.
Staging and production still run Keycloak with `--import-realm`; see the
note below.

In development and CI only, a second service, `keycloak-config-users`, applies
[`keycloak/realm/bluecore-dev-users.yaml`](../keycloak/realm/bluecore-dev-users.yaml)
to seed the five test accounts below. It never runs against staging or
production.

## 🌬️ Airflow Login

Open Airflow at:

```text
http://localhost/workflows
```

Use the local development account:

| Field | Value |
|---|---|
| Realm | `bluecore` |
| Client | `bluecore_workflows` |
| Username | `developer` |
| Password | `123456` |

Additional local users use the same password. Each holds exactly the
`bluecore_workflows` client role named below (verified against the running
dev stack with `kcadm.sh get-roles`):

| Username | Role |
|---|---|
| `dev_op` | `Op` |
| `dev_public` | `Public` |
| `dev_user` | `User` |
| `dev_viewer` | `Viewer` |

`developer` additionally holds the `Admin`, `update`, and `create`
`bluecore_workflows` client roles, plus the realm roles `create`, `export`,
and `update`.

## 🛡️ Keycloak Admin Login

Open Keycloak at:

```text
http://localhost/keycloak
```

Use the master realm admin account:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `gracious-professed` |

## ✏️ Changing the Realm

Realm structure (clients, roles, authorization policies, …) is config-as-code.
**Do not use the admin console to change realm structure.** Instead:

1. Edit [`keycloak/realm/bluecore.yaml`](../keycloak/realm/bluecore.yaml).
2. Open a pull request.
3. Apply it locally to see the change take effect:

   ```bash
   docker compose -f compose-dev.yaml up -d keycloak-config
   ```

Console edits are exactly the kind of drift this setup exists to catch —
[`scripts/keycloak/drift-check.sh`](../scripts/keycloak/drift-check.sh) reports
whether a live realm has diverged from the repo:

```bash
./scripts/keycloak/drift-check.sh                    # development (default)
./scripts/keycloak/drift-check.sh --env=staging       # staging (once cut over)
./scripts/keycloak/drift-check.sh --env=production    # production (once cut over)
```

It is read-only: it never mutates the target realm, it only exports it
(briefly stopping and restarting the target's `keycloak` container to do so)
and diffs it against what `keycloak/realm/` would produce. It exits `0` when
there is no drift and non-zero when there is.

> ⚠️ Staging and production still run Keycloak with `--import-realm` against
> `KEYCLOAK_REALM_DIR` (see [deploy.md](deploy.md)); their cutover to
> `keycloak-config` is separate follow-on work. Development and CI are fully
> on the declarative flow described here.

### Two gotchas that will burn you

- **Variable syntax is `$(env:VAR)`, never `${env:VAR}`.** The `${}` form is a
  silent no-op — the literal string is written straight into Keycloak. In a
  password field, that seeds the literal placeholder text as the password and
  every login then fails with nothing pointing at the cause. (Keycloak's own
  realm representations use `${role_...}` / `${authBaseUrl}` placeholders, so
  a `${}`-based substitutor would consume those too.)
- **Substitution scans the whole file's raw text, including comments.** A
  comment containing example `$(env:...)` syntax gets "resolved" too, and
  fails the import if it names a variable that doesn't exist.

`keycloak/realm/bluecore.yaml` and `bluecore-dev-users.yaml` document their own
variables in a header comment; read that before adding a new one.

### Verifying the config

```bash
./scripts/keycloak/verify-realm.sh [equivalence|convergence|user-safety|dev-users|tamper|all]
```

runs the declarative config against a throwaway Keycloak and checks it against
the frozen pre-migration export
(`tests/fixtures/keycloak/bluecore-realm-pre-migration.json`, a **test
fixture**, not something to hand-edit). CI runs `all` plus `tamper` on every
push.

## 🔑 Rotating credentials

To change the Airflow client secret, a dev user password, a real
staging/production user's password, or the master admin login, see
[updating-keycloak-credentials.md](updating-keycloak-credentials.md).
