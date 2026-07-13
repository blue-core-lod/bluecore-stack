# 🔑 Updating Keycloak Credentials

Step-by-step guide for changing Keycloak credentials (client secrets, realm user
passwords, admin login) and persisting the new settings with the export script.

Do this whenever you rotate a secret — especially before a public deploy, since
the committed dev realm secret should never be reused in production (see
[deploy.md](deploy.md#-rotate-before-going-public)).

> **Where exports go** (chosen by `--env`, defaults to `development`)
> - **development:** `keycloak-export/development/bluecore-realm.json` — **committed** (dev-only values).
> - **staging:** `keycloak-export/staging/bluecore-realm.json` — **git-ignored**.
> - **production:** `keycloak-export/production/bluecore-realm.json` — **git-ignored**.
>
> The staging/production files hold real secrets and stay on their servers, where
> `compose.yaml` imports them from the dir named by `KEYCLOAK_REALM_DIR`.

---

## ✅ Before you start

- The stack is running (`./scripts/dev/run`, or the deployed stack for prod).
- You can reach the Keycloak admin console:
  - Local: `http://localhost/keycloak`
  - Production: `https://<your-domain>/keycloak`
- You have the **master realm admin** login (`KEYCLOAK_ADMIN` /
  `KEYCLOAK_ADMIN_PASSWORD` from `.env`; local default `admin` /
  `gracious-professed`).

> Changes made in the admin console are saved to the Keycloak database
> immediately. The **export script** is what copies that live state into a realm
> JSON file so it survives a fresh deploy.

---

## 1️⃣ Log in to the Keycloak admin console

1. Open `http://localhost/keycloak` (or your public URL).
2. Sign in with the master admin account.
3. Use the realm switcher (top-left) to select the **`bluecore`** realm for the
   steps below. (Admin-account changes happen in the **`master`** realm — see
   [Updating the admin login](#4️⃣-updating-the-master-admin-login).)

---

## 2️⃣ Regenerate a client secret

For the `bluecore_workflows` client (the Airflow OAuth client):

1. In the **`bluecore`** realm, go to **Clients → `bluecore_workflows`**.
2. Open the **Credentials** tab.
3. Click **Regenerate** next to the client secret.
4. **Copy the new secret** — you'll paste it into `.env` next.

Then sync it into `.env` so the Airflow client keeps working:

```dotenv
AIRFLOW_KEYCLOAK_CLIENT_SECRET=<paste-the-new-secret>
```

⚠️ Restart the bluecore-stack so the changes take effect.


> The client secret **is** included in the realm export, so Step 5 captures it.
> Keeping `.env` and the export in sync avoids a login-loop after a fresh deploy.

---

## 3️⃣ Change a realm user's password

For the local/dev accounts (`developer`, `dev_op`, `dev_public`, `dev_user`,
`dev_viewer`) or any real user:

1. In the **`bluecore`** realm, go to **Users** and select the user.
2. Open the **Credentials** tab.
3. Click **Reset password**, enter the new password, and set **Temporary** to
   **Off** (unless you want a forced reset at next login).
4. Click **Save**.

User password hashes are exported with `--users=realm_file`, so Step 5 captures
them.

---

## 4️⃣ Updating the master admin login

The `admin` account lives in the **`master`** realm, **not** `bluecore`, so it is
**not** captured by the realm export.

- **To change it now:** in the **`master`** realm go to **Users → admin →
  Credentials → Reset password**. This persists to the database immediately.
- **For fresh deploys:** `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` in `.env`
  only bootstrap the admin account the **first time** Keycloak starts against an
  empty database. Update them in `.env` too so a rebuilt stack gets the new
  credentials.

---

## 5️⃣ Export the realm to save your changes

Run the export script to write the current live realm (including regenerated
client secrets and user passwords) to a realm JSON file.

**development** (default) — writes the **committed** dev realm to
`keycloak-export/development/bluecore-realm.json`:

```bash
./scripts/export-keycloak-realm.sh
```

**staging / production** — writes to the matching **git-ignored** dir
(`keycloak-export/staging/` or `keycloak-export/production/`):

```bash
./scripts/export-keycloak-realm.sh --env=staging
./scripts/export-keycloak-realm.sh --env=production
```

The script runs `docker compose ... run --rm keycloak export --realm=bluecore
--users=realm_file` and prints `✅ Export completed successfully.` on success.

> 💡 If the export fails with a database lock, stop the running Keycloak
> container first (`docker compose -f compose.yaml stop keycloak`), re-run the
> export, then start it again.

---

## 6️⃣ Verify and save

**Local/dev** — commit the updated dev realm so other developers get it:

```bash
git diff keycloak-export/development/bluecore-realm.json  # confirm the changes happened
git add keycloak-export/development/bluecore-realm.json
git commit -m "Rotate bluecore Keycloak dev credentials"
```

**Deployed (staging / production)** — **do NOT commit.**
`keycloak-export/staging/` and `keycloak-export/production/` are git-ignored and
hold real secrets. Just confirm the file was written and stays on the server:

```bash
keycloak-export/production/bluecore-realm.json  # Production keycloak config location 
keycloak-export/staging/bluecore-realm.json     # Staging keycloak config location
```

> ⚠️ Never reuse a credential that has been committed to git. The dev realm
> (`keycloak-export/development/bluecore-realm.json`) is public in the repo — production must
> use its own regenerated secrets, kept only in `keycloak-export/production/` and
> the server's `.env`.

---

## 🌱 First-time deployed setup (staging / production)

The deployed realm dir is git-ignored, so `keycloak-export/<env>/bluecore-realm.json`
won't exist on a brand-new server. Seed it once before the first
`docker compose -f compose.yaml up` (swap `production` for `staging` as needed):

1. Create the directory and a starting realm file (e.g. from the dev export):

   ```bash
   mkdir -p keycloak-export/production
   cp keycloak-export/development/bluecore-realm.json keycloak-export/production/bluecore-realm.json
   ```

2. Edit that copy for the environment — set the public redirect URIs / web origins
   and a freshly generated `bluecore_workflows` client secret (see
   [deploy.md](deploy.md)).
3. Point the stack at that dir. `compose.yaml` defaults to
   `keycloak-export/production`; for staging set `KEYCLOAK_REALM_DIR` in the
   server's `.env`:

   ```dotenv
   KEYCLOAK_REALM_DIR=./keycloak-export/staging
   ```

4. Start the stack; Keycloak imports the realm from that directory.
5. From then on, make changes in the admin console and re-run
   `./scripts/export-keycloak-realm.sh --env=<env>` to update the file in place.

---

## ♻️ Applying an updated export to an existing environment

Keycloak only imports the realm file on startup **when the realm does not already
exist** in the database. Re-running the stack against a database that already has
the `bluecore` realm will **not** re-apply an exported JSON. To make a new file
take effect, either:

- Make the change directly in the target's admin console (then export), or
- Recreate the Keycloak database so the realm re-imports on next start
  (destructive — only for throwaway/dev data):

  ```bash
  ./scripts/dev/down --volumes && ./scripts/dev/run
  ```
