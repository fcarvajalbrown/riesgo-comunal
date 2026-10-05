import pytest

from app.hazards.air_quality import AirQualityModule
from app.hazards.base import Assessment, Evidence, max_level
from app.hazards.flood import FloodModule
from app.hazards.meteo import MeteoModule
from app.hazards.rules import classify_air_quality, classify_flood, classify_rain, classify_tsunami, classify_wildfire
from app.hazards.tsunami import TsunamiModule
from app.hazards.wildfire import WildfireModule

WILDFIRE = WildfireModule.default_thresholds
AIR = AirQualityModule.default_thresholds
FLOOD = FloodModule.default_thresholds
TSUNAMI = TsunamiModule.default_thresholds
RAIN = MeteoModule.default_thresholds


@pytest.mark.parametrize(
    ("area", "ge3", "ge4", "covered", "expected"),
    [
        (100, 0, 0, 0, "SIN_DATOS"),
        (0, 0, 0, 0, "SIN_DATOS"),
        (100, 5, 0, 20, "BAJO"),
        (100, 10, 0, 20, "MODERADO"),
        (100, 10, 9.99, 20, "MODERADO"),
        (100, 12, 10, 20, "ALTO"),
        (100, 40, 29.9, 40, "ALTO"),
        (100, 40, 30, 40, "CRITICO"),
    ],
)
def test_wildfire_boundaries(area, ge3, ge4, covered, expected):
    assert classify_wildfire(area, ge3, ge4, covered, WILDFIRE).level == expected


def test_wildfire_custom_threshold_changes_level():
    custom = {**WILDFIRE, "high_share_alto": 0.20}
    assert classify_wildfire(100, 15, 15, 20, WILDFIRE).level == "ALTO"
    assert classify_wildfire(100, 15, 15, 20, custom).level == "MODERADO"


def test_wildfire_reason_states_share_and_threshold():
    reason = classify_wildfire(100, 15, 15, 20, WILDFIRE).reason
    assert "15%" in reason and "10%" in reason


@pytest.mark.parametrize(
    ("km2", "has_layer", "expected"),
    [(0, False, "SIN_DATOS"), (1.5, False, "SIN_DATOS"), (0, True, "BAJO"), (0.01, True, "ALTO")],
)
def test_tsunami(km2, has_layer, expected):
    assert classify_tsunami(km2, has_layer, TSUNAMI).level == expected


def test_tsunami_level_is_configurable():
    assert classify_tsunami(2, True, {"level_if_in_evacuation_area": "CRITICO"}).level == "CRITICO"


@pytest.mark.parametrize(
    ("mean", "hours", "expected"),
    [
        (None, 0, "SIN_DATOS"),
        (200, 17, "SIN_DATOS"),
        (79.9, 24, "BAJO"),
        (80, 24, "MODERADO"),
        (109.9, 18, "MODERADO"),
        (110, 24, "ALTO"),
        (169.9, 24, "ALTO"),
        (170, 24, "CRITICO"),
    ],
)
def test_air_quality_ds12_ranges(mean, hours, expected):
    assert classify_air_quality(mean, hours, AIR).level == expected


def test_air_quality_reason_cites_norm():
    assert "D.S. 12/2011" in classify_air_quality(120, 24, AIR).reason


@pytest.mark.parametrize(
    ("count", "has_data", "expected"),
    [(0, False, "SIN_DATOS"), (9, False, "SIN_DATOS"), (0, True, "BAJO"), (1, True, "BAJO"), (2, True, "MODERADO"), (4, True, "MODERADO"), (5, True, "ALTO")],
)
def test_flood(count, has_data, expected):
    assert classify_flood(count, has_data, FLOOD).level == expected


@pytest.mark.parametrize(("mm", "expected"), [(None, "SIN_DATOS"), (0, "BAJO"), (29.9, "BAJO"), (30, "MODERADO"), (60, "ALTO")])
def test_rain(mm, expected):
    assert classify_rain(mm, RAIN).level == expected


def test_rain_reason_marks_thresholds_provisional():
    assert "provisional" in classify_rain(45, RAIN).reason


def test_max_level_ignores_missing_and_informative():
    assert max_level(["SIN_DATOS", "INFORMATIVO", "BAJO"]) == "BAJO"
    assert max_level(["SIN_DATOS", "INFORMATIVO"]) == "INFORMATIVO"
    assert max_level(["SIN_DATOS"]) == "SIN_DATOS"
    assert max_level(["MODERADO", "CRITICO", "ALTO"]) == "CRITICO"
    assert max_level([]) == "SIN_DATOS"


def test_assessment_is_always_labelled_derived_with_notice():
    data = Assessment(
        hazard="x",
        hazard_name="X",
        level="ALTO",
        headline="h",
        explanation=["e"],
        evidence=[Evidence("a", 1, "official", "Fuente: SENAPRED")],
    ).to_dict()
    assert data["data_class"] == "derived"
    assert data["data_class_label"] == "Cálculo de la plataforma"
    assert "No es una evaluación ni una alerta oficial" in data["notice"]
    assert "ausencia de un nivel alto no significa ausencia de peligro" in data["notice"]
    assert data["evidence"][0]["data_class_label"] == "Oficial"


def test_threshold_overrides_only_known_keys_and_coerce_types():
    module = WildfireModule()
    merged = module.thresholds({"high_share_alto": "0.25", "unknown": 1})
    assert merged["high_share_alto"] == 0.25
    assert "unknown" not in merged


def test_every_data_class_has_a_spanish_label():
    import importlib.util
    from pathlib import Path

    from app.hazards.base import DATA_CLASS_LABEL

    path = Path(__file__).parents[1] / "alembic" / "versions" / "0002_estimated_modelled_classes.py"
    spec = importlib.util.spec_from_file_location("m0002", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classes = {c.strip("'") for c in module.EXTENDED.split(",")}
    assert classes == set(DATA_CLASS_LABEL)


def test_dmc_warning_levels_follow_the_official_bulletin():
    from app.hazards.rules import classify_dmc_warnings

    assert classify_dmc_warnings([]).level == "BAJO"
    assert classify_dmc_warnings([("Aviso", True)]).level == "MODERADO"
    assert classify_dmc_warnings([("Aviso", True), ("Alerta", True)]).level == "ALTO"
    assert classify_dmc_warnings([("Alarma", True), ("Aviso", True)]).level == "CRITICO"


def test_upcoming_dmc_warning_is_informative_only():
    from app.hazards.rules import classify_dmc_warnings

    assert classify_dmc_warnings([("Alarma", False)]).level == "INFORMATIVO"
    assert classify_dmc_warnings([("Alarma", False), ("Aviso", True)]).level == "MODERADO"
