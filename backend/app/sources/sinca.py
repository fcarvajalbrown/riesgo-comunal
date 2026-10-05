import html
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.sources.base import (
    Batch,
    FeatureRecord,
    IngestScope,
    ObservationRecord,
    RawPayload,
    SourceAdapter,
    SourceMeta,
)

URL = "https://sinca.mma.gob.cl/index.php/json/listadomapa2k19/"
CHILE = ZoneInfo("America/Santiago")
VALUE_RE = re.compile(r"<strong>\s*([-+]?\d+(?:[.,]\d+)?)\s*(.*?)</strong>", re.IGNORECASE | re.DOTALL)


def parse_tooltip(tooltip: str) -> tuple[float | None, str | None]:
    text = html.unescape(tooltip or "")
    match = VALUE_RE.search(text)
    if not match:
        return None, None
    value = float(match.group(1).replace(",", "."))
    unit_html = match.group(2).replace("<sup>3</sup>", "³").replace("<sup>2</sup>", "²")
    unit = re.sub(r"<[^>]+>", "", unit_html).replace("⁄", "/").strip()
    return value, unit or None


def parse_local_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=CHILE)


class SincaAdapter(SourceAdapter):
    meta = SourceMeta(
        key="sinca",
        name="SINCA: calidad del aire en línea",
        organization="Ministerio del Medio Ambiente, Sistema de Información Nacional de Calidad del Aire",
        url=URL,
        license="Sin texto de licencia publicado en el portal",
        commercial_use="UNVERIFIED",
        cache_allowed="UNVERIFIED",
        authority="Oficial; datos en línea no validados",
        attribution="Fuente: SINCA, Ministerio del Medio Ambiente. Datos en línea no validados.",
        interval_minutes=60,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        response = client.get(URL)
        response.raise_for_status()
        body = response.json()
        return [RawPayload(dataset="aq_station", url=URL, body=body), RawPayload(dataset="aq_observation", url=URL, body=body)]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        if raw.dataset == "aq_station":
            records = [
                FeatureRecord(
                    external_id=str(s["key"]),
                    geometry={"type": "Point", "coordinates": [float(s["longitud"]), float(s["latitud"])]},
                    name=s.get("nombre"),
                    category=s.get("calificacion"),
                    properties={
                        "comuna_etiqueta": s.get("comuna"),
                        "red": s.get("red"),
                        "region": s.get("region"),
                        "empresa": s.get("empresa"),
                        "parametros": [r.get("code") for r in s.get("realtime", [])],
                    },
                )
                for s in parsed
                if s.get("latitud") is not None and s.get("longitud") is not None
            ]
            return Batch(dataset=raw.dataset, url=raw.url, records=records, transformation="Catálogo de estaciones desde el listado en línea")

        records = []
        latest: datetime | None = None
        for station in parsed:
            for series in station.get("realtime", []):
                for row in (series.get("info") or {}).get("rows", []):
                    cells = row.get("c", [])
                    if len(cells) < 4:
                        continue
                    value, unit = parse_tooltip(str(cells[3].get("v", "")))
                    if value is None:
                        continue
                    observed_at = parse_local_time(cells[0]["v"])
                    latest = max(latest, observed_at) if latest else observed_at
                    records.append(
                        ObservationRecord(
                            station_external_id=str(station["key"]),
                            station_name=station.get("nombre"),
                            parameter=series.get("code"),
                            parameter_name=html.unescape(series.get("name") or ""),
                            value=value,
                            unit=unit,
                            observed_at=observed_at,
                            validation_status="unvalidated",
                            lon=float(station["longitud"]),
                            lat=float(station["latitud"]),
                        )
                    )
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            source_time=latest,
            transformation="Concentración y unidad leídas del texto del tooltip de cada hora (el valor numérico del gráfico no es la concentración); hora local de Chile",
        )
