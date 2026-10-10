import argparse
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import fwi
import spi

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
POINTS = {
    "Talca": (-35.4264, -71.6554),
    "Curicó": (-34.9828, -71.2394),
    "Linares": (-35.8467, -71.5931),
    "Cauquenes": (-35.9671, -72.3225),
}
HOURLY = ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation")
WINDOW_DAYS = 30
BASELINE_START = date(1990, 12, 1)
BASELINE_YEARS = range(1991, 2021)
SPIN_UP_DAYS = 400
NOON = 12
WET_SPI = 1.0
HERE = Path(__file__).parent


def fetch_json(url: str, params: dict) -> object:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=600) as response:
        return json.load(response)


def fetch_hourly(start: date, end: date) -> dict[str, dict]:
    lats = ",".join(str(lat) for lat, _ in POINTS.values())
    lons = ",".join(str(lon) for _, lon in POINTS.values())
    data = fetch_json(ARCHIVE, {"latitude": lats, "longitude": lons, "start_date": start.isoformat(), "end_date": end.isoformat(), "hourly": ",".join(HOURLY), "timezone": "America/Santiago"})
    return {name: entry["hourly"] for name, entry in zip(POINTS, data if isinstance(data, list) else [data])}


def daily_weather(hourly: dict) -> list[dict]:
    days = []
    rain_since_noon = 0.0
    for stamp, temp, rh, wind, rain in zip(hourly["time"], *(hourly[v] for v in HOURLY)):
        rain_since_noon += rain or 0.0
        moment = datetime.fromisoformat(stamp)
        if moment.hour != NOON or None in (temp, rh, wind):
            continue
        days.append({"day": moment.date(), "temp": temp, "rh": rh, "wind": wind, "rain": rain_since_noon})
        rain_since_noon = 0.0
    return days


def daily_rain(hourly: dict) -> dict[date, float]:
    totals: dict[date, float] = defaultdict(float)
    for stamp, rain in zip(hourly["time"], hourly["precipitation"]):
        totals[datetime.fromisoformat(stamp).date()] += rain or 0.0
    return totals


def fwi_series(days: list[dict]) -> dict[date, float]:
    codes = fwi.Codes()
    return {d["day"]: fwi.step(codes, d["temp"], d["rh"], d["wind"], d["rain"], d["day"].month) for d in days}


def window_key(end: date) -> str:
    return f"{end.month:02d}-{min(end.day, 28) if end.month == 2 else end.day:02d}"


def window_total(values: dict[date, float], end: date) -> float | None:
    window = [values.get(end - timedelta(days=i)) for i in range(WINDOW_DAYS)]
    return None if None in window else sum(window)


def window_mean(values: dict[date, float], end: date) -> float | None:
    total = window_total(values, end)
    return None if total is None else total / WINDOW_DAYS


def baseline() -> dict:
    hourly = fetch_hourly(BASELINE_START, date(BASELINE_YEARS[-1], 12, 31))
    result = {}
    for name, series in hourly.items():
        rain = daily_rain(series)
        fire = fwi_series(daily_weather(series))
        per_key: dict[str, dict] = {}
        for offset in range(366):
            end = date(2001, 1, 1) + timedelta(days=offset)
            key = window_key(end)
            if key in per_key:
                continue
            ends = [end.replace(year=y) for y in BASELINE_YEARS]
            totals = [t for t in (window_total(rain, e) for e in ends) if t is not None]
            fires = [f for f in (window_mean(fire, e) for e in ends) if f is not None]
            per_key[key] = {**spi.fit(totals), "fwi_mean": sum(fires) / len(fires)}
        result[name] = per_key
    return {"source": "ERA5 via Open-Meteo historical API", "period": f"{BASELINE_YEARS[0]}-{BASELINE_YEARS[-1]}", "window_days": WINDOW_DAYS, "points": result}


def latest_oni() -> dict | None:
    with urllib.request.urlopen(ONI, timeout=60) as response:
        rows = [line.split() for line in response.read().decode().splitlines()[1:] if line.strip()]
    if not rows:
        return None
    season, year, _, anomaly = rows[-1]
    return {"season": season, "year": int(year), "anomaly": float(anomaly), "source": ONI}


def current(normal: dict, today: date) -> dict:
    end = today - timedelta(days=1)
    hourly = fetch_hourly(end - timedelta(days=SPIN_UP_DAYS), end)
    points = {}
    for name, series in hourly.items():
        params = normal["points"][name][window_key(end)]
        total = window_total(daily_rain(series), end)
        fire = window_mean(fwi_series(daily_weather(series)), end)
        points[name] = {
            "rain_mm": None if total is None else round(total, 1),
            "spi": None if total is None else spi.index(total, params),
            "fwi": None if fire is None else round(fire, 1),
            "fwi_normal": round(params["fwi_mean"], 1),
        }
    spis = [p["spi"] for p in points.values() if p["spi"] is not None]
    fires = [p["fwi"] for p in points.values() if p["fwi"] is not None]
    region_spi = round(sum(spis) / len(spis), 2) if spis else None
    region_fwi = round(sum(fires) / len(fires), 1) if fires else None
    region_normal = round(sum(p["fwi_normal"] for p in points.values()) / len(points), 1)
    fire_first = region_fwi is not None and region_fwi > region_normal and (region_spi is None or region_spi < WET_SPI)
    for p in points.values():
        p["spi"] = None if p["spi"] is None else round(p["spi"], 2)
    return {
        "computed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "window_end": end.isoformat(),
        "window_days": WINDOW_DAYS,
        "lead": "incendios" if fire_first else "lluvia",
        "spi": region_spi,
        "fwi": region_fwi,
        "fwi_normal": region_normal,
        "oni": latest_oni(),
        "points": points,
        "rule": f"Incendios primero si el FWI medio de {WINDOW_DAYS} días supera su normal 1991-2020 y el SPI es menor que {WET_SPI:g}; si no, lluvia primero.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Monthly season signal for the Maule site: SPI (McKee 1993) and Canadian FWI (Van Wagner 1987) from ERA5")
    sub = parser.add_subparsers(dest="command", required=True)
    base = sub.add_parser("baseline", help="Compute the 1991-2020 normals once")
    base.add_argument("--out", type=Path, default=HERE / "baseline.json")
    now = sub.add_parser("current", help="Compute the signal for the last 30 days")
    now.add_argument("--baseline", type=Path, default=HERE / "baseline.json")
    now.add_argument("--out", type=Path, required=True)
    now.add_argument("--today", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    if args.command == "baseline":
        result = baseline()
    else:
        result = current(json.loads(args.baseline.read_text(encoding="utf-8")), args.today or datetime.now(UTC).date())
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
