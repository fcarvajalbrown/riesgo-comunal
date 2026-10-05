from datetime import timedelta

from app.db import rows
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance


class EarthquakeModule(HazardModule):
    key = "earthquake"
    name = "Sismos recientes"
    description = "Sismos de las últimas 72 horas cerca de la comuna según USGS (fuente complementaria; la fuente oficial chilena es el CSN)."
    modes = ("ahora", "planificar")
    spatial = False
    default_thresholds = {"radius_km": 150.0, "min_magnitude": 4.0, "hours": 72}
    layers = ("earthquake",)

    def recent(self, ctx: HazardContext, t: dict) -> list[dict]:
        return rows(
            ctx.conn,
            """
            select e.id, e.external_id, e.occurred_at, e.magnitude, coalesce(e.depth_km, 0) as depth_km, e.place, e.provenance_id,
                   st_x(e.geom) as lon, st_y(e.geom) as lat,
                   st_distance(e.geom::geography, m.boundary::geography) / 1000 as distance_km
            from historical_event e, municipality m
            where m.id = :mid and e.hazard = 'earthquake' and e.occurred_at >= :since
              and e.magnitude >= :minmag and st_dwithin(e.geom::geography, m.boundary::geography, :radius)
            order by e.occurred_at desc
            """,
            mid=ctx.municipality_id,
            since=ctx.now - timedelta(hours=t["hours"]),
            minmag=t["min_magnitude"],
            radius=t["radius_km"] * 1000,
        )

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        events = self.recent(ctx, t)
        prov = latest_provenance(ctx.conn, "usgs", "earthquake")
        evidence = [
            Evidence(
                f"M{e['magnitude']:.1f} {e['place'] or ''}",
                f"a {e['distance_km']:.0f} km de la comuna, profundidad {e['depth_km']:.0f} km",
                "observed",
                prov["attribution"],
                e["occurred_at"],
                e["provenance_id"],
            )
            for e in events
        ]
        if events:
            strongest = max(events, key=lambda e: e["magnitude"])
            headline = f"{len(events)} sismo(s) de magnitud {t['min_magnitude']:.0f} o más en las últimas {t['hours']} horas a menos de {t['radius_km']:.0f} km; el mayor fue M{strongest['magnitude']:.1f}."
        else:
            headline = f"Sin sismos de magnitud {t['min_magnitude']:.0f} o más en las últimas {t['hours']} horas a menos de {t['radius_km']:.0f} km."
        explanation = [
            "Información de sismos ya ocurridos. Los sismos no se pueden pronosticar y esta plataforma no lo intenta.",
            "Fuente complementaria USGS. La información sísmica oficial de Chile es la del Centro Sismológico Nacional.",
        ]
        updated = prov["source_time"] or prov["ingested_at"]
        if updated is None or (ctx.now - updated).total_seconds() > 3 * 3600:
            return Assessment(
                hazard=self.key,
                hazard_name=self.name,
                level="SIN_DATOS",
                headline="El catálogo de sismos no se ha actualizado en las últimas 3 horas.",
                explanation=explanation,
                evidence=evidence,
                missing=["Actualización reciente del catálogo USGS"],
                thresholds=t,
                area_name=area.name,
            )
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level="INFORMATIVO",
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            thresholds=t,
            area_name=area.name,
        )
