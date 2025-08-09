"""Unit tests for SQL query builder."""

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
