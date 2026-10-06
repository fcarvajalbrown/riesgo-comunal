import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from app.alerts import active_alerts
from app.db import row, rows, scalar

WILDFIRE_CLASS = {1: "Muy baja", 2: "Baja", 3: "Media", 4: "Alta", 5: "Muy alta"}
MAX_DISTANCE_M = 5000
CODE_LIKE = re.compile(r"[0-9]{3,}[A-Z]{1,4}[0-9]*")


def meeting_label(name: str | None) -> str:
    if not name or CODE_LIKE.fullmatch(name):
        return f"código {name}" if name else "sin nombre"
    return name


class OutsideComuna(ValueError):
    pass


def _point(lon: float, lat: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


def place_report(conn: Connection, municipality_id: int, lon: float, lat: float) -> dict[str, Any]:
    point = _point(lon, lat)
    near = scalar(
        conn,
        "select st_dwithin(cast(:p as geometry)::geography, boundary::geography, :d) from municipality where id = :m",
        p=point,
        d=MAX_DISTANCE_M,
        m=municipality_id,
    )
    if not near:
        raise OutsideComuna("El lugar está fuera de la comuna.")

    items: list[dict[str, Any]] = []
    tsunami = row(
        conn,
        """
        select f.provenance_id, p.source_time, p.acquired_at
        from feature f left join provenance p on p.id = f.provenance_id
        where f.dataset = 'tsunami_evacuation_area' and st_intersects(f.geom, cast(:p as geometry)) limit 1
        """,
        p=point,
    )
    meeting = row(
        conn,
        """
        select f.name, st_x(f.geom) as lon, st_y(f.geom) as lat, f.provenance_id,
               st_distance(f.geom::geography, cast(:p as geometry)::geography) as meters
        from feature f
        where f.dataset = 'tsunami_meeting_point' and st_dwithin(f.geom::geography, cast(:p as geometry)::geography, 6000)
        order by f.geom <-> cast(:p as geometry) limit 1
        """,
        p=point,
    )
    if tsunami:
        text = "Este lugar está dentro del área que se debe evacuar ante un tsunami."
        if meeting:
            text += f" El punto de encuentro más cercano ({meeting_label(meeting['name'])}) está a unos {round(meeting['meters'] / 50) * 50:.0f} m en línea recta."
        items.append(
            {
                "hazard": "tsunami",
                "status": "dentro",
                "text": text,
                "action": "Si un sismo le impide mantenerse en pie, evacúe de inmediato hacia la zona segura sin esperar alerta.",
                "data_class": "official",
                "source": "SENAPRED, amenaza por tsunami",
                "provenance_id": tsunami["provenance_id"],
                "meeting_point": meeting,
            }
        )
    elif meeting and meeting["meters"] < 3000:
        items.append(
            {
                "hazard": "tsunami",
                "status": "fuera",
                "text": "Este lugar está fuera del área de evacuación por tsunami publicada por SENAPRED.",
                "action": None,
                "data_class": "official",
                "source": "SENAPRED, amenaza por tsunami",
                "provenance_id": meeting["provenance_id"],
                "meeting_point": None,
            }
        )

    wildfire = row(
        conn,
        """
        select (f.properties->>'clase')::int as clase, f.provenance_id
        from feature f where f.dataset = 'wildfire_hazard' and st_intersects(f.geom, cast(:p as geometry))
        order by (f.properties->>'clase')::int desc limit 1
        """,
        p=point,
    )
    if wildfire and wildfire["clase"] in WILDFIRE_CLASS:
        label = WILDFIRE_CLASS[wildfire["clase"]]
        items.append(
            {
                "hazard": "wildfire",
                "status": label,
                "text": f"La recurrencia de incendios forestales en este sector es {label.lower()} (incendios registrados 2020-2024).",
                "action": "Mantenga limpio de pasto seco y basura el entorno de su vivienda y no haga quemas." if wildfire["clase"] >= 3 else None,
                "data_class": "official",
                "source": "SENAPRED con datos de CONAF",
                "provenance_id": wildfire["provenance_id"],
                "meeting_point": None,
            }
        )

    now = datetime.now(UTC)
    warnings = rows(
        conn,
        """
        select a.level, a.title, a.starts_at, a.ends_at, a.source_url, a.provenance_id
        from alert a
        where a.source_key = 'dmc_cap' and (a.ends_at is null or a.ends_at > :now) and st_intersects(a.area, cast(:p as geometry))
        order by a.starts_at
        """,
        p=point,
        now=now,
    )
    municipal_alerts = [a for a in active_alerts(conn, municipality_id, now) if a["source_key"] is None]
    return {
        "lon": lon,
        "lat": lat,
        "items": items,
        "warnings": warnings,
        "alerts": municipal_alerts,
        "checked_at": now,
        "notice": (
            "Información de referencia a partir de mapas y boletines oficiales. No reemplaza las instrucciones de SENAPRED ni de la autoridad. "
            "Que no aparezca una amenaza no significa que no exista peligro."
        ),
    }
