import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from app.db import row, rows
from app.hazards.common import latest_provenance
from app.risk import assess_sectors


@dataclass(frozen=True)
class LayerDef:
    key: str
    name: str
    description: str
    data_class: str
    source_key: str | None
    dataset: str | None
    geometry: str
    legend: tuple[tuple[str, str], ...] = ()
    default_on: bool = False


LAYERS: dict[str, LayerDef] = {
    layer.key: layer
    for layer in (
        LayerDef("comuna", "Límite comunal", "Límite oficial de la comuna (DPA 2023).", "official", "senapred", "comuna_boundary", "polygon", default_on=True),
        LayerDef(
            "sectors",
            "Nivel por sector",
            "Nivel calculado por la plataforma para cada sector o celda de análisis.",
            "derived",
            None,
            None,
            "polygon",
            (("CRITICO", "Crítico"), ("ALTO", "Alto"), ("MODERADO", "Moderado"), ("BAJO", "Bajo"), ("SIN_DATOS", "Sin datos")),
            default_on=True,
        ),
        LayerDef(
            "wildfire_hazard",
            "Recurrencia de incendios forestales",
            "Densidad de incendios 2020-2024 por clase (SENAPRED con datos CONAF).",
            "official",
            "senapred",
            "wildfire_hazard",
            "polygon",
            (("5", "Muy alta"), ("4", "Alta"), ("3", "Media"), ("2", "Baja"), ("1", "Muy baja")),
        ),
        LayerDef("tsunami_evacuation_area", "Área a evacuar por tsunami", "Áreas de evacuación por tsunami (SENAPRED).", "official", "senapred", "tsunami_evacuation_area", "polygon"),
        LayerDef("tsunami_meeting_point", "Puntos de encuentro (tsunami)", "Puntos de encuentro ante tsunami (SENAPRED).", "official", "senapred", "tsunami_meeting_point", "point"),
        LayerDef("school", "Establecimientos educacionales", "Directorio MINEDUC vía IDE Chile.", "official", "ide_geoportal", "school", "point", default_on=True),
        LayerDef("health_facility", "Establecimientos de salud", "Establecimientos MINSAL vía IDE Chile.", "official", "ide_geoportal", "health_facility", "point", default_on=True),
        LayerDef(
            "dmc_warning",
            "Avisos, alertas y alarmas DMC",
            "Boletines meteorológicos oficiales vigentes o próximos que cubren la comuna (Dirección Meteorológica de Chile).",
            "official_warning",
            "dmc_cap",
            "dmc_warning",
            "polygon",
            (("Alarma", "Alarma"), ("Alerta", "Alerta"), ("Aviso", "Aviso")),
        ),
        LayerDef("aq_station", "Estaciones de calidad del aire", "Estaciones SINCA con último MP2,5 (no validado).", "observed", "sinca", "aq_station", "point"),
        LayerDef("dga_station", "Estaciones hidrométricas DGA", "Catálogo de la Red Hidrométrica Nacional.", "official", "dga_red_hidrometrica", "dga_station", "point"),
        LayerDef("earthquake", "Sismos últimos 30 días", "Sismos M2,5+ a menos de 300 km (USGS, complementario).", "observed", "usgs", "earthquake", "point"),
        LayerDef("municipal_asset", "Activos municipales", "Infraestructura y recursos cargados por el municipio.", "municipal", None, None, "mixed", default_on=True),
        LayerDef("municipal_incident", "Incidentes históricos municipales", "Incidentes registrados por el municipio.", "historical", None, None, "point"),
    )
}


