# Riesgo Comunal

Municipal risk intelligence platform for Chilean comunas. It collects official public data (SENAPRED, IDE Chile, SINCA, DGA, USGS, DMC), combines it with each municipality's own data, and answers three questions in Spanish: what is happening now (AHORA), which areas are vulnerable (RIESGO), and what history and priorities the comuna has (PLANIFICAR). Every figure links back to its source.

It is a decision-support tool. Levels shown are platform calculations from official data, not official alerts or assessments. Official alerts come from SENAPRED and the competent authorities.

## What it does

- Ingests official layers on a schedule through source adapters; the browser and the assistant read only the platform database.
- Hazard modules per comuna (wildfire, tsunami, flood, air quality, earthquake, meteorology, SENAPRED alerts) with a transparent rules engine and configurable thresholds.
- Map, role-based screens and reports (Alcalde, Emergencias, SECPLAN, Comunicaciones) with PDF export.
- Uploads of municipal data: CSV, GeoJSON, KML, KMZ, zipped Shapefile, GeoPackage, GeoTIFF, photos, PDF, TXT, MD.
- Public residents' page at `/c/{slug}`: official alerts in force, a per-hazard summary, an address or location check (tsunami evacuation area and nearest meeting point, wildfire recurrence, weather warnings), emergency numbers and official links. No login.
- Statistics with period, sample size, source, method and limitations.
- Spanish assistant that answers from platform tools and municipal documents with citations; works without an LLM and with any OpenAI-compatible endpoint.
- Multi-tenant: one installation, many comunas, data isolated per municipality.

## Run with Docker

```bash
cp .env.example .env    # set passwords, JWT_SECRET, TENANT_CUT, TENANT_SLUG, ADMIN_EMAIL, ADMIN_PASSWORD, SITE_ADDRESS
docker compose up -d --build
```

Open `https://<SITE_ADDRESS>`. Details, sizing, backups and updates: `docs/deployment.md`.

## Develop without Docker

See "Local development" in `docs/deployment.md`. Tests:

```bash
cd backend && uv run pytest
cd frontend && pnpm test && pnpm typecheck
```

## Documentation

| Document | Content |
|---|---|
| `ROADMAP.md` | phases, open items and blockers |
| `docs/mvp.md` | MVP scope and pilot comuna |
| `docs/architecture.md` | components, data model, stack choices |
| `docs/data-sources.md` | every source evaluated, with status |
| `docs/data-licensing.md` | what each source's terms say, open licence questions |
| `docs/risk-model.md` | hazard modules, rules, thresholds, labels |
| `docs/ai-rag.md` | assistant, tools, document search |
| `docs/api.md` | HTTP API |
| `docs/ux.md` | screens and interface rules |
| `docs/municipal-customization.md` | onboarding a comuna, configuration, extending modules and sources |
| `docs/security.md` | security controls in place and pending |
| `docs/deployment.md` | install, resources, backups, updates |

## Stack

PostgreSQL with PostGIS (and pgvector when available), FastAPI, APScheduler worker, Next.js with MapLibre GL, Caddy, Docker Compose. Reasons for each choice: `docs/architecture.md`.
