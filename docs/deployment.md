# Deployment

## Services (`docker-compose.yml`)

| Service | Image | Role |
|---|---|---|
| `db` | built from `postgis/postgis:17-3.5` + `postgresql-17-pgvector` | PostgreSQL, PostGIS, pgvector |
| `bootstrap` | `backend/` | one-shot: migrations, tenant creation (downloads comuna boundaries), first admin, optional DEMO data |
| `api` | `backend/` | FastAPI on port 8000 (internal) |
| `worker` | `backend/` | APScheduler loop running due source adapters every minute |
| `web` | `frontend/` | Next.js standalone server on port 3000 (internal) |
| `caddy` | `caddy:2-alpine` | HTTPS, `/api/*` to `api`, everything else to `web` |
| `ollama` | `ollama/ollama` | optional, profile `local-llm` |

## Install

```bash
cp .env.example .env        # set POSTGRES_PASSWORD, JWT_SECRET, TENANT_CUT, TENANT_SLUG, ADMIN_EMAIL, ADMIN_PASSWORD, SITE_ADDRESS
docker compose up -d --build
docker compose logs -f bootstrap   # wait for it to exit 0
```

`TENANT_CUT` is the 5-digit CUT code (Lota is `08106`). With `SITE_ADDRESS` set to a public domain whose DNS points to the server, Caddy obtains a Let's Encrypt certificate automatically. With `localhost` or an internal name, Caddy uses its own local CA (browsers warn until that CA is trusted). Set `SEED_DEMO=true` only on demonstration installs; DEMO records are labelled in every screen and the generated user passwords are printed in the bootstrap log.

The first worker run downloads all sources and the USGS backfill since 2000 (about 22,000 events for Chile), which takes a few minutes.

## Minimum resources

Measured on the development install (one tenant, all sources): database 122 MB after ingestion. Process memory has not been measured yet; the figures below are planning estimates for one to five tenants:

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB (16 GB with a local LLM) |
| Disk | 20 GB SSD | 50 GB SSD plus backup space |
| OS | Any 64-bit Linux with Docker Engine 24+ and Compose v2 | Ubuntu Server 24.04 LTS |
| Network | Outbound HTTPS to the sources in `data-sources.md`; inbound 80/443 | Static IP and DNS name |

A local LLM needs its own sizing (a 7-8B model quantised to 4 bits needs roughly 6 GB RAM and runs slowly on CPU).

## Hosting options

- **Municipal server or VM**: the compose stack as is.
- **VPS (including Hostinger VPS plans)**: same stack; Docker must be installable, so a KVM VPS is required.
- **Shared web hosting (including Hostinger shared/Business web hosting)**: not supported. It does not run Docker, PostgreSQL with PostGIS, or long-running workers.

## Backups

```bash
docker compose exec db pg_dump -U riesgo -Fc riesgo > backup-$(date +%F).dump
docker run --rm -v riesgo-comunal_uploads:/data -v "$PWD":/out alpine tar czf /out/uploads-$(date +%F).tgz -C /data .
```

Restore with `pg_restore -U riesgo -d riesgo --clean` into the `db` container and untar the uploads volume. Schedule both daily (cron on the host) and keep copies off the server. Official data can always be re-downloaded; municipal uploads and configuration cannot.

## Updates

```bash
git pull
docker compose up -d --build
```

The `bootstrap` service re-runs migrations on every start; it is idempotent.

## Local development (no Docker)

`tools/dev-db/setup.sh` copies a local PostgreSQL 18 installation into `%LOCALAPPDATA%\riesgo-comunal`, adds the PostGIS bundle and initialises a database on port 5440 without administrator rights; `tools/dev-db/start.sh` runs it. Then `cd backend && uv run alembic upgrade head`, `uv run python -m app.cli create-tenant --cut 08106 --slug lota`, `uv run python -m app.cli ingest`, `uv run uvicorn app.main:app`, and `cd frontend && pnpm dev` (port 3100). pgvector is not available in this setup; document search uses full-text search.
