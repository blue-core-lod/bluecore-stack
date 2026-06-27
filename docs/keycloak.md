# Keycloak

The local Keycloak container imports the Blue Core realm from `keycloak-export/bluecore-realm.json` when it starts.

## Airflow Login

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

## Keycloak Admin Login

Open Keycloak at:

```text
http://localhost/keycloak
```

Use the master realm admin account:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `gracious-professed` |

## Export Realm Configuration

After changing the `bluecore` realm in the Keycloak UI, export the realm config back to `keycloak-export/bluecore-realm.json`.

For local development:

```bash
./scripts/export-keycloak-realm.sh
```

For the deployed EC2 production layout:

```bash
./scripts/export-keycloak-realm.sh --env=production
```

The production command writes to `/home/ubuntu/keycloak-export/bluecore-realm.json` through the production compose file.
