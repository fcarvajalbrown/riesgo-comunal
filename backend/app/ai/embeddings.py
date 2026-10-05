import logging

import httpx
from sqlalchemy import Connection, text

from app.config import get_settings
from app.db import has_extension, rows

log = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    settings = get_settings()
    if not settings.embeddings_enabled or not texts:
        return None
    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"} if settings.embedding_api_key else {}
    try:
        response = httpx.post(
            f"{settings.embedding_base_url.rstrip('/')}/embeddings",
            json={"model": settings.embedding_model, "input": texts},
            headers=headers,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return [item["embedding"] for item in sorted(response.json()["data"], key=lambda d: d["index"])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("embedding request failed: %s", exc)
        return None


def vector_ready(conn: Connection) -> bool:
    return get_settings().embeddings_enabled and has_extension(conn, "vector")


def embed_document(conn: Connection, document_id: int) -> int:
    if not vector_ready(conn):
        return 0
    chunks = rows(conn, "select id, content from document_chunk where document_id = :d order by chunk_index", d=document_id)
    done = 0
    for start in range(0, len(chunks), 32):
        batch = chunks[start : start + 32]
        vectors = embed_texts([c["content"] for c in batch])
        if not vectors:
            return done
        for chunk, vector in zip(batch, vectors):
            conn.execute(
                text("update document_chunk set embedding = cast(:v as vector) where id = :id"),
                {"v": "[" + ",".join(f"{x:.6f}" for x in vector) + "]", "id": chunk["id"]},
            )
            done += 1
    return done
