# Session notes

## Current state

The public Maule site (https://synterra.cl/maule/) is live for launch on 11 October 2026, rebuilt about every 15 minutes by the `static-site` workflow (Hostinger cron dispatch). Comuna pages: one row per hazard, official alert beside "Nuestro análisis"; footer pages for method, initiative and press. Launch blockers from the pre-launch review are fixed and verified live. 146 backend tests pass. Next step: the "Pulido de la página" list in `ROADMAP.md` (items 3-21), starting with item 3 (overall level wording) and item 4 (env variable names in public copy).

## Open flags

- Senator quote pending her media manager; `minuta-prensa-lanzamiento.md` (repo root, uncommitted) still has placeholders.
- SHOA bulletin reader never worked (snamchile.cl and shoa.cl answer 403); the tsunami row still says "Sin alerta oficial".
- Blocked on external parties: DMC credential, official SENAPRED feed, CSN approval. Licence questions are not pursued (owner decision).
- DART 34420 off Concepción offline; no second aluvión source.
- Local dev DB on port 5440 has the 30 Maule comunas but not the full ingest.
