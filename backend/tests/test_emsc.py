import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.hazards.earthquake import merge_quakes
from app.sources.base import RawPayload
from app.sources.emsc import EmscAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def test_emsc_payload_is_normalized_from_real_response():
    body = json.loads((FIXTURES / "emsc_chile.json").read_text(encoding="utf-8"))
    batch = EmscAdapter().normalize(RawPayload(dataset="earthquake", url="https://example", body=body), body)
    assert len(batch.records) == len(body["features"])
    record = batch.records[0]
    first = body["features"][0]["properties"]
    assert record.external_id == first["unid"]
    assert record.magnitude == first["mag"]
    assert record.depth_km == first["depth"] and record.depth_km > 0
    assert record.properties["author"] == first["auth"]
    assert record.properties["url"].endswith(first["unid"])
    assert record.occurred_at.tzinfo is not None


def quake(source: str, seconds: int, lat: float, lon: float, magnitude: float) -> dict:
    return {
        "source_key": source,
        "occurred_at": datetime(2026, 10, 10, 3, 0, tzinfo=UTC) + timedelta(seconds=seconds),
        "lat": lat,
        "lon": lon,
        "magnitude": magnitude,
    }


def test_same_quake_in_both_catalogues_counts_once():
    groups = merge_quakes([quake("usgs", 0, -35.5, -72.5, 4.8), quake("emsc", 20, -35.6, -72.4, 4.6)])
    assert len(groups) == 1
    assert {e["source_key"] for e in groups[0]} == {"usgs", "emsc"}


def test_distinct_quakes_stay_separate():
    far_in_time = merge_quakes([quake("usgs", 0, -35.5, -72.5, 4.8), quake("emsc", 600, -35.5, -72.5, 4.6)])
    far_in_space = merge_quakes([quake("usgs", 0, -35.5, -72.5, 4.8), quake("emsc", 10, -30.0, -71.5, 4.6)])
    same_catalogue = merge_quakes([quake("usgs", 0, -35.5, -72.5, 4.8), quake("usgs", 10, -35.5, -72.5, 4.6)])
    assert len(far_in_time) == len(far_in_space) == len(same_catalogue) == 2
