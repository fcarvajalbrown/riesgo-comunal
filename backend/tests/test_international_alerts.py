from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.sources.international_alerts import (
    gdacs_record,
    gdacs_relevant,
    parse_gdacs,
    parse_ptwc,
    ptwc_record,
    ptwc_relevant,
)

FIXTURES = Path(__file__).parent / "fixtures"
MAULE = ((-72.8, -36.6, -70.3, -34.6),)


def gdacs_items():
    return {i["guid"]: i for i in parse_gdacs((FIXTURES / "gdacs_rss.xml").read_text(encoding="utf-8"))}


def test_gdacs_feed_is_parsed_from_real_payload():
    items = gdacs_items()
    assert set(items) == {"WF1032574", "EQ1569807", "FL1104207"}
    fire = items["WF1032574"]
    assert fire["iso3"] == "BOL" and fire["alert_level"] == "Green" and fire["is_current"]
    assert fire["bbox"] == [-67.1250473944409, -59.1250473944408, -17.0350039971287, -9.0350039971287]
    assert fire["from_date"] == datetime(2026, 10, 2, tzinfo=UTC)
    assert not items["FL1104207"]["is_current"]


def test_gdacs_keeps_only_events_affecting_chile_or_near_a_comuna():
    items = gdacs_items()
    assert not any(gdacs_relevant(i, MAULE) for i in items.values())
    chile = {**items["WF1032574"], "iso3": "CHL", "country": "Chile"}
    assert gdacs_relevant(chile, MAULE)
    shared = {**items["WF1032574"], "iso3": "ARG, CHL", "country": "Argentina, Chile"}
    assert gdacs_relevant(shared, MAULE)
    offshore = {**items["EQ1569807"], "iso3": "", "country": "", "lat": -35.5, "lon": -73.5}
    assert gdacs_relevant(offshore, MAULE)
    far_offshore = {**offshore, "lon": -80.0}
    assert not gdacs_relevant(far_offshore, MAULE)


def test_gdacs_record_is_labelled_international_and_mapped():
    item = {**gdacs_items()["WF1032574"], "alert_level": "Orange"}
    record = gdacs_record(item)
    assert record.level == "GDACS naranja"
    assert record.hazard == "wildfire"
    assert record.title.startswith("Fuente internacional (GDACS), no reemplaza el aviso oficial")
    assert record.ends_at is None
    assert record.area["coordinates"][0][0][0] == [-67.1250473944409, -17.0350039971287]
    ended = gdacs_record(gdacs_items()["FL1104207"])
    assert ended.ends_at is not None


def test_ptwc_atom_is_parsed_from_real_payload():
    entries = parse_ptwc((FIXTURES / "ptwc_paaq_atom.xml").read_text(encoding="utf-8"))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["center"] == "PAAQ" and entry["event_id"] == "tmi0xj" and entry["number"] == 1
    assert entry["category"] == "Information"
    assert entry["magnitude"] == 5.3
    assert "NO tsunami danger" in entry["note"]
    assert entry["updated"] == datetime(2026, 10, 6, 18, 39, 18, tzinfo=UTC)
    assert not ptwc_relevant(entry, "TSUNAMI INFORMATION STATEMENT ... ALASKA")


def test_ptwc_relevance_and_record():
    entry = parse_ptwc((FIXTURES / "ptwc_paaq_atom.xml").read_text(encoding="utf-8"))[0]
    assert ptwc_relevant(entry, "... HAZARDOUS TSUNAMI WAVES ARE POSSIBLE FOR COASTS OF CHILE ...")
    off_chile = {**entry, "lat": -36.0, "lon": -73.5, "number": 3, "category": "Threat"}
    assert ptwc_relevant(off_chile, "")
    record = ptwc_record(off_chile, ["07102"])
    assert record.external_id == "PAAQ-tmi0xj-3"
    assert record.supersedes == ("PAAQ-tmi0xj-1", "PAAQ-tmi0xj-2")
    assert record.level == "PTWC amenaza de tsunami"
    assert record.area_cut_codes == ("07102",)
    assert record.ends_at - record.starts_at == timedelta(hours=12)
    assert "no reemplaza el aviso oficial" in record.title
    assert ptwc_record({**entry, "category": "Cancellation"}, []).cancelled

