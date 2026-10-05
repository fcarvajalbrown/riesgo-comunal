from app.alerts import active_alerts
from app.hazards.base import Area, Assessment, Evidence, HazardContext, HazardModule
from app.hazards.rules import classify_senapred_alerts

EQUIVALENCE_NOTE = (
    "El nivel de la plataforma sigue a la alerta oficial: Temprana Preventiva = Moderado, Amarilla = Alto, Roja = Crítico. "
    "La alerta, su cobertura y sus instrucciones son las de SENAPRED; confírmelas en senapred.cl."
)
ORIGIN = {
    "senapred_alertas": "leída automáticamente de la página pública senapred.cl/alertas",
    None: "ingresada por el municipio con su enlace oficial",
}


class SenapredAlertModule(HazardModule):
    key = "senapred_alert"
    name = "Alertas de SENAPRED"
    description = "Alertas Temprana Preventiva, Amarilla y Roja de SENAPRED vigentes cuya cobertura incluye la comuna."
    modes = ("ahora",)
    spatial = False
    default_thresholds: dict = {}
    layers = ()

    def assess(self, ctx: HazardContext, area: Area) -> Assessment:
        alerts = [
            a
            for a in active_alerts(ctx.conn, ctx.municipality_id, ctx.now)
            if a["source_key"] == "senapred_alertas" or (a["source_key"] is None and "senapred" in (a["issuer"] or "").lower())
        ]
        alerts = [a for a in alerts if a["starts_at"] <= ctx.now]
        result = classify_senapred_alerts([a["level"] for a in alerts])
        evidence = [
            Evidence(
                f"{a['level']}: {a['title']}",
                ORIGIN.get(a["source_key"], ORIGIN[None]),
                "official_warning",
                "Fuente: SENAPRED",
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
            explanation=[result.reason, EQUIVALENCE_NOTE, "Que no haya una alerta registrada no significa que no haya peligro."],
            evidence=evidence,
            missing=[],
            thresholds={},
            area_name=area.name,
        )
