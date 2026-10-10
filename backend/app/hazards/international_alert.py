from app.alerts import FALLBACK_SOURCES, active_alerts
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import classify_international_alerts

EQUIVALENCE_NOTE = (
    "Equivalencia de la plataforma: GDACS verde = Informativo, naranja = Alto, roja = Crítico; "
    "PTWC información = Informativo, vigilancia o aviso = Moderado, amenaza o alerta = Alto. "
    "Estas fuentes miden el impacto o la amenaza a escala mundial y no conocen la situación local."
)


def plain_headline(titles: list[str]) -> str:
    if not titles:
        return "No hay avisos de sistemas internacionales para la zona."
    topics = "; ".join(dict.fromkeys(t.removeprefix("Aviso internacional: ").removeprefix("Aviso internacional de ") for t in titles))
    return f"{len(titles)} aviso(s) de sistemas internacionales para la zona: {topics}. No reemplazan los avisos oficiales."


class InternationalAlertModule(HazardModule):
    key = "international_alert"
    name = "Avisos internacionales"
    description = "Alertas de GDACS y mensajes de tsunami de NOAA (PTWC/NTWC) que alcanzan la comuna. Respaldo cuando falla la lectura de SENAPRED; no reemplazan los avisos oficiales."
    modes = ("ahora",)
    spatial = False
    default_thresholds: dict = {}
    layers = ()

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        alerts = [
            a
            for a in active_alerts(ctx.conn, ctx.municipality_id, ctx.now)
            if a["source_key"] in FALLBACK_SOURCES and a["starts_at"] <= ctx.now
        ]
        result = classify_international_alerts([a["level"] for a in alerts])
        evidence = [
            Evidence(
                a["title"],
                a["description"],
                "international",
                a["issuer"],
                a["starts_at"],
                a["provenance_id"],
                a["source_url"],
            )
            for a in alerts
        ]
        return Assessment(
            hazard=self.key,
            hazard_name=self.name,
            level=result.level,
            headline=plain_headline([a["title"] for a in alerts]),
            explanation=[result.reason, EQUIVALENCE_NOTE],
            evidence=evidence,
            missing=[],
            thresholds={},
            area_name=area.name,
        )
