import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import flood_stats
from app.db import get_engine, rows

FLOOD = "https://flood-api.open-meteo.com/v1/flood"
CELL = 0.05
OFFSET = 0.025
BATCH = 100
RECENT_DAYS = 31
HISTORY_START = date(1997, 1, 1)
PERIODS = (2, 5, 20)
OUT = HERE.parents[1] / "backend" / "app" / "sources" / "river_points.json"

CELLS_SQL = """
with cells as (
    select m.cut_code, m.name, x, y
    from municipality m,
         generate_series((floor((st_xmin(m.boundary) - :off) / :cell) * :cell + :off)::numeric, st_xmax(m.boundary)::numeric, (:cell)::numeric) as x,
         generate_series((floor((st_ymin(m.boundary) - :off) / :cell) * :cell + :off)::numeric, st_ymax(m.boundary)::numeric, (:cell)::numeric) as y
    where m.cut_code like :region
)
select c.cut_code, c.name, round(c.x::numeric, 3)::float as lon, round(c.y::numeric, 3)::float as lat
from cells c join municipality m on m.cut_code = c.cut_code
where st_contains(m.boundary, st_setsrid(st_makepoint(c.x::float, c.y::float), 4326))
order by c.cut_code
"""


def get(params: dict) -> object:
    url = f"{FLOOD}?{urllib.parse.urlencode(params)}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(60 * (attempt + 1))
    raise RuntimeError("unreachable")


def as_list(data: object) -> list[dict]:
    return data if isinstance(data, list) else [data]


def mean_recent_flow(cells: list[dict]) -> list[float]:
    flows = []
    for start in range(0, len(cells), BATCH):
        batch = cells[start : start + BATCH]
        data = get({"latitude": ",".join(str(c["lat"]) for c in batch), "longitude": ",".join(str(c["lon"]) for c in batch), "daily": "river_discharge", "past_days": RECENT_DAYS, "forecast_days": 1})
        for entry in as_list(data):
            values = [v for v in entry["daily"]["river_discharge"] if v is not None]
            flows.append(sum(values) / len(values) if values else 0.0)
    return flows


def annual_maxima(lat: float, lon: float, last_year: int) -> dict[int, float]:
    data = as_list(get({"latitude": lat, "longitude": lon, "daily": "river_discharge", "start_date": HISTORY_START.isoformat(), "end_date": f"{last_year}-12-31"}))[0]
    peaks: dict[int, float] = defaultdict(float)
    for day, value in zip(data["daily"]["time"], data["daily"]["river_discharge"]):
        if value is not None:
            peaks[int(day[:4])] = max(peaks[int(day[:4])], value)
    return dict(peaks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Main GloFAS river cell per comuna and its 2/5/20-year flood thresholds (Gumbel L-moments, Mann-Kendall + Sen's slope)")
    parser.add_argument("--region", default="07")
    parser.add_argument("--present-year", type=int, default=date.today().year)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    with get_engine().connect() as conn:
        cells = rows(conn, CELLS_SQL, region=f"{args.region}%", cell=CELL, off=OFFSET)
    flows = mean_recent_flow(cells)
    best: dict[str, dict] = {}
    for cell, flow in zip(cells, flows):
        if cell["cut_code"] not in best or flow > best[cell["cut_code"]]["recent_mean_m3s"]:
            best[cell["cut_code"]] = {"name": cell["name"], "lat": cell["lat"], "lon": cell["lon"], "recent_mean_m3s": round(flow, 2)}
    for cut, point in sorted(best.items()):
        maxima = annual_maxima(point["lat"], point["lon"], args.present_year - 1)
        point["thresholds"] = flood_stats.thresholds(maxima, args.present_year, PERIODS)
        print(cut, point["name"], point["recent_mean_m3s"], point["thresholds"]["levels"], "trend" if point["thresholds"]["nonstationary"] else "")
    result = {
        "source": "GloFAS river discharge via the Open-Meteo Flood API",
        "method": "Main river = GloFAS 0.05 degree cell inside the comuna with the largest mean discharge over the last 31 days. Annual maxima from 1997, where the GloFAS history served by Open-Meteo begins; Mann-Kendall trend test at 5%; if significant, maxima moved to the present year with Sen's slope; Gumbel fit by L-moments; 2, 5 and 20-year return levels.",
        "cells_sampled": len(cells),
        "points": best,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
