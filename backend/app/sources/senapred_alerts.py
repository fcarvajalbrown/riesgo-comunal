import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.sources.base import AlertRecord, Batch, IngestScope, RawPayload, SourceAdapter, SourceError, SourceMeta

PAGE_URL = "https://senapred.cl/alertas"
CHILE = ZoneInfo("America/Santiago")
MAX_PAGES = 5
LEVELS = ("Alerta Roja", "Alerta Amarilla", "Alerta Temprana Preventiva")
ACTIONS = (
    ("se cancela", "cancel"),
    ("se declara", "declare"),
    ("monitoreo", "monitor"),
    ("se mantiene", "monitor"),
    ("se modifica", "modify"),
    ("se actualiza", "modify"),
    ("se amplia", "modify"),
    ("se extiende", "modify"),
    ("se reduce", "modify"),
    ("se eleva", "modify"),
    ("se rebaja", "modify"),
)
HAZARDS = (
    ("tsunami", "tsunami"),
    ("volcan", "volcanic"),
    ("incendio", "wildfire"),
    ("remocion", "landslide"),
    ("aluvion", "landslide"),
    ("crecida", "flood"),
    ("desborde", "flood"),
    ("inundacion", "flood"),
    ("marejada", "coastal"),
    ("sismo", "earthquake"),
    ("viento", "wind"),
    ("calor", "heat"),
    ("temperatura", "heat"),
    ("meteorologic", "meteo"),
    ("precipitacion", "rain"),
    ("nevazon", "snow"),
)
DATE = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})")
SLUG_TIME = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})$")
SCOPE = re.compile(r"\bpara\s+(.+?),?\s+por\s+(.+)$", re.IGNORECASE)
SCOPE_KEYWORD = re.compile(r"(?:\b(?:la|las|el|los)\s+)?\b(regiones|region|provincias|provincia|comunas|comuna)\b(?:\s+(?:de|del))?\s+")
QUALIFIER = re.compile(r"\s+en\s+(?:la|el)\s+(?:region|provincia)\b.*$")
TRAILING = re.compile(r"(?:,|\s)+(?:y|para|y\s+para|en)?\s*$")
KIND = {"region": "region", "regiones": "region", "provincia": "provincia", "provincias": "provincia", "comuna": "comuna", "comunas": "comuna"}

CARDS_SCRIPT = """
() => Array.from(document.querySelectorAll('.amplify-card')).map((card) => ({
  text: card.innerText,
  links: Array.from(card.querySelectorAll('a[href]')).map((a) => a.href),
}))
"""


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.replace("´", "").replace("'", "").replace("’", ""))
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).lower().split())


@dataclass
class Bulletin:
    link: str
    title: str
    action: str
    level: str | None
    scopes: list[tuple[str, list[str]]]
    reason: str
    hazard: str
    published_at: datetime


def parse_scope(text: str) -> list[tuple[str, list[str]]]:
    folded = fold(text)
    if "nacional" in folded or "todo el pais" in folded:
        return [("nacional", [])]
    matches = list(SCOPE_KEYWORD.finditer(folded))
    scopes = []
    for index, match in enumerate(matches):
        if folded[: match.start()].endswith("en "):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(folded)
        segment = QUALIFIER.sub("", folded[match.end() : end])
        segment = TRAILING.sub("", segment).strip(" ,")
        names = [n.strip() for n in re.split(r",\s*|\s+y\s+", segment) if n.strip()]
        if names:
            scopes.append((KIND[match.group(1)], names))
    return scopes


def parse_card(text: str, link: str) -> Bulletin | None:
    lines = [line.strip() for line in text.replace("​", "").splitlines() if line.strip()]
    if not lines or not link:
        return None
    title = lines[0]
    date_match = next((DATE.search(line) for line in lines if DATE.search(line)), None)
    if not date_match:
        return None
    day, month, year, hour, minute = (int(v) for v in date_match.groups())
    published = datetime(year, month, day, hour, minute, tzinfo=CHILE)
    folded = fold(title)
    action = next((value for prefix, value in ACTIONS if folded.startswith(prefix)), "update")
    level = next((lvl for lvl in LEVELS if fold(lvl) in folded), None)
    scope_text, reason = "", ""
    match = SCOPE.search(title)
    if match:
        scope_text, reason = match.group(1), match.group(2)
    folded_reason = fold(reason)
    hazard = next((value for word, value in HAZARDS if word in folded_reason), "other")
    return Bulletin(link, title, action, level, parse_scope(scope_text), reason, hazard, published)


