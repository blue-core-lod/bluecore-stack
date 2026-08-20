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
| `AIRFLOW_WWW_USER_USERNAME` / `AIRFLOW_WWW_USER_PASSWORD` | `developer` / `123456` | Strong, unique Airflow admin login |
| `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` | `admin` / `gracious-professed` | Strong, unique Keycloak master-admin login |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | `KIu8gWa8rtjlT0Zl7zkNzsObFZGJ2IsJ` | **Regenerate** in Keycloak; keep in sync with the realm export |
| `JUPYTERHUB_KEYCLOAK_CLIENT_SECRET` | `25dab91f94aa830290df93924b7ec89a1e84e8286356afef` | **Regenerate** in Keycloak; keep in sync with the realm export |
| `JUPYTERHUB_COOKIE_SECRET` | `27bcff...e0bc82` | Regenerate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |

---

## 🗄️ Database (external Postgres)

Production runs against an **external** Postgres (the `compose.yaml` stack has no `postgres` service). `compose.yaml` 
builds **every** service's DB connection -> bc_api, all Airflow services, and Keycloak — from these four variables, which
default to `airflow` / `airflow` / `postgres` / `5432` when unset. **Add them to `.env`:**

> Both compose files build **every** DB connection from the four vars below:

| Variable | Default (if unset) | Change to |
|---|---|---|
| `DATABASE_USERNAME` | `airflow` | Your external DB user |
| `DATABASE_PASSWORD` | `airflow` | Your external DB password |
| `DATABASE_HOSTNAME` | `postgres` | Your external DB host |
| `DATABASE_PORT` | `5432` | Your external DB port |

Create the `jupyterhub` database on the external Postgres yourself before starting
`jupyterhub` (there's no `init-multi-postgres-dbs.sh` equivalent against an external
DB — that script only runs against the dev-mode `postgres` container).

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
| `MARVA_BASE_URL` | `http://localhost/marva/` | `https://bcld.info/marva/` |
| `SINOPIA_BASE_URL` | `http://localhost/sinopia/` | `https://bcld.info/sinopia/` |
| `CORS_ORIGIN` | `*` | Lock to the public origin, e.g. `https://bcld.info` |
| `JUPYTERHUB_EXTERNAL_URL` | `http://localhost/jupyter/` | `https://bcld.info/jupyter/` |
| `JUPYTERHUB_DOCKER_NETWORK` | `bluecore-stack_default` | The Docker network name on the deploy host — check `docker network ls`, it depends on the server's Compose project name/directory |

> ✅ Leave the internal service URLs as-is — `KEYCLOAK_INTERNAL_URL`,
> `KEYCLOAK_MIDDLEWARE_BASE`, and `AIRFLOW_INTERNAL_URL` use Docker service names
> and don't change between environments.

---

## 🔑 Keycloak realm configuration (deployed environments)

On the server, `compose.yaml` imports/exports the realm from the directory named
by `KEYCLOAK_REALM_DIR` (a git-ignored dir holding real secrets):

| Variable | Default | Set to |
|---|---|---|
| `KEYCLOAK_REALM_DIR` | `./keycloak-export/production` | Leave default for production; set `./keycloak-export/staging` on a staging server |

Seed `<KEYCLOAK_REALM_DIR>/bluecore-realm.json` **before** the first `docker compose -f compose.yaml up`, 
and update its public redirect URIs / web origins for the deploy host. 
Full steps: [updating-keycloak-credentials.md](updating-keycloak-credentials.md).

---

## 🚨 Rotate before going public

`AIRFLOW_KEYCLOAK_CLIENT_SECRET` is committed to the repo (in `.env` and in `keycloak-export/development/bluecore-realm.json`), 
so treat it as **compromised**: regenerate the `bluecore_workflows` client secret in Keycloak and update both the `.env` 
value and the realm export.

`JUPYTERHUB_KEYCLOAK_CLIENT_SECRET` and `JUPYTERHUB_COOKIE_SECRET` are likewise committed (dev-only values) — regenerate
both before a public deploy. Rotating the cookie secret invalidates every logged-in Hub session (harmless; users just log
back in), so there's no realm export to keep in sync for it.

`AIRFLOW_WWW_USER_USERNAME` / `AIRFLOW_WWW_USER_PASSWORD` is committed to the repo (in `.env` and in `keycloak-export/development/bluecore-realm.json`),
so treat those as **compromised**: change the user credentials in Keycloak and update both the `.env` value and re-export the `bluecore` realm settings
"Partial export" to include groups, roles, and clients. Upload the exported file to the server (do not commit to github repository).

🚨 Never reuse a credential that has been in version control. See [updating-keycloak-credentials.md](updating-keycloak-credentials.md).