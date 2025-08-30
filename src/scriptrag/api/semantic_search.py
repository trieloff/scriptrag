"""Semantic search service for scenes and bible content using embeddings.

This module exposes the public dataclasses and service and delegates heavier
operations to internal helpers to keep this file lean and maintainable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.api.semantic_generation_ops import (
    generate_bible_embeddings as _gen_bible,
)
from scriptrag.api.semantic_generation_ops import (
    generate_scene_embeddings as _gen_scenes,
)
from scriptrag.api.semantic_result_processing import (
    build_bible_results as _build_bible_results,
)
from scriptrag.api.semantic_result_processing import (
    build_scene_results as _build_scene_results,
)
from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


@dataclass
class SceneSearchResult:
    """Result from a scene similarity search."""

    scene_id: int
    script_id: int
    heading: str
    location: str | None
    content: str
    similarity_score: float
    metadata: dict[str, Any] | None = None


@dataclass
class BibleSearchResult:
    """Result from a bible content similarity search."""

    chunk_id: int
    bible_id: int
    script_id: int
    bible_title: str | None
    heading: str | None
    content: str
    similarity_score: float
    level: int | None = None
    metadata: dict[str, Any] | None = None


class SemanticSearchService:
    """Service for semantic search of scenes using vector embeddings."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        db_ops: DatabaseOperations | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        """Initialize semantic search service.

        Args:
            settings: Configuration settings
            db_ops: Database operations handler
            embedding_service: Embedding service for generating query embeddings
        """
        self.settings = settings
        self.db_ops = db_ops or DatabaseOperations(settings)
        self.embedding_service = embedding_service or EmbeddingService(settings)

    async def search_similar_scenes(
        self,
        query: str,
        script_id: int | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
        model: str | None = None,
    ) -> list[SceneSearchResult]:
        """Search for scenes similar to a query text.

        Args:
            query: Query text to search for
            script_id: Optional script ID to limit search
            top_k: Number of top results to return
            threshold: Minimum similarity threshold
            model: Embedding model to use (defaults to service default)

        Returns:
            List of scene search results sorted by similarity
        """
        model = model or self.embedding_service.default_model

        # Generate embedding for query with error handling
        try:
            query_embedding: list[
                float
            ] = await self.embedding_service.generate_embedding(query, model)
        except Exception as e:
            logger.error(
                "Failed to generate embedding for query",
                query=query[:100],  # Truncate long queries for logging
                model=model,
                error=str(e),
            )
            raise ValueError(
                f"Failed to generate embedding for search query: {e}"
            ) from e

        # Encode embedding for database storage
        try:
            query_bytes: bytes = self.embedding_service.encode_embedding_for_db(
                query_embedding
            )
        except Exception as e:
            logger.error(
                "Failed to encode embedding for database",
                model=model,
                error=str(e),
            )
            raise ValueError(
                f"Failed to encode embedding for database storage: {e}"
            ) from e

        # Search in database and process results
        with self.db_ops.transaction() as conn:
            candidates: list[dict[str, Any]] = self.db_ops.search_similar_scenes(
                conn, query_bytes, script_id, model, limit=100
            )

            results: list[SceneSearchResult] = _build_scene_results(
                candidates,
                query_embedding=query_embedding,
                embedding_service=self.embedding_service,
                threshold=threshold,
                builder=SceneSearchResult,
            )
            return results[:top_k]

    async def find_related_scenes(
        self,
        scene_id: int,
        script_id: int | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
        model: str | None = None,
    ) -> list[SceneSearchResult]:
        """Find scenes related to a given scene.

        Args:
            scene_id: ID of the scene to find related scenes for
            script_id: Optional script ID to limit search
            top_k: Number of top results to return
            threshold: Minimum similarity threshold
            model: Embedding model to use (defaults to service default)

        Returns:
            List of related scene search results sorted by similarity
        """
        model = model or self.embedding_service.default_model

        with self.db_ops.transaction() as conn:
            # Get embedding for the source scene
            source_embedding_bytes: bytes | None = self.db_ops.get_embedding(
                conn, "scene", scene_id, model
            )

            if not source_embedding_bytes:
                logger.warning(f"No embedding found for scene {scene_id}")
                return []

            # Decode source embedding
            try:
                source_embedding: list[float] = (
                    self.embedding_service.decode_embedding_from_db(
                        source_embedding_bytes
                    )
                )
            except ValueError as e:
                logger.warning(
                    "Failed to decode source scene embedding",
                    scene_id=scene_id,
                    error=str(e),
                )
                return []

            # Get scenes with embeddings
            candidates: list[dict[str, Any]] = self.db_ops.search_similar_scenes(
                conn, source_embedding_bytes, script_id, model, limit=100
            )

            results: list[SceneSearchResult] = _build_scene_results(
                candidates,
                query_embedding=source_embedding,
                embedding_service=self.embedding_service,
                threshold=threshold,
                builder=SceneSearchResult,
                skip_id=scene_id,
            )
            return results[:top_k]

    async def generate_missing_embeddings(
        self,
        script_id: int | None = None,
        model: str | None = None,
        batch_size: int = 10,
    ) -> tuple[int, int]:
        """Generate embeddings for scenes that don't have them.

        Args:
            script_id: Optional script ID to limit generation
            model: Embedding model to use (defaults to service default)
            batch_size: Number of embeddings to generate in each batch

        Returns:
            Tuple of (scenes_processed, embeddings_generated)
        """
        model = model or self.embedding_service.default_model

        with self.db_ops.transaction() as conn:
            processed, generated = await _gen_scenes(
                conn,
                db_ops=self.db_ops,
                embedding_service=self.embedding_service,
                model=model,
                script_id=script_id,
                batch_size=batch_size,
            )
        # Parity with old logging paths: log per-error inside generator not available,
        # but aggregate counts are returned here to callers/tests.
        return processed, generated

    async def search_similar_bible_content(
        self,
        query: str,
        script_id: int | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
        model: str | None = None,
    ) -> list[BibleSearchResult]:
        """Search for bible content similar to a query text.

        Args:
            query: Query text to search for
            script_id: Optional script ID to limit search
            top_k: Number of top results to return
            threshold: Minimum similarity threshold
            model: Embedding model to use (defaults to service default)

        Returns:
            List of bible search results sorted by similarity
        """
        model = model or self.embedding_service.default_model

        # Generate embedding for query with error handling
        try:
            query_embedding: list[
                float
            ] = await self.embedding_service.generate_embedding(query, model)
        except Exception as e:
            logger.error(
                "Failed to generate embedding for bible search query",
                query=query[:100],
                model=model,
                error=str(e),
            )
            raise ValueError(
                f"Failed to generate embedding for bible search: {e}"
            ) from e

        # Note: query_bytes not used in this method as we fetch all chunks
        # and calculate similarity in Python rather than using database search

        with self.db_ops.transaction() as conn:
            # Get bible chunks with embeddings from the embeddings table
            if script_id:
                query_sql = """
                    SELECT bc.*, sb.title as bible_title, sb.script_id, e.embedding
                    FROM bible_chunks bc
                    JOIN script_bibles sb ON bc.bible_id = sb.id
                    JOIN embeddings e ON e.entity_id = bc.id
                    WHERE sb.script_id = ?
                    AND e.entity_type = 'bible_chunk'
                    AND e.embedding_model = ?
                    AND e.embedding IS NOT NULL
                """
                params: tuple[Any, ...] = (script_id, model)
            else:
                query_sql = """
                    SELECT bc.*, sb.title as bible_title, sb.script_id, e.embedding
                    FROM bible_chunks bc
                    JOIN script_bibles sb ON bc.bible_id = sb.id
                    JOIN embeddings e ON e.entity_id = bc.id
                    WHERE e.entity_type = 'bible_chunk'
                    AND e.embedding_model = ?
                    AND e.embedding IS NOT NULL
                """
                params = (model,)

            cursor = conn.execute(query_sql, params)
            chunks: list[dict[str, Any]] = cursor.fetchall()

            results: list[BibleSearchResult] = _build_bible_results(
                chunks,
                query_embedding=query_embedding,
                embedding_service=self.embedding_service,
                threshold=threshold,
                builder=BibleSearchResult,
            )
            return results[:top_k]

    async def generate_bible_embeddings(
        self,
        script_id: int | None = None,
        model: str | None = None,
        batch_size: int = 10,
    ) -> tuple[int, int]:
        """Generate embeddings for bible chunks that don't have them.

        Args:
            script_id: Optional script ID to limit generation
            model: Embedding model to use (defaults to service default)
            batch_size: Number of embeddings to generate in each batch

        Returns:
            Tuple of (chunks_processed, embeddings_generated)
        """
        model = model or self.embedding_service.default_model

        with self.db_ops.transaction() as conn:
            processed, generated = await _gen_bible(
                conn,
                db_ops=self.db_ops,
                embedding_service=self.embedding_service,
                model=model,
                script_id=script_id,
                batch_size=batch_size,
            )
        return processed, generated
