from dataclasses import dataclass


@dataclass(frozen=True)
class RuleResult:
    level: str
    reason: str


def classify_wildfire(area_km2: float, km2_class_ge3: float, km2_class_ge4: float, covered_km2: float, t: dict) -> RuleResult:
    if covered_km2 <= 0 or area_km2 <= 0:
        return RuleResult("SIN_DATOS", "El mapa de amenaza de SENAPRED no tiene polígonos de recurrencia en esta área.")
    share_high = km2_class_ge4 / area_km2
    share_mid = km2_class_ge3 / area_km2
    pct_high = f"{share_high:.0%}"
    if share_high >= t["high_share_critico"]:
        return RuleResult("CRITICO", f"{pct_high} del área está en recurrencia Alta o Muy alta (umbral {t['high_share_critico']:.0%}).")
    if share_high >= t["high_share_alto"]:
        return RuleResult("ALTO", f"{pct_high} del área está en recurrencia Alta o Muy alta (umbral {t['high_share_alto']:.0%}).")
    if share_mid >= t["mid_share_moderado"]:
        return RuleResult("MODERADO", f"{share_mid:.0%} del área está en recurrencia Media o superior (umbral {t['mid_share_moderado']:.0%}).")
    return RuleResult("BAJO", "El área tiene registro de incendios, pero sólo en clases de recurrencia bajas o con poca superficie.")


def classify_tsunami(evacuation_km2: float, comuna_has_layer: bool, t: dict) -> RuleResult:
    if not comuna_has_layer:
        return RuleResult("SIN_DATOS", "No hay áreas de evacuación por tsunami publicadas por SENAPRED para esta comuna.")
    if evacuation_km2 > 0:
        return RuleResult(
            t["level_if_in_evacuation_area"],
            f"{evacuation_km2:.2f} km² del área están dentro de un área a evacuar por tsunami.",
        )
    return RuleResult("BAJO", "El área no intersecta las áreas a evacuar por tsunami publicadas para la comuna.")


def classify_air_quality(mean_24h: float | None, valid_hours: int, t: dict) -> RuleResult:
    if mean_24h is None or valid_hours < t["min_hours"]:
        return RuleResult(
            "SIN_DATOS",
            f"Hay {valid_hours} horas con datos de MP2,5 en las últimas 24 horas; se requieren al menos {t['min_hours']}.",
        )
    value = f"{mean_24h:.0f} µg/m³"
    if mean_24h >= t["emergencia"]:
        return RuleResult("CRITICO", f"Promedio 24 h de MP2,5 {value}, en el rango de emergencia del D.S. 12/2011 (≥ {t['emergencia']:.0f}).")
    if mean_24h >= t["preemergencia"]:
        return RuleResult("ALTO", f"Promedio 24 h de MP2,5 {value}, en el rango de preemergencia del D.S. 12/2011 (≥ {t['preemergencia']:.0f}).")
    if mean_24h >= t["alerta"]:
        return RuleResult("MODERADO", f"Promedio 24 h de MP2,5 {value}, en el rango de alerta del D.S. 12/2011 (≥ {t['alerta']:.0f}).")
    return RuleResult("BAJO", f"Promedio 24 h de MP2,5 {value}, bajo el umbral de alerta ({t['alerta']:.0f}).")


def classify_flood(incident_count: int, has_municipal_flood_data: bool, t: dict) -> RuleResult:
    if not has_municipal_flood_data:
        return RuleResult("SIN_DATOS", "No hay registros municipales de inundación o anegamiento cargados.")
    period = f"en los últimos {t['years']} años"
    if incident_count >= t["incidents_alto"]:
        return RuleResult("ALTO", f"{incident_count} incidentes de inundación registrados {period} (umbral {t['incidents_alto']}).")
    if incident_count >= t["incidents_moderado"]:
        return RuleResult("MODERADO", f"{incident_count} incidentes de inundación registrados {period} (umbral {t['incidents_moderado']}).")
    if incident_count >= 1:
        return RuleResult("BAJO", f"{incident_count} incidente de inundación registrado {period}.")
    return RuleResult("BAJO", f"Sin incidentes de inundación registrados {period} en esta área.")


