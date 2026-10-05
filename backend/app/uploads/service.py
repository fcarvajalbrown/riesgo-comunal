import hashlib
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, text

from app.config import get_settings
from app.db import scalar
from app.uploads.parsers import ParsedFeature, ParseError, extract_text, normalize_value, parse_features

ASSET_CATEGORIES = {
    "albergue": "albergue",
    "albergues": "albergue",
    "escuela": "establecimiento_educacional",
    "colegio": "establecimiento_educacional",
    "establecimiento educacional": "establecimiento_educacional",
    "salud": "establecimiento_salud",
    "cesfam": "establecimiento_salud",
    "punto critico inundacion": "punto_critico_inundacion",
    "punto de inundacion": "punto_critico_inundacion",
    "anegamiento": "punto_critico_inundacion",
    "puente": "puente",
    "generador": "generador",
    "estanque de agua": "estanque_agua",
    "grifo": "grifo",
    "vehiculo municipal": "vehiculo",
    "maquinaria": "maquinaria",
    "sumidero": "sumidero",
    "ruta de evacuacion": "ruta_evacuacion",
}
HAZARD_ALIASES = {
    "inundacion": "inundacion",
    "anegamiento": "anegamiento",
    "desborde": "desborde",
    "desborde de cauce": "desborde",
    "incendio": "incendio",
    "incendio forestal": "incendio",
    "remocion en masa": "remocion",
    "remocion": "remocion",
    "aluvion": "remocion",
    "temporal": "temporal",
    "viento": "temporal",
    "marejada": "marejada",
    "sismo": "sismo",
}
EXTENSIONS = {
    "assets": (".csv", ".geojson", ".json", ".kml", ".kmz"),
    "incidents": (".csv", ".geojson", ".json", ".kml", ".kmz"),
    "sectors": (".geojson", ".json", ".kml", ".kmz"),
    "document": (".pdf", ".txt", ".md"),
}


class UploadError(ValueError):
    pass


def category_for(raw: str | None, default: str | None) -> str:
    value = normalize_value(raw or default or "")
    if not value:
        raise UploadError("Falta la categoría: indíquela en el formulario o en una columna 'categoria'")
    return ASSET_CATEGORIES.get(value, value.replace(" ", "_"))


def hazard_for(raw: str | None) -> str:
    value = normalize_value(raw or "")
    if not value:
        raise UploadError("Cada incidente necesita una columna 'amenaza' (por ejemplo inundación, incendio, remoción)")
    return HAZARD_ALIASES.get(value, "otro")


def parse_date(raw: Any) -> date:
    if isinstance(raw, date):
        return raw
    value = str(raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[: len(datetime.now().strftime(fmt))], fmt).date()
        except ValueError:
            continue
    raise UploadError(f"Fecha no reconocida: '{value}'. Use AAAA-MM-DD o DD-MM-AAAA")


def store_file(municipality_id: int, filename: str, data: bytes) -> tuple[str, str]:
    settings = get_settings()
    digest = hashlib.sha256(data).hexdigest()
    directory = Path(settings.upload_dir) / str(municipality_id)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    path = directory / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return str(path), digest


