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
    "CRITICO": ("#b42318", "#ffffff", "!!", "Crítico"),
    "ALTO": ("#d4590f", "#ffffff", "!", "Alto"),
    "MODERADO": ("#e3b505", "#422006", "~", "Moderado"),
    "BAJO": ("#2f7d4a", "#ffffff", "-", "Bajo"),
    "INFORMATIVO": ("#2b5ea7", "#ffffff", "i", "Informativo"),
    "SIN_DATOS": ("#8a929c", "#ffffff", "?", "Sin datos"),
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
    ("Dirección Meteorológica de Chile", "Pronósticos, avisos, alertas y alarmas meteorológicas", "https://www.meteochile.gob.cl"),
]

EMERGENCY_PHONES = [("131", "Ambulancia (SAMU)"), ("132", "Bomberos"), ("133", "Carabineros")]

STYLE = """
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5;color:#1e293b;background:#f8fafc}
main,header>div{max-width:52rem;margin:0 auto;padding:1rem}
header{background:#1e3a5f;color:#fff}
header h1{margin:0;font-size:1.4rem}
header p{margin:.25rem 0 0}
a{color:#1d4ed8}
header a{color:#fff}
section{background:#fff;border:1px solid #e2e8f0;border-radius:1rem;padding:1rem;margin:1rem 0}
h2{font-size:1.15rem;margin:0 0 .75rem}
h3{font-size:1rem;margin:1rem 0 .5rem}
ul{padding:0;list-style:none;margin:0}
.snapshot{border:2px solid #b45309;background:#fffbeb;color:#451a03;border-radius:.75rem;padding:.75rem 1rem;margin:1rem 0}
.notice{border:1px solid #fcd34d;background:#fffbeb;border-radius:.75rem;padding:.75rem 1rem}
.badge{display:inline-block;border-radius:999px;padding:.1rem .6rem;font-weight:600;font-size:.85rem;white-space:nowrap}
.badge span{font-family:monospace;opacity:.8;margin-right:.3rem}
.overall{font-size:1.05rem}
.list>li{border-top:1px solid #e2e8f0;padding:.6rem 0}
.list>li:first-child{border-top:0}
.alert{border:1px solid #e2e8f0;border-left:6px solid #b42318;border-radius:.75rem;padding:.75rem;margin:.5rem 0;background:#fff}
.alert p{margin:.2rem 0}
.muted{color:#475569;font-size:.875rem}
.small{font-size:.8rem}
.phones{display:flex;gap:.5rem;flex-wrap:wrap}
.phones a{display:block;border:1px solid #e2e8f0;border-radius:.75rem;padding:.5rem 1rem;text-align:center;text-decoration:none;color:#1e293b}
.phones strong{display:block;font-size:1.5rem;color:#1e3a5f}
footer{max-width:52rem;margin:0 auto;padding:1rem 1rem 2rem;border-top:1px solid #e2e8f0}
.index li{display:flex;justify-content:space-between;gap:.75rem;align-items:center;flex-wrap:wrap}
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
    return f"{local.day} de {MONTHS[local.month - 1]} de {local.year}, {local:%H:%M} (hora de Chile)"


def level_badge(level: str, label: str | None = None) -> str:
    background, foreground, icon, default_label = LEVELS.get(level, LEVELS["SIN_DATOS"])
    return f'<span class="badge" style="background:{background};color:{foreground}"><span aria-hidden="true">{escape(icon)}</span>{escape(label or default_label)}</span>'


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
{body}
</body>
</html>
"""


def snapshot_notice(generated: str) -> str:
    return (
        '<div class="snapshot" role="note"><p><strong>Copia estática temporal.</strong> '
        f"Esta página es una copia fija generada el {escape(generated)} y no se actualiza sola. "
        "Las alertas oficiales deben confirmarse en "
        '<a href="https://senapred.cl">senapred.cl</a>, <a href="https://www.shoa.cl">shoa.cl</a> '
        "y los canales de su municipalidad.</p></div>"
    )


def alerts_html(summary: dict) -> str:
    if not summary["alerts"]:
        return (
            '<div class="notice"><p><strong>No hay avisos ni alertas oficiales registrados para la comuna en este momento.</strong></p>'
            '<p class="muted">Que no aparezca una alerta no significa que no exista peligro. Confirme en senapred.cl.</p></div>'
        )
    items = []
    for alert in summary["alerts"]:
        border = WARNING_BORDER.get(alert["level"], "#b42318")
        timing = f"{'desde' if alert['in_force'] else 'comienza'} {format_time(alert['starts_at'])}"
        if alert["ends_at"]:
            timing += f" · hasta {format_time(alert['ends_at'])}"
        link = f'<p><a href="{escape(alert["source_url"])}" rel="noreferrer">Ver el anuncio oficial</a></p>' if alert["source_url"] else ""
        items.append(
            f'<li class="alert" style="border-left-color:{border}">'
            f'<p><strong>{escape(alert["level"])}</strong> · {"Vigente" if alert["in_force"] else "Próximo"} · Alerta oficial</p>'
            f'<p><strong>{escape(alert["title"])}</strong></p>'
            f'<p class="small">{escape(alert["issuer"])} · {escape(timing)}</p>'
            f'<p class="small">Origen: {escape(alert["origin"])}.</p>{link}</li>'
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
        "<h3>Estado de las fuentes</h3>",
        '<p class="muted">La plataforma lee varias fuentes independientes. Si una falla, las demás siguen funcionando y se muestra el último dato recibido de cada una.</p>',
    ]
    if alert_down:
        tail = f"Siguen funcionando: {names(alert_up)}." if alert_up else "Ninguna fuente de alertas responde ahora; consulte senapred.cl y los canales de su municipalidad."
        out.append(f'<p class="notice small">Sin respuesta reciente: {escape(names(alert_down))}. {escape(tail)}</p>')
    out.append('<ul class="list small">')
    for source in alert_sources:
        label, colour = SOURCE_STATE[source["state"]]
        out.append(
            f'<li><strong>{escape(source["name"])}</strong> <strong style="color:{colour}">{escape(label)}</strong><br>'
            f'<span class="muted">{escape(source["organization"])} · último dato recibido: {escape(last_data(source))}</span></li>'
        )
    out.append(f"<li><strong>Otras fuentes de datos:</strong> {len(data_sources) - len(data_down)} de {len(data_sources)} funcionando.")
    if data_down:
        out.append('<ul class="muted">')
        for source in data_down:
            label, colour = SOURCE_STATE[source["state"]]
            out.append(f'<li><strong style="color:{colour}">{escape(label)}</strong>: {escape(source["name"])}, último dato {escape(last_data(source))}</li>')
        out.append("</ul>")
    out.append("</li></ul>")
    return "".join(out)


