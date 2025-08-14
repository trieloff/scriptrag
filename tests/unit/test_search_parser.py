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

    def test_parse_location_keywords_ignored(self) -> None:
        """Test location keywords are properly ignored and don't get categorized."""
        # Test simple location keywords
        simple_keywords = [
            "INT",
            "EXT",
            "DAY",
            "NIGHT",
            "MORNING",
            "AFTERNOON",
            "EVENING",
            "CONTINUOUS",
            "LATER",
        ]

        for keyword in simple_keywords:
            query = self.parser.parse(f"{keyword} something else")
            assert keyword not in query.characters
            assert keyword not in query.locations
            assert query.text_query == "something else"

        # Test INT/EXT separately as it has special replace behavior
        query_int_ext = self.parser.parse("INT/EXT something else")
        assert "INT/EXT" not in query_int_ext.characters
        assert "INT/EXT" not in query_int_ext.locations
        # The / gets left behind due to replace logic
        assert query_int_ext.text_query == "/ something else"

    def test_parse_caps_as_location(self) -> None:
        """Test parsing multi-word ALL CAPS as locations."""
        query = self.parser.parse("POLICE STATION and JOHN HOUSE")

        # Multi-word caps should be locations
        assert "POLICE STATION" in query.locations
        assert "JOHN HOUSE" in query.locations
        assert "POLICE" not in query.characters
        assert "STATION" not in query.characters
        assert "JOHN" not in query.characters  # Part of location, not character
        assert "HOUSE" not in query.characters

    def test_parse_remaining_query_cleanup(self) -> None:
        """Test edge cases in remaining query cleanup after component extraction."""
        # Test case where remaining query becomes empty after whitespace cleanup
        query = self.parser.parse('SARAH "dialogue" (whisper)     ')

        assert "SARAH" in query.characters
        assert query.dialogue == "dialogue"
        assert query.parenthetical == "whisper"
        assert query.text_query is None  # Should be None, not empty string

    def test_parse_multiple_spaces_cleanup(self) -> None:
        """Test cleanup of multiple spaces in remaining text query."""
        query = self.parser.parse("SARAH   walks    very    slowly")

        assert "SARAH" in query.characters
        assert query.text_query == "walks very slowly"  # Multiple spaces cleaned up

    def test_parse_invalid_episode_range(self) -> None:
        """Test parsing invalid episode range strings."""
        # Invalid range format should not crash, just not set range values
        query = self.parser.parse("test", range_str="invalid")

        assert query.season_start is None
        assert query.episode_start is None
        assert query.season_end is None
        assert query.episode_end is None

    def test_parse_episode_range_case_insensitive(self) -> None:
        """Test episode range parsing is case insensitive."""
        query = self.parser.parse("", range_str="S2E3")

        assert query.season_start == 2
        assert query.episode_start == 3
        assert query.season_end == 2
        assert query.episode_end == 3

    def test_parse_multiple_parentheticals(self) -> None:
        """Test handling multiple parentheticals - should use first one."""
        query = self.parser.parse("(whisper) some text (shout)")

        assert query.parenthetical == "whisper"
        assert query.text_query == "some text"

    def test_parse_complex_character_location_mix(self) -> None:
        """Test complex mix of characters, locations, and keywords."""
        # The ALL_CAPS_PATTERN regex matches the entire sequence as one match
        query = self.parser.parse("INT SARAH COFFEE SHOP DAY JOHN walks")

        # The entire ALL CAPS sequence gets treated as one location since it has spaces
        assert "INT SARAH COFFEE SHOP DAY JOHN" in query.locations
        assert query.text_query == "walks"

        # Test with separate capitalized words for individual character detection
        query2 = self.parser.parse("SARAH walks with JOHN")
        assert "SARAH" in query2.characters
        assert "JOHN" in query2.characters
        assert query2.text_query == "walks with"

    def test_auto_detect_skip_with_explicit_params(self) -> None:
        """Test auto-detection is skipped when explicit parameter is provided."""
        # Even with caps in query, explicit params should take precedence
        query = self.parser.parse(
            'SARAH "auto dialogue" (auto whisper)', character="EXPLICIT_CHAR"
        )

        # Auto-detection should be skipped, only explicit params used
        assert query.characters == ["EXPLICIT_CHAR"]
        assert query.dialogue is None  # Not auto-detected
        assert query.parenthetical is None  # Not auto-detected
        assert query.text_query is None  # Not auto-detected

    def test_parse_edge_case_empty_components(self) -> None:
        """Test edge cases with empty quoted strings and parentheticals."""
        # The regex patterns only match non-empty content inside quotes/parens
        query = self.parser.parse('""  ()  some text')

        # Empty quotes and parens are not matched by the regex patterns
        assert query.dialogue is None
        assert query.parenthetical is None
        assert query.text_query == '"" () some text'

    def test_regex_patterns_coverage(self) -> None:
        """Test regex pattern edge cases for complete coverage."""
        # Test dialogue pattern - the regex stops at the first closing quote
        query = self.parser.parse('"she said hello" remaining')
        assert query.dialogue == "she said hello"

        # Test parenthetical pattern - matches content inside first parentheses
        query2 = self.parser.parse("(he whispered quietly) text")
        assert query2.parenthetical == "he whispered quietly"

        # Test with multiple quote styles
        query3 = self.parser.parse('"first dialogue" and "second dialogue"')
        assert query3.dialogue == "first dialogue"  # Uses first match
        assert query3.text_query == "and"

    def test_parse_remaining_query_edge_case_empty_after_cleanup(self) -> None:
        """Test edge case where remaining query becomes empty after space cleanup."""
        # Create a case where text exists but becomes empty after split().join()
        # This happens with whitespace-only remaining text
        query = self.parser.parse('SARAH "dialogue"   \t\n   ')

        assert "SARAH" in query.characters
        assert query.dialogue == "dialogue"
        # The remaining whitespace should result in None text_query after cleanup
        assert query.text_query is None
