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
