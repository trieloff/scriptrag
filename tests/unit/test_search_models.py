"""Comprehensive unit tests for search models."""

from unittest.mock import Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class TestSearchMode:
    """Test SearchMode enumeration."""

    def test_search_mode_values(self) -> None:
        """Test all SearchMode enum values."""
        assert SearchMode.STRICT == "strict"
        assert SearchMode.FUZZY == "fuzzy"
        assert SearchMode.AUTO == "auto"

    def test_search_mode_inheritance(self) -> None:
        """Test SearchMode inherits from str and Enum."""
        assert isinstance(SearchMode.STRICT, str)
        assert hasattr(SearchMode, "__members__")
        assert (
            len(SearchMode.__members__) == 6
        )  # STRICT, FUZZY, AUTO, SCENE, CHARACTER, DIALOGUE

    def test_search_mode_comparison(self) -> None:
        """Test SearchMode string comparison."""
        assert SearchMode.STRICT == "strict"
        assert SearchMode.STRICT != "fuzzy"
        assert SearchMode.FUZZY in ["fuzzy", "auto"]


class TestSearchQuery:
    """Test SearchQuery dataclass functionality."""

    def test_default_initialization(self) -> None:
        """Test SearchQuery with minimal initialization."""
        query = SearchQuery(raw_query="test query")

        assert query.raw_query == "test query"
        assert query.text_query is None
        assert query.characters == []
        assert query.locations == []
        assert query.dialogue is None
        assert query.parenthetical is None
        assert query.action is None
        assert query.project is None
        assert query.season_start is None
        assert query.season_end is None
        assert query.episode_start is None
        assert query.episode_end is None
        assert query.mode == SearchMode.AUTO
        assert query.limit == 5
        assert query.offset == 0

    def test_full_initialization(self) -> None:
        """Test SearchQuery with all fields populated."""
        query = SearchQuery(
            raw_query="original query",
            text_query="processed query",
            characters=["SHERLOCK", "WATSON"],
            locations=["BAKER STREET", "SCOTLAND YARD"],
            dialogue="Elementary, my dear Watson",
            parenthetical="confidently",
            action="deduces the solution",
            project="The Great Detective",
            season_start=1,
            season_end=2,
            episode_start=3,
            episode_end=8,
            mode=SearchMode.STRICT,
            limit=10,
            offset=15,
        )

        assert query.raw_query == "original query"
        assert query.text_query == "processed query"
        assert query.characters == ["SHERLOCK", "WATSON"]
        assert query.locations == ["BAKER STREET", "SCOTLAND YARD"]
        assert query.dialogue == "Elementary, my dear Watson"
        assert query.parenthetical == "confidently"
        assert query.action == "deduces the solution"
        assert query.project == "The Great Detective"
        assert query.season_start == 1
        assert query.season_end == 2
        assert query.episode_start == 3
        assert query.episode_end == 8
        assert query.mode == SearchMode.STRICT
        assert query.limit == 10
        assert query.offset == 15

    def test_list_fields_are_independent(self) -> None:
        """Test that list fields don't share references between instances."""
        query1 = SearchQuery(raw_query="query1")
        query2 = SearchQuery(raw_query="query2")

        query1.characters.append("SHERLOCK")
        query1.locations.append("BAKER STREET")

        assert query1.characters == ["SHERLOCK"]
        assert query1.locations == ["BAKER STREET"]
        assert query2.characters == []
        assert query2.locations == []

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_strict_mode(self, mock_get_settings) -> None:
        """Test needs_vector_search returns False for STRICT mode."""
        query = SearchQuery(
            raw_query="any query text here",
            text_query="very long query with many words that exceeds threshold",
            mode=SearchMode.STRICT,
        )

        # Should not call get_settings for strict mode
        assert not query.needs_vector_search
        mock_get_settings.assert_not_called()

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_fuzzy_mode(self, mock_get_settings) -> None:
        """Test needs_vector_search returns True for FUZZY mode."""
        query = SearchQuery(
            raw_query="short query", text_query="short", mode=SearchMode.FUZZY
        )

        # Should not call get_settings for fuzzy mode
        assert query.needs_vector_search
        mock_get_settings.assert_not_called()

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_below_threshold(
        self, mock_get_settings
    ) -> None:
        """Test needs_vector_search with AUTO mode below threshold."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 10
        mock_get_settings.return_value = mock_settings

        # Test with dialogue (8 words < 10 threshold)
        query = SearchQuery(
            raw_query="test",
            dialogue="short dialogue with exactly eight words total here",
            mode=SearchMode.AUTO,
        )

        assert not query.needs_vector_search
        mock_get_settings.assert_called_once()

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_above_threshold(
        self, mock_get_settings
    ) -> None:
        """Test needs_vector_search with AUTO mode above threshold."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 5
        mock_get_settings.return_value = mock_settings

        # Test with action (12 words > 5 threshold)
        query = SearchQuery(
            raw_query="test",
            action=(
                "very long action description with many detailed words "
                "explaining the scene thoroughly"
            ),
            mode=SearchMode.AUTO,
        )

        assert query.needs_vector_search
        mock_get_settings.assert_called_once()

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_text_query(self, mock_get_settings) -> None:
        """Test needs_vector_search prioritizes dialogue/action over text_query."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 3
        mock_get_settings.return_value = mock_settings

        # Test with both text_query and dialogue - should use dialogue
        query = SearchQuery(
            raw_query="test",
            text_query="very long text query with many words",
            dialogue="short dialogue",  # 2 words < 3 threshold
            mode=SearchMode.AUTO,
        )

        assert not query.needs_vector_search

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_fallback_to_text_query(
        self, mock_get_settings
    ) -> None:
        """Test needs_vector_search falls back to text_query.

        When dialogue/action are absent, should use text_query for evaluation.
        """
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 3
        mock_get_settings.return_value = mock_settings

        # Test with only text_query (5 words > 3 threshold)
        query = SearchQuery(
            raw_query="test", text_query="this is a longer query", mode=SearchMode.AUTO
        )

        assert query.needs_vector_search

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_empty_query(self, mock_get_settings) -> None:
        """Test needs_vector_search with empty or None query text."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 1
        mock_get_settings.return_value = mock_settings

        # Test with all None values
        query = SearchQuery(
            raw_query="test",
            dialogue=None,
            action=None,
            text_query=None,
            mode=SearchMode.AUTO,
        )

        assert not query.needs_vector_search

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_priority_order(
        self, mock_get_settings
    ) -> None:
        """Test needs_vector_search priority: dialogue > action > text_query."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 3
        mock_get_settings.return_value = mock_settings

        # Test priority: dialogue wins even with longer action
        query = SearchQuery(
            raw_query="test",
            dialogue="two words",  # 2 words < 3 threshold
            action="very long action description with many words",  # Would exceed
            text_query="also very long text query here",  # Would exceed
            mode=SearchMode.AUTO,
        )

        # Should use dialogue (shortest), not action or text_query
        assert not query.needs_vector_search

    @patch("scriptrag.search.models.get_settings")
    def test_needs_vector_search_auto_mode_action_priority(
        self, mock_get_settings
    ) -> None:
        """Test needs_vector_search uses action when dialogue is None."""
        mock_settings = Mock(spec=ScriptRAGSettings)
        mock_settings.search_vector_threshold = 2
        mock_get_settings.return_value = mock_settings

        # Test action priority over text_query
        query = SearchQuery(
            raw_query="test",
            dialogue=None,
            action="short action",  # 2 words = 2 threshold (not greater)
            text_query="much longer text query here",  # Would exceed threshold
            mode=SearchMode.AUTO,
        )

        # Should use action, not text_query
        assert not query.needs_vector_search

    def test_dataclass_equality(self) -> None:
        """Test SearchQuery equality comparison."""
        query1 = SearchQuery(
            raw_query="test", text_query="processed", characters=["SHERLOCK"]
        )
        query2 = SearchQuery(
            raw_query="test", text_query="processed", characters=["SHERLOCK"]
        )
        query3 = SearchQuery(
            raw_query="different", text_query="processed", characters=["SHERLOCK"]
        )

        assert query1 == query2
        assert query1 != query3

    def test_dataclass_repr(self) -> None:
        """Test SearchQuery string representation."""
        query = SearchQuery(raw_query="test query", mode=SearchMode.STRICT)

        repr_str = repr(query)
        assert "SearchQuery" in repr_str
        assert "raw_query='test query'" in repr_str
        strict_mode_pattern = (
            "mode=<SearchMode.STRICT: 'strict'>" in repr_str
            or "mode='strict'" in repr_str
        )
        assert strict_mode_pattern


class TestSearchResult:
    """Test SearchResult dataclass functionality."""

    def test_minimal_initialization(self) -> None:
        """Test SearchResult with required fields only."""
        result = SearchResult(
            script_id=1,
            script_title="The Great Detective",
            script_author="Arthur Conan Doyle",
            scene_id=42,
            scene_number=1,
            scene_heading="INT. BAKER STREET - DAY",
            scene_location="Baker Street",
            scene_time="Day",
            scene_content="SHERLOCK examines the evidence.",
        )

        assert result.script_id == 1
        assert result.script_title == "The Great Detective"
        assert result.script_author == "Arthur Conan Doyle"
        assert result.scene_id == 42
        assert result.scene_number == 1
        assert result.scene_heading == "INT. BAKER STREET - DAY"
        assert result.scene_location == "Baker Street"
        assert result.scene_time == "Day"
        assert result.scene_content == "SHERLOCK examines the evidence."

        # Test default values
        assert result.season is None
        assert result.episode is None
        assert result.match_type == "text"
        assert result.relevance_score == 1.0
        assert result.matched_text is None
        assert result.character_name is None

    def test_full_initialization(self) -> None:
        """Test SearchResult with all fields populated."""
        result = SearchResult(
            script_id=123,
            script_title="Sherlock Chronicles",
            script_author="Arthur Conan Doyle",
            scene_id=456,
            scene_number=7,
            scene_heading="EXT. SCOTLAND YARD - NIGHT",
            scene_location="Scotland Yard",
            scene_time="Night",
            scene_content="The inspector reviews the case files.",
            season=2,
            episode=8,
            match_type="dialogue",
            relevance_score=0.87,
            matched_text="reviews the case files",
            character_name="INSPECTOR LESTRADE",
        )

        assert result.script_id == 123
        assert result.script_title == "Sherlock Chronicles"
        assert result.script_author == "Arthur Conan Doyle"
        assert result.scene_id == 456
        assert result.scene_number == 7
        assert result.scene_heading == "EXT. SCOTLAND YARD - NIGHT"
        assert result.scene_location == "Scotland Yard"
        assert result.scene_time == "Night"
        assert result.scene_content == "The inspector reviews the case files."
        assert result.season == 2
        assert result.episode == 8
        assert result.match_type == "dialogue"
        assert result.relevance_score == 0.87
        assert result.matched_text == "reviews the case files"
        assert result.character_name == "INSPECTOR LESTRADE"

    def test_none_author(self) -> None:
        """Test SearchResult with None author."""
        result = SearchResult(
            script_id=1,
            script_title="Anonymous Script",
            script_author=None,
            scene_id=1,
            scene_number=1,
            scene_heading="INT. ROOM - DAY",
            scene_location=None,
            scene_time=None,
            scene_content="Someone does something.",
        )

        assert result.script_author is None
        assert result.scene_location is None
        assert result.scene_time is None

    def test_match_type_variations(self) -> None:
        """Test different match_type values."""
        base_kwargs = {
            "script_id": 1,
            "script_title": "Test",
            "script_author": "Test Author",
            "scene_id": 1,
            "scene_number": 1,
            "scene_heading": "INT. TEST - DAY",
            "scene_location": "Test Location",
            "scene_time": "Day",
            "scene_content": "Test content.",
        }

        for match_type in ["text", "dialogue", "action", "vector"]:
            result = SearchResult(**base_kwargs, match_type=match_type)
            assert result.match_type == match_type

    def test_relevance_score_range(self) -> None:
        """Test different relevance_score values."""
        base_kwargs = {
            "script_id": 1,
            "script_title": "Test",
            "script_author": "Test Author",
            "scene_id": 1,
            "scene_number": 1,
            "scene_heading": "INT. TEST - DAY",
            "scene_location": "Test Location",
            "scene_time": "Day",
            "scene_content": "Test content.",
        }

        for score in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]:
            result = SearchResult(**base_kwargs, relevance_score=score)
            assert result.relevance_score == score

    def test_dataclass_equality(self) -> None:
        """Test SearchResult equality comparison."""
        kwargs = {
            "script_id": 1,
            "script_title": "Test",
            "script_author": "Author",
            "scene_id": 1,
            "scene_number": 1,
            "scene_heading": "INT. TEST - DAY",
            "scene_location": "Location",
            "scene_time": "Day",
            "scene_content": "Content",
        }

        result1 = SearchResult(**kwargs)
        result2 = SearchResult(**kwargs)
        result3 = SearchResult(**kwargs, relevance_score=0.5)

        assert result1 == result2
        assert result1 != result3

    def test_dataclass_repr(self) -> None:
        """Test SearchResult string representation."""
        result = SearchResult(
            script_id=42,
            script_title="The Great Detective",
            script_author="Doyle",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. ROOM - DAY",
            scene_location="Room",
            scene_time="Day",
            scene_content="Content",
        )

        repr_str = repr(result)
        assert "SearchResult" in repr_str
        assert "script_id=42" in repr_str
        assert "script_title='The Great Detective'" in repr_str


class TestSearchResponse:
    """Test SearchResponse dataclass functionality."""

    def test_minimal_initialization(self) -> None:
        """Test SearchResponse with required fields only."""
        query = SearchQuery(raw_query="test")
        results = [
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Test Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. TEST - DAY",
                scene_location="Test",
                scene_time="Day",
                scene_content="Test content.",
            )
        ]

        response = SearchResponse(
            query=query, results=results, total_count=1, has_more=False
        )

        assert response.query == query
        assert response.results == results
        assert response.total_count == 1
        assert not response.has_more

        # Test default values
        assert response.execution_time_ms is None
        assert response.search_methods == []
        assert response.metadata == {}

    def test_full_initialization(self) -> None:
        """Test SearchResponse with all fields populated."""
        query = SearchQuery(raw_query="comprehensive test")
        results = [
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Test Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. TEST - DAY",
                scene_location="Test",
                scene_time="Day",
                scene_content="Test content.",
            )
        ]

        response = SearchResponse(
            query=query,
            results=results,
            total_count=50,
            has_more=True,
            execution_time_ms=123.45,
            search_methods=["text", "vector"],
            metadata={"debug": True, "source": "test"},
        )

        assert response.query == query
        assert response.results == results
        assert response.total_count == 50
        assert response.has_more
        assert response.execution_time_ms == 123.45
        assert response.search_methods == ["text", "vector"]
        assert response.metadata == {"debug": True, "source": "test"}

    def test_empty_results(self) -> None:
        """Test SearchResponse with empty results."""
        query = SearchQuery(raw_query="no matches")

        response = SearchResponse(
            query=query, results=[], total_count=0, has_more=False
        )

        assert response.results == []
        assert response.total_count == 0
        assert not response.has_more

    def test_list_fields_are_independent(self) -> None:
        """Test that list/dict fields don't share references between instances."""
        query1 = SearchQuery(raw_query="query1")
        query2 = SearchQuery(raw_query="query2")

        response1 = SearchResponse(
            query=query1, results=[], total_count=0, has_more=False
        )
        response2 = SearchResponse(
            query=query2, results=[], total_count=0, has_more=False
        )

        response1.search_methods.append("text")
        response1.metadata["test"] = "value"

        assert response1.search_methods == ["text"]
        assert response1.metadata == {"test": "value"}
        assert response2.search_methods == []
        assert response2.metadata == {}

    def test_pagination_has_more_logic(self) -> None:
        """Test different has_more scenarios."""
        query = SearchQuery(raw_query="test")

        # Case 1: No more results
        response_no_more = SearchResponse(
            query=query, results=[], total_count=0, has_more=False
        )
        assert not response_no_more.has_more

        # Case 2: Has more results
        response_has_more = SearchResponse(
            query=query, results=[], total_count=100, has_more=True
        )
        assert response_has_more.has_more

    def test_execution_time_precision(self) -> None:
        """Test execution_time_ms with various precision values."""
        query = SearchQuery(raw_query="test")

        for time_ms in [0.1, 1.23, 12.345, 123.4567, 1234.0]:
            response = SearchResponse(
                query=query,
                results=[],
                total_count=0,
                has_more=False,
                execution_time_ms=time_ms,
            )
            assert response.execution_time_ms == time_ms

    def test_dataclass_equality(self) -> None:
        """Test SearchResponse equality comparison."""
        query = SearchQuery(raw_query="test")

        response1 = SearchResponse(
            query=query, results=[], total_count=5, has_more=True
        )
        response2 = SearchResponse(
            query=query, results=[], total_count=5, has_more=True
        )
        response3 = SearchResponse(
            query=query,
            results=[],
            total_count=10,  # Different total_count
            has_more=True,
        )

        assert response1 == response2
        assert response1 != response3

    def test_dataclass_repr(self) -> None:
        """Test SearchResponse string representation."""
        query = SearchQuery(raw_query="test query")

        response = SearchResponse(
            query=query, results=[], total_count=42, has_more=True
        )

        repr_str = repr(response)
        assert "SearchResponse" in repr_str
        assert "total_count=42" in repr_str
        assert "has_more=True" in repr_str


