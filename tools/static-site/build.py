import argparse
import json
import unicodedata

import httpx
import shutil
import sys
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.api.layers import layer_geojson
from app.api.routes import public_comuna, public_sources, public_summary
from app.db import get_engine, rows

CHILE = ZoneInfo("America/Santiago")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

LEVELS = {
    "CRITICO": ("#b42318", "#ffffff", "Crítico"),
    "ALTO": ("#d4590f", "#ffffff", "Alto"),
    "MODERADO": ("#e3b505", "#2a1a00", "Moderado"),
    "BAJO": ("#2f7d4a", "#ffffff", "Bajo"),
    "INFORMATIVO": ("#2b5ea7", "#ffffff", "Informativo"),
    "SIN_DATOS": ("#8a929c", "#ffffff", "Sin datos"),
}

WARNING_TONE = {
    "Alarma": "tone-red",
    "Alerta": "tone-orange",
    "Aviso": "tone-yellow",
    "Alerta Roja": "tone-red",
    "Alerta Amarilla": "tone-yellow",
    "Alerta Temprana Preventiva": "tone-green",
}

SOURCE_STATE = {
    "live": ("Funcionando", "#166534"),
    "stale": ("Sin datos nuevos", "#92400e"),
    "failed": ("Falla", "#991b1b"),
    "pending": ("Aún sin datos", "#334155"),
    "unconfigured": ("No configurada", "#475569"),
}

MAP_LAYERS = [
    ("tsunami_evacuation_area", "Área de evacuación por tsunami", "SENAPRED", True, '<span class="sq" style="background:rgba(37,99,235,.3);border:1px solid #1d4ed8"></span>'),
    ("tsunami_meeting_point", "Puntos de encuentro por tsunami", "SENAPRED", True, '<span class="dot" style="background:#059669"></span>'),
    ("dmc_warning", "Avisos y alertas meteorológicas vigentes", "Dirección Meteorológica de Chile", True, '<span class="sq" style="background:#eab308"></span>'),
    ("wildfire_hazard", "Recurrencia de incendios forestales", "SENAPRED con datos de CONAF", True, '<span class="sq" style="background:linear-gradient(90deg,#fde68a,#9a3412)"></span>'),
]

OFFICIAL_LINKS = [
    ("SENAPRED", "Servicio Nacional de Prevención y Respuesta ante Desastres", "https://senapred.cl"),
    ("Alertas vigentes de SENAPRED", "Listado oficial de alertas declaradas", "https://senapred.cl/alertas"),
    ("SHOA", "Servicio Hidrográfico y Oceanográfico de la Armada, alertas de tsunami", "https://www.shoa.cl"),
    ("Dirección Meteorológica de Chile", "Pronósticos, avisos, alertas y alarmas meteorológicas", "https://www.meteochile.gob.cl"),
]

LIVE_LAYERS = [
    ("lluvia", "Lluvia medida por satélite, último dato con unas 4 horas de retraso", "NASA, GPM IMERG", '<span class="sq" style="background:linear-gradient(90deg,#9bd5ff,#1f5bff,#b000c8)"></span>'),
    ("viento", "Viento ahora: flechas con su dirección y velocidad", "Open-Meteo", '<span class="sq" style="background:#0f172a;clip-path:polygon(50% 0,100% 50%,62% 50%,62% 100%,38% 100%,38% 50%,0 50%)"></span>'),
]

WIND_STEP = 0.1
WIND_BATCH = 100

EMERGENCY_PHONES = [("131", "Ambulancia (SAMU)"), ("132", "Bomberos"), ("133", "Carabineros")]

PROVINCES = {"071": "Provincia de Talca", "073": "Provincia de Curicó", "074": "Provincia de Linares", "072": "Provincia de Cauquenes"}

FAVICON = "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%23e42827%27/%3E%3Cpath d=%27M16 5 29 27H3z%27 fill=%27%23ffffff%27/%3E%3Crect x=%2714.5%27 y=%2712%27 width=%273%27 height=%278%27 fill=%27%23e42827%27/%3E%3Crect x=%2714.5%27 y=%2722%27 width=%273%27 height=%273%27 fill=%27%23e42827%27/%3E%3C/svg%3E"

ASSETS = ["maplibre-gl.js", "maplibre-gl-shared.js", "maplibre-gl-worker.js", "maplibre-gl.css", "MAPLIBRE-LICENSE.txt", "og-maule.png", "icon-180.png", "icon-32.png"]
SITE_NAME = "Riesgo en mi comuna, Región del Maule"
INITIATIVE = "Una iniciativa de la oficina de la senadora Paulina Vodanovic."

