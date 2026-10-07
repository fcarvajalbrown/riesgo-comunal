import json
from datetime import UTC, datetime
from pathlib import Path

from app.hazards.rules import classify_forecast
from app.sources.base import IngestScope
from app.sources.open_meteo import forecast_points, forecast_records, summarize

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "open_meteo_forecast.json").read_text(encoding="utf-8"))
THRESHOLDS = {"rain_24h_moderado": 30.0, "rain_24h_alto": 60.0}


def test_points_are_bbox_centres():
    assert forecast_points(IngestScope(((-72.0, -36.0, -71.0, -35.0),))) == [(-35.5, -71.5)]


def test_summary_takes_maxima_inside_the_window():
    hourly = {
        "time": [f"2026-10-07T{h:02d}:00" for h in range(24)] + [f"2026-10-08T{h:02d}:00" for h in range(24)],
        "precipitation": [1.0] * 48,
        "wind_gusts_10m": [10.0] * 47 + [80.0],
        "temperature_2m": [20.0] * 48,
    }
    summary = summarize(hourly, datetime(2026, 10, 7, 0, 30, tzinfo=UTC))
    assert summary == {"om_rain_24h_max": 24.0, "om_gust_max": 80.0, "om_temp_max": 20.0}
    later = summarize(hourly, datetime(2026, 10, 8, 12, tzinfo=UTC))
    assert later["om_rain_24h_max"] == 12.0


def test_records_from_real_response():
    issued = datetime.fromisoformat(FIXTURE[0]["hourly"]["time"][0]).replace(tzinfo=UTC)
    records = forecast_records(FIXTURE, [(-35.43, -71.67), (-35.33, -72.41)], issued)
    assert {"om_rain_24h_max", "om_gust_max", "om_temp_max", "om_d0_tmax"} <= {r.parameter for r in records}
    assert {r.station_external_id for r in records} == {"-35.430,-71.670", "-35.330,-72.410"}
    assert all(r.validation_status == "forecast" and r.value is not None for r in records)


def test_forecast_rule_levels():
    assert classify_forecast(None, None, None, THRESHOLDS).level == "SIN_DATOS"
    assert classify_forecast(5.0, 40.0, 25.0, THRESHOLDS).level == "BAJO"
    assert classify_forecast(35.0, 40.0, 25.0, THRESHOLDS).level == "MODERADO"
    assert classify_forecast(70.0, 40.0, 25.0, THRESHOLDS).level == "ALTO"
    assert classify_forecast(None, 90.0, 36.0, THRESHOLDS).level == "INFORMATIVO"
    assert "ráfagas de hasta 90 km/h" in classify_forecast(None, 90.0, 36.0, THRESHOLDS).reason


def test_plain_outlook_says_when_it_rains():
    from datetime import date

    from app.hazards.rules import plain_outlook

    values = {"om_d0_rain_tarde": 3.2, "om_d0_rain_noche": 0.4, "om_d0_tmax": 18.4, "om_d1_rain_manana": 0.0, "om_d1_tmax": 22.0, "om_d2_rain_madrugada": 1.0, "om_d2_rain_noche": 6.0, "om_d2_tmax": 15.0}
    lines = plain_outlook(values, date(2026, 10, 7))
    assert lines == [
        "Hoy: lluvia durante la tarde, máxima de 18 grados.",
        "Mañana: sin lluvia, máxima de 22 grados.",
        "El viernes: lluvia durante la madrugada y la noche, máxima de 15 grados.",
    ]


def test_daily_outlook_splits_local_periods():
    from app.sources.open_meteo import daily_outlook

    hourly = {"time": ["2026-10-07T18:00", "2026-10-07T19:00", "2026-10-07T23:00"], "precipitation": [2.0, 1.5, 4.0], "temperature_2m": [15.0, 16.0, 12.0]}
    out = daily_outlook(hourly, datetime(2026, 10, 7, 18, tzinfo=UTC))
    assert out["om_d0_rain_tarde"] == 3.5
    assert out["om_d0_rain_noche"] == 4.0
    assert out["om_d0_tmax"] == 16.0
