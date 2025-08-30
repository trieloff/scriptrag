"""Tests for query formatter."""

import json
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from scriptrag.query.formatter import QueryFormatter


class TestQueryFormatter:
    """Test query result formatter."""

    @pytest.fixture
    def formatter(self):
        """Create formatter with mock console."""
        console = MagicMock(spec=Console)
        return QueryFormatter(console=console)

    def test_format_empty_results(self, formatter):
        """Test formatting empty results."""
        result = formatter.format_results(
            rows=[],
            query_name="test_query",
            execution_time_ms=10.5,
            output_json=False,
        )

        assert result is None
        formatter.console.print.assert_called_with(
            "[yellow]No results found for query 'test_query'.[/yellow]",
            style="bold",
        )

    def test_format_as_json(self, formatter):
        """Test JSON output format."""
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        result = formatter.format_results(
            rows=rows,
            query_name="test_query",
            execution_time_ms=15.3,
            output_json=True,
        )

        assert result is not None
        data = json.loads(result)
        assert data["query"] == "test_query"
        assert data["count"] == 2
        assert data["execution_time_ms"] == 15.3
        assert len(data["results"]) == 2
        assert data["results"][0]["name"] == "Alice"

    def test_is_scene_like_true(self, formatter):
        """Test detection of scene-like results."""
        rows = [
            {
                "script_title": "Test Script",
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_content": "Action here",
                "other_field": "value",
            }
        ]

        assert formatter._is_scene_like(rows) is True

    def test_is_scene_like_false(self, formatter):
        """Test detection of non-scene results."""
        rows = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
        ]

        assert formatter._is_scene_like(rows) is False

    def test_is_scene_like_partial(self, formatter):
        """Test detection with partial scene columns."""
        # Has 3 out of 4 key columns - should be scene-like
        rows = [
            {
                "script_title": "Test",
                "scene_number": 1,
                "scene_heading": "INT. ROOM",
                "other_field": "value",
            }
        ]
        assert formatter._is_scene_like(rows) is True

        # Has only 2 out of 4 - not scene-like
        rows = [
            {
                "script_title": "Test",
                "scene_number": 1,
                "other_field": "value",
            }
        ]
        assert formatter._is_scene_like(rows) is False

    @patch("scriptrag.query.formatter.ResultFormatter")
    def test_format_as_scenes(self, _mock_result_formatter_class, formatter):
        """Test formatting scene-like results."""
        mock_result_formatter = MagicMock(
            spec=["content", "model", "provider", "usage", "format_results"]
        )
        formatter.result_formatter = mock_result_formatter

        rows = [
            {
                "script_id": 1,
                "script_title": "Test Script",
                "script_author": "Author",
                "scene_id": 10,
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_location": "Office",
                "scene_time": "Day",
                "scene_content": "The scene content",
                "season": 1,
                "episode": 2,
            }
        ]

        formatter._format_as_scenes(
            rows=rows,
            query_name="test_query",
            execution_time_ms=20.0,
            limit=10,
            offset=0,
        )

        # Should call ResultFormatter.format_results
        mock_result_formatter.format_results.assert_called_once()
        response = mock_result_formatter.format_results.call_args[0][0]

        # Check response structure
        assert len(response.results) == 1
        assert response.results[0].script_title == "Test Script"
        assert response.results[0].scene_heading == "INT. OFFICE - DAY"
        assert response.execution_time_ms == 20.0

    def test_format_as_table(self, formatter):
        """Test formatting as generic table."""
        from rich.table import Table

        rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]

        formatter._format_as_table(
            rows=rows,
            query_name="test_query",
            execution_time_ms=12.5,
        )

        # Check that console.print was called with query info
        calls = formatter.console.print.call_args_list
        assert len(calls) == 2

        # First call should be query info
        assert "test_query" in str(calls[0])
        assert "2 rows" in str(calls[0])
        assert "12.5" in str(calls[0])

        # Second call should be a Table
        table_arg = calls[1][0][0]
        assert isinstance(table_arg, Table)

    def test_format_results_with_scenes(self, formatter):
        """Test complete format_results with scene-like data."""
        rows = [
            {
                "script_title": "Test",
                "scene_number": 1,
                "scene_heading": "INT. ROOM",
                "scene_content": "Content",
            }
        ]

        with patch.object(formatter, "_format_as_scenes") as mock_scenes:
            result = formatter.format_results(
                rows=rows,
                query_name="test",
                execution_time_ms=10.0,
                output_json=False,
            )

            assert result is None
            mock_scenes.assert_called_once()

    def test_format_results_with_table(self, formatter):
        """Test complete format_results with non-scene data."""
        rows = [
            {"id": 1, "name": "Alice"},
        ]

        with patch.object(formatter, "_format_as_table") as mock_table:
            result = formatter.format_results(
                rows=rows,
                query_name="test",
                execution_time_ms=10.0,
                output_json=False,
            )

            assert result is None
            mock_table.assert_called_once()

    def test_format_json_with_none_values(self, formatter):
        """Test JSON formatting handles None values."""
        rows = [
            {"id": 1, "name": "Alice", "email": None},
            {"id": 2, "name": None, "email": "bob@example.com"},
        ]

        result = formatter.format_results(
            rows=rows,
            query_name="test",
            execution_time_ms=5.0,
            output_json=True,
        )

        data = json.loads(result)
        assert data["results"][0]["email"] is None
        assert data["results"][1]["name"] is None

    def test_has_more_heuristic(self, formatter):
        """Test has_more detection in scene formatting."""
        # Create rows equal to limit - should indicate has_more
        rows = [
            {
                "script_title": f"Script {i}",
                "scene_number": i,
                "scene_heading": f"Scene {i}",
                "scene_content": f"Content {i}",
            }
            for i in range(10)
        ]

        with patch.object(formatter.result_formatter, "format_results") as mock_format:
            formatter._format_as_scenes(
                rows=rows,
                query_name="test",
                execution_time_ms=10.0,
                limit=10,
                offset=0,
            )

            response = mock_format.call_args[0][0]
            assert response.has_more is True

        # Fewer rows than limit - no more results
        rows_partial = rows[:5]

        with patch.object(formatter.result_formatter, "format_results") as mock_format:
            formatter._format_as_scenes(
                rows=rows_partial,
                query_name="test",
                execution_time_ms=10.0,
                limit=10,
                offset=0,
            )

            response = mock_format.call_args[0][0]
            assert response.has_more is False

    def test_format_dialogue_in_scenes(self, formatter):
        """Test formatting dialogue content in scene results."""
        mock_result_formatter = MagicMock()
        formatter.result_formatter = mock_result_formatter

        # Test with dialogue and parenthetical
        rows = [
            {
                "script_id": 1,
                "script_title": "Test Script",
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_content": "Original scene content",
                "character": "JOHN",
                "dialogue": "Hello there",
                "parenthetical": "nervously",
            },
            {
                "script_id": 1,
                "script_title": "Test Script",
                "scene_number": 2,
                "scene_heading": "EXT. STREET - DAY",
                "scene_content": "",  # Empty scene content
                "character": "JANE",
                "dialogue": "Hi John!",
                "parenthetical": "",
            },
        ]

        formatter._format_as_scenes(
            rows=rows,
            query_name="dialogue_query",
            execution_time_ms=15.0,
            limit=None,
            offset=None,
        )

        # Check the formatted results
        response = mock_result_formatter.format_results.call_args[0][0]
        assert len(response.results) == 2

        # First result should have dialogue appended to scene content
        assert "JOHN (nervously): Hello there" in response.results[0].scene_content
        assert "Original scene content" in response.results[0].scene_content

        # Second result should use dialogue as scene content (since original was empty)
        assert response.results[1].scene_content == "JANE: Hi John!"

    def test_format_results_empty_rows_message(self):
        """Test format_results with empty rows shows message - lines 54-58 coverage."""
        formatter = QueryFormatter()

        with patch.object(formatter.console, "print") as mock_print:
            result = formatter.format_results(
                rows=[],
                query_name="test_query",
                execution_time_ms=10.0,
                output_json=False,
            )

            assert result is None
            mock_print.assert_called_once_with(
                "[yellow]No results found for query 'test_query'.[/yellow]",
                style="bold",
            )

    def test_is_scene_like_empty_rows(self):
        """Test _is_scene_like with empty rows - line 78 coverage."""
        formatter = QueryFormatter()

        result = formatter._is_scene_like([])
        assert result is False

    def test_format_json_complex_result(self):
        """Test _format_json with complex result structure - line 173 coverage."""
        formatter = QueryFormatter()

        rows = [
            {"id": 1, "data": {"nested": "value"}, "list": [1, 2, 3]},
            {"id": 2, "data": None, "list": []},
        ]

        result = formatter._format_json(rows, "complex_query", 15.5)

        # Should return properly formatted JSON string
        import json

        parsed = json.loads(result)

        assert parsed["query"] == "complex_query"
        assert parsed["execution_time_ms"] == 15.5
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["data"]["nested"] == "value"
        assert parsed["results"][1]["data"] is None
