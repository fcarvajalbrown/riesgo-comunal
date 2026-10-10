import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.hazards.sea_level import anomalous_gauges
from app.sources.ioc_sea_level import oscillation, summarize

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_constitucion_data_gives_level_and_calm_oscillation_per_sensor():
    data = json.loads((FIXTURES / "ioc_const.json").read_text(encoding="utf-8"))
    records = summarize("const", data, datetime(2026, 10, 10, 4, 0, tzinfo=UTC))
    sensors = {r.station_external_id for r in records}
    assert sensors == {"const-ra2", "const-rad"}
    swings = [r.value for r in records if r.parameter == "sea_level_oscillation"]
    assert len(swings) == 2 and all(0 < s < 0.5 for s in swings)


def test_a_wave_in_the_last_hour_is_measured():
    start = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
    series = [(start + timedelta(minutes=i), 4.0 + (0.8 if i == 90 else 0.0)) for i in range(120)]
    assert oscillation(series, start + timedelta(minutes=60)) > 0.7


def test_gauge_is_anomalous_only_when_every_sensor_agrees():
    both = [{"gauge": "const", "parameter": "sea_level_oscillation", "value": 0.6}, {"gauge": "const", "parameter": "sea_level_oscillation", "value": 0.55}]
    one = [{"gauge": "boye", "parameter": "sea_level_oscillation", "value": 0.9}, {"gauge": "boye", "parameter": "sea_level_oscillation", "value": 0.1}]
    single_sensor = [{"gauge": "boye", "parameter": "sea_level_oscillation", "value": 0.9}]
    assert anomalous_gauges(both + one + single_sensor, 0.5) == ["const"]
