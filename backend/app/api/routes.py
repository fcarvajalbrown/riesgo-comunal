import json
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import Connection, text

from app.ai.assistant import answer
from app.ai.tools import ALERT_FEED_NOTE, active_alerts
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
        "municipality": {k: municipality[k] for k in ("id", "name", "cut_code", "region", "slug", "config", "lon", "lat", "bbox_geojson")},
        "municipalities": municipalities,
        "labels": {"levels": LEVEL_LABEL, "data_classes": DATA_CLASS_LABEL},
    }


@router.get("/ahora")
def ahora(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    result = assess_comuna(conn, principal.municipality_id, mode="ahora")
    result["alerts"] = active_alerts(conn, principal.municipality_id)
    result["alert_feed_note"] = ALERT_FEED_NOTE
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


@router.get("/sources")
def sources(principal: Principal = Depends(current_principal), conn: Connection = Depends(get_conn)) -> list[dict[str, Any]]:
    data = rows(
        conn,
        """
        select s.*, (select json_agg(j order by j.started_at desc) from
            (select id, started_at, finished_at, status, record_count, error from ingestion_job
             where source_key = s.key order by started_at desc limit 5) j) as recent_jobs
        from source s order by s.key
        """,
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


class ConfigUpdate(BaseModel):
    branding: dict[str, Any] | None = None
    hazards: dict[str, dict[str, Any]] | None = None
    terminology: dict[str, str] | None = None
    contacts: list[dict[str, str]] | None = None


@router.put("/municipality/config")
def update_config(body: ConfigUpdate, principal: Principal = Depends(require("configure")), conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    current = row(conn, "select config from municipality where id = :m", m=principal.municipality_id)["config"] or {}
    patch = body.model_dump(exclude_none=True)
    for key, value in (patch.get("hazards") or {}).items():
        if key not in MODULES:
            raise HTTPException(422, f"Amenaza desconocida: {key}")
        unknown = set((value.get("thresholds") or {})) - set(MODULES[key].default_thresholds)
        if unknown:
            raise HTTPException(422, f"Umbrales desconocidos para {key}: {', '.join(sorted(unknown))}")
    updated = merge_config(current, patch)
    conn.execute(text("update municipality set config = cast(:c as jsonb) where id = :m"), {"c": json.dumps(updated, ensure_ascii=False), "m": principal.municipality_id})
    audit(conn, principal, "config_update", "municipality", patch)
    return get_municipality(conn, principal.municipality_id)["config"]


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
    kind: Literal["assets", "incidents", "sectors", "document"] = Form(...),
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    title: str | None = Form(default=None),
    principal: Principal = Depends(require("upload")),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    data = await file.read()
    try:
        result = handle_upload(conn, principal.municipality_id, principal.user_id, kind, file.filename or "archivo", file.content_type, data, category, title)
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
    deleted = conn.execute(text("delete from upload where id = :id and municipality_id = :m"), {"id": upload_id, "m": principal.municipality_id}).rowcount
    if not deleted:
        raise HTTPException(404, "Carga no encontrada")
    audit(conn, principal, "upload_delete", str(upload_id))
    return {"deleted": upload_id}


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


@router.get("/public/{slug}/resumen")
def public_summary(slug: str, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    municipality_id = scalar(conn, "select id from municipality where slug = :s", s=slug)
    if not municipality_id:
        raise HTTPException(404, "Comuna no encontrada")
    result = assess_comuna(conn, municipality_id)
    return {
        "municipality": result["municipality"]["name"],
        "computed_at": result["computed_at"],
        "items": [{"hazard": a["hazard_name"], "level": a["level"], "level_label": a["level_label"], "headline": a["headline"]} for a in result["assessments"]],
        "alerts": [{"title": a["title"], "issuer": a["issuer"], "source_url": a["source_url"]} for a in active_alerts(conn, municipality_id)],
        "notice": result["notice"],
        "official_information": "Para alertas oficiales consulte senapred.cl y los canales de su municipalidad.",
    }