def handle_upload(
    conn: Connection,
    municipality_id: int,
    user_id: int | None,
    kind: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    category: str | None = None,
    title: str | None = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    if kind not in EXTENSIONS:
        raise UploadError("Tipo de carga desconocido")
    safe_name = Path(filename or "archivo").name
    if not safe_name.lower().endswith(EXTENSIONS[kind]):
        raise UploadError(f"Extensión no permitida para {kind}. Permitidas: {', '.join(EXTENSIONS[kind])}")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadError(f"El archivo supera {settings.max_upload_mb} MB")
    if not data:
        raise UploadError("El archivo está vacío")
    path, digest = store_file(municipality_id, safe_name, data)
    upload_id = scalar(
        conn,
        """
        insert into upload (municipality_id, filename, kind, category, content_type, size_bytes, sha256, stored_path, is_demo, uploaded_by)
        values (:m, :f, :k, :c, :ct, :sz, :sha, :p, :demo, :u) returning id
        """,
        m=municipality_id,
        f=safe_name,
        k=kind,
        c=category,
        ct=content_type,
        sz=len(data),
        sha=digest,
        p=path,
        demo=is_demo,
        u=user_id,
    )
    provenance_id = scalar(
        conn,
        """
        insert into provenance (municipality_id, upload_id, dataset, url, acquired_at, transformation, version)
        values (:m, :u, :d, :url, now(), :t, :v) returning id
        """,
        m=municipality_id,
        u=upload_id,
        d=f"municipal_{kind}",
        url=f"upload://{upload_id}/{safe_name}",
        t=f"Carga municipal de {safe_name}" + (" (DEMO)" if is_demo else ""),
        v=digest[:12],
    )
    try:
        with conn.begin_nested():
            if kind == "document":
                count = _store_document(conn, municipality_id, upload_id, safe_name, data, title, is_demo)
            else:
                features = parse_features(safe_name, data)
                if not features:
                    raise UploadError("El archivo no contiene registros")
                count = _store_features(conn, kind, municipality_id, upload_id, provenance_id, features, category, is_demo)
        conn.execute(text("update upload set status = 'done', record_count = :n where id = :id"), {"n": count, "id": upload_id})
        return {"upload_id": upload_id, "status": "done", "records": count}
    except (ParseError, UploadError) as exc:
        conn.execute(text("update upload set status = 'failed', error = :e where id = :id"), {"e": str(exc), "id": upload_id})
        return {"upload_id": upload_id, "status": "failed", "error": str(exc)}


def _geometry_sql() -> str:
    return "st_makevalid(st_setsrid(st_geomfromgeojson(:g), 4326))"


def _check_inside(conn: Connection, municipality_id: int, geometry: dict, index: int) -> None:
    inside = scalar(
        conn,
        f"select st_dwithin({_geometry_sql()}::geography, boundary::geography, 5000) from municipality where id = :m",
        g=json.dumps(geometry),
        m=municipality_id,
    )
    if not inside:
        raise UploadError(
            f"El registro {index} está a más de 5 km de la comuna. Revise que las coordenadas estén en WGS84 (latitud y longitud en grados)."
        )


def _store_features(conn, kind, municipality_id, upload_id, provenance_id, features: list[ParsedFeature], category, is_demo) -> int:
    count = 0
    for index, feature in enumerate(features, start=1):
        p = feature.properties
        if kind in ("assets", "sectors") and not feature.geometry:
            raise UploadError(f"El registro {index} no tiene geometría ni columnas de latitud y longitud")
        if feature.geometry:
            _check_inside(conn, municipality_id, feature.geometry, index)
        name = p.get("nombre") or p.get("name") or p.get("sector") or f"Registro {index}"
        if is_demo and not str(name).upper().startswith("DEMO"):
            name = f"DEMO {name}"
        if kind == "assets":
            conn.execute(
                text(
                    f"""
                    insert into municipal_asset (municipality_id, category, name, properties, geom, is_demo, upload_id, provenance_id)
                    values (:m, :c, :n, cast(:p as jsonb), {_geometry_sql()}, :demo, :u, :pid)
                    """
                ),
                {
                    "m": municipality_id,
                    "c": category_for(p.get("categoria") or p.get("tipo"), category),
                    "n": str(name),
                    "p": json.dumps(p, ensure_ascii=False, default=str),
                    "g": json.dumps(feature.geometry),
                    "demo": is_demo,
                    "u": upload_id,
                    "pid": provenance_id,
                },
            )
        elif kind == "incidents":
            occurred = parse_date(p.get("fecha") or p.get("date") or p.get("fecha_evento"))
            affected = p.get("afectados") or p.get("personas_afectadas")
            conn.execute(
                text(
                    f"""
                    insert into municipal_incident (municipality_id, hazard, occurred_on, sector_name, description,
                                                    affected_people, geom, is_demo, upload_id, provenance_id)
                    values (:m, :h, :d, :s, :desc, :a,
                            case when cast(:g as text) is null then null else st_centroid({_geometry_sql()}) end,
                            :demo, :u, :pid)
                    """
                ),
                {
                    "m": municipality_id,
                    "h": hazard_for(p.get("amenaza") or p.get("tipo") or p.get("hazard")),
                    "d": occurred,
                    "s": p.get("sector"),
                    "desc": p.get("descripcion") or p.get("description"),
                    "a": int(float(affected)) if affected not in (None, "") else None,
                    "g": json.dumps(feature.geometry) if feature.geometry else None,
                    "demo": is_demo,
                    "u": upload_id,
                    "pid": provenance_id,
                },
            )
        elif kind == "sectors":
            if feature.geometry.get("type") not in ("Polygon", "MultiPolygon"):
                raise UploadError(f"El sector {index} no es un polígono")
            conn.execute(
                text(
                    f"""
                    insert into sector (municipality_id, name, kind, geom, is_demo, upload_id, provenance_id)
                    values (:m, :n, 'municipal', st_multi(st_collectionextract({_geometry_sql()}, 3)), :demo, :u, :pid)
                    """
                ),
                {"m": municipality_id, "n": str(name), "g": json.dumps(feature.geometry), "demo": is_demo, "u": upload_id, "pid": provenance_id},
            )
        count += 1
    return count


def _store_document(conn, municipality_id, upload_id, filename, data, title, is_demo) -> int:
    chunks, pages = extract_text(filename, data)
    final_title = title or Path(filename).stem.replace("_", " ")
    if is_demo and not final_title.upper().startswith("DEMO"):
        final_title = f"DEMO {final_title}"
    document_id = scalar(
        conn,
        """
        insert into document (municipality_id, upload_id, title, filename, page_count, is_demo)
        values (:m, :u, :t, :f, :p, :demo) returning id
        """,
        m=municipality_id,
        u=upload_id,
        t=final_title,
        f=filename,
        p=pages,
        demo=is_demo,
    )
    for index, chunk in enumerate(chunks):
        conn.execute(
            text(
                "insert into document_chunk (document_id, municipality_id, chunk_index, page, content) values (:d, :m, :i, :p, :c)"
            ),
            {"d": document_id, "m": municipality_id, "i": index, "p": chunk.page, "c": chunk.content},
        )
    from app.ai.embeddings import embed_document

    embed_document(conn, document_id)
    return len(chunks)
