# 🚀 Public Deployment — Env Values to Change

The values in [configuration.md](configuration.md) are the local-development `.env`. Before a public-facing deploy, 
override everything below in the `.env` on the server. Anything left at its local default is either insecure or points 
at `localhost` and will break.

> This guide tracks the repo's **`.env`** file (the one the stack actually reads).
> `deploy.env` is an unrelated scratch file — ignore it.

---

## 🔐 Credentials & secrets

Change these to strong, unique values.

| Variable | `.env` default | Change to |
|---|---|---|
| `CR_PAT` | `YOUR_GITHUB_TOKEN` | GHCR token with `read:packages` (for private image pulls) |
| `AIRFLOW_WWW_USER_USERNAME` / `AIRFLOW_WWW_USER_PASSWORD` | `airflow` / `airflow` | Strong, unique Airflow admin login |
| `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` | `admin` / `gracious-professed` | Strong, unique Keycloak master-admin login |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | `KIu8gWa8rtjlT0Zl7zkNzsObFZGJ2IsJ` | **Regenerate** in Keycloak; keep in sync with the realm export |

---

## 🗄️ Database (external Postgres)

Production runs against an **external** Postgres (the `compose.yaml` stack has no `postgres` service). `compose.yaml` 
builds **every** service's DB connection -> bc_api, all Airflow services, and Keycloak — from these four variables, which
default to `airflow` / `airflow` / `postgres` / `5432` when unset. **Add them to `.env`:**

| Variable | Default (if unset) | Change to |
|---|---|---|
| `DATABASE_USERNAME` | `airflow` | Your external DB user |
| `DATABASE_PASSWORD` | `airflow` | Your external DB password |
| `DATABASE_HOSTNAME` | `postgres` | Your external DB host |
| `DATABASE_PORT` | `5432` | Your external DB port |

> Both compose files build the DB connection from the four vars above

---

## 🌐 Public URLs & CORS

Move every browser-facing URL from `localhost` to the public HTTPS origin
(example: `https://bcld.info`).

| Variable | `.env` default | Change to |
|---|---|---|
| `BLUECORE_URL` | `http://localhost` | `https://bcld.info` |
| `AIRFLOW_EXTERNAL_URL` | `http://localhost/workflows/` | `https://bcld.info/workflows/` |
| `KEYCLOAK_EXTERNAL_URL` | `http://localhost/keycloak/` | `https://bcld.info/keycloak/` |
| `KC_HOSTNAME` | `http://localhost/keycloak` | `https://bcld.info/keycloak` |
| `KC_HOSTNAME_STRICT` | `false` | `true` |
| `MARVA_REDIRECT_BASE` | `http://localhost/marva/` | `https://bcld.info/marva/` |
| `BLUECORE_STACK_KEYCLOAK_REDIRECT_URI` | `http://localhost/marva/util/auth/callback` | `https://bcld.info/marva/util/auth/callback` |
| `CORS_ORIGIN` | `*` | Lock to the public origin, e.g. `https://bcld.info` |

> ✅ Leave the internal service URLs as-is — `KEYCLOAK_INTERNAL_URL`,
> `KEYCLOAK_MIDDLEWARE_BASE`, and `AIRFLOW_INTERNAL_URL` use Docker service names
> and don't change between environments.

---

## 🚨 Rotate before going public

`AIRFLOW_KEYCLOAK_CLIENT_SECRET` is committed to the repo (in `.env` and in `keycloak-export/development/bluecore-realm.json`), 
so treat it as **compromised**: regenerate the `bluecore_workflows` client secret in Keycloak and update both the `.env` 
value and the realm export. Never reuse a credential that has been in version control. See [updating-keycloak-credentials.md](updating-keycloak-credentials.md).
