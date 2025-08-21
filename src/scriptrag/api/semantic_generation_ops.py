"""Helpers for batch embedding generation and persistence.

These functions encapsulate the SQL selection and persistence logic used by
SemanticSearchService for generating missing embeddings.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from scriptrag.config import get_logger

from .database_operations import DatabaseOperations

logger = get_logger(__name__)


async def generate_scene_embeddings(
    conn: sqlite3.Connection,
    *,
    db_ops: DatabaseOperations,
    embedding_service: Any,
    model: str,
    script_id: int | None,
    batch_size: int,
) -> tuple[int, int]:
    """Generate embeddings for scenes without existing embeddings in DB."""
    params: tuple[Any, ...]
    if script_id:
        query = """
            SELECT s.id, s.heading, s.content
            FROM scenes s
            LEFT JOIN embeddings e ON e.entity_id = s.id
                AND e.entity_type = 'scene'
                AND e.embedding_model = ?
            WHERE s.script_id = ? AND e.id IS NULL
        """
        params = (model, script_id)
    else:
        query = """
            SELECT s.id, s.heading, s.content
            FROM scenes s
            LEFT JOIN embeddings e ON e.entity_id = s.id
                AND e.entity_type = 'scene'
                AND e.embedding_model = ?
            WHERE e.id IS NULL
        """
        params = (model,)

    cursor = conn.execute(query, params)
    scenes = cursor.fetchall()

    scenes_processed = 0
    embeddings_generated = 0

    for i in range(0, len(scenes), batch_size):
        batch = scenes[i : i + batch_size]
        for scene in batch:
            scenes_processed += 1
            try:
                embedding = await embedding_service.generate_scene_embedding(
                    scene["content"], scene["heading"]
                )
                lfs_path = embedding_service.save_embedding_to_lfs(
                    embedding, "scene", scene["id"], model
                )
                embedding_bytes = embedding_service.encode_embedding_for_db(embedding)
                db_ops.upsert_embedding(
                    conn,
                    entity_type="scene",
                    entity_id=scene["id"],
                    embedding_model=model,
                    embedding_data=embedding_bytes,
                    embedding_path=str(lfs_path),
                )
                embeddings_generated += 1
            except Exception as e:
                logger.error(
                    "Failed to generate scene embedding",
                    scene_id=scene["id"],
                    model=model,
                    error=str(e),
                )
                # Continue processing remaining items
                continue

    return scenes_processed, embeddings_generated


async def generate_bible_embeddings(
    conn: sqlite3.Connection,
    *,
    db_ops: DatabaseOperations,
    embedding_service: Any,
    model: str,
    script_id: int | None,
    batch_size: int,
) -> tuple[int, int]:
    """Generate embeddings for bible chunks without existing embeddings in DB."""
    params: tuple[Any, ...]
    if script_id:
        query_sql = """
            SELECT bc.id, bc.heading, bc.content
            FROM bible_chunks bc
            JOIN script_bibles sb ON bc.bible_id = sb.id
            LEFT JOIN embeddings e ON e.entity_id = bc.id
                AND e.entity_type = 'bible_chunk'
                AND e.embedding_model = ?
            WHERE sb.script_id = ? AND e.id IS NULL
        """
        params = (model, script_id)
    else:
        query_sql = """
            SELECT bc.id, bc.heading, bc.content
            FROM bible_chunks bc
            LEFT JOIN embeddings e ON e.entity_id = bc.id
                AND e.entity_type = 'bible_chunk'
                AND e.embedding_model = ?
            WHERE e.id IS NULL
        """
        params = (model,)

    cursor = conn.execute(query_sql, params)
    chunks = cursor.fetchall()

    chunks_processed = 0
    embeddings_generated = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        for chunk in batch:
            chunks_processed += 1
            try:
                text = chunk["content"]
                if chunk["heading"]:
                    text = f"{chunk['heading']}\n\n{text}"
                embedding = await embedding_service.generate_embedding(text, model)
                lfs_path = embedding_service.save_embedding_to_lfs(
                    embedding, "bible_chunk", chunk["id"], model
                )
                embedding_bytes = embedding_service.encode_embedding_for_db(embedding)
                db_ops.upsert_embedding(
                    conn,
                    entity_type="bible_chunk",
                    entity_id=chunk["id"],
                    embedding_model=model,
                    embedding_data=embedding_bytes,
                    embedding_path=str(lfs_path),
                )
                embeddings_generated += 1
            except Exception as e:
                logger.error(
                    "Failed to generate bible chunk embedding",
                    chunk_id=chunk["id"],
                    model=model,
                    error=str(e),
                )
                # Continue processing remaining items
                continue

    return chunks_processed, embeddings_generated
