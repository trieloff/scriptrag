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
            script_title="Breaking Bad",
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
            project="Breaking Bad",
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
