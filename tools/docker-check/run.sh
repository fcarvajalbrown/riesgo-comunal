#!/usr/bin/env bash
set -euo pipefail

repo="${1:?usage: run.sh <repo-dir> [https-port]}"
port="${2:-8443}"
cd "$repo"

docker compose up -d

for _ in $(seq 1 120); do
  state=$(docker compose ps -a bootstrap --format '{{.State}} {{.ExitCode}}')
  case "$state" in exited*) break ;; esac
  sleep 5
done
echo "bootstrap: $state"
docker compose logs bootstrap 2>&1 | grep -viE 'password|contrase|clave' | tail -30
[ "$state" = "exited 0" ] || exit 1

for _ in $(seq 1 60); do
  health=$(docker compose ps api --format '{{.Health}}')
  [ "$health" = "healthy" ] && break
  sleep 5
done
echo "api: $health"

docker compose ps --format '{{.Service}} {{.State}} {{.Status}}'

echo "health: $(curl -sk "https://localhost:$port/api/health")"
echo "web: $(curl -sk -o /dev/null -w '%{http_code}' "https://localhost:$port/")"
echo "public: $(curl -sk "https://localhost:$port/api/public/${TENANT_SLUG:-lota}/resumen" | head -c 400)"
