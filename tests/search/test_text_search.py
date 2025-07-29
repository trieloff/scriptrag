"""Tests for text search engine module."""

from unittest.mock import MagicMock

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.search.text_search import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    TextSearchEngine,
)


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    conn = MagicMock(spec=DatabaseConnection)
    conn.fetch_all = MagicMock(return_value=[])
    conn.fetch_one = MagicMock(return_value=None)
    return conn


@pytest.fixture
def text_engine(mock_connection):
    """Create text search engine with mock connection."""
    return TextSearchEngine(mock_connection)


class TestTextSearchEngineInit:
    """Test TextSearchEngine initialization."""

    def test_init(self, mock_connection):
        """Test engine initialization."""
        engine = TextSearchEngine(mock_connection)
        assert engine.connection == mock_connection


class TestTextSearchEngineValidation:
    """Test TextSearchEngine input validation."""

    def test_validate_limit_valid(self, text_engine):
        """Test limit validation with valid values."""
        assert text_engine._validate_limit(10) == 10
        assert text_engine._validate_limit(1) == 1
        assert text_engine._validate_limit(MAX_SEARCH_LIMIT) == MAX_SEARCH_LIMIT

    def test_validate_limit_invalid_zero_negative(self, text_engine):
        """Test limit validation with zero and negative values."""
        assert text_engine._validate_limit(0) == DEFAULT_SEARCH_LIMIT
        assert text_engine._validate_limit(-5) == DEFAULT_SEARCH_LIMIT

    def test_validate_limit_exceeds_max(self, text_engine):
        """Test limit validation when exceeding maximum."""
        assert text_engine._validate_limit(MAX_SEARCH_LIMIT + 1) == MAX_SEARCH_LIMIT
        assert text_engine._validate_limit(9999) == MAX_SEARCH_LIMIT


class TestTextSearchEngineDialogueSearch:
    """Test TextSearchEngine dialogue search functionality."""

    @pytest.mark.asyncio
    async def test_search_dialogue_basic(self, text_engine, mock_connection):
        """Test basic dialogue search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "This is a test dialogue line",
                "character_name": "Bob",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "EXT. STREET - DAY",
                "script_order": 5,
            }
        ]

        results = await text_engine.search_dialogue("test")

        assert len(results) == 1
        result = results[0]
        assert result["id"] == "d1"
        assert result["type"] == "dialogue"
        assert result["content"] == "This is a test dialogue line"
        assert result["metadata"]["character"] == "Bob"
        assert result["metadata"]["scene_id"] == "s1"
        assert result["metadata"]["scene_heading"] == "EXT. STREET - DAY"
        assert result["metadata"]["script_order"] == 5
        assert result["metadata"]["element_order"] == 1
        assert result["score"] > 0
        assert isinstance(result["highlights"], list)

    @pytest.mark.asyncio
    async def test_search_dialogue_with_character_filter(
        self, text_engine, mock_connection
    ):
        """Test dialogue search with character filter."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_dialogue("hello", filters={"character": "Alice"})

        # Verify SQL parameters include character filter
        call_args = mock_connection.fetch_all.call_args
        assert "Alice" in call_args[0][1]  # Parameters tuple

    @pytest.mark.asyncio
    async def test_search_dialogue_with_scene_filter(
        self, text_engine, mock_connection
    ):
        """Test dialogue search with scene filter."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_dialogue("hello", filters={"scene_id": "s1"})

        # Verify SQL parameters include scene filter
        call_args = mock_connection.fetch_all.call_args
        assert "s1" in call_args[0][1]  # Parameters tuple

    @pytest.mark.asyncio
    async def test_search_dialogue_empty_query(self, text_engine, mock_connection):
        """Test dialogue search with empty query."""
        mock_connection.fetch_all.return_value = []

        results = await text_engine.search_dialogue("")

        # Should still work but with no text filter
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_dialogue_limit_validation(self, text_engine, mock_connection):
        """Test dialogue search with invalid limit."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_dialogue("test", limit=-1)

        # Should use default limit
        call_args = mock_connection.fetch_all.call_args
        # Last parameter is limit
        assert call_args[0][1][-1] == DEFAULT_SEARCH_LIMIT


