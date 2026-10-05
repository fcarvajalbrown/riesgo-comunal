from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.db import row, rows
from app.hazards.common import latest_provenance
from app.stats.trend import mann_kendall

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
HAZARD_LABELS = {
    "inundacion": "Inundación",
    "anegamiento": "Anegamiento",
    "desborde": "Desborde de cauce",
    "incendio": "Incendio forestal",
    "remocion": "Remoción en masa",
    "temporal": "Temporal / viento",
    "marejada": "Marejada",
    "sismo": "Sismo",
    "otro": "Otro",
}


def earthquake_statistics(conn: Connection, municipality_id: int, radius_km: float = 150, min_magnitude: float = 4.0,
                          start_year: int = 2000, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    last_complete = now.year - 1
    data = rows(
        conn,
        """
        with m as (select boundary as g from municipality where id = :mid),
        years as (select generate_series(cast(:y0 as int), cast(:y1 as int)) as year)
        select y.year,
               count(e.id) as total,
               count(e.id) filter (where e.magnitude >= 4 and e.magnitude < 5) as m4,
               count(e.id) filter (where e.magnitude >= 5 and e.magnitude < 6) as m5,
               count(e.id) filter (where e.magnitude >= 6) as m6,
               max(e.magnitude) as max_magnitude
        from years y
        left join historical_event e on e.hazard = 'earthquake' and extract(year from e.occurred_at) = y.year
             and e.magnitude >= :minmag
             and e.geom && st_expand((select g from m), :radius / 85000.0)
             and st_dwithin(e.geom::geography, (select g from m)::geography, :radius)
        group by y.year order by y.year
        """,
        mid=municipality_id,
        y0=start_year,
        y1=last_complete,
        minmag=min_magnitude,
        radius=radius_km * 1000,
    )
    prov = latest_provenance(conn, "usgs", "earthquake")
    trend = mann_kendall([float(r["total"]) for r in data])
    total = sum(r["total"] for r in data)
    return {
        "key": "earthquakes_by_year",
        "title": f"Sismos de magnitud {min_magnitude:.0f} o más a menos de {radius_km:.0f} km de la comuna, por año",
        "data_class": "historical",
        "period": f"{start_year}-{last_complete} (años completos)",
        "sample_size": total,
        "series": data,
        "source": prov["attribution"],
        "updated_at": prov["ingested_at"],
        "provenance_id": prov["id"],
        "method": (
            "Conteo anual de eventos del catálogo USGS FDSN con magnitud igual o superior al umbral, cuyo epicentro está "
            "a la distancia indicada del límite comunal (cálculo geodésico en PostGIS). La prueba de tendencia es "
            "Mann-Kendall bilateral con aproximación normal y corrección por empates."
        ),
        "limitations": [
            "USGS es una fuente complementaria; el catálogo oficial chileno es el del Centro Sismológico Nacional, que puede registrar más eventos de baja magnitud.",
            "Las réplicas de un gran terremoto (por ejemplo 2010) concentran conteos en pocos años; el número de sismos no mide por sí solo el peligro sísmico.",
            "La magnitud mínima detectada de forma completa por catálogos globales varía en el tiempo.",
        ],
        "trend": asdict(trend),
    }


def incident_statistics(conn: Connection, municipality_id: int) -> dict[str, Any]:
    summary = row(
        conn,
        """
        select count(*) as n, min(occurred_on) as first_on, max(occurred_on) as last_on,
               bool_or(is_demo) as has_demo, coalesce(sum(affected_people), 0) as people
        from municipal_incident where municipality_id = :mid
        """,
        mid=municipality_id,
    )
    if not summary["n"]:
        return {
            "key": "municipal_incidents",
            "title": "Incidentes registrados por el municipio",
            "data_class": "municipal",
            "sample_size": 0,
            "empty": True,
            "message": "No hay incidentes municipales cargados. Cárguelos en Datos municipales (CSV o GeoJSON) para obtener estadísticas por año, amenaza, sector y mes.",
        }
    by_year = rows(
        conn,
        """
        with years as (select generate_series(extract(year from min(occurred_on))::int, extract(year from max(occurred_on))::int) as year
                       from municipal_incident where municipality_id = :mid)
        select y.year, count(i.id) as total from years y
        left join municipal_incident i on i.municipality_id = :mid and extract(year from i.occurred_on) = y.year
        group by y.year order by y.year
        """,
        mid=municipality_id,
    )
    by_hazard = rows(
        conn,
        "select hazard, count(*) as total, coalesce(sum(affected_people),0) as people from municipal_incident where municipality_id = :mid group by 1 order by 2 desc",
        mid=municipality_id,
    )
    for item in by_hazard:
        item["label"] = HAZARD_LABELS.get(item["hazard"], item["hazard"])
    by_sector = rows(
        conn,
        """
        select coalesce(sector_name, 'Sin sector') as sector, count(*) as total,
               count(distinct extract(year from occurred_on)) as years_with_events
        from municipal_incident where municipality_id = :mid group by 1 order by 2 desc limit 15
        """,
        mid=municipality_id,
    )
    by_month = rows(
        conn,
        "select extract(month from occurred_on)::int as month, count(*) as total from municipal_incident where municipality_id = :mid group by 1 order by 1",
        mid=municipality_id,
    )
    months = {r["month"]: r["total"] for r in by_month}
    seasonality = [{"month": m, "label": MONTHS[m - 1], "total": months.get(m, 0)} for m in range(1, 13)]
    trend = mann_kendall([float(r["total"]) for r in by_year])
    limitations = [
        "Sólo incluye incidentes registrados y cargados por el municipio; la ausencia de registros no significa ausencia de eventos.",
        "Cambios en la forma de registrar incidentes a lo largo de los años pueden crear tendencias aparentes.",
    ]
    if summary["has_demo"]:
        limitations.insert(0, "Incluye datos DEMO de ejemplo que no corresponden a eventos reales.")
    return {
        "key": "municipal_incidents",
        "title": "Incidentes registrados por el municipio",
        "data_class": "municipal",
        "is_demo": bool(summary["has_demo"]),
        "period": f"{summary['first_on']:%Y-%m-%d} a {summary['last_on']:%Y-%m-%d}",
        "sample_size": summary["n"],
        "affected_people": summary["people"],
        "by_year": by_year,
        "by_hazard": by_hazard,
        "by_sector": by_sector,
        "seasonality": seasonality,
        "recurrence": [s for s in by_sector if s["years_with_events"] >= 2],
        "source": "Registro municipal",
        "method": "Conteos por año calendario, tipo de amenaza, sector declarado y mes de ocurrencia. Recurrencia: sectores con incidentes en dos o más años distintos. Tendencia: Mann-Kendall sobre conteos anuales.",
        "limitations": limitations,
        "trend": asdict(trend),
    }


def icfsr_context(conn: Connection, cut_code: str) -> dict[str, Any] | None:
    data = row(
        conn,
        """
        with ranked as (
            select cut_code, year, value, level, components, provenance_id,
                   rank() over (order by value desc) as rank, count(*) over () as total
            from comuna_index where index_key = 'icfsr'
        )
        select * from ranked where cut_code = :c order by year desc limit 1
        """,
        c=cut_code,
    )
    if not data:
        return None
    prov = latest_provenance(conn, "senapred", "icfsr")
    return {
        "key": "icfsr",
        "title": "Índice Comunal de Factores Subyacentes del Riesgo (ICFSR)",
        "data_class": "official",
        "value": data["value"],
        "level": data["level"],
        "year": data["year"],
        "rank": data["rank"],
        "total": data["total"],
        "components": {
            "Ordenamiento Territorial": data["components"].get("ic_ot"),
            "Cambio Climático y Recursos Naturales": data["components"].get("ic_cc"),
            "Condiciones Socioeconómicas y Demográficas": data["components"].get("ic_soc"),
            "Gobernanza": data["components"].get("ic_gob"),
        },
        "source": prov["attribution"],
        "updated_at": prov["source_time"] or prov["ingested_at"],
        "provenance_id": prov["id"],
        "note": (
            "Índice publicado por SENAPRED a partir de un autodiagnóstico comunal de 41 variables en cuatro dimensiones. "
            "Escala 0 a 1; SENAPRED define riesgo mínimo bajo 0,10, bajo 0,10-0,20, moderado 0,20-0,43 y alto desde 0,43. "
            "Describe factores subyacentes del riesgo; no es un nivel de amenaza ni una alerta."
        ),
    }