REGION_SQL = """
select slug, name, cut_code as cut, st_asgeojson(st_simplifypreservetopology(boundary, 0.001), 5) as g
from municipality where cut_code like '07%'
"""

EXTENT_SQL = """
select st_xmin(e) as x0, st_ymin(e) as y0, st_xmax(e) as x1, st_ymax(e) as y1
from (select st_extent(boundary) as e from municipality where cut_code like '07%') t
"""

STYLE = """
:root{--bg:#f4f5f7;--surface:#ffffff;--fg:#1b2430;--muted:#5b6573;--border:#dde1e7;--brand:#1f4e79;--senator:#e42827;--senator-deep:#d6152a}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,"Segoe UI",system-ui,-apple-system,Roboto,sans-serif;font-size:16px;line-height:1.5}
a{color:inherit}
a:focus-visible,input:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
h1,h2,h3,p{margin:0}
ul{list-style:none;margin:0;padding:0}
.senator{background:var(--senator);color:#fff;border-bottom:3px solid var(--senator-deep)}
.senator .in{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:.25rem 1.5rem;padding:.55rem 1rem}
.senator strong{font-size:clamp(1rem,1.9vw,1.35rem);font-weight:700}
.senator span{font-size:.85rem}
.in{max-width:72rem;margin:0 auto}
.muni{background:var(--brand);color:#fff}
.muni .in{display:flex;align-items:center;gap:.8rem;padding:1rem}
.initials{display:flex;align-items:center;justify-content:center;width:3rem;height:3rem;border-radius:.6rem;background:rgba(255,255,255,.15);font-weight:700;font-size:1.1rem;flex:none}
.muni h1{font-size:1.25rem;font-weight:600;line-height:1.2}
.muni p{font-size:.9rem;opacity:.9}
.muni nav{margin-left:auto;font-size:.9rem}
.wrap{max-width:72rem;margin:0 auto;padding:1rem}
.notice{border:1px solid var(--border);background:var(--surface);color:var(--fg);border-radius:.75rem;padding:.6rem .75rem;font-size:.88rem}
.rain{border:2px solid #1d4ed8}
.rain h2{color:#1d4ed8}
.outlook{font-size:.95rem;margin-bottom:.6rem}
.down{background:var(--fg);color:#fff;border-radius:.75rem;padding:.8rem 1rem;margin-bottom:.75rem;font-size:.95rem}
.grid{display:grid;gap:1rem;margin-top:1rem;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);align-items:start}
.grid2{display:grid;gap:1rem;margin-top:1rem;grid-template-columns:1fr 1fr}
.card{background:var(--surface);border:1px solid var(--border);border-radius:1rem;padding:1.1rem 1.25rem}
.card+.card{margin-top:1rem}
.card h2{font-size:1.125rem;font-weight:600;margin-bottom:.75rem}
.card h3{font-size:.9rem;font-weight:600;margin:1rem 0 .5rem;display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
.now{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-bottom:.75rem;font-size:.95rem}
.pill{display:inline-block;border-radius:999px;padding:.1rem .65rem;font-size:.8rem;font-weight:600;white-space:nowrap}
.pill-out{border:1px solid currentColor;background:transparent}
.tag{display:inline-block;border-radius:.4rem;border:1px solid var(--border);background:#f8fafc;color:var(--muted);padding:.05rem .45rem;font-size:.72rem;font-weight:500}
.tag-official{border-color:#fecdd3;background:#fff1f2;color:#be123c}
.alerts li{border:1px solid;border-radius:.75rem;padding:.75rem;font-size:.9rem;margin-bottom:.5rem}
.alerts .head{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
.alerts .title{font-weight:600;margin-top:.3rem}
.alerts .small{font-size:.78rem}
.alerts .origin{font-size:.78rem;opacity:.8;margin-top:.2rem}
.alerts a{font-size:.78rem;font-weight:600;display:inline-block;margin-top:.25rem}
.tone-red{border-color:#fca5a5;background:#fef2f2;color:#450a0a}
.tone-orange{border-color:#fdba74;background:#fff7ed;color:#431407}
.tone-yellow{border-color:#fde047;background:#fefce8;color:#422006}
.tone-green{border-color:#86efac;background:#f0fdf4;color:#052e16}
.calm{border:1px solid var(--border);background:#f8fafc;border-radius:.75rem;padding:.75rem;font-size:.9rem}
.calm p+p{color:var(--muted);margin-top:.25rem}
.note{font-size:.78rem;color:var(--muted);margin-top:.6rem}
.rows{border:1px solid var(--border);border-radius:.75rem;overflow:hidden}
.rows li{display:flex;gap:.75rem;align-items:flex-start;padding:.7rem .8rem;font-size:.9rem;border-top:1px solid var(--border)}
.rows li:first-child{border-top:0}
.rows .pill{flex:none;min-width:6.5rem;text-align:center}
.rows strong{font-weight:600}
.mapcard{position:sticky;top:1rem;height:calc(100vh - 2rem);min-height:28rem;display:flex;flex-direction:column;padding:0;overflow:hidden}
.map{flex:1;min-height:0}
.map-error::after{content:"No se pudo cargar el mapa base. Revise la conexión a internet.";display:block;padding:1rem;font-size:.9rem;color:#991b1b}
.toggles{border-top:1px solid var(--border);padding:.7rem 1rem;display:grid;gap:.35rem;font-size:.85rem}
.toggles label{display:flex;gap:.5rem;align-items:center;cursor:pointer}
.toggles .src{color:var(--muted);font-size:.75rem}
.sq{display:inline-block;width:.8rem;height:.8rem;border-radius:2px;flex:none}
.dot{display:inline-block;width:.8rem;height:.8rem;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px #059669;flex:none}
.phones{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem}
.phones a{display:flex;flex-direction:column;align-items:center;border:1px solid var(--border);border-radius:.75rem;padding:.75rem;text-decoration:none;text-align:center}
.phones a:hover{background:#f8fafc}
.phones strong{font-size:1.6rem;color:var(--brand);line-height:1.2}
.phones span{font-size:.78rem;color:var(--muted)}
.links li{padding:.5rem 0;border-top:1px solid var(--border);font-size:.9rem}
.links li:first-child{border-top:0}
.links a{font-weight:600;color:var(--brand)}
.links span{display:block;font-size:.78rem;color:var(--muted)}
.src-list li{padding:.45rem 0;border-top:1px solid var(--border);font-size:.85rem}
.src-list li:first-child{border-top:0}
.src-list span{display:block;font-size:.75rem;color:var(--muted)}
.foot{max-width:72rem;margin:0 auto;padding:1rem 1rem 2.5rem;font-size:.78rem;color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;padding:.6rem 1rem;border-top:1px solid var(--border);font-size:.82rem}
.intro{font-size:.9rem;color:var(--muted);margin-bottom:.75rem}
.comunas-line{font-size:.78rem;margin-top:.2rem}
.legend li{display:flex;align-items:center;gap:.35rem}
.prov{margin-top:1rem}
.prov h2{font-size:.95rem;font-weight:600;color:var(--muted);margin-bottom:.5rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(12.5rem,1fr));gap:.5rem}
.tile{display:flex;flex-direction:column;gap:.35rem;height:100%;background:var(--surface);border:1px solid var(--border);border-radius:.75rem;padding:.7rem .8rem;text-decoration:none}
.tile:hover{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand)}
.tile strong{font-size:1rem;font-weight:600}
.tile .count{font-size:.8rem;color:var(--muted)}
.tile .first{font-size:.78rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
body.fit{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
.region{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,3fr) minmax(22rem,2fr);gap:1rem;padding:1rem}
.region .mapcard{position:relative;top:0;height:100%;min-height:0}
.side{overflow-y:auto;min-height:0;padding-right:.25rem}
.side .card+.card,.side .card+.notice,.side .down+.card{margin-top:1rem}
@media (max-width:960px){
body.fit{height:auto;overflow:visible}
.region{grid-template-columns:1fr}
.region .mapcard{height:70vh}
.side{overflow:visible}
.grid,.grid2{grid-template-columns:1fr}
.mapcard{position:relative;top:0;height:70vh}
.muni nav{display:none}
}
"""


