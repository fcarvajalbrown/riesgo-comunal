from datetime import timedelta

from app.db import row, rows
from app.hazards.base import Area, Assessment, Evidence, Exposure, HazardContext, HazardModule
from app.hazards.rules import classify_flood

FLOOD_HAZARDS = ("inundacion", "anegamiento", "desborde")


class FloodModule(HazardModule):
    key = "flood"
    name = "Inundación y anegamiento"
    description = "Incidentes y puntos críticos de inundación registrados por el municipio. No hay mapas oficiales de inundación en formato de datos para la mayoría de las comunas."
    modes = ("riesgo", "planificar")
    default_thresholds = {"years": 10, "incidents_moderado": 2, "incidents_alto": 5, "flood_point_buffer_m": 150.0}
    layers = ("municipal_incident", "municipal_asset")

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        since = (ctx.now - timedelta(days=365 * t["years"])).date()
        has_data = row(
            ctx.conn,
            """
            select exists(select 1 from municipal_incident where municipality_id = :mid and hazard = any(:hz))
                or exists(select 1 from municipal_asset where municipality_id = :mid and category = 'punto_critico_inundacion')
                as present,
                exists(select 1 from municipal_incident where municipality_id = :mid and hazard = any(:hz) and is_demo)
                or exists(select 1 from municipal_asset where municipality_id = :mid and category = 'punto_critico_inundacion' and is_demo)
                as demo
            """,
            mid=ctx.municipality_id,
            hz=list(FLOOD_HAZARDS),
        )
        stats = row(
            ctx.conn,
            f"""
            with area as (select {area.geom_sql()} as g)
            select count(*) as n, min(occurred_on) as first_on, max(occurred_on) as last_on,
                   coalesce(sum(affected_people), 0) as people
            from municipal_incident i, area
            where i.municipality_id = :mid and i.hazard = any(:hz) and i.occurred_on >= :since
              and i.geom is not null and st_intersects(i.geom, area.g)
            """,
            mid=ctx.municipality_id,
            hz=list(FLOOD_HAZARDS),
            since=since,
            **area.params(),
        )
        points = rows(
            ctx.conn,
            f"""
            with area as (select {area.geom_sql()} as g)
            select a.id, a.name, a.is_demo, st_x(st_pointonsurface(a.geom)) as lon, st_y(st_pointonsurface(a.geom)) as lat
            from municipal_asset a, area
            where a.municipality_id = :mid and a.category = 'punto_critico_inundacion' and st_intersects(a.geom, area.g)
            order by a.name
            """,
            mid=ctx.municipality_id,
            **area.params(),
        )
        result = classify_flood(stats["n"], bool(has_data["present"]), t)
        demo_note = "Incluye datos DEMO de ejemplo, no reales." if has_data["demo"] else None
        evidence = []
        if has_data["present"]:
            evidence.append(
                Evidence(
                    f"Incidentes de inundación desde {since:%Y}",
                    stats["n"],
                    "historical",
                    "Registro municipal",
                    note=demo_note,
                )
            )
            evidence.append(Evidence("Personas afectadas registradas", stats["people"], "municipal", "Registro municipal", note=demo_note))
        exposure = []
        if points:
            exposure.append(
                Exposure(
                    "municipal:punto_critico_inundacion",
                    "Puntos críticos de inundación" + (" (DEMO)" if any(p["is_demo"] for p in points) else ""),
                    len(points),
                    "municipal",
                    "Registro municipal",
                    points[:25],
                )
            )
        headline = {
            "ALTO": "Esta área se ha inundado repetidamente según los registros municipales.",
            "MODERADO": "Esta área tiene antecedentes de inundación en los registros municipales.",
            "BAJO": "Pocos o ningún antecedente de inundación registrado en esta área.",
            "SIN_DATOS": "No hay datos de inundación cargados para la comuna.",
        }.get(result.level, "")
        explanation = [result.reason]
        if result.level == "SIN_DATOS":
            explanation.append("Cargue incidentes históricos o puntos críticos de inundación en la sección Datos municipales para activar este análisis.")
        missing = [] if has_data["present"] else ["Registros municipales de incidentes de inundación", "Mapa oficial de amenaza de inundación DGA en formato de datos"]
        actions = []
        if result.level in ("ALTO", "MODERADO"):
            actions = ["Revisar sumideros y canales en los puntos críticos antes de lluvias intensas."]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            exposure=exposure,
            missing=missing,
            actions=actions,
            thresholds=t,
            area_name=area.name,
        )
