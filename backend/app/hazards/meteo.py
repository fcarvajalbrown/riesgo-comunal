from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import row, rows
from app.hazards.base import LEVEL_RANK, Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import classify_dmc_warnings, classify_rain

CHILE = ZoneInfo("America/Santiago")
WARNING_NOTE = (
    "El nivel de la plataforma sigue al boletín oficial: Aviso = Moderado, Alerta = Alto, Alarma = Crítico. "
    "El boletín oficial y sus instrucciones son los de la Dirección Meteorológica de Chile."
)


def _local(value: datetime | None) -> str:
    return f"{value.astimezone(CHILE):%d-%m %H:%M} hora de Chile" if value else "sin término indicado"


class MeteoModule(HazardModule):
    key = "meteo"
    name = "Condiciones meteorológicas"
    description = (
        "Avisos, alertas y alarmas oficiales de la Dirección Meteorológica de Chile cuyo polígono cubre la comuna, "
        "y precipitación de 24 horas en la estación DMC más cercana cuando hay credenciales."
    )
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"rain_24h_moderado": 30.0, "rain_24h_alto": 60.0, "station_radius_km": 25.0}
    layers = ("dmc_station", "dmc_warning")

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        now = ctx.now
        warnings = rows(
            ctx.conn,
            """
            select a.level, a.title, a.starts_at, a.ends_at, a.source_url, a.provenance_id, a.properties->>'event' as event
            from alert a, municipality m
            where m.id = :mid and a.source_key = 'dmc_cap' and (a.ends_at is null or a.ends_at > :now)
              and st_relate(a.area, m.boundary, 'T********')
            order by a.starts_at
            """,
            mid=ctx.municipality_id,
            now=now,
        )
        warning_result = classify_dmc_warnings([(w["level"], w["starts_at"] <= now) for w in warnings])
        evidence = [
            Evidence(
                f"{w['level']} DMC: {w['event'] or w['title']}",
                f"vigente hasta {_local(w['ends_at'])}" if w["starts_at"] <= now else f"desde {_local(w['starts_at'])}",
                "official_warning",
                "Fuente: Dirección Meteorológica de Chile (Sistema de Alerta Temprana)",
                w["starts_at"],
                w["provenance_id"],
                w["source_url"],
            )
            for w in warnings
        ]
        missing = []
        explanation = [warning_result.reason, WARNING_NOTE]
        headline = warning_result.reason

        settings = get_settings()
        rain_level = "SIN_DATOS"
        if settings.dmc_user and settings.dmc_token:
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
            rain = classify_rain(obs["value"] if obs else None, t)
            rain_level = rain.level
            explanation.append(rain.reason)
            explanation.append("Los umbrales de lluvia son provisionales de la plataforma, no oficiales; el municipio debe definir los suyos.")
            if LEVEL_RANK[rain_level] > LEVEL_RANK[warning_result.level]:
                headline = rain.reason
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
            else:
                missing.append("Estación DMC con precipitación cerca de la comuna")
        else:
            missing.append("Observaciones de estaciones DMC (requieren DMC_USER y DMC_TOKEN)")

        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=max((warning_result.level, rain_level), key=LEVEL_RANK.__getitem__),
            headline=headline,
            explanation=explanation,
            evidence=evidence,
            missing=missing,
            thresholds=t,
            area_name=area.name,
        )
