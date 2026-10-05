import json
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


def test_ahora_states_which_alert_feeds_exist(env):
    client, tokens, *_ = env
    note = client.get("/api/ahora", headers=tokens["lota_alcalde"]).json()["alert_feed_note"]
    assert "Dirección Meteorológica de Chile se reciben automáticamente" in note
    assert "SENAPRED" in note and "no cuentan con un servicio público oficial" in note


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


def test_automatic_warning_applies_only_where_its_polygon_reaches(env):
    from app.ai.tools import active_alerts

    def square(lon, lat):
        return json.dumps({"type": "MultiPolygon", "coordinates": [[[[lon - 0.3, lat - 0.3], [lon + 0.3, lat - 0.3], [lon + 0.3, lat + 0.3], [lon - 0.3, lat + 0.3], [lon - 0.3, lat - 0.3]]]]})

    _, _, lota, _ = env
    with transaction() as conn:
        for external_id, geometry in (("pytest-near", square(-73.15, -37.1)), ("pytest-far", square(-109.35, -27.11)), ("pytest-none", None)):
            conn.execute(
                text(
                    """
                    insert into alert (source_key, external_id, issuer, hazard, level, title, source_url, starts_at, ends_at, area)
                    values ('dmc_cap', :e, 'DMC', 'wind', 'Aviso', :e, 'https://example.invalid', now() - interval '1 hour',
                            now() + interval '1 day', case when cast(:g as text) is null then null else st_setsrid(st_geomfromgeojson(:g), 4326) end)
                    """
                ),
                {"e": external_id, "g": geometry},
            )
    try:
        with transaction() as conn:
            titles = {a["title"] for a in active_alerts(conn, lota)}
        assert "pytest-near" in titles
        assert "pytest-far" not in titles and "pytest-none" not in titles
    finally:
        with transaction() as conn:
            conn.execute(text("delete from alert where external_id like 'pytest-%'"))


def _geotiff_near_lota() -> bytes:
    import numpy as np
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    values = np.arange(60 * 80, dtype="float32").reshape(60, 80)
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", width=80, height=60, count=1, dtype="float32", crs="EPSG:32718", transform=from_origin(668000, 5897000, 30, 30)) as dataset:
            dataset.write(values, 1)
        return memory.read()


def test_geotiff_upload_is_previewed_and_isolated(env):
    from pathlib import Path

    client, tokens, *_ = env
    response = client.post(
        "/api/uploads",
        headers=tokens["lota_admin"],
        data={"kind": "raster", "title": "pytest raster"},
        files={"file": ("pytest.tif", _geotiff_near_lota(), "image/tiff")},
    )
    assert response.status_code == 200 and response.json()["status"] == "done", response.text
    upload_id = response.json()["upload_id"]
    raster = next(r for r in client.get("/api/rasters", headers=tokens["lota_admin"]).json() if r["name"] == "pytest raster")
    assert -73.2 < raster["west"] < raster["east"] < -73.0
    preview = client.get(f"/api/rasters/{raster['id']}/preview.png", headers=tokens["lota_admin"])
    assert preview.status_code == 200 and preview.content[:4] == b"\x89PNG"
    assert client.get(f"/api/rasters/{raster['id']}/preview.png", headers=tokens["other_admin"]).status_code == 404
    with transaction() as conn:
        files = [scalar(conn, "select stored_path from upload where id = :id", id=upload_id), scalar(conn, "select preview_path from municipal_raster where id = :id", id=raster["id"])]
    assert client.delete(f"/api/uploads/{upload_id}", headers=tokens["lota_admin"]).status_code == 200
    assert not any(Path(f).exists() for f in files)


