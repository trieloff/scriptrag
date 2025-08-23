"""Bible-related VSS operations (internal helpers).

These helpers are used by VSSService to keep the service thin and focused.
Public callers should continue to use VSSService methods.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import numpy as np

from .vss_utils import as_vec_blob, distance_to_similarity


def store_bible_embedding(
    conn: sqlite3.Connection,
    chunk_id: int,
    embedding: list[float] | np.ndarray,
    model: str,
    *,
    serializer: Callable[[list[float]], Any],
) -> None:
    """Store a bible chunk embedding and related metadata into VSS tables."""
    embedding_blob = as_vec_blob(embedding, serializer)

    conn.execute(
        """
        INSERT OR REPLACE INTO bible_chunk_embeddings
        (chunk_id, embedding_model, embedding)
        VALUES (?, ?, ?)
        """,
        (chunk_id, model, embedding_blob),
    )

    dimensions = len(embedding)
    conn.execute(
        """
        INSERT OR REPLACE INTO embedding_metadata
        (entity_type, entity_id, embedding_model, dimensions)
        VALUES ('bible_chunk', ?, ?, ?)
        """,
        (chunk_id, model, dimensions),
    )


def search_similar_bible_chunks(
    conn: sqlite3.Connection,
    query_embedding: list[float] | np.ndarray,
    model: str,
    *,
    limit: int = 10,
    script_id: int | None = None,
    serializer: Callable[[list[float]], Any],
) -> list[dict[str, Any]]:
    """Search for bible chunks similar to the given query embedding."""
    query_blob = as_vec_blob(query_embedding, serializer)

    if script_id:
        query = """
            SELECT
                bc.*,
                sb.title as bible_title,
                sb.script_id,
                be.chunk_id,
                be.distance
            FROM bible_chunk_embeddings be
            JOIN bible_chunks bc ON bc.id = be.chunk_id
            JOIN script_bibles sb ON bc.bible_id = sb.id
            WHERE be.embedding_model = ?
            AND sb.script_id = ?
            AND be.embedding MATCH ?
            ORDER BY be.distance
            LIMIT ?
        """
        params: tuple[Any, ...] = (model, script_id, query_blob, limit)
    else:
        query = """
            SELECT
                bc.*,
                sb.title as bible_title,
                sb.script_id,
                be.chunk_id,
                be.distance
            FROM bible_chunk_embeddings be
            JOIN bible_chunks bc ON bc.id = be.chunk_id
            JOIN script_bibles sb ON bc.bible_id = sb.id
            WHERE be.embedding_model = ?
            AND be.embedding MATCH ?
            ORDER BY be.distance
            LIMIT ?
        """
        params = (model, query_blob, limit)

    cursor = conn.execute(query, params)
    results: list[dict[str, Any]] = []
    for row in cursor:
        result = dict(row)
        result["similarity_score"] = distance_to_similarity(result.pop("distance", 0))
        results.append(result)
    return results