def as_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def format_time(value) -> str:
    moment = as_datetime(value)
    if moment is None:
        return "sin fecha"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(CHILE)
    return f"{local:%d-%m-%Y, %H:%M} hora de Chile ({moment.astimezone(UTC):%H:%M} UTC)"


def generated_label(moment: datetime) -> str:
    local = moment.astimezone(CHILE)
    return f"{local.day} de {MONTHS[local.month - 1]} de {local.year} a las {local:%H:%M}"


def level_style(level: str) -> tuple[str, str, str]:
    return LEVELS.get(level, LEVELS["SIN_DATOS"])


def level_pill(level: str, label: str | None = None) -> str:
    background, foreground, default_label = level_style(level)
    return f'<span class="pill" style="background:{background};color:{foreground}">{escape(label or default_label)}</span>'


def share_tags(base_url: str, path: str, title: str, description: str, root: str) -> str:
    tags = [
        f'<meta name="description" content="{escape(description)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{escape(SITE_NAME)}">',
        '<meta property="og:locale" content="es_CL">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(base_url)}/{escape(path)}">',
        f'<meta property="og:image" content="{escape(base_url)}/assets/og-maule.png">',
        '<meta property="og:image:type" content="image/png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{escape(SITE_NAME)}. {escape(INITIATIVE)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<link rel="icon" type="image/png" sizes="32x32" href="{root}assets/icon-32.png">',
        f'<link rel="apple-touch-icon" href="{root}assets/icon-180.png">',
        '<meta name="theme-color" content="#e42827">',
    ]
    return "".join(tag + "\n" for tag in tags)


