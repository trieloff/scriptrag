"""Text-based search engine for screenplay content.

This module provides traditional text search functionality including
full-text search, pattern matching, and entity-based searches.
"""

import re
from typing import Any

from scriptrag.config import get_logger
from scriptrag.database.connection import DatabaseConnection

from .types import SearchResult, SearchResults

logger = get_logger(__name__)


class TextSearchEngine:
    """Text-based search engine for screenplay content."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize text search engine.

        Args:
            connection: Database connection
        """
        self.connection = connection

    async def search_dialogue(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search within dialogue content.

        Args:
            query: Search query
            filters: Additional filters
            limit: Maximum results

        Returns:
            Search results from dialogue
        """
        conditions = ["se.element_type = 'dialogue'"]
        params = []

        # Add search condition
        if query:
            conditions.append("se.text LIKE ?")
            params.append(f"%{query}%")

        # Add filters
        if filters:
            if "character" in filters:
                conditions.append("se.character_name = ?")
                params.append(filters["character"])
            if "scene_id" in filters:
                conditions.append("se.scene_id = ?")
                params.append(filters["scene_id"])

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Query dialogue with scene context
        rows = self.connection.fetch_all(
            f"""
            SELECT se.id, se.text as content, se.character_name, se.order_in_scene,
                   se.scene_id, s.heading as scene_heading, s.script_order
            FROM scene_elements se
            JOIN scenes s ON se.scene_id = s.id
            {where_clause}
            ORDER BY s.script_order, se.order_in_scene
            LIMIT ?
            """,
            (*params, limit),
        )

        results = []
        for row in rows:
            # Calculate basic relevance score
            score = self._calculate_text_score(query, row["content"])

            # Extract highlights
            highlights = self._extract_highlights(query, row["content"])

            result = SearchResult(
                id=row["id"],
                type="dialogue",
                content=row["content"],
                score=score,
                metadata={
                    "character": row["character_name"],
                    "scene_id": row["scene_id"],
                    "scene_heading": row["scene_heading"],
                    "script_order": row["script_order"],
                    "element_order": row["order_in_scene"],
                },
                highlights=highlights,
            )
            results.append(result)

        return results

    async def search_action(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search within action/description content.

        Args:
            query: Search query
            filters: Additional filters
            limit: Maximum results

        Returns:
            Search results from action lines
        """
        conditions = ["se.element_type = 'action'"]
        params = []

        # Add search condition
        if query:
            conditions.append("se.text LIKE ?")
            params.append(f"%{query}%")

        # Add filters
        if filters and "scene_id" in filters:
            conditions.append("se.scene_id = ?")
            params.append(filters["scene_id"])

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Query action content
        rows = self.connection.fetch_all(
            f"""
            SELECT se.id, se.text as content, se.order_in_scene,
                   se.scene_id, s.heading as scene_heading, s.script_order
            FROM scene_elements se
            JOIN scenes s ON se.scene_id = s.id
            {where_clause}
            ORDER BY s.script_order, se.order_in_scene
            LIMIT ?
            """,
            (*params, limit),
        )

        results = []
        for row in rows:
            score = self._calculate_text_score(query, row["content"])
            highlights = self._extract_highlights(query, row["content"])

            result = SearchResult(
                id=row["id"],
                type="action",
                content=row["content"],
                score=score,
                metadata={
                    "scene_id": row["scene_id"],
                    "scene_heading": row["scene_heading"],
                    "script_order": row["script_order"],
                    "element_order": row["order_in_scene"],
                },
                highlights=highlights,
            )
            results.append(result)

        return results

    async def search_full_text(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Full-text search across all content types.

        Args:
            query: Search query
            filters: Additional filters
            limit: Maximum results

        Returns:
            Search results from all content
        """
        # Search dialogue and action in parallel
        dialogue_results = await self.search_dialogue(query, filters, limit)
        action_results = await self.search_action(query, filters, limit)
        scene_results = await self.search_scenes(query, filters, limit)

        # Combine and sort by score
        all_results = dialogue_results + action_results + scene_results
        all_results.sort(key=lambda x: x["score"], reverse=True)

        return all_results[:limit]

    async def search_entities(
        self,
        query: str,
        entity_type: str,
        filters: dict[str, Any] | None = None,  # noqa: ARG002
        limit: int = 10,
    ) -> SearchResults:
        """Search for entities (characters, locations, objects).

        Args:
            query: Search query
            entity_type: Type of entity to search
            filters: Additional filters
            limit: Maximum results

        Returns:
            Entity search results
        """
        # Map entity types to tables
        table_map = {
            "character": "characters",
            "location": "locations",
            "object": "objects",
        }

        if entity_type not in table_map:
            logger.warning(f"Unknown entity type: {entity_type}")
            return []

        table = table_map[entity_type]
        conditions = []
        params = []

        # Add search condition
        if query:
            conditions.append("name LIKE ?")
            params.append(f"%{query}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Query entities
        rows = self.connection.fetch_all(
            f"""
            SELECT id, name, description, first_appearance_scene_id
            FROM {table}
            {where_clause}
            ORDER BY name
            LIMIT ?
            """,
            (*params, limit),
        )

        results = []
        for row in rows:
            score = self._calculate_text_score(query, row["name"])

            # Get appearance count
            appearance_count = self._get_entity_appearance_count(entity_type, row["id"])

            result = SearchResult(
                id=row["id"],
                type=entity_type,
                content=row["name"],
                score=score,
                metadata={
                    "description": row["description"],
                    "first_appearance_scene_id": row["first_appearance_scene_id"],
                    "appearance_count": appearance_count,
                },
                highlights=[],
            )
            results.append(result)

        return results

    async def search_scenes(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search scene headings and descriptions.

        Args:
            query: Search query
            filters: Additional filters
            limit: Maximum results

        Returns:
            Scene search results
        """
        conditions = []
        params = []

        # Add search conditions
        if query:
            # Search in heading and description
            conditions.append("(heading LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        # Add filters
        if filters:
            if "location" in filters:
                conditions.append(
                    "EXISTS (SELECT 1 FROM scene_locations sl "
                    "WHERE sl.scene_id = scenes.id AND sl.location_id = ?)"
                )
                params.append(filters["location"])
            if "character" in filters:
                conditions.append(
                    "EXISTS (SELECT 1 FROM scene_characters sc "
                    "WHERE sc.scene_id = scenes.id AND sc.character_id = ?)"
                )
                params.append(filters["character"])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Query scenes
        rows = self.connection.fetch_all(
            f"""
            SELECT id, heading, script_order, description,
                   time_of_day, location_type, story_time
            FROM scenes
            {where_clause}
            ORDER BY script_order
            LIMIT ?
            """,
            (*params, limit),
        )

        results = []
        for row in rows:
            # Calculate score based on heading and description matches
            heading_score = self._calculate_text_score(query, row["heading"])
            desc_score = self._calculate_text_score(query, row["description"] or "")
            score = max(heading_score, desc_score * 0.8)  # Prioritize heading matches

            # Get highlights from both fields
            highlights = self._extract_highlights(query, row["heading"])
            if row["description"]:
                highlights.extend(self._extract_highlights(query, row["description"]))

            result = SearchResult(
                id=row["id"],
                type="scene",
                content=row["heading"],
                score=score,
                metadata={
                    "script_order": row["script_order"],
                    "description": row["description"],
                    "time_of_day": row["time_of_day"],
                    "location_type": row["location_type"],
                    "story_time": row["story_time"],
                },
                highlights=highlights[:3],  # Limit highlights
            )
            results.append(result)

        return results

    def _calculate_text_score(self, query: str, content: str) -> float:
        """Calculate relevance score for text content.

        Args:
            query: Search query
            content: Content to score

        Returns:
            Relevance score between 0 and 1
        """
        if not query or not content:
            return 0.0

        query_lower = query.lower()
        content_lower = content.lower()

        # Exact match
        if query_lower == content_lower:
            return 1.0

        # Whole word match
        if re.search(rf"\b{re.escape(query_lower)}\b", content_lower):
            return 0.9

        # Substring match
        if query_lower in content_lower:
            # Score based on position and frequency
            position = content_lower.find(query_lower)
            position_score = 1.0 - (position / len(content_lower))
            frequency = content_lower.count(query_lower)
            frequency_score = min(frequency / 5, 1.0)  # Cap at 5 occurrences
            return 0.5 + (position_score * 0.2) + (frequency_score * 0.2)

        # Partial word matches (each word in query)
        query_words = query_lower.split()
        matches = sum(1 for word in query_words if word in content_lower)
        if matches > 0:
            return 0.3 * (matches / len(query_words))

        return 0.0

    def _extract_highlights(
        self, query: str, content: str, context_length: int = 50
    ) -> list[str]:
        """Extract highlighted snippets from content.

        Args:
            query: Search query
            content: Content to extract from
            context_length: Characters of context on each side

        Returns:
            List of highlighted snippets
        """
        if not query or not content:
            return []

        highlights = []
        query_lower = query.lower()
        content_lower = content.lower()

        # Find all occurrences
        start = 0
        while True:
            pos = content_lower.find(query_lower, start)
            if pos == -1:
                break

            # Extract context
            context_start = max(0, pos - context_length)
            context_end = min(len(content), pos + len(query) + context_length)

            # Find word boundaries
            if context_start > 0:
                while context_start < pos and content[context_start] not in " \n\t":
                    context_start += 1
            if context_end < len(content):
                while (
                    context_end > pos + len(query)
                    and content[context_end - 1] not in " \n\t"
                ):
                    context_end -= 1

            # Build highlight
            prefix = "..." if context_start > 0 else ""
            suffix = "..." if context_end < len(content) else ""
            highlight = f"{prefix}{content[context_start:context_end]}{suffix}"

            highlights.append(highlight)
            start = pos + 1

            # Limit number of highlights
            if len(highlights) >= 3:
                break

        return highlights

    def _get_entity_appearance_count(self, entity_type: str, entity_id: str) -> int:
        """Get the number of appearances for an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Number of appearances
        """
        # Map entity types to junction tables
        junction_map = {
            "character": ("scene_characters", "character_id"),
            "location": ("scene_locations", "location_id"),
            "object": ("scene_objects", "object_id"),
        }

        if entity_type not in junction_map:
            return 0

        table, id_column = junction_map[entity_type]

        row = self.connection.fetch_one(
            f"SELECT COUNT(*) as count FROM {table} WHERE {id_column} = ?",
            (entity_id,),
        )

        return row["count"] if row else 0
