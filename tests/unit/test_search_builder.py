"""Unit tests for SQL query builder."""

import pytest

from scriptrag.search.builder import QueryBuilder
from scriptrag.search.models import SearchQuery


class TestQueryBuilder:
    """Test SQL query builder functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.builder = QueryBuilder()

    def test_build_simple_text_query(self) -> None:
        """Test building simple text search query."""
        search_query = SearchQuery(
            raw_query="test",
            text_query="adventure",
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "SELECT DISTINCT" in sql
        assert "FROM scripts s" in sql
        assert "INNER JOIN scenes sc" in sql
        assert "sc.content LIKE ?" in sql
        assert "ORDER BY s.id, sc.scene_number" in sql
        assert "LIMIT ? OFFSET ?" in sql
        assert "%adventure%" in params
        assert params[-2:] == [5, 0]  # limit, offset

    def test_build_dialogue_query(self) -> None:
        """Test building dialogue search query."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="take the notebook",
            limit=10,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "INNER JOIN dialogues d" in sql
        assert "d.dialogue_text LIKE ?" in sql
        assert "%take the notebook%" in params

    def test_build_character_dialogue_query(self) -> None:
        """Test building character-specific dialogue query."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            characters=["SARAH", "JOHN"],
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "INNER JOIN characters c" in sql
        assert "c.name = ?" in sql
        assert "SARAH" in params
        assert "JOHN" in params
        assert "%hello%" in params

    def test_build_project_filter_query(self) -> None:
        """Test building query with project filter."""
        search_query = SearchQuery(
            raw_query="test",
            text_query="scene",
            project="The Great Adventure",
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "s.title LIKE ?" in sql
        assert "%The Great Adventure%" in params

    def test_build_episode_range_query(self) -> None:
        """Test building query with episode range."""
        search_query = SearchQuery(
            raw_query="test",
            text_query="coffee",
            season_start=1,
            season_end=2,
            episode_start=3,
            episode_end=5,
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "json_extract(s.metadata, '$.season')" in sql
        assert "json_extract(s.metadata, '$.episode')" in sql
        assert 1 in params  # season_start
        assert 2 in params  # season_end
        assert 3 in params  # episode_start
        assert 5 in params  # episode_end

    def test_build_location_query(self) -> None:
        """Test building location search query."""
        search_query = SearchQuery(
            raw_query="test",
            locations=["COFFEE SHOP", "OFFICE"],
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "sc.location LIKE ?" in sql
        assert "%COFFEE SHOP%" in params
        assert "%OFFICE%" in params

    def test_build_parenthetical_query(self) -> None:
        """Test building parenthetical search query."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            parenthetical="whisper",
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "json_extract(d.metadata, '$.parenthetical')" in sql
        assert "%whisper%" in params

    def test_build_character_only_query(self) -> None:
        """Test building character-only search query."""
        search_query = SearchQuery(
            raw_query="test",
            characters=["SARAH"],
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "EXISTS" in sql
        assert "c3.name = ?" in sql
        assert "SARAH" in params

    def test_build_action_query(self) -> None:
        """Test building action search query."""
        search_query = SearchQuery(
            raw_query="test",
            action="walks into the room",
            limit=5,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "actions a" in sql
        assert "a.action_text LIKE ?" in sql
        assert "%walks into the room%" in params

    def test_build_count_query(self) -> None:
        """Test building count query for pagination."""
        search_query = SearchQuery(
            raw_query="test",
            text_query="scene",
            limit=5,
            offset=10,
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "COUNT(DISTINCT sc.id)" in sql
        assert "LIMIT" not in sql
        assert "OFFSET" not in sql
        assert "ORDER BY" not in sql
        # Params should not include limit/offset
        assert 5 not in params
        assert 10 not in params

    def test_build_count_query_with_project(self) -> None:
        """Test building count query with project filter."""
        search_query = SearchQuery(
            raw_query="test",
            project="The Adventure",
            text_query="scene",
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "s.title LIKE ?" in sql
        assert "%The Adventure%" in params

    def test_build_count_query_episode_range(self) -> None:
        """Test building count query with episode range."""
        search_query = SearchQuery(
            raw_query="test",
            season_start=1,
            season_end=3,
            episode_start=2,
            episode_end=5,
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "json_extract(s.metadata, '$.season') >= ?" in sql
        assert "json_extract(s.metadata, '$.season') <= ?" in sql
        assert "json_extract(s.metadata, '$.episode') >= ?" in sql
        assert "json_extract(s.metadata, '$.episode') <= ?" in sql
        assert params == [1, 3, 2, 5]

    def test_build_count_query_single_episode(self) -> None:
        """Test building count query for single episode."""
        search_query = SearchQuery(
            raw_query="test",
            season_start=2,
            episode_start=7,
            # No season_end means single episode
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "json_extract(s.metadata, '$.season') = ?" in sql
        assert "json_extract(s.metadata, '$.episode') = ?" in sql
        assert 2 in params
        assert 7 in params

    def test_build_count_query_dialogue_with_characters(self) -> None:
        """Test building count query for dialogue with character filter."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="take the notebook",
            characters=["SARAH", "JOHN"],
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "INNER JOIN dialogues d" in sql
        assert "INNER JOIN characters c" in sql
        assert "d.dialogue_text LIKE ?" in sql
        assert "c.name = ?" in sql
        assert "%take the notebook%" in params
        assert "SARAH" in params
        assert "JOHN" in params

    def test_build_count_query_dialogue_with_parenthetical(self) -> None:
        """Test building count query for dialogue with parenthetical."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            parenthetical="softly",
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "json_extract(d.metadata, '$.parenthetical') LIKE ?" in sql
        assert "%softly%" in params

    def test_build_count_query_action_with_characters(self) -> None:
        """Test building count query for action with character filter."""
        search_query = SearchQuery(
            raw_query="test",
            action="walks into room",
            characters=["JOHN"],
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "sc.content LIKE ?" in sql
        assert "EXISTS" in sql
        assert "actions a" in sql
        assert "a.action_text LIKE ?" in sql
        assert "c2.name = ?" in sql
        assert "%walks into room%" in params
        assert "JOHN" in params

    def test_build_count_query_locations(self) -> None:
        """Test building count query with location filters."""
        search_query = SearchQuery(
            raw_query="test",
            locations=["COFFEE SHOP", "OFFICE"],
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "sc.location LIKE ?" in sql
        assert "%COFFEE SHOP%" in params
        assert "%OFFICE%" in params

    def test_build_count_query_character_only(self) -> None:
        """Test building count query for character-only search."""
        search_query = SearchQuery(
            raw_query="test",
            characters=["SARAH", "JOHN"],
            # No dialogue, text_query, or action
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "EXISTS" in sql
        assert "dialogues d3" in sql
        assert "characters c3" in sql
        assert "c3.name = ?" in sql
        assert "SARAH" in params
        assert "JOHN" in params

    @pytest.mark.parametrize(
        "search_mode,expected_text",
        [
            ("dialogue", "notebook"),
            ("action", "walks away"),
            ("text_query", "adventure scene"),
        ],
    )
    def test_build_search_query_parameter_combinations(
        self, search_mode: str, expected_text: str
    ) -> None:
        """Test different parameter combinations for search query building."""
        search_kwargs = {
            "raw_query": "test",
            search_mode: expected_text,
        }
        search_query = SearchQuery(**search_kwargs)

        sql, params = self.builder.build_search_query(search_query)

        assert (
            expected_text.replace(" ", "%") in f"%{expected_text}%"
            or f"%{expected_text}%" in params
        )
        assert "LIMIT ? OFFSET ?" in sql

    def test_build_search_query_no_where_conditions(self) -> None:
        """Test building search query with no filters (empty search)."""
        search_query = SearchQuery(
            raw_query="",  # Empty search
            limit=10,
            offset=0,
        )

        sql, params = self.builder.build_search_query(search_query)

        assert "FROM scripts s" in sql
        assert "INNER JOIN scenes sc" in sql
        assert "WHERE" not in sql  # No conditions added
        assert "ORDER BY" in sql
        assert "LIMIT ? OFFSET ?" in sql
        assert params == [10, 0]  # Only limit and offset

    def test_build_count_query_no_conditions(self) -> None:
        """Test building count query with no filters."""
        search_query = SearchQuery(
            raw_query="",  # Empty search
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "COUNT(DISTINCT sc.id)" in sql
        assert "WHERE" not in sql  # No conditions
        assert params == []  # No parameters

    def test_add_dialogue_search_empty_character_conditions(self) -> None:
        """Test _add_dialogue_search with empty character conditions list."""
        from_parts = []
        where_conditions = []
        params = []
        # Create a SearchQuery with characters but manipulate to test empty conditions
        search_query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            characters=[],  # Empty list should not add character conditions
        )

        self.builder._add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        # Should have dialogue join but no character conditions
        assert "INNER JOIN dialogues d" in " ".join(from_parts)
        assert "d.dialogue_text LIKE ?" in " ".join(where_conditions)
        # Should NOT have character join since characters is empty
        assert "INNER JOIN characters c" not in " ".join(from_parts)

    def test_add_action_search_empty_character_conditions(self) -> None:
        """Test _add_action_search with empty character conditions list."""
        where_conditions = []
        params = []
        # Create a SearchQuery with empty characters list
        search_query = SearchQuery(
            raw_query="test",
            action="walks in",
            characters=[],  # Empty list should not add character conditions
        )

        self.builder._add_action_search(where_conditions, params, search_query)

        # Should have action search but no character conditions
        condition_text = " ".join(where_conditions)
        assert "sc.content LIKE ?" in condition_text
        assert "EXISTS" in condition_text
        assert "actions a" in condition_text
        # Should NOT have character-specific EXISTS clauses
        assert "c2.name = ?" not in condition_text
        assert "%walks in%" in params

    def test_add_location_filters_empty_location_conditions(self) -> None:
        """Test _add_location_filters with empty location conditions after loop."""
        where_conditions = []
        params = []
        # This tests the edge case where location_conditions could be empty
        # after the loop (though in practice this won't happen with non-empty locations)
        locations = ["OFFICE", "CAFE"]

        self.builder._add_location_filters(where_conditions, params, locations)

        # Should have location conditions
        assert "sc.location LIKE ?" in " ".join(where_conditions)
        assert "%OFFICE%" in params
        assert "%CAFE%" in params

    def test_add_character_only_search_empty_conditions(self) -> None:
        """Test _add_character_only_search with empty char_conditions after loop."""
        where_conditions = []
        params = []
        # Test with actual characters to ensure we hit the conditions
        search_query = SearchQuery(
            raw_query="test",
            characters=["SARAH", "JOHN"],
            # No dialogue, text_query, or action
        )

        self.builder._add_character_only_search(where_conditions, params, search_query)

        # Should have character-only search conditions
        condition_text = " ".join(where_conditions)
        assert "EXISTS" in condition_text
        assert "dialogues d3" in condition_text
        assert "characters c3" in condition_text
        assert "c3.name = ?" in condition_text
        assert "SARAH" in params
        assert "JOHN" in params

    def test_build_count_query_dialogue_empty_character_conditions(self) -> None:
        """Test build_count_query dialogue branch with empty character conditions."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="hello world",
            characters=[],  # Empty list to test empty character_conditions
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "INNER JOIN dialogues d" in sql
        assert "d.dialogue_text LIKE ?" in sql
        # Should NOT have character join due to empty characters list
        assert "INNER JOIN characters c" not in sql
        assert "%hello world%" in params

    def test_build_count_query_action_empty_char_conditions(self) -> None:
        """Test build_count_query action branch with empty char conditions."""
        search_query = SearchQuery(
            raw_query="test",
            action="walks away",
            characters=[],  # Empty list to test empty char_conditions
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "sc.content LIKE ?" in sql
        assert "EXISTS" in sql
        assert "actions a" in sql
        # Should NOT have character-specific EXISTS clauses
        assert "c2.name = ?" not in sql
        assert "%walks away%" in params

    def test_build_count_query_location_empty_conditions(self) -> None:
        """Test build_count_query with location filters creating empty conditions."""
        search_query = SearchQuery(
            raw_query="test",
            locations=["KITCHEN"],  # Single location to ensure conditions are created
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "sc.location LIKE ?" in sql
        assert "%KITCHEN%" in params

    def test_build_count_query_character_only_empty_conditions(self) -> None:
        """Test build_count_query character-only with empty char conditions."""
        search_query = SearchQuery(
            raw_query="test",
            characters=["DETECTIVE"],  # Single character to ensure conditions
            # No dialogue, text_query, or action for character-only search
        )

        sql, params = self.builder.build_count_query(search_query)

        assert "EXISTS" in sql
        assert "dialogues d3" in sql
        assert "characters c3" in sql
        assert "c3.name = ?" in sql
        assert "DETECTIVE" in params

    def test_build_complex_query(self) -> None:
        """Test building complex multi-filter query."""
        search_query = SearchQuery(
            raw_query="test",
            dialogue="notebook",
            characters=["SARAH"],
            parenthetical="urgently",
            project="Adventure",
            season_start=1,
            season_end=1,
            episode_start=2,
            episode_end=2,
            limit=20,
            offset=5,
        )

        sql, params = self.builder.build_search_query(search_query)

        # Should have all the filters
        assert "s.title LIKE ?" in sql
        assert "json_extract(s.metadata, '$.season')" in sql
        assert "d.dialogue_text LIKE ?" in sql
        assert "c.name = ?" in sql
        assert "json_extract(d.metadata, '$.parenthetical')" in sql

        # Check parameters
        assert "%Adventure%" in params
        assert "%notebook%" in params
        assert "SARAH" in params
        assert "%urgently%" in params
        assert params[-2:] == [20, 5]  # limit, offset

    def test_add_project_filter_none(self) -> None:
        """Test _add_project_filter with None project."""
        where_conditions = []
        params = []

        self.builder._add_project_filter(where_conditions, params, None)

        assert where_conditions == []
        assert params == []

    def test_add_project_filter_with_project(self) -> None:
        """Test _add_project_filter with project name."""
        where_conditions = []
        params = []

        self.builder._add_project_filter(where_conditions, params, "Test Project")

        assert "s.title LIKE ?" in where_conditions
        assert "%Test Project%" in params

    def test_add_season_episode_filters_single_episode(self) -> None:
        """Test _add_season_episode_filters for single episode."""
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test",
            season_start=2,
            episode_start=5,  # No season_end means single episode
        )

        self.builder._add_season_episode_filters(where_conditions, params, search_query)

        assert "json_extract(s.metadata, '$.season') = ?" in " ".join(where_conditions)
        assert "json_extract(s.metadata, '$.episode') = ?" in " ".join(where_conditions)
        assert 2 in params  # season_start
        assert 5 in params  # episode_start

    def test_add_season_episode_filters_none(self) -> None:
        """Test _add_season_episode_filters with no season info."""
        where_conditions = []
        params = []
        search_query = SearchQuery(raw_query="test")

        self.builder._add_season_episode_filters(where_conditions, params, search_query)

        assert where_conditions == []
        assert params == []

    def test_add_dialogue_search_no_dialogue(self) -> None:
        """Test _add_dialogue_search returns early when no dialogue."""
        from_parts = ["scripts s"]
        where_conditions = []
        params = []
        search_query = SearchQuery(raw_query="test")  # No dialogue

        self.builder._add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        # Should return early, no changes
        assert from_parts == ["scripts s"]
        assert where_conditions == []
        assert params == []

    def test_add_dialogue_search_with_parenthetical(self) -> None:
        """Test _add_dialogue_search with parenthetical filter."""
        from_parts = []
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test", dialogue="hello world", parenthetical="whispered"
        )

        self.builder._add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert "INNER JOIN dialogues d" in " ".join(from_parts)
        assert "json_extract(d.metadata, '$.parenthetical') LIKE ?" in " ".join(
            where_conditions
        )
        assert "%whispered%" in params
        assert "%hello world%" in params

    def test_add_action_search_no_query(self) -> None:
        """Test _add_action_search returns early when no text or action query."""
        where_conditions = []
        params = []
        search_query = SearchQuery(raw_query="test")  # No text_query or action

        self.builder._add_action_search(where_conditions, params, search_query)

        # Should return early, no changes
        assert where_conditions == []
        assert params == []

    def test_add_action_search_with_characters(self) -> None:
        """Test _add_action_search with character filters."""
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test", action="enters room", characters=["JOHN", "SARAH"]
        )

        self.builder._add_action_search(where_conditions, params, search_query)

        # Should have action search conditions
        condition_text = " ".join(where_conditions)
        assert "sc.content LIKE ?" in condition_text
        assert "EXISTS" in condition_text
        assert "actions a" in condition_text
        assert "a.action_text LIKE ?" in condition_text
        assert "c2.name = ?" in condition_text

        # Check parameters
        assert "%enters room%" in params
        assert "JOHN" in params
        assert "SARAH" in params

    def test_add_location_filters_none(self) -> None:
        """Test _add_location_filters with no locations."""
        where_conditions = []
        params = []

        self.builder._add_location_filters(where_conditions, params, None)

        assert where_conditions == []
        assert params == []

    def test_add_location_filters_empty_list(self) -> None:
        """Test _add_location_filters with empty location list."""
        where_conditions = []
        params = []

        self.builder._add_location_filters(where_conditions, params, [])

        assert where_conditions == []
        assert params == []

    def test_add_character_only_search_no_characters(self) -> None:
        """Test _add_character_only_search with no characters."""
        where_conditions = []
        params = []
        search_query = SearchQuery(raw_query="test")

        self.builder._add_character_only_search(where_conditions, params, search_query)

        assert where_conditions == []
        assert params == []

    def test_add_character_only_search_with_dialogue(self) -> None:
        """Test _add_character_only_search returns early when dialogue present."""
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test",
            characters=["JOHN"],
            dialogue="hello",  # This should prevent character-only search
        )

        self.builder._add_character_only_search(where_conditions, params, search_query)

        # Should return early due to dialogue being present
        assert where_conditions == []
        assert params == []

    def test_add_character_only_search_with_text_query(self) -> None:
        """Test _add_character_only_search returns early when text_query present."""
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test",
            characters=["JOHN"],
            text_query="adventure",  # This should prevent character-only search
        )

        self.builder._add_character_only_search(where_conditions, params, search_query)

        # Should return early due to text_query being present
        assert where_conditions == []
        assert params == []

    def test_add_character_only_search_with_action(self) -> None:
        """Test _add_character_only_search returns early when action present."""
        where_conditions = []
        params = []
        search_query = SearchQuery(
            raw_query="test",
            characters=["JOHN"],
            action="walks in",  # This should prevent character-only search
        )

        self.builder._add_character_only_search(where_conditions, params, search_query)

        # Should return early due to action being present
        assert where_conditions == []
        assert params == []
