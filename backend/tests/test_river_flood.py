from datetime import UTC, datetime

from app.hazards.river_flood import flood_level, trend_sentence
from app.sources.glofas_flood import river_points, summarize

NOW = datetime(2026, 10, 10, 5, 0, tzinfo=UTC)
POINT = {"name": "Prueba", "lat": -35.3, "lon": -72.4, "thresholds": {"levels": {"2": 100.0, "5": 200.0, "20": 300.0}}}


def daily(peaks: list[float]) -> dict[str, list]:
    series = {"river_discharge": [50.0, peaks[0]]}
    for i, peak in enumerate(peaks[1:], start=1):
        series[f"river_discharge_member{i:02d}"] = [50.0, peak, None]
    return series


def counts(records) -> dict[str, float]:
    return {r.parameter: r.value for r in records}


def test_every_maule_comuna_has_a_river_with_ordered_thresholds():
    points = river_points()
    assert len(points) == 30
    for point in points.values():
        levels = point["thresholds"]["levels"]
        assert 0 < levels["2"] < levels["5"] < levels["20"]


def test_members_are_counted_against_each_return_level():
    values = counts(summarize("07102", POINT, daily([90.0, 150.0, 250.0, 350.0]), NOW))
    assert values["glofas_members"] == 4
    assert (values["glofas_over_2y"], values["glofas_over_5y"], values["glofas_over_20y"]) == (3, 2, 1)
    assert values["glofas_discharge_today"] == 50.0


def test_level_needs_half_of_the_members():
    assert flood_level({"glofas_members": 51, "glofas_over_2y": 25, "glofas_over_5y": 0}, 0.5) == "BAJO"
    assert flood_level({"glofas_members": 51, "glofas_over_2y": 26, "glofas_over_5y": 10}, 0.5) == "MODERADO"
    assert flood_level({"glofas_members": 51, "glofas_over_2y": 40, "glofas_over_5y": 26}, 0.5) == "ALTO"
    assert flood_level({}, 0.5) == "SIN_DATOS"


def test_trend_is_explained_only_when_significant():
    flat = {"nonstationary": False, "years": "1997-2025"}
    falling = {"nonstationary": True, "years": "1997-2025", "trend_m3s_per_year": -17.6, "mann_kendall_p": 0.007, "present_year": 2026}
    assert "no muestran una tendencia" in trend_sentence(flat)
    assert "han bajado unos 18" in trend_sentence(falling)
