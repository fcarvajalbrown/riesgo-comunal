from app.db import rows
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance
from app.hazards.rules import classify_air_quality


class AirQualityModule(HazardModule):
    key = "air_quality"
    name = "Calidad del aire (MP2,5)"
    description = "Material particulado fino medido por estaciones SINCA en la comuna o cercanas. Datos en línea no validados."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"alerta": 80.0, "preemergencia": 110.0, "emergencia": 170.0, "min_hours": 18, "station_radius_km": 5.0}
    layers = ("aq_station",)

    def stations(self, ctx: HazardContext, radius_km: float) -> list[dict]:
        return rows(
            ctx.conn,
            """
            with m as materialized (select boundary as g, boundary::geography as gg from municipality where id = :mid),
            latest as (
                select station_external_id, max(observed_at) as last_at
                from observation where source_key = 'sinca' and parameter = 'PM25' group by 1
            )
            select o.station_external_id, max(o.station_name) as station_name,
                   avg(o.value) as mean_24h, count(*) as hours, max(o.observed_at) as last_at,
                   (array_agg(o.value order by o.observed_at desc))[1] as last_value,
                   max(o.unit) as unit, max(o.provenance_id) as provenance_id,
                   bool_or(st_intersects(o.geom, m.g)) as inside
            from observation o join latest l using (station_external_id), m
            where o.source_key = 'sinca' and o.parameter = 'PM25'
              and o.observed_at > l.last_at - interval '24 hours'
              and st_dwithin(o.geom::geography, m.gg, :radius)
            group by o.station_external_id
            order by mean_24h desc
            """,
            mid=ctx.municipality_id,
            radius=radius_km * 1000,
        )

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        stations = [s for s in self.stations(ctx, t["station_radius_km"]) if (ctx.now - s["last_at"]).total_seconds() < 36 * 3600]
        prov = latest_provenance(ctx.conn, "sinca", "aq_observation")
        if not stations:
            result = classify_air_quality(None, 0, t)
            worst = None
        else:
            worst = stations[0]
            result = classify_air_quality(worst["mean_24h"], worst["hours"], t)
        evidence = [
            Evidence(
                f"MP2,5 estación {s['station_name']}{'' if s['inside'] else ' (fuera de la comuna, cercana)'}",
                f"promedio 24 h {s['mean_24h']:.0f} {s['unit'] or 'µg/m³'} ({s['hours']} h); última hora {s['last_value']:.0f}",
                "observed",
                prov["attribution"],
                s["last_at"],
                s["provenance_id"],
                note="Dato en línea no validado",
            )
            for s in stations
        ]
        headline = {
            "CRITICO": "El aire medido está en niveles de emergencia según la norma de MP2,5.",
            "ALTO": "El aire medido está en niveles de preemergencia según la norma de MP2,5.",
            "MODERADO": "El aire medido supera el nivel de alerta de la norma de MP2,5.",
            "BAJO": "El aire medido está bajo el nivel de alerta de MP2,5.",
            "SIN_DATOS": "No hay mediciones recientes suficientes de MP2,5 para la comuna.",
        }[result.level]
        explanation = [
            result.reason,
            "Los episodios críticos los declara la autoridad competente; este cálculo no es una declaración de episodio.",
            "SINCA publica estos datos en línea sin validar; pueden corregirse después.",
        ]
        missing = [] if stations else ["Estaciones SINCA con MP2,5 dentro de la comuna o a menos de " f"{t['station_radius_km']:.0f} km"]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            missing=missing,
            thresholds=t,
            area_name=area.name,
        )
