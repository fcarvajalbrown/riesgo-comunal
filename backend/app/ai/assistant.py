import json
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.ai.llm import LlmError, chat
from app.ai.tools import call_tool, openai_tool_specs
from app.config import get_settings
from app.hazards.base import LEVEL_LABEL

log = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = """Eres el asistente de una plataforma municipal de información de riesgo de desastres en Chile.
Respondes en español claro a funcionarios municipales y autoridades.

Reglas obligatorias:
1. Sólo afirmas datos que vienen de las herramientas. Si una herramienta no entrega un dato, dices que no está disponible.
2. Nunca inventas alertas oficiales, cifras, lugares, fechas ni nombres.
3. Distingues siempre el tipo de dato: observado, pronóstico, alerta oficial, histórico, municipal o cálculo de la plataforma.
4. Los niveles de riesgo son cálculos de esta plataforma, no evaluaciones oficiales de SENAPRED ni de ningún organismo. Dilo cuando los menciones.
5. Nunca presentas un pronóstico como observación. Esta plataforma no tiene hoy una fuente de pronóstico conectada salvo que la herramienta la entregue.
6. Que no haya una alerta registrada no significa que no haya peligro.
7. No tomas decisiones de emergencia por las autoridades: puedes sugerir qué revisar, indicando que la decisión es de ellas.
8. Incluyes horas de actualización cuando las herramientas las entregan.
9. Si la pregunta es sobre documentos municipales, citas el título y la página.
10. Respuestas breves, con viñetas cuando ayuden. No uses jerga técnica salvo que el usuario la pida.
"""

AUDIENCE_HINT = {
    "ejecutivo": "Responde como resumen ejecutivo para el alcalde o alcaldesa: cinco líneas como máximo, lo más importante primero.",
    "tecnico": "Responde con detalle técnico: incluye cifras, umbrales y método.",
    "vecino": "Explica como a un vecino o vecina, sin tecnicismos, con frases cortas.",
}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


INTENTS: list[tuple[str, tuple[str, dict[str, Any]]]] = [
    (r"llov|lluvi|precipit|pronostic|clima|tiempo hoy", ("situacion_actual", {})),
    (r"ahora|actual|pasando|hoy|situacion|resumen", ("situacion_actual", {})),
    (r"inund|anega|desborde", ("riesgo_por_amenaza", {"amenaza": "flood"})),
    (r"incendi|fuego|forestal", ("riesgo_por_amenaza", {"amenaza": "wildfire"})),
    (r"tsunami|maremoto|evacua", ("riesgo_por_amenaza", {"amenaza": "tsunami"})),
    (r"escuela|colegio|liceo|establecimiento|salud|hospital|cesfam|infraestructura|expuest", ("infraestructura_expuesta", {})),
    (r"sector|primero|priori|revisar|(?<!de )donde", ("sectores_prioritarios", {})),
    (r"sismo|terremoto|temblor", ("estadisticas", {"tipo": "sismos"})),
    (r"aire|humo|contamina|mp2|particulado", ("situacion_actual", {})),
    (r"histori|paso|temporal|estadistic|tendencia|anterior|incidente", ("estadisticas", {"tipo": "incidentes"})),
    (r"icfsr|factores subyacentes|indice", ("estadisticas", {"tipo": "icfsr"})),
    (r"plan |protocolo|procedimiento|documento|dice el|segun el|manual|albergue", ("buscar_documentos", {})),
    (r"fuente|de donde|origen|confiable", ("fuentes", {})),
]


def detect_intents(question: str) -> list[tuple[str, dict[str, Any]]]:
    q = _norm(question)
    found: list[tuple[str, dict[str, Any]]] = []
    for pattern, (tool, args) in INTENTS:
        if re.search(pattern, q):
            call = (tool, dict(args))
            if tool == "buscar_documentos":
                call[1]["consulta"] = question
            if tool == "sectores_prioritarios":
                for hazard_pattern, key in (("inund|anega", "flood"), ("incendi|fuego", "wildfire"), ("tsunami", "tsunami")):
                    if re.search(hazard_pattern, q):
                        call[1]["amenaza"] = key
            if call not in found:
                found.append(call)
    if not found:
        found.append(("situacion_actual", {}))
    return found[:3]


