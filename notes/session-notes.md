# Session notes

## Current state

MVP complete and verified with `docker compose up -d` on a clean clone. Full-spec gap items done: G3, G4, G14, G15, G16, G17; G9 partly (official DMC warnings; observations blocked). Tenants: Lota (08106) and Retiro (07405). 99 backend tests pass. Next step: G5 volcanic module. The paste-ready handoff is in `PROMPT.md`.

## Open flags

- Blocked on external parties: DMC credential, NASA FIRMS key, official SENAPRED feed, licence confirmations (SENAPRED, IDE Chile, SINCA, DGA, MOP), CSN approval.
- Retiro tsunami card says "Sin datos" instead of "no aplica" for an inland comuna.
- OpenStreetMap urban streets deferred.
- `frontend/e2e/` and `frontend/playwright.config.ts` uncommitted, waiting for G20.
- Local dev: run uvicorn with `--timeout-keep-alive 75` behind the Next proxy.
- Docker Engine stays installed in WSL Ubuntu-22.04 for compose checks.
