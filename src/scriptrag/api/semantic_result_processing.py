"""Helpers for processing semantic search candidates into results.

These functions are internal and used by SemanticSearchService to reduce
duplication and keep file sizes small. They deliberately avoid importing
the public dataclasses to prevent circular imports; callers pass a
``builder`` callable (usually the dataclass itself) to construct outputs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)


def build_scene_results(
    candidates: Iterable[dict[str, Any]],
    *,
    query_embedding: list[float] | Any,
    embedding_service: Any,
    threshold: float,
    builder: Callable[..., Any],
    skip_id: int | None = None,
) -> list[Any]:
    """Convert scene candidates into filtered, sorted results.

    - Decodes candidate embeddings
    - Computes cosine similarity to ``query_embedding``
    - Applies ``threshold`` and optional ``skip_id``
    - Constructs results using ``builder`` and sorts by similarity desc
    """
    results: list[Any] = []

    for scene in candidates:
        if skip_id is not None and scene.get("id") == skip_id:
            continue

        try:
            scene_embedding = embedding_service.decode_embedding_from_db(
                scene["_embedding"]
            )
        except (ValueError, KeyError) as e:
            # Skip scenes with corrupted or missing embeddings
            logger.warning(
                "Skipping scene with corrupted or missing embedding",
                scene_id=scene.get("id"),
                script_id=scene.get("script_id"),
                heading=scene.get("heading"),
                error_type=type(e).__name__,
                error=str(e),
            )
            continue

        similarity = embedding_service.cosine_similarity(
            query_embedding, scene_embedding
        )
        if similarity >= threshold:
            results.append(
                builder(
                    scene_id=scene["id"],
                    script_id=scene["script_id"],
                    heading=scene["heading"],
                    location=scene.get("location"),
                    content=scene["content"],
                    similarity_score=similarity,
                    metadata=scene.get("metadata"),
                )
            )

    # Sort by similarity_score - handle both dict and object results
    try:
        # Try attribute access first (for dataclass/object results)
        results.sort(key=lambda x: x.similarity_score, reverse=True)
    except AttributeError:
        # Fall back to dict access
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results


def build_bible_results(
    chunks: Iterable[dict[str, Any]],
    *,
    query_embedding: list[float] | Any,
    embedding_service: Any,
    threshold: float,
    builder: Callable[..., Any],
) -> list[Any]:
    """Convert bible chunk candidates into filtered, sorted results."""
    results: list[Any] = []
    for chunk in chunks:
        try:
            chunk_embedding = embedding_service.decode_embedding_from_db(
                chunk["embedding"]
            )
        except (ValueError, KeyError) as e:
            # Skip chunks with corrupted or missing embeddings
            logger.warning(
                "Skipping bible chunk with corrupted or missing embedding",
                chunk_id=chunk.get("id"),
                bible_id=chunk.get("bible_id"),
                script_id=chunk.get("script_id"),
                bible_title=chunk.get("bible_title"),
                heading=chunk.get("heading"),
                error_type=type(e).__name__,
                error=str(e),
            )
            continue

        similarity = embedding_service.cosine_similarity(
            query_embedding, chunk_embedding
        )
        if similarity >= threshold:
            results.append(
                builder(
                    chunk_id=chunk["id"],
                    bible_id=chunk["bible_id"],
                    script_id=chunk["script_id"],
                    bible_title=chunk.get("bible_title"),
                    heading=chunk.get("heading"),
                    content=chunk["content"],
                    similarity_score=similarity,
                    level=chunk.get("level"),
                    metadata=chunk.get("metadata"),
                )
            )

    # Sort by similarity_score - handle both dict and object results
    try:
        # Try attribute access first (for dataclass/object results)
        results.sort(key=lambda x: x.similarity_score, reverse=True)
    except AttributeError:
        # Fall back to dict access
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results
