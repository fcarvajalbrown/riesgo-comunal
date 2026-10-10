import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from app.sources.base import Batch, IngestScope, ObservationRecord, RawPayload, SourceAdapter, SourceMeta

URL = "https://flood-api.open-meteo.com/v1/flood"
POINTS_FILE = Path(__file__).with_name("river_points.json")
FORECAST_DAYS = 7
PERIODS = ("2", "5", "20")


def river_points() -> dict[str, dict]:
    return json.loads(POINTS_FILE.read_text(encoding="utf-8"))["points"]


def member_peaks(daily: dict[str, list]) -> list[float]:
    peaks = []
    for key, values in daily.items():
        if key != "river_discharge" and not key.startswith("river_discharge_member"):
            continue
        clean = [v for v in values if v is not None]
        if clean:
            peaks.append(max(clean))
    return peaks


def summarize(cut: str, point: dict, daily: dict[str, list], now: datetime) -> list[ObservationRecord]:
    peaks = member_peaks(daily)
    if not peaks:
        return []
    today = next((v for v in daily.get("river_discharge", []) if v is not None), None)
    levels = point["thresholds"]["levels"]
    base = {"station_external_id": f"glofas-{cut}", "station_name": f"Río principal de {point['name']} (modelo GloFAS)", "observed_at": now, "validation_status": "forecast", "lon": point["lon"], "lat": point["lat"]}
    records = [
        ObservationRecord(parameter="glofas_members", parameter_name="Escenarios del pronóstico", value=float(len(peaks)), unit=None, **base),
        ObservationRecord(parameter="glofas_peak_median", parameter_name=f"Caudal máximo esperado en {FORECAST_DAYS} días (mediana de los escenarios)", value=round(median(peaks), 1), unit="m3/s", **base),
    ]
    if today is not None:
        records.append(ObservationRecord(parameter="glofas_discharge_today", parameter_name="Caudal de hoy según el modelo", value=round(today, 1), unit="m3/s", **base))
    for period in PERIODS:
        over = sum(1 for p in peaks if p >= levels[period])
        records.append(ObservationRecord(parameter=f"glofas_over_{period}y", parameter_name=f"Escenarios sobre el caudal de crecida de {period} años", value=float(over), unit=None, **base))
    return records


class GlofasFloodAdapter(SourceAdapter):
    meta = SourceMeta(
        key="glofas_flood",
        name="GloFAS: pronóstico de caudal de ríos (Copernicus, vía Open-Meteo)",
        organization="Copernicus Emergency Management Service, Global Flood Awareness System; servido por Open-Meteo",
        url="https://open-meteo.com/en/docs/flood-api",
        license="Datos de Copernicus GloFAS servidos por Open-Meteo",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="No es un aviso oficial chileno; modelo hidrológico global de 5 km",
        attribution="Fuente: Copernicus GloFAS, vía Open-Meteo",
        interval_minutes=180,
    )

    def __init__(self, now: datetime | None = None):
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        points = river_points()
        cuts = sorted(points)
        params = {
            "latitude": ",".join(str(points[c]["lat"]) for c in cuts),
            "longitude": ",".join(str(points[c]["lon"]) for c in cuts),
            "daily": "river_discharge",
            "ensemble": "true",
            "forecast_days": FORECAST_DAYS,
        }
        response = client.get(URL, params=params, timeout=120)
        response.raise_for_status()
        return [RawPayload(dataset="river_flow", url=str(response.url), body=response.json(), options={"cuts": cuts, "now": now.isoformat()})]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        points = river_points()
        entries = parsed if isinstance(parsed, list) else [parsed]
        now = datetime.fromisoformat(raw.options["now"])
        records = []
        for cut, entry in zip(raw.options["cuts"], entries):
            records.extend(summarize(cut, points[cut], entry.get("daily", {}), now))
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation=f"Pico de caudal de cada uno de los escenarios del pronóstico GloFAS en {FORECAST_DAYS} días, comparado con los caudales de crecida de 2, 5 y 20 años del río principal de cada comuna",
        )
