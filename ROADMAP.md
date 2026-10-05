# Roadmap

Phase-based. Scope and the reasoning behind the stack are in `docs/mvp.md` and `docs/architecture.md`. No ADRs have been written yet.

## Open items

| Item | Status | Blocker |
|---|---|---|
| `docker compose up -d` verified on a clean machine | Blocked | Docker is not installed on the development machine |
| DMC meteorology adapter live | Blocked | DMC API user and token (free registration at climatologia.meteochile.gob.cl) |
| Automatic SENAPRED alerts | Blocked | No public, authorised SENAPRED alert service exists; alerts are entered by the municipality with the official link |
| Licence confirmation for SENAPRED, IDE Chile (MINEDUC, MINSAL), SINCA (MMA), DGA layers | Blocked | Written answer from each data owner, then review by a qualified lawyer (`docs/data-licensing.md`) |
| CSN earthquake catalogue | Blocked | Written approval from CSN for non-academic use; USGS is used meanwhile |
| Process memory measurement for `docs/deployment.md` | Not Started | Needs the Docker run |

## Phase 1: MVP (pilot comuna Lota, CUT 08106)

Status: **In Progress** (only the Docker verification remains)

- Done: research and licensing docs; PostGIS schema with tenants and provenance; source adapters for SENAPRED (comunas, ICFSR, wildfire hazard, tsunami areas and meeting points), IDE Chile geoportal (schools, health facilities), SINCA, DGA stations, USGS, DMC (credential pending); APScheduler worker; hazard modules wildfire, tsunami, flood, air quality, earthquake, meteorology; rules engine with tests; AHORA, RIESGO, PLANIFICAR; uploads (CSV, GeoJSON, KML, KMZ, PDF, TXT, MD); statistics with period, n, source, method, limitations; assistant with tools and full-text RAG, deterministic without an LLM; role reports with PDF; DEMO labelling; compose file, Dockerfiles, Caddy.
- Remaining: run `docker compose up -d` on a machine with Docker and fix what it shows.

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
