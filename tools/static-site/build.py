import argparse
import json
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
    ("dmc_warning", "Avisos y alertas meteorológicas vigentes", "Dirección Meteorológica de Chile", False, '<span class="sq" style="background:#eab308"></span>'),
    ("wildfire_hazard", "Recurrencia de incendios forestales", "SENAPRED con datos de CONAF", False, '<span class="sq" style="background:linear-gradient(90deg,#fde68a,#9a3412)"></span>'),
]

OFFICIAL_LINKS = [
    ("SENAPRED", "Servicio Nacional de Prevención y Respuesta ante Desastres", "https://senapred.cl"),
    ("Alertas vigentes de SENAPRED", "Listado oficial de alertas declaradas", "https://senapred.cl/alertas"),
    ("SHOA", "Servicio Hidrográfico y Oceanográfico de la Armada, alertas de tsunami", "https://www.shoa.cl"),
    ("Dirección Meteorológica de Chile", "Pronósticos, avisos, alertas y alarmas meteorológicas", "https://www.meteochile.gob.cl"),
]

EMERGENCY_PHONES = [("131", "Ambulancia (SAMU)"), ("132", "Bomberos"), ("133", "Carabineros")]

PROVINCES = {"071": "Provincia de Talca", "073": "Provincia de Curicó", "074": "Provincia de Linares", "072": "Provincia de Cauquenes"}

FAVICON = "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%23e42827%27/%3E%3Cpath d=%27M16 5 29 27H3z%27 fill=%27%23ffffff%27/%3E%3Crect x=%2714.5%27 y=%2712%27 width=%273%27 height=%278%27 fill=%27%23e42827%27/%3E%3Crect x=%2714.5%27 y=%2722%27 width=%273%27 height=%273%27 fill=%27%23e42827%27/%3E%3C/svg%3E"

ASSETS = ["maplibre-gl.js", "maplibre-gl-shared.js", "maplibre-gl-worker.js", "maplibre-gl.css", "MAPLIBRE-LICENSE.txt", "og-maule.png", "icon-180.png", "icon-32.png"]
SITE_NAME = "Riesgo en mi comuna, Región del Maule"
INITIATIVE = "Una iniciativa de la oficina de la senadora Paulina Vodanovic."

