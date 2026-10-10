import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import Connection, text

from app.ai.assistant import answer
from app.alerts import ALERT_FEED_NOTE, ALERT_ORIGIN, FALLBACK_SOURCES, active_alerts, alert_feed_status
from app.api.layers import LAYERS, layer_catalog, layer_geojson, provenance_detail, search_places
from app.auth import Principal, audit, current_principal, issue_token, require, verify_password
from app.db import get_conn, row, rows, scalar
from app.hazards.base import DATA_CLASS_LABEL, LEVEL_LABEL
from app.hazards.registry import MODULES
from app.ingest.runner import run_source
from app.reports.builder import ROLES, build_report
from app.reports.pdf import render_pdf
from app.risk import assess_area, assess_comuna, assess_sectors, module_catalog
from app.stats.history import earthquake_statistics, icfsr_context, incident_statistics
from app.config import get_settings
from app.geocode import GeocodeError, search_address
from app.place import OutsideComuna, place_report
from app.tenants import get_municipality, merge_config, refresh_analysis_cells
from app.uploads.service import UploadError, handle_upload

router = APIRouter(prefix="/api")
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def rate_limit(bucket: str, limit: int, window_seconds: int):
    def check(request: Request) -> None:
        key = (bucket, request.client.host if request.client else "unknown")
        now = time.monotonic()
        hits = _hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(429, "Demasiadas solicitudes; espere un momento")
        hits.append(now)

    return check


class LoginRequest(BaseModel):
    email: str
    password: str


