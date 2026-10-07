from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db import get_engine, rows, scalar
from app.hazards.base import Area
from app.hazards.registry import MODULES
from app.risk import context
from app.tenants import get_municipality


def _lota_id() -> int | None:
    try:
        with get_engine().connect() as conn:
            return scalar(conn, "select id from municipality where cut_code = '08106'")
    except Exception:
        return None


pytestmark = pytest.mark.skipif(_lota_id() is None, reason="requiere la comuna piloto creada")


def test_batched_sector_assessment_matches_per_sector_assessment():
    now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    with get_engine().connect() as conn:
        mid = _lota_id()
        sectors = rows(conn, "select id, name from sector where municipality_id = :m and kind = 'analysis_cell' order by id", m=mid)
        flooded = [s["id"] for s in sectors[:6]]
        for index, sector_id in enumerate(flooded):
            point = "(select st_pointonsurface(geom) from sector where id = :s)"
            for _ in range(index):
                conn.execute(
                    text(f"insert into municipal_incident (municipality_id, hazard, occurred_on, affected_people, geom, is_demo) values (:m, 'inundacion', '2024-06-01', 3, {point}, true)"),
                    {"m": mid, "s": sector_id},
                )
            conn.execute(
                text(f"insert into municipal_asset (municipality_id, category, name, geom) values (:m, 'punto_critico_inundacion', :n, {point})"),
                {"m": mid, "n": f"Punto {index % 3}", "s": sector_id},
            )
        municipality = get_municipality(conn, mid)
        areas = [Area("sector", s["id"], s["name"]) for s in sectors]
        for module in MODULES.values():
            if not module.spatial:
                continue
            ctx = context(conn, municipality, module.key, now, detail=False)
            assert module.assess_sectors(ctx, areas) == [module.assess(ctx, area) for area in areas], module.key
        conn.rollback()