class TestTextSearchEngineActionSearch:
    """Test TextSearchEngine action search functionality."""

    @pytest.mark.asyncio
    async def test_search_action_basic(self, text_engine, mock_connection):
        """Test basic action search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "a1",
                "content": "The door slowly opens",
                "order_in_scene": 2,
                "scene_id": "s1",
                "scene_heading": "INT. HALLWAY - NIGHT",
                "script_order": 10,
            }
        ]

        results = await text_engine.search_action("door")

        assert len(results) == 1
        result = results[0]
        assert result["id"] == "a1"
        assert result["type"] == "action"
        assert result["content"] == "The door slowly opens"
        assert result["metadata"]["scene_id"] == "s1"
        assert result["metadata"]["scene_heading"] == "INT. HALLWAY - NIGHT"
        assert result["metadata"]["script_order"] == 10
        assert result["metadata"]["element_order"] == 2
        assert result["score"] > 0

    @pytest.mark.asyncio
    async def test_search_action_with_scene_filter(self, text_engine, mock_connection):
        """Test action search with scene filter."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_action("door", filters={"scene_id": "s2"})

        # Verify SQL parameters include scene filter
        call_args = mock_connection.fetch_all.call_args
        assert "s2" in call_args[0][1]


class TestTextSearchEngineFullTextSearch:
    """Test TextSearchEngine full-text search functionality."""

    @pytest.mark.asyncio
    async def test_search_full_text(self, text_engine):
        """Test full-text search combines all search types."""
        from unittest.mock import patch

        with (
            patch.object(
                text_engine,
                "search_dialogue",
                return_value=[
                    {
                        "id": "d1",
                        "type": "dialogue",
                        "content": "test dialogue",
                        "score": 0.8,
                        "metadata": {},
                        "highlights": [],
                    }
                ],
            ),
            patch.object(
                text_engine,
                "search_action",
                return_value=[
                    {
                        "id": "a1",
                        "type": "action",
                        "content": "test action",
                        "score": 0.7,
                        "metadata": {},
                        "highlights": [],
                    }
                ],
            ),
            patch.object(
                text_engine,
                "search_scenes",
                return_value=[
                    {
                        "id": "s1",
                        "type": "scene",
                        "content": "test scene",
                        "score": 0.9,
                        "metadata": {},
                        "highlights": [],
                    }
                ],
            ),
        ):
            results = await text_engine.search_full_text("test", limit=10)

            # Should combine all results and sort by score
            assert len(results) == 3
            assert results[0]["score"] >= results[1]["score"] >= results[2]["score"]
            assert results[0]["id"] == "s1"  # Highest score

    @pytest.mark.asyncio
    async def test_search_full_text_respects_limit(self, text_engine):
        """Test full-text search respects limit parameter."""
        from unittest.mock import patch

        # Create many results to test limit
        dialogue_results = [
            {
                "id": f"d{i}",
                "type": "dialogue",
                "content": f"dialogue {i}",
                "score": 0.8,
                "metadata": {},
                "highlights": [],
            }
            for i in range(5)
        ]
        action_results = [
            {
                "id": f"a{i}",
                "type": "action",
                "content": f"action {i}",
                "score": 0.7,
                "metadata": {},
                "highlights": [],
            }
            for i in range(5)
        ]
        scene_results = [
            {
                "id": f"s{i}",
                "type": "scene",
                "content": f"scene {i}",
                "score": 0.6,
                "metadata": {},
                "highlights": [],
            }
            for i in range(5)
        ]

        with (
            patch.object(text_engine, "search_dialogue", return_value=dialogue_results),
            patch.object(text_engine, "search_action", return_value=action_results),
            patch.object(text_engine, "search_scenes", return_value=scene_results),
        ):
            results = await text_engine.search_full_text("test", limit=3)

            assert len(results) == 3


