"""Unit tests for search query parser."""

from scriptrag.search.models import SearchMode
from scriptrag.search.parser import QueryParser


class TestQueryParser:
    """Test query parser functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.parser = QueryParser()

    def test_parse_simple_text_query(self) -> None:
        """Test parsing simple text query."""
        query = self.parser.parse("the adventure begins")

        assert query.raw_query == "the adventure begins"
        assert query.text_query == "the adventure begins"
        assert query.dialogue is None
        assert query.parenthetical is None
        assert query.characters == []
        assert query.locations == []

    def test_parse_dialogue_query(self) -> None:
        """Test parsing dialogue in quotes."""
        query = self.parser.parse('"take the notebook"')

        assert query.dialogue == "take the notebook"
        assert query.text_query is None

    def test_parse_parenthetical_query(self) -> None:
        """Test parsing parenthetical text."""
        query = self.parser.parse("(whisper)")

        assert query.parenthetical == "whisper"
        assert query.text_query is None

    def test_parse_character_caps(self) -> None:
        """Test parsing ALL CAPS character names."""
        query = self.parser.parse("SARAH walks in")

        assert "SARAH" in query.characters
        assert query.text_query == "walks in"

    def test_parse_location_caps(self) -> None:
        """Test parsing ALL CAPS multi-word locations."""
        query = self.parser.parse("COFFEE SHOP scene")

        assert "COFFEE SHOP" in query.locations
        assert query.text_query == "scene"

    def test_parse_combined_query(self) -> None:
        """Test parsing combined dialogue and character."""
        query = self.parser.parse('SARAH "take the notebook" (whisper)')

        assert "SARAH" in query.characters
        assert query.dialogue == "take the notebook"
        assert query.parenthetical == "whisper"
        assert query.text_query is None

    def test_parse_with_explicit_params(self) -> None:
        """Test parsing with explicit parameters."""
        query = self.parser.parse(
            "some text",
            character="JOHN",
            dialogue="hello world",
            parenthetical="loudly",
        )

        assert query.characters == ["JOHN"]
        assert query.dialogue == "hello world"
        assert query.parenthetical == "loudly"
        # When explicit params are provided, auto-detection is skipped
        # so raw query stays as is but text_query is not set
        assert query.raw_query == "some text"
        assert query.text_query is None  # Not auto-detected due to explicit params

    def test_parse_episode_range_single(self) -> None:
        """Test parsing single episode range."""
        query = self.parser.parse("", range_str="s1e2")

        assert query.season_start == 1
        assert query.episode_start == 2
        assert query.season_end == 1
        assert query.episode_end == 2

    def test_parse_episode_range_multi(self) -> None:
        """Test parsing multi-episode range."""
        query = self.parser.parse("", range_str="s1e2-s2e5")

        assert query.season_start == 1
        assert query.episode_start == 2
        assert query.season_end == 2
        assert query.episode_end == 5

    def test_parse_project_filter(self) -> None:
        """Test parsing with project filter."""
        query = self.parser.parse("dialogue", project="The Great Adventure")

        assert query.project == "The Great Adventure"
        assert query.text_query == "dialogue"

    def test_parse_mode_settings(self) -> None:
        """Test parsing with different search modes."""
        strict_query = self.parser.parse("text", mode=SearchMode.STRICT)
        assert strict_query.mode == SearchMode.STRICT
        assert not strict_query.needs_vector_search

        fuzzy_query = self.parser.parse("text", mode=SearchMode.FUZZY)
        assert fuzzy_query.mode == SearchMode.FUZZY
        assert fuzzy_query.needs_vector_search

        auto_query = self.parser.parse("short text", mode=SearchMode.AUTO)
        assert auto_query.mode == SearchMode.AUTO
        assert not auto_query.needs_vector_search  # Short query

        long_text = " ".join(["word"] * 15)
        auto_long_query = self.parser.parse(long_text, mode=SearchMode.AUTO)
        assert auto_long_query.needs_vector_search  # Long query

    def test_parse_pagination(self) -> None:
        """Test parsing with pagination parameters."""
        query = self.parser.parse("text", limit=10, offset=20)

        assert query.limit == 10
        assert query.offset == 20

    def test_skip_location_keywords(self) -> None:
        """Test that location keywords are skipped."""
        query = self.parser.parse("INT NIGHT the scene")

        # INT and NIGHT should be skipped
        assert "INT" not in query.characters
        assert "INT" not in query.locations
        assert "NIGHT" not in query.characters
        assert "NIGHT" not in query.locations
        assert query.text_query == "the scene"

    def test_multiple_quoted_strings(self) -> None:
        """Test handling multiple quoted strings."""
        query = self.parser.parse('"first quote" and "second quote"')

        # Should use first quote as dialogue
        assert query.dialogue == "first quote"
        assert query.text_query == "and"

    def test_empty_query(self) -> None:
        """Test parsing empty query."""
        query = self.parser.parse("")

        assert query.raw_query == ""
        assert query.text_query is None
        assert query.dialogue is None
        assert query.characters == []
