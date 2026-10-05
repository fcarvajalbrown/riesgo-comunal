import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.db import rows, scalar
from app.hazards.base import DERIVED_NOTICE, LEVEL_LABEL, LEVEL_RANK, Area, HazardContext, max_level
from app.hazards.registry import MODULES, enabled_modules
from app.tenants import active_sector_kind, get_municipality

SECTOR_CACHE_SECONDS = 300
_sector_cache: dict[tuple, tuple[float, list[dict[str, Any]]]] = {}


def context(conn: Connection, municipality: dict, module_key: str, now: datetime, detail: bool = True) -> HazardContext:
    overrides = municipality["config"]["hazards"].get(module_key, {}).get("thresholds", {})
    return HazardContext(conn=conn, municipality=municipality, thresholds=overrides, now=now, detail=detail)


def assess_comuna(conn: Connection, municipality_id: int, mode: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    municipality = get_municipality(conn, municipality_id)
    area = Area("comuna", municipality_id, municipality["name"])
    assessments = []
    for module in enabled_modules(municipality["config"]):
        if mode and mode not in module.modes:
            continue
        assessments.append(module.assess(context(conn, municipality, module.key, now), area).to_dict())
    overall = max_level([a["level"] for a in assessments])
    return {
        "municipality": {"id": municipality_id, "name": municipality["name"], "cut_code": municipality["cut_code"]},
        "mode": mode,
        "computed_at": now,
        "overall_level": overall,
        "overall_level_label": LEVEL_LABEL[overall],
        "overall_data_class": "derived",
        "notice": DERIVED_NOTICE,
        "assessments": sorted(assessments, key=lambda a: _rank(a["level"]), reverse=True),
    }


def assess_sectors(conn: Connection, municipality_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    municipality = get_municipality(conn, municipality_id)
    kind = active_sector_kind(conn, municipality_id)
    stamp = scalar(conn, "select max(ingested_at) from provenance where municipality_id is null or municipality_id = :m", m=municipality_id)
    key = (municipality_id, kind, str(stamp), str(municipality["config"]))
    cached = _sector_cache.get(key)
    if cached and time.monotonic() - cached[0] < SECTOR_CACHE_SECONDS:
        return cached[1]
    modules = [m for m in enabled_modules(municipality["config"]) if m.spatial]
    sectors = rows(
        conn,
        "select id, name, kind, is_demo from sector where municipality_id = :m and kind = :k order by id",
        m=municipality_id,
        k=kind,
    )
    result = []
    for sector in sectors:
        area = Area("sector", sector["id"], sector["name"])
        levels = {}
        reasons = []
        uses_demo = False
        for module in modules:
            assessment = module.assess(context(conn, municipality, module.key, now, detail=False), area)
            levels[module.key] = assessment.level
            uses_demo = uses_demo or assessment.uses_demo_data
            if assessment.level in ("MODERADO", "ALTO", "CRITICO"):
                reasons.append(f"{module.name}: {assessment.explanation[0]}")
        overall = max_level(list(levels.values()))
        result.append(
            {**sector, "levels": levels, "overall_level": overall, "overall_level_label": LEVEL_LABEL[overall], "reasons": reasons, "uses_demo_data": uses_demo}
        )
    _sector_cache[key] = (time.monotonic(), result)
    return result


def assess_area(conn: Connection, municipality_id: int, sector_id: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    municipality = get_municipality(conn, municipality_id)
    sector = rows(conn, "select id, name, kind, is_demo from sector where id = :s and municipality_id = :m", s=sector_id, m=municipality_id)
    if not sector:
        raise LookupError("sector")
    area = Area("sector", sector_id, sector[0]["name"])
    assessments = [
        module.assess(context(conn, municipality, module.key, now), area).to_dict()
        for module in enabled_modules(municipality["config"])
        if module.spatial
    ]
    return {"sector": sector[0], "computed_at": now, "notice": DERIVED_NOTICE, "assessments": assessments,
            "overall_level": max_level([a["level"] for a in assessments])}


def module_catalog() -> list[dict[str, Any]]:
    return [m.describe() for m in MODULES.values()]


def _rank(level: str) -> int:
    return LEVEL_RANK[level]
