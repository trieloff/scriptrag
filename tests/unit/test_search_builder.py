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
        assert "c.name = ?" in sql
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
        assert "c.name = ?" in sql
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
        assert "dialogues d" in sql
        assert "characters c" in sql
        assert "c.name = ?" in sql
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
        assert "c.name = ?" not in sql
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
        assert "dialogues d" in sql
        assert "characters c" in sql
        assert "c.name = ?" in sql
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
