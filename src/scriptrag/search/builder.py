"""SQL query builder for search functionality."""

from typing import Any

from scriptrag.search.models import SearchQuery


class QueryBuilder:
    """Build SQL queries for different search types."""

    def _add_project_filter(
        self, where_conditions: list[str], params: list[Any], project: str | None
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

    def _add_season_episode_filters(
        self,
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
                # Single episode
                where_conditions.append(
                    """
                    (
                        json_extract(s.metadata, '$.season') = ? AND
                        json_extract(s.metadata, '$.episode') = ?
                    )
                    """
                )
                params.extend([search_query.season_start, search_query.episode_start])

    def _add_dialogue_search(
        self,
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

        from_parts.append("INNER JOIN dialogues d ON sc.id = d.scene_id")
        where_conditions.append("d.dialogue_text LIKE ?")
        params.append(f"%{search_query.dialogue}%")

        # Add character filter for dialogue
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

    def _add_action_search(
        self,
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

        # Add character filter for action search
        if search_query.characters:
            char_conditions = []
            for char in search_query.characters:
                char_query = """
                    EXISTS (
                        SELECT 1 FROM dialogues d2
                        INNER JOIN characters c2 ON d2.character_id = c2.id
                        WHERE d2.scene_id = sc.id AND c2.name = ?
                    )
                """
                char_conditions.append(char_query)
                params.append(char)
            if char_conditions:
                where_conditions.append(f"({' OR '.join(char_conditions)})")

    def _add_location_filters(
        self,
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

    def _add_character_only_search(
        self,
        where_conditions: list[str],
        params: list[Any],
        search_query: SearchQuery,
    ) -> None:
        """Add character-only search (find all scenes with character).

        Args:
            where_conditions: List of WHERE conditions to append to
            params: List of query parameters to append to
            search_query: Search query containing character info
        """
        if not search_query.characters:
            return

        if search_query.dialogue or search_query.text_query or search_query.action:
            return

        char_conditions = []
        for char in search_query.characters:
            char_query = """
                EXISTS (
                    SELECT 1 FROM dialogues d3
                    INNER JOIN characters c3 ON d3.character_id = c3.id
                    WHERE d3.scene_id = sc.id AND c3.name = ?
                )
            """
            char_conditions.append(char_query)
            params.append(char)
        if char_conditions:
            where_conditions.append(f"({' OR '.join(char_conditions)})")

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

        # Add various filters using helper methods
        self._add_project_filter(where_conditions, params, search_query.project)
        self._add_season_episode_filters(where_conditions, params, search_query)

        # Handle different search types
        if search_query.dialogue:
            self._add_dialogue_search(
                from_parts, where_conditions, params, search_query
            )
        elif search_query.text_query or search_query.action:
            self._add_action_search(where_conditions, params, search_query)

        # Add location and character filters
        self._add_location_filters(where_conditions, params, search_query.locations)
        self._add_character_only_search(where_conditions, params, search_query)

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
        # Build count query directly without string manipulation
        from_parts = ["scripts s", "INNER JOIN scenes sc ON s.id = sc.script_id"]
        where_conditions: list[str] = []
        params: list[Any] = []

        # Add project filter
        if search_query.project:
            where_conditions.append("s.title LIKE ?")
            params.append(f"%{search_query.project}%")

        # Add season/episode filters from metadata
        if search_query.season_start is not None:
            # Parse metadata JSON to filter by season/episode
            if search_query.season_end is not None:
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
                # Single episode
                where_conditions.append(
                    """
                    (
                        json_extract(s.metadata, '$.season') = ? AND
                        json_extract(s.metadata, '$.episode') = ?
                    )
                    """
                )
                params.extend([search_query.season_start, search_query.episode_start])

        # Handle dialogue search
        if search_query.dialogue:
            from_parts.append("INNER JOIN dialogues d ON sc.id = d.scene_id")
            where_conditions.append("d.dialogue_text LIKE ?")
            params.append(f"%{search_query.dialogue}%")

            # Add character filter for dialogue
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

        # Handle action/general text search
        elif search_query.text_query or search_query.action:
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

            # Add character filter for action search
            if search_query.characters:
                char_conditions = []
                for char in search_query.characters:
                    char_query = """
                        EXISTS (
                            SELECT 1 FROM dialogues d2
                            INNER JOIN characters c2 ON d2.character_id = c2.id
                            WHERE d2.scene_id = sc.id AND c2.name = ?
                        )
                    """
                    char_conditions.append(char_query)
                    params.append(char)
                if char_conditions:
                    where_conditions.append(f"({' OR '.join(char_conditions)})")

        # Handle location search
        if search_query.locations:
            location_conditions = []
            for location in search_query.locations:
                location_conditions.append("sc.location LIKE ?")
                params.append(f"%{location}%")
            if location_conditions:
                where_conditions.append(f"({' OR '.join(location_conditions)})")

        # Handle character-only search (find all scenes with character)
        if search_query.characters and not (
            search_query.dialogue or search_query.text_query or search_query.action
        ):
            char_conditions = []
            for char in search_query.characters:
                char_query = """
                    EXISTS (
                        SELECT 1 FROM dialogues d3
                        INNER JOIN characters c3 ON d3.character_id = c3.id
                        WHERE d3.scene_id = sc.id AND c3.name = ?
                    )
                """
                char_conditions.append(char_query)
                params.append(char)
            if char_conditions:
                where_conditions.append(f"({' OR '.join(char_conditions)})")

        # Build final count query
        sql = f"""
            SELECT COUNT(DISTINCT sc.id) as total
            FROM {" ".join(from_parts)}
        """

        if where_conditions:
            sql += f" WHERE {' AND '.join(where_conditions)}"

        return sql, params
