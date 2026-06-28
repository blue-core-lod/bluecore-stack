# 🧱 Developing bluecore-models

`bluecore-models` is source code used by the API, Airflow/workflows tasks, and 
Alembic migrations. It is not a standalone service.

In local source mode, `scripts/dev/run` mounts the sibling `../bluecore-models`
checkout into the API and Airflow containers.

## 🔁 Live Code Changes

- API: model-code changes reload live.
- Workflows/Airflow: imports local model code, but restart the local stack after 
model-code changes so Airflow processes pick them up.

## 🗄️ Migrations

When you change SQLAlchemy models and need a migration, keep the stack running 
so Postgres is available, then run:

```bash
cd ../bluecore-models
uv run alembic revision --autogenerate -m "describe the model change"
```

Review the generated migration under:

```text
../bluecore-models/src/bluecore_models/migrations/versions/
```

Then restart the API so startup applies the new local migration:

```bash
./scripts/dev/run
# OR
./scripts/dev/run --api
```

If your models checkout is somewhere else, set `LOCAL_BLUECORE_MODELS_DIR` before
running `scripts/dev/run`, or update the default in `scripts/dev/local-repo-paths`.
