# 🔑 Updating Keycloak Credentials

Step-by-step guide for rotating Keycloak credentials: the Airflow client
secret, development seed-user passwords, real staging/production user
passwords, and the master admin login.

Do this whenever you rotate a secret — especially before a public deploy,
since the committed dev realm secrets should never be reused in production
(see [deploy.md](deploy.md#-rotate-before-going-public)).

The `bluecore` realm itself is config-as-code, applied from
[`keycloak/realm/bluecore.yaml`](../keycloak/realm/bluecore.yaml) by the
`keycloak-config` compose service on every `up` (see
[keycloak.md](keycloak.md)). Rotating a credential means changing a value in
`.env` and re-running the relevant one-shot service — there is no export step
and nothing to commit back.

---

## ✅ Before you start

- The stack is running (`./scripts/dev/run`, or the deployed stack for prod).
- You have the environment's `.env` file to edit.
- You have the **master realm admin** login (`KEYCLOAK_ADMIN` /
  `KEYCLOAK_ADMIN_PASSWORD` from `.env`; local default `admin` /
  `gracious-professed`) if you need the admin console at all (only the real
  staging/production user case below still needs it).

---

## 1️⃣ Rotate the Airflow client secret

The `bluecore_workflows` client secret lives in one place:
`AIRFLOW_KEYCLOAK_CLIENT_SECRET` in the environment's `.env`. It used to be
copied across five places by hand; now there is one.

1. Generate a new secret value (any sufficiently random string).
2. Set it in that environment's `.env`:

   ```dotenv
   AIRFLOW_KEYCLOAK_CLIENT_SECRET=<new-secret>
   ```

3. Re-run the config apply so Keycloak picks it up:

   ```bash
   docker compose -f compose-dev.yaml up -d keycloak-config
   ```

4. Restart Airflow so it picks up the new secret from `.env`.

> ⚠️ **Gotcha:** keycloak-config-cli caches a checksum of the last file it
> successfully applied to a realm and skips reprocessing entirely when the
> next run's (post-substitution) content matches it (with
> `LOGGING_LEVEL_DE_ADORSYS=DEBUG` this logs as `No need to update realm
> 'bluecore', import checksum same`). Setting a genuinely new secret changes
> that content, so it always forces a real reapply — confirmed by rotating
> the secret and reading the new value back from Keycloak. The cache instead
> bites a *different* case: re-running the apply unchanged, expecting it to
> overwrite a hand-edited value made in the console. If a re-run ever reports
> success but nothing changed, force a real reapply — for local/dev, the
> simplest fix is recreating the realm
> (`./scripts/dev/down --volumes && ./scripts/dev/run`).

---

## 2️⃣ Rotate a development/CI seed-user password

The five seed accounts (`developer`, `dev_op`, `dev_user`, `dev_viewer`,
`dev_public`) all share one password, `KEYCLOAK_DEV_USER_PASSWORD`, applied
from [`keycloak/realm/bluecore-dev-users.yaml`](../keycloak/realm/bluecore-dev-users.yaml)
by the `keycloak-config-users` service (development/CI only — it never runs
against staging or production).

1. Set the new password in `.env`:

   ```dotenv
   KEYCLOAK_DEV_USER_PASSWORD=<new-password>
   ```

2. Re-run the seed apply:

   ```bash
   docker compose -f compose-dev.yaml up -d keycloak-config-users
   ```

> ⚠️ Same checksum-cache gotcha as above. A real password change always
> forces a real reapply; it's only re-running *unchanged* that can silently
> no-op. If that happens, recreate the realm to force it through
> (`./scripts/dev/down --volumes && ./scripts/dev/run`).

---

## 3️⃣ Rotate a real staging/production user's password

Real users in staging and production are **not** declared in the repo —
`keycloak/realm/bluecore-dev-users.yaml` is development/CI seed data only, and
keycloak-config-cli is upsert-only for users: it can create or update users
it manages, but it cannot delete or modify an account it doesn't know about.
So this one still goes through the admin console:

1. Open the admin console (`https://<your-domain>/keycloak`) and sign in with
   the master admin account.
2. Switch to the **`bluecore`** realm, go to **Users**, select the user.
3. Open the **Credentials** tab, click **Reset password**, set the new value,
   and set **Temporary** to **Off** (unless you want a forced reset at next
   login).

This is the one credential rotation that still lives entirely in Keycloak's
database; there is nothing to sync back into the repo.

---

## 4️⃣ Updating the master admin login

Unchanged. The `admin` account lives in the **`master`** realm, not
`bluecore`, and is outside the declarative config entirely.

- **To change it now:** in the **`master`** realm go to **Users → admin →
  Credentials → Reset password**. This persists to the database immediately.
- **For fresh deploys:** `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` in `.env`
  only bootstrap the admin account the **first time** Keycloak starts against
  an empty database. Update them in `.env` too so a rebuilt stack gets the new
  credentials.

---

## ✏️ Changing realm structure, not credentials

If what you actually need is a new client, role, or authorization policy —
not a rotated secret or password — that is a pull request against
[`keycloak/realm/bluecore.yaml`](../keycloak/realm/bluecore.yaml), not an
admin-console change. See [keycloak.md](keycloak.md#-changing-the-realm) for
the workflow and the `$(env:VAR)` variable-syntax gotchas, and
[`scripts/keycloak/drift-check.sh`](../scripts/keycloak/drift-check.sh) for
catching console changes that bypass this.
