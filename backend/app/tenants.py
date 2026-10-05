import json
from typing import Any

from sqlalchemy import Connection, text

from app.db import row, scalar

ANALYSIS_CELL_DEG = 0.015

DEFAULT_CONFIG: dict[str, Any] = {
    "branding": {"display_name": None, "primary_color": "#1f4e79", "logo_url": None},
    "hazards": {
        "wildfire": {"enabled": True, "thresholds": {}},
        "tsunami": {"enabled": True, "thresholds": {}},
        "air_quality": {"enabled": True, "thresholds": {}},
        "earthquake": {"enabled": True, "thresholds": {}},
        "flood": {"enabled": True, "thresholds": {}},
        "meteo": {"enabled": True, "thresholds": {}},
    },
    "terminology": {},
}


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_municipality(conn: Connection, municipality_id: int) -> dict[str, Any] | None:
    m = row(
        conn,
        """
        select id, cut_code, name, region, slug, config, boundary is not null as has_boundary,
               st_asgeojson(st_envelope(boundary))::json as bbox_geojson,
               st_x(st_centroid(boundary)) as lon, st_y(st_centroid(boundary)) as lat
        from municipality where id = :id
        """,
        id=municipality_id,
    )
    if m:
        m["config"] = merge_config(DEFAULT_CONFIG, m["config"] or {})
    return m


def create_municipality(conn: Connection, cut_code: str, slug: str, name: str | None = None) -> int:
    existing = scalar(conn, "select id from municipality where cut_code = :c", c=cut_code)
    if existing:
        return existing
    if not scalar(conn, "select 1 from feature where dataset = 'comuna_boundary' and external_id = :c", c=cut_code):
        raise ValueError(f"no existe el límite comunal para CUT {cut_code}")
    boundary = row(
        conn,
        "select name, properties->>'region' as region from feature where dataset = 'comuna_boundary' and external_id = :c",
        c=cut_code,
    )
    return scalar(
        conn,
        """
        insert into municipality (cut_code, name, region, slug, config, boundary)
        values (:c, :n, :r, :s, cast(:cfg as jsonb),
                (select st_multi(st_collectionextract(geom, 3)) from feature
                 where dataset = 'comuna_boundary' and external_id = :c))
        returning id
        """,
        c=cut_code,
        n=name or (boundary or {}).get("name") or cut_code,
        r=(boundary or {}).get("region"),
        s=slug,
        cfg=json.dumps({}),
    )


def refresh_analysis_cells(conn: Connection, municipality_id: int) -> int:
    conn.execute(text("delete from sector where municipality_id = :m and kind = 'analysis_cell'"), {"m": municipality_id})
    conn.execute(
        text(
            """
            insert into sector (municipality_id, name, kind, geom)
            select :m, 'Celda ' || row_number() over (order by st_ymax(g.geom) desc, st_xmin(g.geom)),
                   'analysis_cell', st_multi(st_collectionextract(st_intersection(g.geom, m.boundary), 3))
            from municipality m
            cross join lateral st_squaregrid(:size, m.boundary) g
            where m.id = :m and st_intersects(g.geom, m.boundary)
              and st_area(st_intersection(g.geom, m.boundary)::geography) > 20000
            """
        ),
        {"m": municipality_id, "size": ANALYSIS_CELL_DEG},
    )
    return scalar(conn, "select count(*) from sector where municipality_id = :m and kind = 'analysis_cell'", m=municipality_id)


def has_municipal_sectors(conn: Connection, municipality_id: int) -> bool:
    return bool(scalar(conn, "select 1 from sector where municipality_id = :m and kind = 'municipal' limit 1", m=municipality_id))


def active_sector_kind(conn: Connection, municipality_id: int) -> str:
    return "municipal" if has_municipal_sectors(conn, municipality_id) else "analysis_cell"
