import csv
import io
from datetime import UTC, datetime
from typing import Any

import httpx

from app.sources.base import Batch, EventRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta
from app.sources.usgs import CHILE_BBOX

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
FILES = {
    "viirs_noaa20": f"{BASE}/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv",
    "viirs_noaa21": f"{BASE}/noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_America_24h.csv",
    "viirs_snpp": f"{BASE}/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv",
    "modis": f"{BASE}/modis-c6.1/csv/MODIS_C6_1_South_America_24h.csv",
}
SATELLITE = {"N20": "NOAA-20", "N21": "NOAA-21", "N": "Suomi NPP", "T": "Terra", "A": "Aqua"}


def in_chile(lat: float, lon: float) -> bool:
    return CHILE_BBOX["minlatitude"] <= lat <= CHILE_BBOX["maxlatitude"] and CHILE_BBOX["minlongitude"] <= lon <= CHILE_BBOX["maxlongitude"]


def parse_firms(text: str) -> list[dict[str, Any]]:
    detections = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
            seen = datetime.strptime(f"{row['acq_date']} {row['acq_time'].zfill(4)}", "%Y-%m-%d %H%M").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        if not in_chile(lat, lon):
            continue
        frp = (row.get("frp") or "").strip()
        detections.append(
            {
                "lat": lat,
                "lon": lon,
                "seen": seen,
                "satellite": SATELLITE.get((row.get("satellite") or "").strip(), (row.get("satellite") or "").strip()),
                "confidence": (row.get("confidence") or "").strip(),
                "frp": float(frp) if frp else None,
                "daynight": (row.get("daynight") or "").strip(),
            }
        )
    return detections


class NasaFirmsAdapter(SourceAdapter):
    meta = SourceMeta(
        key="nasa_firms",
        name="NASA FIRMS: focos de calor VIIRS y MODIS (respaldo internacional)",
        organization="NASA Fire Information for Resource Management System (EE.UU.)",
        url=f"{BASE}/",
        license="Archivos públicos de NASA FIRMS; licencia no confirmada",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="No es una fuente oficial chilena; detección satelital que no confirma un incendio en terreno",
        attribution="Fuente: NASA FIRMS (VIIRS y MODIS)",
        interval_minutes=30,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        payloads = []
        for name, url in FILES.items():
            response = client.get(url)
            response.raise_for_status()
            payloads.append(RawPayload(dataset="fire_detection", url=url, body=response.text, options={"instrument": name}))
        return payloads

    def parse(self, raw: RawPayload) -> Any:
        return parse_firms(raw.body)

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        instrument = raw.options.get("instrument", "")
        records = [
            EventRecord(
                external_id=f"{instrument}-{d['seen']:%Y%m%d%H%M}-{d['lat']:.5f}-{d['lon']:.5f}",
                hazard="fire_detection",
                occurred_at=d["seen"],
                lon=d["lon"],
                lat=d["lat"],
                magnitude=d["frp"],
                properties={"satellite": d["satellite"], "frp_mw": d["frp"], "confidence": d["confidence"], "daynight": d["daynight"], "instrument": instrument},
            )
            for d in parsed
        ]
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation="CSV de 24 horas de Sudamérica de NASA FIRMS, filas dentro del rectángulo de Chile continental",
        )