def classify_rain(rain_24h_mm: float | None, t: dict) -> RuleResult:
    if rain_24h_mm is None:
        return RuleResult("SIN_DATOS", "No hay observaciones de precipitación disponibles para la comuna.")
    if rain_24h_mm >= t["rain_24h_alto"]:
        return RuleResult("ALTO", f"{rain_24h_mm:.1f} mm en 24 h (umbral provisional {t['rain_24h_alto']:.0f} mm).")
    if rain_24h_mm >= t["rain_24h_moderado"]:
        return RuleResult("MODERADO", f"{rain_24h_mm:.1f} mm en 24 h (umbral provisional {t['rain_24h_moderado']:.0f} mm).")
    return RuleResult("BAJO", f"{rain_24h_mm:.1f} mm en 24 h, bajo el umbral provisional de {t['rain_24h_moderado']:.0f} mm.")


DMC_WARNING_LEVEL = {"Aviso": "MODERADO", "Alerta": "ALTO", "Alarma": "CRITICO"}


def classify_dmc_warnings(warnings: list[tuple[str, bool]]) -> RuleResult:
    in_force = [level for level, started in warnings if started and level in DMC_WARNING_LEVEL]
    upcoming = [level for level, started in warnings if not started and level in DMC_WARNING_LEVEL]
    if in_force:
        rank = ("Aviso", "Alerta", "Alarma")
        top = max(in_force, key=rank.index)
        return RuleResult(DMC_WARNING_LEVEL[top], f"{top} de la Dirección Meteorológica de Chile vigente para la comuna.")
    if upcoming:
        return RuleResult("INFORMATIVO", f"{len(upcoming)} boletín(es) de la Dirección Meteorológica de Chile con inicio próximo para la comuna.")
    return RuleResult("BAJO", "No hay avisos, alertas ni alarmas meteorológicas de la Dirección Meteorológica de Chile vigentes para la comuna.")


SENAPRED_ALERT_LEVEL = {"Alerta Temprana Preventiva": "MODERADO", "Alerta Amarilla": "ALTO", "Alerta Roja": "CRITICO"}


def classify_senapred_alerts(levels: list[str]) -> RuleResult:
    known = [level for level in levels if level in SENAPRED_ALERT_LEVEL]
    if not known:
        if levels:
            return RuleResult("INFORMATIVO", "Hay alertas de SENAPRED para la comuna con un nivel no reconocido; revise el detalle oficial.")
        return RuleResult("BAJO", "No hay alertas de SENAPRED vigentes para la comuna registradas en la plataforma.")
    order = list(SENAPRED_ALERT_LEVEL)
    top = max(known, key=order.index)
    return RuleResult(SENAPRED_ALERT_LEVEL[top], f"{top} de SENAPRED vigente para la comuna.")


INTERNATIONAL_ALERT_LEVEL = {
    "GDACS verde": "INFORMATIVO",
    "GDACS naranja": "ALTO",
    "GDACS roja": "CRITICO",
    "PTWC información": "INFORMATIVO",
    "PTWC vigilancia de tsunami": "MODERADO",
    "PTWC aviso de tsunami": "MODERADO",
    "PTWC amenaza de tsunami": "ALTO",
    "PTWC alerta de tsunami": "ALTO",
}
INTERNATIONAL_NOTE = "Fuente internacional, no reemplaza el aviso oficial de SENAPRED ni del SHOA."


def classify_international_alerts(levels: list[str]) -> RuleResult:
    if not levels:
        return RuleResult("BAJO", "No hay alertas de las fuentes internacionales de respaldo (GDACS, PTWC) que alcancen la comuna.")
    ranked = [INTERNATIONAL_ALERT_LEVEL.get(level, "INFORMATIVO") for level in levels]
    order = ("INFORMATIVO", "MODERADO", "ALTO", "CRITICO")
    top = max(ranked, key=order.index)
    names = ", ".join(sorted({level for level, rank in zip(levels, ranked) if rank == top}))
    return RuleResult(top, f"{names} vigente para la comuna. {INTERNATIONAL_NOTE}")


def senapred_feed_problem(last_success_at, last_error: str | None, interval_minutes: int, now, enabled: bool = True) -> str | None:
    if not enabled:
        return "La lectura automática de alertas de SENAPRED está desactivada."
    lines = (last_error or "").strip().splitlines()
    last_error = lines[0][:160].rstrip(".:") if lines else None
    if last_success_at is None:
        return "La lectura automática de alertas de SENAPRED no ha funcionado todavía" + (f" (último error: {last_error})." if last_error else ".")
    age_minutes = (now - last_success_at).total_seconds() / 60
    if last_error:
        return f"La última lectura de alertas de SENAPRED falló (error: {last_error}); la última lectura correcta fue hace {age_minutes:.0f} min."
    if age_minutes > 3 * interval_minutes:
        return f"Las alertas de SENAPRED no se actualizan hace {age_minutes:.0f} min (se esperan cada {interval_minutes} min)."
    return None
