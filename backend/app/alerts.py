from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.db import rows
from app.hazards.rules import senapred_feed_problem

ALERT_ORIGIN = {
    "dmc_cap": "canal oficial CAP de la DMC",
    "senapred_alertas": "leída de la página pública senapred.cl/alertas",
    "shoa_snam": "leída de la tabla pública de boletines del SNAM (snamchile.cl)",
    "gdacs": "fuente internacional GDACS (gdacs.org), no reemplaza el aviso oficial",
    "ptwc_tsunami": "fuente internacional PTWC/NTWC de NOAA (tsunami.gov), no reemplaza el aviso oficial del SHOA",
}
FALLBACK_SOURCES = ("gdacs", "ptwc_tsunami")
ALERT_FEED_NOTE = (
    "Los avisos, alertas y alarmas meteorológicas de la Dirección Meteorológica de Chile se reciben automáticamente desde su canal oficial CAP. "
    "Las alertas de SENAPRED (temprana preventiva, amarilla, roja) se leen automáticamente cada 10 minutos desde la página pública senapred.cl/alertas, "
    "que no es un servicio oficial de datos: confirme siempre en senapred.cl. Los boletines de tsunami del SHOA se leen cada 5 minutos desde la tabla pública del SNAM (snamchile.cl), que tampoco es un servicio oficial de datos. El municipio también puede ingresar alertas con su enlace oficial. "
    "Como respaldo se leen fuentes internacionales (GDACS y los centros de alerta de tsunami de NOAA), que no reemplazan los avisos oficiales de SENAPRED ni del SHOA."
)


def active_alerts(conn: Connection, municipality_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    return rows(
        conn,
        """
        select a.id, a.issuer, a.hazard, a.level, a.title, a.description, a.source_url, a.starts_at, a.ends_at,
               a.data_class, a.created_at, a.source_key, a.properties, a.provenance_id,
               a.source_key is not null as automatic
        from alert a, municipality m
        where m.id = :m
          and (a.municipality_id = m.id or (a.municipality_id is null and (
                case when a.properties ? 'cut_codes'
                     then m.cut_code in (select jsonb_array_elements_text(a.properties->'cut_codes'))
                     else a.area is null and a.source_key is null or st_relate(a.area, m.boundary, 'T********')
                end)))
          and (a.ends_at is null or a.ends_at > :now)
          and (a.source_key is null and a.starts_at <= :now or a.source_key is not null)
        order by case a.level when 'Alarma' then 0 when 'Alerta' then 1 else 2 end, a.starts_at desc
        """,
        m=municipality_id,
        now=now,
    )


def alert_feed_status(conn: Connection, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    found = {
        r["key"]: r
        for r in rows(
            conn,
            "select key, name, enabled, last_success_at, last_error, interval_minutes from source where key = any(:k)",
            k=["senapred_alertas", *FALLBACK_SOURCES],
        )
    }
    senapred = found.get("senapred_alertas")
    problem = (
        senapred_feed_problem(senapred["last_success_at"], senapred["last_error"], senapred["interval_minutes"], now, senapred["enabled"])
        if senapred
        else "La lectura automática de alertas de SENAPRED no está registrada en la plataforma."
    )
    fallbacks = [
        {"key": key, "name": found[key]["name"], "last_success_at": found[key]["last_success_at"]}
        for key in FALLBACK_SOURCES
        if key in found and not senapred_feed_problem(found[key]["last_success_at"], found[key]["last_error"], found[key]["interval_minutes"], now, found[key]["enabled"])
    ]
    message = None
    if problem:
        active = ", ".join(f["name"] for f in fallbacks) or "ninguna (las fuentes de respaldo tampoco tienen lecturas recientes)"
        message = f"{problem} Fuentes de respaldo internacionales activas: {active}. Confirme las alertas oficiales en senapred.cl y shoa.cl."
    return {"senapred_ok": problem is None, "senapred_problem": problem, "fallbacks": fallbacks, "message": message}
