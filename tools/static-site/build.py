import argparse
import sys
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

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

WARNING_BORDER = {
    "Alarma": "#b42318",
    "Alerta": "#d4590f",
    "Aviso": "#e3b505",
    "Alerta Roja": "#b42318",
    "Alerta Amarilla": "#e3b505",
    "Alerta Temprana Preventiva": "#2f7d4a",
}

SOURCE_STATE = {
    "live": ("Funcionando", "#166534"),
    "stale": ("Sin datos nuevos", "#92400e"),
    "failed": ("Falla", "#991b1b"),
    "pending": ("Aún sin datos", "#334155"),
    "unconfigured": ("No configurada", "#475569"),
}

OFFICIAL_LINKS = [
    ("SENAPRED", "Servicio Nacional de Prevención y Respuesta ante Desastres", "https://senapred.cl"),
    ("Alertas vigentes de SENAPRED", "Listado oficial de alertas declaradas", "https://senapred.cl/alertas"),
    ("SHOA", "Servicio Hidrográfico y Oceanográfico de la Armada, alertas de tsunami", "https://www.shoa.cl"),
    ("Dirección Meteorológica de Chile", "Pronósticos, avisos, alertas y alarmas meteorológicas", "https://www.meteochile.gob.cl"),
]

EMERGENCY_PHONES = [("131", "Ambulancia (SAMU)"), ("132", "Bomberos"), ("133", "Carabineros")]

PROVINCES = {"071": "Provincia de Talca", "073": "Provincia de Curicó", "074": "Provincia de Linares", "072": "Provincia de Cauquenes"}

FAVICON = "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%2314212c%27/%3E%3Cpath d=%27M16 5 29 27H3z%27 fill=%27%23e3b505%27/%3E%3Crect x=%2714.5%27 y=%2712%27 width=%273%27 height=%278%27 fill=%27%2314212c%27/%3E%3Crect x=%2714.5%27 y=%2722%27 width=%273%27 height=%273%27 fill=%27%2314212c%27/%3E%3C/svg%3E"