@pytest.mark.parametrize(
    "mode,dialogue,action,text_query,threshold,expected",
    [
        # STRICT mode - always False
        (SearchMode.STRICT, "any text here", None, None, 1, False),
        (SearchMode.STRICT, None, "any action here", None, 1, False),
        (SearchMode.STRICT, None, None, "any query here", 1, False),
        # FUZZY mode - always True
        (SearchMode.FUZZY, "short", None, None, 10, True),
        (SearchMode.FUZZY, None, "short", None, 10, True),
        (SearchMode.FUZZY, None, None, "short", 10, True),
        # AUTO mode - threshold-based
        (SearchMode.AUTO, "short text", None, None, 3, False),  # 2 <= 3
        (SearchMode.AUTO, "this is longer text", None, None, 3, True),  # 4 > 3
        (SearchMode.AUTO, None, "short action", None, 3, False),  # 2 <= 3
        (SearchMode.AUTO, None, "this is longer action", None, 3, True),  # 4 > 3
        (SearchMode.AUTO, None, None, "short query", 3, False),  # 2 <= 3
        (SearchMode.AUTO, None, None, "this is longer query", 3, True),  # 4 > 3
        # AUTO mode priority: dialogue > action > text_query
        (
            SearchMode.AUTO,
            "short",
            "very long action text here",
            "very long query text here",
            2,
            False,
        ),  # Uses dialogue (1 <= 2)
        (
            SearchMode.AUTO,
            None,
            "short action",
            "very long query text here",
            2,
            False,
        ),  # Uses action (2 <= 2, so False)
        (
            SearchMode.AUTO,
            None,
            "short action",
            "very long query text here",
            1,
            True,
        ),  # Uses action (2 > 1)
        # Edge cases
        (SearchMode.AUTO, "", None, None, 1, False),  # Empty string
        (SearchMode.AUTO, None, None, None, 1, False),  # All None
        (SearchMode.AUTO, "   ", None, None, 1, False),  # Whitespace only
    ],
)
@patch("scriptrag.search.models.get_settings")
def test_needs_vector_search_parametrized(
    mock_get_settings,
    mode: SearchMode,
    dialogue: str | None,
    action: str | None,
    text_query: str | None,
    threshold: int,
    expected: bool,
) -> None:
    """Parametrized test for needs_vector_search logic."""
    mock_settings = Mock(spec=ScriptRAGSettings)
    mock_settings.search_vector_threshold = threshold
    mock_get_settings.return_value = mock_settings

    query = SearchQuery(
        raw_query="test",
        dialogue=dialogue,
        action=action,
        text_query=text_query,
        mode=mode,
    )

    result = query.needs_vector_search
    assert result == expected

    # Verify get_settings is only called for AUTO mode
    if mode == SearchMode.AUTO:
        mock_get_settings.assert_called_once()
    else:
        mock_get_settings.assert_not_called()
