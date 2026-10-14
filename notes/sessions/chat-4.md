# Session 4

## Done

- Static-site failure emails diagnosed: 13 of 402 runs since 8 October failed (3.2%), 10 from `ssh-keyscan` timing out on Hostinger, 3 from ArcGIS answering 304 to the comuna boundary query.
- ArcGIS reader retries 304 and 5xx; `ssh-keyscan` retried with a longer timeout; GitHub Pages deploys before the Hostinger upload, which no longer fails the run.
- Database carried between runs in the Actions cache (`pg_dump` / `pg_restore`); `fresh` dispatch input starts empty.
- Daily failure digest: `tools/static-site-health` and the `static-site-health` workflow comment on issue #1 only on days with a failure.
- Runs cut from about 11 min to under 3: only due sources ingest (`--due`), six in parallel (`--jobs`), failed sources retry hourly, SENAPRED official alert pages checked six at a time.
- Phone layout: region map height, no sideways scroll at 360 px, three-column emergency phone tiles, level badge above the title in "Nuestro análisis" cards.
- `tools/page-shot` gained `--overflow` and `--add-style`; new `tools/source-probe` with a `source-probe` workflow.
- SHOA: snamchile.cl blocks GitHub runner addresses (405 to every client, including headless Chromium); the tsunami row now says the SHOA bulletins could not be read instead of "Sin alerta oficial".

## Flags opened

- ROADMAP needs reordering around a defined goal and an ordered line of work.
- Phone home page about 10,000 px tall (comuna list not collapsed).
- Map credits box covers part of the phone map.

## Flags closed

- Static-site failure emails.
- Runs too slow for the 15-minute promise.
- Phone pages scrolling sideways.
- Tsunami row claiming "Sin alerta oficial" while SHOA is unread.
