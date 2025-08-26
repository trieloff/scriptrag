"""Tests for search result formatter."""

import json
from unittest.mock import MagicMock

from rich.console import Console

from scriptrag.search.formatter import ResultFormatter
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class TestResultFormatter:
    """Test ResultFormatter class."""

    def test_init_default(self):
        """Test initialization with default console."""
        formatter = ResultFormatter()
        assert isinstance(formatter.console, Console)

    def test_init_with_console(self):
        """Test initialization with provided console."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)
        assert formatter.console is console

    def test_format_results_no_results(self):
        """Test formatting when no results are found."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test", text_query="test")
        response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            has_more=False,
            execution_time_ms=10.5,
            search_methods=["sql"],
        )

        formatter.format_results(response)

        console.print.assert_called_once_with(
            "[yellow]No results found for your search.[/yellow]",
            style="bold",
        )

    def test_format_results_with_results(self):
        """Test formatting with search results."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test", dialogue="test dialogue")
        result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=10,
            scene_number=5,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="Test scene content",
            season=1,
            episode=2,
            match_type="dialogue",
        )

        response = SearchResponse(
            query=query,
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=15.3,
            search_methods=["sql"],
        )

        formatter.format_results(response)

        # Check that methods were called
        assert console.print.call_count >= 3  # Info, result, pagination

    def test_format_results_verbose(self):
        """Test verbose formatting."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test", action="fight")
        result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=10,
            scene_number=5,
            scene_heading="EXT. STREET - NIGHT",
            scene_location="STREET",
            scene_time="NIGHT",
            scene_content="A fight breaks out.",
            season=None,
            episode=None,
            match_type="action",
        )

        response = SearchResponse(
            query=query,
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=20.0,
            search_methods=["sql", "vector"],
        )

        formatter.format_results(response, verbose=True)

        # In verbose mode, more information should be displayed
        assert console.print.call_count >= 2

    def test_display_search_info(self):
        """Test search info display."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            characters=["JOHN", "JANE"],
            locations=["OFFICE"],
            project="TestProject",
            mode=SearchMode.FUZZY,
        )

        response = SearchResponse(
            query=query,
            results=[],
            total_count=5,
            has_more=True,
            execution_time_ms=25.5,
            search_methods=["sql", "vector"],
        )

        formatter._display_search_info(response)

        # Check that search info was printed
        console.print.assert_called()

    def test_display_result(self):
        """Test single result display."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        result = SearchResult(
            script_id=1,
            script_title="Breaking_Bad",
            script_author="Vince Gilligan",
            scene_id=100,
            scene_number=42,
            scene_heading="INT. RV - DAY",
            scene_location="RV",
            scene_time="DAY",
            scene_content="WALTER and JESSE cook.",
            season=1,
            episode=1,
            match_type="dialogue",
        )

        formatter._display_result(result, 1, verbose=False)

        # Should create a panel with the result
        console.print.assert_called()
        call_args = console.print.call_args
        assert call_args is not None

    def test_display_result_verbose(self):
        """Test verbose single result display."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        result = SearchResult(
            script_id=2,
            script_title="The Wire",
            script_author="David Simon",
            scene_id=200,
            scene_number=15,
            scene_heading="EXT. CORNER - NIGHT",
            scene_location="CORNER",
            scene_time="NIGHT",
            scene_content="Drug dealers on the corner.",
            season=1,
            episode=3,
            match_type="action",
        )

        formatter._display_result(result, 2, verbose=True)

        # In verbose mode, full scene content should be shown
        console.print.assert_called()

    def test_display_pagination_info(self):
        """Test pagination info display."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test", limit=5, offset=10)
        response = SearchResponse(
            query=query,
            results=[],
            total_count=50,
            has_more=True,
            execution_time_ms=30.0,
            search_methods=["sql"],
        )

        formatter._display_pagination_info(response)

        # Should show pagination info
        console.print.assert_called()
        call_args = console.print.call_args[0][0]
        assert "Showing" in call_args or "results" in call_args

    def test_format_json_output(self):
        """Test JSON output formatting."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test")
        result = SearchResult(
            script_id=1,
            script_title="Test",
            script_author="Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. ROOM - DAY",
            scene_location="ROOM",
            scene_time="DAY",
            scene_content="Content",
            season=1,
            episode=1,
            match_type="text",
        )

        response = SearchResponse(
            query=query,
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=10.0,
            search_methods=["sql"],
        )

        json_output = formatter.format_json(response)

        # Should return valid JSON string
        parsed = json.loads(json_output)
        assert "results" in parsed
        assert "total_count" in parsed
        assert "execution_time_ms" in parsed
        assert len(parsed["results"]) == 1

    def test_result_with_no_season_episode(self):
        """Test formatting result without season/episode info."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        result = SearchResult(
            script_id=1,
            script_title="Feature Film",
            script_author="Writer",
            scene_id=10,
            scene_number=5,
            scene_heading="INT. HOUSE - NIGHT",
            scene_location="HOUSE",
            scene_time="NIGHT",
            scene_content="Scene content",
            season=None,
            episode=None,
            match_type="text",
        )

        formatter._display_result(result, 1, verbose=False)

        # Should handle None season/episode gracefully
        console.print.assert_called()

    def test_multiple_search_methods(self):
        """Test display with multiple search methods."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="complex query", mode=SearchMode.FUZZY)
        response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            has_more=False,
            execution_time_ms=100.0,
            search_methods=["sql", "vector", "semantic"],
        )

        formatter._display_search_info(response)

        # Should show all search methods used
        console.print.assert_called()

    def test_complex_query_formatting(self):
        """Test formatting with complex query parameters."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(
            raw_query="complex",
            dialogue="hello world",
            characters=["WALTER", "JESSE", "SAUL"],
            locations=["LAB", "DESERT"],
            parenthetical="whispering",
            action="explosion",
            project="Breaking_Bad",
            season_start=1,
            season_end=3,
            episode_start=1,
            episode_end=10,
            mode=SearchMode.FUZZY,
            limit=20,
            offset=40,
        )

        response = SearchResponse(
            query=query,
            results=[],
            total_count=100,
            has_more=True,
            execution_time_ms=50.0,
            search_methods=["sql", "vector"],
        )

        formatter._display_search_info(response)

        # Should handle complex query gracefully
        console.print.assert_called()

    def test_format_brief_no_results(self):
        """Test brief format with no results."""
        formatter = ResultFormatter()

        query = SearchQuery(raw_query="test")
        response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            has_more=False,
        )

        result = formatter.format_brief(response)
        assert result == "No results found."

    def test_format_brief_with_results(self):
        """Test brief format with results."""
        formatter = ResultFormatter()

        query = SearchQuery(raw_query="test")
        result1 = SearchResult(
            script_id=1,
            script_title="Breaking_Bad",
            script_author="Vince Gilligan",
            scene_id=10,
            scene_number=5,
            scene_heading="INT. RV - DAY",
            scene_location="RV",
            scene_time="DAY",
            scene_content="Chemistry lab",
            season=1,
            episode=1,
            match_type="dialogue",
        )

        result2 = SearchResult(
            script_id=2,
            script_title="Feature Film",
            script_author="Director",
            scene_id=20,
            scene_number=10,
            scene_heading="EXT. STREET - NIGHT",
            scene_location="STREET",
            scene_time="NIGHT",
            scene_content="Action scene",
            season=None,  # No season for feature film
            episode=None,
            match_type="action",
        )

        response = SearchResponse(
            query=query,
            results=[result1, result2],
            total_count=2,
            has_more=False,
        )

        result = formatter.format_brief(response)

        # Should contain both results
        assert "1. Breaking_Bad S1E1 - Scene 5: INT. RV - DAY" in result
        assert "2. Feature Film - Scene 10: EXT. STREET - NIGHT" in result

    def test_format_brief_with_more_results(self):
        """Test brief format indicating more results available."""
        formatter = ResultFormatter()

        query = SearchQuery(raw_query="test", limit=1)
        result = SearchResult(
            script_id=1,
            script_title="The Wire",
            script_author="David Simon",
            scene_id=30,
            scene_number=15,
            scene_heading="EXT. CORNER - NIGHT",
            scene_location="CORNER",
            scene_time="NIGHT",
            scene_content="Street corner",
            season=2,
            episode=5,
            match_type="location",
        )

        response = SearchResponse(
            query=query,
            results=[result],
            total_count=50,
            has_more=True,
        )

        formatted = formatter.format_brief(response)

        assert "1. The Wire S2E5 - Scene 15: EXT. CORNER - NIGHT" in formatted
        assert "... and 49 more results" in formatted

    def test_display_search_info_with_text_query(self):
        """Test search info display with text query."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(
            raw_query="search term",
            text_query="search term",  # This covers line 72
        )

        response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            has_more=False,
        )

        formatter._display_search_info(response)

        # Should display text query
        console.print.assert_called()

    def test_display_search_info_single_season_episode(self):
        """Test search info with single season/episode (no range)."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(
            raw_query="test",
            season_start=1,
            season_end=1,  # Same as start, so single episode
            episode_start=5,
            episode_end=5,
        )

        response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            has_more=False,
        )

        formatter._display_search_info(response)

        # Should display single episode format (line 81)
        console.print.assert_called()

    def test_display_search_info_no_execution_time(self):
        """Test search info without execution time."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        query = SearchQuery(raw_query="test")
        response = SearchResponse(
            query=query,
            results=[],
            total_count=5,
            has_more=False,
            execution_time_ms=None,  # No execution time (lines 91-97)
            search_methods=[],  # No search methods
        )

        formatter._display_search_info(response)

        # Should handle missing execution time and methods
        console.print.assert_called()

    def test_display_result_no_author(self):
        """Test result display without script author."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        result = SearchResult(
            script_id=1,
            script_title="Anonymous Script",
            script_author=None,  # No author (lines 116-119)
            scene_id=10,
            scene_number=5,
            scene_heading="INT. ROOM - DAY",
            scene_location="ROOM",
            scene_time="DAY",
            scene_content="Scene without author",
        )

        formatter._display_result(result, 1, verbose=False)

        # Should handle missing author gracefully
        console.print.assert_called()

    def test_display_result_no_location_time(self):
        """Test result display without scene location and time."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        result = SearchResult(
            script_id=1,
            script_title="Minimal Script",
            script_author="Writer",
            scene_id=10,
            scene_number=5,
            scene_heading="FADE IN:",
            scene_location=None,  # No location (lines 127-130)
            scene_time=None,  # No time (lines 130-133)
            scene_content="Minimal scene content",
        )

        formatter._display_result(result, 1, verbose=False)

        # Should handle missing location and time
        console.print.assert_called()

    def test_display_result_long_content_truncation(self):
        """Test result display with content truncation."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        # Create long content that will be truncated (line 143)
        long_content = "\n".join([f"Line {i}" for i in range(1, 10)])

        result = SearchResult(
            script_id=1,
            script_title="Long Script",
            script_author="Verbose Writer",
            scene_id=10,
            scene_number=5,
            scene_heading="INT. LIBRARY - DAY",
            scene_location="LIBRARY",
            scene_time="DAY",
            scene_content=long_content,
        )

        formatter._display_result(result, 1, verbose=False)

        # Should truncate content and add ellipsis
        console.print.assert_called()

    def test_format_json_complete_structure(self):
        """Test JSON formatting with complete data structure."""
        formatter = ResultFormatter()

        query = SearchQuery(raw_query="test")
        result = SearchResult(
            script_id=1,
            script_title="Complete Test",
            script_author="Full Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. COMPLETE - DAY",
            scene_location="COMPLETE",
            scene_time="DAY",
            scene_content="Full content",
            season=1,
            episode=1,
            match_type="complete",
        )

        response = SearchResponse(
            query=query,
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=25.5,
            search_methods=["sql", "vector"],
        )

        json_output = formatter.format_json(response)
        parsed = json.loads(json_output)

        # Verify all fields are present
        assert parsed["total_count"] == 1
        assert parsed["has_more"] is False
        assert parsed["execution_time_ms"] == 25.5
        assert parsed["search_methods"] == ["sql", "vector"]

        result_data = parsed["results"][0]
        assert result_data["script_id"] == 1
        assert result_data["script_title"] == "Complete Test"
        assert result_data["script_author"] == "Full Author"
        assert result_data["scene_id"] == 1
        assert result_data["scene_number"] == 1
        assert result_data["scene_heading"] == "INT. COMPLETE - DAY"
        assert result_data["scene_location"] == "COMPLETE"
        assert result_data["scene_time"] == "DAY"
        assert result_data["scene_content"] == "Full content"
        assert result_data["season"] == 1
        assert result_data["episode"] == 1
        assert result_data["match_type"] == "complete"

    def test_get_query_attr_with_object(self):
        """Test _get_query_attr with SearchQuery object."""
        formatter = ResultFormatter()
        query = SearchQuery(raw_query="test", text_query="test query")

        # Test getting existing attribute
        assert formatter._get_query_attr(query, "raw_query") == "test"
        assert formatter._get_query_attr(query, "text_query") == "test query"

        # Test getting non-existent attribute with default
        assert formatter._get_query_attr(query, "nonexistent", "default") == "default"
        assert formatter._get_query_attr(query, "nonexistent") is None

    def test_get_query_attr_with_string(self):
        """Test _get_query_attr with string query (defensive handling)."""
        formatter = ResultFormatter()
        query = "string query"

        # String should always return default since it has no custom attributes
        assert formatter._get_query_attr(query, "raw_query", "default") == "default"
        assert formatter._get_query_attr(query, "any_attr") is None

    def test_format_results_with_string_query(self):
        """Test format_results handles string query gracefully."""
        console = MagicMock(spec=Console)
        formatter = ResultFormatter(console=console)

        # Create response with string query (edge case)
        response = SearchResponse(
            query="string query",  # String instead of SearchQuery
            results=[],
            total_count=0,
            has_more=False,
            execution_time_ms=10.5,
        )

        # Should not crash
        formatter.format_results(response)

        # Should still print no results message
        console.print.assert_any_call(
            "[yellow]No results found for your search.[/yellow]",
            style="bold",
        )
