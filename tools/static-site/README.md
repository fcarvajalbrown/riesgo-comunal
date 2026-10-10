# static-site

Temporary static snapshot of the public residents page for the 30 Maule comunas (CUT codes starting with `07`), served from the `gh-pages` branch until the VPS is live.

- `build.py --out DIR` writes `DIR/index.html` (the comunas with their overall level) and `DIR/<slug>/index.html` per comuna, plus `.nojekyll`. It calls the public API functions `public_comuna`, `public_summary` and `public_sources` from `backend/app/api/routes.py` against the local database, inside a transaction that is rolled back. No map, no address check, no staff content.
- Every page ends with the same footer (`site_footer` in `build.py`): links to all comunas and to three information pages, the initiative line, the not-official notice and the data credits. The information pages are `como-lo-calculamos/`, `sobre-esta-iniciativa/` and `prensa/`; their Spanish copy lives in `info_pages.py`. The methodology copy restates thresholds from `backend/app/hazards/*.py` and `tools/season/README.md` in plain words, so a threshold change there needs the same change in `info_pages.py`.
- `make_banner.py` renders the senator's brand kit in `assets/graficas-vodanovik/` (`4.svg` white logo, `1.svg` navy texture with the Maule silhouette) through headless Chromium into `vendor/senator-logo.png` and `vendor/senator-banner.webp`, which `build.py` copies into the site. Rerun it only when the brand kit changes: `cd backend && ~/.local/bin/uv.exe run python ../tools/static-site/make_banner.py`.
- `publish.sh` builds into a temp directory and force-pushes it as a single-commit orphan `gh-pages` branch.

Run from the repo root with the dev database up (`tools/dev-db/start.sh`) and fresh data (`uv run python -m app.cli ingest` in `backend/`):

```
bash tools/static-site/publish.sh
```

Build only: `cd backend && ~/.local/bin/uv.exe run python ../tools/static-site/build.py --out <dir>`.

Refresh: a Hostinger cron runs `deploy/hostinger/trigger_static_site.php` every 15 minutes, which starts `.github/workflows/static-site.yml` through the GitHub API. The fine-grained token (repository `riesgo-comunal`, Actions read and write) lives only in `~/riesgo-comunal/github-token` on Hostinger, mode 600. GitHub's own cron in the workflow stays as a backup.
