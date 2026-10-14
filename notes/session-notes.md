# Session notes

## Current state

The public Maule site (https://synterra.cl/maule/) is live, rebuilt every 15 minutes by the `static-site` workflow (Hostinger cron dispatch) in under 3 minutes, with the database carried between runs in the Actions cache. Failures are reported once a day on issue #1 by the `static-site-health` workflow, not by email. Next step: reorder `ROADMAP.md` around one defined goal and an ordered line of work.

## Open flags

- Senator quote pending her media manager; `minuta-prensa-lanzamiento.md` (repo root, uncommitted) still has placeholders.
- SHOA bulletins unreadable from GitHub Actions (snamchile.cl blocks runner addresses); the site says so on the tsunami row. Routing around the block was declined.
- Phone home page about 10,000 px tall; map credits box covers part of the phone map.
- Blocked on external parties: DMC credential, official SENAPRED feed, CSN approval. Licence questions are not pursued (owner decision).
- DART 34420 off Concepción offline; no second aluvión source.
- Untracked `frontend/e2e/` and `frontend/playwright.config.ts` left as found.
