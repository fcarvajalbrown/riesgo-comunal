from datetime import UTC, datetime
from pathlib import Path

from app.sources.ndbc_dart import parse_dart, summarize

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 10, 5, 0, tzinfo=UTC)


def values(records) -> dict[str, float]:
    return {r.parameter: r.value for r in records}


def test_real_valparaiso_buoy_is_read_in_normal_mode():
    readings = parse_dart((FIXTURES / "dart_32404.txt").read_text(encoding="utf-8"))
    assert readings and readings[-1]["at"] == datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
    result = values(summarize("32404", readings, NOW))
    assert result["dart_event_mode"] == 0.0
    assert 4000 < result["dart_height"] < 4300


def test_one_minute_readings_mean_event_mode():
    readings = parse_dart("2026 10 10 03 00 00 2 4141.400\n2026 10 10 02 45 00 1 4141.300\n")
    assert values(summarize("32404", readings, NOW))["dart_event_mode"] == 1.0


def test_old_event_is_ignored():
    readings = parse_dart("2026 10 09 12 00 00 3 4141.400\n2026 10 10 04 45 00 1 4141.300\n")
    assert values(summarize("32404", readings, NOW))["dart_event_mode"] == 0.0
