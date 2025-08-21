"""Administrative helpers for VSS statistics and migrations."""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Callable
from typing import Any

from scriptrag.config import get_logger

from .vss_bible_ops import store_bible_embedding as store_bible
from .vss_scene_ops import store_scene_embedding as store_scene

logger = get_logger(__name__)


def get_embedding_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Collect summary statistics about embeddings stored in VSS tables."""
    stats: dict[str, Any] = {}

    # Count scene embeddings by model
    cursor = conn.execute(
        "SELECT COUNT(*) as count, embedding_model "
        "FROM scene_embeddings GROUP BY embedding_model"
    )
    stats["scene_embeddings"] = {row["embedding_model"]: row["count"] for row in cursor}

    # Count bible embeddings by model
    cursor = conn.execute(
        "SELECT COUNT(*) as count, embedding_model "
        "FROM bible_embeddings GROUP BY embedding_model"
    )
    stats["bible_embeddings"] = {row["embedding_model"]: row["count"] for row in cursor}

    # Metadata stats by entity type
    cursor = conn.execute(
        """
        SELECT entity_type, COUNT(*) as count, AVG(dimensions) as avg_dims
        FROM embedding_metadata
        GROUP BY entity_type
        """
    )
    stats["metadata"] = {
        row["entity_type"]: {"count": row["count"], "avg_dimensions": row["avg_dims"]}
        for row in cursor
    }

    return stats


def migrate_from_blob_storage(
    conn: sqlite3.Connection,
    *,
    serializer: Callable[[list[float]], Any],
    store_scene_fn: Callable[[sqlite3.Connection, int, list[float], str, Any], None]
    | None = None,
    store_bible_fn: Callable[[sqlite3.Connection, int, list[float], str, Any], None]
    | None = None,
) -> tuple[int, int]:
    """Migrate embeddings from legacy BLOB table into VSS tables.

    Returns a tuple of (scenes_migrated, bible_chunks_migrated).
    """
    scenes_migrated = 0
    bible_migrated = 0

    # Default to direct VSS ops if no override provided
    if store_scene_fn is None:

        def store_scene_fn(
            conn_: sqlite3.Connection,
            entity_id: int,
            values: list[float],
            model: str,
            serializer_: Any,
        ) -> None:
            return store_scene(conn_, entity_id, values, model, serializer=serializer_)

    if store_bible_fn is None:

        def store_bible_fn(
            conn_: sqlite3.Connection,
            entity_id: int,
            values: list[float],
            model: str,
            serializer_: Any,
        ) -> None:
            return store_bible(conn_, entity_id, values, model, serializer=serializer_)

    # Check if old table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings_old'"
    )
    if not cursor.fetchone():
        return (0, 0)

    # Migrate scene embeddings
    cursor = conn.execute(
        """
        SELECT entity_id, embedding_model, embedding
        FROM embeddings_old
        WHERE entity_type = 'scene' AND embedding IS NOT NULL
        """
    )

    for row in cursor:
        try:
            data = row["embedding"]
            dimension = struct.unpack("<I", data[:4])[0]
            format_str = f"<{dimension}f"
            values = struct.unpack(format_str, data[4 : 4 + dimension * 4])
            store_scene_fn(
                conn,
                row["entity_id"],
                list(values),
                row["embedding_model"],
                serializer,
            )
            scenes_migrated += 1
        except Exception as e:
            logger.warning(
                "Skipping corrupted scene embedding during migration",
                extra={
                    "entity_id": dict(row).get("entity_id"),
                    "model": dict(row).get("embedding_model"),
                    "error": str(e),
                },
            )

    # Migrate bible chunk embeddings
    cursor = conn.execute(
        """
        SELECT entity_id, embedding_model, embedding
        FROM embeddings_old
        WHERE entity_type = 'bible_chunk' AND embedding IS NOT NULL
        """
    )

    for row in cursor:
        try:
            data = row["embedding"]
            dimension = struct.unpack("<I", data[:4])[0]
            format_str = f"<{dimension}f"
            values = struct.unpack(format_str, data[4 : 4 + dimension * 4])
            store_bible_fn(
                conn,
                row["entity_id"],
                list(values),
                row["embedding_model"],
                serializer,
            )
            bible_migrated += 1
        except Exception as e:
            logger.warning(
                "Skipping corrupted bible embedding during migration",
                extra={
                    "entity_id": dict(row).get("entity_id"),
                    "model": dict(row).get("embedding_model"),
                    "error": str(e),
                },
            )

    return (scenes_migrated, bible_migrated)
