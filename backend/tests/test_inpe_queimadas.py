from pathlib import Path

from app.sources.base import RawPayload
from app.sources.inpe_queimadas import InpeQueimadasAdapter, parse_detections

FIXTURES = Path(__file__).parent / "fixtures"


def test_only_chilean_detections_are_kept_from_real_csv():
    text = (FIXTURES / "inpe_focos_diario.csv").read_text(encoding="utf-8")
    detections = parse_detections(text)
    assert detections and all(d["region"] for d in detections)
    assert len(detections) == sum(1 for line in text.splitlines() if ",Chile," in line)
    first = detections[0]
    assert first["seen"].tzinfo is not None and first["satellite"]


def test_detections_become_fire_events():
    text = (FIXTURES / "inpe_focos_diario.csv").read_text(encoding="utf-8")
    adapter = InpeQueimadasAdapter()
    raw = RawPayload(dataset="fire_detection", url="https://example", body=text)
    batch = adapter.normalize(raw, adapter.parse(raw))
    assert batch.records and all(r.hazard == "fire_detection" for r in batch.records)
    assert batch.records[0].properties["satellite"]
