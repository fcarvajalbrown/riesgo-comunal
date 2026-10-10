import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.sources.base import AlertRecord, Batch, IngestScope, RawPayload, SourceAdapter, SourceError, SourceMeta

GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
PTWC_FEEDS = ("https://www.tsunami.gov/events/xml/PHEBAtom.xml", "https://www.tsunami.gov/events/xml/PAAQAtom.xml")
GDACS_NS = {"gdacs": "http://www.gdacs.org", "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
NEAR_DEG = 1.0
PTWC_WINDOW_HOURS = 12
SOUTH_AMERICA_PACIFIC = (-120.0, -60.0, -65.0, 5.0)
GDACS_HAZARD = {"EQ": "earthquake", "FL": "flood", "WF": "wildfire", "VO": "volcanic", "DR": "drought", "TC": "cyclone", "TS": "tsunami"}
GDACS_LEVEL = {"Green": "GDACS verde", "Orange": "GDACS naranja", "Red": "GDACS roja"}
GDACS_HAZARD_NAME = {
    "EQ": "sismo",
    "FL": "inundación",
    "WF": "incendio forestal",
    "VO": "actividad volcánica",
    "DR": "sequía",
    "TC": "ciclón tropical",
    "TS": "tsunami",
}
GDACS_MEANING = {
    "Green": "Nivel verde: se espera un impacto bajo.",
    "Orange": "Nivel naranja: podría causar un desastre local.",
    "Red": "Nivel rojo: se espera un desastre grave.",
}
GDACS_ISSUER = "Lo emite GDACS, un sistema de la Comisión Europea y la ONU. En Chile, las alertas oficiales son las de SENAPRED y, para tsunamis, las del SHOA."
PTWC_ISSUER = "Lo emite el Centro de Alerta de Tsunamis del Pacífico (NOAA, Estados Unidos). En Chile, las alertas oficiales de tsunami son las del SHOA y SENAPRED."
PTWC_LEVEL = {
    "Warning": "PTWC alerta de tsunami",
    "Threat": "PTWC amenaza de tsunami",
    "Advisory": "PTWC aviso de tsunami",
    "Watch": "PTWC vigilancia de tsunami",
    "Information": "PTWC información",
}
CATEGORY = re.compile(r"Category:[|\s]*([^|]+?)\s*\|", re.IGNORECASE)
MAGNITUDE = re.compile(r"Preliminary Magnitude:[|\s]*([\d.]+)", re.IGNORECASE)
NOTE = re.compile(r"Note:[|\s]*([^|]*)", re.IGNORECASE)
BULLETIN_PATH = re.compile(r"/events/([A-Z]+)/\d{4}/\d{2}/\d{2}/([^/]+)/(\d+)/")


def international_label(publisher: str) -> str:
    return f"Fuente internacional ({publisher}), no reemplaza el aviso oficial de SENAPRED ni del SHOA"


def _root(xml_text: str, name: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text.lstrip("﻿"))
    except ET.ParseError as exc:
        raise SourceError(f"{name} inválido: {exc}")


def _rfc822(value: str | None) -> datetime | None:
    try:
        return parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None


def parse_gdacs(xml_text: str) -> list[dict[str, Any]]:
    items = []
    for item in _root(xml_text, "RSS de GDACS").iter("item"):
        text = lambda path: (item.findtext(path, namespaces=GDACS_NS) or "").strip()
        try:
            lat, lon = float(text("geo:Point/geo:lat")), float(text("geo:Point/geo:long"))
        except ValueError:
            continue
        bbox = [float(v) for v in text("gdacs:bbox").split()] if len(text("gdacs:bbox").split()) == 4 else None
        items.append(
            {
                "guid": text("guid"),
                "title": text("title"),
                "description": text("description"),
                "link": text("link"),
                "event_type": text("gdacs:eventtype"),
                "event_name": text("gdacs:eventname"),
                "alert_level": text("gdacs:alertlevel"),
                "is_current": text("gdacs:iscurrent").lower() == "true",
                "country": text("gdacs:country"),
                "iso3": text("gdacs:iso3"),
                "lat": lat,
                "lon": lon,
                "bbox": bbox,
                "from_date": _rfc822(text("gdacs:fromdate")),
                "to_date": _rfc822(text("gdacs:todate")),
                "modified": _rfc822(text("gdacs:datemodified")),
            }
        )
    return [i for i in items if i["guid"] and i["from_date"]]


def _near(lon: float, lat: float, boxes: tuple[tuple[float, float, float, float], ...], margin: float) -> bool:
    return any(x0 - margin <= lon <= x1 + margin and y0 - margin <= lat <= y1 + margin for x0, y0, x1, y1 in boxes)


def gdacs_relevant(item: dict[str, Any], boxes: tuple[tuple[float, float, float, float], ...]) -> bool:
    codes = [c.strip().upper() for c in re.split(r"[,;\s]+", item["iso3"]) if c.strip()]
    if "CHL" in codes or "chile" in item["country"].lower():
        return True
    return not codes and _near(item["lon"], item["lat"], boxes, NEAR_DEG)


def bbox_polygon(bbox: list[float]) -> dict[str, Any]:
    x0, x1, y0, y1 = bbox
    return {"type": "MultiPolygon", "coordinates": [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]]}


