# River points

`river_points.py` picks the main river of every comuna in a region and fits its flood thresholds, writing `backend/app/sources/river_points.json`, which the `glofas_flood` source and the `river_flood` card read.

Run from `backend/` against a database that has the region loaded (`python -m app.cli create-region --region 07`):

`~/.local/bin/uv.exe run python ../tools/river-points/river_points.py`

- Main river: every 0.05 degree GloFAS cell centre inside the comuna is sampled through the Open-Meteo Flood API; the cell with the largest mean discharge over the last 31 days wins.
- Thresholds (`flood_stats.py`): annual maximum discharge from 1997 (where the GloFAS history served by Open-Meteo begins) to last year; Mann-Kendall trend test at 5%; when significant, each maximum is moved to the present year with Sen's slope (time-varying location, Salas and Obeysekera 2014); Gumbel fit by L-moments, as GloFAS does; 2, 5 and 20-year return levels (GloFAS yellow, red and purple bands).
- Rerun once a year so the present-year adjustment and the latest annual maximum stay current.