def layer_catalog(conn: Connection) -> list[dict[str, Any]]:
    result = []
    for layer in LAYERS.values():
        prov = latest_provenance(conn, layer.source_key, layer.dataset) if layer.source_key else None
        result.append(
            {
                "key": layer.key,
                "name": layer.name,
                "description": layer.description,
                "data_class": layer.data_class,
                "geometry": layer.geometry,
                "legend": [{"value": v, "label": label} for v, label in layer.legend],
                "default_on": layer.default_on,
                "source": prov["attribution"] if prov else ("Registro municipal" if layer.data_class in ("municipal", "historical") else "Cálculo de la plataforma"),
                "updated_at": (prov["source_time"] or prov["ingested_at"]) if prov else None,
                "provenance_id": prov["id"] if prov else None,
            }
        )
    return result


def _collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": f.pop("fid"), "geometry": json.loads(f.pop("geojson")), "properties": f}
            for f in features
            if f.get("geojson")
        ],
    }


def layer_geojson(conn: Connection, municipality_id: int, key: str) -> dict[str, Any]:
    if key not in LAYERS:
        raise KeyError(key)
    m = {"mid": municipality_id}
    if key == "comuna":
        return _collection(
            rows(conn, "select id as fid, name, cut_code, st_asgeojson(boundary, 6) as geojson from municipality where id = :mid", **m)
        )
    if key == "sectors":
        levels = {s["id"]: s for s in assess_sectors(conn, municipality_id)}
        features = rows(
            conn,
            """
            select s.id as fid, s.id, s.name, s.kind, s.is_demo, st_asgeojson(s.geom, 6) as geojson
            from sector s where s.municipality_id = :mid
              and s.kind = (case when exists(select 1 from sector where municipality_id = :mid and kind = 'municipal')
                                 then 'municipal' else 'analysis_cell' end)
            """,
            **m,
        )
        for f in features:
            info = levels.get(f["id"], {})
            f["level"] = info.get("overall_level", "SIN_DATOS")
            f["level_label"] = info.get("overall_level_label", "Sin datos")
            f["levels"] = info.get("levels", {})
            f["reasons"] = info.get("reasons", [])
            f["uses_demo_data"] = info.get("uses_demo_data", False)
        return _collection(features)
    if key in ("wildfire_hazard", "tsunami_evacuation_area"):
        return _collection(
            rows(
                conn,
                """
                select f.id as fid, f.name, f.category, f.properties->>'clase' as clase, f.properties->>'sector' as sector,
                       f.provenance_id, st_asgeojson(st_intersection(f.geom, m.boundary), 6) as geojson
                from feature f, municipality m
                where m.id = :mid and f.dataset = :d and st_intersects(f.geom, m.boundary)
                """,
                d=key,
                **m,
            )
        )
    if key == "dmc_warning":
        return _collection(
            rows(
                conn,
                """
                select a.id as fid, a.level, a.title, a.properties->>'event' as event, a.starts_at, a.ends_at,
                       a.source_url, a.provenance_id, st_asgeojson(st_intersection(a.area, m.boundary), 6) as geojson
                from alert a, municipality m
                where m.id = :mid and a.source_key = 'dmc_cap' and (a.ends_at is null or a.ends_at > now())
                  and st_intersects(a.area, m.boundary)
                order by case a.level when 'Aviso' then 0 when 'Alerta' then 1 else 2 end
                """,
                **m,
            )
        )
    if key in ("tsunami_meeting_point", "school", "health_facility", "dga_station"):
        return _collection(
            rows(
                conn,
                """
                select f.id as fid, f.name, f.category, f.provenance_id, f.source_updated_at,
                       f.properties->>'mat_total' as matricula, f.properties->>'direccion' as direccion,
                       f.properties->>'tipo' as tipo, f.properties->>'vigencia' as vigencia,
                       st_asgeojson(f.geom, 6) as geojson
                from feature f, municipality m
                where m.id = :mid and f.dataset = :d and st_dwithin(f.geom::geography, m.boundary::geography, 500)
                """,
                d=key,
                **m,
            )
        )
    if key == "aq_station":
        return _collection(
            rows(
                conn,
                """
                select f.id as fid, f.name, f.category, f.provenance_id,
                       o.value as pm25, o.unit, o.observed_at, o.validation_status,
                       st_asgeojson(f.geom, 6) as geojson
                from feature f
                join municipality m on m.id = :mid
                left join lateral (
                    select value, unit, observed_at, validation_status from observation
                    where source_key = 'sinca' and station_external_id = f.external_id and parameter = 'PM25'
                    order by observed_at desc limit 1
                ) o on true
                where f.dataset = 'aq_station' and st_dwithin(f.geom::geography, m.boundary::geography, 15000)
                """,
                **m,
            )
        )
    if key == "earthquake":
        return _collection(
            rows(
                conn,
                """
                select e.id as fid, e.magnitude, e.depth_km, e.place, e.occurred_at, e.provenance_id,
                       st_asgeojson(e.geom, 4) as geojson
                from historical_event e, municipality m
                where m.id = :mid and e.hazard = 'earthquake' and e.occurred_at > now() - interval '30 days'
                  and st_dwithin(e.geom::geography, m.boundary::geography, 300000)
                order by e.occurred_at desc
                """,
                **m,
            )
        )
    if key == "municipal_asset":
        return _collection(
            rows(
                conn,
                "select id as fid, category, name, is_demo, provenance_id, st_asgeojson(geom, 6) as geojson from municipal_asset where municipality_id = :mid",
                **m,
            )
        )
    return _collection(
        rows(
            conn,
            """
            select id as fid, hazard, occurred_on, sector_name, description, affected_people, is_demo, provenance_id,
                   st_asgeojson(geom, 6) as geojson
            from municipal_incident where municipality_id = :mid and geom is not null
            """,
            **m,
        )
    )


