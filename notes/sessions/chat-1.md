# Session 1

## Done

- Research of Chilean official sources and their terms (`docs/data-sources.md`, `docs/data-licensing.md`); pilot comuna Lota chosen by highest ICFSR.
- Stack challenged and slimmed (APScheduler instead of Celery+Redis, thin OpenAI-compatible client, no shadcn), recorded in `docs/architecture.md`.
- Backend: PostGIS schema with tenants and provenance, source adapters (SENAPRED, IDE Chile geoportal, SINCA, DGA, USGS, DMC), worker, six hazard modules, rules engine, statistics, assistant with tools and full-text RAG, uploads, role reports with PDF, RBAC, audit log.
- Frontend: Next.js with MapLibre, AHORA / RIESGO / PLANIFICAR, assistant, reports, municipal data, sources, configuration.
- All docs listed in the goal, README and ROADMAP.
- Docker: Docker Engine installed in WSL Ubuntu-22.04; `docker compose up -d` verified on a clean clone and fresh volumes; images pruned afterwards.

## Flags opened and closed

- Closed: DB image base `postgis/postgis:17-3.5` (Debian bullseye, pgdg repo archived) replaced by `pgvector/pgvector:0.8.7-pg17-bookworm` plus `postgresql-17-postgis-3`.
- Closed: a new tenant left SENAPRED hazard layers and ICFSR waiting 24 h because the boundary-only run stamped the source; tenant creation now marks all sources due (test added).
- Open: DMC credential, SENAPRED alert feed, licence confirmations, CSN approval (all in ROADMAP open items).
- Open: the Ubuntu-22.04 WSL disk image grew to 9.9 GB while holding 3.3 GB; space is not returned to Windows until the VHDX is compacted.

## Tests

Backend 71 passed (pytest), frontend 5 passed (`node --test`), typecheck clean.