def page(title: str, body: str, body_class: str = "", head: str = "") -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="icon" href="{FAVICON}">
{head}<style>{STYLE}</style>
</head>
<body class="{body_class}">
{body}
</body>
</html>
"""


EL_NINO_SOURCE = "https://www.emol.com/noticias/Nacional/2026/07/28/1206898/lluvias-primavera-efecto-el-nino.html"
RAIN_WORDS = ("precipit", "lluvi", "temporal", "crecida", "inundac", "desborde", "sistema frontal", "aguacero")


def plain(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c)).lower()


def is_rain(alert: dict) -> bool:
    return any(word in plain(alert["title"]) for word in RAIN_WORDS)


def rain_card(alerts_html_text: str, outlook: str | None, title: str) -> str:
    forecast = f'<p class="outlook"><strong>Pronóstico:</strong> {escape(outlook)}</p>' if outlook else ""
    season = (
        '<p class="note" style="margin:.6rem 0 0"><strong>Temporada de El Niño:</strong> la Dirección Meteorológica de Chile proyecta lluvias sobre lo normal en el centro-sur del país. '
        f'<a href="{EL_NINO_SOURCE}" rel="noreferrer">Fuente</a></p>'
    )
    return f'<section class="card rain" aria-labelledby="lluvia"><h2 id="lluvia">{escape(title)}</h2>{forecast}{alerts_html_text}{season}</section>'


def senapred_status(sources: list[dict], summaries: list[dict]) -> str | None:
    if any(s["key"] == "senapred_alertas" and s["state"] in ("failed", "stale", "pending") for s in sources):
        return "La página de alertas de SENAPRED no está respondiendo."
    if any(a.get("official_page_unavailable") for summary in summaries for a in summary["alerts"]):
        return "La página oficial de una alerta vigente de SENAPRED no está respondiendo."
    return None


def down_banner(headline: str | None) -> str:
    if not headline:
        return ""
    return (
        f'<p class="down" role="status"><strong>{escape(headline)}</strong> '
        "La información no puede esperar: aquí está nuestra evaluación del riesgo, calculada con todas las fuentes que sí responden.</p>"
    )


def senator_bar(generated: str) -> str:
    return f'<div class="senator"><div class="in"><strong>Una iniciativa de la oficina de la senadora Paulina Vodanovic</strong><span>Última actualización: {escape(generated)}</span></div></div>'


def alert_item(alert: dict, comunas: list[str] | None = None) -> str:
    timing = f"{'desde' if alert['in_force'] else 'comienza'} {format_time(alert['starts_at'])}"
    if alert["ends_at"]:
        timing += f", hasta {format_time(alert['ends_at'])}"
    unavailable = alert.get("official_page_unavailable")
    label = "Intentar abrir el anuncio oficial" if unavailable else "Ver el anuncio oficial"
    link = f'<a href="{escape(alert["source_url"])}" rel="noreferrer">{label}</a>' if alert["source_url"] else ""
    if unavailable:
        link = '<p class="comunas-line"><strong>La página oficial de esta alerta no responde en senapred.cl.</strong> Se mantiene vigente hasta que SENAPRED publique un nuevo boletín.</p>' + link
    where = ""
    if comunas is not None:
        where = f'<p class="comunas-line"><strong>Comunas:</strong> {escape("todas las comunas de la región" if len(comunas) >= 30 else ", ".join(comunas))}</p>'
    return (
        f'<li class="{WARNING_TONE.get(alert["level"], "tone-red")}">'
        f'<p class="head"><span class="pill pill-out">{escape(alert["level"])}</span><span class="small">{"Vigente" if alert["in_force"] else "Próximo"}</span><span class="tag tag-official">Alerta oficial</span></p>'
        f'<p class="title">{escape(alert["title"])}</p>'
        f'<p class="small">{escape(alert["issuer"])}, {escape(timing)}</p>{where}'
        f'<p class="origin">Origen: {escape(alert["origin"])}.</p>{link}</li>'
    )


def no_alerts_html() -> str:
    return (
        '<div class="calm"><p><strong>No hay avisos ni alertas oficiales registrados en este momento.</strong></p>'
        "<p>Que no aparezca una alerta no significa que no exista peligro. Confirme en senapred.cl.</p></div>"
    )


def alerts_html(summary: dict) -> str:
    if not summary["alerts"]:
        return no_alerts_html()
    return f'<ul class="alerts">{"".join(alert_item(a) for a in summary["alerts"])}</ul>'


def region_alerts_html(entries: list[tuple[str, str, dict]]) -> str:
    grouped: dict[tuple, tuple[dict, list[str]]] = {}
    for _, name, summary in entries:
        for alert in summary["alerts"]:
            key = (alert["title"], alert["issuer"], alert["level"], str(alert["starts_at"]))
            grouped.setdefault(key, (alert, []))[1].append(name)
    if not grouped:
        return no_alerts_html()
    ordered = sorted(grouped.values(), key=lambda pair: (not pair[0]["in_force"], -len(pair[1])))
    return f'<ul class="alerts">{"".join(alert_item(alert, names) for alert, names in ordered)}</ul>'


def sources_html(sources: list[dict]) -> str:
    alert_sources = [s for s in sources if s["alert"]]
    data_sources = [s for s in sources if not s["alert"]]
    alert_down = [s for s in alert_sources if s["state"] in ("failed", "stale")]
    alert_up = [s for s in alert_sources if s["state"] == "live"]
    data_down = [s for s in data_sources if s["state"] != "live"]

    def last_data(source: dict) -> str:
        return format_time(source["last_success_at"]) if source["last_success_at"] else "nunca"

    def names(group: list[dict]) -> str:
        return ", ".join(s["name"] for s in group)

    out = ['<h3>Estado de las fuentes</h3>']
    if alert_down:
        tail = f"Siguen funcionando: {names(alert_up)}." if alert_up else "Ninguna fuente de alertas responde ahora; consulte senapred.cl y los canales de su municipalidad."
        out.append(f'<p class="calm" style="margin-bottom:.5rem">Sin respuesta reciente: {escape(names(alert_down))}. {escape(tail)}</p>')
    out.append('<ul class="src-list">')
    for source in alert_sources:
        label, colour = SOURCE_STATE[source["state"]]
        out.append(f'<li><strong>{escape(source["name"])}</strong>: <strong style="color:{colour}">{escape(label)}</strong><span>Último dato recibido: {escape(last_data(source))}</span></li>')
    out.append(f"<li><strong>Otras fuentes de datos</strong>: {len(data_sources) - len(data_down)} de {len(data_sources)} funcionando.</li></ul>")
    return "".join(out)


def items_html(items: list[dict], with_level: bool = True) -> str:
    rows_html = "".join(
        f'<li>{level_pill(item["level"], item["level_label"]) if with_level else ""}<span><strong>{escape(item["hazard"])}.</strong> {escape(item["headline"])}</span></li>'
        for item in items
    )
    return f'<ul class="rows">{rows_html}</ul>'


def toggles_html(counts: dict[str, int], has_wind: bool) -> str:
    live = "".join(
        f'<label><input type="checkbox" data-layer="{key}" checked>{swatch}<span>{escape(name)}<span class="src"> ({escape(source)})</span></span></label>'
        for key, name, source, swatch in LIVE_LAYERS
        if key != "viento" or has_wind
    )
    data = "".join(
        f'<label><input type="checkbox" data-layer="{key}"{" checked" if on else ""}>{swatch}<span>{escape(name)}<span class="src"> ({escape(source)})</span></span></label>'
        for key, name, source, on, swatch in MAP_LAYERS
        if counts.get(key)
    )
    return f'<div class="toggles">{live}{data}<span class="src">Toque un punto o una zona del mapa para ver qué es.</span></div>'


def map_html(bbox, counts: dict[str, int], has_wind: bool) -> str:
    wind = ' data-wind="../assets/viento.json"' if has_wind else ""
    return (
        f'<div class="card mapcard"><div class="map" data-map data-layers="capas/"{wind} data-bbox="{escape(json.dumps(list(bbox)))}" role="region" aria-label="Mapa de la comuna"></div>'
        f"{toggles_html(counts, has_wind)}</div>"
    )


def wind_grid(extent: dict) -> dict:
    points = []
    lat = extent["y0"]
    while lat <= extent["y1"] + 1e-9:
        lon = extent["x0"]
        while lon <= extent["x1"] + 1e-9:
            points.append((round(lat, 3), round(lon, 3)))
            lon += WIND_STEP
        lat += WIND_STEP
    body: list[dict] = []
    try:
        for i in range(0, len(points), WIND_BATCH):
            chunk = points[i : i + WIND_BATCH]
            response = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": ",".join(str(a) for a, _ in chunk),
                    "longitude": ",".join(str(b) for _, b in chunk),
                    "current": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
                    "timezone": "GMT",
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            body.extend(data if isinstance(data, list) else [data])
    except (httpx.HTTPError, ValueError):
        return {"type": "FeatureCollection", "features": []}
    features = []
    for (lat, lon), item in zip(points, body):
        current = item.get("current") or {}
        if current.get("wind_speed_10m") is None or current.get("wind_direction_10m") is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"speed": current["wind_speed_10m"], "dir": current["wind_direction_10m"], "gust": current.get("wind_gusts_10m") or current["wind_speed_10m"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def comuna_page(comuna: dict, summary: dict, sources: list[dict], generated: str, counts: dict[str, int], base_url: str, slug: str, has_wind: bool, banner: str) -> str:
    phones = "".join(f'<li><a href="tel:{n}"><strong>{n}</strong><span>{escape(label)}</span></a></li>' for n, label in EMERGENCY_PHONES)
    links = "".join(f'<li><a href="{escape(href)}" rel="noreferrer">{escape(label)}</a><span>{escape(detail)}</span></li>' for label, detail, href in OFFICIAL_LINKS)
    standing = summary.get("standing_items", [])
    standing_html = (
        '<section class="card" aria-labelledby="permanentes"><h2 id="permanentes">Peligros permanentes del territorio</h2>'
        '<p class="note" style="margin:0 0 .6rem">Zonas de la comuna expuestas según los mapas oficiales. Sirven para prepararse y no indican una emergencia en curso.</p>'
        f"{items_html(standing, with_level=False)}</section>"
        if standing
        else ""
    )
    body = f"""{senator_bar(generated)}
