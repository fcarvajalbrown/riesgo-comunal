from app.alerts import ALERT_ORIGIN, FALLBACK_SOURCES, active_alerts
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import INTERNATIONAL_NOTE, classify_international_alerts

EQUIVALENCE_NOTE = (
    "Equivalencia de la plataforma: GDACS verde = Informativo, naranja = Alto, roja = Crítico; "
    "PTWC información = Informativo, vigilancia o aviso = Moderado, amenaza o alerta = Alto. "
    "Estas fuentes miden el impacto o la amenaza a escala mundial y no conocen la situación local."
)


class InternationalAlertModule(HazardModule):
    key = "international_alert"
    name = "Alertas internacionales de respaldo"
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
                f"{a['level']}: {a['title']}",
                ALERT_ORIGIN[a["source_key"]],
                "official_warning",
                INTERNATIONAL_NOTE,
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
            headline=result.reason,
            explanation=[result.reason, EQUIVALENCE_NOTE],
            evidence=evidence,
            missing=[],
            thresholds={},
            area_name=area.name,
        )