FONT = "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap"

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
:root{--paper:#e8edf1;--ink:#14212c;--soft:#4a5a68;--land:#ffffff;--sea:#cfdce6;--rule:#b6c4cf;--line:#d3dce3;--warn:#fff4d6;--warn-ink:#4a3200}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0;font-family:"Atkinson Hyperlegible",system-ui,sans-serif;font-size:1.0625rem;line-height:1.55;color:var(--ink);background:var(--paper)}
a{color:inherit;text-underline-offset:.18em}
a:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
h1,h2,h3,p{margin:0}
h1,h2,h3{line-height:1.15}
ul{list-style:none;margin:0;padding:0}
.brand{background:var(--ink);color:#ffffff;padding:clamp(.8rem,2vw,1.4rem) clamp(1rem,3vw,2.5rem)}
.brand-line{font-size:clamp(1.5rem,3.6vw,2.9rem);font-weight:700;line-height:1.1;max-width:60rem}
.snap{margin-top:.5rem;font-size:.95rem;color:#c9d4dd}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap;padding:1.1rem clamp(1rem,3vw,2.5rem);border-bottom:1px solid var(--rule)}
.top h1{font-size:clamp(1.35rem,2.4vw,1.9rem)}
.top p{color:var(--soft)}
body.fit{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
.region{display:grid;grid-template-columns:minmax(0,3fr) minmax(20rem,2fr);flex:1;min-height:0}
.mapwrap{min-height:0;height:100%;background:var(--sea);display:flex;flex-direction:column}
.mapwrap svg{flex:1;min-height:0;width:100%;display:block}
.map path{stroke:#ffffff;stroke-width:1.2;vector-effect:non-scaling-stroke;transition:filter .15s}
.map a:hover path{filter:brightness(.82);stroke:var(--ink);stroke-width:2.2}
.legend{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;padding:.8rem clamp(1rem,3vw,2.5rem);background:var(--paper);border-top:1px solid var(--rule);font-size:.9rem}
.sw{width:.95rem;height:.95rem;border-radius:2px;display:inline-block;flex:none}
.list{padding:1.5rem clamp(1rem,3vw,2.5rem) 3rem;border-left:1px solid var(--rule);overflow-y:auto;min-height:0}
.intro{color:var(--soft);max-width:36rem;margin-bottom:1.5rem}
.prov{margin-bottom:1.75rem}
.prov h2{font-size:1rem;color:var(--soft);font-weight:400;padding-bottom:.4rem;border-bottom:1px solid var(--rule)}
.prov a{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.55rem .25rem;border-bottom:1px solid var(--line);text-decoration:none}
.prov a:hover{background:#dde5eb}
.prov a strong{font-size:1.1rem}
.lvl{display:inline-flex;align-items:center;gap:.45rem;font-weight:700;font-size:.95rem;white-space:nowrap}
.band{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2rem;align-items:center;padding:clamp(1.5rem,4vw,3.5rem) clamp(1rem,3vw,2.5rem)}
.band nav a{font-size:.95rem}
.band h1{font-size:clamp(1.6rem,3.2vw,2.6rem);font-weight:400;margin:.6rem 0 .2rem}
.word{font-size:clamp(3.4rem,11vw,8.5rem);font-weight:700;line-height:.95;letter-spacing:-.02em}
.word-note{margin-top:.8rem;max-width:40rem;font-size:1rem}
.band svg{width:clamp(7rem,22vw,17rem);height:auto;display:block}
.band svg path{fill:currentColor;fill-opacity:.25;stroke:currentColor;stroke-width:1.5;vector-effect:non-scaling-stroke}
.body{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:clamp(1.5rem,3vw,3.5rem);padding:2rem clamp(1rem,3vw,2.5rem) 3rem}
.body h2{font-size:1.35rem;margin-bottom:.9rem}
.body section+section{margin-top:2.25rem}
.alert{border-left:.45rem solid;background:var(--land);padding:1rem 1.1rem;margin-bottom:.8rem}
.alert h3{font-size:1.15rem;margin:.25rem 0 .4rem}
.alert p+p{margin-top:.25rem}
.meta{color:var(--soft);font-size:.92rem;display:block}
.calm{background:var(--land);padding:1rem 1.1rem;border-left:.45rem solid var(--rule)}
.calm p+p{margin-top:.35rem}
.haz li{display:grid;grid-template-columns:.4rem minmax(0,1fr);gap:.85rem;padding:.75rem 0;border-bottom:1px solid var(--line)}
.bar{border-radius:2px}
.note{color:var(--soft);font-size:.92rem;max-width:44rem;margin-top:.8rem}
.src{margin-top:.8rem}
.src li{padding:.5rem 0;border-bottom:1px solid var(--line)}
.phones{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.6rem}
.phones a{display:block;background:var(--land);padding:.8rem;text-decoration:none;text-align:center;font-size:.92rem}
.phones strong{display:block;font-size:2rem;line-height:1.1}
.links li{padding:.55rem 0;border-bottom:1px solid var(--line)}
.links a{font-weight:700}
.foot{padding:1.5rem clamp(1rem,3vw,2.5rem) 2.5rem;border-top:1px solid var(--rule);color:var(--soft);font-size:.9rem}
@media (max-width:900px){
body.fit{height:auto;overflow:visible}
.region{grid-template-columns:1fr}
.mapwrap{height:62vh}
.list{border-left:0;overflow:visible}
.body,.band{grid-template-columns:1fr}
.band svg{width:9rem}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
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
    return f"{local.day} de {MONTHS[local.month - 1]}, {local:%H:%M} hora de Chile ({moment.astimezone(UTC):%H:%M} UTC)"


def generated_label(moment: datetime) -> str:
    local = moment.astimezone(CHILE)
    return f"{local.day} de {MONTHS[local.month - 1]} de {local.year} a las {local:%H:%M}"


def level_style(level: str) -> tuple[str, str, str]:
    return LEVELS.get(level, LEVELS["SIN_DATOS"])


def level_mark(level: str, label: str | None = None) -> str:
    background, _, default_label = level_style(level)
    return f'<span class="lvl"><span class="sw" style="background:{background}" aria-hidden="true"></span>{escape(label or default_label)}</span>'


def page(title: str, body: str, body_class: str = "") -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONT}">
<style>{STYLE}</style>
</head>
<body class="{body_class}">
{body}
</body>
</html>
"""


def snapshot_strip(generated: str) -> str:
    return (
        '<div class="brand"><p class="brand-line">Una iniciativa de la oficina de la senadora Paulina Vodanovic</p>'
        f'<p class="snap">Última actualización: {escape(generated)}.</p></div>'
    )


def alerts_html(summary: dict) -> str:
    if not summary["alerts"]:
        return (
            '<div class="calm"><p><strong>No hay avisos ni alertas oficiales registrados para la comuna en este momento.</strong></p>'
            '<p class="meta">Que no aparezca una alerta no significa que no exista peligro. Confirme en senapred.cl.</p></div>'
        )
    items = []
    for alert in summary["alerts"]:
        border = WARNING_BORDER.get(alert["level"], "#b42318")
        state = "vigente" if alert["in_force"] else "próxima"
        timing = f"{'Desde el' if alert['in_force'] else 'Comienza el'} {format_time(alert['starts_at'])}"
        if alert["ends_at"]:
            timing += f", hasta el {format_time(alert['ends_at'])}"
        link = f'<p><a href="{escape(alert["source_url"])}" rel="noreferrer">Ver el anuncio oficial</a></p>' if alert["source_url"] else ""
        items.append(
            f'<li class="alert" style="border-color:{border}">'
            f'<p class="meta"><strong>{escape(alert["level"])}</strong>, {state}</p>'
            f'<h3>{escape(alert["title"])}</h3>'
            f'<p class="meta">{escape(alert["issuer"])}. {escape(timing)}.</p>'
            f'<p class="meta">Origen: {escape(alert["origin"])}.</p>{link}</li>'
        )
    return f'<ul>{"".join(items)}</ul>'


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

    out = [
        '<section aria-labelledby="fuentes"><h2 id="fuentes">Estado de las fuentes</h2>',
        '<p class="note">La plataforma lee varias fuentes independientes. Si una falla, las demás siguen funcionando y se muestra el último dato recibido de cada una.</p>',
    ]
    if alert_down:
        tail = f"Siguen funcionando: {names(alert_up)}." if alert_up else "Ninguna fuente de alertas responde ahora; consulte senapred.cl y los canales de su municipalidad."
        out.append(f'<p class="calm note">Sin respuesta reciente: {escape(names(alert_down))}. {escape(tail)}</p>')
    out.append('<ul class="src">')
    for source in alert_sources:
        label, colour = SOURCE_STATE[source["state"]]
        out.append(
            f'<li><strong>{escape(source["name"])}</strong>: <strong style="color:{colour}">{escape(label)}</strong>'
            f'<span class="meta">{escape(source["organization"])}. Último dato recibido: {escape(last_data(source))}.</span></li>'
        )
    out.append(f"<li><strong>Otras fuentes de datos</strong>: {len(data_sources) - len(data_down)} de {len(data_sources)} funcionando.")
    for source in data_down:
        label, colour = SOURCE_STATE[source["state"]]
        out.append(f'<span class="meta"><strong style="color:{colour}">{escape(label)}</strong>: {escape(source["name"])}, último dato {escape(last_data(source))}.</span>')
    out.append("</li></ul></section>")
    return "".join(out)


def view_box(x0: float, y0: float, x1: float, y1: float, pad: float) -> str:
    return f"{x0 - pad} {-y1 - pad} {x1 - x0 + 2 * pad} {y1 - y0 + 2 * pad}"


def silhouette(shape: dict) -> str:
    pad = max(shape["x1"] - shape["x0"], shape["y1"] - shape["y0"]) * 0.04
    return f'<svg viewBox="{view_box(shape["x0"], shape["y0"], shape["x1"], shape["y1"], pad)}" aria-hidden="true" focusable="false"><path d="{shape["d"]}"/></svg>'


def comuna_page(comuna: dict, summary: dict, sources: list[dict], generated: str, shape: dict) -> str:
    background, foreground, _ = level_style(summary["overall_level"])
    hazards = "".join(
        f'<li><span class="bar" style="background:{level_style(item["level"])[0]}" aria-hidden="true"></span>'
        f'<div><strong>{escape(item["hazard"])}: {escape(item["level_label"])}</strong><span class="meta">{escape(item["headline"])}</span></div></li>'
        for item in summary["items"]
    )
    phones = "".join(f'<li><a href="tel:{n}"><strong>{n}</strong>{escape(label)}</a></li>' for n, label in EMERGENCY_PHONES)
    links = "".join(f'<li><a href="{escape(href)}" rel="noreferrer">{escape(label)}</a><span class="meta">{escape(detail)}</span></li>' for label, detail, href in OFFICIAL_LINKS)
    body = f"""{snapshot_strip(generated)}
<header class="band" style="background:{background};color:{foreground}">
<div>
<nav><a href="../index.html">Todas las comunas del Maule</a></nav>
<h1>{escape(comuna["name"])}, nivel general</h1>
<p class="word">{escape(summary["overall_level_label"])}</p>
<p class="word-note">Cálculo de referencia con información oficial. En una emergencia, siga las indicaciones de SENAPRED y de su municipalidad.</p>
</div>
{silhouette(shape)}
</header>
<main class="body">
<div>
<section aria-labelledby="alertas">
<h2 id="alertas">Alertas oficiales</h2>
{alerts_html(summary)}
<p class="note">{escape(summary["alert_feed_note"])}</p>
</section>
{sources_html(sources)}
</div>
<div>
<section aria-labelledby="amenazas">
<h2 id="amenazas">Por amenaza</h2>
<ul class="haz">{hazards}</ul>
<p class="note">{escape(summary["notice"])}</p>
<p class="note">Calculado el {escape(format_time(summary["computed_at"]))}.</p>
</section>
<section aria-labelledby="telefonos">
<h2 id="telefonos">Teléfonos de emergencia</h2>
<ul class="phones">{phones}</ul>
</section>
<section aria-labelledby="enlaces">
<h2 id="enlaces">Información oficial</h2>
<ul class="links">{links}</ul>
<p class="note">{escape(summary["official_information"])}</p>
</section>
</div>
</main>
<footer class="foot"><p>Fuentes: SENAPRED, SHOA, Dirección Meteorológica de Chile, CONAF, INE y las demás fuentes listadas en Estado de las fuentes.</p></footer>"""
    return page(f"{comuna['name']}: {summary['overall_level_label']}", body)


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
    legend = "".join(f"<li>{level_mark(level)}</li>" for level in present)
    return (
        f'<div class="mapwrap"><svg class="map" viewBox="{view_box(x0, y0, x1, y1, (x1 - x0) * 0.03)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">{paths}</svg>'
        f'<ul class="legend" aria-label="Leyenda del mapa">{legend}</ul></div>'
    )


def index_page(entries: list[tuple[str, str, dict]], generated: str, shapes: dict) -> str:
    groups = []
    for prefix, province in PROVINCES.items():
        members = [(slug, name, s) for slug, name, s in entries if shapes[slug]["cut"].startswith(prefix)]
        items = "".join(f'<li><a href="{escape(slug)}/index.html"><strong>{escape(name)}</strong>{level_mark(s["overall_level"], s["overall_level_label"])}</a></li>' for slug, name, s in members)
        groups.append(f'<section class="prov" aria-labelledby="p{prefix}"><h2 id="p{prefix}">{escape(province)}</h2><ul>{items}</ul></section>')
    body = f"""{snapshot_strip(generated)}
<header class="top"><h1>Riesgo en mi comuna, Región del Maule</h1><p>{len(entries)} comunas</p></header>
<main class="region">
{region_map(entries, shapes)}
<div class="list">
<p class="intro">Nivel general de cada comuna según el cálculo de la plataforma, que reúne información de SENAPRED, SHOA, la Dirección Meteorológica de Chile y otras fuentes oficiales. Elija su comuna para ver las alertas y el detalle por amenaza.</p>
{"".join(groups)}
</div>
</main>"""
    return page("Riesgo en mi comuna, Región del Maule", body, "fit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static public snapshot for the Maule comunas")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    generated = generated_label(datetime.now(UTC))
    entries = []
    with get_engine().connect() as conn:
        slugs = [r["slug"] for r in rows(conn, "select slug from municipality where cut_code like '07%' order by name")]
        shapes = {r["slug"]: r for r in rows(conn, SHAPES_SQL)}
        for slug in slugs:
            comuna = public_comuna(slug, conn)
            summary = public_summary(slug, conn)
            sources = public_sources(slug, conn)
            target = args.out / slug
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(comuna_page(comuna, summary, sources, generated, shapes[slug]), encoding="utf-8")
            entries.append((slug, comuna["name"], summary))
        conn.rollback()
    (args.out / "index.html").write_text(index_page(entries, generated, shapes), encoding="utf-8")
    (args.out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(entries)} comuna pages and index written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