<header class="muni"><div class="in">
<span class="initials" aria-hidden="true">{escape(comuna["name"][:2].upper())}</span>
<div><h1>{escape(comuna["display_name"])}</h1><p>Información sobre riesgos de desastre para la comunidad de {escape(comuna["name"])}</p></div>
<nav><a href="../index.html">Todas las comunas del Maule</a></nav>
</div></header>
<main class="wrap">
{banner}
<p class="notice"><strong>Cuando la información oficial no está disponible, la gente igual necesita saber:</strong> aquí está nuestra evaluación del riesgo, con SENAPRED, el SHOA, la Dirección Meteorológica de Chile y todas las fuentes que sí responden. En una emergencia, siga las indicaciones de la autoridad.</p>
<div class="grid">
<div>
{rain_card(
    f'<ul class="alerts">{"".join(alert_item(a) for a in summary["alerts"] if is_rain(a))}</ul>' if any(is_rain(a) for a in summary["alerts"]) else '<p class="note" style="margin:0">No hay alertas de lluvia ni de crecidas vigentes para la comuna.</p>',
    next((i["headline"] for i in summary["items"] if i["hazard"] == "Pronóstico del tiempo"), None),
    "Lluvia y crecidas",
)}
<section class="card" aria-labelledby="ahora">
<h2 id="ahora">Qué está pasando ahora</h2>
<p class="now">Nuestra evaluación del riesgo {level_pill(summary["overall_level"], summary["overall_level_label"])}</p>
{alerts_html(summary)}
<h3>Por amenaza</h3>
{items_html(summary["items"])}
<p class="note">Pronóstico: <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>. Calculado el {escape(format_time(summary["computed_at"]))}.</p>
{sources_html(sources)}
</section>
{standing_html}
</div>
{map_html(comuna["bbox"], counts, has_wind)}
</div>
<div class="grid2">
<section class="card" aria-labelledby="telefonos"><h2 id="telefonos">Teléfonos de emergencia</h2><ul class="phones">{phones}</ul></section>
<section class="card" aria-labelledby="enlaces"><h2 id="enlaces">Información oficial</h2><ul class="links">{links}</ul></section>
</div>
</main>
<footer class="foot">Mapa base: OpenFreeMap, OpenMapTiles, datos de OpenStreetMap. Capas: SENAPRED, CONAF, Dirección Meteorológica de Chile. Lluvia por satélite: NASA GIBS (GPM IMERG). Pronóstico: <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a> (CC BY 4.0).</footer>
<script type="module" src="../assets/map.js"></script>"""
    title = f"Riesgo en {comuna['name']}: alertas y mapa de la comuna"
    description = f"Alertas oficiales vigentes, mapa de peligros y pronóstico para {comuna['name']}, Región del Maule. {INITIATIVE}"
    head = share_tags(base_url, f"{slug}/", title, description, "../") + '<link rel="stylesheet" href="../assets/maplibre-gl.css">\n'
    return page(title, body, head=head)


def tile(slug: str, name: str, summary: dict) -> str:
    in_force = [a for a in summary["alerts"] if a["in_force"]]
    count = f"{len(in_force)} alerta vigente" if len(in_force) == 1 else f"{len(in_force)} alertas vigentes" if in_force else "Sin alertas vigentes"
    first = f'<span class="first">{escape(in_force[0]["title"])}</span>' if in_force else ""
    return (
        f'<li><a class="tile" href="{escape(slug)}/index.html">'
        f'<strong>{escape(name)}</strong>{level_pill(summary["overall_level"], summary["overall_level_label"])}'
        f'<span class="count">{count}</span>{first}</a></li>'
    )


def index_page(entries: list[tuple[str, str, dict]], generated: str, region: dict, base_url: str, counts: dict[str, int], has_wind: bool, banner: str) -> str:
    groups = []
    for prefix, province in PROVINCES.items():
        members = [(slug, name, s) for slug, name, s in entries if region["cuts"][slug].startswith(prefix)]
        items = "".join(tile(slug, name, s) for slug, name, s in members)
        groups.append(f'<section class="prov" aria-labelledby="p{prefix}"><h3 id="p{prefix}">{escape(province)}</h3><ul class="tiles">{items}</ul></section>')
    present = [level for level in LEVELS if any(s["overall_level"] == level for _, _, s in entries)]
    legend = "".join(f'<li><span class="sq" style="background:{level_style(level)[0]}"></span>{escape(level_style(level)[2])}</li>' for level in present)
    rain = rain_card(region_alerts_html([(slug, name, {**s, "alerts": [a for a in s["alerts"] if is_rain(a)]}) for slug, name, s in entries]), None, "Lluvia y crecidas en el Maule")
    phones = "".join(f'<li><a href="tel:{n}"><strong>{n}</strong><span>{escape(label)}</span></a></li>' for n, label in EMERGENCY_PHONES)
    links = "".join(f'<li><a href="{escape(href)}" rel="noreferrer">{escape(label)}</a><span>{escape(detail)}</span></li>' for label, detail, href in OFFICIAL_LINKS)
    wind = ' data-wind="assets/viento.json"' if has_wind else ""
    body = f"""{senator_bar(generated)}