@router.get("/health")
def health(conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    scalar(conn, "select 1")
    return {"status": "ok", "time": datetime.now(UTC)}


@router.post("/auth/login", dependencies=[Depends(rate_limit("login", 10, 60))])
def login(body: LoginRequest, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    user = row(conn, "select id, email, name, role, municipality_id, password_hash, active from app_user where email = :e", e=body.email.lower().strip())
    if not user or not user["active"] or not verify_password(body.password, user["password_hash"]):
        audit(conn, None, "login_failed", body.email.lower().strip())
        raise HTTPException(401, "Correo o contraseña incorrectos")
    audit(conn, None, "login", user["email"], municipality_id=user["municipality_id"])
    return {"token": issue_token(user), "user": {k: user[k] for k in ("id", "email", "name", "role", "municipality_id")}}


@router.get("/me")
def me(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    municipality = get_municipality(conn, principal.municipality_id)
    permissions = [p for p in ("upload", "configure", "alert:create", "source:run", "audit:read") if principal.can(p)]
    municipalities = rows(conn, "select id, name, slug from municipality order by name") if principal.role == "SUPER_ADMIN" else []
    return {
        "user": {"id": principal.user_id, "email": principal.email, "name": principal.name, "role": principal.role},
        "permissions": permissions,
        "municipality": {
            **{k: municipality[k] for k in ("id", "name", "cut_code", "region", "slug", "lon", "lat", "bbox_geojson")},
            "config": public_config(municipality["config"]),
        },
        "municipalities": municipalities,
        "labels": {"levels": LEVEL_LABEL, "data_classes": DATA_CLASS_LABEL},
    }


@router.get("/ahora")
def ahora(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    result = assess_comuna(conn, principal.municipality_id, mode="ahora")
    result["alerts"] = active_alerts(conn, principal.municipality_id)
    result["alert_feed_note"] = ALERT_FEED_NOTE
    result["alert_feed_status"] = alert_feed_status(conn)
    result["exposure_summary"] = _exposure_summary(conn, principal.municipality_id)
    return result


def _exposure_summary(conn: Connection, municipality_id: int) -> list[dict[str, Any]]:
    risk = assess_comuna(conn, municipality_id, mode="riesgo")
    summary = []
    for a in risk["assessments"]:
        if a["level"] in ("MODERADO", "ALTO", "CRITICO"):
            summary.append(
                {
                    "hazard": a["hazard"],
                    "hazard_name": a["hazard_name"],
                    "level": a["level"],
                    "level_label": a["level_label"],
                    "exposure": [{"label": x["label"], "count": x["count"], "data_class": x["data_class"]} for x in a["exposure"] if x["count"]],
                }
            )
    return summary


@router.get("/riesgo")
def riesgo(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    result = assess_comuna(conn, principal.municipality_id, mode="riesgo")
    sectors = assess_sectors(conn, principal.municipality_id)
    result["sectors"] = sorted(sectors, key=lambda s: (-["SIN_DATOS", "INFORMATIVO", "BAJO", "MODERADO", "ALTO", "CRITICO"].index(s["overall_level"]), s["id"]))
    result["sector_kind"] = sectors[0]["kind"] if sectors else None
    return result


@router.get("/riesgo/sector/{sector_id}")
def riesgo_sector(sector_id: int, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    try:
        return assess_area(conn, principal.municipality_id, sector_id)
    except LookupError:
        raise HTTPException(404, "Sector no encontrado")


@router.get("/planificar")
def planificar(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    municipality = get_municipality(conn, principal.municipality_id)
    risk = assess_comuna(conn, principal.municipality_id, mode="planificar")
    return {
        "icfsr": icfsr_context(conn, municipality["cut_code"]),
        "earthquakes": earthquake_statistics(conn, principal.municipality_id),
        "incidents": incident_statistics(conn, principal.municipality_id),
        "assessments": risk["assessments"],
        "notice": risk["notice"],
    }


@router.get("/layers")
def layers(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return layer_catalog(conn)


@router.get("/layers/{key}")
def layer(key: str, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    if key not in LAYERS:
        raise HTTPException(404, "Capa no encontrada")
    return layer_geojson(conn, principal.municipality_id, key)


@router.get("/search")
def search(q: str, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    if len(q.strip()) < 2:
        return []
    return search_places(conn, principal.municipality_id, q)


@router.get("/provenance/{provenance_id}")
def provenance(provenance_id: int, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    data = provenance_detail(conn, principal.municipality_id, provenance_id)
    if not data:
        raise HTTPException(404, "Origen no encontrado")
    return data


SOURCE_STATE = """
    case when s.last_error like 'falta configurar%' then 'unconfigured'
         when s.last_error is not null then 'failed'
         when s.last_success_at is null then 'pending'
         when s.last_success_at < now() - make_interval(mins => greatest(s.interval_minutes * 3, 30)) then 'stale'
         else 'live' end as state,
    s.key = any(:alert_keys) as alert
"""


@router.get("/sources")
def sources(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    data = rows(
        conn,
        f"""
        select s.*, {SOURCE_STATE}, (select json_agg(j order by j.started_at desc) from
            (select id, started_at, finished_at, status, record_count, error from ingestion_job
             where source_key = s.key order by started_at desc limit 5) j) as recent_jobs
        from source s order by s.key
        """,
        alert_keys=list(ALERT_ORIGIN),
    )
    return data


@router.post("/sources/{key}/run")
def run(key: str, principal: Principal = Depends(require("source:run")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    if not scalar(conn, "select 1 from source where key = :k", k=key):
        raise HTTPException(404, "Fuente desconocida")
    audit(conn, principal, "source_run", key)
    return run_source(key)


@router.get("/hazards")
def hazards(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    config = get_municipality(conn, principal.municipality_id)["config"]["hazards"]
    catalog = module_catalog()
    for item in catalog:
        item["enabled"] = config.get(item["key"], {}).get("enabled", True)
        item["thresholds"] = MODULES[item["key"]].thresholds(config.get(item["key"], {}).get("thresholds"))
    return catalog


TERMINOLOGY_KEYS = (
    "tab_ahora",
    "tab_riesgo",
    "tab_planificar",
    "tab_asistente",
    "tab_informes",
    "tab_datos",
    "tab_fuentes",
    "tab_config",
    "sector",
    "sectores",
)
LOGO_TYPES = {bytes.fromhex("89504e470d0a1a0a"): ("image/png", ".png"), bytes.fromhex("ffd8ff"): ("image/jpeg", ".jpg")}
MAX_LOGO_BYTES = 1024 * 1024


class Branding(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class ConfigUpdate(BaseModel):
    branding: Branding | None = None
    hazards: dict[str, dict[str, Any]] | None = None
    terminology: dict[str, str] | None = None


@router.put("/municipality/config")
def update_config(body: ConfigUpdate, principal: Principal = Depends(require("configure")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    current = row(conn, "select config from municipality where id = :m", m=principal.municipality_id)["config"] or {}
    patch = body.model_dump(exclude_none=True)
    unknown_terms = set(patch.get("terminology") or {}) - set(TERMINOLOGY_KEYS)
    if unknown_terms:
        raise HTTPException(422, f"Términos desconocidos: {', '.join(sorted(unknown_terms))}")
    if any(len(v) > 40 for v in (patch.get("terminology") or {}).values()):
        raise HTTPException(422, "Cada término admite hasta 40 caracteres")
    if "terminology" in patch:
        patch["terminology"] = {k: v.strip() for k, v in patch["terminology"].items() if v.strip()}
    for key, value in (patch.get("hazards") or {}).items():
        if key not in MODULES:
            raise HTTPException(422, f"Amenaza desconocida: {key}")
        unknown = set((value.get("thresholds") or {})) - set(MODULES[key].default_thresholds)
        if unknown:
            raise HTTPException(422, f"Umbrales desconocidos para {key}: {', '.join(sorted(unknown))}")
    updated = merge_config(current, patch)
    if "terminology" in patch:
        updated["terminology"] = patch["terminology"]
    conn.execute(text("update municipality set config = cast(:c as jsonb) where id = :m"), {"c": json.dumps(updated, ensure_ascii=False), "m": principal.municipality_id})
    audit(conn, principal, "config_update", "municipality", patch)
    return public_config(get_municipality(conn, principal.municipality_id)["config"])


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    branding = {k: v for k, v in (config.get("branding") or {}).items() if k != "logo_path"}
    return {**config, "branding": branding}


def _set_logo(conn: Connection, municipality_id: int, logo_path: str | None, logo_url: str | None) -> None:
    config = row(conn, "select config from municipality where id = :m", m=municipality_id)["config"] or {}
    config["branding"] = {**(config.get("branding") or {}), "logo_path": logo_path, "logo_url": logo_url}
    conn.execute(text("update municipality set config = cast(:c as jsonb) where id = :m"), {"c": json.dumps(config, ensure_ascii=False), "m": municipality_id})


@router.put("/municipality/logo")
async def upload_logo(file: UploadFile = File(...), principal: Principal = Depends(require("configure")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    data = await file.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(422, "El logo no puede superar 1 MB")
    kind = next((v for signature, v in LOGO_TYPES.items() if data.startswith(signature)), None)
    if not kind:
        raise HTTPException(422, "El logo debe ser una imagen PNG o JPEG")
    municipality = get_municipality(conn, principal.municipality_id)
    old = (municipality["config"].get("branding") or {}).get("logo_path")
    folder = Path(get_settings().upload_dir) / str(principal.municipality_id)
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:12]
    path = folder / f"logo-{digest}{kind[1]}"
    path.write_bytes(data)
    _set_logo(conn, principal.municipality_id, str(path), f"/api/public/{municipality['slug']}/logo?v={digest}")
    if old and old != str(path):
        Path(old).unlink(missing_ok=True)
    audit(conn, principal, "logo_update", "municipality", {"sha256": digest})
    return public_config(get_municipality(conn, principal.municipality_id)["config"])


@router.delete("/municipality/logo")
def delete_logo(principal: Principal = Depends(require("configure")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    old = (get_municipality(conn, principal.municipality_id)["config"].get("branding") or {}).get("logo_path")
    _set_logo(conn, principal.municipality_id, None, None)
    if old:
        Path(old).unlink(missing_ok=True)
    audit(conn, principal, "logo_delete", "municipality")
    return public_config(get_municipality(conn, principal.municipality_id)["config"])


@router.get("/public/{slug}/logo")
def public_logo(slug: str, conn: Connection = Depends(get_conn)) -> Response:
    path = scalar(conn, "select config->'branding'->>'logo_path' from municipality where slug = :s", s=slug)
    if not path or not Path(path).exists():
        raise HTTPException(404, "Logo no encontrado")
    media = "image/png" if path.endswith(".png") else "image/jpeg"
    return Response(Path(path).read_bytes(), media_type=media, headers={"Cache-Control": "public, max-age=86400"})


class AlertCreate(BaseModel):
    issuer: str = Field(min_length=2, max_length=120)
    hazard: str = Field(min_length=2, max_length=60)
    level: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_url: HttpUrl
    starts_at: datetime
    ends_at: datetime | None = None


@router.get("/alerts")
def list_alerts(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        "select a.*, u.name as entered_by_name from alert a left join app_user u on u.id = a.entered_by where a.municipality_id = :m order by a.starts_at desc limit 100",
        m=principal.municipality_id,
    )


@router.post("/alerts")
def create_alert(body: AlertCreate, principal: Principal = Depends(require("alert:create")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    alert_id = scalar(
        conn,
        """
        insert into alert (municipality_id, issuer, hazard, level, title, description, source_url, starts_at, ends_at, entered_by)
        values (:m, :i, :h, :l, :t, :d, :u, :s, :e, :by) returning id
        """,
        m=principal.municipality_id,
        i=body.issuer,
        h=body.hazard,
        l=body.level,
        t=body.title,
        d=body.description,
        u=str(body.source_url),
        s=body.starts_at,
        e=body.ends_at,
        by=principal.user_id,
    )
    audit(conn, principal, "alert_create", str(alert_id), body.model_dump(mode="json"))
    return {"id": alert_id}


@router.post("/alerts/{alert_id}/end")
def end_alert(alert_id: int, principal: Principal = Depends(require("alert:create")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    updated = conn.execute(
        text("update alert set ends_at = now() where id = :id and municipality_id = :m and (ends_at is null or ends_at > now())"),
        {"id": alert_id, "m": principal.municipality_id},
    ).rowcount
    if not updated:
        raise HTTPException(404, "Alerta no encontrada o ya finalizada")
    audit(conn, principal, "alert_end", str(alert_id))
    return {"id": alert_id, "ended": True}


@router.post("/uploads", dependencies=[Depends(rate_limit("upload", 30, 60))])
async def upload(
    kind: Literal["assets", "incidents", "sectors", "document", "raster", "contacts", "inspections", "photo"] = Form(...),
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    title: str | None = Form(default=None),
    asset_id: int | None = Form(default=None),
    principal: Principal = Depends(require("upload")),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    data = await file.read()
    try:
        result = handle_upload(
            conn, principal.municipality_id, principal.user_id, kind, file.filename or "archivo", file.content_type, data, category, title, asset_id=asset_id
        )
    except UploadError as exc:
        raise HTTPException(422, str(exc))
    if kind == "sectors" and result["status"] == "done":
        refresh_analysis_cells(conn, principal.municipality_id)
    audit(conn, principal, "upload", file.filename, {"kind": kind, **result})
    return result


@router.get("/uploads")
def list_uploads(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select u.id, u.filename, u.kind, u.category, u.size_bytes, u.status, u.record_count, u.error, u.is_demo, u.uploaded_at,
               au.name as uploaded_by
        from upload u left join app_user au on au.id = u.uploaded_by
        where u.municipality_id = :m order by u.uploaded_at desc
        """,
        m=principal.municipality_id,
    )


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, principal: Principal = Depends(require("upload")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    files = [
        r["path"]
        for r in rows(
            conn,
            """
            select stored_path as path from upload where id = :id and municipality_id = :m
            union all
            select preview_path from municipal_raster where upload_id = :id and municipality_id = :m
            """,
            id=upload_id,
            m=principal.municipality_id,
        )
    ]
    deleted = conn.execute(text("delete from upload where id = :id and municipality_id = :m"), {"id": upload_id, "m": principal.municipality_id}).rowcount
    if not deleted:
        raise HTTPException(404, "Carga no encontrada")
    for path in files:
        Path(path).unlink(missing_ok=True)
    audit(conn, principal, "upload_delete", str(upload_id))
    return {"deleted": upload_id}


@router.get("/contacts")
def contacts(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select id, kind, name, role, organization, phone, email, notes, is_demo, provenance_id
        from emergency_contact where municipality_id = :m order by kind, name
        """,
        m=principal.municipality_id,
    )


@router.get("/inspections")
def inspections(asset_id: int | None = None, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select i.id, i.asset_id, i.asset_name, i.inspected_on, i.status, i.notes, i.inspector, i.is_demo, i.provenance_id,
               a.category as asset_category
        from inspection i left join municipal_asset a on a.id = i.asset_id
        where i.municipality_id = :m and (cast(:a as bigint) is null or i.asset_id = :a)
        order by i.inspected_on desc limit 500
        """,
        m=principal.municipality_id,
        a=asset_id,
    )


@router.get("/photos")
def photos(asset_id: int | None = None, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select p.id, p.asset_id, a.name as asset_name, p.caption, p.content_type, p.is_demo, p.provenance_id, p.created_at
        from photo p left join municipal_asset a on a.id = p.asset_id
        where p.municipality_id = :m and (cast(:a as bigint) is null or p.asset_id = :a)
        order by p.created_at desc limit 200
        """,
        m=principal.municipality_id,
        a=asset_id,
    )


@router.get("/photos/{photo_id}/file")
def photo_file(photo_id: int, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> Response:
    found = row(conn, "select stored_path, content_type from photo where id = :id and municipality_id = :m", id=photo_id, m=principal.municipality_id)
    if not found or not Path(found["stored_path"]).exists():
        raise HTTPException(404, "Foto no encontrada")
    return Response(Path(found["stored_path"]).read_bytes(), media_type=found["content_type"], headers={"Cache-Control": "private, max-age=3600"})


@router.get("/rasters")
def rasters(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select r.id, r.name, r.properties, r.is_demo, r.data_class, r.provenance_id, r.created_at,
               st_xmin(r.footprint) as west, st_ymin(r.footprint) as south, st_xmax(r.footprint) as east, st_ymax(r.footprint) as north
        from municipal_raster r where r.municipality_id = :m order by r.created_at desc
        """,
        m=principal.municipality_id,
    )


@router.get("/rasters/{raster_id}/preview.png")
def raster_preview(raster_id: int, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> Response:
    path = scalar(conn, "select preview_path from municipal_raster where id = :id and municipality_id = :m", id=raster_id, m=principal.municipality_id)
    if not path or not Path(path).exists():
        raise HTTPException(404, "Capa raster no encontrada")
    return Response(Path(path).read_bytes(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/documents")
def documents(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select d.id, d.title, d.filename, d.page_count, d.is_demo, d.created_at, count(c.id) as chunks
        from document d left join document_chunk c on c.document_id = d.id
        where d.municipality_id = :m group by d.id order by d.created_at desc
        """,
        m=principal.municipality_id,
    )


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    audience: Literal["ejecutivo", "tecnico", "vecino"] = "ejecutivo"


@router.post("/assistant", dependencies=[Depends(rate_limit("assistant", 30, 60))])
def assistant(body: AssistantRequest, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    result = answer(conn, principal.municipality_id, body.question, body.audience)
    audit(conn, principal, "assistant_question", None, {"question": body.question, "mode": result.get("mode"), "tools": result.get("tools")})
    return result


@router.get("/reports")
def report_list(principal: Principal = Depends(current_principal)) -> list[dict[str, str]]:
    return [{"role": k, "title": v} for k, v in ROLES.items()]


@router.get("/reports/{role}")
def report(role: str, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    if role not in ROLES:
        raise HTTPException(404, "Informe no encontrado")
    return build_report(conn, principal.municipality_id, role)


@router.get("/reports/{role}/pdf")
def report_pdf(role: str, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> Response:
    if role not in ROLES:
        raise HTTPException(404, "Informe no encontrado")
    data = build_report(conn, principal.municipality_id, role)
    audit(conn, principal, "report_pdf", role)
    filename = f"informe-{role}-{datetime.now(UTC):%Y%m%d-%H%M}.pdf"
    return Response(render_pdf(data), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/audit")
def audit_log(principal: Principal = Depends(require("audit:read")), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        select a.id, a.action, a.target, a.details, a.at, u.name as user_name
        from audit_log a left join app_user u on u.id = a.user_id
        where a.municipality_id = :m order by a.at desc limit 200
        """,
        m=principal.municipality_id,
    )


PUBLIC_LAYERS = ("comuna", "tsunami_evacuation_area", "tsunami_meeting_point", "wildfire_hazard", "dmc_warning")


def _bbox(conn: Connection, municipality_id: int) -> tuple[float, float, float, float]:
    b = row(
        conn,
        "select st_xmin(e) as w, st_ymin(e) as s, st_xmax(e) as e, st_ymax(e) as n from (select st_expand(st_envelope(boundary), 0.02) as e from municipality where id = :m) x",
        m=municipality_id,
    )
    return b["w"], b["s"], b["e"], b["n"]


def _geocode(conn: Connection, municipality_id: int, q: str) -> list[dict[str, Any]]:
    name = scalar(conn, "select name from municipality where id = :m", m=municipality_id)
    try:
        return search_address(q, _bbox(conn, municipality_id), name)
    except GeocodeError as exc:
        raise HTTPException(503, str(exc))


def _public_municipality(conn: Connection, slug: str) -> int:
    municipality_id = scalar(conn, "select id from municipality where slug = :s", s=slug)
    if not municipality_id:
        raise HTTPException(404, "Comuna no encontrada")
    return municipality_id


def _place(conn: Connection, municipality_id: int, lon: float, lat: float) -> dict[str, Any]:
    try:
        return place_report(conn, municipality_id, lon, lat)
    except OutsideComuna as exc:
        raise HTTPException(422, str(exc))


@router.get("/geocode", dependencies=[Depends(rate_limit("geocode", 30, 60))])
def geocode(q: str, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return _geocode(conn, principal.municipality_id, q)


@router.get("/lugar")
def lugar(lon: float, lat: float, principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    return _place(conn, principal.municipality_id, lon, lat)


@router.get("/public/{slug}/geocode", dependencies=[Depends(rate_limit("public_geocode", 20, 60))])
def public_geocode(slug: str, q: str, conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    return _geocode(conn, _public_municipality(conn, slug), q)


@router.get("/public/{slug}/lugar", dependencies=[Depends(rate_limit("public_place", 60, 60))])
def public_place(slug: str, lon: float, lat: float, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    return _place(conn, _public_municipality(conn, slug), lon, lat)


@router.get("/public/{slug}/capas/{key}", dependencies=[Depends(rate_limit("public_layers", 120, 60))])
def public_layer(slug: str, key: str, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    if key not in PUBLIC_LAYERS:
        raise HTTPException(404, "Capa no disponible en el portal público")
    return layer_geojson(conn, _public_municipality(conn, slug), key)


@router.get("/public/{slug}/comuna")
def public_comuna(slug: str, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    municipality = get_municipality(conn, _public_municipality(conn, slug))
    config = public_config(municipality["config"])
    return {
        "name": municipality["name"],
        "region": municipality["region"],
        "lon": municipality["lon"],
        "lat": municipality["lat"],
        "bbox": _bbox(conn, municipality["id"]),
        "display_name": config["branding"].get("display_name") or f"Municipalidad de {municipality['name']}",
        "primary_color": config["branding"].get("primary_color"),
        "logo_url": config["branding"].get("logo_url"),
    }


@router.get("/public/{slug}/fuentes", dependencies=[Depends(rate_limit("public_sources", 60, 60))])
def public_sources(slug: str, conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    _public_municipality(conn, slug)
    return rows(
        conn,
        f"select s.key, s.name, s.organization, s.interval_minutes, s.last_attempt_at, s.last_success_at, {SOURCE_STATE} from source s where s.enabled order by s.name",
        alert_keys=list(ALERT_ORIGIN),
    )


@router.get("/public/{slug}/resumen")
def public_summary(slug: str, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    municipality_id = _public_municipality(conn, slug)
    result = assess_comuna(conn, municipality_id, mode="ahora")
    standing = assess_comuna(conn, municipality_id, mode="riesgo", now=result["computed_at"])
    now = datetime.now(UTC)

    def brief(assessments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"hazard": a["hazard_name"], "level": a["level"], "level_label": a["level_label"], "headline": a["headline"]} for a in assessments]

    return {
        "municipality": result["municipality"]["name"],
        "computed_at": result["computed_at"],
        "overall_level": result["overall_level"],
        "overall_level_label": result["overall_level_label"],
        "items": brief(result["assessments"]),
        "standing_items": brief(standing["assessments"]),
        "alerts": [
            {
                "title": a["title"],
                "issuer": a["issuer"],
                "level": a["level"],
                "hazard": a["hazard"],
                "source_url": a["source_url"],
                "starts_at": a["starts_at"],
                "ends_at": a["ends_at"],
                "in_force": a["starts_at"] <= now,
                "origin": ALERT_ORIGIN.get(a["source_key"], "ingresada por la municipalidad"),
                "international": a["source_key"] in FALLBACK_SOURCES,
                "description": a["description"] if a["source_key"] in FALLBACK_SOURCES else None,
                "official_page_unavailable": bool((a["properties"] or {}).get("pagina_oficial_no_disponible")),
            }
            for a in active_alerts(conn, municipality_id, now)
        ],
        "alert_feed_note": ALERT_FEED_NOTE,
        "notice": result["notice"],
        "official_information": "Para alertas oficiales consulte senapred.cl y los canales de su municipalidad.",
    }
