from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection

from app.ai.tools import active_alerts
from app.db import rows
from app.hazards.base import DATA_CLASS_LABEL, DERIVED_NOTICE, LEVEL_LABEL, LEVEL_RANK
from app.risk import assess_comuna, assess_sectors
from app.stats.history import earthquake_statistics, icfsr_context, incident_statistics
from app.tenants import get_municipality

ROLES = {
    "alcalde": "Informe ejecutivo para Alcaldía",
    "emergencias": "Informe de operaciones de emergencia",
    "secplan": "Informe de planificación (SECPLAN)",
    "comunicaciones": "Informe para Comunicaciones",
}
CHILE = ZoneInfo("America/Santiago")


def _item(text: str, data_class: str | None = None, source: str | None = None, updated_at: Any = None) -> dict[str, Any]:
    return {
        "text": text,
        "data_class": data_class,
        "data_class_label": DATA_CLASS_LABEL.get(data_class or "", None),
        "source": source,
        "updated_at": updated_at,
    }


def _local(value: datetime | None) -> str:
    if not value:
        return "sin fecha"
    return f"{value.astimezone(CHILE):%d-%m-%Y %H:%M} hora de Chile ({value.astimezone(UTC):%H:%M} UTC)"


def _assessment_items(assessments: list[dict], detail: bool) -> list[dict]:
    items = []
    for a in assessments:
        items.append(_item(f"{a['hazard_name']}: {LEVEL_LABEL[a['level']]}. {a['headline']}", "derived", "Cálculo de la plataforma"))
        if detail:
            for reason in a["explanation"][:1]:
                items.append(_item(f"   {reason}", "derived", "Cálculo de la plataforma"))
            for e in a["evidence"][:4]:
                items.append(_item(f"   {e['label']}: {e['value']}", e["data_class"], e["source"], e["updated_at"]))
            for m in a["missing"]:
                items.append(_item(f"   Falta: {m}", None, None))
    return items


def _exposure_items(assessments: list[dict], names: bool) -> list[dict]:
    items = []
    for a in assessments:
        for x in a["exposure"]:
            if not x["count"]:
                continue
            text = f"{a['hazard_name']}: {x['count']} {x['label'].lower()}"
            if names:
                listed = ", ".join(i["name"] for i in x["items"][:10] if i.get("name"))
                if listed:
                    text += f" ({listed}{'...' if x['count'] > 10 else ''})"
            items.append(_item(text, x["data_class"], x["source"]))
    return items


def _alert_items(alerts: list[dict]) -> list[dict]:
    if not alerts:
        return [
            _item(
                "No hay alertas oficiales ingresadas en la plataforma. La plataforma no recibe automáticamente las alertas de SENAPRED; consulte senapred.cl/alertas. Que no haya alerta registrada no significa que no haya peligro.",
                None,
                None,
            )
        ]
    return [_item(f"{a['title']} ({a['issuer']}, nivel {a['level']}). Enlace oficial: {a['source_url']}", "official_warning", a["issuer"], a["starts_at"]) for a in alerts]


def _top_sectors(sectors: list[dict], limit: int) -> list[dict]:
    ranked = sorted(sectors, key=lambda s: (LEVEL_RANK[s["overall_level"]], len(s["reasons"])), reverse=True)
    items = []
    for s in ranked[:limit]:
        if LEVEL_RANK[s["overall_level"]] < 2:
            break
        reason = s["reasons"][0] if s["reasons"] else ""
        items.append(_item(f"{s['name']}: {s['overall_level_label']}. {reason}", "derived", "Cálculo de la plataforma"))
    return items or [_item("Ningún sector con nivel calculado moderado o superior.", "derived", "Cálculo de la plataforma")]


