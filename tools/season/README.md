# Season signal

Decides, once a month, whether the rain row or the fire row leads on the Maule comuna pages (after rows that carry an official alert), from what the weather actually did rather than the calendar.

- `season.py baseline` computes the 1991-2020 normals once into `baseline.json`: for every calendar day, the gamma fit of 30-day rain totals and the mean 30-day Fire Weather Index. Run again only to change the points or the window.
- `season.py current --out current.json` computes the last 30 days (ending yesterday) and writes `current.json`, which `tools/static-site/build.py` reads.
- The `season` GitHub workflow runs `current` on the 1st of each month at 10:00 UTC and commits the result; the 15-minute site build picks it up.

Method:

- Rain: Standardized Precipitation Index (McKee et al. 1993; WMO-recommended), 30-day window, gamma fit with Thom's estimator and a zero-rain share.
- Fire weather: Canadian Fire Weather Index (Van Wagner 1987), daily from local-noon temperature, humidity and wind and the 24 h rain to noon, southern-hemisphere day-length factors; `fwi.py` reproduces Van Wagner's worked example (FFMC 87.7, ISI 10.9, BUI 8.5, FWI 10.1).
- Points: Talca, Curicó, Linares and Cauquenes, averaged.
- Rule: fire first when the 30-day mean FWI is above its 1991-2020 normal for the same dates and the SPI is below +1; otherwise rain first. The NOAA CPC ONI (El Niño) is shown as context and does not decide.
- Data: ERA5 through the Open-Meteo historical API; ONI from NOAA CPC. Standard library only.
