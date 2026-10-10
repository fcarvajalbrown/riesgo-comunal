import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
from sqlalchemy import Connection, text

from app.alerts import FALLBACK_SOURCES
from app.config import get_settings
from app.db import rows, scalar, transaction
from app.sources.base import (
    AlertRecord,
    Batch,
    EventRecord,
    FeatureRecord,
    IndexRecord,
    IngestScope,
    ObservationRecord,
    SourceAdapter,
)
from app.sources.registry import ADAPTERS, get_adapter

log = logging.getLogger(__name__)
BBOX_MARGIN_DEG = 0.05


def sync_source_registry(conn: Connection) -> None:
    settings = get_settings()
    for key, cls in ADAPTERS.items():
        m = cls.meta
        adapter = cls()
        enabled_default = not adapter.missing_requirements(settings)
        conn.execute(
            text(
                """
                insert into source (key, name, organization, url, license, commercial_use, cache_allowed, authority,
                                    attribution, interval_minutes, enabled, requires)
                values (:key, :name, :organization, :url, :license, :commercial_use, :cache_allowed, :authority,
                        :attribution, :interval_minutes, :enabled, :requires)
                on conflict (key) do update set
                    name = excluded.name, organization = excluded.organization, url = excluded.url,
                    license = excluded.license, commercial_use = excluded.commercial_use,
                    cache_allowed = excluded.cache_allowed, authority = excluded.authority,
                    attribution = excluded.attribution, requires = excluded.requires
                """
            ),
            {**asdict(m), "requires": list(m.requires), "enabled": enabled_default},
        )


def ingest_scope(conn: Connection) -> IngestScope:
    boxes = rows(
        conn,
        """
        select st_xmin(e) as x0, st_ymin(e) as y0, st_xmax(e) as x1, st_ymax(e) as y1
        from (select st_envelope(boundary) as e from municipality where boundary is not null) b
        union all
        select st_xmin(e), st_ymin(e), st_xmax(e), st_ymax(e)
        from (select st_envelope(f.geom) as e from municipality m
              join feature f on f.dataset = 'comuna_boundary' and f.external_id = m.cut_code
              where m.boundary is null) c
        """,
    )
    m = BBOX_MARGIN_DEG
    return IngestScope(tuple((r["x0"] - m, r["y0"] - m, r["x1"] + m, r["y1"] + m) for r in boxes))


def run_source(key: str, adapter: SourceAdapter | None = None, **adapter_options) -> dict:
    settings = get_settings()
    adapter = adapter or get_adapter(key, **adapter_options)
    with transaction() as conn:
        sync_source_registry(conn)
        missing = adapter.missing_requirements(settings)
        if missing:
            message = f"falta configurar: {', '.join(missing)}"
            conn.execute(text("update source set last_attempt_at = now(), last_error = :e where key = :k"), {"e": message, "k": key})
            return {"source": key, "status": "skipped", "error": message}
        job_id = scalar(conn, "insert into ingestion_job (source_key) values (:k) returning id", k=key)
        conn.execute(text("update source set last_attempt_at = now() where key = :k"), {"k": key})
        scope = ingest_scope(conn)

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}, follow_redirects=True) as client:
            batches = adapter.run(client, scope)
        with transaction() as conn:
            total, warnings = store_batches(conn, adapter, batches, job_id, scope)
            conn.execute(
                text("update ingestion_job set finished_at = now(), status = 'success', record_count = :n, warnings = cast(:w as jsonb) where id = :id"),
                {"n": total, "w": json.dumps(warnings[:200], ensure_ascii=False), "id": job_id},
            )
            conn.execute(
                text("update source set last_success_at = now(), last_error = null, last_record_count = :n where key = :k"),
                {"n": total, "k": key},
            )
        return {"source": key, "status": "success", "records": total, "warnings": len(warnings)}
    except Exception as exc:
        log.exception("ingestion failed for %s", key)
        with transaction() as conn:
            conn.execute(
                text("update ingestion_job set finished_at = now(), status = 'failed', error = :e where id = :id"),
                {"e": str(exc)[:2000], "id": job_id},
            )
            conn.execute(text("update source set last_error = :e where key = :k"), {"e": str(exc)[:2000], "k": key})
        return {"source": key, "status": "failed", "error": str(exc)}


