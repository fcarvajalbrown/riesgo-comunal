from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.sources.base import Batch, IngestScope, ObservationRecord, RawPayload, SourceAdapter, SourceMeta

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_HOURS = 48
PARAMETERS = {
    "om_rain_24h_max": ("Lluvia máxima en 24 horas pronosticada para las próximas 48 horas", "mm"),
    "om_gust_max": ("Ráfaga máxima pronosticada para las próximas 48 horas", "km/h"),
    "om_temp_max": ("Temperatura máxima pronosticada para las próximas 48 horas", "°C"),
}


def forecast_points(scope: IngestScope) -> list[tuple[float, float]]:
    return sorted({(round((y0 + y1) / 2, 3), round((x0 + x1) / 2, 3)) for x0, y0, x1, y1 in scope.bboxes})


def summarize(hourly: dict[str, list], now: datetime) -> dict[str, float | None]:
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=HORIZON_HOURS)
    window = [
        i
        for i, stamp in enumerate(hourly.get("time", []))
        if start <= datetime.fromisoformat(stamp).replace(tzinfo=UTC) < end
    ]

    def values(name: str) -> list[float]:
        series = hourly.get(name) or []
        return [series[i] for i in window if i < len(series) and series[i] is not None]

    rain = values("precipitation")
    rain_24h = max((sum(rain[i : i + 24]) for i in range(max(len(rain) - 23, 1))), default=None) if rain else None
    gusts = values("wind_gusts_10m")
    temps = values("temperature_2m")
    return {
        "om_rain_24h_max": round(rain_24h, 1) if rain_24h is not None else None,
        "om_gust_max": max(gusts) if gusts else None,
        "om_temp_max": max(temps) if temps else None,
    }


class OpenMeteoAdapter(SourceAdapter):
    meta = SourceMeta(
        key="open_meteo",
        name="Open-Meteo: pronóstico de lluvia, viento y temperatura por coordenadas",
        organization="Open-Meteo (modelos meteorológicos nacionales e internacionales)",
        url="https://open-meteo.com",
        license="Datos CC BY 4.0; API gratuita para uso no comercial, el uso comercial requiere un plan pagado de Open-Meteo",
        commercial_use="No sin plan pagado",
        cache_allowed="UNVERIFIED",
        authority="Pronóstico de modelo internacional, no es un aviso oficial",
        attribution="Weather data by Open-Meteo.com (https://open-meteo.com/), CC BY 4.0",
        interval_minutes=60,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        points = forecast_points(scope)
        if not points:
            return []
        params = {
            "latitude": ",".join(str(lat) for lat, _ in points),
            "longitude": ",".join(str(lon) for _, lon in points),
            "hourly": "precipitation,wind_gusts_10m,temperature_2m",
            "forecast_days": 3,
            "timezone": "GMT",
        }
        response = client.get(URL, params=params)
        response.raise_for_status()
        body = response.json()
        return [RawPayload(dataset="weather_forecast", url=URL, body=body if isinstance(body, list) else [body], options={"points": points})]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        issued = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=forecast_records(parsed, raw.options["points"], issued),
            source_time=issued,
            transformation="Máximos de las próximas 48 horas calculados desde el pronóstico horario en el centro de cada comuna",
        )


def forecast_records(parsed: list[dict], points: list[tuple[float, float]], issued: datetime) -> list[ObservationRecord]:
    records = []
    for (lat, lon), item in zip(points, parsed):
        for parameter, value in summarize(item.get("hourly") or {}, issued).items():
            if value is None:
                continue
            name, unit = PARAMETERS[parameter]
            records.append(
                ObservationRecord(
                    station_external_id=f"{lat:.3f},{lon:.3f}",
                    station_name=f"Punto de pronóstico {lat:.2f}, {lon:.2f}",
                    parameter=parameter,
                    parameter_name=name,
                    value=float(value),
                    unit=unit,
                    observed_at=issued,
                    validation_status="forecast",
                    lon=lon,
                    lat=lat,
                )
            )
    return records
