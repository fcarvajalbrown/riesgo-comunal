# Static-site health digest

Tells the owner about failed `static-site` runs without one email per failure.

- `report.py --repo <owner/name> --hours 24` counts the last day's finished runs: failed runs (the site did not update), runs where the step "Hostinger upload missed" ran (synterra.cl/maule kept the previous version) and runs where "Region setup failed" ran. When any count is above zero it comments on the issue titled `static-site health`, creating it the first time. Clean days post nothing.
- `--dry-run` prints the digest without commenting.
- The `static-site-health` workflow runs it daily at 12:00 UTC (09:00 in Chile during summer time).
- Needs the `gh` CLI, logged in or with `GH_TOKEN`. Standard library only. Tests: `pytest tools/static-site-health/test_report.py`.
