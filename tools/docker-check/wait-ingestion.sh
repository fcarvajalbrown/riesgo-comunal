#!/usr/bin/env bash
set -euo pipefail

repo="${1:?usage: wait-ingestion.sh <repo-dir> [timeout-seconds]}"
limit="${2:-900}"
cd "$repo"

sql() { docker compose exec -T db psql -U riesgo -d riesgo -Atc "$1"; }

start=$(date +%s)
while :; do
  running=$(sql "select count(*) from ingestion_job where status = 'running'")
  pending=$(sql "select count(*) from source s where s.enabled and not exists (select 1 from ingestion_job j where j.source_key = s.key and j.status <> 'running')")
  elapsed=$(( $(date +%s) - start ))
  [ "$running" = "0" ] && [ "$pending" = "0" ] && break
  if [ "$elapsed" -ge "$limit" ]; then
    echo "timeout after ${elapsed}s: running=$running pending=$pending"
    break
  fi
  sleep 15
done
echo "first ingestion pass: ${elapsed}s"
sql "select distinct on (source_key) source_key, status, record_count, jsonb_array_length(warnings), coalesce(left(error, 160), '') from ingestion_job order by source_key, started_at desc"