def comuna_page(comuna: dict, summary: dict, sources: list[dict], generated: str) -> str:
    hazards = "".join(
        f'<li>{level_badge(item["level"], item["level_label"])} <strong>{escape(item["hazard"])}.</strong> {escape(item["headline"])}</li>' for item in summary["items"]
    )
    phones = "".join(f'<li><a href="tel:{n}"><strong>{n}</strong><span class="muted">{escape(label)}</span></a></li>' for n, label in EMERGENCY_PHONES)
    links = "".join(f'<li><a href="{escape(href)}" rel="noreferrer"><strong>{escape(label)}</strong></a><br><span class="muted">{escape(detail)}</span></li>' for label, detail, href in OFFICIAL_LINKS)
    body = f"""<header><div>
<p class="small"><a href="../index.html">Todas las comunas del Maule</a></p>
<h1>{escape(comuna["display_name"])}</h1>
<p>Información sobre riesgos de desastre para la comunidad de {escape(comuna["name"])}</p>
</div></header>
<main>
{snapshot_notice(generated)}
<p class="notice">Esta página reúne información oficial de varias fuentes independientes, entre ellas SENAPRED y la Dirección Meteorológica de Chile, y un cálculo de referencia hecho por la plataforma. No reemplaza las instrucciones de la autoridad. <strong>En una emergencia, siga las indicaciones de SENAPRED y de su municipalidad.</strong></p>
<section aria-labelledby="ahora">
<h2 id="ahora">Qué está pasando ahora</h2>
<p class="overall">Nivel general de la comuna: {level_badge(summary["overall_level"], summary["overall_level_label"])}</p>
{alerts_html(summary)}
<p class="muted">{escape(summary["alert_feed_note"])}</p>
<h3>Resumen por amenaza <span class="muted">(cálculo de la plataforma)</span></h3>
<ul class="list">{hazards}</ul>
<p class="muted">{escape(summary["notice"])}</p>
<p class="muted">Actualizado: {escape(format_time(summary["computed_at"]))}.</p>
<p class="muted">{escape(summary["official_information"])}</p>
{sources_html(sources)}
</section>
<section aria-labelledby="telefonos">
<h2 id="telefonos">Teléfonos de emergencia</h2>
<ul class="phones">{phones}</ul>
</section>
<section aria-labelledby="enlaces">
<h2 id="enlaces">Información oficial</h2>
<ul class="list">{links}</ul>
</section>
</main>
<footer class="muted small"><p>Fuentes: SENAPRED, Dirección Meteorológica de Chile, CONAF.</p></footer>"""
    return page(f"Riesgo en {comuna['name']}", body)


def index_page(entries: list[tuple[str, str, dict]], generated: str) -> str:
    items = "".join(f'<li><a href="{escape(slug)}/index.html">{escape(name)}</a> {level_badge(s["overall_level"], s["overall_level_label"])}</li>' for slug, name, s in entries)
    body = f"""<header><div>
<h1>Riesgo en mi comuna: Región del Maule</h1>
<p>Información sobre riesgos de desastre para las comunas del Maule</p>
</div></header>
<main>
{snapshot_notice(generated)}
<section aria-labelledby="comunas">
<h2 id="comunas">Comunas</h2>
<p class="muted">Nivel general de cada comuna según el cálculo de la plataforma al momento de generar esta copia.</p>
<ul class="list index">{items}</ul>
</section>
</main>"""
    return page("Riesgo en el Maule", body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static public snapshot for the Maule comunas")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    generated = generated_label(datetime.now(UTC))
    entries = []
    with get_engine().connect() as conn:
        slugs = [r["slug"] for r in rows(conn, "select slug from municipality where cut_code like '07%' order by name")]
        for slug in slugs:
            comuna = public_comuna(slug, conn)
            summary = public_summary(slug, conn)
            sources = public_sources(slug, conn)
            target = args.out / slug
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(comuna_page(comuna, summary, sources, generated), encoding="utf-8")
            entries.append((slug, comuna["name"], summary))
        conn.rollback()
    (args.out / "index.html").write_text(index_page(entries, generated), encoding="utf-8")
    (args.out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(entries)} comuna pages and index written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
