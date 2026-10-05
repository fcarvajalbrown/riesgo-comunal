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