def search_places(conn: Connection, municipality_id: int, query: str, limit: int = 12) -> list[dict[str, Any]]:
    like = f"%{query.strip()}%"
    return rows(
        conn,
        """
        (select 'feature' as kind, f.dataset as layer, f.name, st_x(st_pointonsurface(f.geom)) as lon, st_y(st_pointonsurface(f.geom)) as lat
         from feature f, municipality m
         where m.id = :mid and f.dataset in ('school','health_facility','tsunami_meeting_point','aq_station','dga_station')
           and f.name ilike :q and st_dwithin(f.geom::geography, m.boundary::geography, 2000))
        union all
        (select 'sector', 'sectors', name, st_x(st_pointonsurface(geom)), st_y(st_pointonsurface(geom))
         from sector where municipality_id = :mid and name ilike :q)
        union all
        (select 'asset', 'municipal_asset', name, st_x(st_pointonsurface(geom)), st_y(st_pointonsurface(geom))
         from municipal_asset where municipality_id = :mid and name ilike :q)
        limit :n
        """,
        mid=municipality_id,
        q=like,
        n=limit,
    )


def provenance_detail(conn: Connection, municipality_id: int, provenance_id: int) -> dict[str, Any] | None:
    data = row(
        conn,
        """
        select p.id, p.dataset, p.url, p.source_time, p.acquired_at, p.ingested_at, p.transformation, p.version,
               p.municipality_id, p.upload_id,
               s.key as source_key, s.name as source_name, s.organization, s.license, s.commercial_use,
               s.cache_allowed, s.authority, s.attribution, s.url as source_url,
               j.id as job_id, j.started_at as job_started_at, j.status as job_status, j.record_count as job_records,
               u.filename as upload_filename, u.uploaded_at, u.is_demo as upload_is_demo, au.name as uploaded_by
        from provenance p
        left join source s on s.key = p.source_key
        left join ingestion_job j on j.id = p.ingestion_job_id
        left join upload u on u.id = p.upload_id
        left join app_user au on au.id = u.uploaded_by
        where p.id = :id
        """,
        id=provenance_id,
    )
    if not data or (data["municipality_id"] is not None and data["municipality_id"] != municipality_id):
        return None
    return data
