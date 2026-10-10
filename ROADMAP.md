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
| Per-hazard scorecards ("Nuestro análisis") | In Progress | Owner decision: the open licence questions on the scorecard sources (CSN solutions via EMSC, IOC tide gauges, Open-Meteo free API, INPE) are not pursued at this site's scale; do not raise them again. The site's differentiator when SENAPRED is down: one scorecard per hazard showing a composite indicator produced by fusing several sources from several countries, with the sources behind each score one click away. Public label "Nuestro análisis"; the terms composite indicator, data fusion and multi-model consensus belong in the methodology. Done: expandable cards with evidence, seasonal trim (tsunami coastal only, air quality April-September or when high), felt quakes only (M4.5+ within 200 km, 24 h; provisional threshold). Coastal self-evacuation rule (SENAPRED wording) on the quake card of coastal comunas. EMSC added next to USGS: EMSC republishes the Chilean CSN's own solutions (author CSN), and on the 30 days to 10 October 2026, 39 of 61 Chilean quakes of M4+ appeared in both catalogues, matched within 90 s and 100 km, magnitudes mostly within 0.1. INPE Queimadas added (South America daily CSV filtered to Chile; INPE's municipio field holds the Chilean province, so comunas come from our boundaries) and a new "Focos de incendio detectados" card, the site's first active-fire element: Moderado on any detection in the comuna in 24 h, Alto when two satellite passes or two sources see the same spot within 1 km, never Crítico without an official alert. On 9 October 2026 it would have shown Alto in Vichuquén (TERRA and NOAA-20 passes on one spot); ground truth unknown. NASA FIRMS added from its public 24-hour South America CSVs (VIIRS NOAA-20, NOAA-21, Suomi NPP and MODIS), which need no MAP_KEY; both Vichuquén spots were seen independently by INPE and FIRMS. Persistent industrial heat sources (Caletones/El Teniente and Chuquicamata appear in the files, outside Maule) are not filtered yet. Observed weather skipped for now: DMC publishes hourly SYNOP on WIS2 under the core data policy, but only as MQTT notifications (globalbroker.meteo.fr and others, topic cache/a/wis2/cl-meteochile/data/core/weather/surface-based-observations/synop) pointing to BUFR files, which needs an always-on subscriber and a BUFR decoder, so it waits for the VPS; the free aviationweather.gov METAR feed has only Curicó (SCIC, automatic, no present-weather group) inside Maule. IOC/UNESCO tide gauges added for Constitución (const) and Boyeruca (boye), per-minute data from SHOA-operated stations, non-commercial terms: new coastal-only card "Mar y tsunami ahora"; a calm day oscillates at most 0.13-0.22 m after removing the tide with a 31-minute running mean, so a gauge is flagged as anomalous (Alto) only when all its sensors pass 0.5 m in the last hour; detection lags about 15 minutes because the running mean is centred. Open-Meteo multi-model added: ECMWF IFS, GFS and ICON fetched separately (models=ecmwf_ifs025,gfs_seamless,icon_seamless); the forecast card keeps its level from the blended forecast and adds how many of the three models reach the heavy-rain threshold. Each cross-checked card (quakes, fire, forecast, sea level) shows a short "N de M fuentes" line under its headline. Layout decided by the owner (in progress): on the comuna page each hazard is one row, official alert on the left ("Sin alerta oficial" when none) and our card on the right, stacked official-first on a phone, each alert shown once (the separate rain card and the alert list go away). Alert-to-card mapping: tsunami to Tsunami and Mar y tsunami ahora; incendio to Incendio forestal and Focos de incendio; crecida, inundación and lluvia to Inundación y anegamiento; remoción en masa and aluvión also to Inundación y anegamiento for now (no second landslide source yet; NASA LHASA v2 is the only candidate found); sismo to Sismos recientes; viento, tormenta, nieve, helada, calor and general meteorological alerts to Condiciones meteorológicas; marejada and tsunami on a comuna without those cards get their own row with "Todavía no tenemos análisis propio para esta amenaza"; volcanic and unclassified alerts go in an "Otras alertas oficiales" block at the end. Readability rules for the audience are in docs/ux.md. Next: filter persistent industrial heat sources from fire detections; heat and volcanic cards |
| Public static site for Maule (senator's initiative) | In Progress | Live at synterra.cl/maule (rsync to Hostinger) and on GitHub Pages, built by `.github/workflows/static-site.yml`. The workflow's 15-minute cron does not deliver 15 minutes: GitHub ran it only every 4 to 7 hours in 7-10 October, so the live data can be hours old. Each run also starts from an empty database (region setup 1.5 min, full ingest with backfill 7 min, about 11 min per run). Fixed with a Hostinger cron (`*/15 * * * *`, `/usr/bin/php ~/riesgo-comunal/trigger_static_site.php`, script in `deploy/hostinger/`) that starts the workflow through the GitHub API with a fine-grained token kept in `~/riesgo-comunal/github-token` (repository riesgo-comunal, Actions read and write); a run takes about 9 minutes; senator's banner uses her office's brand kit (`assets/graficas-vodanovik/`: navy #263d55, red #a41111, white logo, navy texture with the Maule silhouette); the banner is navy rather than red because #a41111 is almost the Crítico level red #b42318. The link preview card `og-maule.jpg` uses the same kit and stays a JPEG under 300 KB because WhatsApp drops larger preview images. Target host later: Hostinger Business (static sites only, no web apps). Next: bring the interactive hazard maps of the main app into the static pages |

## Research: which hazards matter for Maule in the 2026-27 season, and multi-country backup sources

Web research, 24 searches. Every point has its source; "not found" means the search did not confirm it.

### Seasonal relevance of each element

| Element | Finding | Verdict |
|---|---|---|
| Wildfire | CONAF asked for a Preventive Emergency State from October 2026 to May 2027, Atacama to Magallanes; El Niño raises danger, temperature peak January-February ([Cámara](https://www.camara.cl/cms/2026/09/03/comision-analizo-programa-de-proteccion-contra-incendios-forestales-2026-2027/), [Diario Oficial](https://www.diariooficial.interior.gob.cl/publicaciones/2026/06/26/44485/01/2830725.pdf)) | Top element November to March |
| Floods / crecidas | NOAA keeps the El Niño advisory, 97 % chance it lasts to autumn 2027; DMC projects above-normal rain for October-December in central and centre-south Chile ([Meteored](https://www.meteored.cl/noticias/prediccion/dmc-anticipa-un-cierre-de-2026-mas-lluvioso-en-chile-central-y-con-maximas-bajo-lo-normal.html), [Radio Agricultura](https://www.radioagricultura.cl/noticias/nacional/dmc-anticipa-un-trimestre-mas-lluvioso-en-chile-precipitaciones-sobre-lo-normal-se-extenderian-hasta-primavera_20260805/)). The Mataquito overflowed at Licantén in July 2026 ([El Desconcierto](https://eldesconcierto.cl/actualidad/licanten-otra-vez-amenazada-desborde-rio-mataquito-senapred-decreta-alerta-roja-y-evacua-personas-n5460811)); red alert in Cauquenes, Parral and Sagrada Familia in August 2026 ([BioBioChile](https://www.biobiochile.cl/noticias/nacional/chile/2026/08/02/balance-de-senapred-por-sistema-frontal-2-fallecidos-desbordes-de-rios-y-mas-de-6-mil-aislados.shtml)) | Stays important through spring |
| Extreme heat | DMC heat alerts repeatedly name interior Maule as the hottest area (December 2024; January 2026 with 37 °C forecast for Talca) ([The Clinic](https://www.theclinic.cl/2024/12/23/ola-de-calor-se-posara-sobre-nueve-regiones-en-navidad/), [El Dínamo](https://www.eldinamo.cl/pais/2026/01/09/cuales-son-las-regiones-para-las-que-se-alerto-por-ola-de-calor-termometro-podria-superar-los-38c/)) | Missing; needed November to March |
| Marejadas | Armada warnings reached Constitución in February and July 2026 ([Radio Agricultura](https://www.radioagricultura.cl/noticias/nacional/emiten-avispo-por-marejadas-en-el-pais-revisa-las-zonas-afectadas_20260210/), [24horas](https://www.24horas.cl/regiones/zona-centro/maule/sistema-frontal-ingreso-por-la-costa-al-maule)) | Missing; coastal comunas only |
| Volcanic | Planchón-Peteroa and Laguna del Maule back to green technical alert in April 2026; swarm of over 150 events at Laguna del Maule in May 2026 ([24horas](https://www.24horas.cl/regiones/zona-centro/maule/senapred-mantiene-alerta-temprana-preventiva-en-el-maule-pese-a-baja-de), [24horas](https://www.24horas.cl/regiones/zona-centro/maule/alerta-por-enjambre-sismico-en-el-complejo-volcanico-laguna-del-maule)) | Missing; medium priority, Andean comunas |
| Tsunami | SHOA inundation charts exist for Constitución and, since December 2024, Llico-Lipimávida and Duao-Iloca; none found for Pelluhue or Curanipe ([ONEMI repository](https://repositoriodigitalonemi.cl/web/bitstream/handle/2012/1122/Constitucion_sequence-1.pdf), [24horas](https://www.24horas.cl/actualidad/nacional/shoa-nuevas-cartas-inundacion-tsunami-costa-chilena-shoa)) | Keep, only for coastal comunas |
| Recent earthquakes | No evidence that a public list of recent quakes helps residents; frequent incomplete seismic information raises stress ([Delfino](https://delfino.cr/2023/06/de-anticipaciones-pronosticos-y-predicciones-sismologicas-el-caso-de-la-region-de-osa-costa-rica), [UNAL](https://revistas.unal.edu.co/index.php/esrj/article/view/77206)) | Candidate to reshape: only felt quakes, with the coastal self-evacuation rule |
| Air quality MP2.5 | Critical-episode management in Talca-Maule runs 1 April to 30 September; Curicó has its own MP2.5 plan ([MMA GEC 2025](https://ppda.mma.gob.cl/wp-content/uploads/2026/04/INFORME_TERMINO_GEC_2025_PDA_Talca-Maule.pdf)) | Low relevance October to March except wildfire smoke |
| Drought | No 2026 scarcity decree for Maule found; the last ones are from 2019 and 2021 ([Infraestructura Pública](https://www.infraestructurapublica.cl/confirman-nuevo-decreto-escasez-hidrica-las-30-comunas-la-region-del-maule/)) | Not needed this season |

Overload: people recall less with every extra message (41 % lower odds per extra message in a health-provider trial), and the most important information should come first ([NSW Behavioural Insights Unit](https://www.nsw.gov.au/departments-and-agencies/behavioural-insights-unit/blog/ten-tips-for-communicating-information-to-customers-an-emergency)).

### Multi-country backup sources per element

| Element | Candidate | Status |
|---|---|---|
| Earthquake | EMSC SeismicPortal FDSN event API and websocket, GeoJSON/QuakeML, CC BY 4.0 ([EMSC](https://seismicportal.eu/webservices.html)) | Ready to add next to USGS |
| Wildfire detection | NASA FIRMS area API, CSV, free MAP_KEY, about 3 h latency ([connector doc](https://learn.microsoft.com/en-us/connectors/nasafirms)); INPE Queimadas South America 24/48 h CSV and WMS from polar and GOES satellites ([INPE metadata](https://data.inpe.br/geonetwork/geonetwork/api/records/c4b6504f-5d54-4b61-a745-4123fae873ec)) | Two independent detections possible; FIRMS licence not confirmed |
| Fire danger | GWIS fire danger forecast 1-10 days from ECMWF, Météo-France and NASA GEOS-5 FWI ([GWIS](https://gwis.jrc.ec.europa.eu/about-gwis/technical-background/fire-danger-forecast)) | No API found |
| Floods | GloFAS return-period thresholds, Copernicus full and open ([EEA](https://cis2.eea.europa.eu/data/934/), [ECMWF](https://confluence.ecmwf.int/spaces/CEMS/pages/265028721/GloFAS+v3.1+flood+thresholds+and+comparison+with+GloFAS+2.1)) | Open-Meteo flood API terms not confirmed |
| Severe weather | Open-Meteo per-model forecasts (DWD ICON, NOAA GFS, ECMWF IFS), CC BY 4.0 ([Open-Meteo licence](https://open-meteo.com/en/licence)) | Commercial-use terms conflict between sources; check before relying on it |
| Observed rain | JAXA GSMaP NRT, 4 h latency like IMERG; GSMaP_NOW does not cover South America ([JMA](https://www.data.jma.go.jp/mscweb/en/aomsuc6/abstract/abst_s03-1.pdf)) | Adds little; licence not found |
| Volcanic | Buenos Aires VAAC (Argentina SMN) ash advisories ([UNIGE](https://www.unige.ch/sciences/terre/CERG-C/download_file/view/516/386)) | No live feed found; SERNAGEOMIN format not found |
| Landslide | NASA LHASA v2 daily 1 km nowcast at GES DISC, a ranking rather than a calibrated probability ([README](https://acdisc.gsfc.nasa.gov/data/Landslide/Global_Landslide_Nowcast.2.0.0/doc/README.Global_Landslide_Nowcast_2.0.0.pdf)) | Access terms conflict between AWS and data.gov listings |
| Tsunami | Peru DHN and Ecuador INOCAR relay PTWC messages; no CAP feed found ([oceanexpert](https://oceanexpert.org/downloadFile/58618)) | Nothing to add beyond PTWC |
| Aggregator | IFRC Alert Hub, official CAP alerts from the WMO register ([Prepare Center](https://preparecenter.org/initiative/the-ifrc-alert-hub/)) | Chile and Argentina feed status not confirmed |

Method: WMO alert frameworks are built to strengthen the authoritative national voice, and the WMO Severe Weather Information Centre notes that official centres can disagree ([GMAS](https://www.droughtmanagement.info/wp-content/uploads/2018/08/Global-Multi-Hazard-Alert-System-GMAS-.pdf), [SWIC](https://severeweather.wmo.int/tc.html)). No WMO guidance on fusing unofficial sources was found; one flood study found official and unofficial warnings complementary ([Journal of Contingencies and Crisis Management](https://www.pollux-fid.de/r/cr-10.1111/1468-5973.12121)).

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
| G10 | Hazards | Wildfire activity and smoke (NASA FIRMS hotspots, CONAF if available) | In Progress | Active fires done (INPE and FIRMS public files, no key needed); smoke and CONAF not done |
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