def store_batches(
    conn: Connection, adapter: SourceAdapter, batches: list[Batch], job_id: int, scope: IngestScope
) -> tuple[int, list[str]]:
    total = 0
    warnings: list[str] = []
    for batch in batches:
        provenance_id = scalar(
            conn,
            """
            insert into provenance (source_key, dataset, url, source_time, acquired_at, ingestion_job_id, transformation, version)
            values (:s, :d, :u, :t, now(), :j, :tr, :v) returning id
            """,
            s=adapter.meta.key,
            d=batch.dataset,
            u=batch.url,
            t=batch.source_time,
            j=job_id,
            tr=batch.transformation,
            v=batch.version,
        )
        warnings.extend(batch.warnings)
        for record in batch.records:
            store_record(conn, adapter.meta.key, batch.dataset, record, provenance_id)
        total += len(batch.records)
        if batch.replace:
            remove_stale_features(conn, adapter.meta.key, batch, provenance_id, scope)
            end_missing_alerts(conn, adapter.meta.key, batch.dataset, provenance_id)
        post_process(conn, adapter.meta.key, batch.dataset)
    return total, warnings


def _solid_rings(polygon: list) -> list:
    rings = [ring for ring in polygon if len({tuple(point) for point in ring}) >= 3]
    return rings if rings and rings[0] is polygon[0] else []


def drop_collapsed_parts(geometry: dict | None) -> dict | None:
    if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return geometry
    if geometry["type"] == "Polygon":
        return {**geometry, "coordinates": _solid_rings(geometry["coordinates"])}
    parts = [rings for rings in map(_solid_rings, geometry["coordinates"]) if rings]
    return {**geometry, "coordinates": parts}


