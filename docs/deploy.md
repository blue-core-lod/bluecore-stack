# 🚀 Public Deployment — Env Values to Change

The defaults in [configuration.md](configuration.md) are for **local development only**. Before a public-facing deploy, 
override every value below in the `.env` on the server. Anything left at its local default is either insecure or points 
at `localhost` and will break.

---

## 🔐 Credentials & secrets

Change all of these to strong, unique values.

| Variable | Local default | Change to |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | `airflow` / `airflow` | Strong, unique DB credentials |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | `airflow` / `airflow` | Same DB credentials |
| `DATABASE_URL` | `...airflow:airflow@postgres/bluecore` | Rebuild with prod host + credentials |
| `AIRFLOW_CONN_BLUECORE_DB` | `...airflow:airflow@postgres:5432/bluecore` | Rebuild with prod host + credentials |
| `KC_DB_USERNAME` / `KC_DB_PASSWORD` | `airflow` / `airflow` | Same DB credentials |
| `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` | `admin` / `gracious-professed` | Strong, unique admin login |
| `AIRFLOW_WWW_USER_USERNAME` / `AIRFLOW_WWW_USER_PASSWORD` | `airflow` / `airflow` | Strong, unique Airflow admin login |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | `KIu8gWa8rtjlT0Zl7zkNzsObFZGJ2IsJ` | **Regenerate** in Keycloak, keep in sync with the realm |
| `CR_PAT` | `YOUR_GITHUB_TOKEN` | GHCR token with `read:packages` |

---

## 🌐 Public URLs & CORS

Move every browser-facing URL from `localhost` to the public HTTPS origin
(example: `https://bcld.info`).

| Variable | Local default | Change to |
|---|---|---|
| `BLUECORE_URL` | `http://localhost` | `https://bcld.info` |
| `AIRFLOW_EXTERNAL_URL` | `http://localhost/workflows/` | `https://bcld.info/workflows/` |
| `KEYCLOAK_EXTERNAL_URL` | `http://localhost/keycloak/` | `https://bcld.info/keycloak/` |
| `KC_HOSTNAME` | `http://localhost/keycloak` | `https://bcld.info/keycloak` |
| `KC_HOSTNAME_STRICT` | `false` | `true` |
| `MARVA_REDIRECT_BASE` | `http://localhost/marva/` | `https://bcld.info/marva/` |
| `BLUECORE_STACK_KEYCLOAK_REDIRECT_URI` | `http://localhost/marva/util/auth/callback` | `https://bcld.info/marva/util/auth/callback` |
| `MARVA_BASE_URL` | `http://localhost/marva/` | `https://bcld.info/marva/` |
| `SINOPIA_BASE_URL` | `http://localhost/sinopia/` | `https://bcld.info/sinopia/` |
| `CORS_ORIGIN` | `*` | Lock to the public origin (e.g. `https://bcld.info`) |
| `AIRFLOW_VAR_SINOPIA_ENV` | `dev` | `stage` / `prod` |

> ✅ Leave the internal service URLs as-is — `KEYCLOAK_INTERNAL_URL`,
> `KEYCLOAK_MIDDLEWARE_BASE`, and `AIRFLOW_INTERNAL_URL` use Docker service names
> and do not change between environments.

---

## 🚨 Rotate before going public

`AIRFLOW_KEYCLOAK_CLIENT_SECRET` is committed to the repo (in `.env` and in `keycloak-export/development/bluecore-realm.json`), 
so treat it as **compromised**:regenerate the `bluecore_workflows` client secret in Keycloak and update both the `.env` 
value and the realm export. Never reuse a credential that has been in version control.
