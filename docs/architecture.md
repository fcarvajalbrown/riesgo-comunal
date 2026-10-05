# Architecture

## Principles

1. **The data layer is the source of truth; the AI explains and queries it.** No component, the AI included, produces a fact that is not in the database with provenance.
2. **The browser and the AI never call external services.** External data enters only through source adapters run by the worker, is normalised into PostGIS, and is served by the API.
3. **Every value carries its class**: `observed`, `forecast`, `official_warning`, `historical`, `municipal`, `derived`. The class travels from the table to the API response to the UI badge to the report line.
4. **Modules, not a monolith of hazards.** Hazards and sources are registered plugins. Turning one off is configuration.
5. **One codebase, many comunas.** Tenant boundaries exist from the first table, and a single-comuna municipal install is the same software with one tenant.
6. **Operational simplicity is a product requirement.** A municipality with one IT person must be able to run `docker compose up -d`.

## Component diagram

```text
 External sources (SENAPRED ArcGIS, IDE geoportal WFS, SINCA, DGA, USGS, DMC*)  * needs credential
            |
            v
 +----------------------+        +-----------------------------+
 | worker (Python)      |        | api (FastAPI)               |
 |  APScheduler         |        |  auth / RBAC / audit        |
 |  source adapters ----+--+     |  modes: ahora/riesgo/plan   |
 |  provenance writer   |  |     |  hazard registry            |
 +----------------------+  |     |  risk engine (rules)        |
                           |     |  statistics                 |
                           v     |  uploads (CSV/GeoJSON/KML/  |
                 +--------------------+  PDF) -> tenant rows     |
                 | PostgreSQL 17      |  assistant (tools + RAG) |
                 |  PostGIS           |  reports (JSON + PDF)    |
                 |  pgvector (opt.)   |<-+                       |
                 |  full-text search  |  +-----------------------+
                 +--------------------+            ^
                                                   | /api (JSON)
 +-----------------------------+                   |
 | web (Next.js, TypeScript)   |-------------------+
 |  MapLibre GL, TanStack Query|
 |  role views, progressive    |
 |  disclosure, Spanish UI     |
 +-----------------------------+
            ^
            | HTTPS
 +-----------------------------+      optional
 | caddy (TLS, reverse proxy)  |      +---------------------------+
 +-----------------------------+      | LLM: any OpenAI-compatible|
                                      | endpoint (Ollama, vLLM,   |
                                      | LiteLLM proxy, hosted API)|
                                      +---------------------------+
```

## Data flow

1. The worker runs each enabled adapter at its declared interval. An adapter `fetch`es, `parse`s, `normalize`s into the internal records, `validate`s them, and returns a batch. The ingestion runner opens an `ingestion_job`, writes a `provenance` row, upserts records with the provenance id, assigns each geometry to a comuna by spatial join, then closes the job with counts or the error. The source's `last_success_at` / `last_error` are updated.
2. The API reads only from the database. Mode endpoints call the hazard registry; each enabled hazard module assesses the comuna (and its sectors) with the tenant's thresholds and returns an `Assessment` with level, factors, explanation, data classes and sources.
3. The web app renders the simple answer first (level, one sentence), then explanation, detail and technical data on demand.
4. The assistant receives a question, selects tools (structured, spatial, document search), and composes an answer only from tool outputs, attaching sources and timestamps from those outputs.

## Ingestion architecture

`backend/app/sources/base.py` defines `SourceAdapter` with:

| Member | Purpose |
|---|---|
| `meta: SourceMeta` | key, name, organization, url, license text, `commercial_use`, `cache_allowed`, authority, attribution, default interval, `requires` (credentials) |
| `fetch(client)` | network I/O only, returns raw payloads |
| `parse(raw)` | raw to Python structures |
| `normalize(parsed)` | to internal records (`FeatureRecord`, `ObservationRecord`, `EventRecord`, `IndexRecord`) |
| `validate(records)` | drops or flags invalid records, returns warnings |

Adapters are registered in `sources/registry.py`. Source-specific formats never leave the adapter. Replacing SENAPRED's endpoint means editing one adapter.

## Database architecture

PostgreSQL 17 + PostGIS 3. All geometries are EPSG:4326 with GiST indexes; distance and area work casts to `geography`. Main tables:

| Table | Tenant-scoped | Contents |
|---|---|---|
| `municipality` | is the tenant | CUT code, name, region, boundary, branding, configuration (enabled hazards, thresholds) |
| `app_user`, `audit_log` | yes | users with role; every write and login |
| `source`, `ingestion_job`, `provenance` | no | source registry, run history, per-batch lineage |
| `feature` | no | official geospatial features (schools, health centres, hazard polygons, stations) with `dataset`, `cut_code`, `properties`, `data_class` |
| `observation` | no | time series per station and parameter, with `validation_status` |
| `forecast` | no | forecasts (empty until a forecast source is configured) |
| `alert` | optional | official alerts from authorised feeds, or entered by a municipal operator with a source URL |
| `historical_event` | no | earthquakes and other dated events from sources |
| `comuna_index` | no | per-comuna indices such as SENAPRED's ICFSR |
| `sector` | yes | municipal sectors (uploaded) or derived analysis cells |
| `municipal_asset`, `municipal_incident` | yes | uploaded municipal data |
| `upload`, `document`, `document_chunk` | yes | files, extracted text, full-text vector, optional embedding |

