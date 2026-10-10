# Riesgo Comunal

Municipal risk intelligence platform for Chilean comunas.

**It keeps working when one source fails.** The platform reads alerts and data from several independent sources on its own schedule, stores what each one last delivered, and shows on the staff dashboard and on the public page which sources are working, which have failed and which have stopped sending new data, with the time of the last data received from each. If SENAPRED's page stops responding, the screen says so, keeps showing the alerts and data already received, and lists the sources that are still running.

Alert sources currently read automatically:

- SENAPRED public alerts page (`senapred.cl/alertas`), every 10 minutes
- Dirección Meteorológica de Chile official CAP feed (warnings, alerts and alarms)
- SHOA tsunami bulletins from the SNAM public table (`snamchile.cl`), every 5 minutes
- GDACS global disaster alerts (earthquakes, floods, wildfires, volcanoes) affecting Chile, as an international backup
- NOAA Pacific and National Tsunami Warning Center messages (PTWC/NTWC) for the South American Pacific coast, as an international backup

International backups are labelled as such and never replace SENAPRED or SHOA warnings.

It collects official public data (SENAPRED, IDE Chile, SINCA, DGA, USGS, DMC, INE Censo 2024, MOP Vialidad), combines it with each municipality's own data, and answers three questions in Spanish: what is happening now (AHORA), which areas are vulnerable (RIESGO), and what history and priorities the comuna has (PLANIFICAR). Every figure links back to its source.

It is a decision-support tool. Levels shown are platform calculations from official data, not official alerts or assessments. Official alerts come from SENAPRED and the competent authorities.

## What it does

- Ingests official layers on a schedule through source adapters; the browser and the assistant read only the platform database.
- Hazard modules per comuna (wildfire, tsunami, flood, air quality, earthquake, meteorology, SENAPRED alerts) with a transparent rules engine and configurable thresholds; each hazard zone and sector also reports people, people aged 60 or over and dwellings inside it, estimated from INE Censo 2024 blocks, plus MOP bridges and km of national road network.
- Map with layer, place and address search (address search runs the same place check as the public page) and a side-by-side view to compare two hazard layers; role-based screens and reports (Alcalde, Emergencias, SECPLAN, Comunicaciones) with PDF export.
- Uploads of municipal data: CSV, GeoJSON, KML, KMZ, zipped Shapefile, GeoPackage, GeoTIFF, photos, PDF, TXT, MD.
- Public residents' page at `/c/{slug}`: official alerts in force, a per-hazard summary, an address or location check (tsunami evacuation area and nearest meeting point, wildfire recurrence, weather warnings), emergency numbers and official links. No login.
- Statistics with period, sample size, source, method and limitations.
- Spanish assistant that answers from platform tools and municipal documents with citations; works without an LLM and with any OpenAI-compatible endpoint.
- Multi-tenant: one installation, many comunas, data isolated per municipality.

## Public Maule site

A static public site for the 30 comunas of the Región del Maule, an initiative of the office of senator Paulina Vodanovic, is live at https://synterra.cl/maule/. `tools/static-site/build.py` generates it from the same database and public API functions; the `static-site` GitHub workflow rebuilds it about every 15 minutes, triggered by a Hostinger cron. Each comuna page shows one row per hazard with the official alert (SENAPRED, DMC, SHOA) beside "Nuestro análisis", a card that cross-checks independent sources:

- Sismos: USGS and EMSC (which carries the CSN's solutions).
- Incendios: INPE and NASA FIRMS satellite fire detections.
- Crecidas de ríos: the Copernicus GloFAS 51-member river forecast against each river's 2, 5 and 20-year flows (`tools/river-points`).
- Mar y tsunami: IOC/UNESCO tide gauges at Constitución and Boyeruca and NOAA DART buoys.
- Tiempo: three weather models (ECMWF, GFS, ICON) through Open-Meteo.

Rows with an official alert come first, then by level, then by a monthly season signal (SPI and Canadian FWI from ERA5, `tools/season`). The footer links to "Cómo lo calculamos", "Sobre esta iniciativa" and "Prensa". Audience and readability rules are in `docs/ux.md`.

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
| `docs/ux.md` | screens, interface rules, audience of the Maule site and layout research |
| `docs/municipal-customization.md` | onboarding a comuna, configuration, extending modules and sources |
| `docs/security.md` | security controls in place and pending |
| `docs/deployment.md` | install, resources, backups, updates |

## Stack

PostgreSQL with PostGIS (and pgvector when available), FastAPI, APScheduler worker, Next.js with MapLibre GL, Caddy, Docker Compose. Reasons for each choice: `docs/architecture.md`.
