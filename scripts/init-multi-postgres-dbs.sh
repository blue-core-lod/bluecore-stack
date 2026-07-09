#!/bin/bash
set -e

# Pick which databases to create. If POSTGRES_MULTIPLE_DB is set (e.g. the compose
# files pass "airflow, keycloak, bluecore"), split that comma-separated list into
# the `databases` array; otherwise fall back to default set. This lets
# a single Postgres container host all the logical DBs the stack needs.
if [[ -n "${POSTGRES_MULTIPLE_DB:-}" ]]; then
  IFS=',' read -ra databases <<< "$POSTGRES_MULTIPLE_DB"
else
  databases=(
      keycloak
      bluecore
  )
fi

for db in "${databases[@]}"; do
  # Trim surrounding whitespace (the comma-split above leaves e.g. " keycloak"
  # with a leading space); `xargs` with no command collapses/strips it.
  db="$(echo "$db" | xargs)"
  # Skip empty entries (e.g. a trailing comma or blank field in the list).
  [[ -n "$db" ]] || continue

  echo "Creating database $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
    GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;
EOSQL
done