class TestTextSearchEngineEntitySearch:
    """Test TextSearchEngine entity search functionality."""

    @pytest.mark.asyncio
    async def test_search_entities_characters(self, text_engine, mock_connection):
        """Test character entity search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "c1",
                "name": "John Smith",
                "description": "Main character",
                "first_appearance_scene_id": "s1",
            }
        ]
        mock_connection.fetch_one.return_value = {"count": 15}

        results = await text_engine.search_entities("John", "character")

        assert len(results) == 1
        result = results[0]
        assert result["id"] == "c1"
        assert result["type"] == "character"
        assert result["content"] == "John Smith"
        assert result["metadata"]["description"] == "Main character"
        assert result["metadata"]["first_appearance_scene_id"] == "s1"
        assert result["metadata"]["appearance_count"] == 15

    @pytest.mark.asyncio
    async def test_search_entities_locations(self, text_engine, mock_connection):
        """Test location entity search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "l1",
                "name": "Coffee Shop",
                "description": "Local coffee shop",
                "first_appearance_scene_id": "s2",
            }
        ]
        mock_connection.fetch_one.return_value = {"count": 8}

        results = await text_engine.search_entities("Coffee", "location")

        assert len(results) == 1
        result = results[0]
        assert result["type"] == "location"
        assert result["content"] == "Coffee Shop"

    @pytest.mark.asyncio
    async def test_search_entities_unknown_type(self, text_engine, mock_connection):
        """Test entity search with unknown entity type."""
        results = await text_engine.search_entities("test", "unknown_type")

        assert results == []
        mock_connection.fetch_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_entities_invalid_table(self, text_engine):
        """Test entity search prevents SQL injection."""
        from unittest.mock import patch

        # Mock an entity type that maps to invalid table
        with patch.dict(
            "scriptrag.search.text_search.VALID_ENTITY_TABLES",
            {"malicious": "invalid_table"},
        ):
            results = await text_engine.search_entities("test", "malicious")

            # Should return empty results for security
            assert results == []

    @pytest.mark.asyncio
    async def test_search_entities_empty_query(self, text_engine, mock_connection):
        """Test entity search with empty query."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "c1",
                "name": "All Characters",
                "description": "Test",
                "first_appearance_scene_id": "s1",
            }
        ]
        mock_connection.fetch_one.return_value = {"count": 5}

        results = await text_engine.search_entities("", "character")

        # Should still work, returning all entities
        assert len(results) == 1


class TestTextSearchEngineSceneSearch:
    """Test TextSearchEngine scene search functionality."""

    @pytest.mark.asyncio
    async def test_search_scenes_basic(self, text_engine, mock_connection):
        """Test basic scene search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. OFFICE - DAY",
                "script_order": 1,
                "description": "A busy office environment",
                "time_of_day": "DAY",
                "location_type": "INT",
                "story_time": None,
            }
        ]

        results = await text_engine.search_scenes("office")

        assert len(results) == 1
        result = results[0]
        assert result["id"] == "s1"
        assert result["type"] == "scene"
        assert result["content"] == "INT. OFFICE - DAY"
        assert result["metadata"]["script_order"] == 1
        assert result["metadata"]["description"] == "A busy office environment"
        assert result["metadata"]["time_of_day"] == "DAY"
        assert result["metadata"]["location_type"] == "INT"

    @pytest.mark.asyncio
    async def test_search_scenes_with_location_filter(
        self, text_engine, mock_connection
    ):
        """Test scene search with location filter."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_scenes("office", filters={"location": "loc1"})

        # Verify SQL includes location filter
        call_args = mock_connection.fetch_all.call_args
        sql_query = call_args[0][0]
        assert "scene_locations" in sql_query
        assert "location_id" in sql_query

    @pytest.mark.asyncio
    async def test_search_scenes_with_character_filter(
        self, text_engine, mock_connection
    ):
        """Test scene search with character filter."""
        mock_connection.fetch_all.return_value = []

        await text_engine.search_scenes("office", filters={"character": "char1"})

        # Verify SQL includes character filter
        call_args = mock_connection.fetch_all.call_args
        sql_query = call_args[0][0]
        assert "scene_characters" in sql_query
        assert "character_id" in sql_query

    @pytest.mark.asyncio
    async def test_search_scenes_description_match(self, text_engine, mock_connection):
        """Test scene search matches both heading and description."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. ROOM - DAY",
                "script_order": 1,
                "description": "An office setting with modern decor",
                "time_of_day": "DAY",
                "location_type": "INT",
                "story_time": None,
            }
        ]

        results = await text_engine.search_scenes("office")

        # Should find match in description even if not in heading
        assert len(results) == 1
        assert len(results[0]["highlights"]) > 0


