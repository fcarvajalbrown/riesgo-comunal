# Session notes

## Current state

MVP complete (ROADMAP Phase 1 Done). Runs natively (dev DB on port 5440 via `tools/dev-db/`) and with `docker compose up -d` (verified on a clean clone). Smoke checks: `tools/docker-check/run.sh` and `tools/docker-check/api-check.sh`.

## Open flags

- Blocked on external parties: DMC credential, SENAPRED alert feed, licence confirmations, CSN approval (see ROADMAP open items).
- Ubuntu-22.04 WSL VHDX holds about 6.6 GB of freed space; left as is by choice. Docker Engine stays installed there for future compose checks.
- No git remote configured; commits are local only.
- No ADRs written yet; stack decisions live in `docs/architecture.md`.
