from typing import Any

from app.db import rows
from app.hazards.base import Area, Exposure, HazardContext

FACILITY_LABELS = {
    "school": ("Establecimientos educacionales", "official", "IDE Chile / MINEDUC"),
    "health_facility": ("Establecimientos de salud", "official", "IDE Chile / MINSAL"),
}


def exposure_within(ctx: HazardContext, area: Area, hazard_sql: str, params: dict[str, Any], limit_items: int = 25) -> list[Exposure]:
    base = f"""
        with area as (select {area.geom_sql()} as g),
        hz as (select st_union(h.g) as g from ({hazard_sql}) h)
    """
    p = {**area.params(), **params, "mid": ctx.municipality_id}
    official = rows(
        ctx.conn,
        base
        + """
        select f.dataset, f.id, f.name, f.category, st_x(f.geom) as lon, st_y(f.geom) as lat,
               f.properties->>'mat_total' as enrollment
        from feature f, area, hz
        where f.dataset in ('school', 'health_facility')
          and st_intersects(f.geom, area.g) and st_intersects(f.geom, hz.g)
        order by f.dataset, f.name
        """,
        **p,
    )
    municipal = rows(
        ctx.conn,
        base
        + """
        select a.category, a.id, a.name, a.is_demo, st_x(st_pointonsurface(a.geom)) as lon,
               st_y(st_pointonsurface(a.geom)) as lat
        from municipal_asset a, area, hz
        where a.municipality_id = :mid and st_intersects(a.geom, area.g) and st_intersects(a.geom, hz.g)
        order by a.category, a.name
        """,
        **p,
    )
    result: list[Exposure] = []
    for dataset, (label, data_class, source) in FACILITY_LABELS.items():
        items = [r for r in official if r["dataset"] == dataset]
        if dataset == "school":
            students = sum(int(r["enrollment"]) for r in items if (r["enrollment"] or "").isdigit())
            label = f"{label} (matrícula total {students})" if items else label
        result.append(Exposure(dataset, label, len(items), data_class, source, _items(items, limit_items)))
    categories = sorted({r["category"] for r in municipal})
    for category in categories:
        items = [r for r in municipal if r["category"] == category]
        demo = any(r["is_demo"] for r in items)
        result.append(
            Exposure(
                f"municipal:{category}",
                f"{category.replace('_', ' ').capitalize()} (registro municipal{', DEMO' if demo else ''})",
                len(items),
                "municipal",
                "Registro municipal",
                _items(items, limit_items),
            )
        )
    return result


def _items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {k: v for k, v in item.items() if k in {"id", "name", "category", "lon", "lat", "is_demo", "enrollment"}}
        for item in items[:limit]
    ]
