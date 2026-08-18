# 🏗️ Architecture

`bluecore-stack` is an orchestration repository. Most application code is built in sibling repositories or pulled as published images.

## 🧱 Compose File Layout

| File | Purpose |
|---|---|
| `compose-base.yaml` | Base Airflow cluster, Postgres, Redis, Blue Core API, Sinopia, Marva, and Marva middleware |
| `compose-dev.yaml` | Local development image stack with Keycloak using its `start-dev` command and Nginx on port 80 |
| `compose-local-dev.yaml` | Local-source overlay with builds, bind mounts, live reload, and profile-gated optional services |
| `compose.yaml` | Production variant with Keycloak `start`, Nginx on port 443, and absolute deployment paths |
| `compose-integration-test.yaml` | Integration test overrides, direct test ports, separate test DB, and lighter service profile defaults |
| `compose-integration-test-dev-mode.yaml` | Integration-test dev overlay with local source mounts and API autoreload |
| `compose-arm64-workflows.yaml` | Apple Silicon override added automatically by scripts |

## 🕸️ Service Topology

```text
Nginx (:80) -> bc_api (:8100)            -> Postgres (airflow/keycloak/bluecore/jupyterhub DBs)
            -> Airflow apiserver (:8080) -> Redis (Celery broker)
            -> Keycloak (:8080)          -> Postgres (keycloak DB)
            -> Sinopia (:8004)
            -> Marva (:8080) + marva-keycloak-middleware (:9401)
            -> JupyterHub (:8000)        -> Postgres (jupyterhub DB)
                                         -> Docker socket -> per-user "jupyter-<user>" containers
```

Airflow uses CeleryExecutor with Redis as the broker. DAGs live in the workflows image at `/opt/airflow/ils_middleware/dags`.

The shared Postgres container hosts the `airflow`, `keycloak`, `bluecore`, and `jupyterhub` databases. Integration tests also create `bluecore_integration_test`. Database creation is handled by `scripts/init-multi-postgres-dbs.sh`.

## 🚦 Nginx Routing

All local browser traffic enters through Nginx.

| Route | Upstream |
|---|---|
| `/api/` | `bc_api:8100` |
| `/instances/`, `/works/` | `bc_api:8100` |
| `/workflows/` | `airflow-apiserver:8080` |
| `/keycloak/` | `keycloak:8080` |
| `/sinopia/` | `sinopia:8004` |
| `/marva/` | `marva:8080` |
| `/marva/util/` | `marva-keycloak-middleware:9401` |
| `/jupyter/` | `jupyterhub:8000` |

In local-source subset mode, some upstreams may intentionally be absent. Nginx still starts; disabled routes return `502`.

## 📓 JupyterHub

`jupyterhub` (`jupyterhub/Dockerfile`) is built from the stock JupyterHub image plus `dockerspawner`,
`oauthenticator`, and `psycopg2-binary`. It authenticates against Keycloak's `bluecore_jupyterhub` client
(see [keycloak.md](keycloak.md)) and stores Hub state in the shared Postgres `jupyterhub` database, so the
`jupyterhub` container itself is disposable.

Each login spawns a dedicated single-user container (`jupyterhub/singleuser/Dockerfile`, built from
`quay.io/jupyter/scipy-notebook` with `training/pyproject.toml`'s dependencies and `training/notebooks/`
baked in) via `DockerSpawner`. This requires mounting `/var/run/docker.sock` into the `jupyterhub`
container, which is effectively root-equivalent access to the Docker host — the same tradeoff any
docker-outside-of-docker setup makes. There is no per-user CPU/memory limit yet; treat this as a
prototype, not a hardened multi-tenant deployment.

The single-user image is built by its own `jupyterhub-singleuser` compose service, gated behind a
`profiles: ["build-only"]` that's never active — a normal `up` never starts or builds it. Build/refresh it
explicitly (`docker compose build jupyterhub-singleuser`) whenever `jupyterhub/singleuser/` or
`training/` changes; DockerSpawner then picks it up on the next spawn via `JUPYTERHUB_SINGLEUSER_IMAGE`.

`scripts/init-multi-postgres-dbs.sh` (which creates the `jupyterhub` database) only runs the first time a
Postgres volume initializes, so adding this feature to an already-existing local Postgres volume requires
creating the `jupyterhub` database by hand — see [local-development.md](local-development.md).

**Known rough edge:** `DockerSpawner.network_name` (env var `JUPYTERHUB_DOCKER_NETWORK`) must match the
Docker network this compose project actually creates, which Compose derives from the project name (by
default, the checkout directory's name). If notebooks can't reach `bc_api`/Keycloak/etc., check
`docker network ls` and correct `JUPYTERHUB_DOCKER_NETWORK` in `.env`. A follow-up should replace this
with an explicit `networks:` block so the name is stable across checkouts.
