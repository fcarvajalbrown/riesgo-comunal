from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.sources.base import Batch, EventRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta
from app.sources.usgs import CHILE_BBOX, RECENT_MIN_MAGNITUDE

URL = "https://www.seismicportal.eu/fdsnws/event/1/query"
DETAILS_URL = "https://www.seismicportal.eu/eventdetails.html?unid="
WINDOW_DAYS = 30


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class EmscAdapter(SourceAdapter):
    meta = SourceMeta(
        key="emsc",
        name="EMSC: catálogo de sismos (complementario, incluye soluciones del CSN)",
        organization="Euro-Mediterranean Seismological Centre",
        url=URL,
        license="CC BY 4.0",
        commercial_use="Sí, con atribución",
        cache_allowed="Sí",
        authority="Complementaria; reúne soluciones de agencias nacionales, entre ellas el Centro Sismológico Nacional de Chile",
        attribution="Fuente: EMSC (seismicportal.eu), CC BY 4.0",
        interval_minutes=15,
    )

    def __init__(self, now: datetime | None = None):
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        params = {
            "format": "json",
            "start": (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%S"),
            "end": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmag": RECENT_MIN_MAGNITUDE,
            "minlat": CHILE_BBOX["minlatitude"],
            "maxlat": CHILE_BBOX["maxlatitude"],
            "minlon": CHILE_BBOX["minlongitude"],
            "maxlon": CHILE_BBOX["maxlongitude"],
            "orderby": "time",
        }
        response = client.get(URL, params=params)
        if response.status_code == 204:
            return [RawPayload(dataset="earthquake", url=str(response.url), body={"features": []})]
        response.raise_for_status()
        return [RawPayload(dataset="earthquake", url=str(response.url), body=response.json())]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        records = []
        for f in parsed.get("features", []):
            p = f.get("properties") or {}
            occurred = parse_time(p.get("time"))
            if occurred is None or p.get("lon") is None or p.get("lat") is None:
                continue
            unid = p.get("unid") or f.get("id")
            records.append(
                EventRecord(
                    external_id=str(unid),
                    hazard="earthquake",
                    occurred_at=occurred,
                    lon=p["lon"],
                    lat=p["lat"],
                    magnitude=p.get("mag"),
                    depth_km=p.get("depth"),
                    place=(p.get("flynn_region") or "").title() or None,
                    properties={"mag_type": p.get("magtype"), "author": p.get("auth"), "url": f"{DETAILS_URL}{unid}"},
                )
            )
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation="FDSN event JSON de EMSC, rectángulo de Chile continental",
        )
