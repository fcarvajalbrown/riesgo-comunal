import secrets

import pytest
from sqlalchemy import text

from app.auth import hash_password
from app.db import scalar, transaction

TEST_CUT = "08102"
TEST_SLUG = "test-coronel"


def _db_ready() -> bool:
    try:
        with transaction() as conn:
            return bool(scalar(conn, "select 1 from feature where dataset = 'comuna_boundary' and external_id = :c", c=TEST_CUT))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="requiere la base de datos con límites comunales ingestados")


@pytest.fixture(scope="module")
def env():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.tenants import create_municipality, refresh_analysis_cells

    password = secrets.token_urlsafe(10)
    with transaction() as conn:
        lota = scalar(conn, "select id from municipality where cut_code = '08106'")
        if lota is None:
            pytest.skip("requiere la comuna piloto creada")
        other = create_municipality(conn, TEST_CUT, TEST_SLUG)
        refresh_analysis_cells(conn, other)
        users = {}
        for key, municipality_id, role in (
            ("lota_alcalde", lota, "ALCALDE"),
            ("lota_admin", lota, "MUNICIPAL_ADMIN"),
            ("other_admin", other, "MUNICIPAL_ADMIN"),
        ):
            email = f"pytest.{key}@test.local"
            scalar(
                conn,
                """
                insert into app_user (municipality_id, email, name, password_hash, role) values (:m, :e, :n, :p, :r)
                on conflict (email) do update set password_hash = excluded.password_hash, municipality_id = excluded.municipality_id, role = excluded.role
                returning id
                """,
                m=municipality_id,
                e=email,
                n=key,
                p=hash_password(password),
                r=role,
            )
            users[key] = email
    client = TestClient(app)
    tokens = {}
    for key, email in users.items():
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        tokens[key] = {"Authorization": f"Bearer {response.json()['token']}"}
    yield client, tokens, lota, other
    with transaction() as conn:
        conn.execute(text("delete from app_user where email like 'pytest.%@test.local'"))
        conn.execute(text("delete from municipality where slug = :s"), {"s": TEST_SLUG})


def test_login_rejects_wrong_password(env):
    client, *_ = env
    assert client.post("/api/auth/login", json={"email": "pytest.lota_admin@test.local", "password": "incorrecta"}).status_code == 401


def test_requests_without_token_are_rejected(env):
    client, *_ = env
    assert client.get("/api/riesgo").status_code == 401


def test_me_returns_own_tenant(env):
    client, tokens, lota, _ = env
    body = client.get("/api/me", headers=tokens["lota_alcalde"]).json()
    assert body["municipality"]["id"] == lota
    assert "upload" not in body["permissions"]


def test_alcalde_cannot_upload(env):
    client, tokens, *_ = env
    response = client.post("/api/uploads", headers=tokens["lota_alcalde"], data={"kind": "assets", "category": "albergue"}, files={"file": ("a.csv", b"nombre,lat,lon\nX,-37.09,-73.15\n", "text/csv")})
    assert response.status_code == 403


def test_tenant_isolation_for_uploads_and_provenance(env):
    client, tokens, _, other = env
    with transaction() as conn:
        center = conn.execute(text("select st_y(st_pointonsurface(boundary)), st_x(st_pointonsurface(boundary)) from municipality where id = :m"), {"m": other}).first()
    csv_bytes = f"nombre,categoria,lat,lon\nAlbergue prueba,albergue,{center[0]},{center[1]}\n".encode()
    upload = client.post("/api/uploads", headers=tokens["other_admin"], data={"kind": "assets"}, files={"file": ("prueba.csv", csv_bytes, "text/csv")})
    assert upload.status_code == 200, upload.text
    assert upload.json()["status"] == "done"
    upload_id = upload.json()["upload_id"]

    lota_uploads = client.get("/api/uploads", headers=tokens["lota_admin"]).json()
    assert upload_id not in [u["id"] for u in lota_uploads]

    with transaction() as conn:
        provenance_id = scalar(conn, "select id from provenance where upload_id = :u", u=upload_id)
    assert client.get(f"/api/provenance/{provenance_id}", headers=tokens["lota_admin"]).status_code == 404
    assert client.get(f"/api/provenance/{provenance_id}", headers=tokens["other_admin"]).status_code == 200

    assert client.delete(f"/api/uploads/{upload_id}", headers=tokens["lota_admin"]).status_code == 404
    assert client.delete(f"/api/uploads/{upload_id}", headers=tokens["other_admin"]).status_code == 200