Official data is shared across tenants because it is public and identical for everyone; municipal data is filtered by `municipality_id` in every query path, enforced in the repository layer and covered by tests.

## Risk engine

Rules-based and explainable; see `risk-model.md`. Each hazard module implements `assess(ctx) -> Assessment`. The engine never calls a model to decide a level.

## AI / RAG architecture

See `ai-rag.md`. A provider-agnostic client speaks the OpenAI-compatible chat API (works with Ollama, llama.cpp server, vLLM, LiteLLM proxy and hosted providers). Tools: situation, risk summary, exposed assets, statistics, document search, source lookup. Document search is PostgreSQL full-text search (Spanish configuration) by default, with pgvector similarity added when the extension and an embedding endpoint are configured. When no LLM is configured, a deterministic answerer composes replies from the same tools, so the assistant still works and never invents text.

## Frontend architecture

Next.js (App Router) with TypeScript, Tailwind CSS, TanStack Query for server state and MapLibre GL JS for the map. The app is a client-side application served by Next.js; all data comes from the FastAPI `/api`. Structure: `app/` routes (login, main workspace), `components/` (mode panels, map, badges, assistant, reports, uploads), `lib/` (API client, types, formatting). Map state lives in the URL where useful.

## Deployment architecture

Docker Compose services: `db` (PostGIS + pgvector image built from `pgvector/pgvector` plus the PostGIS package), `api`, `worker` (same image as `api`, different command), `web`, `caddy`. Optional `ollama` profile. Volumes: database, uploaded files, Caddy certificates. See `deployment.md`.

## Municipal customisation architecture

Per-tenant configuration in `municipality.config` (JSON validated by Pydantic): branding (name, colours, logo path), enabled hazards, thresholds per hazard, terminology overrides, emergency contacts. Admins edit it from the "Configuración" screen; changes are audited. See `municipal-customization.md`.

## Multi-tenant architecture

- **Model A, dedicated install**: one compose stack, one tenant row.
- **Model B, hosted**: one stack, many tenant rows. Every municipal table has `municipality_id`; JWTs carry `municipality_id` and role; the API derives the tenant from the token, never from a request parameter, except for `SUPER_ADMIN`.
- Row-level security in PostgreSQL is the planned hardening step (roadmap), on top of application-level filtering.

## Stack decisions, each challenged

| Baseline component | Decision | Requirement that decided it |
|---|---|---|
| PostgreSQL + PostGIS | **Kept** | Spatial joins, buffers, areas and exposure counts are the product. |
| pgvector | **Kept as optional** | The Docker image includes it. Embeddings need an embedding model; municipalities without one still need document search, so full-text search is the default and pgvector is additive. |
| FastAPI | **Kept** | Python is where the GIS, ETL and LLM libraries are. |
| SQLAlchemy + Alembic | **Kept** | Migrations must run unattended on municipal servers. |
| Celery + Redis | **Replaced by APScheduler in a dedicated worker process** | MVP jobs are a handful of periodic HTTP pulls (minutes to days). Celery adds Redis and a broker to operate, more RAM and more failure modes for a one-person municipal IT team. Revisit when job volume or fan-out requires a queue (hosted model with many tenants). |
| Next.js + React + TypeScript | **Kept** | Role-specific dashboards, map, chat and reports are complex client state. |
| Tailwind | **Kept** | |
| shadcn/ui | **Not adopted in MVP** | It copies Radix-based components into the repo and adds several packages. The MVP needs a small set of components (cards, badges, tabs, dialog); they are written directly in Tailwind. Revisit when forms and tables multiply. |
| TanStack Query | **Kept** | Polling, caching and invalidation of server state. |
| Zustand | **Not needed yet** | Client state is small (selected mode, layers); React state and the URL cover it. |
| MapLibre GL JS | **Kept** | Open source, no vendor key. Basemap from OpenFreeMap (free, commercial use allowed) with self-hosting as the offline path. |
| Martin tile server | **Deferred** | Per-comuna layers are small enough for GeoJSON from the API (bounded by comuna). Add vector tiles when national layers are rendered at once. |
| LiteLLM | **Replaced by a thin OpenAI-compatible client** | Ollama, llama.cpp, vLLM, LiteLLM proxy and most hosted providers expose this API, so one client covers them without the LiteLLM dependency tree. A LiteLLM proxy can still sit behind it. |
| MinIO | **Filesystem volume** | Files are small and per tenant; an S3 backend can replace the storage interface later. |
| Caddy | **Kept** | Automatic HTTPS with a one-line config. |
| JWT + RBAC | **Kept** | Keycloak later for SSO. |
| GeoPandas / Polars / Rasterio | **Not needed in MVP** | Parsing is done with the standard library and PostGIS functions; no raster sources are ingested yet. Fewer native wheels makes the image smaller and builds more reliable. |
| PDF export | **fpdf2** (pure Python) | WeasyPrint needs system GTK/Pango libraries; fpdf2 has no native dependencies. |
