from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.ai.rag import search_documents
from app.alerts import ALERT_FEED_NOTE, ALERT_ORIGIN, active_alerts
from app.db import rows
from app.hazards.base import LEVEL_LABEL, LEVEL_RANK
from app.risk import assess_comuna, assess_sectors
from app.stats.history import earthquake_statistics, icfsr_context, incident_statistics
from app.tenants import get_municipality


def _source(label: str, updated_at: Any = None, data_class: str | None = None, provenance_id: int | None = None) -> dict[str, Any]:
    return {"source": label, "updated_at": updated_at, "data_class": data_class, "provenance_id": provenance_id}


def _sources_from_assessments(assessments: list[dict]) -> list[dict]:
    result = []
    for a in assessments:
        for e in a["evidence"]:
            result.append(_source(e["source"], e["updated_at"], e["data_class"], e["provenance_id"]))
        for x in a["exposure"]:
            result.append(_source(x["source"], None, x["data_class"]))
        result.append(_source("Cálculo de la plataforma (reglas publicadas)", a.get("computed_at"), "derived"))
    return result


def tool_situacion_actual(conn: Connection, municipality_id: int, **_) -> dict[str, Any]:
    now = datetime.now(UTC)
    result = assess_comuna(conn, municipality_id, mode="ahora", now=now)
    alerts = active_alerts(conn, municipality_id, now)
    sources = _sources_from_assessments(result["assessments"])
    sources += [
        _source(
            f"{a['issuer']} ({ALERT_ORIGIN.get(a['source_key'], 'alerta ingresada por el municipio')}, {a['source_url']})",
            a["starts_at"],
            "official_warning",
        )
        for a in alerts
    ]
    return {
        "data": {
            "assessments": result["assessments"],
            "alerts": alerts,
            "alert_feed_note": ALERT_FEED_NOTE,
            "computed_at": now,
        },
        "sources": sources,
    }


def tool_riesgo(conn: Connection, municipality_id: int, amenaza: str | None = None, **_) -> dict[str, Any]:
    result = assess_comuna(conn, municipality_id, mode="riesgo")
    assessments = [a for a in result["assessments"] if not amenaza or a["hazard"] == amenaza]
    return {"data": {"assessments": assessments, "computed_at": result["computed_at"]}, "sources": _sources_from_assessments(assessments)}


def tool_sectores_prioritarios(conn: Connection, municipality_id: int, amenaza: str | None = None, limite: int = 8, **_) -> dict[str, Any]:
    sectors = assess_sectors(conn, municipality_id)

    def level_of(s):
        return s["levels"].get(amenaza, "SIN_DATOS") if amenaza else s["overall_level"]

    ranked = sorted(sectors, key=lambda s: (LEVEL_RANK[level_of(s)], len(s["reasons"])), reverse=True)
    top = [
        {"id": s["id"], "name": s["name"], "kind": s["kind"], "is_demo": s["is_demo"], "level": level_of(s),
         "level_label": LEVEL_LABEL[level_of(s)], "reasons": s["reasons"]}
        for s in ranked
        if LEVEL_RANK[level_of(s)] >= 2
    ][:limite]
    kind = sectors[0]["kind"] if sectors else "analysis_cell"
    return {
        "data": {
            "sectors": top,
            "total_sectors": len(sectors),
            "sector_kind": kind,
            "sector_note": "Las celdas de análisis son una grilla de ~1,6 km generada por la plataforma porque el municipio no ha cargado sus sectores." if kind == "analysis_cell" else "Sectores definidos por el municipio.",
        },
        "sources": [_source("Cálculo de la plataforma (reglas publicadas)", None, "derived")],
    }


