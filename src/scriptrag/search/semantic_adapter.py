"""Adapter to connect SemanticSearchService to SearchEngine."""

from __future__ import annotations

import struct

import numpy as np

from scriptrag.api.semantic_search import SemanticSearchService
from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.search.models import BibleSearchResult, SearchQuery, SearchResult

logger = get_logger(__name__)


class SemanticSearchAdapter:
    """Adapter to bridge SemanticSearchService with SearchEngine.

    This adapter allows the new pre-indexed semantic search to be used
    in place of the old on-demand VectorSearchEngine while maintaining
    the same interface.
    """

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize the semantic search adapter.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.semantic_service = SemanticSearchService(settings)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the semantic search service if needed."""
        if not self._initialized:
            # The semantic service is already initialized via __init__
            self._initialized = True
            logger.info("Initialized semantic search adapter")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self._initialized = False

    async def enhance_results_with_semantic_search(
        self,
        query: SearchQuery,
        existing_results: list[SearchResult],
        limit: int = 5,
    ) -> tuple[list[SearchResult], list[BibleSearchResult]]:
        """Enhance search results with semantic search.

        This method replaces the old vector search enhancement with the new
        pre-indexed semantic search.

        Args:
            query: Search query
            existing_results: Results from SQL search
            limit: Maximum number of semantic results to add

        Returns:
            Tuple of (enhanced scene results, bible results)
        """
        # Extract query text for semantic search
        query_text = query.dialogue or query.action or query.text_query or ""

        if not query_text:
            # No text to search with
            return existing_results, []

        try:
            # Get semantic search results for scenes
            scene_results = await self.semantic_service.search_similar_scenes(
                query=query_text,
                script_id=None,  # Search across all scripts
                top_k=limit * 2,  # Get more to allow for deduplication
                threshold=self.settings.search_vector_similarity_threshold,
            )

            # Get semantic search results for bible content if needed
            bible_results = []
            if query.include_bible or query.only_bible:
                bible_search_results = (
                    await self.semantic_service.search_similar_bible_content(
                        query=query_text,
                        script_id=None,
                        top_k=limit,
                        threshold=self.settings.search_vector_similarity_threshold,
                    )
                )

                # Convert to SearchEngine's BibleSearchResult format
                for br in bible_search_results:
                    bible_result = BibleSearchResult(
                        script_id=br.script_id,
                        script_title=br.bible_title or "Unknown",  # Use bible_title
                        bible_id=br.bible_id,
                        bible_title=br.bible_title,
                        chunk_id=br.chunk_id,
                        chunk_heading=br.heading,  # br.heading, not br.chunk_heading
                        chunk_level=br.level or 0,  # br.level, not br.chunk_level
                        chunk_content=br.content,  # br.content, not br.chunk_content
                        match_type="semantic",
                        relevance_score=br.similarity_score,
                    )
                    bible_results.append(bible_result)

            # Create a set of existing scene IDs for deduplication
            existing_scene_ids = {r.scene_id for r in existing_results}

            # Add non-duplicate semantic results
            added_count = 0
            combined_results = list(existing_results)

            for scene_result in scene_results:
                if scene_result.scene_id not in existing_scene_ids:
                    # Convert to SearchEngine's SearchResult format
                    # Note: semantic search results don't include script metadata
                    # We'll need to fetch script info separately if needed
                    search_result = SearchResult(
                        script_id=scene_result.script_id,
                        script_title="Unknown",  # Would need separate query to get this
                        script_author="Unknown",  # Need separate query
                        scene_id=scene_result.scene_id,
                        scene_number=0,  # Not available in semantic result
                        scene_heading=scene_result.heading,  # Use .heading
                        scene_location=scene_result.location,  # Use .location
                        scene_time=None,  # Not available in current semantic result
                        scene_content=scene_result.content,  # Use .content
                        season=None,  # Metadata not included in semantic result
                        episode=None,  # Metadata not included in semantic result
                        match_type="semantic",
                        relevance_score=scene_result.similarity_score,
                    )
                    combined_results.append(search_result)
                    existing_scene_ids.add(scene_result.scene_id)
                    added_count += 1
                    if added_count >= limit:
                        break

            logger.info(
                f"Added {added_count} semantic scene results "
                f"and {len(bible_results)} bible results"
            )
            return combined_results, bible_results

        except Exception as e:
            logger.error(f"Failed to enhance with semantic search: {e}")
            # Return original results on error
            return existing_results, []

    async def ensure_embeddings_generated(
        self,
        script_id: int | None = None,
        force_regenerate: bool = False,
    ) -> tuple[int, int]:
        """Ensure embeddings are generated for indexed content.

        Args:
            script_id: Optional script ID to limit generation
            force_regenerate: Whether to regenerate existing embeddings

        Returns:
            Tuple of (scenes_generated, bible_chunks_generated)
        """
        scenes_generated = 0
        bible_generated = 0

        try:
            # Generate missing scene embeddings
            if not force_regenerate:
                (
                    scenes_generated,
                    _,
                ) = await self.semantic_service.generate_missing_embeddings(
                    script_id=script_id,
                    batch_size=10,
                )
            else:
                # For force regenerate, we would need to clear existing embeddings first
                # This is not implemented in the current service
                logger.warning("Force regenerate not yet implemented")
                (
                    scenes_generated,
                    _,
                ) = await self.semantic_service.generate_missing_embeddings(
                    script_id=script_id,
                    batch_size=10,
                )

            # Generate missing bible embeddings
            bible_generated, _ = await self.semantic_service.generate_bible_embeddings(
                script_id=script_id,
                batch_size=10,
            )

            logger.info(
                f"Generated embeddings: {scenes_generated} scenes, "
                f"{bible_generated} bible chunks"
            )

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")

        return scenes_generated, bible_generated

    def decode_embedding_blob(self, blob: bytes) -> np.ndarray:
        """Decode embedding blob from database.

        Compatibility method for code that expects the old interface.

        Args:
            blob: Binary blob from database

        Returns:
            Numpy array of embeddings
        """
        # Assuming embeddings are stored as float32 binary
        num_floats = len(blob) // 4
        floats = struct.unpack(f"{num_floats}f", blob)
        return np.array(floats, dtype=np.float32)

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Compatibility method for code that expects the old interface.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