def declared_at(link: str) -> datetime | None:
    match = SLUG_TIME.search(link.rstrip("/"))
    if not match:
        return None
    year, month, day, hour, minute, second = (int(v) for v in match.groups())
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=CHILE)
    except ValueError:
        return None


def match_cut_codes(scopes: list[tuple[str, list[str]]], comunas: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    for kind, names in scopes:
        if kind == "nacional":
            return [c["cut"] for c in comunas]
        field_name = {"region": "region", "provincia": "provincia", "comuna": "name"}[kind]
        wanted = [fold(n) for n in names]
        for comuna in comunas:
            value = fold(comuna.get(field_name) or "")
            if not value or comuna["cut"] in codes:
                continue
            if field_name == "name":
                if value in wanted:
                    codes.append(comuna["cut"])
            elif any(w == value or (len(w) > 3 and (w in value or value in w)) for w in wanted):
                codes.append(comuna["cut"])
    return codes


def lifecycle(bulletins: list[Bulletin]) -> dict[str, list[Bulletin]]:
    threads: dict[str, list[Bulletin]] = {}
    for bulletin in bulletins:
        threads.setdefault(bulletin.link, []).append(bulletin)
    for items in threads.values():
        items.sort(key=lambda b: b.published_at)
    return threads


def to_records(bulletins: list[Bulletin], comunas: list[dict[str, Any]]) -> tuple[list[AlertRecord], list[str]]:
    records: list[AlertRecord] = []
    warnings: list[str] = []
    for link, items in lifecycle(bulletins).items():
        latest = items[-1]
        level = next((b.level for b in reversed(items) if b.level), None)
        codes = match_cut_codes(latest.scopes, comunas)
        if not codes:
            warnings.append(f"sin cobertura reconocida: {latest.title}")
        start = declared_at(link) or items[0].published_at
        records.append(
            AlertRecord(
                external_id=link.rstrip("/").rsplit("/", 1)[-1],
                issuer="SENAPRED",
                hazard=latest.hazard,
                level=level or "Alerta",
                title=latest.title,
                description="; ".join(f"{b.published_at:%d-%m-%Y %H:%M}: {b.title}" for b in items),
                source_url=link,
                starts_at=start,
                ends_at=latest.published_at if latest.action == "cancel" else None,
                area=None,
                properties={
                    "event": latest.reason,
                    "action": latest.action,
                    "scopes": [{"kind": k, "names": n} for k, n in latest.scopes],
                    "last_update": latest.published_at.isoformat(),
                    "listing": PAGE_URL,
                    "read_from": "senapred.cl/alertas (página pública)",
                },
                area_cut_codes=tuple(codes),
            )
        )
    return records, warnings


def render_cards(max_pages: int = MAX_PAGES, timeout_ms: int = 60000) -> list[dict[str, Any]]:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                page.goto(PAGE_URL, wait_until="networkidle", timeout=timeout_ms)
                page.wait_for_selector(".amplify-card", timeout=timeout_ms)
                for _ in range(max_pages):
                    batch = page.evaluate(CARDS_SCRIPT)
                    fresh = [c for c in batch if (c["text"], tuple(c["links"])) not in seen]
                    if not fresh:
                        break
                    for card in fresh:
                        seen.add((card["text"], tuple(card["links"])))
                    cards.extend(fresh)
                    following = page.get_by_text(">>", exact=True)
                    if following.count() == 0:
                        break
                    following.first.click()
                    page.wait_for_timeout(2500)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise SourceError(f"No se pudo leer senapred.cl/alertas: {exc}")
    return cards


NOT_FOUND_TEXT = "pagina no encontrada"
UNAVAILABLE_FLAG = "pagina_oficial_no_disponible"


def page_missing(body_text: str) -> bool:
    return NOT_FOUND_TEXT in fold(body_text or "")


def check_pages(urls: list[str], timeout_ms: int = 30000) -> dict[str, bool]:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    results: dict[str, bool] = {}
    if not urls:
        return results
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for url in urls:
                try:
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                    page.wait_for_timeout(2000)
                    results[url] = page_missing(page.inner_text("body"))
                except PlaywrightError:
                    continue
        finally:
            browser.close()
    return results


def flag_records(records: list[AlertRecord], checks: dict[str, bool]) -> None:
    for record in records:
        if record.source_url in checks:
            record.properties[UNAVAILABLE_FLAG] = checks[record.source_url]


def probe() -> dict[str, Any]:
    cards = render_cards(max_pages=2)
    return {"cards": len(cards), "parsed": [parse_card(c["text"], (c["links"] or [""])[0]) for c in cards[:6]]}


class SenapredAlertsAdapter(SourceAdapter):
    meta = SourceMeta(
        key="senapred_alertas",
        name="SENAPRED: alertas vigentes (lectura de senapred.cl/alertas)",
        organization="Servicio Nacional de Prevención y Respuesta ante Desastres",
        url=PAGE_URL,
        license="Sin licencia publicada; se lee la página pública como la vería un visitante",
        commercial_use="No verificado",
        cache_allowed="No verificado",
        authority="Oficial: SENAPRED declara las alertas; esta lectura no es un servicio oficial",
        attribution="Fuente: SENAPRED (senapred.cl/alertas), leído automáticamente por la plataforma",
        interval_minutes=10,
        requires=("senapred_alerts_enabled",),
    )

    def __init__(self, cards: list[dict[str, Any]] | None = None):
        self.cards = cards

    def fetch(self, client: httpx.Client, scope: IngestScope) -> list[RawPayload]:
        cards = self.cards if self.cards is not None else render_cards()
        if not cards:
            raise SourceError("senapred.cl/alertas no mostró alertas; la página pudo cambiar")
        checks: dict[str, bool] = {}
        if self.cards is None:
            from app.db import rows, transaction

            with transaction() as conn:
                urls = [
                    r["source_url"]
                    for r in rows(
                        conn,
                        """
                        select distinct source_url from alert
                        where source_key = 'senapred_alertas' and source_url is not null and (ends_at is null or ends_at > now())
                        """,
                    )
                ]
            checks = check_pages(urls)
        return [RawPayload(dataset="senapred_alert", url=PAGE_URL, body=cards, options={"page_checks": checks})]

    def normalize(self, raw: RawPayload, parsed: Any) -> Batch:
        from app.db import rows, transaction

        bulletins = []
        warnings = []
        for card in parsed:
            link = (card.get("links") or [""])[0]
            bulletin = parse_card(card.get("text", ""), link)
            if bulletin:
                bulletins.append(bulletin)
            else:
                warnings.append(f"tarjeta no reconocida: {card.get('text', '')[:80]}")
        with transaction() as conn:
            comunas = rows(
                conn,
                "select external_id as cut, name, properties->>'region' as region, properties->>'provincia' as provincia from feature where dataset = 'comuna_boundary'",
            )
        records, more = to_records(bulletins, comunas)
        checks = raw.options.get("page_checks") or {}
        flag_records(records, checks)
        if checks:
            from sqlalchemy import text

            with transaction() as conn:
                for url, missing in checks.items():
                    conn.execute(
                        text(
                            """
                            update alert set properties = coalesce(properties, '{}'::jsonb) || jsonb_build_object(cast(:flag as text), cast(:missing as boolean))
                            where source_key = 'senapred_alertas' and source_url = :url
                            """
                        ),
                        {"flag": UNAVAILABLE_FLAG, "missing": missing, "url": url},
                    )
        return Batch(
            dataset=raw.dataset,
            url=raw.url,
            records=records,
            transformation="Página pública renderizada con navegador sin interfaz; tarjetas agrupadas por enlace de declaración; cobertura desde límites DPA",
            warnings=warnings + more,
        )