def gdacs_record(item: dict[str, Any]) -> AlertRecord:
    label = international_label("GDACS")
    level = GDACS_LEVEL.get(item["alert_level"], f"GDACS {item['alert_level'] or 'sin nivel'}")
    area = bbox_polygon(item["bbox"]) if item["bbox"] else bbox_polygon([item["lon"] - NEAR_DEG, item["lon"] + NEAR_DEG, item["lat"] - NEAR_DEG, item["lat"] + NEAR_DEG])
    return AlertRecord(
        external_id=item["guid"],
        issuer="GDACS (Comisión Europea y Naciones Unidas)",
        hazard=GDACS_HAZARD.get(item["event_type"], "other"),
        level=level,
        title=f"Aviso internacional: {GDACS_HAZARD_NAME.get(item['event_type'], 'evento')} en {item['country'] or 'la zona'}",
        description=f"{GDACS_MEANING.get(item['alert_level'], 'Nivel sin informar.')} {GDACS_ISSUER}",
        source_url=item["link"],
        starts_at=item["from_date"],
        ends_at=None if item["is_current"] else (item["modified"] or item["to_date"]),
        area=area,
        properties={
            "international": True,
            "notice": label,
            "alert_level": item["alert_level"],
            "event_type": item["event_type"],
            "event_name": item["event_name"],
            "country": item["country"],
            "lat": item["lat"],
            "lon": item["lon"],
            "sent": (item["modified"] or item["from_date"]).isoformat(),
        },
    )


class GdacsAdapter(SourceAdapter):
    meta = SourceMeta(
        key="gdacs",
        name="GDACS: alertas mundiales de desastres (respaldo internacional)",
        organization="Global Disaster Alert and Coordination System (Comisión Europea y Naciones Unidas)",
        url=GDACS_URL,
        license="El canal RSS declara «public domain»; los términos de gdacs.org advierten que la información es indicativa",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="No es una fuente oficial chilena; respaldo internacional que no reemplaza a SENAPRED ni al SHOA",
        attribution="Fuente internacional: GDACS (gdacs.org), no reemplaza el aviso oficial",
        interval_minutes=15,
    )

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        response = client.get(GDACS_URL)
        response.raise_for_status()
        return [RawPayload(dataset="gdacs_alert", url=GDACS_URL, body=response.text, options={"scoped": False, "boxes": scope.bboxes})]

    def parse(self, raw: RawPayload) -> Any:
        return parse_gdacs(raw.body)

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        boxes = raw.options.get("boxes") or ()
        records = [gdacs_record(item) for item in parsed if gdacs_relevant(item, boxes)]
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation=f"RSS de GDACS; se conservan eventos con Chile en país/ISO3 o, sin país, a menos de {NEAR_DEG}° de una comuna; área = gdacs:bbox",
        )


