#!/usr/bin/env bash
set -euo pipefail

PG_SRC="${PG_SRC:-/c/Program Files/PostgreSQL/18}"
POSTGIS_ZIP_URL="${POSTGIS_ZIP_URL:-https://download.osgeo.org/postgis/windows/pg18/postgis-bundle-pg18-3.6.2x64.zip}"
ROOT="${DEV_DB_ROOT:-$LOCALAPPDATA/riesgo-comunal}"
PG_HOME="$ROOT/pgsql"
PG_DATA="$ROOT/data"
PORT="${DEV_DB_PORT:-5440}"
DB_NAME="${DEV_DB_NAME:-riesgo}"
DB_USER="${DEV_DB_USER:-riesgo}"

mkdir -p "$ROOT"

if [ ! -x "$PG_HOME/bin/postgres.exe" ]; then
  mkdir -p "$PG_HOME"
  for part in bin lib share include; do
    cp -r "$PG_SRC/$part" "$PG_HOME/"
  done
fi

if [ ! -f "$PG_HOME/share/extension/postgis.control" ]; then
  zip="$ROOT/postgis-bundle.zip"
  [ -f "$zip" ] || curl -fL --retry 3 -o "$zip" "$POSTGIS_ZIP_URL"
  tmp="$ROOT/postgis-extract"
  rm -rf "$tmp" && mkdir -p "$tmp"
  unzip -q "$zip" -d "$tmp"
  bundle="$(find "$tmp" -maxdepth 1 -mindepth 1 -type d | head -1)"
  cp -r "$bundle"/* "$PG_HOME/"
  rm -rf "$tmp"
fi

if [ ! -f "$PG_DATA/PG_VERSION" ]; then
  "$PG_HOME/bin/initdb.exe" -D "$PG_DATA" -U postgres -A trust -E UTF8 --locale=C >/dev/null
fi

if ! "$PG_HOME/bin/pg_ctl.exe" -D "$PG_DATA" status >/dev/null 2>&1; then
  "$PG_HOME/bin/pg_ctl.exe" -D "$PG_DATA" -o "-p $PORT -c listen_addresses=127.0.0.1" -l "$ROOT/postgres.log" -w start >/dev/null
fi

PSQL=("$PG_HOME/bin/psql.exe" -h 127.0.0.1 -p "$PORT" -U postgres -v ON_ERROR_STOP=1 -qtA)
if [ "$("${PSQL[@]}" -c "select 1 from pg_roles where rolname='$DB_USER'")" != "1" ]; then
  "${PSQL[@]}" -c "create role $DB_USER login password '$DB_USER' superuser"
fi
if [ "$("${PSQL[@]}" -c "select 1 from pg_database where datname='$DB_NAME'")" != "1" ]; then
  "${PSQL[@]}" -c "create database $DB_NAME owner $DB_USER"
fi
"${PSQL[@]}" -d "$DB_NAME" -c "create extension if not exists postgis"
"${PSQL[@]}" -d "$DB_NAME" -c "select postgis_full_version()" | cut -c1-80
echo "DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_USER@127.0.0.1:$PORT/$DB_NAME"
