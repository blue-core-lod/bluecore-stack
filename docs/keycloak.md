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

## 📓 JupyterHub Login

Open JupyterHub at:

```text
http://localhost/jupyter
```

Use the local development account:

| Field | Value |
|---|---|
| Realm | `bluecore` |
| Client | `bluecore_jupyterhub` |
| Username | `developer` |
| Password | `123456` |

Any enabled realm user can currently log in (`Authenticator.allow_all = True` in
`jupyterhub/jupyterhub_config.py`) — there's no role/group check restricting Hub access the way
`bluecore_workflows` restricts Airflow menus. `JUPYTERHUB_ADMIN_USERS` (comma-separated usernames)
grants JupyterHub's own admin UI (start/stop other users' servers), independent of Keycloak roles.

If login fails with `client_not_found` on a Keycloak instance that predates this client, `--import-realm`
skipped it because the `bluecore` realm already existed — see the JupyterHub section of
[local-development.md](local-development.md) for the `kcadm.sh` command to add it by hand.

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