class TestTextSearchEngineScoring:
    """Test TextSearchEngine scoring and highlighting."""

    def test_calculate_text_score_exact_match(self, text_engine):
        """Test text scoring for exact matches."""
        score = text_engine._calculate_text_score("test", "test")
        assert score == 1.0

    def test_calculate_text_score_whole_word_match(self, text_engine):
        """Test text scoring for whole word matches."""
        score = text_engine._calculate_text_score("test", "This is a test case")
        assert 0.8 <= score <= 1.0

    def test_calculate_text_score_substring_match(self, text_engine):
        """Test text scoring for substring matches."""
        score = text_engine._calculate_text_score("test", "testing 123")
        assert 0.5 <= score <= 0.9

    def test_calculate_text_score_partial_word_match(self, text_engine):
        """Test text scoring for partial word matches."""
        score = text_engine._calculate_text_score("hello world", "hello there friend")
        assert 0.1 <= score <= 0.5  # Partial match

    def test_calculate_text_score_no_match(self, text_engine):
        """Test text scoring for no matches."""
        score = text_engine._calculate_text_score("test", "nothing here")
        assert score == 0.0

    def test_calculate_text_score_empty_inputs(self, text_engine):
        """Test text scoring with empty inputs."""
        assert text_engine._calculate_text_score("", "content") == 0.0
        assert text_engine._calculate_text_score("query", "") == 0.0
        assert text_engine._calculate_text_score("", "") == 0.0

    def test_calculate_text_score_case_insensitive(self, text_engine):
        """Test text scoring is case insensitive."""
        score1 = text_engine._calculate_text_score("TEST", "test content")
        score2 = text_engine._calculate_text_score("test", "TEST CONTENT")
        assert score1 == score2
        assert score1 > 0

    def test_calculate_text_score_frequency_boost(self, text_engine):
        """Test scoring considers frequency of matches."""
        single_match = text_engine._calculate_text_score("test", "test content")
        multiple_match = text_engine._calculate_text_score(
            "test", "test content test again test more"
        )

        assert multiple_match >= single_match

    def test_calculate_text_score_position_boost(self, text_engine):
        """Test scoring considers position of matches."""
        early_match = text_engine._calculate_text_score("test", "test content here")
        late_match = text_engine._calculate_text_score("test", "some content here test")

        assert early_match >= late_match


class TestTextSearchEngineHighlighting:
    """Test TextSearchEngine highlight extraction."""

    def test_extract_highlights_basic(self, text_engine):
        """Test basic highlight extraction."""
        content = "This is a test sentence with test word repeated."
        highlights = text_engine._extract_highlights("test", content)

        assert len(highlights) >= 1
        assert all("test" in highlight.lower() for highlight in highlights)

    def test_extract_highlights_context(self, text_engine):
        """Test highlight extraction includes context."""
        content = "The quick brown fox jumps over the lazy dog and runs fast."
        highlights = text_engine._extract_highlights("fox", content, context_length=10)

        assert len(highlights) >= 1
        highlight = highlights[0]
        assert "fox" in highlight.lower()
        # Should include some context around the match
        assert len(highlight) > len("fox")

    def test_extract_highlights_word_boundaries(self, text_engine):
        """Test highlight extraction respects word boundaries."""
        content = (
            "This is a very long sentence that needs to be truncated at "
            "word boundaries for highlights."
        )
        highlights = text_engine._extract_highlights("long", content, context_length=20)

        assert len(highlights) >= 1
        highlight = highlights[0]
        # Should not cut words in half
        assert not highlight.startswith(" ") or highlight.startswith("...")
        assert not highlight.endswith(" ") or highlight.endswith("...")

    def test_extract_highlights_multiple_matches(self, text_engine):
        """Test highlight extraction for multiple matches."""
        content = "Test content with test word and another test occurrence."
        highlights = text_engine._extract_highlights("test", content)

        assert len(highlights) >= 2  # Should find multiple matches
        assert all("test" in highlight.lower() for highlight in highlights)

    def test_extract_highlights_limit(self, text_engine):
        """Test highlight extraction respects limit."""
        content = " ".join(["test content"] * 10)  # Many matches
        highlights = text_engine._extract_highlights("test", content)

        assert len(highlights) <= 3  # Should be limited

    def test_extract_highlights_empty_inputs(self, text_engine):
        """Test highlight extraction with empty inputs."""
        assert text_engine._extract_highlights("", "content") == []
        assert text_engine._extract_highlights("query", "") == []
        assert text_engine._extract_highlights("", "") == []

    def test_extract_highlights_no_match(self, text_engine):
        """Test highlight extraction when no matches found."""
        highlights = text_engine._extract_highlights("xyz", "content without match")
        assert highlights == []

    def test_extract_highlights_ellipsis(self, text_engine):
        """Test highlight extraction adds ellipsis appropriately."""
        long_content = (
            "This is a very long piece of content " * 10 + "test" + " more content" * 10
        )
        highlights = text_engine._extract_highlights(
            "test", long_content, context_length=20
        )

        assert len(highlights) >= 1
        highlight = highlights[0]
        # Should have ellipsis at start and/or end due to truncation
        assert highlight.startswith("...") or highlight.endswith("...")


