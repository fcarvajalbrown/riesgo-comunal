# Roadmap

Phase-based. Scope and the reasoning behind the stack are in `docs/mvp.md` and `docs/architecture.md`. No ADRs have been written yet.

## Open items

| Item | Status | Blocker |
|---|---|---|
| DMC meteorology adapter live | Blocked | DMC API user and token (free registration at climatologia.meteochile.gob.cl) |
| Official SENAPRED alert feed | Blocked | Alerts are read automatically from the public page senapred.cl/alertas (working); an official feed or written OK from SENAPRED is still pending |
| Licence confirmation for SENAPRED, IDE Chile (MINEDUC, MINSAL), SINCA (MMA), DGA, MOP Vialidad layers | Blocked | Written answer from each data owner, then review by a qualified lawyer (`docs/data-licensing.md`) |
| CSN earthquake catalogue | Blocked | Written approval from CSN for non-academic use; USGS is used meanwhile |
| Maule region install (30 tenants) on a VPS | In Progress | Code, backup alert sources, sector batching and deploy kit merged on main (113 tests pass). The existing IONOS VPS 74.208.35.90 was ruled out: it runs the VDP OOB responder on port 80 and has 1.8 GB RAM. A dedicated IONOS VPS L+ (4 vCores, 8 GB, Ubuntu 24.04) is being ordered. Domain at IONOS not bought yet; the site starts on plain HTTP at the new IP. Container RAM for 31 tenants still unmeasured |
| Public static site for Maule (senator's initiative) | In Progress | Live on GitHub Pages, rebuilt every 15 min by `.github/workflows/static-site.yml`; senator's banner uses her office's brand kit (`assets/graficas-vodanovik/`: navy #263d55, red #a41111, white logo, navy texture with the Maule silhouette); the banner is navy rather than red because #a41111 is almost the Crítico level red #b42318. The link preview card `og-maule.jpg` uses the same kit and stays a JPEG under 300 KB because WhatsApp drops larger preview images. Target host later: Hostinger Business (static sites only, no web apps). Next: bring the interactive hazard maps of the main app into the static pages |

## Full-spec gap list

The MVP list of the original specification is complete. These items from the rest of that specification are not built yet. Each one moves to Done here when it is built, tested and documented.

| # | Area | Gap | Status | Blocker |
|---|---|---|---|---|
| G1 | Research | Sources not yet researched: CONAF, MINVU, Dirección de Obras Hidráulicas, Ministerio de Transportes, datos.gob.cl, regional government datasets, municipal open-data portals, NOAA | Not Started | |
| G2 | Research | Per-source fields missing from `docs/data-sources.md`: WMS/WFS/WMTS availability, rate limits, geographic resolution, reliability, known limitations as separate columns | Not Started | |
| G3 | Exposure | Population exposed per hazard zone and sector (INE census) | Done | INE Censo 2024 blocks, area-weighted estimate |
| G4 | Exposure | Roads and bridges exposed | Done | Official MOP Vialidad network and bridge inventory instead of OpenStreetMap; urban streets not covered |
| G5 | Hazards | Volcanic module (SENAPRED layer, SERNAGEOMIN alert levels) | Not Started | |
| G6 | Hazards | Landslide / remoción en masa module | Not Started | Official source to be found |
| G7 | Hazards | Coastal surge / marejadas module | Not Started | Official machine-readable source to be found |
| G8 | Hazards | Drought module (DGA water-scarcity decrees) | Not Started | |
| G9 | Hazards | Official DMC warnings (all weather hazards): Done via the public CAP feed. Station observations (rain, wind, temperature): Blocked | Blocked (observations only) | DMC credential |
| G10 | Hazards | Wildfire activity and smoke (NASA FIRMS hotspots, CONAF if available) | Blocked | FIRMS MAP_KEY (free registration) |
| G11 | Hazards | River conditions (DGA levels and flows) | Not Started | Only web pages verified so far |
| G12 | Statistics | Incidents by sector, seasonality, recurrence, affected area | Not Started | |
| G13 | Reports | Maps inside PDF reports; historical comparisons | Not Started | |
| G14 | Residents | Public portal page: what is happening, am I near an affected area, official links | Done | `/c/{slug}` |
| G15 | Map | Address search, comparing two hazards side by side | Done | Staff map: Enter searches addresses and runs the place check; "Comparar amenazas" shows two synced maps |
| G16 | Municipal data | Zipped Shapefile, GeoPackage, GeoTIFF, photos, emergency contacts and personnel, inspection records | Done | |
| G17 | Customisation | Logo, brand colour, terminology overrides, emergency contacts in the UI | Done | |
| G18 | Assistant | Report generation on request; hazard and housing overlap question | Not Started | G3 for housing |
| G19 | Security | Row-level security, encrypted secrets at rest, structured logging, monitoring of ingestion failures | Not Started | |
| G20 | Testing | Frontend unit tests (Vitest) and end-to-end tests (Playwright) | Not Started | New dependencies (approval) |

## Phase 1: MVP (pilot comuna Lota, CUT 08106)

Status: **Done**

- Done: research and licensing docs; PostGIS schema with tenants and provenance; source adapters for SENAPRED (comunas, ICFSR, wildfire hazard, tsunami areas and meeting points), IDE Chile geoportal (schools, health facilities), SINCA, DGA stations, USGS, DMC (credential pending); APScheduler worker; hazard modules wildfire, tsunami, flood, air quality, earthquake, meteorology; rules engine with tests; AHORA, RIESGO, PLANIFICAR; uploads (CSV, GeoJSON, KML, KMZ, PDF, TXT, MD); statistics with period, n, source, method, limitations; assistant with tools and full-text RAG, deterministic without an LLM; role reports with PDF; DEMO labelling; compose file, Dockerfiles, Caddy.
- Verified: `docker compose up -d` on a clean clone (Docker Engine 29.8 in WSL Ubuntu 22.04) brings up all services; bootstrap, worker ingestion of every source except DMC (no credential), authenticated API, PDF and assistant work through Caddy (`tools/docker-check/run.sh`, `tools/docker-check/api-check.sh`).

## Phase 2: Pilot hardening

Status: **Not Started**

- PostgreSQL row-level security as a second tenant barrier.
- Password reset, lockout, MFA.
- Shapefile and GeoPackage uploads (GDAL).
- Alerting on ingestion failures.
- Accessibility audit (keyboard, screen reader), mobile layout.
- Self-hosted basemap tiles for offline installs.
- DMC observations and forecasts once the credential exists; rainfall thresholds validated with the municipality.

## Phase 3: More comunas and hazards

Status: **Not Started**

- Onboard further comunas, starting from the highest ICFSR values (the criterion used to pick Lota in `docs/mvp.md`).
- Hazard layers evaluated but not used in the MVP (for example SENAPRED's volcanic hazard layer, see `docs/data-sources.md`) as modules per comuna.
- NASA FIRMS hotspots as satellite detections (labelled as not official confirmation).
- Vector tiles (Martin) if national layers are rendered.
- SSO for municipalities with an institutional identity provider.
