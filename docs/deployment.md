# Deployment

## Services (`docker-compose.yml`)

| Service | Image | Role |
|---|---|---|
| `db` | built from `pgvector/pgvector:0.8.7-pg17-bookworm` + `postgresql-17-postgis-3` | PostgreSQL, PostGIS, pgvector |
| `bootstrap` | `backend/` | one-shot: migrations, tenant creation (downloads comuna boundaries), first admin, optional DEMO data |
| `api` | `backend/` | FastAPI on port 8000 (internal) |
| `worker` | `backend/` | APScheduler loop running due source adapters every minute; includes headless Chromium (Playwright) for the SENAPRED alerts page |
| `web` | `frontend/` | Next.js standalone server on port 3000 (internal) |
| `caddy` | `caddy:2-alpine` | HTTPS, `/api/*` to `api`, everything else to `web` |
| `ollama` | `ollama/ollama` | optional, profile `local-llm` |

## Install

```bash
cp .env.example .env        # set POSTGRES_PASSWORD, JWT_SECRET, TENANT_CUT, TENANT_SLUG, ADMIN_EMAIL, ADMIN_PASSWORD, SITE_ADDRESS
docker compose up -d --build
docker compose logs -f bootstrap   # wait for it to exit 0
```

`TENANT_CUT` is the 5-digit CUT code (Lota is `08106`). To install a whole region instead, set `TENANT_REGION` to the 2-digit region code (Maule is `07`) and leave `TENANT_CUT` and `TENANT_SLUG` empty: bootstrap creates one tenant per comuna whose CUT starts with that code (30 for Maule), with slugs taken from the comuna names (`constitucion`, `rio-claro`), and `ADMIN_EMAIL` becomes a `SUPER_ADMIN` that can switch between them. `python -m app.cli create-region --region 07` does the same on a running install and skips comunas that already exist. With `SITE_ADDRESS` set to a public domain whose DNS points to the server, Caddy obtains a Let's Encrypt certificate automatically. With `localhost` or an internal name, Caddy uses its own local CA (browsers warn until that CA is trusted). Set `SEED_DEMO=true` only on demonstration installs; DEMO records are labelled in every screen and the generated user passwords are printed in the bootstrap log.

The first worker run downloads all sources and the USGS backfill since 2000 (about 22,000 events for Chile), which takes a few minutes.

## Minimum resources

Measured with `docker compose` on a clean clone (one tenant, all sources ingested, DEMO data, `tools/docker-check/`): image build 3 min 17 s; first ingestion pass of every source 99 s; database 137 MB; container memory at rest db 726 MiB (mostly PostgreSQL cache), worker 279 MiB, api 114 MiB, web 39 MiB, caddy 13 MiB, about 1.2 GiB in total. While the worker reads the SENAPRED alerts page with headless Chromium (every 10 minutes), the worker peaks at about 600 MiB. Images take 4.0 GB on disk (the backend image, 2.7 GB with Chromium and GDAL, is shared by `api`, `worker` and `bootstrap`), volumes 0.3 GB, and the build leaves 4.9 GB of cache (`docker builder prune` reclaims it). The figures below are planning estimates for one to five tenants:

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB (16 GB with a local LLM) |
| Disk | 20 GB SSD | 50 GB SSD plus backup space |
| OS | Any 64-bit Linux with Docker Engine 24+ and Compose v2 | Ubuntu Server 24.04 LTS |
| Network | Outbound HTTPS to the sources in `data-sources.md`; inbound 80/443 | Static IP and DNS name |

Maule region install (31 tenants: the 30 Maule comunas plus Lota), measured natively on the local dev database, not in Docker: `create-region --region 07` takes 81 s including the national boundary download; the first full ingestion takes about 4.5 min (slowest sources MOP Vialidad 67 s, INE census 49 s for 84,769 blocks, SENAPRED layers 45 s); database 211 MB with 30,271 features and 15,580 analysis cells. Risk evaluation per request grows with comuna size: San Clemente (2,154 analysis cells) takes 1.9 s for the comuna level and 9.1 s for the per-sector level, against 0.8 s and 0.6 s for Lota. Container memory for 31 tenants is not measured yet (no Docker on the measuring machine).

A local LLM needs its own sizing (a 7-8B model quantised to 4 bits needs roughly 6 GB RAM and runs slowly on CPU).

## Hosting options

- **Municipal server or VM**: the compose stack as is.
- **VPS (including Hostinger or IONOS VPS plans)**: same stack; Docker must be installable, so a KVM VPS is required. This is the target for the Maule install.
- **Shared web hosting (including Hostinger shared/Business web hosting)**: not supported. It does not run Docker, PostgreSQL with PostGIS, or long-running workers.

## Domain (IONOS)

For a domain registered at IONOS and a VPS anywhere: in the domain's DNS settings at IONOS, point an `A` record for the domain (and `www` if used) to the VPS public IPv4 address, plus an `AAAA` record if the VPS has IPv6. Remove any default IONOS records that point the same names elsewhere. Then set `SITE_ADDRESS` to the domain and `PUBLIC_URL` to `https://` plus the domain in `.env`, open ports 80 and 443 on the VPS firewall, and start the stack; Caddy obtains the certificate once DNS resolves to the VPS (`dig +short <domain>` should return the VPS address).

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

`tools/dev-db/setup.sh` copies a local PostgreSQL 18 installation into `%LOCALAPPDATA%\riesgo-comunal`, adds the PostGIS bundle and initialises a database on port 5440 without administrator rights; `tools/dev-db/start.sh` runs it. Then `cd backend && uv run alembic upgrade head`, `uv run python -m app.cli create-tenant --cut 08106 --slug lota`, `uv run python -m app.cli ingest`, `uv run uvicorn app.main:app --timeout-keep-alive 75`, and `cd frontend && pnpm dev` (port 3100). The longer keep-alive matters only here, where Next.js proxies `/api`: with uvicorn's default of 5 s, Node can reuse a connection uvicorn has just closed and the request fails with "socket hang up". In Docker, Caddy sends `/api` straight to the API. pgvector is not available in this setup; document search uses full-text search.
