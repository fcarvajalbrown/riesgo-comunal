# API

FastAPI under `/api`. The interactive OpenAPI schema is served at `/api/docs` (`/api/openapi.json`). All endpoints except `health`, `auth/login` and `public/*` need `Authorization: Bearer <token>`. The tenant is taken from the token; `SUPER_ADMIN` can pick one with `X-Municipality-Id`. Error messages are in Spanish because the UI shows them.

## Session

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/health` | public | liveness |
| POST | `/auth/login` | public, 10/min per IP | `{email, password}` → `{token, user}` |
| GET | `/me` | any | user, role, permissions, municipality and its config |

## Modes

| Method | Path | Purpose |
|---|---|---|
| GET | `/ahora` | AHORA assessments, alerts entered with official link, alert-feed note, exposure summary of moderate-or-higher hazards |
| GET | `/riesgo` | RIESGO assessments plus sectors (or analysis cells) ranked by derived level |
| GET | `/riesgo/sector/{id}` | assessment of one sector |
| GET | `/planificar` | ICFSR context, earthquake statistics, municipal incident statistics, planning assessments |

Every assessment carries `level`, `level_label`, `data_class`, `headline`, `reasons`, `evidence[]` (each with `provenance_id`), `exposure[]`, `limitations[]`, `derived_notice` and `uses_demo_data`. Every statistic carries `period`, `n`, `source`, `method` and `limitations`.

## Map, search and provenance

| Method | Path | Purpose |
|---|---|---|
| GET | `/layers` | layer catalogue with source, data class and style |
| GET | `/layers/{key}` | GeoJSON for the tenant's comuna |
| GET | `/search?q=` | official features, sectors and municipal assets by name |
| GET | `/provenance/{id}` | "¿De dónde salió este dato?": source, dataset, URL, source and ingestion times, licence notes |

## Sources and configuration

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sources` | any | registry with status, last run, record counts, licence flags, plus the same `state` and `alert` fields as `/public/{slug}/fuentes` and the last error text |
| POST | `/sources/{key}/run` | `source:run` | run an adapter now |
| GET | `/hazards` | any | modules, enabled flag, default and effective thresholds |
| PUT | `/municipality/config` | `configure` | branding and hazard settings; unknown thresholds rejected |
| GET | `/alerts` | any | alerts entered by the municipality |
| POST | `/alerts` | `alert:create` | enter an official alert; `source_url` is required |
| POST | `/alerts/{id}/end` | `alert:create` | mark an alert as ended |
| PUT | `/municipality/logo` | `configure` | upload a PNG or JPEG logo (1 MB) |
| DELETE | `/municipality/logo` | `configure` | remove the logo |
| GET | `/audit` | `audit:read` | last 200 audit entries |

## Municipal data and assistant

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/uploads` | `upload`, 30/min | multipart: `kind` (`assets`, `incidents`, `sectors`, `document`, `raster`, `contacts`, `inspections`, `photo`), `file`, optional `category`, `title`, `asset_id` (photos) |
| GET | `/uploads` | any | uploads with status and counts |
| DELETE | `/uploads/{id}` | `upload` | remove an upload, its records and its stored files |
| GET | `/contacts` | any | emergency contacts and municipal emergency personnel |
| GET | `/inspections?asset_id=` | any | inspection records, newest first, linked to assets by name |
| GET | `/photos?asset_id=` | any | photo list |
| GET | `/photos/{id}/file` | any | photo file (tenant-checked) |
| GET | `/rasters` | any | GeoTIFF layers of the tenant with WGS84 bounds and metadata |
| GET | `/rasters/{id}/preview.png` | any | transparent WGS84 preview of one GeoTIFF (tenant-checked) |
| GET | `/documents` | any | documents with page and chunk counts |
| POST | `/assistant` | any, 30/min | `{question, audience}` → `{answer, sources[], tools[], mode, generated_at, disclaimer}` |

## Reports

| Method | Path | Purpose |
|---|---|---|
| GET | `/reports` | available roles (`alcalde`, `emergencias`, `secplan`, `comunicaciones`) |
| GET | `/reports/{role}` | report as JSON |
| GET | `/reports/{role}/pdf` | same report as PDF |

## Public

| Method | Path | Purpose |
|---|---|---|
| GET | `/public/{slug}/comuna` | name, region, centre, bounding box and branding (display name, colour, logo URL) |
| GET | `/public/{slug}/resumen` | citizen summary: overall and per-hazard platform levels with headlines, official alerts in force or upcoming (level, dates, issuer, how it reached the platform, official link), feed note, notice |
| GET | `/public/{slug}/geocode?q=` | address search within the comuna through the configured Nominatim server; 20/min per IP, cached, one upstream request per second |
| GET | `/public/{slug}/lugar?lon=&lat=` | place check: tsunami evacuation area and nearest meeting point, wildfire recurrence class, DMC warnings over the point, municipal alerts; 422 beyond 5 km of the comuna; 60/min per IP |
| GET | `/public/{slug}/capas/{key}` | GeoJSON for the public layers only (`comuna`, `tsunami_evacuation_area`, `tsunami_meeting_point`, `wildfire_hazard`, `dmc_warning`); 120/min per IP |
| GET | `/public/{slug}/fuentes` | enabled sources with `state` (`live`, `stale` when no success for 3 intervals or 30 min, `failed`, `pending`, `unconfigured`), `alert` (alert feed or not) and last success time; no error text; 60/min per IP |
| GET | `/public/{slug}/logo` | the comuna's logo |

The residents' page at `/c/{slug}` (for example `/c/lota`) is built only on these endpoints. It needs no login and never shows municipal assets, incidents, contacts or uploads.
