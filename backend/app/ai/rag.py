import re
from typing import Any

from sqlalchemy import Connection

from app.ai.embeddings import embed_texts, vector_ready
from app.db import rows

STOPWORDS = {"que", "qué", "cual", "cuál", "como", "cómo", "dice", "sobre", "del", "las", "los", "una", "para", "por", "con", "plan", "el", "la", "de", "en", "y", "a"}


def search_documents(conn: Connection, municipality_id: int, query: str, limit: int = 5) -> list[dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}
    for hit in _fulltext(conn, municipality_id, query, limit):
        results[hit["chunk_id"]] = hit
    if vector_ready(conn):
        for hit in _vector(conn, municipality_id, query, limit):
            results.setdefault(hit["chunk_id"], hit)
    ranked = sorted(results.values(), key=lambda h: h["score"], reverse=True)[:limit]
    for hit in ranked:
        hit["data_class"] = "municipal"
        hit["source"] = f"Documento municipal: {hit['title']}" + (f", página {hit['page']}" if hit["page"] else "")
    return ranked


def _fulltext(conn, municipality_id, query, limit):
    hits = rows(
        conn,
        """
        select c.id as chunk_id, c.content, c.page, d.id as document_id, d.title, d.is_demo, d.created_at,
               ts_rank_cd(c.tsv, q) as score
        from document_chunk c join document d on d.id = c.document_id,
             websearch_to_tsquery('spanish', :q) q
        where c.municipality_id = :m and c.tsv @@ q
        order by score desc limit :n
        """,
        m=municipality_id,
        q=query,
        n=limit,
    )
    if hits:
        return hits
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 3 and t not in STOPWORDS]
    if not terms:
        return []
    return rows(
        conn,
        """
        select c.id as chunk_id, c.content, c.page, d.id as document_id, d.title, d.is_demo, d.created_at,
               ts_rank_cd(c.tsv, q) as score
        from document_chunk c join document d on d.id = c.document_id,
             to_tsquery('spanish', :q) q
        where c.municipality_id = :m and c.tsv @@ q
        order by score desc limit :n
        """,
        m=municipality_id,
        q=" | ".join(terms),
        n=limit,
    )


def _vector(conn, municipality_id, query, limit):
    vectors = embed_texts([query])
    if not vectors:
        return []
    literal = "[" + ",".join(f"{x:.6f}" for x in vectors[0]) + "]"
    return rows(
        conn,
        """
        select c.id as chunk_id, c.content, c.page, d.id as document_id, d.title, d.is_demo, d.created_at,
               1 - (c.embedding <=> cast(:v as vector)) as score
        from document_chunk c join document d on d.id = c.document_id
        where c.municipality_id = :m and c.embedding is not null
        order by c.embedding <=> cast(:v as vector) limit :n
        """,
        m=municipality_id,
        v=literal,
        n=limit,
    )
