#!/bin/sh
# Runs once, on first initialisation of the Postgres data directory.
# Creates the login role the application connects as. It is deliberately not a
# superuser and does not own the tables, so row-level security applies to it.
set -e
psql -v ON_ERROR_STOP=1 -v pw="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE aegle_app LOGIN PASSWORD :'pw';
SQL
