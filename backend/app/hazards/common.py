from typing import Any

from sqlalchemy import Connection

from app.db import row


def latest_provenance(conn: Connection, source_key: str, dataset: str) -> dict[str, Any]:
    return row(
        conn,
        """
        select p.id, p.source_time, p.ingested_at, p.url, s.attribution, s.name as source_name
        from provenance p join source s on s.key = p.source_key
        where p.source_key = :s and p.dataset = :d
        order by p.ingested_at desc limit 1
        """,
        s=source_key,
        d=dataset,
    ) or {"id": None, "source_time": None, "ingested_at": None, "url": None, "attribution": source_key, "source_name": source_key}
