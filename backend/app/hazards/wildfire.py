from app.db import row
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance
from app.hazards.exposure import exposure_within
from app.hazards.rules import classify_wildfire

HIGH_CLASSES_SQL = """
    select st_intersection(f.geom, (select g from area)) as g
    from feature f
    where f.dataset = 'wildfire_hazard' and (f.properties->>'clase')::int >= 4
      and st_intersects(f.geom, (select g from area))
"""


class WildfireModule(HazardModule):
    key = "wildfire"
    name = "Incendio forestal"
    description = "Recurrencia histórica de incendios forestales 2020-2024 (mapa de amenaza SENAPRED con datos CONAF) y exposición de establecimientos."
    modes = ("riesgo", "planificar")
    default_thresholds = {"high_share_critico": 0.30, "high_share_alto": 0.10, "mid_share_moderado": 0.10}
    layers = ("wildfire_hazard",)

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        stats = row(
            ctx.conn,
            f"""
            with area as (select {area.geom_sql()} as g),
            parts as (
                select (f.properties->>'clase')::int as clase,
                       st_area(st_intersection(f.geom, area.g)::geography) / 1e6 as km2
                from feature f, area
                where f.dataset = 'wildfire_hazard' and st_intersects(f.geom, area.g)
            )
            select (select st_area(g::geography) / 1e6 from area) as area_km2,
                   coalesce(sum(km2), 0) as covered,
                   coalesce(sum(km2) filter (where clase >= 3), 0) as ge3,
                   coalesce(sum(km2) filter (where clase >= 4), 0) as ge4,
                   coalesce(sum(km2) filter (where clase = 5), 0) as c5
            from parts
            """,
            **area.params(),
        )
        result = classify_wildfire(stats["area_km2"], stats["ge3"], stats["ge4"], stats["covered"], t)
        prov = latest_provenance(ctx.conn, "senapred", "wildfire_hazard")
        evidence = [
            Evidence("Superficie analizada", f"{stats['area_km2']:.1f} km²", "derived", "Cálculo de la plataforma"),
            Evidence(
                "Superficie con recurrencia Alta o Muy alta (2020-2024)",
                f"{stats['ge4']:.1f} km²",
                "official",
                prov["attribution"],
                prov["source_time"] or prov["ingested_at"],
                prov["id"],
            ),
            Evidence(
                "Superficie con recurrencia Media o superior",
                f"{stats['ge3']:.1f} km²",
                "official",
                prov["attribution"],
                prov["source_time"] or prov["ingested_at"],
                prov["id"],
            ),
        ]
        exposure = exposure_within(ctx, area, HIGH_CLASSES_SQL, {}) if ctx.detail and stats["ge4"] > 0 else []
        exposed_total = sum(e.count for e in exposure)
        headline = {
            "CRITICO": "Gran parte del territorio tiene recurrencia alta de incendios forestales.",
            "ALTO": "Hay sectores con recurrencia alta de incendios forestales.",
            "MODERADO": "Hay sectores con recurrencia media de incendios forestales.",
            "BAJO": "La recurrencia de incendios registrada es baja.",
            "SIN_DATOS": "No hay datos de recurrencia de incendios para esta área.",
        }[result.level]
        explanation = [
            result.reason,
            "La recurrencia describe dónde hubo más incendios en las últimas cinco temporadas; no es un pronóstico del día.",
        ]
        if exposed_total:
            explanation.append(f"{exposed_total} establecimientos o activos están dentro de zonas de recurrencia Alta o Muy alta.")
        actions = []
        if result.level in ("ALTO", "CRITICO"):
            actions = [
                "Revisar cortafuegos y limpieza de microbasurales en los sectores de interfaz señalados.",
                "Verificar rutas de evacuación y comunicación con los establecimientos expuestos.",
            ]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            exposure=exposure,
            actions=actions,
            thresholds=t,
            area_name=area.name,
        )
