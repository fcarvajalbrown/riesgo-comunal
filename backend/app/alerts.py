from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.db import rows

ALERT_ORIGIN = {
    "dmc_cap": "canal oficial CAP de la DMC",
    "senapred_alertas": "leída de la página pública senapred.cl/alertas",
}
ALERT_FEED_NOTE = (
    "Los avisos, alertas y alarmas meteorológicas de la Dirección Meteorológica de Chile se reciben automáticamente desde su canal oficial CAP. "
    "Las alertas de SENAPRED (temprana preventiva, amarilla, roja) se leen automáticamente cada 10 minutos desde la página pública senapred.cl/alertas, "
    "que no es un servicio oficial de datos: confirme siempre en senapred.cl. El municipio también puede ingresar alertas con su enlace oficial."
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
          and (a.municipality_id = m.id or (a.municipality_id is null and (a.area is null and a.source_key is null or st_relate(a.area, m.boundary, 'T********'))))
          and (a.ends_at is null or a.ends_at > :now)
          and (a.source_key is null and a.starts_at <= :now or a.source_key is not null)
        order by case a.level when 'Alarma' then 0 when 'Alerta' then 1 else 2 end, a.starts_at desc
        """,
        m=municipality_id,
        now=now,
    )
