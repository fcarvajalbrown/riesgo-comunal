from datetime import UTC, datetime, timedelta

from app.hazards.active_fire import confirmed, group_spots, level_for


def detection(source: str, satellite: str, minutes: int, lat: float, lon: float) -> dict:
    return {
        "source_key": source,
        "satellite": satellite,
        "occurred_at": datetime(2026, 10, 9, 5, 0, tzinfo=UTC) + timedelta(minutes=minutes),
        "lat": lat,
        "lon": lon,
        "frp": 2.0,
    }


def test_no_detections_is_low():
    assert level_for([]) == "BAJO"


def test_single_pass_is_moderate_and_unconfirmed():
    spots = group_spots([detection("inpe_queimadas", "NOAA-20", 0, -34.9385, -72.0651), detection("inpe_queimadas", "NOAA-20", 0, -34.9357, -72.0643)])
    assert len(spots) == 1 and not confirmed(spots[0])
    assert level_for(spots) == "MODERADO"


def test_second_pass_or_second_source_confirms():
    two_passes = group_spots([detection("inpe_queimadas", "TERRA_M-M", 0, -34.9385, -72.0749), detection("inpe_queimadas", "NOAA-20", 205, -34.9385, -72.0651)])
    two_sources = group_spots([detection("inpe_queimadas", "NOAA-20", 0, -34.9385, -72.0651), detection("nasa_firms", "NOAA-20", 0, -34.9386, -72.0652)])
    assert level_for(two_passes) == level_for(two_sources) == "ALTO"


def test_distant_spots_stay_separate():
    spots = group_spots([detection("inpe_queimadas", "NOAA-20", 0, -34.94, -72.06), detection("inpe_queimadas", "NOAA-20", 0, -35.40, -71.70)])
    assert len(spots) == 2 and level_for(spots) == "MODERADO"
