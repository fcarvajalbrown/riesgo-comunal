# Security

## In place

| Area | Implementation |
|---|---|
| Authentication | Email and password, bcrypt hashes, JWT (HS256) with configurable lifetime (`JWT_TTL_MINUTES`, default 12 h) |
| Authorisation | Roles `SUPER_ADMIN`, `MUNICIPAL_ADMIN`, `ALCALDE`, `EMERGENCIAS`, `SECPLAN`, `COMUNICACIONES`, `VIEWER`; permission map in `backend/app/auth.py` (upload, configure, alert:create, source:run, audit:read) |
| Tenant isolation | The tenant comes from the user record behind the token, never from the request, except for `SUPER_ADMIN` (`X-Municipality-Id`). Every municipal query filters by `municipality_id`; provenance of an upload is only visible to its tenant. Covered by `tests/test_api.py` |
| Audit log | Logins, failed logins, uploads, deletions, configuration changes, alerts, source runs, report downloads and assistant questions in `audit_log`; readable by admins at `/api/audit` |
| Uploads | Extension allow-list per kind, size limit (`MAX_UPLOAD_MB`, default 25), SHA-256 stored, random file names, coordinates checked to be within 5 km of the comuna, parsing inside a savepoint |
| Rate limiting | In-memory per-IP limits: login 10/min, assistant 30/min, uploads 30/min |
| Transport | Caddy HTTPS with HSTS; security headers from Caddy and the API |
| Secrets | Only in `.env` / environment variables; nothing sent to the browser; `.env` is git-ignored |
| Database | Not exposed outside the compose network; the API uses one database role |
| Containers | API and web run as non-root users |

## Not yet in place (roadmap)

- PostgreSQL row-level security as a second tenant barrier.
- Account lockout and password policy; password reset flow; MFA.
- Rate limits shared across API replicas (needs Redis if the API is scaled out).
- Antivirus scan of uploaded files.
- Encrypted backups and documented key handling.
- Central log shipping and alerting on ingestion failures (today: the "Fuentes" screen and container logs).
- SSO (Keycloak) for municipalities with institutional identity providers.

## Operational rules

- Change `POSTGRES_PASSWORD`, `JWT_SECRET` (48+ random characters) and `ADMIN_PASSWORD` before the first start.
- Never enable `SEED_DEMO` on a production tenant.
- If a hosted LLM is configured, municipal data in questions and tool results leaves the server; record that in the municipality's data processing terms.
