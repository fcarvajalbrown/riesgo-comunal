from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from app.db import rows, scalar
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance

COASTAL_ACTIONS = [
    "Si está en el borde costero y el sismo le dificulta mantenerse en pie, evacúe de inmediato hacia un punto de encuentro o área de seguridad.",
    "Si el mar se recoge de forma anormal, evacúe de inmediato hacia terrenos elevados.",
    "Evacúe a pie, siga las vías de evacuación señalizadas y regrese solo cuando las autoridades lo indiquen.",
]
CATALOGUES = {"usgs": "USGS", "emsc": "EMSC"}
SAME_QUAKE_SECONDS = 90
SAME_QUAKE_KM = 100.0
MAGNITUDE_MARGIN = 0.5
STALE_SECONDS = 3 * 3600


def distance_km(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def same_quake(a: dict, b: dict) -> bool:
    return abs((a["occurred_at"] - b["occurred_at"]).total_seconds()) <= SAME_QUAKE_SECONDS and distance_km(a, b) <= SAME_QUAKE_KM


def merge_quakes(events: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for event in sorted(events, key=lambda e: e["occurred_at"]):
        match = next((g for g in groups if event["source_key"] not in {e["source_key"] for e in g} and any(same_quake(event, e) for e in g)), None)
        if match is None:
            groups.append([event])
        else:
            match.append(event)
    return groups


def reading(event: dict) -> str:
    author = f", solución del {event['author']}" if event.get("author") == "CSN" else ""
    return f"{CATALOGUES.get(event['source_key'], event['source_key'])} M{event['magnitude']:.1f}{author}"


class EarthquakeModule(HazardModule):
    key = "earthquake"
    name = "Sismos recientes"
    description = "Sismos sentidos de las últimas 24 horas cerca de la comuna, cruzando los catálogos USGS y EMSC (EMSC incluye soluciones del CSN)."
    modes = ("ahora", "planificar")
    spatial = False
    default_thresholds = {"radius_km": 200.0, "min_magnitude": 4.5, "hours": 24}
    layers = ("earthquake",)

    def recent(self, ctx: HazardContext, t: dict) -> list[dict]:
        return rows(
            ctx.conn,
            """
            select e.id, e.source_key, e.external_id, e.occurred_at, e.magnitude, coalesce(e.depth_km, 0) as depth_km, e.place,
                   e.provenance_id, e.properties->>'author' as author, st_x(e.geom) as lon, st_y(e.geom) as lat,
                   st_distance(e.geom::geography, m.boundary::geography) / 1000 as distance_km
            from historical_event e, municipality m
            where m.id = :mid and e.hazard = 'earthquake' and e.source_key = any(:sources) and e.occurred_at >= :since
              and e.magnitude >= :minmag and st_dwithin(e.geom::geography, m.boundary::geography, :radius)
            order by e.occurred_at desc
            """,
            mid=ctx.municipality_id,
            sources=list(CATALOGUES),
            since=ctx.now - timedelta(hours=t["hours"]),
            minmag=t["min_magnitude"] - MAGNITUDE_MARGIN,
            radius=t["radius_km"] * 1000,
        )

    def coastal(self, ctx: HazardContext) -> bool:
        return bool(
            scalar(
                ctx.conn,
                "select 1 from feature f, municipality m where m.id = :mid and f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, m.boundary) limit 1",
                mid=ctx.municipality_id,
            )
        )

    def live_catalogues(self, ctx: HazardContext) -> list[str]:
        live = []
        for key in CATALOGUES:
            prov = latest_provenance(ctx.conn, key, "earthquake")
            updated = prov["source_time"] or prov["ingested_at"]
            if updated is not None and (ctx.now - updated).total_seconds() <= STALE_SECONDS:
                live.append(key)
        return live

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        actions = COASTAL_ACTIONS if self.coastal(ctx) else []
        live = self.live_catalogues(ctx)
        quakes = [g for g in merge_quakes(self.recent(ctx, t)) if max(e["magnitude"] for e in g) >= t["min_magnitude"]]
        evidence = []
        for group in quakes:
            strongest = max(group, key=lambda e: e["magnitude"])
            evidence.append(
                Evidence(
                    f"M{strongest['magnitude']:.1f} {strongest['place'] or ''}".strip(),
                    f"a {strongest['distance_km']:.0f} km de la comuna, profundidad {strongest['depth_km']:.0f} km. Registrado por {len(group)} de {len(CATALOGUES)} catálogos: {'; '.join(reading(e) for e in group)}",
                    "observed",
                    " y ".join(CATALOGUES[e["source_key"]] for e in group),
                    strongest["occurred_at"],
                    strongest["provenance_id"],
                )
            )
        if quakes:
            top = max(max(e["magnitude"] for e in g) for g in quakes)
            headline = f"{len(quakes)} sismo(s) de magnitud {t['min_magnitude']:g} o más en las últimas {t['hours']} horas a menos de {t['radius_km']:.0f} km; el mayor fue M{top:.1f}."
        else:
            headline = f"Sin sismos de magnitud {t['min_magnitude']:g} o más en las últimas {t['hours']} horas a menos de {t['radius_km']:.0f} km."
        explanation = [
            "Información de sismos ya ocurridos. Los sismos no se pueden pronosticar y esta plataforma no lo intenta.",
            "Cruzamos dos catálogos: USGS (Estados Unidos) y EMSC (Europa), que incluye las soluciones del Centro Sismológico Nacional de Chile. Un sismo registrado por ambos cuenta una sola vez.",
            f"{len(live)} de {len(CATALOGUES)} catálogos respondieron en las últimas 3 horas.",
        ]
        missing = [f"Actualización reciente del catálogo {CATALOGUES[k]}" for k in CATALOGUES if k not in live]
        if not live:
            return Assessment(
                hazard=self.key,
                hazard_name=self.name,
                level="SIN_DATOS",
                headline="Ningún catálogo de sismos se ha actualizado en las últimas 3 horas.",
                explanation=explanation,
                evidence=evidence,
                missing=missing,
                actions=actions,
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
            missing=missing,
            actions=actions,
            thresholds=t,
            area_name=area.name,
        )
