from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.sources.base import Batch, IngestScope, ObservationRecord, RawPayload, SourceAdapter, SourceMeta

URL = "https://www.ndbc.noaa.gov/data/realtime2/{buoy}.dart"
BUOYS = {
    "34420": ("Boya DART 34420, frente a Concepción", -35.758, -75.243),
    "32404": ("Boya DART 32404, frente a Valparaíso", -32.13, -73.797),
}
EVENT_TYPES = {2, 3}
EVENT_WINDOW_HOURS = 6


def parse_dart(text: str) -> list[dict[str, Any]]:
    readings = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            moment = datetime(*map(int, parts[:6]), tzinfo=UTC)
            readings.append({"at": moment, "type": int(parts[6]), "height": float(parts[7])})
        except ValueError:
            continue
    return sorted(readings, key=lambda r: r["at"])


def summarize(buoy: str, readings: list[dict[str, Any]], now: datetime) -> list[ObservationRecord]:
    if not readings:
        return []
    name, lat, lon = BUOYS[buoy]
    last = readings[-1]
    since = now - timedelta(hours=EVENT_WINDOW_HOURS)
    event = any(r["type"] in EVENT_TYPES for r in readings if r["at"] >= since)
    base = {"station_external_id": f"dart-{buoy}", "station_name": name, "observed_at": last["at"], "validation_status": "unvalidated", "lon": lon, "lat": lat}
    return [
        ObservationRecord(parameter="dart_height", parameter_name="Altura de la columna de agua", value=last["height"], unit="m", **base),
        ObservationRecord(parameter="dart_event_mode", parameter_name=f"Boya en modo evento en las últimas {EVENT_WINDOW_HOURS} horas", value=1.0 if event else 0.0, unit=None, **base),
    ]


class NdbcDartAdapter(SourceAdapter):
    meta = SourceMeta(
        key="ndbc_dart",
        name="NOAA DART: boyas de detección de tsunami frente a Chile central (respaldo internacional)",
        organization="NOAA National Data Buoy Center (EE.UU.)",
        url="https://www.ndbc.noaa.gov/dart/dart.shtml",
        license="Datos del Gobierno de EE.UU., dominio público",
        commercial_use="Sí",
        cache_allowed="Sí",
        authority="No es un aviso oficial chileno; sensores de presión en el fondo del océano",
        attribution="Fuente: NOAA National Data Buoy Center (boyas DART)",
        interval_minutes=15,
    )

    def __init__(self, now: datetime | None = None):
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        payloads = []
        for buoy in BUOYS:
            response = client.get(URL.format(buoy=buoy))
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payloads.append(RawPayload(dataset="sea_level", url=URL.format(buoy=buoy), body=response.text, options={"buoy": buoy, "now": now.isoformat()}))
        return payloads

    def parse(self, raw: RawPayload) -> Any:
        return parse_dart(raw.body)

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=summarize(raw.options["buoy"], parsed, datetime.fromisoformat(raw.options["now"])),
            transformation=f"Última altura de la columna de agua y si hubo mediciones de 1 minuto o 15 segundos (modo evento) en las últimas {EVENT_WINDOW_HOURS} horas",
        )
