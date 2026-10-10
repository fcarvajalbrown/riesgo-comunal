# Session 3

## Done

- Senator banner rebuilt from her brand kit (`tools/static-site/make_banner.py`), share card rebranded, white site header under her navy band, one navy for all chrome.
- SENAPRED status message split into "failed" and "stale". 15-minute refresh through a Hostinger PHP cron that dispatches the GitHub workflow.
- International alerts (GDACS, PTWC) kept out of the official alert lists; plain Spanish wording.
- Per-hazard "Nuestro análisis" cards with sources one click away. New sources: EMSC, INPE Queimadas, NASA FIRMS, IOC tide gauges, Open-Meteo multi-model, GloFAS river forecast, NOAA DART buoys. New cards: Focos de incendio detectados, Mar y tsunami ahora, Crecidas de ríos (live on every comuna and the home page).
- Comuna page redesigned as one row per hazard, official alert beside our card, each alert once; rows full width, map below (list-first evidence in `docs/ux.md`). Base text 18 px in rem.
- Audience of the Maule site and layout and type research recorded in `docs/ux.md`.
- Monthly season signal (SPI + FWI from ERA5) orders the rain and fire rows (`tools/season`, `season` workflow).
- River thresholds: Gumbel by L-moments, Mann-Kendall trend test and Sen's slope adjustment (`tools/river-points`); 14 of 30 rivers show falling peaks.
- Pre-launch review by an agent; launch blockers fixed and verified live: SENAPRED alerts matched by comuna code, not boundary overlap (13 comunas showed neighbours' alerts); pages titled "Riesgo en <comuna>".
- Logo links home; notice box in a navy tint (the brand kit has no yellow); map height fixed on phones; DART buoy map layer; wind arrows 20% smaller.
- Footer with "Cómo lo calculamos", "Sobre esta iniciativa" (unsigned, sourced "Por qué existe este sitio") and "Prensa" (contact from senado.cl).
- Launch press note drafted at `minuta-prensa-lanzamiento.md` (uncommitted, placeholders).

## Flags opened

- Page polish list (ROADMAP "Pulido de la página", items 3-21).
- Senator quote pending her media manager.
- SHOA bulletin reader never worked (403).
- DART 34420 offline; no second aluvión source.

## Flags closed

- Neighbour comunas inheriting SENAPRED alerts.
- "Municipalidad de" page titles.
- No live flood analysis.
- No second tsunami source.
- Retiro tsunami card "Sin datos" for an inland comuna (tsunami row now coastal-only).
