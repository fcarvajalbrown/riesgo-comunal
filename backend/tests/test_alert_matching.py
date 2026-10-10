import json
from datetime import UTC, datetime, timedelta

import pytest

from app.alerts import active_alerts
from app.db import get_engine, row

NOW = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)

NEIGHBOURS_SQL = """
select a.id as declared_id, a.cut_code as declared_cut, b.id as neighbour_id
from municipality a join municipality b on a.id < b.id and st_touches(a.boundary, b.boundary)
limit 1
"""


def insert_alert(conn, declared_cut: str, declared_id: int, codes: list[str] | None) -> None:
    properties = {"cut_codes": codes} if codes is not None else {}
    conn.exec_driver_sql(
        """
        insert into alert (source_key, external_id, issuer, hazard, level, title, source_url, starts_at, area, data_class, properties)
        select 'senapred_alertas', %(e)s, 'SENAPRED', 'flood', 'Alerta Amarilla', 'Prueba', 'https://senapred.cl', %(st)s,
               st_multi(st_buffer(boundary, 0.002)), 'official_warning', cast(%(p)s as jsonb)
        from municipality where id = %(mid)s
        """,
        {"e": f"pytest-{declared_cut}-{codes is not None}", "st": NOW - timedelta(hours=1), "p": json.dumps(properties), "mid": declared_id},
    )


@pytest.fixture()
def conn():
    try:
        connection = get_engine().connect()
    except Exception:
        pytest.skip("requiere la base de datos")
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


def test_coded_alert_reaches_only_the_declared_comuna(conn):
    pair = row(conn, NEIGHBOURS_SQL)
    if pair is None:
        pytest.skip("requiere dos comunas vecinas")
    insert_alert(conn, pair["declared_cut"], pair["declared_id"], [pair["declared_cut"]])
    assert any(a["title"] == "Prueba" for a in active_alerts(conn, pair["declared_id"], NOW))
    assert not any(a["title"] == "Prueba" for a in active_alerts(conn, pair["neighbour_id"], NOW))


def test_uncoded_alert_still_matches_by_area(conn):
    pair = row(conn, NEIGHBOURS_SQL)
    if pair is None:
        pytest.skip("requiere dos comunas vecinas")
    insert_alert(conn, pair["declared_cut"], pair["declared_id"], None)
    assert any(a["title"] == "Prueba" for a in active_alerts(conn, pair["declared_id"], NOW))
