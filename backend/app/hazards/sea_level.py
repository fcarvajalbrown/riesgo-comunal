from datetime import timedelta

from app.db import rows, scalar
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule

STALE_SECONDS = 3600


def anomalous_gauges(readings: list[dict], threshold: float) -> list[str]:
    gauges: dict[str, list[float]] = {}
    for r in readings:
        if r["parameter"] == "sea_level_oscillation" and r["value"] is not None:
            gauges.setdefault(r["gauge"], []).append(r["value"])
    return sorted(g for g, swings in gauges.items() if len(swings) >= 2 and all(s >= threshold for s in swings))


class SeaLevelModule(HazardModule):
    key = "sea_level"
    name = "Mar y tsunami ahora"
    description = "Nivel del mar en vivo en los mareógrafos de Constitución y Boyeruca (IOC/UNESCO, datos del SHOA) y aviso de oscilación anormal."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"oscillation_m": 0.5}
    layers = ()

    def coastal(self, ctx: HazardContext) -> bool:
        return bool(
            scalar(
                ctx.conn,
                "select 1 from feature f, municipality m where m.id = :mid and f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, m.boundary) limit 1",
                mid=ctx.municipality_id,
            )
        )

    def readings(self, ctx: HazardContext) -> list[dict]:
        return rows(
            ctx.conn,
            """
            select distinct on (o.station_external_id, o.parameter)
                   split_part(o.station_external_id, '-', 1) as gauge, o.station_name, o.parameter, o.value, o.observed_at, o.provenance_id
            from observation o
            where o.source_key = 'ioc_sea_level' and o.observed_at >= :since
            order by o.station_external_id, o.parameter, o.observed_at desc
            """,
            since=ctx.now - timedelta(seconds=STALE_SECONDS),
        )

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        explanation = [
            "Mostramos el nivel del mar medido cada minuto por los mareógrafos de Constitución y Boyeruca, que opera el SHOA y publica la IOC/UNESCO.",
            f"Restamos la marea con una media móvil de 31 minutos. En un día tranquilo el mar oscila menos de 0,25 m; si todos los sensores de un mareógrafo superan {t['oscillation_m']:g} m en la última hora, lo marcamos como oscilación anormal.",
            "Una oscilación anormal puede deberse a un tsunami o a una marejada fuerte. Los avisos oficiales de tsunami son los del SHOA y SENAPRED.",
        ]
        if not self.coastal(ctx):
            return Assessment(self.key, self.name, "INFORMATIVO", "La comuna no tiene borde costero.", explanation, area_name=area.name, thresholds=t)
        readings = self.readings(ctx)
        evidence = [
            Evidence(
                f"{r['station_name']}, {'nivel del mar' if r['parameter'] == 'sea_level' else 'oscilación máxima sin marea en la última hora'}",
                f"{r['value']:.2f} m",
                "observed",
                "IOC/UNESCO (datos del SHOA)",
                r["observed_at"],
                r["provenance_id"],
            )
            for r in readings
        ]
        if not readings:
            return Assessment(self.key, self.name, "SIN_DATOS", "Los mareógrafos de Constitución y Boyeruca no han enviado datos en la última hora.", explanation,
                              evidence=evidence, missing=["Datos recientes de los mareógrafos"], thresholds=t, area_name=area.name)
        anomalous = anomalous_gauges(readings, t["oscillation_m"])
        consensus = f"{len({r['gauge'] for r in readings})} de 2 mareógrafos responden"
        if anomalous:
            names = ", ".join(sorted({r["station_name"].split(" (")[0] for r in readings if r["gauge"] in anomalous}))
            return Assessment(self.key, self.name, "ALTO", f"Oscilación anormal del mar en {names}. Aléjese de la costa y siga las indicaciones del SHOA y SENAPRED.", explanation,
                              evidence=evidence, consensus=consensus, actions=["Aléjese del borde costero hacia terrenos elevados y siga las indicaciones del SHOA y SENAPRED."], thresholds=t, area_name=area.name)
        return Assessment(self.key, self.name, "BAJO", "El nivel del mar se comporta con normalidad en Constitución y Boyeruca.", explanation,
                          evidence=evidence, consensus=consensus, thresholds=t, area_name=area.name)
