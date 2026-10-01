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
| `HOSTNAME` | *(required)* | Your public domain, e.g. `bcld.info` (must match `/etc/letsencrypt/live/<HOSTNAME>`) |
| `HOSTNAME_ALT` | *(unset)* | Only for a host answering to a second domain — see [Two domains on one host](#-two-domains-on-one-host) |
| `NGINX_EXTRA_SERVERS` | *(unset)* | Only for a host answering to a second domain — see [Two domains on one host](#-two-domains-on-one-host) |
| `MARVA_BASE_URL` | `http://localhost/marva/` | `https://bcld.info/marva/` |
| `SINOPIA_BASE_URL` | `http://localhost/sinopia/` | `https://bcld.info/sinopia/` |
| `CORS_ORIGIN` | `*` | Lock to the public origin, e.g. `https://bcld.info` |

> ✅ Leave the internal service URLs as-is — `KEYCLOAK_INTERNAL_URL`,
> `KEYCLOAK_MIDDLEWARE_BASE`, and `AIRFLOW_INTERNAL_URL` use Docker service names
> and don't change between environments.

---

## 🌍 Two domains on one host

Staging answers to **two** names — `stage.bcld.info` and
`bluecore-stage.stanford.edu` — and each has its own Let's Encrypt certificate.
nginx chooses between them by SNI, so both must be configured; a single
certificate cannot cover both names.

**Both domains serve the full stack** — `/api/`, `/workflows/`, `/instances/`,
`/works/`, `/hubs/`, `/profiles/`, `/keycloak/`, `/sinopia/` and `/marva/` all
resolve on either name, because both server blocks include the same
`nginx/site-body.conf`. Upstreams receive the domain the client actually asked
for (`Host` is forwarded as `$host` / `$http_host`, not rewritten).

`HOSTNAME` is still the **canonical** domain: it owns `default_server`, so it
answers requests that arrive without SNI or with an unrecognized `Host`.

Set in the server's `.env`:

| Variable | Set to |
|---|---|
| `HOSTNAME` | The canonical domain, e.g. `stage.bcld.info` |
| `HOSTNAME_ALT` | The secondary domain, e.g. `bluecore-stage.stanford.edu` |
| `NGINX_EXTRA_SERVERS` | `server-alt.conf` |

```bash
# .env on the staging server
HOSTNAME=stage.bcld.info
HOSTNAME_ALT=bluecore-stage.stanford.edu
NGINX_EXTRA_SERVERS=server-alt.conf
```

Both certificate directories must exist on the host before starting:

```bash
ls -d /etc/letsencrypt/live/stage.bcld.info \
      /etc/letsencrypt/live/bluecore-stage.stanford.edu
```

If either is missing, nginx refuses to start rather than serving the wrong
certificate. `./scripts/prod/run` warns up front when the `HOSTNAME` directory
is absent.

> ⚠️ **`HOSTNAME` must be set in `.env`, not left to the machine name.** Bash
> defines `HOSTNAME` automatically, so on the staging box it would otherwise
> resolve to the Stanford machine name and make the *wrong* domain canonical.
> `./scripts/prod/run` reads `.env` first precisely so this stays a deliberate
> choice.

**Single-domain hosts (production) change nothing** — leave `HOSTNAME_ALT` and
`NGINX_EXTRA_SERVERS` unset and `HOSTNAME` keeps working exactly as before.

Verify after deploying:

```bash
# each name is served its own certificate
openssl s_client -connect stage.bcld.info:443 \
  -servername stage.bcld.info </dev/null 2>/dev/null | openssl x509 -noout -subject
openssl s_client -connect bluecore-stage.stanford.edu:443 \
  -servername bluecore-stage.stanford.edu </dev/null 2>/dev/null | openssl x509 -noout -subject

# every route answers on both names
for host in stage.bcld.info bluecore-stage.stanford.edu; do
  for path in /health-check /api/ /workflows/ /instances/ /keycloak/ /sinopia/ /marva/; do
    printf '%s%-14s %s\n' "$host" "$path" \
      "$(curl -s -o /dev/null -w '%{http_code}' "https://$host$path")"
  done
done
```

### ⚠️ Login and CORS are still single-origin

Proxying works on both domains, but several `.env` values name exactly **one**
origin, so any flow that bounces through them lands back on that origin:

| Variable | Effect on the second domain |
|---|---|
| `KC_HOSTNAME` | Keycloak builds its login URLs at this origin, so a login started on the second domain jumps to the canonical one |
| `AIRFLOW_EXTERNAL_URL` | Airflow's post-login redirect returns to the canonical origin |
| `MARVA_REDIRECT_BASE`, `BLUECORE_STACK_KEYCLOAK_REDIRECT_URI` | Marva's auth callback returns to the canonical origin |
| `CORS_ORIGIN` | A browser request from the other origin is refused unless it is allowed too |
| `MARVA_BASE_URL`, `SINOPIA_BASE_URL`, `BLUECORE_URL` | Links the editors build point at the canonical origin |

Unauthenticated routes (`/api/` reads, `/health-check`, static pages) work on
both names as-is. To make **logins** work on both, additionally:

1. **Let Keycloak derive its hostname from the request** — leave `KC_HOSTNAME`
   unset and keep `KC_HOSTNAME_STRICT=false`. `KC_PROXY_HEADERS=xforwarded` is
   already set, so Keycloak honours the forwarded `Host`.
2. **Add both origins to the realm** — every affected client's *Valid redirect
   URIs* and *Web origins* needs the second origin as well. See
   [updating-keycloak-credentials.md](updating-keycloak-credentials.md).
3. **Allow both origins in CORS** — `CORS_ORIGIN` must permit the second origin.

Until those are done, treat the second domain as good for API and health access
and expect interactive logins to settle on the canonical domain.

### How it fits together

| File | Role |
|---|---|
| `nginx/base.conf` | Shared skeleton: one server block plus an `include` for optional extra blocks |
| `nginx/site-body.conf` | Every proxy route and error page, shared by any server block that serves the app |
| `nginx/server.conf` | The canonical HTTPS block (`${HOSTNAME}`, `default_server`) |
| `nginx/server-alt.conf` | The second HTTPS block (`${HOSTNAME_ALT}`), which includes the same site body |
| `nginx/no-extra-servers.conf` | Comment-only placeholder used when `NGINX_EXTRA_SERVERS` is unset |

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

`AIRFLOW_KEYCLOAK_CLIENT_SECRET` is committed to the repo (in `.env` and, frozen as
of the pre-migration snapshot, in `tests/fixtures/keycloak/bluecore-realm-pre-migration.json`),
so treat it as **compromised**: regenerate the `bluecore_workflows` client secret in
Keycloak and update the `.env` value (see
[updating-keycloak-credentials.md](updating-keycloak-credentials.md) for every
other place the development value needs updating too).

`AIRFLOW_WWW_USER_USERNAME` / `AIRFLOW_WWW_USER_PASSWORD` is committed to the repo (in `.env` and, frozen as
of the pre-migration snapshot, in `tests/fixtures/keycloak/bluecore-realm-pre-migration.json`),
so treat those as **compromised**: change the user credentials in Keycloak and update both the `.env` value and re-export the `bluecore` realm settings
"Partial export" to include groups, roles, and clients. Upload the exported file to the server (do not commit to github repository).

🚨 Never reuse a credential that has been in version control. See [updating-keycloak-credentials.md](updating-keycloak-credentials.md).