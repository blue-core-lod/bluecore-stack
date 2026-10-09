# 🔐 Keycloak

The local Keycloak container imports the Blue Core realm from `keycloak-export/development/bluecore-realm.json` when it starts.

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

Additional local users use the same password:

| Username | Intended role |
|---|---|
| `dev_op` | Operator |
| `dev_public` | Public user |
| `dev_user` | Standard user |
| `dev_viewer` | Viewer |

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

## 💾 Export Realm Configuration

After changing the `bluecore` realm in the Keycloak UI, export the realm config back to `keycloak-export/development/bluecore-realm.json`.

For local development:

```bash
./scripts/export-keycloak-realm.sh
```

For deployed environments (staging or production):

```bash
./scripts/export-keycloak-realm.sh --env=staging
./scripts/export-keycloak-realm.sh --env=production
```

These write to `keycloak-export/staging/bluecore-realm.json` or `keycloak-export/production/bluecore-realm.json` — **git-ignored** directories so real secrets are never committed. On the server, `compose.yaml` imports the realm from the directory named by `KEYCLOAK_REALM_DIR` (defaults to `keycloak-export/production`).

The export environment defaults to `development` when `--env` is omitted.

## 🔑 Rotating credentials

To change client secrets, user passwords, or the admin login and save them back
to the realm export, see [updating-keycloak-credentials.md](updating-keycloak-credentials.md).

## ⬆️ Upgrading Keycloak

The Keycloak server version is pinned in three places, and nothing flags new releases. Change all three together:

| File | Pin |
|---|---|
| `compose.yaml` | `KEYCLOAK_IMAGE` default |
| `compose-dev.yaml` | `KEYCLOAK_IMAGE` default |
| `.github/workflows/bluecore-integration-test.yml` | `keycloak_image=` in the resolve step |

A server's `.env` can override `KEYCLOAK_IMAGE`, so check staging and production too.

### Before upgrading

- **Back up the `keycloak` database.** Keycloak migrates its schema on startup and the migration is one-way; rolling back means restoring the backup.
- **Read the release notes** for every version between the current one and the target, especially across a major (e.g. 26 → 27).
- **Export the realm** (see [Export Realm Configuration](#-export-realm-configuration)) so you have a fresh copy.

### After upgrading

- `--import-realm` skips a realm that already exists, so the upgrade leaves the realm's data as-is. Re-export and diff against the previous export to catch format changes the new version made.
- Log in through each client: Airflow (`bluecore_workflows`), Sinopia, Marva, the API's `/docs` Authorize button, and **Export to Catalog** on a Blue Core Instance page.

### Browser clients (keycloak-js)

Since Keycloak 26, the browser adapter `keycloak-js` is released separately from the server, and each 26.x release supports all current server versions. It doesn't need to match the server exactly, but check it on a major upgrade:

| Repo | Where | Kept current by |
|---|---|---|
| sinopia_editor | `package.json` / `package-lock.json` | npm |
| bluecore_api | `src/bluecore_api/app/views/templates/_fields.html` (jsDelivr URL + `sha384` in the import map) | The "Update keycloak-js pin" step in `.github/workflows/dependency-updates.yml`, within `KEYCLOAK_JS_MAJOR` |

On a server major upgrade, raise `KEYCLOAK_JS_MAJOR` in bluecore_api's `dependency-updates.yml`; the weekly run then moves the pin and its hash to the new major.

The Airflow login uses `apache-airflow-providers-keycloak` (bluecore-workflows `pyproject.toml`); check its compatibility on a major upgrade too.
