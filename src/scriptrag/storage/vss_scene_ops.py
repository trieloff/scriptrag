"""Scene-related VSS operations (internal helpers).

These helpers are used by VSSService to keep the service thin and focused.
Public callers should continue to use VSSService methods.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import numpy as np

from .vss_utils import as_vec_blob, distance_to_similarity


def store_scene_embedding(
    conn: sqlite3.Connection,
    scene_id: int,
    embedding: list[float] | np.ndarray,
    model: str,
    *,
    serializer: Callable[[list[float]], Any],
) -> None:
    """Store a scene embedding and related metadata into VSS tables."""
    embedding_blob = as_vec_blob(embedding, serializer)

    conn.execute(
        """
        INSERT OR REPLACE INTO scene_embeddings
        (scene_id, embedding_model, embedding)
        VALUES (?, ?, ?)
        """,
        (scene_id, model, embedding_blob),
    )

    dimensions = len(embedding)
    conn.execute(
        """
        INSERT OR REPLACE INTO embedding_metadata
        (entity_type, entity_id, embedding_model, dimensions)
        VALUES ('scene', ?, ?, ?)
        """,
        (scene_id, model, dimensions),
    )


def search_similar_scenes(
    conn: sqlite3.Connection,
    query_embedding: list[float] | np.ndarray,
    model: str,
    *,
    limit: int = 10,
    script_id: int | None = None,
    serializer: Callable[[list[float]], Any],
) -> list[dict[str, Any]]:
    """Search for scenes similar to the given query embedding."""
    query_blob = as_vec_blob(query_embedding, serializer)

    if script_id:
        query = """
            SELECT
                s.*,
                se.scene_id,
                se.distance
            FROM scene_embeddings se
            JOIN scenes s ON s.id = se.scene_id
            WHERE se.embedding_model = ?
            AND s.script_id = ?
            AND se.embedding MATCH ?
            ORDER BY se.distance
            LIMIT ?
        """
        params: tuple[Any, ...] = (model, script_id, query_blob, limit)
    else:
        query = """
            SELECT
                s.*,
                se.scene_id,
                se.distance
            FROM scene_embeddings se
            JOIN scenes s ON s.id = se.scene_id
            WHERE se.embedding_model = ?
            AND se.embedding MATCH ?
            ORDER BY se.distance
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