def parse_ptwc(xml_text: str) -> list[dict[str, Any]]:
    entries = []
    for entry in _root(xml_text, "Atom del PTWC").findall("atom:entry", ATOM_NS):
        summary_el = entry.find("atom:summary", ATOM_NS)
        summary = ET.tostring(summary_el, encoding="unicode") if summary_el is not None else ""
        links = {link.get("title"): link.get("href", "").strip() for link in entry.findall("atom:link", ATOM_NS)}
        bulletin = links.get("Bulletin", "")
        path = BULLETIN_PATH.search(bulletin)
        try:
            lat = float(entry.findtext("geo:lat", namespaces=ATOM_NS) or "")
            lon = float(entry.findtext("geo:long", namespaces=ATOM_NS) or "")
            updated = datetime.fromisoformat((entry.findtext("atom:updated", namespaces=ATOM_NS) or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if not path:
            continue
        summary_text = re.sub(r"<[^>]+>", "|", re.sub(r"\s+", " ", summary))
        category = CATEGORY.search(summary_text)
        magnitude = MAGNITUDE.search(summary_text)
        note = NOTE.search(summary_text)
        entries.append(
            {
                "center": path.group(1),
                "event_id": path.group(2),
                "number": int(path.group(3)),
                "title": (entry.findtext("atom:title", namespaces=ATOM_NS) or "").strip(),
                "category": category.group(1).strip() if category else "",
                "magnitude": float(magnitude.group(1)) if magnitude else None,
                "note": note.group(1).strip() if note else "",
                "lat": lat,
                "lon": lon,
                "updated": updated,
                "bulletin_url": bulletin,
                "cap_url": links.get("CapXML document", ""),
            }
        )
    return entries


def ptwc_relevant(entry: dict[str, Any], bulletin_text: str) -> bool:
    x0, y0, x1, y1 = SOUTH_AMERICA_PACIFIC
    return x0 <= entry["lon"] <= x1 and y0 <= entry["lat"] <= y1 or "CHILE" in bulletin_text.upper()


def ptwc_record(entry: dict[str, Any], coastal_codes: list[str]) -> AlertRecord:
    label = international_label("PTWC, NOAA")
    prefix = f"{entry['center']}-{entry['event_id']}"
    cancelled = entry["category"].lower().startswith("cancel")
    level = PTWC_LEVEL.get(entry["category"], f"PTWC {entry['category'] or 'sin categoría'}")
    magnitude = f" (magnitud preliminar {entry['magnitude']})" if entry["magnitude"] else ""
    return AlertRecord(
        external_id=f"{prefix}-{entry['number']}",
        issuer="Pacific Tsunami Warning Center / National Tsunami Warning Center (NOAA, EE.UU.)",
        hazard="tsunami",
        level=level,
        title=f"Aviso internacional de tsunami tras un sismo{magnitude}",
        description=PTWC_ISSUER,
        source_url=entry["bulletin_url"],
        starts_at=entry["updated"],
        ends_at=entry["updated"] + timedelta(hours=PTWC_WINDOW_HOURS),
        area=None,
        properties={
            "international": True,
            "notice": label,
            "category": entry["category"],
            "magnitude": entry["magnitude"],
            "lat": entry["lat"],
            "lon": entry["lon"],
            "cap_url": entry["cap_url"],
            "sent": entry["updated"].isoformat(),
        },
        supersedes=tuple(f"{prefix}-{n}" for n in range(1, entry["number"])),
        cancelled=cancelled,
        area_cut_codes=tuple(coastal_codes),
    )


def coastal_cut_codes() -> list[str]:
    from app.db import rows, transaction

    with transaction() as conn:
        found = rows(
            conn,
            """
            select distinct c.external_id as cut from feature c
            where c.dataset = 'comuna_boundary'
              and exists (select 1 from feature t where t.dataset = 'tsunami_evacuation_area' and st_intersects(t.geom, c.geom))
            """,
        ) or rows(conn, "select external_id as cut from feature where dataset = 'comuna_boundary'")
    return [r["cut"] for r in found]


class PtwcAdapter(SourceAdapter):
    meta = SourceMeta(
        key="ptwc_tsunami",
        name="PTWC / NTWC: mensajes de tsunami (respaldo internacional)",
        organization="NOAA National Weather Service, Pacific Tsunami Warning Center y National Tsunami Warning Center",
        url="https://www.tsunami.gov/",
        license="Dominio público según el aviso legal del National Weather Service (weather.gov/disclaimer)",
        commercial_use="Sí, «para cualquier fin lícito» sin presentarlo como material oficial modificado",
        cache_allowed="Sí",
        authority="No es una fuente oficial chilena; el SHOA y SENAPRED emiten las alertas de tsunami en Chile",
        attribution="Fuente internacional: NOAA PTWC/NTWC (tsunami.gov), no reemplaza el aviso oficial del SHOA",
        interval_minutes=5,
    )

    def __init__(self, coastal_codes: list[str] | None = None):
        self.coastal_codes = coastal_codes

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        documents = []
        for url in PTWC_FEEDS:
            response = client.get(url)
            response.raise_for_status()
            for entry in parse_ptwc(response.text):
                bulletin = client.get(entry["bulletin_url"])
                documents.append((entry, bulletin.text if bulletin.status_code == 200 else ""))
        return [RawPayload(dataset="ptwc_message", url=" ".join(PTWC_FEEDS), body=documents)]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        relevant = [entry for entry, text in parsed if ptwc_relevant(entry, text)]
        codes = self.coastal_codes if self.coastal_codes is not None else (coastal_cut_codes() if relevant else [])
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=[ptwc_record(entry, codes) for entry in relevant],
            transformation=(
                "Atom de PTWC y NTWC más el boletín de texto; se conservan mensajes con epicentro frente a Sudamérica o que nombran Chile; "
                f"cobertura = comunas con áreas de evacuación por tsunami; vigencia {PTWC_WINDOW_HOURS} h desde la emisión"
            ),
        )