class TestTextSearchEngineEntityAppearances:
    """Test TextSearchEngine entity appearance counting."""

    def test_get_entity_appearance_count_character(self, text_engine, mock_connection):
        """Test getting character appearance count."""
        mock_connection.fetch_one.return_value = {"count": 12}

        count = text_engine._get_entity_appearance_count("character", "c1")

        assert count == 12
        # Verify correct table and column used
        call_args = mock_connection.fetch_one.call_args
        sql_query = call_args[0][0]
        assert "scene_characters" in sql_query
        assert "character_id" in sql_query

    def test_get_entity_appearance_count_location(self, text_engine, mock_connection):
        """Test getting location appearance count."""
        mock_connection.fetch_one.return_value = {"count": 8}

        count = text_engine._get_entity_appearance_count("location", "l1")

        assert count == 8
        # Verify correct table and column used
        call_args = mock_connection.fetch_one.call_args
        sql_query = call_args[0][0]
        assert "scene_locations" in sql_query
        assert "location_id" in sql_query

    def test_get_entity_appearance_count_object(self, text_engine, mock_connection):
        """Test getting object appearance count."""
        mock_connection.fetch_one.return_value = {"count": 3}

        count = text_engine._get_entity_appearance_count("object", "o1")

        assert count == 3
        # Verify correct table and column used
        call_args = mock_connection.fetch_one.call_args
        sql_query = call_args[0][0]
        assert "scene_objects" in sql_query
        assert "object_id" in sql_query

    def test_get_entity_appearance_count_unknown_type(
        self, text_engine, mock_connection
    ):
        """Test getting appearance count for unknown entity type."""
        count = text_engine._get_entity_appearance_count("unknown", "id1")

        assert count == 0
        mock_connection.fetch_one.assert_not_called()

    def test_get_entity_appearance_count_no_result(self, text_engine, mock_connection):
        """Test getting appearance count when query returns no result."""
        mock_connection.fetch_one.return_value = None

        count = text_engine._get_entity_appearance_count("character", "c1")

        assert count == 0


class TestTextSearchEngineEdgeCases:
    """Test TextSearchEngine edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_search_with_sql_injection_attempt(
        self, text_engine, mock_connection
    ):
        """Test search handles potential SQL injection attempts."""
        malicious_query = "'; DROP TABLE scenes; --"
        mock_connection.fetch_all.return_value = []

        # Should not crash and should use parameterized queries
        results = await text_engine.search_dialogue(malicious_query)

        assert isinstance(results, list)
        # Verify parameterized query was used
        call_args = mock_connection.fetch_all.call_args
        assert "DROP TABLE" not in call_args[0][0]  # Not in SQL string

    @pytest.mark.asyncio
    async def test_search_with_unicode_content(self, text_engine, mock_connection):
        """Test search handles unicode content properly."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "Café naïve résumé 你好",
                "character_name": "François",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. CAFÉ - DAY",
                "script_order": 1,
            }
        ]

        results = await text_engine.search_dialogue("café")

        assert len(results) == 1
        assert "Café" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_with_very_long_query(self, text_engine, mock_connection):
        """Test search handles very long queries."""
        long_query = "test " * 1000  # Very long query
        mock_connection.fetch_all.return_value = []

        results = await text_engine.search_dialogue(long_query)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self, text_engine, mock_connection):
        """Test search handles special regex characters."""
        special_query = ".*+?^${}()|[]\\test"
        mock_connection.fetch_all.return_value = []

        # Should not crash due to regex errors
        results = await text_engine.search_dialogue(special_query)

        assert isinstance(results, list)