def build_report(conn: Connection, municipality_id: int, role: str) -> dict[str, Any]:
    if role not in ROLES:
        raise KeyError(role)
    now = datetime.now(UTC)
    municipality = get_municipality(conn, municipality_id)
    full = assess_comuna(conn, municipality_id, now=now)
    now_mode = [a for a in full["assessments"] if a["hazard"] in ("air_quality", "earthquake", "meteo")]
    risk_mode = [a for a in full["assessments"] if a["hazard"] in ("wildfire", "tsunami", "flood")]
    alerts = active_alerts(conn, municipality_id, now)
    sectors = assess_sectors(conn, municipality_id, now)
    sections: list[dict[str, Any]] = []

    summary_lines = [
        _item(
            f"Nivel general calculado: {full['overall_level_label']}. Corresponde al nivel más alto entre las amenazas evaluadas con datos.",
            "derived",
            "Cálculo de la plataforma",
        )
    ]
    for a in full["assessments"]:
        if LEVEL_RANK[a["level"]] >= 2:
            summary_lines.append(_item(f"{a['hazard_name']}: {a['headline']}", "derived", "Cálculo de la plataforma"))

    if role == "alcalde":
        sections.append({"title": "Resumen ejecutivo", "items": summary_lines})
        sections.append({"title": "Alertas oficiales", "items": _alert_items(alerts)})
        sections.append({"title": "Situación actual", "items": _assessment_items(now_mode, detail=False)})
        sections.append({"title": "Riesgos principales", "items": _assessment_items(risk_mode, detail=False)})
        sections.append({"title": "Infraestructura crítica expuesta", "items": _exposure_items(risk_mode, names=False)})
        sections.append({"title": "Sectores que requieren atención", "items": _top_sectors(sectors, 5)})
    elif role == "emergencias":
        sections.append({"title": "Alertas oficiales", "items": _alert_items(alerts)})
        sections.append({"title": "Condiciones actuales", "items": _assessment_items(now_mode, detail=True)})
        sections.append({"title": "Zonas de riesgo", "items": _assessment_items(risk_mode, detail=True)})
        sections.append({"title": "Infraestructura afectada potencialmente", "items": _exposure_items(risk_mode, names=True)})
        sections.append({"title": "Sectores prioritarios", "items": _top_sectors(sectors, 12)})
        resources = rows(
            conn,
            "select category, count(*) as n, bool_or(is_demo) as demo from municipal_asset where municipality_id = :m group by 1 order by 1",
            m=municipality_id,
        )
        sections.append(
            {
                "title": "Recursos municipales registrados",
                "items": [_item(f"{r['category']}: {r['n']}{' (DEMO)' if r['demo'] else ''}", "municipal", "Registro municipal") for r in resources]
                or [_item("No hay recursos municipales cargados.", None, None)],
            }
        )
    elif role == "secplan":
        icfsr = icfsr_context(conn, municipality["cut_code"])
        if icfsr:
            sections.append(
                {
                    "title": "Factores subyacentes del riesgo (ICFSR)",
                    "items": [
                        _item(f"ICFSR {icfsr['value']:.2f}, nivel {icfsr['level']} (año {icfsr['year']}), posición {icfsr['rank']} de {icfsr['total']} comunas.", "official", icfsr["source"], icfsr["updated_at"]),
                        *[_item(f"   {k}: {v}", "official", icfsr["source"]) for k, v in icfsr["components"].items()],
                        _item(icfsr["note"], None, None),
                    ],
                }
            )
        sections.append({"title": "Riesgo territorial por amenaza", "items": _assessment_items(risk_mode, detail=True)})
        sections.append({"title": "Exposición de infraestructura", "items": _exposure_items(risk_mode, names=True)})
        sections.append({"title": "Sectores vulnerables", "items": _top_sectors(sectors, 15)})
        quake = earthquake_statistics(conn, municipality_id, now=now)
        sections.append(
            {
                "title": "Estadística sísmica",
                "items": [
                    _item(f"{quake['title']} ({quake['period']}): {quake['sample_size']} eventos.", "historical", quake["source"], quake["updated_at"]),
                    _item(quake["trend"]["statement"], "derived", "Cálculo de la plataforma"),
                    _item("Método: " + quake["method"], None, None),
                    *[_item("Limitación: " + lim, None, None) for lim in quake["limitations"]],
                ],
            }
        )
        incidents = incident_statistics(conn, municipality_id)
        if incidents.get("empty"):
            sections.append({"title": "Incidentes históricos municipales", "items": [_item(incidents["message"], None, None)]})
        else:
            sections.append(
                {
                    "title": "Incidentes históricos municipales",
                    "items": [
                        _item(f"{incidents['sample_size']} incidentes, período {incidents['period']}.", "municipal", "Registro municipal"),
                        *[_item(f"   {h['label']}: {h['total']}", "municipal", "Registro municipal") for h in incidents["by_hazard"]],
                        _item(incidents["trend"]["statement"], "derived", "Cálculo de la plataforma"),
                        *[_item("Limitación: " + lim, None, None) for lim in incidents["limitations"]],
                    ],
                }
            )
        sections.append(
            {
                "title": "Recomendaciones para análisis posterior",
                "items": [
                    _item("Cargar los sectores oficiales del municipio para reemplazar las celdas de análisis.", None, None),
                    _item("Cargar el registro histórico de incidentes (inundaciones, remociones, incendios) para habilitar estadísticas y el módulo de inundación.", None, None),
                    _item("Solicitar a la DGA y al SHOA las capas de amenaza en formato de datos para incorporarlas.", None, None),
                ],
            }
        )
    elif role == "comunicaciones":
        verified = []
        for a in now_mode + risk_mode:
            for e in a["evidence"]:
                if e["data_class"] in ("observed", "official", "official_warning"):
                    verified.append(_item(f"{e['label']}: {e['value']}", e["data_class"], e["source"], e["updated_at"]))
        sections.append({"title": "Información verificada disponible", "items": verified[:12] or [_item("Sin datos verificados recientes.", None, None)]})
        sections.append({"title": "Alertas oficiales", "items": _alert_items(alerts)})
        sections.append(
            {
                "title": "Resumen en lenguaje simple",
                "items": [_item(a["headline"], "derived", "Cálculo de la plataforma") for a in full["assessments"] if a["level"] != "SIN_DATOS"],
            }
        )
        draft = _communication_draft(municipality["name"], now_mode, risk_mode, alerts, now)
        sections.append({"title": "Borrador de comunicación pública (requiere revisión antes de publicar)", "items": [_item(draft, None, None)]})

    sources = {}
    for section in sections:
        for item in section["items"]:
            if item["source"]:
                current = sources.get(item["source"])
                if current is None or (item["updated_at"] and (not current or str(item["updated_at"]) > str(current))):
                    sources[item["source"]] = item["updated_at"]
    return {
        "role": role,
        "title": ROLES[role],
        "municipality": municipality["name"],
        "generated_at": now,
        "generated_at_local": _local(now),
        "overall_level": full["overall_level"],
        "overall_level_label": full["overall_level_label"],
        "sections": sections,
        "sources": [{"source": k, "updated_at": v, "updated_at_local": _local(v) if v else None} for k, v in sources.items()],
        "disclaimer": DERIVED_NOTICE + " Esta plataforma no es SENAPRED ni un sistema oficial de alertas.",
    }


