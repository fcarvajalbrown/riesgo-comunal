from pathlib import Path

from app.sources.shoa_snam import parse_table, to_records

FIXTURE = Path(__file__).parent / "fixtures" / "snam_index.html"


def row(states: list[str], ids: list[int]) -> str:
    times = "<br/>".join(f"06-10-2026 03:{20 + i}" for i in range(len(ids)))
    cells = ["06-10-2026 03:16", "FRENTE A CONSTITUCION", times, "<BR/>".join(states)]
    links = "".join(f"<a onclick='modalBol({i}, \"x\")'>{n}</a><br/>" for n, i in enumerate(ids, 1))
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + f"<td>{links}</td><td></td></tr>"


def test_snam_table_is_read_with_chile_time_and_epicentre():
    events = parse_table(FIXTURE.read_text(encoding="utf-8"))
    assert len(events) == 10
    first = events[0]
    assert first.bulletin_ids == [3512] and first.place == "40 KM AL W DE OLLAGUE"
    assert first.occurred_at.isoformat() == "2026-10-06T03:16:00-03:00"
    assert first.bulletin_times[0].isoformat() == "2026-10-06T03:27:00-03:00"
    assert first.states == ["INFORMATIVO PARA LAS COSTAS DE CHILE"]
    assert (first.lat, first.lon, first.magnitude, first.agency) == (-21.29, -68.37, 5.0, "GFZ")


def test_snam_informative_bulletins_are_closed_on_issue():
    record = to_records(parse_table(FIXTURE.read_text(encoding="utf-8")), ["07102"])[0]
    assert record.external_id == "snam-3512" and record.hazard == "tsunami" and record.level == "Informativo"
    assert record.ends_at == record.starts_at and record.area_cut_codes == ("07102",)


def test_snam_latest_state_of_multi_bulletin_event_decides_level():
    open_event = to_records(parse_table(row(["PRECAUCION", "ALARMA"], [7, 8])), ["07102"])[0]
    assert open_event.level == "Alarma" and open_event.ends_at is None and open_event.external_id == "snam-7"
    closed = to_records(parse_table(row(["ALARMA", "CANCELACION"], [9, 10])), [])[0]
    assert closed.ends_at.isoformat() == "2026-10-06T03:21:00-03:00"


def test_snam_page_without_table_yields_nothing():
    assert parse_table("<html><body>403 Forbidden</body></html>") == []