def _fmt_time(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        from zoneinfo import ZoneInfo

        local = value.astimezone(ZoneInfo("America/Santiago"))
        return f"{local:%d-%m-%Y %H:%M} hora de Chile ({value.astimezone(UTC):%H:%M} UTC)"
    return "sin fecha"


def compose_deterministic(question: str, results: list[tuple[str, dict]], audience: str) -> str:
    lines: list[str] = []
    simple = audience == "vecino"
    for tool, result in results:
        data = result["data"]
        if tool in ("situacion_actual", "riesgo_por_amenaza"):
            for a in data["assessments"]:
                label = LEVEL_LABEL[a["level"]]
                lines.append(f"**{a['hazard_name']}: {label}** ({a['data_class_label'].lower()}). {a['headline']}")
                if not simple:
                    for reason in a["explanation"][:2]:
                        lines.append(f"- {reason}")
                    for e in a["evidence"][:3]:
                        lines.append(f"- {e['label']}: {e['value']} [{e['data_class_label']}, {e['source']}]")
                for x in a["exposure"]:
                    if x["count"]:
                        lines.append(f"- {x['label']}: {x['count']}")
                for m in a["missing"]:
                    lines.append(f"- Falta: {m}")
            if tool == "situacion_actual":
                if data["alerts"]:
                    for alert in data["alerts"]:
                        lines.append(f"**{alert['level']} vigente ({alert['issuer']}):** {alert['title']}. Enlace oficial: {alert['source_url']}")
                else:
                    lines.append("No hay alertas oficiales vigentes para la comuna en la plataforma. " + data["alert_feed_note"])
        elif tool == "sectores_prioritarios":
            if not data["sectors"]:
                lines.append("Ningún sector tiene nivel calculado moderado o superior con los datos disponibles.")
            else:
                lines.append(f"**Sectores a revisar primero** ({data['sector_note']}):")
                for s in data["sectors"]:
                    reason = s["reasons"][0] if s["reasons"] else ""
                    lines.append(f"- {s['name']}: {s['level_label']}. {reason}")
        elif tool == "infraestructura_expuesta":
            if not data["exposure"]:
                lines.append("No se encontraron establecimientos ni activos dentro de zonas de amenaza con los datos cargados.")
            for x in data["exposure"]:
                names = ", ".join(i["name"] for i in x["items"][:6] if i.get("name"))
                lines.append(f"- {x['hazard_name']}: {x['count']} {x['label'].lower()} [{x['data_class_label']}]" + (f". Entre ellos: {names}" if names and not simple else ""))
        elif tool == "estadisticas":
            if data is None:
                lines.append("No hay datos del índice para esta comuna.")
            elif data.get("empty"):
                lines.append(data["message"])
            elif data["key"] == "earthquakes_by_year":
                busiest = max(data["series"], key=lambda r: r["total"])
                lines.append(f"**{data['title']}** ({data['period']}): {data['sample_size']} eventos; año con más eventos {busiest['year']} ({busiest['total']}).")
                lines.append(f"- {data['trend']['statement']}")
                if not simple:
                    lines.append(f"- Limitación: {data['limitations'][0]}")
            elif data["key"] == "municipal_incidents":
                lines.append(f"**{data['title']}** ({data['period']}): {data['sample_size']} incidentes.")
                for h in data["by_hazard"][:5]:
                    lines.append(f"- {h['label']}: {h['total']}")
                if data["recurrence"]:
                    lines.append("- Sectores con incidentes en dos o más años: " + ", ".join(s["sector"] for s in data["recurrence"][:6]))
                lines.append(f"- {data['trend']['statement']}")
                if data.get("is_demo"):
                    lines.append("- Atención: incluye datos DEMO de ejemplo, no reales.")
            elif data["key"] == "icfsr":
                lines.append(
                    f"**{data['title']}**: {data['value']:.2f} (nivel {data['level']}, año {data['year']}), posición {data['rank']} de {data['total']} comunas. {data['note']}"
                )
        elif tool == "buscar_documentos":
            if not data["results"]:
                lines.append("No encontré información sobre eso en los documentos municipales cargados.")
            for hit in data["results"][:3]:
                excerpt = hit["content"][:400] + ("..." if len(hit["content"]) > 400 else "")
                lines.append(f"- {hit['source']}{' (DEMO)' if hit['is_demo'] else ''}: \"{excerpt}\"")
        elif tool == "fuentes":
            for s in data["sources"]:
                status = f"última actualización {_fmt_time(s['last_success_at'])}" if s["last_success_at"] else "sin datos aún"
                lines.append(f"- {s['name']} ({s['organization']}): {status}" + (f". Error: {s['last_error'][:120]}" if s["last_error"] else ""))
    return "\n".join(lines)


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for s in sources:
        key = s["source"]
        current = seen.get(key)
        if current is None or (s.get("updated_at") and (not current.get("updated_at") or str(s["updated_at"]) > str(current["updated_at"]))):
            seen[key] = s
    return list(seen.values())


def answer(conn: Connection, municipality_id: int, question: str, audience: str = "ejecutivo") -> dict[str, Any]:
    question = (question or "").strip()[:1000]
    if not question:
        return {"answer": "Escriba una pregunta.", "sources": [], "mode": "none", "tools": []}
    settings = get_settings()
    if settings.llm_enabled:
        try:
            return _answer_with_llm(conn, municipality_id, question, audience)
        except LlmError as exc:
            log.warning("LLM unavailable, falling back: %s", exc)
            result = _answer_deterministic(conn, municipality_id, question, audience)
            result["notice"] = "El modelo de lenguaje no respondió; esta respuesta se armó directamente desde los datos."
            return result
    return _answer_deterministic(conn, municipality_id, question, audience)


def _answer_deterministic(conn, municipality_id, question, audience):
    calls = detect_intents(question)
    results = [(tool, call_tool(conn, municipality_id, tool, args)) for tool, args in calls]
    text = compose_deterministic(question, results, audience)
    sources = _dedupe_sources([s for _, r in results for s in r["sources"]])
    return {
        "answer": text,
        "sources": sources,
        "mode": "datos",
        "tools": [t for t, _ in calls],
        "generated_at": datetime.now(UTC),
        "disclaimer": "Respuesta generada desde los datos de la plataforma. Los niveles son cálculos de la plataforma, no alertas oficiales.",
    }


def _answer_with_llm(conn, municipality_id, question, audience):
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n" + AUDIENCE_HINT.get(audience, AUDIENCE_HINT["ejecutivo"])},
        {"role": "user", "content": question},
    ]
    sources: list[dict] = []
    used: list[str] = []
    for _ in range(MAX_TOOL_ROUNDS):
        reply = chat(messages, tools=openai_tool_specs())
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            content = (reply.get("content") or "").strip()
            if not used:
                fallback = _answer_deterministic(conn, municipality_id, question, audience)
                fallback["notice"] = "El modelo respondió sin consultar datos; se muestra la respuesta construida desde los datos."
                return fallback
            return {
                "answer": content,
                "sources": _dedupe_sources(sources),
                "mode": "llm",
                "tools": used,
                "generated_at": datetime.now(UTC),
                "disclaimer": "Respuesta redactada por un modelo de lenguaje a partir de los datos consultados (ver fuentes). Puede contener errores de redacción; verifique las cifras en las fuentes.",
            }
        messages.append({"role": "assistant", "content": reply.get("content"), "tool_calls": tool_calls})
        for call in tool_calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if name not in {t["function"]["name"] for t in openai_tool_specs()}:
                content = json.dumps({"error": "herramienta desconocida"})
            else:
                result = call_tool(conn, municipality_id, name, arguments)
                sources.extend(result["sources"])
                used.append(name)
                content = json.dumps(result["data"], ensure_ascii=False, default=str)[:12000]
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    raise LlmError("demasiadas rondas de herramientas")