def test_upload_outside_comuna_is_rejected(env):
    client, tokens, *_ = env
    csv_bytes = b"nombre,categoria,lat,lon\nLejos,albergue,-33.45,-70.66\n"
    result = client.post("/api/uploads", headers=tokens["other_admin"], data={"kind": "assets"}, files={"file": ("lejos.csv", csv_bytes, "text/csv")}).json()
    assert result["status"] == "failed"
    assert "5 km" in result["error"]


def test_config_rejects_unknown_threshold(env):
    client, tokens, *_ = env
    response = client.put("/api/municipality/config", headers=tokens["other_admin"], json={"hazards": {"wildfire": {"thresholds": {"inventado": 1}}}})
    assert response.status_code == 422


def test_config_threshold_change_is_applied(env):
    client, tokens, *_ = env
    response = client.put("/api/municipality/config", headers=tokens["other_admin"], json={"hazards": {"wildfire": {"thresholds": {"high_share_alto": 0.5}}}})
    assert response.status_code == 200
    hazards = {h["key"]: h for h in client.get("/api/hazards", headers=tokens["other_admin"]).json()}
    assert hazards["wildfire"]["thresholds"]["high_share_alto"] == 0.5


def test_risk_levels_are_labelled_derived(env):
    client, tokens, *_ = env
    body = client.get("/api/riesgo", headers=tokens["lota_alcalde"]).json()
    assert body["overall_data_class"] == "derived"
    assert all(a["data_class"] == "derived" for a in body["assessments"])
    assert "No es una evaluación ni una alerta oficial" in body["notice"]


def test_ahora_states_missing_alert_feed(env):
    client, tokens, *_ = env
    body = client.get("/api/ahora", headers=tokens["lota_alcalde"]).json()
    assert "no recibe automáticamente las alertas de SENAPRED" in body["alert_feed_note"]


def test_assistant_answers_with_sources_and_disclaimer(env):
    client, tokens, *_ = env
    body = client.post("/api/assistant", headers=tokens["lota_alcalde"], json={"question": "¿Hay escuelas en zonas de riesgo?"}).json()
    assert body["sources"]
    assert "no alertas oficiales" in body["disclaimer"] or "modelo de lenguaje" in body["disclaimer"]


def test_report_pdf(env):
    client, tokens, *_ = env
    response = client.get("/api/reports/alcalde/pdf", headers=tokens["lota_alcalde"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_public_summary_has_notice(env):
    client, *_ = env
    body = client.get(f"/api/public/{TEST_SLUG}/resumen").json()
    assert "ausencia de un nivel alto no significa ausencia de peligro" in body["notice"]


def test_manual_alert_requires_source_url(env):
    client, tokens, *_ = env
    response = client.post(
        "/api/alerts",
        headers=tokens["other_admin"],
        json={"issuer": "SENAPRED", "hazard": "tsunami", "level": "Roja", "title": "Prueba", "source_url": "no-es-url", "starts_at": "2026-10-05T10:00:00Z"},
    )
    assert response.status_code == 422


def test_new_tenant_makes_every_source_due(env):
    from app.ingest.runner import due_sources, mark_all_sources_due

    with transaction() as conn:
        saved = conn.execute(text("select key, last_attempt_at from source")).all()
        conn.execute(text("update source set last_attempt_at = now()"))
    try:
        assert due_sources() == []
        with transaction() as conn:
            mark_all_sources_due(conn)
            enabled = {r[0] for r in conn.execute(text("select key from source where enabled"))}
        assert set(due_sources()) == enabled
    finally:
        with transaction() as conn:
            for key, last in saved:
                conn.execute(text("update source set last_attempt_at = :t where key = :k"), {"t": last, "k": key})
