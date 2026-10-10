import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.sources.base import Batch, EventRecord, IngestScope, RawPayload, SourceAdapter, SourceMeta

DAILY_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/America_Sul/focos_diario_{day}.csv"
COUNTRY = "Chile"
DAYS = 2


def parse_detections(text: str) -> list[dict[str, Any]]:
    detections = []
    for row in csv.DictReader(io.StringIO(text)):
        if (row.get("pais") or "").strip() != COUNTRY:
            continue
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
            seen = datetime.strptime(row["data_hora_gmt"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        frp = (row.get("frp") or "").strip()
        detections.append(
            {
                "id": row["id"].strip(),
                "lat": lat,
                "lon": lon,
                "seen": seen,
                "satellite": (row.get("satelite") or "").strip(),
                "comuna": (row.get("municipio") or "").strip(),
                "region": (row.get("estado") or "").strip(),
                "frp": float(frp) if frp else None,
            }
        )
    return detections


class InpeQueimadasAdapter(SourceAdapter):
    meta = SourceMeta(
        key="inpe_queimadas",
        name="INPE Queimadas: focos de calor por satélite en Sudamérica (respaldo internacional)",
        organization="Instituto Nacional de Pesquisas Espaciais (INPE), Brasil",
        url="https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/America_Sul/",
        license="Datos abiertos publicados por el INPE; licencia no confirmada",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="No es una fuente oficial chilena; detección satelital que no confirma un incendio en terreno",
        attribution="Fuente: INPE, programa Queimadas (Brasil)",
        interval_minutes=30,
    )

    def __init__(self, now: datetime | None = None):
        self.now = now

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        now = self.now or datetime.now(UTC)
        payloads = []
        for offset in range(DAYS):
            url = DAILY_URL.format(day=(now - timedelta(days=offset)).strftime("%Y%m%d"))
            response = client.get(url)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payloads.append(RawPayload(dataset="fire_detection", url=url, body=response.text))
        return payloads

    def parse(self, raw: RawPayload) -> Any:
        return parse_detections(raw.body)

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        records = [
            EventRecord(
                external_id=d["id"],
                hazard="fire_detection",
                occurred_at=d["seen"],
                lon=d["lon"],
                lat=d["lat"],
                magnitude=d["frp"],
                properties={"satellite": d["satellite"], "frp_mw": d["frp"], "inpe_area": d["comuna"], "inpe_region": d["region"]},
            )
            for d in parsed
        ]
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation="CSV diario de focos de calor de Sudamérica del INPE, solo filas con país Chile",
        )