def test_contacts_inspections_and_photos(env):
    client, tokens, lota, _ = env
    admin = tokens["lota_admin"]
    with transaction() as conn:
        asset = conn.execute(text("select id, name from municipal_asset where municipality_id = :m order by id limit 1"), {"m": lota}).mappings().first()
    if asset is None:
        pytest.skip("requiere activos municipales cargados")
    uploads = []
    contacts_csv = "nombre;cargo;telefono;tipo\nPytest Encargada;Directora de Emergencia;+56 9 1111 1111;personal\nPytest Bomberos;Cuerpo de Bomberos;132;contacto\n"
    response = client.post("/api/uploads", headers=admin, data={"kind": "contacts"}, files={"file": ("contactos.csv", contacts_csv.encode(), "text/csv")})
    assert response.json()["status"] == "done" and response.json()["records"] == 2, response.text
    uploads.append(response.json()["upload_id"])
    names = {c["name"]: c["kind"] for c in client.get("/api/contacts", headers=admin).json()}
    assert names["Pytest Encargada"] == "personal" and names["Pytest Bomberos"] == "contacto"

    inspection_csv = f"fecha,activo,estado,observaciones\n2026-09-30,{asset['name'].removeprefix('DEMO ')},operativo,pytest\n"
    response = client.post("/api/uploads", headers=admin, data={"kind": "inspections"}, files={"file": ("inspecciones.csv", inspection_csv.encode(), "text/csv")})
    assert response.json()["status"] == "done", response.text
    uploads.append(response.json()["upload_id"])
    found = [i for i in client.get(f"/api/inspections?asset_id={asset['id']}", headers=admin).json() if i["notes"] == "pytest"]
    assert found and found[0]["asset_id"] == asset["id"]

    png = bytes.fromhex("89504e470d0a1a0a") + b"pytest"
    response = client.post("/api/uploads", headers=admin, data={"kind": "photo", "title": "pytest foto", "asset_id": str(asset["id"])}, files={"file": ("foto.png", png, "image/png")})
    assert response.json()["status"] == "done", response.text
    uploads.append(response.json()["upload_id"])
    photo = next(p for p in client.get(f"/api/photos?asset_id={asset['id']}", headers=admin).json() if p["caption"] == "pytest foto")
    assert client.get(f"/api/photos/{photo['id']}/file", headers=admin).content == png
    assert client.get(f"/api/photos/{photo['id']}/file", headers=tokens["other_admin"]).status_code == 404

    fake = client.post("/api/uploads", headers=admin, data={"kind": "photo"}, files={"file": ("foto.png", b"not an image", "image/png")})
    assert fake.json()["status"] == "failed"
    uploads.append(fake.json()["upload_id"])
    for upload_id in uploads:
        client.delete(f"/api/uploads/{upload_id}", headers=admin)


def test_terminology_and_branding_are_validated(env):
    client, tokens, *_ = env
    admin = tokens["lota_admin"]
    assert client.put("/api/municipality/config", headers=admin, json={"terminology": {"inventado": "x"}}).status_code == 422
    assert client.put("/api/municipality/config", headers=admin, json={"branding": {"primary_color": "rojo"}}).status_code == 422
    try:
        config = client.put("/api/municipality/config", headers=admin, json={"terminology": {"sector": "Unidad vecinal"}}).json()
        assert config["terminology"] == {"sector": "Unidad vecinal"}
    finally:
        client.put("/api/municipality/config", headers=admin, json={"terminology": {}})


def test_logo_upload_is_public_and_hides_server_path(env):
    client, tokens, *_ = env
    admin = tokens["lota_admin"]
    png = bytes.fromhex("89504e470d0a1a0a") + b"pytest-logo"
    assert client.put("/api/municipality/logo", headers=admin, files={"file": ("logo.gif", b"GIF89a", "image/gif")}).status_code == 422
    try:
        config = client.put("/api/municipality/logo", headers=admin, files={"file": ("logo.png", png, "image/png")}).json()
        assert "logo_path" not in config["branding"] and config["branding"]["logo_url"].startswith("/api/public/")
        assert client.get(config["branding"]["logo_url"]).content == png
        assert "logo_path" not in client.get("/api/me", headers=admin).json()["municipality"]["config"]["branding"]
    finally:
        assert client.delete("/api/municipality/logo", headers=admin).json()["branding"]["logo_url"] is None
