# page-shot

Headless page checks for the web app; no window opens.

- `shot.py URL OUT.png [--width W --height H] [--wait-text TEXT] [--fill SELECTOR TEXT [--press-enter]] [--click TEXT ...] [--select SELECTOR VALUE ...] [--local-storage KEY=VALUE ...] [--overflow] [--add-style CSS]` renders the page with Playwright's headless Chromium, prints console and page errors, and saves a full-page PNG. `--overflow` lists elements wider than the viewport (sideways scroll on a phone); `--add-style` injects CSS after load, to try a style fix on the live site before changing the build.
- `session_token.py EMAIL` prints a session token for a user in the local database, to pass as `--local-storage riesgo.token=...` for staff pages.

Run both from `backend/` with `uv run python ../tools/page-shot/<script>`.
