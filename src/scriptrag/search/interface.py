"""Main search interface for ScriptRAG.

This module provides a unified interface for all search operations,
combining text-based, semantic, entity, and temporal search capabilities.
"""

import asyncio
from typing import Any

from scriptrag.config import get_logger
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.embedding_pipeline import EmbeddingPipeline
from scriptrag.llm.client import LLMClient

from .types import SearchResult, SearchResults, SearchType

logger = get_logger(__name__)


class SearchInterface:
    """Unified search interface for screenplay content.

    Provides comprehensive search functionality across all screenplay
    elements using both traditional text search and semantic embeddings.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Initialize search interface.

        Args:
            connection: Database connection
            llm_client: LLM client for semantic search
        """
        from .ranking import SearchRanker
        from .text_search import TextSearchEngine

        self.connection = connection
        self.text_engine = TextSearchEngine(connection)
        self.embedding_pipeline = EmbeddingPipeline(connection, llm_client)
        self.ranker = SearchRanker()

    async def search(
        self,
        query: str,
        search_types: list[SearchType] | None = None,
        entity_filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
        min_score: float = 0.0,
    ) -> SearchResults:
        """Perform a comprehensive search across screenplay content.

        Args:
            query: Search query text
            search_types: Types of search to perform (all if None)
            entity_filter: Additional filters (e.g., character_id, location_id)
            limit: Maximum number of results
            offset: Offset for pagination
            min_score: Minimum score threshold

        Returns:
            List of search results
        """
        if not query.strip():
            return []

        # Default to all search types
        if search_types is None:
            search_types = list(SearchType)

        # Collect results from different search methods
        all_results: SearchResults = []
        tasks = []

        # Text-based searches
        if SearchType.DIALOGUE in search_types:
            tasks.append(self._search_dialogue(query, entity_filter))
        if SearchType.ACTION in search_types:
            tasks.append(self._search_action(query, entity_filter))
        if SearchType.FULL_TEXT in search_types:
            tasks.append(self._search_full_text(query, entity_filter))

        # Entity searches
        if SearchType.CHARACTER in search_types:
            tasks.append(self._search_characters(query, entity_filter))
        if SearchType.LOCATION in search_types:
            tasks.append(self._search_locations(query, entity_filter))
        if SearchType.SCENE in search_types:
            tasks.append(self._search_scenes(query, entity_filter))

        # Semantic search
        if SearchType.SEMANTIC in search_types:
            tasks.append(self._search_semantic(query, entity_filter))

        # Temporal search
        if SearchType.TEMPORAL in search_types:
            tasks.append(self._search_temporal(query, entity_filter))

        # Execute all searches in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Search task failed", error=str(result))
                elif isinstance(result, list):
                    all_results.extend(result)

        # Rank and filter results
        ranked_results = self.ranker.rank_results(all_results, query)
        filtered_results = [r for r in ranked_results if r["score"] >= min_score]

        # Apply pagination
        start_idx = offset
        end_idx = offset + limit
        return filtered_results[start_idx:end_idx]

    async def search_dialogue(
        self,
        query: str,
        character: str | None = None,
        scene_id: str | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search specifically within dialogue.

        Args:
            query: Search query
            character: Filter by character name
            scene_id: Filter by scene
            limit: Maximum results

        Returns:
            Dialogue search results
        """
        entity_filter = {}
        if character:
            entity_filter["character"] = character
        if scene_id:
            entity_filter["scene_id"] = scene_id

        return await self._search_dialogue(query, entity_filter, limit)

    async def search_similar_scenes(
        self,
        scene_id: str,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> SearchResults:
        """Find scenes similar to a given scene.

        Args:
            scene_id: Reference scene ID
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            Similar scenes
        """
        try:
            similar_scenes = await self.embedding_pipeline.get_similar_scenes(
                scene_id, limit=limit, min_similarity=min_similarity
            )

            results = []
            for scene in similar_scenes:
                result = SearchResult(
                    id=scene["entity_id"],
                    type="scene",
                    content=scene["content"],
                    score=scene["similarity"],
                    metadata=scene.get("entity_details", {}),
                    highlights=[],
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error("Similar scene search failed", error=str(e))
            return []

    async def search_by_theme(
        self,
        theme: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search for content matching a theme or mood.

        Args:
            theme: Theme/mood to search for (e.g., "betrayal", "joy")
            entity_type: Filter by entity type
            limit: Maximum results

        Returns:
            Thematically related results
        """
        results = await self.embedding_pipeline.semantic_search(
            theme, entity_type=entity_type, limit=limit
        )

        # Convert to standard format
        search_results: SearchResults = []
        for result in results:
            search_result = SearchResult(
                id=result["entity_id"],
                type=result["entity_type"],
                content=result["content"],
                score=result["similarity"],
                metadata=result.get("entity_details", {}),
                highlights=[],
            )
            search_results.append(search_result)

        return search_results

    async def search_temporal(
        self,
        time_range: tuple[str | None, str | None] | None = None,
        day_night: str | None = None,
        sequence: str | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search based on temporal criteria.

        Args:
            time_range: Tuple of (start_time, end_time) for story time
            day_night: Filter by DAY/NIGHT
            sequence: Search for sequential patterns
            limit: Maximum results

        Returns:
            Temporally filtered results
        """
        filters: dict[str, Any] = {}
        if time_range:
            filters["time_range"] = time_range
        if day_night:
            filters["day_night"] = day_night
        if sequence:
            filters["sequence"] = sequence

        return await self._search_temporal("", filters, limit)

    # Private search methods
    async def _search_dialogue(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search dialogue content."""
        return await self.text_engine.search_dialogue(query, filters, limit)

    async def _search_action(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search action/description content."""
        return await self.text_engine.search_action(query, filters, limit)

    async def _search_full_text(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Full-text search across all content."""
        return await self.text_engine.search_full_text(query, filters, limit)

    async def _search_characters(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search for characters."""
        return await self.text_engine.search_entities(
            query, "character", filters, limit
        )

    async def _search_locations(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search for locations."""
        return await self.text_engine.search_entities(query, "location", filters, limit)

    async def _search_scenes(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search scene headings and content."""
        return await self.text_engine.search_scenes(query, filters, limit)

    async def _search_semantic(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Semantic search using embeddings."""
        entity_type = filters.get("entity_type") if filters else None
        results = await self.embedding_pipeline.semantic_search(
            query, entity_type=entity_type, limit=limit
        )

        # Convert to standard format
        search_results = []
        for result in results:
            search_result = SearchResult(
                id=result["entity_id"],
                type=result["entity_type"],
                content=result["content"],
                score=result["similarity"],
                metadata=result.get("entity_details", {}),
                highlights=[],
            )
            search_results.append(search_result)

        return search_results

    async def _search_temporal(
        self,
        query: str,  # noqa: ARG002
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search based on temporal criteria."""
        # Build temporal query
        conditions = []
        params = []

        if filters:
            if "time_range" in filters:
                start_time, end_time = filters["time_range"]
                if start_time:
                    conditions.append("story_time >= ?")
                    params.append(start_time)
                if end_time:
                    conditions.append("story_time <= ?")
                    params.append(end_time)

            if "day_night" in filters:
                conditions.append("time_of_day = ?")
                params.append(filters["day_night"].upper())

            if "sequence" in filters:
                # Complex sequential pattern matching would go here
                pass

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Query scenes based on temporal criteria
        rows = self.connection.fetch_all(
            f"""
            SELECT s.id, s.heading, s.script_order, s.description,
                   s.story_time, s.time_of_day
            FROM scenes s
            {where_clause}
            ORDER BY s.script_order
            LIMIT ?
            """,
            (*params, limit),
        )

        results = []
        for row in rows:
            result = SearchResult(
                id=row["id"],
                type="scene",
                content=row["heading"],
                score=1.0,  # Temporal search doesn't have natural scores
                metadata={
                    "script_order": row["script_order"],
                    "description": row["description"],
                    "story_time": row["story_time"],
                    "time_of_day": row["time_of_day"],
                },
                highlights=[],
            )
            results.append(result)

        return results

    async def close(self) -> None:
        """Close search interface and cleanup resources."""
        if self.embedding_pipeline:
            await self.embedding_pipeline.close()
