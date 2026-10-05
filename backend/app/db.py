import json
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        json_serializer=lambda value: json.dumps(value, ensure_ascii=False, default=str),
    )


@contextmanager
def transaction() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


def get_conn() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


def rows(conn: Connection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def row(conn: Connection, sql: str, **params: Any) -> dict[str, Any] | None:
    result = conn.execute(text(sql), params).first()
    return dict(result._mapping) if result else None


def scalar(conn: Connection, sql: str, **params: Any) -> Any:
    return conn.execute(text(sql), params).scalar()


def has_extension(conn: Connection, name: str) -> bool:
    return bool(scalar(conn, "select 1 from pg_extension where extname = :n", n=name))
