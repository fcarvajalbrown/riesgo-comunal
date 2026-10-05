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
| GET | `/sources` | any | registry with status, last run, record counts, licence flags |
| POST | `/sources/{key}/run` | `source:run` | run an adapter now |
| GET | `/hazards` | any | modules, enabled flag, default and effective thresholds |
| PUT | `/municipality/config` | `configure` | branding and hazard settings; unknown thresholds rejected |
| GET | `/alerts` | any | alerts entered by the municipality |
| POST | `/alerts` | `alert:create` | enter an official alert; `source_url` is required |
| POST | `/alerts/{id}/end` | `alert:create` | mark an alert as ended |
| GET | `/audit` | `audit:read` | last 200 audit entries |

## Municipal data and assistant

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/uploads` | `upload`, 30/min | multipart: `kind` (`assets`, `incidents`, `sectors`, `document`, `raster`), `file`, optional `category`, `title` |
| GET | `/uploads` | any | uploads with status and counts |
| DELETE | `/uploads/{id}` | `upload` | remove an upload, its records and its stored files |
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
| GET | `/public/{slug}/resumen` | minimal citizen summary: levels, headlines, alerts with official links, notice |
