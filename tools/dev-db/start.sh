#!/usr/bin/env bash
set -euo pipefail

ROOT="${DEV_DB_ROOT:-$LOCALAPPDATA/riesgo-comunal}"
PORT="${DEV_DB_PORT:-5440}"

exec "$ROOT/pgsql/bin/postgres.exe" -D "$ROOT/data" -p "$PORT" -c listen_addresses=127.0.0.1