SHAPES_SQL = """
with g as (
    select slug, cut_code, st_scale(st_simplifypreservetopology(boundary, 0.0015), 0.82, 1) as geom
    from municipality where cut_code like '07%'
)
select slug, cut_code as cut, st_assvg(geom, 0, 4) as d,
       st_xmin(geom) as x0, st_ymin(geom) as y0, st_xmax(geom) as x1, st_ymax(geom) as y1
from g
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
.notice{border:1px solid #fcd34d;background:#fffbeb;color:#451a03;border-radius:.75rem;padding:.75rem;font-size:.9rem}
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
body.fit{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
.region{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,3fr) minmax(20rem,2fr);gap:1rem;padding:1rem;max-width:90rem;width:100%;margin:0 auto}
.regionmap{background:#cfe0ee;border:1px solid var(--border);border-radius:1rem;display:flex;flex-direction:column;min-height:0;overflow:hidden}
.regionmap svg{flex:1;min-height:0;width:100%;display:block}
.regionmap path{stroke:#fff;stroke-width:1.2;vector-effect:non-scaling-stroke}
.regionmap a:hover path{filter:brightness(.85);stroke:var(--fg);stroke-width:2.2}
.legend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;padding:.6rem 1rem;background:var(--surface);border-top:1px solid var(--border);font-size:.82rem}
.legend li{display:flex;align-items:center;gap:.35rem}
.side{overflow-y:auto;min-height:0;padding-right:.25rem}
.side>p{font-size:.9rem;color:var(--muted);margin-bottom:1rem}
.prov{margin-bottom:1.25rem}
.prov h2{font-size:.95rem;font-weight:600;color:var(--muted);margin-bottom:.5rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(12.5rem,1fr));gap:.5rem}
.tile{display:flex;flex-direction:column;gap:.35rem;height:100%;background:var(--surface);border:1px solid var(--border);border-radius:.75rem;padding:.7rem .8rem;text-decoration:none}
.tile:hover{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand)}
.tile strong{font-size:1rem;font-weight:600}
.tile .count{font-size:.8rem;color:var(--muted)}
.tile .first{font-size:.78rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
@media (max-width:960px){
.grid,.grid2{grid-template-columns:1fr}
.mapcard{position:relative;top:0;height:70vh}
body.fit{height:auto;overflow:visible}
.region{grid-template-columns:1fr}
.regionmap{height:60vh}
.side{overflow:visible}
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


def senator_bar(generated: str) -> str:
    return f'<div class="senator"><div class="in"><strong>Una iniciativa de la oficina de la senadora Paulina Vodanovic</strong><span>Última actualización: {escape(generated)}</span></div></div>'


def alerts_html(summary: dict) -> str:
    if not summary["alerts"]:
        return (
            '<div class="calm"><p><strong>No hay avisos ni alertas oficiales registrados para la comuna en este momento.</strong></p>'
            "<p>Que no aparezca una alerta no significa que no exista peligro. Confirme en senapred.cl.</p></div>"
        )
    items = []
    for alert in summary["alerts"]:
        timing = f"{'desde' if alert['in_force'] else 'comienza'} {format_time(alert['starts_at'])}"
        if alert["ends_at"]:
            timing += f", hasta {format_time(alert['ends_at'])}"
        link = f'<a href="{escape(alert["source_url"])}" rel="noreferrer">Ver el anuncio oficial</a>' if alert["source_url"] else ""
        items.append(
            f'<li class="{WARNING_TONE.get(alert["level"], "tone-red")}">'
            f'<p class="head"><span class="pill pill-out">{escape(alert["level"])}</span><span class="small">{"Vigente" if alert["in_force"] else "Próximo"}</span><span class="tag tag-official">Alerta oficial</span></p>'
            f'<p class="title">{escape(alert["title"])}</p>'
            f'<p class="small">{escape(alert["issuer"])}, {escape(timing)}</p>'
            f'<p class="origin">Origen: {escape(alert["origin"])}.</p>{link}</li>'
        )
    return f'<ul class="alerts">{"".join(items)}</ul>'


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

    out = ['<h3>Estado de las fuentes</h3><p class="note" style="margin:0 0 .5rem">La plataforma lee varias fuentes independientes. Si una falla, las demás siguen funcionando.</p>']
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


def map_html(bbox, counts: dict[str, int]) -> str:
    toggles = "".join(
        f'<label><input type="checkbox" data-layer="{key}"{" checked" if on else ""}>{swatch}<span>{escape(name)}<span class="src"> ({escape(source)})</span></span></label>'
        for key, name, source, on, swatch in MAP_LAYERS
        if counts.get(key)
    )
    return (
        f'<div class="card mapcard"><div class="map" data-map data-layers="capas/" data-bbox="{escape(json.dumps(list(bbox)))}" role="region" aria-label="Mapa de la comuna"></div>'
        f'<div class="toggles">{toggles or "<span class=src>Sin capas oficiales con datos para esta comuna.</span>"}</div></div>'
    )


def comuna_page(comuna: dict, summary: dict, sources: list[dict], generated: str, counts: dict[str, int], base_url: str, slug: str) -> str:
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
<p class="notice">Esta página reúne información oficial de varias fuentes independientes, entre ellas SENAPRED y la Dirección Meteorológica de Chile, y un cálculo de referencia hecho por la plataforma. Si una fuente deja de responder, la página lo indica y sigue mostrando las demás. No reemplaza las instrucciones de la autoridad. <strong>En una emergencia, siga las indicaciones de SENAPRED y de su municipalidad.</strong></p>
<div class="grid">
<div>
<section class="card" aria-labelledby="ahora">
<h2 id="ahora">Qué está pasando ahora</h2>
<p class="now">Situación de la comuna {level_pill(summary["overall_level"], summary["overall_level_label"])} <span class="tag">Cálculo de la plataforma</span></p>
{alerts_html(summary)}
<p class="note">{escape(summary["alert_feed_note"])}</p>
<h3>Resumen por amenaza <span class="tag">Cálculo de la plataforma</span></h3>
{items_html(summary["items"])}
<p class="note">{escape(summary["notice"])}</p>
<p class="note">Pronóstico: <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>. Calculado el {escape(format_time(summary["computed_at"]))}.</p>
{sources_html(sources)}
</section>
{standing_html}
</div>
{map_html(comuna["bbox"], counts)}
</div>
<div class="grid2">
<section class="card" aria-labelledby="telefonos"><h2 id="telefonos">Teléfonos de emergencia</h2><ul class="phones">{phones}</ul></section>
<section class="card" aria-labelledby="enlaces"><h2 id="enlaces">Información oficial</h2><ul class="links">{links}</ul><p class="note">{escape(summary["official_information"])}</p></section>
</div>
</main>
<footer class="foot">Mapa base: OpenFreeMap, OpenMapTiles, datos de OpenStreetMap. Capas: SENAPRED, CONAF, Dirección Meteorológica de Chile. Pronóstico: <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a> (CC BY 4.0).</footer>
<script type="module" src="../assets/map.js"></script>"""
    title = f"Riesgo en {comuna['name']}: alertas y mapa de la comuna"
    description = f"Alertas oficiales vigentes, mapa de peligros y pronóstico para {comuna['name']}, Región del Maule. {INITIATIVE}"
    head = share_tags(base_url, f"{slug}/", title, description, "../") + '<link rel="stylesheet" href="../assets/maplibre-gl.css">\n'
    return page(title, body, head=head)


