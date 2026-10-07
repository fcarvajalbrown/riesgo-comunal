import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.sources.base import AlertRecord, Batch, IngestScope, RawPayload, SourceAdapter, SourceError, SourceMeta
from app.sources.senapred_alerts import fold

PAGE_URL = "https://www.snamchile.cl/index.php"
CHILE = ZoneInfo("America/Santiago")
ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")
BULLETIN_ID = re.compile(r"modalBol\((\d+)")
MAP_CALL = re.compile(r"modalMapa\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*'[^']*'\s*,\s*(-?[\d.]+)\s*,\s*'[^']*'\s*,\s*'([^']*)'")
DATE = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})")
COASTAL_SQL = """
    select c.external_id as cut from feature c
    where c.dataset = 'comuna_boundary'
      and exists (select 1 from feature f where f.dataset in ('tsunami_evacuation_area', 'tsunami_meeting_point') and st_intersects(f.geom, c.geom))
"""


@dataclass
class SnamEvent:
    bulletin_ids: list[int]
    occurred_at: datetime
    place: str
    states: list[str]
    bulletin_times: list[datetime]
    lat: float | None
    lon: float | None
    magnitude: float | None
    agency: str | None


def lines(cell: str) -> list[str]:
    parts = (" ".join(html.unescape(TAG.sub("", p)).split()) for p in BREAK.split(cell))
    return [p for p in parts if p]


def chile_time(text: str) -> datetime | None:
    match = DATE.search(text)
    if not match:
        return None
    day, month, year, hour, minute = (int(v) for v in match.groups())
    return datetime(year, month, day, hour, minute, tzinfo=CHILE)


def parse_table(page: str) -> list[SnamEvent]:
    events = []
    for row in ROW.findall(page):
        cells = CELL.findall(row)
        ids = [int(v) for v in BULLETIN_ID.findall(row)]
        if len(cells) < 5 or not ids:
            continue
        occurred = chile_time(TAG.sub("", cells[0]))
        times = [t for t in (chile_time(v) for v in lines(cells[2])) if t]
        states = lines(cells[3])
        if occurred is None or not states:
            continue
        mapped = MAP_CALL.search(row)
        lat, lon, magnitude, agency = (float(mapped[1]), float(mapped[2]), float(mapped[3]), mapped[4]) if mapped else (None, None, None, None)
        events.append(SnamEvent(ids, occurred, " ".join(lines(cells[1])), states, times, lat, lon, magnitude, agency))
    return events


def classify(state: str) -> str:
    folded = fold(state)
    if "cancel" in folded:
        return "cancel"
    if "alarma" in folded:
        return "Alarma"
    if "precaucion" in folded or "alerta" in folded:
        return "Alerta"
    if "informativ" in folded:
        return "Informativo"
    return "Alerta"


def to_records(events: list[SnamEvent], coastal_codes: list[str]) -> list[AlertRecord]:
    records = []
    for event in events:
        latest_state = event.states[-1]
        kind = classify(latest_state)
        issued = event.bulletin_times or [event.occurred_at]
        closed = kind in ("cancel", "Informativo")
        records.append(
            AlertRecord(
                external_id=f"snam-{min(event.bulletin_ids)}",
                issuer="SHOA (SNAM)",
                hazard="tsunami",
                level="Alerta" if kind == "cancel" else kind,
                title=f"{latest_state}: sismo {event.place}",
                description="; ".join(event.states),
                source_url=PAGE_URL,
                starts_at=issued[0],
                ends_at=issued[-1] if closed else None,
                area=None,
                properties={
                    "state": latest_state,
                    "bulletins": event.bulletin_ids,
                    "event_time": event.occurred_at.isoformat(),
                    "place": event.place,
                    "magnitude": event.magnitude,
                    "lat": event.lat,
                    "lon": event.lon,
                    "magnitude_agency": event.agency,
                    "last_update": issued[-1].isoformat(),
                    "read_from": "snamchile.cl (página pública del SNAM)",
                },
                area_cut_codes=tuple(coastal_codes),
            )
        )
    return records


class ShoaSnamAdapter(SourceAdapter):
    meta = SourceMeta(
        key="shoa_snam",
        name="SHOA: boletines del Sistema Nacional de Alarma de Maremotos (lectura de snamchile.cl)",
        organization="Servicio Hidrográfico y Oceanográfico de la Armada",
        url=PAGE_URL,
        license="Sin licencia publicada; se lee la tabla pública de boletines",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="Oficial: el SHOA es el organismo técnico del SNAM; esta lectura no es un servicio oficial de datos",
        attribution="Fuente: SHOA, Sistema Nacional de Alarma de Maremotos (snamchile.cl), leído automáticamente por la plataforma",
        interval_minutes=5,
    )

    def __init__(self, page: str | None = None):
        self.page = page

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        if self.page is not None:
            return [RawPayload(dataset="tsunami_bulletin", url=PAGE_URL, body=self.page)]
        agent = f"Mozilla/5.0 (compatible; {client.headers.get('User-Agent', 'riesgo-comunal')})"
        response = client.get(PAGE_URL, headers={"User-Agent": agent})
        response.raise_for_status()
        return [RawPayload(dataset="tsunami_bulletin", url=PAGE_URL, body=response.text)]

    def parse(self, raw: RawPayload) -> Any:
        events = parse_table(raw.body)
        if not events:
            raise SourceError("snamchile.cl no mostró la tabla de boletines; la página pudo cambiar")
        return events

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        from app.db import rows, transaction

        with transaction() as conn:
            coastal = [r["cut"] for r in rows(conn, COASTAL_SQL)]
        warnings = [] if coastal else ["sin comunas costeras: falta la capa de tsunami de SENAPRED"]
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=to_records(parsed, coastal),
            transformation="Tabla pública de boletines SNAM; estado del último boletín por evento; cobertura: comunas con capa de evacuación por tsunami",
            warnings=warnings,
        )
