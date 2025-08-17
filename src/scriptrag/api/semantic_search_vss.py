"""Semantic search service using SQLite VSS for efficient vector similarity search."""

from dataclasses import dataclass
from typing import Any

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.storage.vss_service import VSSService

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


class SemanticSearchVSS:
    """Semantic search service using SQLite VSS for efficient vector search."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        vss_service: VSSService | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        """Initialize semantic search service with VSS.

        Args:
            settings: Configuration settings
            vss_service: VSS service for vector operations
            embedding_service: Embedding service for generating query embeddings
        """
        self.settings = settings
        self.vss = vss_service or VSSService(settings)
        self.embedding_service = embedding_service or EmbeddingService(settings)

    async def search_similar_scenes(
        self,
        query: str,
        script_id: int | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
        model: str | None = None,
    ) -> list[SceneSearchResult]:
        """Search for scenes similar to a query text using VSS.

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

        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query, model)

        # Search using VSS
        vss_results = self.vss.search_similar_scenes(
            query_embedding=query_embedding,
            model=model,
            limit=top_k * 2,  # Get more candidates for threshold filtering
            script_id=script_id,
        )

        # Convert to SceneSearchResult and filter by threshold
        results = []
        for scene in vss_results:
            if scene["similarity_score"] >= threshold:
                results.append(
                    SceneSearchResult(
                        scene_id=scene["id"],
                        script_id=scene["script_id"],
                        heading=scene["heading"],
                        location=scene.get("location"),
                        content=scene["content"],
                        similarity_score=scene["similarity_score"],
                        metadata=scene.get("metadata"),
                    )
                )

        # Sort by similarity score (should already be sorted by VSS)
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
        """Find scenes related to a given scene using VSS.

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

        # Get the scene's content to generate embedding
        with self.vss.get_connection() as conn:
            cursor = conn.execute(
                "SELECT heading, content FROM scenes WHERE id = ?", (scene_id,)
            )
            scene = cursor.fetchone()
            if not scene:
                logger.warning(f"Scene {scene_id} not found")
                return []

            # Generate embedding for the scene
            combined_text = f"Scene: {scene['heading']}\n\n{scene['content']}"
            scene_embedding = await self.embedding_service.generate_embedding(
                combined_text, model
            )

            # Search for similar scenes
            vss_results = self.vss.search_similar_scenes(
                query_embedding=scene_embedding,
                model=model,
                limit=top_k * 2,  # Get more candidates
                script_id=script_id,
                conn=conn,
            )

        # Convert to SceneSearchResult and filter
        results = []
        for result in vss_results:
            # Skip the source scene itself
            if result["id"] == scene_id:
                continue

            if result["similarity_score"] >= threshold:
                results.append(
                    SceneSearchResult(
                        scene_id=result["id"],
                        script_id=result["script_id"],
                        heading=result["heading"],
                        location=result.get("location"),
                        content=result["content"],
                        similarity_score=result["similarity_score"],
                        metadata=result.get("metadata"),
                    )
                )

        # Sort and return top k
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]

    async def generate_missing_embeddings(
        self,
        script_id: int | None = None,
        model: str | None = None,
        batch_size: int = 10,
    ) -> tuple[int, int]:
        """Generate embeddings for scenes that don't have them and store in VSS.

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

        with self.vss.get_connection() as conn:
            # Find scenes without embeddings in VSS
            params: tuple[Any, ...]
            if script_id:
                query = """
                    SELECT s.id, s.heading, s.content
                    FROM scenes s
                    LEFT JOIN embedding_metadata em ON em.entity_id = s.id
                        AND em.entity_type = 'scene'
                        AND em.embedding_model = ?
                    WHERE s.script_id = ? AND em.id IS NULL
                """
                params = (model, script_id)
            else:
                query = """
                    SELECT s.id, s.heading, s.content
                    FROM scenes s
                    LEFT JOIN embedding_metadata em ON em.entity_id = s.id
                        AND em.entity_type = 'scene'
                        AND em.embedding_model = ?
                    WHERE em.id IS NULL
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
                                scene["content"], scene["heading"], model
                            )
                        )

                        # Store in VSS
                        self.vss.store_scene_embedding(
                            scene["id"], embedding, model, conn
                        )

                        # Save to Git LFS (optional)
                        self.embedding_service.save_embedding_to_lfs(
                            embedding, "scene", scene["id"], model
                        )

                        embeddings_generated += 1
                        logger.info(
                            f"Generated VSS embedding for scene {scene['id']}",
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
        """Search for bible content similar to a query text using VSS.

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

        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query, model)

        # Search using VSS
        vss_results = self.vss.search_similar_bible_chunks(
            query_embedding=query_embedding,
            model=model,
            limit=top_k * 2,  # Get more candidates for threshold filtering
            script_id=script_id,
        )

        # Convert to BibleSearchResult and filter by threshold
        results = []
        for chunk in vss_results:
            if chunk["similarity_score"] >= threshold:
                results.append(
                    BibleSearchResult(
                        chunk_id=chunk["id"],
                        bible_id=chunk["bible_id"],
                        script_id=chunk["script_id"],
                        bible_title=chunk.get("bible_title"),
                        heading=chunk.get("heading"),
                        content=chunk["content"],
                        similarity_score=chunk["similarity_score"],
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
        """Generate embeddings for bible chunks and store in VSS.

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

        with self.vss.get_connection() as conn:
            # Find bible chunks without embeddings
            params: tuple[Any, ...]
            if script_id:
                query = """
                    SELECT bc.id, bc.heading, bc.content
                    FROM bible_chunks bc
                    JOIN script_bibles sb ON bc.bible_id = sb.id
                    LEFT JOIN embedding_metadata em ON em.entity_id = bc.id
                        AND em.entity_type = 'bible_chunk'
                        AND em.embedding_model = ?
                    WHERE sb.script_id = ? AND em.id IS NULL
                """
                params = (model, script_id)
            else:
                query = """
                    SELECT bc.id, bc.heading, bc.content
                    FROM bible_chunks bc
                    LEFT JOIN embedding_metadata em ON em.entity_id = bc.id
                        AND em.entity_type = 'bible_chunk'
                        AND em.embedding_model = ?
                    WHERE em.id IS NULL
                """
                params = (model,)

            cursor = conn.execute(query, params)
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

                        # Store in VSS
                        self.vss.store_bible_embedding(
                            chunk["id"], embedding, model, conn
                        )

                        # Save to Git LFS (optional)
                        self.embedding_service.save_embedding_to_lfs(
                            embedding, "bible_chunk", chunk["id"], model
                        )

                        embeddings_generated += 1
                        logger.info(
                            f"Generated VSS embedding for bible chunk {chunk['id']}",
                            heading=chunk.get("heading"),
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to generate embedding for bible chunk "
                            f"{chunk['id']}: {e}"
                        )

        return chunks_processed, embeddings_generated

    async def migrate_to_vss(self) -> tuple[int, int]:
        """Migrate existing embeddings from BLOB storage to VSS.

        Returns:
            Tuple of (scenes_migrated, bible_chunks_migrated)
        """
        logger.info("Starting migration to VSS...")
        scenes_migrated, bible_migrated = self.vss.migrate_from_blob_storage()
        logger.info(
            f"Migration complete: {scenes_migrated} scenes, "
            f"{bible_migrated} bible chunks"
        )
        return scenes_migrated, bible_migrated

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about VSS embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        return self.vss.get_embedding_stats()
