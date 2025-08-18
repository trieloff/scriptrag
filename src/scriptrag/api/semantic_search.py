"""Semantic search service for scenes and bible content using embeddings."""

from dataclasses import dataclass
from typing import Any

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
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
            query_embedding = await self.embedding_service.generate_embedding(
                query, model
            )
            query_bytes = self.embedding_service.encode_embedding_for_db(
                query_embedding
            )
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

        # Search in database
        with self.db_ops.transaction() as conn:
            # Get scenes with embeddings
            scenes = self.db_ops.search_similar_scenes(
                conn,
                query_bytes,
                script_id,
                model,
                limit=100,  # Get more candidates for similarity calculation
            )

            # Calculate similarities
            results = []
            for scene in scenes:
                # Decode scene embedding
                scene_embedding = self.embedding_service.decode_embedding_from_db(
                    scene["_embedding"]
                )

                # Calculate similarity
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, scene_embedding
                )

                if similarity >= threshold:
                    results.append(
                        SceneSearchResult(
                            scene_id=scene["id"],
                            script_id=scene["script_id"],
                            heading=scene["heading"],
                            location=scene["location"],
                            content=scene["content"],
                            similarity_score=similarity,
                            metadata=scene.get("metadata"),
                        )
                    )

            # Sort by similarity score
            results.sort(key=lambda x: x.similarity_score, reverse=True)

            # Return top k results
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
            source_embedding_bytes = self.db_ops.get_embedding(
                conn, "scene", scene_id, model
            )

            if not source_embedding_bytes:
                logger.warning(f"No embedding found for scene {scene_id}")
                return []

            # Decode source embedding
            source_embedding = self.embedding_service.decode_embedding_from_db(
                source_embedding_bytes
            )

            # Get scenes with embeddings
            scenes = self.db_ops.search_similar_scenes(
                conn,
                source_embedding_bytes,
                script_id,
                model,
                limit=100,  # Get more candidates for similarity calculation
            )

            # Calculate similarities
            results = []
            for scene in scenes:
                # Skip the source scene itself
                if scene["id"] == scene_id:
                    continue

                # Decode scene embedding
                scene_embedding = self.embedding_service.decode_embedding_from_db(
                    scene["_embedding"]
                )

                # Calculate similarity
                similarity = self.embedding_service.cosine_similarity(
                    source_embedding, scene_embedding
                )

                if similarity >= threshold:
                    results.append(
                        SceneSearchResult(
                            scene_id=scene["id"],
                            script_id=scene["script_id"],
                            heading=scene["heading"],
                            location=scene["location"],
                            content=scene["content"],
                            similarity_score=similarity,
                            metadata=scene.get("metadata"),
                        )
                    )

            # Sort by similarity score
            results.sort(key=lambda x: x.similarity_score, reverse=True)

            # Return top k results
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
        scenes_processed = 0
        embeddings_generated = 0

        with self.db_ops.transaction() as conn:
            # Find scenes without embeddings
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

            # Process in batches
            for i in range(0, len(scenes), batch_size):
                batch = scenes[i : i + batch_size]

                for scene in batch:
                    scenes_processed += 1
                    try:
                        # Generate embedding
                        embedding = (
                            await self.embedding_service.generate_scene_embedding(
                                scene["content"], scene["heading"]
                            )
                        )

                        # Save to Git LFS
                        lfs_path = self.embedding_service.save_embedding_to_lfs(
                            embedding,
                            "scene",
                            scene["id"],
                            model,
                        )

                        # Encode for database storage
                        embedding_bytes = (
                            self.embedding_service.encode_embedding_for_db(embedding)
                        )

                        # Store in database
                        self.db_ops.upsert_embedding(
                            conn,
                            entity_type="scene",
                            entity_id=scene["id"],
                            embedding_model=model,
                            embedding_data=embedding_bytes,
                            embedding_path=str(lfs_path),
                        )

                        embeddings_generated += 1
                        logger.info(
                            f"Generated embedding for scene {scene['id']}",
                            heading=scene["heading"],
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to generate embedding for scene {scene['id']}: {e}"
                        )

        return scenes_processed, embeddings_generated

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
            query_embedding = await self.embedding_service.generate_embedding(
                query, model
            )
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

        with self.db_ops.transaction() as conn:
            # Get bible chunks with embeddings from the embeddings table
            params: tuple[Any, ...]
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
                params = (script_id, model)
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
            chunks = cursor.fetchall()

            # Calculate similarities
            results = []
            for chunk in chunks:
                # Decode chunk embedding
                chunk_embedding = self.embedding_service.decode_embedding_from_db(
                    chunk["embedding"]
                )

                # Calculate similarity
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, chunk_embedding
                )

                if similarity >= threshold:
                    results.append(
                        BibleSearchResult(
                            chunk_id=chunk["id"],
                            bible_id=chunk["bible_id"],
                            script_id=chunk["script_id"],
                            bible_title=chunk["bible_title"],
                            heading=chunk.get("heading"),
                            content=chunk["content"],
                            similarity_score=similarity,
                            level=chunk.get("level"),
                            metadata=chunk.get("metadata"),
                        )
                    )

            # Sort by similarity score
            results.sort(key=lambda x: x.similarity_score, reverse=True)

            # Return top k results
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
        chunks_processed = 0
        embeddings_generated = 0

        with self.db_ops.transaction() as conn:
            # Find bible chunks without embeddings
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

            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]

                for chunk in batch:
                    chunks_processed += 1
                    try:
                        # Combine heading and content for richer embedding
                        text = chunk["content"]
                        if chunk["heading"]:
                            text = f"{chunk['heading']}\n\n{text}"

                        # Generate embedding
                        embedding = await self.embedding_service.generate_embedding(
                            text, model
                        )

                        # Save to Git LFS
                        lfs_path = self.embedding_service.save_embedding_to_lfs(
                            embedding,
                            "bible_chunk",
                            chunk["id"],
                            model,
                        )

                        # Encode for database storage
                        embedding_bytes = (
                            self.embedding_service.encode_embedding_for_db(embedding)
                        )

                        # Store in database
                        self.db_ops.upsert_embedding(
                            conn,
                            entity_type="bible_chunk",
                            entity_id=chunk["id"],
                            embedding_model=model,
                            embedding_data=embedding_bytes,
                            embedding_path=str(lfs_path),
                        )

                        embeddings_generated += 1
                        logger.info(
                            f"Generated embedding for bible chunk {chunk['id']}",
                            heading=chunk.get("heading"),
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to generate embedding for bible chunk "
                            f"{chunk['id']}: {e}"
                        )

        return chunks_processed, embeddings_generated
