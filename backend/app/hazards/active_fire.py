from datetime import timedelta

from app.db import rows
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.common import latest_provenance
from app.hazards.earthquake import distance_km

DETECTORS = {"inpe_queimadas": "INPE (Brasil)", "nasa_firms": "NASA FIRMS (EE.UU.)"}
SAME_SPOT_KM = 1.0
STALE_SECONDS = 6 * 3600


def group_spots(detections: list[dict]) -> list[list[dict]]:
    spots: list[list[dict]] = []
    for detection in sorted(detections, key=lambda d: d["occurred_at"]):
        match = next((s for s in spots if any(distance_km(detection, d) <= SAME_SPOT_KM for d in s)), None)
        if match is None:
            spots.append([detection])
        else:
            match.append(detection)
    return spots


def passes(spot: list[dict]) -> set[tuple[str, object]]:
    return {(d["satellite"], d["occurred_at"]) for d in spot}


def confirmed(spot: list[dict]) -> bool:
    return len({d["source_key"] for d in spot}) >= 2 or len(passes(spot)) >= 2


def level_for(spots: list[list[dict]]) -> str:
    if not spots:
        return "BAJO"
    return "ALTO" if any(confirmed(s) for s in spots) else "MODERADO"


class ActiveFireModule(HazardModule):
    key = "active_fire"
    name = "Focos de incendio detectados"
    description = "Focos de calor detectados por satélite dentro de la comuna en las últimas 24 horas, cruzando INPE (Brasil) y NASA FIRMS (EE.UU.)."
    modes = ("ahora",)
    spatial = False
    default_thresholds = {"hours": 24}
    layers = ()

    def detections(self, ctx: HazardContext, hours: int) -> list[dict]:
        return rows(
            ctx.conn,
            """
            select e.source_key, e.occurred_at, e.magnitude as frp, e.provenance_id,
                   coalesce(e.properties->>'satellite', '') as satellite, st_x(e.geom) as lon, st_y(e.geom) as lat
            from historical_event e, municipality m
            where m.id = :mid and e.hazard = 'fire_detection' and e.source_key = any(:sources)
              and e.occurred_at >= :since and st_intersects(e.geom, m.boundary)
            order by e.occurred_at
            """,
            mid=ctx.municipality_id,
            sources=list(DETECTORS),
            since=ctx.now - timedelta(hours=hours),
        )

    def live_detectors(self, ctx: HazardContext) -> list[str]:
        live = []
        for key in DETECTORS:
            prov = latest_provenance(ctx.conn, key, "fire_detection")
            updated = prov["source_time"] or prov["ingested_at"]
            if updated is not None and (ctx.now - updated).total_seconds() <= STALE_SECONDS:
                live.append(key)
        return live

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        t = self.thresholds(ctx.thresholds)
        live = self.live_detectors(ctx)
        spots = group_spots(self.detections(ctx, t["hours"]))
        evidence = []
        for spot in spots:
            first, last = spot[0], spot[-1]
            frp = max((d["frp"] for d in spot if d["frp"] is not None), default=None)
            sources = sorted({DETECTORS[d["source_key"]] for d in spot})
            satellites = sorted({d["satellite"] for d in spot if d["satellite"]})
            power = f"; potencia radiativa máxima {frp:.1f} MW" if frp is not None else ""
            state = "confirmado por más de una pasada o fuente" if confirmed(spot) else "una sola detección, sin confirmar"
            evidence.append(
                Evidence(
                    f"Foco de calor en {first['lat']:.3f}, {first['lon']:.3f}",
                    f"{len(spot)} detección(es) en {len(passes(spot))} pasada(s) de satélite ({', '.join(satellites)}){power}; {state}",
                    "observed",
                    " y ".join(sources),
                    last["occurred_at"],
                    last["provenance_id"],
                    f"https://www.openstreetmap.org/?mlat={first['lat']:.5f}&mlon={first['lon']:.5f}#map=13/{first['lat']:.5f}/{first['lon']:.5f}",
                )
            )
        level = level_for(spots)
        if not spots:
            headline = f"No hay focos de calor detectados por satélite en la comuna en las últimas {t['hours']} horas."
        elif level == "ALTO":
            headline = f"{len(spots)} foco(s) de calor en la comuna en las últimas {t['hours']} horas, al menos uno confirmado por varias pasadas o fuentes. No está confirmado en terreno."
        else:
            headline = f"{len(spots)} posible(s) foco(s) de calor en la comuna en las últimas {t['hours']} horas, sin confirmar."
        explanation = [
            "Los satélites detectan calor, no incendios: un foco puede ser un incendio forestal, una quema agrícola o una fuente industrial.",
            "Cruzamos dos sistemas independientes: INPE (Brasil) y NASA FIRMS (Estados Unidos). Un foco visto por ambos, o por dos pasadas de satélite en el mismo lugar, sube a Alto; nunca llega a Crítico sin una alerta oficial.",
            f"{len(live)} de {len(DETECTORS)} sistemas respondieron en las últimas 6 horas.",
        ]
        actions = [
            "Si ve humo o fuego, llame a Bomberos al 132 y siga las indicaciones de CONAF y SENAPRED.",
        ]
        missing = [f"Actualización reciente de {DETECTORS[k]}" for k in DETECTORS if k not in live]
        both = sum(1 for spot in spots if len({d["source_key"] for d in spot}) >= 2)
        consensus = f"{len(live)} de {len(DETECTORS)} sistemas satelitales responden" + (f"; {both} de {len(spots)} focos vistos por ambos" if spots else "")
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=level if live or spots else "SIN_DATOS",
            headline=headline if live or spots else "Ningún sistema de detección satelital se ha actualizado en las últimas 6 horas.",
            explanation=explanation,
            evidence=evidence,
            actions=actions,
            missing=missing,
            thresholds=t,
            consensus=consensus,
            area_name=area.name,
        )
