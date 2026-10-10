from datetime import timedelta

from app.db import rows, scalar
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.sources.glofas_flood import FORECAST_DAYS, river_points

STALE_HOURS = 36
SOURCE = "Copernicus GloFAS (vía Open-Meteo)"
ACTIONS = ["Manténgase lejos de las riberas de ríos y esteros y siga las indicaciones de SENAPRED y de su municipalidad."]


def flood_level(values: dict[str, float], share: float) -> str:
    members = values.get("glofas_members", 0.0)
    if not members:
        return "SIN_DATOS"
    if values.get("glofas_over_5y", 0.0) >= share * members:
        return "ALTO"
    if values.get("glofas_over_2y", 0.0) >= share * members:
        return "MODERADO"
    return "BAJO"


def trend_sentence(thresholds: dict) -> str:
    if not thresholds["nonstationary"]:
        return f"Las crecidas máximas de este río no muestran una tendencia clara en {thresholds['years']} (prueba de Mann-Kendall), así que los umbrales usan todo ese período por igual."
    direction = "bajado" if thresholds["trend_m3s_per_year"] < 0 else "subido"
    return (
        f"Las crecidas máximas de este río han {direction} unos {abs(thresholds['trend_m3s_per_year']):.0f} m³/s por año en {thresholds['years']} (prueba de Mann-Kendall, p = {thresholds['mann_kendall_p']:.3f}). "
        f"Por eso ajustamos los umbrales a {thresholds['present_year']} con la pendiente de Sen."
    )


class RiverFloodModule(HazardModule):
    key = "river_flood"
    name = "Crecidas de ríos"
    description = "Pronóstico de caudal del río principal de la comuna para los próximos 7 días (51 escenarios de Copernicus GloFAS), comparado con sus caudales de crecida de 2, 5 y 20 años."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"member_share": 0.5}
    layers = ()

    def cut_code(self, ctx: HazardContext) -> str | None:
        return scalar(ctx.conn, "select cut_code from municipality where id = :mid", mid=ctx.municipality_id)

    def readings(self, ctx: HazardContext, cut: str) -> list[dict]:
        return rows(
            ctx.conn,
            """
            select distinct on (o.parameter) o.parameter, o.value, o.observed_at, o.provenance_id
            from observation o
            where o.source_key = 'glofas_flood' and o.station_external_id = :station and o.observed_at >= :since
            order by o.parameter, o.observed_at desc
            """,
            station=f"glofas-{cut}",
            since=ctx.now - timedelta(hours=STALE_HOURS),
        )

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        cut = self.cut_code(ctx)
        point = river_points().get(cut or "")
        if point is None:
            return Assessment(self.key, self.name, "SIN_DATOS", "No tenemos un río modelado para esta comuna.", [], area_name=area.name, thresholds=t)
        levels = point["thresholds"]["levels"]
        explanation = [
            f"Seguimos el río principal de la comuna en el modelo hidrológico global GloFAS de Copernicus (celda de 5 km en {point['lat']:.3f}, {point['lon']:.3f}), con 51 escenarios de pronóstico para los próximos {FORECAST_DAYS} días.",
            f"Caudal de crecida que se espera una vez cada 2 años: {levels['2']:.0f} m³/s; cada 5 años: {levels['5']:.0f} m³/s; cada 20 años: {levels['20']:.0f} m³/s. Los calculamos como GloFAS, con una distribución de Gumbel ajustada por L-momentos a las crecidas máximas de cada año.",
            trend_sentence(point["thresholds"]),
            "Si al menos la mitad de los escenarios supera el caudal de 2 años, el nivel es Moderado; si supera el de 5 años, Alto. Es un modelo global: no reemplaza las mediciones de la DGA ni los avisos de SENAPRED.",
        ]
        readings = self.readings(ctx, cut)
        values = {r["parameter"]: r["value"] for r in readings}
        missing = ["Mediciones de caudal en tiempo real de la DGA (no encontramos un servicio de datos público)"]
        if not readings:
            return Assessment(self.key, self.name, "SIN_DATOS", "No hemos recibido el pronóstico de caudal en las últimas 36 horas.", explanation, missing=missing + ["Pronóstico reciente de GloFAS"], thresholds=t, area_name=area.name)
        latest = max(readings, key=lambda r: r["observed_at"])
        evidence = []
        if "glofas_discharge_today" in values:
            evidence.append(Evidence("Caudal de hoy según el modelo", f"{values['glofas_discharge_today']:.0f} m³/s", "forecast", SOURCE, latest["observed_at"], latest["provenance_id"]))
        if "glofas_peak_median" in values:
            evidence.append(Evidence(f"Caudal máximo esperado en {FORECAST_DAYS} días (mediana)", f"{values['glofas_peak_median']:.0f} m³/s", "forecast", SOURCE, latest["observed_at"], latest["provenance_id"]))
        members = int(values.get("glofas_members", 0))
        for period in ("2", "5", "20"):
            evidence.append(Evidence(f"Escenarios sobre el caudal de crecida de {period} años ({levels[period]:.0f} m³/s)", f"{int(values.get(f'glofas_over_{period}y', 0))} de {members}", "forecast", SOURCE, latest["observed_at"], latest["provenance_id"]))
        level = flood_level(values, t["member_share"])
        over2 = int(values.get("glofas_over_2y", 0))
        consensus = f"{over2} de {members} escenarios del pronóstico superan el caudal de crecida de 2 años"
        exceptional = values.get("glofas_over_20y", 0.0) >= t["member_share"] * members > 0
        headline = {
            "ALTO": f"El río principal podría tener una crecida grande en los próximos {FORECAST_DAYS} días: la mayoría de los escenarios supera el caudal que se espera una vez cada 5 años" + (" e incluso el de 20 años." if exceptional else "."),
            "MODERADO": f"El río principal podría crecer en los próximos {FORECAST_DAYS} días: la mayoría de los escenarios supera el caudal que se espera una vez cada 2 años.",
            "BAJO": f"El río principal no debería salirse de lo habitual en los próximos {FORECAST_DAYS} días.",
            "SIN_DATOS": "El pronóstico de caudal llegó sin escenarios.",
        }[level]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=level,
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            missing=missing,
            actions=ACTIONS if level in ("MODERADO", "ALTO") else [],
            consensus=consensus,
            thresholds=t,
            area_name=area.name,
        )
