from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.sources.base import Batch, EventRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta

URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
CHILE_BBOX = {"minlatitude": -56.5, "maxlatitude": -17.0, "minlongitude": -76.5, "maxlongitude": -66.0}
BACKFILL_START_YEAR = 2000
BACKFILL_MIN_MAGNITUDE = 4.0
RECENT_MIN_MAGNITUDE = 2.5


class UsgsAdapter(SourceAdapter):
    meta = SourceMeta(
        key="usgs",
        name="USGS: catálogo de sismos (complementario)",
        organization="U.S. Geological Survey",
        url=URL,
        license="Dominio público (obra del Gobierno de EE.UU.)",
        commercial_use="Sí",
        cache_allowed="Sí",
        authority="Complementaria; la fuente oficial chilena es el Centro Sismológico Nacional",
        attribution="Fuente: USGS (complementario, no es la fuente oficial chilena)",
        interval_minutes=15,
    )

    def __init__(self, backfill: bool = False, now: datetime | None = None):
        self.backfill = backfill
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        windows = []
        if self.backfill:
            for year in range(BACKFILL_START_YEAR, now.year + 1):
                windows.append((datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC), BACKFILL_MIN_MAGNITUDE))
        windows.append((now - timedelta(days=30), now, RECENT_MIN_MAGNITUDE))
        payloads = []
        for start, end, min_mag in windows:
            params = {
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                "minmagnitude": min_mag,
                "orderby": "time",
                **CHILE_BBOX,
            }
            response = client.get(URL, params=params)
            response.raise_for_status()
            payloads.append(RawPayload(dataset="earthquake", url=str(response.url), body=response.json()))
        return payloads

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        records = []
        for f in parsed.get("features", []):
            p = f.get("properties") or {}
            lon, lat, depth = (f.get("geometry") or {}).get("coordinates", [None, None, None])[:3]
            if p.get("time") is None or lon is None:
                continue
            records.append(
                EventRecord(
                    external_id=str(f.get("id")),
                    hazard="earthquake",
                    occurred_at=datetime.fromtimestamp(p["time"] / 1000, tz=UTC),
                    lon=lon,
                    lat=lat,
                    magnitude=p.get("mag"),
                    depth_km=depth,
                    place=p.get("place"),
                    properties={"mag_type": p.get("magType"), "status": p.get("status"), "url": p.get("url"), "tsunami": p.get("tsunami")},
                )
            )
        generated = (parsed.get("metadata") or {}).get("generated")
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            source_time=datetime.fromtimestamp(generated / 1000, tz=UTC) if generated else None,
            transformation="FDSN event GeoJSON, rectángulo de Chile continental",
        )
