# 🏗️ Architecture

`bluecore-stack` is an orchestration repository. Most application code is built in sibling repositories or pulled as published images.

## 🧱 Compose File Layout

| File | Purpose |
|---|---|
| `compose-base.yaml` | Base Airflow cluster, Postgres, Redis, Milvus stack, Blue Core API, Sinopia, Marva, and Marva middleware |
| `compose-dev.yaml` | Local development image stack with Keycloak using its `start-dev` command and Nginx on port 80 |
| `compose-local-dev.yaml` | Local-source overlay with builds, bind mounts, live reload, and profile-gated optional services |
| `compose.yaml` | Production variant with Keycloak `start`, Nginx on port 443, and absolute deployment paths |
| `compose-integration-test.yaml` | Integration test overrides, direct test ports, separate test DB, and lighter service profile defaults |
| `compose-integration-test-dev-mode.yaml` | Integration-test dev overlay with local source mounts and API autoreload |
| `compose-arm64-workflows.yaml` | Apple Silicon override added automatically by scripts |

## 🕸️ Service Topology

```text
Nginx (:80) -> bc_api (:8100)            -> Postgres (airflow/keycloak/bluecore DBs)
            -> Airflow apiserver (:8080) -> Redis (Celery broker)
            -> Keycloak (:8080)          -> Postgres (keycloak DB)
            -> Sinopia (:8004)
            -> Marva (:8080) + marva-keycloak-middleware (:9401)

bc_api + Airflow workers  -> Milvus (:19530) [vector store]
                          -> etcd + MinIO [Milvus backing services]
```

Airflow uses CeleryExecutor with Redis as the broker. DAGs live in the workflows image at `/opt/airflow/ils_middleware/dags`.

The shared Postgres container hosts the `airflow`, `keycloak`, and `bluecore` databases. Integration tests also create `bluecore_integration_test`. Database creation is handled by `scripts/init-multi-postgres-dbs.sh`.

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

In local-source subset mode, some upstreams may intentionally be absent. Nginx still starts; disabled routes return `502`.
