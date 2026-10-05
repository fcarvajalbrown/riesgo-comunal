# MVP

## Pilot comuna

**Lota (Biobío), CUT 08106.** Chosen from evidence: it has the highest value of SENAPRED's Índice Comunal de Factores Subyacentes del Riesgo (ICFSR 0.8163, level ALTO, application year 2025) among the 345 comunas in the `Factor_IC_FSR` layer. The ICFSR comes from a municipal self-diagnosis of 41 variables in four dimensions (Ordenamiento Territorial; Cambio Climático y Recursos Naturales; Condiciones Socioeconómicas y Demográficas; Gobernanza), per SENAPRED's "Factores Subyacentes" page, so it measures underlying conditions, not hazard intensity. It is coastal (tsunami evacuation layers exist), sits in a wildfire-recurrence area, and has SINCA stations nearby ("Lota urbana", "Lota rural"). The platform loads official data for all comunas, so any other comuna becomes a tenant by configuration.

## In scope

1. Municipality configuration: tenant, boundary from SENAPRED DPA, branding, enabled hazards, thresholds.
2. Interactive map (MapLibre) with plain-language legends, source and timestamp per layer.
3. Ingestion of real official sources on a schedule: SENAPRED ArcGIS (comunas, ICFSR, wildfire hazard, tsunami evacuation areas and meeting points, schools, health centres), SINCA realtime air quality, DGA station catalogue; USGS earthquakes as a labelled complementary source. DMC adapter ready, enabled by credential.
4. AHORA: current situation per hazard module, observations with timestamps and validation status, recent earthquakes, alerts (manual entry with source URL until an authorised feed exists).
5. RIESGO: per hazard level for comuna and sectors with explanation, exposed facilities and assets.
6. PLANIFICAR: historical statistics (earthquakes by year and magnitude band, municipal incidents by year, hazard, sector, month) with period, sample size, source, method, limitations; trend test only when n is sufficient; ICFSR context.
7. Municipal data upload: CSV (lat/lon), GeoJSON, KML, PDF documents. Stored per tenant, labelled municipal.
8. Rules risk engine with per-comuna thresholds and tests.
9. AI assistant (Spanish) with tools and document search; deterministic mode without an LLM.
10. Provenance: "¿De dónde salió este dato?" on every value.
11. Role views: Alcalde/Alcaldesa, Emergencias, SECPLAN, Comunicaciones (+ admin).
12. Role reports in JSON/HTML view and PDF.
13. Docker Compose deployment with Caddy.

## Out of scope

Citizen reporting, citizen portal UI (API ready), native apps, social media integrations, Keycloak/SSO, Kubernetes, raster sources, vector tile server, SHP/GPKG upload (needs GDAL; planned), live SENAPRED alert feed (no authorised API).

## Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Research and docs | data-sources, data-licensing, architecture, mvp, risk-model committed |
| M1 | Schema + ingestion | migrations run; adapters ingest real data for the pilot; provenance populated |
| M2 | Hazard modules + risk engine | levels per hazard for comuna and cells; rule tests pass |
| M3 | API modes, uploads, statistics | AHORA/RIESGO/PLANIFICAR endpoints; upload of CSV/GeoJSON/KML/PDF |
| M4 | Assistant and reports | tool-based answers with sources; PDF reports per role |
| M5 | Web app | role views, map, assistant, reports, uploads, sources screen |
| M6 | Docker | `docker compose up -d` on a clean machine brings up a working stack |

## Dependencies

- Network access to `services5.arcgis.com`, `sinca.mma.gob.cl`, `rest-sit.mop.gob.cl`, `earthquake.usgs.gov`, `tiles.openfreemap.org`.
- Optional: DMC user and token; an OpenAI-compatible LLM endpoint.

## Risks

| Risk | Mitigation |
|---|---|
| Commercial reuse of SENAPRED, SINCA, DGA data not confirmed | Written confirmation before first sale (see `data-licensing.md`); adapters carry flags |
| SINCA endpoint is undocumented and may change | Single adapter; failures surface in "Fuentes" with last success time |
| No live official alert feed | Manual official-alert entry with source URL; UI states the limitation |
| Users read a derived level as official | Persistent "Cálculo de la plataforma" labels, disclaimer, tests on wording |
| LLM invents content | Tools-only answering, sources appended from tool outputs, deterministic fallback |
| SENAPRED schools/health layers last edited 2022 | Shown with their edit date; municipalities can upload current lists |

## Technical unknowns

- Whether SENAPRED will grant an authorised alert feed.
- DMC response shapes beyond the documented examples (verified once a key exists).
- Performance of national layers in a single comuna query on small servers (mitigated by comuna clipping at ingestion).
