from app.db import row, rows, scalar
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance
from app.hazards.exposure import exposure_within
from app.hazards.rules import classify_tsunami

EVACUATION_SQL = """
    select st_intersection(f.geom, (select g from area)) as g
    from feature f
    where f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, (select g from area))
"""

SECTOR_AREA_SQL = """
    select s.id, coalesce(sum(st_area(st_intersection(f.geom, s.geom)::geography)) / 1e6, 0) as km2,
           string_agg(distinct f.properties->>'sector', ', ') as sectores
    from sector s
    left join feature f on f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, s.geom)
    where s.id = any(:ids)
    group by s.id
"""

SECTOR_MEETING_SQL = """
    select s.id, count(f.id) as n
    from sector s
    left join feature f on f.dataset = 'tsunami_meeting_point' and st_dwithin(f.geom::geography, s.geom::geography, 1500)
    where s.id = any(:ids)
    group by s.id
"""


class TsunamiModule(HazardModule):
    key = "tsunami"
    name = "Tsunami"
    description = "Áreas a evacuar y puntos de encuentro por tsunami publicados por SENAPRED (planes de evacuación comunales y SHOA)."
    modes = ("riesgo", "planificar")
    default_thresholds = {"level_if_in_evacuation_area": "ALTO"}
    layers = ("tsunami_evacuation_area", "tsunami_meeting_point")

    def comuna_has_layer(self, ctx: HazardContext) -> bool:
        return bool(
            scalar(
                ctx.conn,
                """
                select 1 from feature f, municipality m
                where m.id = :mid and f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, m.boundary)
                limit 1
                """,
                mid=ctx.municipality_id,
            )
        )

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        km2 = row(
            ctx.conn,
            f"""
            with area as (select {area.geom_sql()} as g)
            select coalesce(sum(st_area(st_intersection(f.geom, area.g)::geography)) / 1e6, 0) as km2,
                   string_agg(distinct f.properties->>'sector', ', ') as sectores
            from feature f, area
            where f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, area.g)
            """,
            **area.params(),
        )
        meeting = rows(
            ctx.conn,
            f"""
            with area as (select {area.geom_sql()} as g)
            select f.id, f.name, st_x(f.geom) as lon, st_y(f.geom) as lat
            from feature f, area
            where f.dataset = 'tsunami_meeting_point' and st_dwithin(f.geom::geography, area.g::geography, 1500)
            order by f.name
            """,
            **area.params(),
        )
        prov = latest_provenance(ctx.conn, "senapred", "tsunami_evacuation_area")
        return self.build(ctx, area, self.comuna_has_layer(ctx), km2, len(meeting), prov)

    def assess_sectors(self, ctx: HazardContext, areas: list[Area]) -> list[Assessment]:
        ids = [a.id for a in areas]
        km2 = {r["id"]: r for r in rows(ctx.conn, SECTOR_AREA_SQL, ids=ids)}
        meeting = {r["id"]: r["n"] for r in rows(ctx.conn, SECTOR_MEETING_SQL, ids=ids)}
        has_layer = self.comuna_has_layer(ctx)
        prov = latest_provenance(ctx.conn, "senapred", "tsunami_evacuation_area")
        return [self.build(ctx, area, has_layer, km2[area.id], meeting[area.id], prov) for area in areas]

    def build(self, ctx: HazardContext, area: Area, comuna_has_layer: bool, km2: dict, meeting_count: int, prov: dict) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        result = classify_tsunami(km2["km2"], comuna_has_layer, t)
        evidence = [
            Evidence(
                "Superficie dentro de área a evacuar",
                f"{km2['km2']:.2f} km²",
                "official",
                prov["attribution"],
                prov["source_time"] or prov["ingested_at"],
                prov["id"],
                note=f"Sectores de evacuación: {km2['sectores']}" if km2["sectores"] else None,
            ),
            Evidence(
                "Puntos de encuentro a menos de 1,5 km",
                meeting_count,
                "official",
                prov["attribution"],
                prov["source_time"] or prov["ingested_at"],
                prov["id"],
            ),
        ]
        exposure = exposure_within(ctx, area, EVACUATION_SQL, {}) if ctx.detail and km2["km2"] > 0 else []
        headline = {
            "ALTO": "Parte del territorio debe evacuarse ante un tsunami.",
            "CRITICO": "Parte del territorio debe evacuarse ante un tsunami.",
            "MODERADO": "Parte del territorio debe evacuarse ante un tsunami.",
            "BAJO": "Esta área queda fuera de las zonas a evacuar por tsunami publicadas.",
            "SIN_DATOS": "No hay información de evacuación por tsunami para esta comuna.",
        }[result.level]
        explanation = [
            result.reason,
            "Recomendación de SENAPRED: si un sismo dificulta mantenerse en pie, evacuar de inmediato sin esperar alerta. Las instrucciones oficiales las entregan SENAPRED y SHOA.",
        ]
        actions = []
        if km2["km2"] > 0:
            actions = [
                "Verificar señalética y estado de vías de evacuación hacia los puntos de encuentro.",
                "Confirmar que los establecimientos dentro del área a evacuar tienen plan de evacuación vigente.",
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