def _communication_draft(name: str, now_mode: list[dict], risk_mode: list[dict], alerts: list[dict], now: datetime) -> str:
    parts = [f"BORRADOR. Municipalidad de {name}, {_local(now)}."]
    if alerts:
        for a in alerts:
            parts.append(f"{a['issuer']} mantiene {a['title']}. Más información en {a['source_url']}.")
    else:
        parts.append("Para conocer alertas vigentes, siga los canales oficiales de SENAPRED (senapred.cl).")
    air = next((a for a in now_mode if a["hazard"] == "air_quality" and a["level"] != "SIN_DATOS"), None)
    if air:
        parts.append(f"Calidad del aire: {air['headline']} (mediciones SINCA en línea, no validadas).")
    tsunami = next((a for a in risk_mode if a["hazard"] == "tsunami" and LEVEL_RANK[a["level"]] >= 2), None)
    if tsunami:
        parts.append("Recuerde conocer su zona de evacuación por tsunami y el punto de encuentro más cercano.")
    wildfire = next((a for a in risk_mode if a["hazard"] == "wildfire" and LEVEL_RANK[a["level"]] >= 2), None)
    if wildfire:
        parts.append("La comuna tiene sectores con alta recurrencia de incendios forestales: evite quemas y mantenga limpios los alrededores de su vivienda.")
    parts.append("Antes de publicar: verificar cada dato con la fuente indicada y obtener aprobación de la autoridad.")
    return " ".join(parts)
