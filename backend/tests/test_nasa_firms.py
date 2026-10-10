from pathlib import Path

from app.sources.base import RawPayload
from app.sources.nasa_firms import NasaFirmsAdapter, parse_firms

FIXTURES = Path(__file__).parent / "fixtures"


def test_viirs_and_modis_rows_are_parsed_from_real_files():
    viirs = parse_firms((FIXTURES / "firms_viirs_n20_24h.csv").read_text(encoding="utf-8"))
    modis = parse_firms((FIXTURES / "firms_modis_24h.csv").read_text(encoding="utf-8"))
    assert viirs and modis
    assert viirs[0]["satellite"] == "NOAA-20" and modis[0]["satellite"] == "Terra"
    assert viirs[0]["seen"].hour == 5 and viirs[0]["seen"].minute == 48
    assert all(d["frp"] is not None for d in viirs + modis)


def test_rows_outside_chile_are_dropped():
    text = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n-5.0,-55.0,300,0.4,0.4,2026-10-08,0406,N20,nominal,2.0NRT,290,3.0,N\n"
    assert parse_firms(text) == []


def test_detections_become_fire_events_with_stable_ids():
    text = (FIXTURES / "firms_viirs_n20_24h.csv").read_text(encoding="utf-8")
    adapter = NasaFirmsAdapter()
    raw = RawPayload(dataset="fire_detection", url="https://example", body=text, options={"instrument": "viirs_noaa20"})
    batch = adapter.normalize(raw, adapter.parse(raw))
    ids = [r.external_id for r in batch.records]
    assert len(ids) == len(set(ids)) and ids[0].startswith("viirs_noaa20-")
