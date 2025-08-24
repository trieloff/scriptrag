"""SQL query builder for search functionality."""

from typing import Any

from scriptrag.search.models import SearchQuery
from scriptrag.search.utils import SearchFilterUtils, SearchTextUtils


class QueryBuilder:
    """Build SQL queries for different search types."""

    def __init__(self) -> None:
        """Initialize query builder with utility classes."""
        self.filter_utils = SearchFilterUtils()
        self.text_utils = SearchTextUtils()

    def build_search_query(self, search_query: SearchQuery) -> tuple[str, list[Any]]:
        """Build SQL query based on search parameters.

        Args:
            search_query: Parsed search query

        Returns:
            Tuple of (sql_query, parameters)
        """
        # Base query with all necessary joins
        select_parts = [
            "DISTINCT s.id as script_id",
            "s.title as script_title",
            "s.author as script_author",
            "s.metadata as script_metadata",
            "sc.id as scene_id",
            "sc.scene_number",
            "sc.heading as scene_heading",
            "sc.location as scene_location",
            "sc.time_of_day as scene_time",
            "sc.content as scene_content",
        ]

        from_parts = ["scripts s", "INNER JOIN scenes sc ON s.id = sc.script_id"]
        where_conditions: list[str] = []
        params: list[Any] = []

        # Add various filters using utility methods
        self.filter_utils.add_project_filter(
            where_conditions, params, search_query.project
        )
        self.filter_utils.add_season_episode_filters(
            where_conditions, params, search_query
        )

        # Handle different search types
        if search_query.dialogue:
            self.text_utils.add_dialogue_search(
                from_parts, where_conditions, params, search_query
            )
        elif search_query.text_query or search_query.action:
            self.text_utils.add_action_search(where_conditions, params, search_query)

        # Add location filters
        self.filter_utils.add_location_filters(
            where_conditions, params, search_query.locations
        )

        # Add character-only search (when searching for characters without text)
        if search_query.characters and not (
            search_query.dialogue or search_query.text_query or search_query.action
        ):
            self.filter_utils.add_character_filter(
                where_conditions, params, search_query.characters
            )

        # Build the complete query
        sql = f"""
            SELECT {", ".join(select_parts)}
            FROM {" ".join(from_parts)}
        """

        if where_conditions:
            sql += f" WHERE {' AND '.join(where_conditions)}"

        # Add ordering (by script, then scene number)
        sql += """
            ORDER BY s.id, sc.scene_number
        """

        # Add pagination
        sql += " LIMIT ? OFFSET ?"
        params.extend([search_query.limit, search_query.offset])

        return sql, params

    def build_count_query(self, search_query: SearchQuery) -> tuple[str, list[Any]]:
        """Build SQL query to count total results.

        Args:
            search_query: Parsed search query

        Returns:
            Tuple of (sql_query, parameters)
        """
        # Build count query using the same logic as search query
        from_parts = ["scripts s", "INNER JOIN scenes sc ON s.id = sc.script_id"]
        where_conditions: list[str] = []
        params: list[Any] = []

        # Use the same utility methods for consistency
        self.filter_utils.add_project_filter(
            where_conditions, params, search_query.project
        )
        self.filter_utils.add_season_episode_filters(
            where_conditions, params, search_query
        )

        # Handle different search types
        if search_query.dialogue:
            self.text_utils.add_dialogue_search(
                from_parts, where_conditions, params, search_query
            )
        elif search_query.text_query or search_query.action:
            self.text_utils.add_action_search(where_conditions, params, search_query)

        # Add location filters
        self.filter_utils.add_location_filters(
            where_conditions, params, search_query.locations
        )

        # Add character-only search
        if search_query.characters and not (
            search_query.dialogue or search_query.text_query or search_query.action
        ):
            self.filter_utils.add_character_filter(
                where_conditions, params, search_query.characters
            )

        # Build final count query
        sql = f"""
            SELECT COUNT(DISTINCT sc.id) as total
            FROM {" ".join(from_parts)}
        """

        if where_conditions:
            sql += f" WHERE {' AND '.join(where_conditions)}"

        return sql, params