def view_box(x0: float, y0: float, x1: float, y1: float, pad: float) -> str:
    return f"{x0 - pad} {-y1 - pad} {x1 - x0 + 2 * pad} {y1 - y0 + 2 * pad}"


def region_map(entries: list[tuple[str, str, dict]], shapes: dict) -> str:
    x0 = min(s["x0"] for s in shapes.values())
    y0 = min(s["y0"] for s in shapes.values())
    x1 = max(s["x1"] for s in shapes.values())
    y1 = max(s["y1"] for s in shapes.values())
    paths = "".join(
        f'<a href="{escape(slug)}/index.html" tabindex="-1"><title>{escape(name)}: {escape(s["overall_level_label"])}</title>'
        f'<path d="{shapes[slug]["d"]}" fill="{level_style(s["overall_level"])[0]}"/></a>'
        for slug, name, s in entries
    )
    present = [level for level in LEVELS if any(s["overall_level"] == level for _, _, s in entries)]
    legend = "".join(f'<li><span class="sq" style="background:{level_style(level)[0]}"></span>{escape(level_style(level)[2])}</li>' for level in present)
    return (
        f'<div class="regionmap"><svg viewBox="{view_box(x0, y0, x1, y1, (x1 - x0) * 0.03)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">{paths}</svg>'
        f'<ul class="legend" aria-label="Leyenda del mapa">{legend}</ul></div>'
    )


def tile(slug: str, name: str, summary: dict) -> str:
    in_force = [a for a in summary["alerts"] if a["in_force"]]
    count = f"{len(in_force)} alerta vigente" if len(in_force) == 1 else f"{len(in_force)} alertas vigentes" if in_force else "Sin alertas vigentes"
    first = f'<span class="first">{escape(in_force[0]["title"])}</span>' if in_force else ""
    return (
        f'<li><a class="tile" href="{escape(slug)}/index.html">'
        f'<strong>{escape(name)}</strong>{level_pill(summary["overall_level"], summary["overall_level_label"])}'
        f'<span class="count">{count}</span>{first}</a></li>'
    )


def index_page(entries: list[tuple[str, str, dict]], generated: str, shapes: dict, base_url: str) -> str:
    groups = []
    for prefix, province in PROVINCES.items():
        members = [(slug, name, s) for slug, name, s in entries if shapes[slug]["cut"].startswith(prefix)]
        items = "".join(tile(slug, name, s) for slug, name, s in members)
        groups.append(f'<section class="prov" aria-labelledby="p{prefix}"><h2 id="p{prefix}">{escape(province)}</h2><ul class="tiles">{items}</ul></section>')
    body = f"""{senator_bar(generated)}
<header class="muni"><div class="in">
<span class="initials" aria-hidden="true">VII</span>
<div><h1>Riesgo en mi comuna, Región del Maule</h1><p>Situación ahora en las {len(entries)} comunas de la región</p></div>
</div></header>
<main class="region">
{region_map(entries, shapes)}
<div class="side">
<p>Situación de cada comuna según el cálculo de la plataforma, que reúne información de SENAPRED, SHOA, la Dirección Meteorológica de Chile y otras fuentes. Elija su comuna para ver las alertas, el mapa y el detalle por amenaza.</p>
{"".join(groups)}
</div>
</main>"""
    description = f"Alertas oficiales, mapa y pronóstico de las {len(entries)} comunas del Maule en un solo lugar. {INITIATIVE}"
    return page(SITE_NAME, body, "fit", head=share_tags(base_url, "", SITE_NAME, description, ""))


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
    with get_engine().connect() as conn:
        tenants = rows(conn, "select id, slug from municipality where cut_code like '07%' order by name")
        shapes = {r["slug"]: r for r in rows(conn, SHAPES_SQL)}
        for tenant in tenants:
            slug = tenant["slug"]
            comuna = public_comuna(slug, conn)
            summary = public_summary(slug, conn)
            sources = public_sources(slug, conn)
            layers_dir = args.out / slug / "capas"
            layers_dir.mkdir(parents=True, exist_ok=True)
            counts = {}
            for key in ["comuna", *[layer[0] for layer in MAP_LAYERS]]:
                collection = layer_geojson(conn, tenant["id"], key)
                counts[key] = len(collection.get("features", []))
                (layers_dir / f"{key}.json").write_text(json.dumps(collection, ensure_ascii=False, default=str, separators=(",", ":")), encoding="utf-8")
            (args.out / slug / "index.html").write_text(comuna_page(comuna, summary, sources, generated, counts, base_url, slug), encoding="utf-8")
            entries.append((slug, comuna["name"], summary))
        conn.rollback()
    (args.out / "index.html").write_text(index_page(entries, generated, shapes, base_url), encoding="utf-8")
    (args.out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(entries)} comuna pages, layers and index written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