def store_record(conn: Connection, source_key: str, dataset: str, record, provenance_id: int) -> None:
    if isinstance(record, FeatureRecord):
        conn.execute(
            text(
                """
                insert into feature (source_key, dataset, external_id, name, category, properties, geom, data_class,
                                     source_updated_at, provenance_id)
                values (:s, :d, :e, :n, :c, cast(:p as jsonb),
                        st_makevalid(st_setsrid(st_geomfromgeojson(:g), 4326)), :dc, :su, :pid)
                on conflict (source_key, dataset, external_id) do update set
                    name = excluded.name, category = excluded.category, properties = excluded.properties,
                    geom = excluded.geom, data_class = excluded.data_class,
                    source_updated_at = excluded.source_updated_at, provenance_id = excluded.provenance_id
                """
            ),
            {
                "s": source_key,
                "d": dataset,
                "e": record.external_id,
                "n": record.name,
                "c": record.category,
                "p": json.dumps(record.properties, ensure_ascii=False, default=str),
                "g": json.dumps(drop_collapsed_parts(record.geometry)),
                "dc": record.data_class,
                "su": record.source_updated_at,
                "pid": provenance_id,
            },
        )
    elif isinstance(record, ObservationRecord):
        conn.execute(
            text(
                """
                insert into observation (source_key, station_external_id, station_name, parameter, parameter_name, value,
                                         unit, observed_at, validation_status, geom, provenance_id)
                values (:s, :st, :sn, :p, :pn, :v, :u, :t, :vs,
                        case when :lon is null then null else st_setsrid(st_makepoint(:lon, :lat), 4326) end, :pid)
                on conflict (source_key, station_external_id, parameter, observed_at) do update set
                    value = excluded.value, unit = excluded.unit, validation_status = excluded.validation_status,
                    provenance_id = excluded.provenance_id
                """
            ),
            {
                "s": source_key,
                "st": record.station_external_id,
                "sn": record.station_name,
                "p": record.parameter,
                "pn": record.parameter_name,
                "v": record.value,
                "u": record.unit,
                "t": record.observed_at,
                "vs": record.validation_status,
                "lon": record.lon,
                "lat": record.lat,
                "pid": provenance_id,
            },
        )
    elif isinstance(record, EventRecord):
        conn.execute(
            text(
                """
                insert into historical_event (source_key, dataset, external_id, hazard, occurred_at, magnitude, depth_km,
                                              place, properties, geom, provenance_id)
                values (:s, :d, :e, :h, :t, :m, :dk, :pl, cast(:p as jsonb), st_setsrid(st_makepoint(:lon, :lat), 4326), :pid)
                on conflict (source_key, external_id) do update set
                    occurred_at = excluded.occurred_at, magnitude = excluded.magnitude, depth_km = excluded.depth_km,
                    place = excluded.place, properties = excluded.properties, geom = excluded.geom,
                    provenance_id = excluded.provenance_id
                """
            ),
            {
                "s": source_key,
                "d": dataset,
                "e": record.external_id,
                "h": record.hazard,
                "t": record.occurred_at,
                "m": record.magnitude,
                "dk": record.depth_km,
                "pl": record.place,
                "p": json.dumps(record.properties, ensure_ascii=False, default=str),
                "lon": record.lon,
                "lat": record.lat,
                "pid": provenance_id,
            },
        )
    elif isinstance(record, IndexRecord):
        conn.execute(
            text(
                """
                insert into comuna_index (source_key, index_key, cut_code, year, value, level, components, provenance_id)
                values (:s, :k, :c, :y, :v, :l, cast(:comp as jsonb), :pid)
                on conflict (source_key, index_key, cut_code, year) do update set
                    value = excluded.value, level = excluded.level, components = excluded.components,
                    provenance_id = excluded.provenance_id
                """
            ),
            {
                "s": source_key,
                "k": record.index_key,
                "c": record.cut_code,
                "y": record.year,
                "v": record.value,
                "l": record.level,
                "comp": json.dumps(record.components, ensure_ascii=False, default=str),
                "pid": provenance_id,
            },
        )

    elif isinstance(record, AlertRecord):
        store_alert(conn, source_key, record, provenance_id)


def store_alert(conn: Connection, source_key: str, record: AlertRecord, provenance_id: int) -> None:
    sent = record.properties.get("sent") or record.starts_at
    if record.supersedes:
        conn.execute(
            text(
                """
                update alert set ends_at = least(coalesce(ends_at, cast(:sent as timestamptz)), cast(:sent as timestamptz))
                where source_key = :s and external_id = any(:refs)
                """
            ),
            {"s": source_key, "refs": list(record.supersedes), "sent": sent},
        )
    conn.execute(
        text(
            """
            insert into alert (source_key, external_id, issuer, hazard, level, title, description, source_url,
                               starts_at, ends_at, area, data_class, properties, provenance_id)
            values (:s, :e, :i, :h, :l, :t, :d, :u, :st,
                    case when :cancelled then cast(:sent as timestamptz) else cast(:en as timestamptz) end,
                    case when cast(:g as text) is not null
                         then st_multi(st_collectionextract(st_makevalid(st_setsrid(st_geomfromgeojson(:g), 4326)), 3))
                         when cardinality(cast(:codes as text[])) > 0
                         then (select st_multi(st_collectionextract(st_makevalid(st_union(geom)), 3)) from feature
                               where dataset = 'comuna_boundary' and external_id = any(cast(:codes as text[])))
                    end,
                    :dc, cast(:p as jsonb), :pid)
            on conflict (source_key, external_id) where external_id is not null do update set
                hazard = excluded.hazard, level = excluded.level, title = excluded.title, description = excluded.description,
                source_url = excluded.source_url, starts_at = excluded.starts_at,
                ends_at = case when alert.ends_at is not null and alert.ends_at < excluded.ends_at then alert.ends_at else excluded.ends_at end,
                area = excluded.area, properties = excluded.properties, provenance_id = excluded.provenance_id
            """
        ),
        {
            "s": source_key,
            "e": record.external_id,
            "i": record.issuer,
            "h": record.hazard,
            "l": record.level,
            "t": record.title,
            "d": record.description,
            "u": record.source_url,
            "st": record.starts_at,
            "en": record.ends_at,
            "cancelled": record.cancelled,
            "sent": sent,
            "g": json.dumps(record.area) if record.area else None,
            "codes": list(record.area_cut_codes),
            "dc": "international" if source_key in FALLBACK_SOURCES else "official_warning",
            "p": json.dumps({**record.properties, "cut_codes": list(record.area_cut_codes)} if record.area_cut_codes else record.properties, ensure_ascii=False, default=str),
            "pid": provenance_id,
        },
    )


