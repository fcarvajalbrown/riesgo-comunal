from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

import httpx

from app.sources.base import Batch, IngestScope, ObservationRecord, RawPayload, SourceAdapter, SourceMeta

URL = "https://www.ioc-sealevelmonitoring.org/service.php"
STATIONS = {
    "const": ("Constitución", -35.355725, -72.457031),
    "boye": ("Boyeruca", -34.6873055, -72.05786),
}
HISTORY_MINUTES = 120
OSCILLATION_MINUTES = 60
HALF_WINDOW = 15


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def oscillation(series: list[tuple[datetime, float]], since: datetime) -> float | None:
    values = [v for _, v in series]
    residuals = [
        abs(values[i] - mean(values[i - HALF_WINDOW : i + HALF_WINDOW + 1]))
        for i in range(HALF_WINDOW, len(values) - HALF_WINDOW)
        if series[i][0] >= since
    ]
    return max(residuals) if residuals else None


def summarize(code: str, data: list[dict[str, Any]], now: datetime) -> list[ObservationRecord]:
    name, lat, lon = STATIONS[code]
    records = []
    for sensor in sorted({d.get("sensor") for d in data if d.get("sensor")}):
        series = sorted(
            (t, d["slevel"])
            for d in data
            if d.get("sensor") == sensor and d.get("slevel") is not None and (t := parse_time(d.get("stime"))) is not None
        )
        if not series:
            continue
        last_at, last_value = series[-1]
        base = {"station_external_id": f"{code}-{sensor}", "station_name": f"{name} (sensor {sensor})", "observed_at": last_at, "validation_status": "unvalidated", "lon": lon, "lat": lat}
        records.append(ObservationRecord(parameter="sea_level", parameter_name="Nivel del mar", value=round(last_value, 3), unit="m", **base))
        swing = oscillation(series, now - timedelta(minutes=OSCILLATION_MINUTES))
        if swing is not None:
            records.append(ObservationRecord(parameter="sea_level_oscillation", parameter_name="Oscilación máxima sin marea, última hora", value=round(swing, 3), unit="m", **base))
    return records


class IocSeaLevelAdapter(SourceAdapter):
    meta = SourceMeta(
        key="ioc_sea_level",
        name="IOC/UNESCO: mareógrafos de Constitución y Boyeruca (respaldo internacional)",
        organization="Sea Level Station Monitoring Facility, IOC/UNESCO y VLIZ; estaciones operadas en Chile por el SHOA",
        url="https://www.ioc-sealevelmonitoring.org/",
        license="Uso no comercial según el sitio de la IOC",
        commercial_use="No",
        cache_allowed="No verificado",
        authority="No es un aviso oficial; datos de mareógrafos en tiempo real sin validar",
        attribution="Fuente: IOC/UNESCO Sea Level Station Monitoring Facility (datos del SHOA)",
        interval_minutes=10,
    )

    def __init__(self, now: datetime | None = None):
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        start = now - timedelta(minutes=HISTORY_MINUTES)
        payloads = []
        for code in STATIONS:
            params = {"query": "data", "code": code, "timestart": f"{start:%Y-%m-%dT%H:%M}", "timestop": f"{now:%Y-%m-%dT%H:%M}", "format": "json"}
            response = client.get(URL, params=params)
            response.raise_for_status()
            payloads.append(RawPayload(dataset="sea_level", url=str(response.url), body=response.json(), options={"code": code, "now": now.isoformat()}))
        return payloads

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        now = datetime.fromisoformat(raw.options["now"])
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=summarize(raw.options["code"], parsed or [], now),
            transformation=f"Nivel del mar por minuto; oscilación = mayor diferencia con la media móvil de {2 * HALF_WINDOW + 1} minutos en los últimos {OSCILLATION_MINUTES} minutos",
        )
