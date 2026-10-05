import csv
import io
import json
import random
import secrets
from datetime import date

from fpdf import FPDF

from app.auth import hash_password
from app.db import rows, scalar, transaction
from app.uploads.service import handle_upload

DEMO_SEED = 20261005
DEMO_ROLES = ("MUNICIPAL_ADMIN", "ALCALDE", "EMERGENCIAS", "SECPLAN", "COMUNICACIONES")

DEMO_DOCUMENT = [
    (
        "DOCUMENTO DE EJEMPLO (DEMO)",
        "Este documento es un texto de ejemplo generado para demostrar la búsqueda en documentos municipales. "
        "No es un plan de emergencia real de ninguna municipalidad y no debe usarse para tomar decisiones.",
    ),
    (
        "1. Albergues (DEMO)",
        "En caso de evacuación, los albergues de ejemplo DEMO se activan por orden de la Dirección de Emergencias. "
        "Cada albergue debe contar con un encargado, registro de personas acogidas, agua potable y un generador. "
        "La apertura se informa a la Delegación Presidencial y a SENAPRED regional.",
    ),
    (
        "2. Inundaciones y anegamientos (DEMO)",
        "Antes del invierno se revisan los sumideros y canales de los puntos críticos de inundación. "
        "Ante lluvias intensas, las cuadrillas municipales recorren primero los puntos críticos con antecedentes de anegamiento "
        "en los últimos años y despejan rejillas y canaletas. Las viviendas afectadas se registran en la ficha FIBE.",
    ),
    (
        "3. Incendios forestales (DEMO)",
        "En temporada de incendios se coordinan cortafuegos con CONAF y bomberos en los sectores de interfaz urbano-forestal. "
        "Se prioriza la limpieza de microbasurales y pastizales cercanos a viviendas y establecimientos educacionales.",
    ),
    (
        "4. Tsunami (DEMO)",
        "Ante un sismo que dificulte mantenerse en pie, la población del borde costero evacúa hacia los puntos de encuentro "
        "sin esperar instrucciones. El municipio apoya la evacuación de establecimientos educacionales ubicados en el área a evacuar.",
    ),
    (
        "5. Comunicaciones (DEMO)",
        "Toda comunicación pública sobre emergencias se basa en información oficial verificada y cita la fuente. "
        "Las publicaciones son aprobadas por la autoridad antes de difundirse.",
    ),
]


def _demo_pdf() -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    for title, body in DEMO_DOCUMENT:
        pdf.set_font("Helvetica", "B", 13)
        pdf.multi_cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 5, body, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    return bytes(pdf.output())


def _points(conn, municipality_id: int, count: int, seed: int) -> list[tuple[float, float]]:
    return [
        (r["lon"], r["lat"])
        for r in rows(
            conn,
            """
            select st_x(g) as lon, st_y(g) as lat
            from (select (st_dump(st_generatepoints(boundary, :n, :seed))).geom as g from municipality where id = :m) p
            """,
            n=count,
            seed=seed,
            m=municipality_id,
        )
    ]


def seed_demo(tenant_slug: str) -> dict:
    rng = random.Random(DEMO_SEED)
    with transaction() as conn:
        municipality_id = scalar(conn, "select id from municipality where slug = :s", s=tenant_slug)
        if not municipality_id:
            raise SystemExit(f"comuna no encontrada: {tenant_slug}")
        if scalar(conn, "select 1 from upload where municipality_id = :m and is_demo limit 1", m=municipality_id):
            return {"status": "already_seeded"}

        users = {}
        for role in DEMO_ROLES:
            email = f"{role.lower().replace('_', '.')}@demo.{tenant_slug}.cl"
            password = secrets.token_urlsafe(9)
            scalar(
                conn,
                """
                insert into app_user (municipality_id, email, name, password_hash, role)
                values (:m, :e, :n, :p, :r)
                on conflict (email) do update set password_hash = excluded.password_hash
                returning id
                """,
                m=municipality_id,
                e=email,
                n=f"Usuario DEMO {role.title().replace('_', ' ')}",
                p=hash_password(password),
                r=role,
            )
            users[email] = password
        admin_id = scalar(conn, "select id from app_user where role = 'MUNICIPAL_ADMIN' and municipality_id = :m order by id limit 1", m=municipality_id)

        points = _points(conn, municipality_id, 60, DEMO_SEED)
        sector_names = [r["name"] for r in rows(conn, "select name from sector where municipality_id = :m and kind = 'analysis_cell' order by id", m=municipality_id)]

        assets = io.StringIO()
        writer = csv.writer(assets)
        writer.writerow(["nombre", "categoria", "latitud", "longitud", "capacidad"])
        plan = [("Albergue", "albergue", 4), ("Generador", "generador", 3), ("Punto crítico de inundación", "punto critico inundacion", 8), ("Estanque de agua", "estanque de agua", 2)]
        cursor = 0
        for label, category, count in plan:
            for i in range(1, count + 1):
                lon, lat = points[cursor]
                cursor += 1
                capacity = rng.choice([40, 60, 80, 120]) if category == "albergue" else ""
                writer.writerow([f"DEMO {label} {i}", category, f"{lat:.6f}", f"{lon:.6f}", capacity])

        incidents = []
        hazards = ["inundacion", "anegamiento", "anegamiento", "incendio", "remocion", "temporal"]
        flood_points = points[4 + 3 : 4 + 3 + 8]
        for i in range(36):
            hazard = rng.choice(hazards)
            if hazard in ("inundacion", "anegamiento"):
                lon, lat = rng.choice(flood_points)
                lon += rng.uniform(-0.002, 0.002)
                lat += rng.uniform(-0.002, 0.002)
                month = rng.choice([5, 6, 6, 7, 7, 8])
            else:
                lon, lat = points[cursor % len(points)]
                cursor += 1
                month = rng.choice([1, 2, 12]) if hazard == "incendio" else rng.randint(1, 12)
            occurred = date(rng.randint(2014, 2025), month, rng.randint(1, 28))
            incidents.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "fecha": occurred.isoformat(),
                        "amenaza": hazard,
                        "sector": rng.choice(sector_names) if sector_names else None,
                        "descripcion": f"Incidente de ejemplo DEMO {i + 1}",
                        "afectados": rng.choice([0, 0, 2, 5, 8, 12]),
                    },
                }
            )
        uploads = [
            handle_upload(conn, municipality_id, admin_id, "assets", "demo_activos.csv", "text/csv", assets.getvalue().encode(), None, None, True),
            handle_upload(
                conn,
                municipality_id,
                admin_id,
                "incidents",
                "demo_incidentes.geojson",
                "application/geo+json",
                json.dumps({"type": "FeatureCollection", "features": incidents}).encode(),
                None,
                None,
                True,
            ),
            handle_upload(conn, municipality_id, admin_id, "document", "demo_plan_emergencia.pdf", "application/pdf", _demo_pdf(), None, "Plan de emergencia de ejemplo", True),
        ]
    return {"status": "seeded", "users": users, "uploads": uploads}
