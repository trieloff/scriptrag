"""Common utilities for search functionality."""

from __future__ import annotations

import json
from typing import Any

from scriptrag.config import get_logger
from scriptrag.search.models import SearchQuery

logger = get_logger(__name__)


class SearchFilterUtils:
    """Utilities for building search filters."""

    @staticmethod
    def add_project_filter(
        where_conditions: list[str], params: list[Any], project: str | None
    ) -> None:
        """Add project filter to query.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            project: Project name to filter by
        """
        if project:
            where_conditions.append("s.title LIKE ?")
            params.append(f"%{project}%")

    @staticmethod
    def add_season_episode_filters(
        where_conditions: list[str],
        params: list[Any],
        search_query: SearchQuery,
    ) -> None:
        """Add season/episode filters to query.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            search_query: Search query containing season/episode info
        """
        if search_query.season_start is not None:
            if search_query.season_end is not None:
                # Range query for season/episode
                where_conditions.append(
                    """
                    (
                        json_extract(s.metadata, '$.season') >= ? AND
                        json_extract(s.metadata, '$.season') <= ? AND
                        json_extract(s.metadata, '$.episode') >= ? AND
                        json_extract(s.metadata, '$.episode') <= ?
                    )
                    """
                )
                params.extend(
                    [
                        search_query.season_start,
                        search_query.season_end,
                        search_query.episode_start,
                        search_query.episode_end,
                    ]
                )
            else:
                # Single episode query
                where_conditions.append(
                    """
                    (
                        json_extract(s.metadata, '$.season') = ? AND
                        json_extract(s.metadata, '$.episode') = ?
                    )
                    """
                )
                params.extend([search_query.season_start, search_query.episode_start])

    @staticmethod
    def add_location_filters(
        where_conditions: list[str],
        params: list[Any],
        locations: list[str] | None,
    ) -> None:
        """Add location filters to query.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            locations: List of locations to filter by
        """
        if not locations:
            return

        location_conditions = []
        for location in locations:
            location_conditions.append("sc.location LIKE ?")
            params.append(f"%{location}%")
        if location_conditions:
            where_conditions.append(f"({' OR '.join(location_conditions)})")

    @staticmethod
    def add_scene_type_filter(
        where_conditions: list[str],
        params: list[Any],
        scene_type: str | None,
    ) -> None:
        """Add scene type filter to query.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            scene_type: Scene type to filter by (INT, EXT, INT/EXT)
        """
        if not scene_type:
            return

        # Scene headings typically start with INT., EXT., or INT/EXT.
        where_conditions.append("sc.heading LIKE ?")
        params.append(f"{scene_type}.%")

    @staticmethod
    def add_character_filter(
        where_conditions: list[str],
        params: list[Any],
        characters: list[str],
        scene_alias: str = "sc",
    ) -> None:
        """Add character filter for scenes containing specific characters.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            characters: List of character names to filter by
            scene_alias: Alias for the scenes table in the query
        """
        if not characters:
            return

        char_conditions = []
        for char in characters:
            char_query = f"""
                EXISTS (
                    SELECT 1 FROM dialogues d
                    INNER JOIN characters c ON d.character_id = c.id
                    WHERE d.scene_id = {scene_alias}.id AND c.name = ?
                )
            """
            char_conditions.append(char_query)
            params.append(char)
        if char_conditions:
            where_conditions.append(f"({' OR '.join(char_conditions)})")


class SearchTextUtils:
    """Utilities for text-based search operations."""

    @staticmethod
    def add_dialogue_search(
        from_parts: list[str],
        where_conditions: list[str],
        params: list[Any],
        search_query: SearchQuery,
    ) -> None:
        """Add dialogue search filters to query.

        Args:
            from_parts: List of FROM clauses to append to
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            search_query: Search query containing dialogue search info
        """
        if not search_query.dialogue:
            return

        # Join with dialogues table
        from_parts.append("INNER JOIN dialogues d ON sc.id = d.scene_id")
        where_conditions.append("d.dialogue_text LIKE ?")
        params.append(f"%{search_query.dialogue}%")

        # Add character filter for dialogue if specified
        if search_query.characters:
            from_parts.append("INNER JOIN characters c ON d.character_id = c.id")
            character_conditions = []
            for char in search_query.characters:
                character_conditions.append("c.name = ?")
                params.append(char)
            if character_conditions:
                where_conditions.append(f"({' OR '.join(character_conditions)})")

        # Add parenthetical filter if specified
        if search_query.parenthetical:
            where_conditions.append(
                "json_extract(d.metadata, '$.parenthetical') LIKE ?"
            )
            params.append(f"%{search_query.parenthetical}%")

    @staticmethod
    def add_action_search(
        where_conditions: list[str],
        params: list[Any],
        search_query: SearchQuery,
    ) -> None:
        """Add action/text search filters to query.

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            search_query: Search query containing action search info
        """
        if not (search_query.text_query or search_query.action):
            return

        query_text = search_query.action or search_query.text_query

        # Search in scene content and actions
        text_conditions = ["sc.content LIKE ?"]
        params.append(f"%{query_text}%")

        # Also search in action lines
        action_query = """
            EXISTS (
                SELECT 1 FROM actions a
                WHERE a.scene_id = sc.id
                AND a.action_text LIKE ?
            )
        """
        text_conditions.append(action_query)
        params.append(f"%{query_text}%")

        where_conditions.append(f"({' OR '.join(text_conditions)})")

        # Add character filter for action search if specified
        if search_query.characters:
            SearchFilterUtils.add_character_filter(
                where_conditions, params, search_query.characters
            )


class SearchResultUtils:
    """Utilities for processing search results."""

    @staticmethod
    def parse_metadata(
        metadata_json: str | None, row_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Parse JSON metadata with error handling.

        Args:
            metadata_json: JSON string to parse
            row_context: Optional context for error logging

        Returns:
            Parsed metadata dictionary or empty dict on error
        """
        if not metadata_json:
            return {}

        try:
            metadata: dict[str, Any] = json.loads(metadata_json)
            return metadata
        except (json.JSONDecodeError, TypeError) as e:
            if row_context:
                logger.warning("Failed to parse metadata", error=str(e), **row_context)
            return {}

    @staticmethod
    def determine_match_type(query: SearchQuery) -> str:
        """Determine the type of match based on query.

        Args:
            query: Search query

        Returns:
            Match type string
        """
        if query.dialogue:
            return "dialogue"
        if query.action:
            return "action"
        if query.text_query:
            return "text"
        if query.characters:
            return "character"
        if query.locations:
            return "location"
        return "text"

    @staticmethod
    def merge_results(
        primary_results: list[Any],
        secondary_results: list[Any],
        key_fn: Any,
    ) -> list[Any]:
        """Merge two lists of results, avoiding duplicates.

        Args:
            primary_results: Primary list of results
            secondary_results: Secondary list to merge in
            key_fn: Function to extract unique key from each result

        Returns:
            Merged list with no duplicates
        """
        existing_keys = {key_fn(result) for result in primary_results}
        merged = list(primary_results)

        for result in secondary_results:
            if key_fn(result) not in existing_keys:
                merged.append(result)
                existing_keys.add(key_fn(result))

        return merged