def tool_infraestructura_expuesta(conn: Connection, municipality_id: int, amenaza: str | None = None, **_) -> dict[str, Any]:
    result = assess_comuna(conn, municipality_id, mode="riesgo")
    exposures = []
    for a in result["assessments"]:
        if amenaza and a["hazard"] != amenaza:
            continue
        for x in a["exposure"]:
            if x["count"]:
                exposures.append({"hazard": a["hazard"], "hazard_name": a["hazard_name"], **x})
    return {"data": {"exposure": exposures, "computed_at": result["computed_at"]}, "sources": _sources_from_assessments(result["assessments"])}


def tool_estadisticas(conn: Connection, municipality_id: int, tipo: str = "incidentes", **_) -> dict[str, Any]:
    municipality = get_municipality(conn, municipality_id)
    if tipo == "sismos":
        stats = earthquake_statistics(conn, municipality_id)
        return {"data": stats, "sources": [_source(stats["source"], stats["updated_at"], "historical", stats["provenance_id"])]}
    if tipo == "icfsr":
        stats = icfsr_context(conn, municipality["cut_code"])
        return {"data": stats, "sources": [_source(stats["source"], stats["updated_at"], "official", stats["provenance_id"])] if stats else []}
    stats = incident_statistics(conn, municipality_id)
    return {"data": stats, "sources": [_source("Registro municipal", None, "municipal")] if stats.get("sample_size") else []}


def tool_buscar_documentos(conn: Connection, municipality_id: int, consulta: str = "", **_) -> dict[str, Any]:
    hits = search_documents(conn, municipality_id, consulta)
    return {
        "data": {"results": hits, "query": consulta},
        "sources": [_source(h["source"] + (" (DEMO)" if h["is_demo"] else ""), h["created_at"], "municipal") for h in hits],
    }


def tool_fuentes(conn: Connection, municipality_id: int, **_) -> dict[str, Any]:
    data = rows(
        conn,
        "select key, name, organization, authority, commercial_use, last_success_at, last_error, enabled from source order by key",
    )
    return {"data": {"sources": data}, "sources": [_source(d["name"], d["last_success_at"], None) for d in data]}


TOOLS = {
    "situacion_actual": (tool_situacion_actual, "Situación actual en la comuna: calidad del aire, sismos recientes, lluvia (si hay datos) y alertas oficiales ingresadas.", {}),
    "riesgo_por_amenaza": (
        tool_riesgo,
        "Nivel de riesgo calculado por la plataforma para la comuna, por amenaza, con evidencia y explicación.",
        {"amenaza": {"type": "string", "enum": ["wildfire", "tsunami", "flood"], "description": "Opcional: wildfire, tsunami o flood"}},
    ),
    "sectores_prioritarios": (
        tool_sectores_prioritarios,
        "Sectores o celdas de la comuna con mayor nivel calculado, para priorizar revisiones.",
        {"amenaza": {"type": "string", "enum": ["wildfire", "tsunami", "flood"]}, "limite": {"type": "integer"}},
    ),
    "infraestructura_expuesta": (
        tool_infraestructura_expuesta,
        "Establecimientos educacionales, de salud y activos municipales dentro de zonas de amenaza.",
        {"amenaza": {"type": "string", "enum": ["wildfire", "tsunami", "flood"]}},
    ),
    "estadisticas": (
        tool_estadisticas,
        "Estadísticas históricas: 'incidentes' municipales, 'sismos' por año, o 'icfsr' (índice SENAPRED).",
        {"tipo": {"type": "string", "enum": ["incidentes", "sismos", "icfsr"]}},
    ),
    "buscar_documentos": (
        tool_buscar_documentos,
        "Busca en los documentos municipales cargados (planes de emergencia, protocolos).",
        {"consulta": {"type": "string"}},
    ),
    "fuentes": (tool_fuentes, "Estado y origen de las fuentes de datos de la plataforma.", {}),
}


def openai_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": params, "additionalProperties": False},
            },
        }
        for name, (_, description, params) in TOOLS.items()
    ]


def call_tool(conn: Connection, municipality_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    func, _, params = TOOLS[name]
    clean = {k: v for k, v in (arguments or {}).items() if k in params}
    return func(conn, municipality_id, **clean)
