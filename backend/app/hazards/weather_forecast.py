from datetime import timedelta
from zoneinfo import ZoneInfo

from app.db import rows
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import classify_forecast, plain_outlook

CHILE = ZoneInfo("America/Santiago")

FORECAST_NOTE = (
    "Pronóstico de modelo calculado en el centro de la comuna (Weather data by Open-Meteo.com). "
    "No es un aviso oficial: los avisos, alertas y alarmas son los de la Dirección Meteorológica de Chile. "
    "Los umbrales de lluvia son provisionales hasta que la municipalidad defina los suyos."
)


class WeatherForecastModule(HazardModule):
    key = "weather_forecast"
    name = "Pronóstico del tiempo"
    description = "Lluvia, ráfagas y temperatura máximas pronosticadas para las próximas 48 horas en el centro de la comuna (Open-Meteo)."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"rain_24h_moderado": 30.0, "rain_24h_alto": 60.0, "point_radius_km": 30.0, "max_age_hours": 6}
    layers = ()

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        latest = rows(
            ctx.conn,
            """
            with m as materialized (select st_centroid(boundary)::geography as center from municipality where id = :mid)
            select distinct on (o.parameter) o.parameter, o.parameter_name, o.value, o.unit, o.observed_at, o.provenance_id
            from observation o, m
            where o.source_key = 'open_meteo' and o.observed_at >= :since
              and st_dwithin(o.geom::geography, m.center, :radius)
            order by o.parameter, o.observed_at desc, st_distance(o.geom::geography, m.center)
            """,
            mid=ctx.municipality_id,
            since=ctx.now - timedelta(hours=t["max_age_hours"]),
            radius=t["point_radius_km"] * 1000,
        )
        values = {r["parameter"]: r for r in latest}

        def value(parameter: str) -> float | None:
            return values[parameter]["value"] if parameter in values else None

        result = classify_forecast(value("om_rain_24h_max"), value("om_gust_max"), value("om_temp_max"), t)
        issued = max((r["observed_at"] for r in latest), default=None)
        outlook = plain_outlook({k: r["value"] for k, r in values.items()}, issued.astimezone(CHILE).date()) if issued else []
        headline = " ".join(outlook) if outlook else result.reason
        evidence = [
            Evidence(r["parameter_name"], f"{r['value']:g} {r['unit']}", "forecast", "Weather data by Open-Meteo.com", r["observed_at"], r["provenance_id"], FORECAST_NOTE)
            for r in latest
        ]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=headline,
            explanation=[headline, result.reason, FORECAST_NOTE],
            evidence=evidence,
            missing=[] if latest else ["Pronóstico reciente de Open-Meteo"],
            thresholds=t,
            area_name=area.name,
        )
