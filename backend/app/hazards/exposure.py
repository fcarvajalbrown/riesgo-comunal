from typing import Any

from app.db import rows
from app.hazards.base import Area, Exposure, HazardContext

CENSUS_SOURCE = "INE, Censo de Población y Vivienda 2024 (base manzana-entidad)"
CENSUS_NOTE = (
    "Estimación de la plataforma: cada manzana o entidad aporta en proporción a la parte de su superficie dentro de la zona, "
    "suponiendo población repartida de forma pareja. En entidades rurales grandes la cifra es aproximada."
)
CENSUS_COUNTS = (
    ("census_population", "n_per", "Personas (Censo 2024)"),
    ("census_older", "n_edad_60_mas", "Personas de 60 años o más (Censo 2024)"),
    ("census_dwellings", "n_vp", "Viviendas particulares (Censo 2024)"),
)

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
    result: list[Exposure] = population_within(ctx, base, p)
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


def population_within(ctx: HazardContext, base: str, params: dict[str, Any]) -> list[Exposure]:
    sums = ", ".join(f"coalesce(sum((b.properties->>'{field}')::numeric * frac), 0) as {key}" for key, field, _ in CENSUS_COUNTS)
    totals = rows(
        ctx.conn,
        base
        + f"""
        , parts as (
            select b.properties, st_area(st_intersection(b.geom, hz.g)) / nullif(st_area(b.geom), 0) as frac
            from feature b, area, hz
            where b.dataset = 'census_block' and st_intersects(b.geom, area.g) and st_intersects(b.geom, hz.g)
        )
        select count(*) as blocks, {sums}
        from parts b
        """,
        **params,
    )[0]
    if not totals["blocks"]:
        return []
    return [Exposure(key, label, round(float(totals[key])), "estimated", CENSUS_SOURCE, note=CENSUS_NOTE) for key, _, label in CENSUS_COUNTS]


def _items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {k: v for k, v in item.items() if k in {"id", "name", "category", "lon", "lat", "is_demo", "enrollment"}}
        for item in items[:limit]
    ]
