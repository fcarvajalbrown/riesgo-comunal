#!/usr/bin/env bash
set -uo pipefail

repo="${1:?usage: api-check.sh <repo-dir> [https-port]}"
port="${2:-8443}"
cd "$repo"
pw=$(docker compose logs bootstrap 2>&1 | grep -o '"emergencias@demo.lota.cl": "[^"]*"' | sed 's/.*: "//; s/"$//')
B="https://localhost:$port/api"
tok=$(curl -sk -X POST $B/auth/login -H 'content-type: application/json' -d "{\"email\":\"emergencias@demo.lota.cl\",\"password\":\"$pw\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
H="Authorization: Bearer $tok"
for p in me ahora riesgo planificar layers sources hazards alerts uploads documents reports reports/emergencias layers/wildfire_hazard "search?q=escuela"; do
  echo "$p $(curl -sk -o /dev/null -w '%{http_code} %{size_download}' -H "$H" "$B/$p")"
done
echo "audit(expect 403) $(curl -sk -o /dev/null -w '%{http_code}' -H "$H" $B/audit)"
curl -sk -H "$H" $B/reports/alcalde/pdf -o "${TMPDIR:-/tmp}/report.pdf"; echo "pdf $(head -c 5 "${TMPDIR:-/tmp}/report.pdf") $(stat -c %s "${TMPDIR:-/tmp}/report.pdf")"
curl -sk -H "$H" -H 'content-type: application/json' -X POST $B/assistant -d '{"question":"¿Qué escuelas están en zona de tsunami?","audience":"ejecutivo"}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["mode"], d["tools"], len(d["sources"])); print(d["answer"][:300])'
curl -sk -H "$H" $B/riesgo | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(a["hazard"], a["level"]) for a in d["assessments"]]'
