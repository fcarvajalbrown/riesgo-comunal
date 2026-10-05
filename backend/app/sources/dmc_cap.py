import math
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from app.sources.base import AlertRecord, Batch, IngestScope, RawPayload, SourceAdapter, SourceError, SourceMeta

FEED_URL = "https://archivos.meteochile.gob.cl/portaldmc/rss/rss.php"
CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
LEVELS = ("Alarma", "Alerta", "Aviso")
HAZARD_WORDS = (
    ("marejada", "coastal"),
    ("tormenta", "storm"),
    ("precipitaci", "rain"),
    ("lluvia", "rain"),
    ("nieve", "snow"),
    ("helada", "frost"),
    ("calor", "heat"),
    ("temperatura", "heat"),
    ("viento", "wind"),
    ("incendio", "wildfire"),
)


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(f"RSS de la DMC inválido: {exc}")
    items = []
    for item in root.iter("item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "category": (item.findtext("category") or "").strip(),
                "guid": (item.findtext("guid") or "").strip(),
                "pub_date": (item.findtext("pubDate") or "").strip(),
            }
        )
    return [i for i in items if i["link"]]


def level_from(category: str, title: str) -> str:
    for level in LEVELS:
        if category.lower() == level.lower() or title.lower().startswith(level.lower()):
            return level
    return category or "Boletín"


def hazard_from(event: str) -> str:
    lowered = event.lower()
    for word, hazard in HAZARD_WORDS:
        if word in lowered:
            return hazard
    return "meteo"


def cap_polygon(text: str) -> list[list[float]] | None:
    ring = []
    for pair in text.split():
        lat, lon = pair.split(",")[:2]
        ring.append([float(lon), float(lat)])
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return [ring]


def cap_circle(text: str, segments: int = 48) -> list[list[float]] | None:
    try:
        center, radius = text.split()
        lat, lon = (float(v) for v in center.split(",")[:2])
        radius_km = float(radius)
    except ValueError:
        return None
    if radius_km <= 0:
        return None
    dlat = radius_km / 110.574
    dlon = radius_km / (111.320 * math.cos(math.radians(lat)))
    ring = [
        [lon + dlon * math.cos(2 * math.pi * i / segments), lat + dlat * math.sin(2 * math.pi * i / segments)]
        for i in range(segments)
    ]
    ring.append(ring[0])
    return [ring]


def parse_cap(xml_text: str, item: dict[str, str]) -> AlertRecord | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(f"CAP de la DMC inválido ({item['link']}): {exc}")
    identifier = root.findtext("cap:identifier", namespaces=CAP_NS)
    status = root.findtext("cap:status", namespaces=CAP_NS)
    if not identifier or status != "Actual":
        return None
    msg_type = root.findtext("cap:msgType", namespaces=CAP_NS) or "Alert"
    sent = root.findtext("cap:sent", namespaces=CAP_NS)
    references = root.findtext("cap:references", namespaces=CAP_NS) or ""
    supersedes = tuple(ref.split(",")[1] for ref in references.split() if ref.count(",") >= 2)
    info = root.find("cap:info", CAP_NS)
    if info is None:
        return None
    event = info.findtext("cap:event", default="", namespaces=CAP_NS)
    polygons = []
    zones = []
    for area in info.findall("cap:area", CAP_NS):
        zones.append(area.findtext("cap:areaDesc", default="", namespaces=CAP_NS))
        for polygon in area.findall("cap:polygon", CAP_NS):
            rings = cap_polygon(polygon.text or "")
            if rings:
                polygons.append(rings)
        for circle in area.findall("cap:circle", CAP_NS):
            rings = cap_circle(circle.text or "")
            if rings:
                polygons.append(rings)
    onset = info.findtext("cap:onset", namespaces=CAP_NS) or info.findtext("cap:effective", namespaces=CAP_NS) or sent
    expires = info.findtext("cap:expires", namespaces=CAP_NS)
    return AlertRecord(
        external_id=identifier,
        issuer="Dirección Meteorológica de Chile",
        hazard=hazard_from(event),
        level=level_from(item["category"], item["title"]),
        title=item["title"] or info.findtext("cap:headline", default=event, namespaces=CAP_NS),
        description=info.findtext("cap:description", namespaces=CAP_NS),
        source_url=info.findtext("cap:web", namespaces=CAP_NS) or item["link"],
        starts_at=datetime.fromisoformat(onset),
        ends_at=datetime.fromisoformat(expires) if expires else None,
        area={"type": "MultiPolygon", "coordinates": polygons} if polygons else None,
        properties={
            "event": event,
            "severity": info.findtext("cap:severity", namespaces=CAP_NS),
            "urgency": info.findtext("cap:urgency", namespaces=CAP_NS),
            "certainty": info.findtext("cap:certainty", namespaces=CAP_NS),
            "msg_type": msg_type,
            "sent": sent,
            "zones": zones,
            "cap_url": item["link"],
        },
        supersedes=supersedes,
        cancelled=msg_type == "Cancel",
    )


class DmcCapAdapter(SourceAdapter):
    meta = SourceMeta(
        key="dmc_cap",
        name="DMC: avisos, alertas y alarmas meteorológicas (CAP)",
        organization="Dirección Meteorológica de Chile",
        url=FEED_URL,
        license="El canal RSS declara «public domain»; feed CAP registrado ante la OMM (Register of Alerting Authorities)",
        commercial_use="Dominio público según el propio canal",
        cache_allowed="Sí",
        authority="Oficial: autoridad de alerta meteorológica de Chile ante la OMM",
        attribution="Fuente: Dirección Meteorológica de Chile (Sistema de Alerta Temprana)",
        interval_minutes=10,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        response = client.get(FEED_URL)
        response.raise_for_status()
        items = parse_feed(response.text)
        documents = []
        for item in items:
            cap = client.get(item["link"])
            if cap.status_code == 200:
                documents.append((item, cap.text))
        return [RawPayload(dataset="dmc_warning", url=FEED_URL, body=documents)]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        records = []
        warnings = []
        for item, xml_text in parsed:
            try:
                record = parse_cap(xml_text, item)
            except (SourceError, ValueError) as exc:
                warnings.append(str(exc))
                continue
            if record:
                records.append(record)
        records.sort(key=lambda r: str(r.properties.get("sent") or r.starts_at.isoformat()))
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation="RSS + documentos CAP 1.2; polígonos lat,lon convertidos a GeoJSON lon,lat",
            warnings=warnings,
        )