<header class="muni"><div class="in">
<span class="initials" aria-hidden="true">VII</span>
<div><h1>Riesgo en mi comuna, Región del Maule</h1><p>Toque su comuna en el mapa o elíjala en la lista</p></div>
</div></header>
<main class="region">
<div class="card mapcard"><div class="map" data-map data-region="assets/comunas.json" data-layers="assets/region/"{wind} data-bbox="{escape(json.dumps(region["bbox"]))}" role="region" aria-label="Mapa de las comunas del Maule por situación"></div>
<ul class="legend" aria-label="Situación de cada comuna"><li><strong>Situación:</strong></li>{legend}</ul>{toggles_html(counts, has_wind)}</div>
<div class="side">
{banner}
<section class="card" aria-labelledby="comunas">
<h2 id="comunas">Elija su comuna</h2>
{"".join(groups)}
</section>
{rain}
<section class="card" aria-labelledby="ahora">
<h2 id="ahora">Alertas vigentes en el Maule</h2>
{region_alerts_html(entries)}
</section>
<section class="card" aria-labelledby="telefonos"><h2 id="telefonos">Teléfonos de emergencia</h2><ul class="phones">{phones}</ul></section>
<section class="card" aria-labelledby="enlaces"><h2 id="enlaces">Información oficial</h2><ul class="links">{links}</ul></section>
<p class="notice"><strong>Cuando la información oficial no está disponible, la gente igual necesita saber:</strong> aquí está nuestra evaluación del riesgo, con SENAPRED, el SHOA, la Dirección Meteorológica de Chile y todas las fuentes que sí responden. En una emergencia, siga las indicaciones de la autoridad.</p>
<p class="foot" style="padding:.75rem 0">Mapa base: OpenFreeMap, OpenMapTiles, datos de OpenStreetMap. Capas: SENAPRED, CONAF, Dirección Meteorológica de Chile. Lluvia por satélite: NASA GIBS (GPM IMERG). Viento y pronóstico: <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a> (CC BY 4.0).</p>
</div>
</main>
<script type="module" src="assets/map.js"></script>"""
    description = f"Alertas oficiales, mapa y pronóstico de las {len(entries)} comunas del Maule en un solo lugar. {INITIATIVE}"
    head = share_tags(base_url, "", SITE_NAME, description, "") + '<link rel="stylesheet" href="assets/maplibre-gl.css">\n'
    return page(SITE_NAME, body, "fit", head=head)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static public snapshot for the Maule comunas")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-url", default="https://synterra.cl/maule")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    generated = generated_label(datetime.now(UTC))
    assets = args.out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(HERE / "vendor" / name, assets / name)
    shutil.copyfile(HERE / "map.js", assets / "map.js")
    entries = []
    regional: dict[str, dict[str, dict]] = {layer[0]: {} for layer in MAP_LAYERS}
    with get_engine().connect() as conn:
        tenants = rows(conn, "select id, slug from municipality where cut_code like '07%' order by name")
        summaries = {t["slug"]: public_summary(t["slug"], conn) for t in tenants}
        banner = down_banner(senapred_status(public_sources(tenants[0]["slug"], conn), list(summaries.values())))
        extent = rows(conn, EXTENT_SQL)[0]
        wind = wind_grid(extent)
        has_wind = bool(wind["features"])
        (assets / "viento.json").write_text(json.dumps(wind, separators=(",", ":")), encoding="utf-8")
        region_rows = rows(conn, REGION_SQL)
        for tenant in tenants:
            slug = tenant["slug"]
            comuna = public_comuna(slug, conn)
            summary = summaries[slug]
            sources = public_sources(slug, conn)
            layers_dir = args.out / slug / "capas"
            layers_dir.mkdir(parents=True, exist_ok=True)
            counts = {}
            for key in ["comuna", *[layer[0] for layer in MAP_LAYERS]]:
                collection = layer_geojson(conn, tenant["id"], key)
                counts[key] = len(collection.get("features", []))
                if key in regional:
                    for feature in collection.get("features", []):
                        regional[key].setdefault(json.dumps(feature, sort_keys=True, default=str), feature)
                (layers_dir / f"{key}.json").write_text(json.dumps(collection, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
            (args.out / slug / "index.html").write_text(comuna_page(comuna, summary, sources, generated, counts, base_url, slug, has_wind, banner), encoding="utf-8")
            entries.append((slug, comuna["name"], summary))
        conn.rollback()
    levels = {slug: summary for slug, _, summary in entries}
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(r["g"]),
            "properties": {
                "slug": r["slug"],
                "name": r["name"],
                "label": levels[r["slug"]]["overall_level_label"],
                "color": level_style(levels[r["slug"]]["overall_level"])[0],
            },
        }
        for r in region_rows
        if r["slug"] in levels
    ]
    (assets / "comunas.json").write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    region = {"cuts": {r["slug"]: r["cut"] for r in region_rows}, "bbox": [extent["x0"], extent["y0"], extent["x1"], extent["y1"]]}
    region_dir = assets / "region"
    region_dir.mkdir(exist_ok=True)
    region_counts = {}
    for key, features in regional.items():
        region_counts[key] = len(features)
        (region_dir / f"{key}.json").write_text(json.dumps({"type": "FeatureCollection", "features": list(features.values())}, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
    (args.out / "index.html").write_text(index_page(entries, generated, region, base_url, region_counts, has_wind, banner), encoding="utf-8")
    (args.out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(entries)} comuna pages, layers and index written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
