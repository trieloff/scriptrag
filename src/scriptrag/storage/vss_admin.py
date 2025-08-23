"""Administrative helpers for VSS statistics."""

from __future__ import annotations

import sqlite3
from typing import Any

from scriptrag.config import get_logger

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

    # Count bible chunk embeddings by model
    cursor = conn.execute(
        "SELECT COUNT(*) as count, embedding_model "
        "FROM bible_chunk_embeddings GROUP BY embedding_model"
    )
    stats["bible_chunk_embeddings"] = {
        row["embedding_model"]: row["count"] for row in cursor
    }

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
