from app.config import get_settings
from app.db import row
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import classify_rain


class MeteoModule(HazardModule):
    key = "meteo"
    name = "Lluvia intensa"
    description = "Precipitación acumulada en 24 horas en la estación DMC más cercana. Requiere credenciales de la Dirección Meteorológica de Chile."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"rain_24h_moderado": 30.0, "rain_24h_alto": 60.0, "station_radius_km": 25.0}
    layers = ("dmc_station",)

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        settings = get_settings()
        if not (settings.dmc_user and settings.dmc_token):
            return Assessment(
                hazard=self.key,
                hazard_name=self.name,
                level="SIN_DATOS",
                headline="Sin datos meteorológicos: la conexión con la Dirección Meteorológica de Chile no está configurada.",
                explanation=[
                    "La DMC entrega sus servicios de datos con usuario y clave personal. Un administrador debe registrarse en el portal de servicios climáticos de la DMC y configurar DMC_USER y DMC_TOKEN.",
                    "Mientras tanto, consulte los pronósticos y avisos oficiales en meteochile.gob.cl.",
                ],
                missing=["Credenciales DMC (DMC_USER, DMC_TOKEN)"],
                thresholds=t,
                area_name=area.name,
            )
        obs = row(
            ctx.conn,
            """
            select o.station_name, o.value, o.unit, o.observed_at, o.provenance_id,
                   st_distance(o.geom::geography, st_centroid(m.boundary)::geography) / 1000 as km
            from observation o, municipality m
            where m.id = :mid and o.source_key = 'dmc' and o.parameter = 'aguaCaida24Horas'
              and st_dwithin(o.geom::geography, m.boundary::geography, :radius)
            order by o.observed_at desc, km asc limit 1
            """,
            mid=ctx.municipality_id,
            radius=t["station_radius_km"] * 1000,
        )
        result = classify_rain(obs["value"] if obs else None, t)
        evidence = []
        if obs:
            evidence.append(
                Evidence(
                    f"Precipitación 24 h, estación {obs['station_name']} ({obs['km']:.0f} km)",
                    f"{obs['value']:.1f} {obs['unit'] or 'mm'}",
                    "observed",
                    "Fuente: Dirección Meteorológica de Chile",
                    obs["observed_at"],
                    obs["provenance_id"],
                )
            )
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=result.reason,
            explanation=[
                result.reason,
                "Los umbrales de lluvia son provisionales de la plataforma, no oficiales; el municipio debe definir los suyos.",
                "Las alertas meteorológicas oficiales las emite la Dirección Meteorológica de Chile.",
            ],
            evidence=evidence,
            missing=[] if obs else ["Estación DMC con precipitación cerca de la comuna"],
            thresholds=t,
            area_name=area.name,
        )