def end_missing_alerts(conn: Connection, source_key: str, dataset: str, provenance_id: int) -> None:
    conn.execute(
        text(
            """
            update alert a set ends_at = now()
            from provenance p
            where a.source_key = :s and a.provenance_id = p.id and p.dataset = :d and a.provenance_id <> :pid
              and (a.ends_at is null or a.ends_at > now())
            """
        ),
        {"s": source_key, "d": dataset, "pid": provenance_id},
    )


def remove_stale_features(conn: Connection, source_key: str, batch: Batch, provenance_id: int, scope: IngestScope) -> None:
    params = {"s": source_key, "d": batch.dataset, "pid": provenance_id}
    if not batch.scoped:
        conn.execute(text("delete from feature where source_key = :s and dataset = :d and provenance_id <> :pid"), params)
        return
    for i, (x0, y0, x1, y1) in enumerate(scope.bboxes):
        conn.execute(
            text(
                """
                delete from feature where source_key = :s and dataset = :d and provenance_id <> :pid
                  and st_within(geom, st_makeenvelope(:x0, :y0, :x1, :y1, 4326))
                """
            ),
            {**params, "x0": x0, "y0": y0, "x1": x1, "y1": y1},
        )


def post_process(conn: Connection, source_key: str, dataset: str) -> None:
    if dataset == "comuna_boundary":
        conn.execute(
            text(
                """
                update municipality m set boundary = st_multi(st_collectionextract(f.geom, 3)),
                    name = coalesce(m.name, f.name)
                from feature f
                where f.dataset = 'comuna_boundary' and f.external_id = m.cut_code
                """
            )
        )
        conn.execute(
            text(
                """
                update feature f set cut_code = c.external_id
                from feature c
                where c.dataset = 'comuna_boundary' and f.dataset <> 'comuna_boundary'
                  and st_geometrytype(f.geom) = 'ST_Point' and st_intersects(c.geom, f.geom)
                """
            )
        )
        return
    conn.execute(
        text(
            """
            update feature f set cut_code = c.external_id
            from feature c
            where f.source_key = :s and f.dataset = :d and c.dataset = 'comuna_boundary'
              and st_geometrytype(f.geom) = 'ST_Point' and st_intersects(c.geom, f.geom)
            """
        ),
        {"s": source_key, "d": dataset},
    )
    conn.execute(
        text(
            """
            update observation o set cut_code = c.external_id
            from feature c
            where o.source_key = :s and o.cut_code is null and o.geom is not null
              and c.dataset = 'comuna_boundary' and st_intersects(c.geom, o.geom)
            """
        ),
        {"s": source_key},
    )


def mark_all_sources_due(conn: Connection) -> None:
    conn.execute(text("update source set last_attempt_at = null"))


def due_sources(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    with transaction() as conn:
        sync_source_registry(conn)
        result = rows(conn, "select key, interval_minutes, last_attempt_at, enabled from source where enabled")
    due = []
    for r in result:
        last = r["last_attempt_at"]
        if last is None or (now - last).total_seconds() >= r["interval_minutes"] * 60:
            due.append(r["key"])
    return due
