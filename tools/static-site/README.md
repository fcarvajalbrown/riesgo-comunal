# static-site

Temporary static snapshot of the public residents page for the 30 Maule comunas (CUT codes starting with `07`), served from the `gh-pages` branch until the VPS is live.

- `build.py --out DIR` writes `DIR/index.html` (the comunas with their overall level) and `DIR/<slug>/index.html` per comuna, plus `.nojekyll`. It calls the public API functions `public_comuna`, `public_summary` and `public_sources` from `backend/app/api/routes.py` against the local database, inside a transaction that is rolled back. No map, no address check, no staff content.
- `publish.sh` builds into a temp directory and force-pushes it as a single-commit orphan `gh-pages` branch.

Run from the repo root with the dev database up (`tools/dev-db/start.sh`) and fresh data (`uv run python -m app.cli ingest` in `backend/`):

```
bash tools/static-site/publish.sh
```

Build only: `cd backend && ~/.local/bin/uv.exe run python ../tools/static-site/build.py --out <dir>`.
