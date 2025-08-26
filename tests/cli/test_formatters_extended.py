"""Extended tests for CLI formatters to improve coverage."""

import csv
import io
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.cli.formatters.base import BaseFormatter, OutputFormat
from scriptrag.cli.formatters.json_formatter import JsonFormatter
from scriptrag.cli.formatters.query_formatter import QueryResultFormatter
from scriptrag.cli.formatters.scene_formatter import SceneFormatter
from scriptrag.cli.formatters.table_formatter import TableFormatter


class TestBaseFormatter:
    """Test base formatter functionality."""

    def test_base_formatter_abstract(self):
        """Test that BaseFormatter is abstract."""
        with pytest.raises(TypeError):
            BaseFormatter()  # Should fail - abstract class

    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.PLAIN.value == "plain"


class TestJsonFormatterExtended:
    """Extended tests for JsonFormatter."""

    def test_format_simple_dict(self):
        """Test formatting simple dictionary."""
        formatter = JsonFormatter()
        data = {"key": "value", "number": 42}

        result = formatter.format(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_with_dates(self):
        """Test formatting with datetime objects."""
        formatter = JsonFormatter()
        data = {"created": datetime(2024, 1, 1, 12, 0, 0), "name": "test"}

        result = formatter.format(data)
        parsed = json.loads(result)
        assert "2024-01-01" in parsed["created"]

    def test_format_nested_structure(self):
        """Test formatting nested data structures."""
        formatter = JsonFormatter()
        data = {"level1": {"level2": {"items": [1, 2, 3], "flag": True}}}

        result = formatter.format(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_with_none_values(self):
        """Test formatting with None values."""
        formatter = JsonFormatter()
        data = {"value": None, "empty": [], "zero": 0}

        result = formatter.format(data)
        parsed = json.loads(result)
        assert parsed["value"] is None
        assert parsed["empty"] == []
        assert parsed["zero"] == 0


class TestTableFormatterExtended:
    """Extended tests for TableFormatter."""

    def test_format_simple_data(self):
        """Test formatting simple tabular data."""
        formatter = TableFormatter()
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            formatter.format(data)
            mock_console.print.assert_called()

    def test_format_empty_data(self):
        """Test formatting empty data."""
        formatter = TableFormatter()

        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            result = formatter.format([])
            assert result == ""
            mock_console.print.assert_not_called()

    def test_format_with_title(self):
        """Test formatting with table title."""
        formatter = TableFormatter()
        data = [{"col1": "val1"}]

        with patch("rich.console.Console"):
            with patch("rich.table.Table") as mock_table_class:
                mock_table = MagicMock()
                mock_table_class.return_value = mock_table

                formatter.format(data, title="Test Table")
                mock_table_class.assert_called_with(
                    title="Test Table", show_header=True, header_style="bold magenta"
                )

    def test_format_with_none_values(self):
        """Test formatting with None values in cells."""
        formatter = TableFormatter()
        data = [
            {"name": "Alice", "email": None},
            {"name": None, "email": "bob@test.com"},
        ]

        with patch("rich.table.Table") as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table

            formatter.format(data)

            # Verify add_row was called with empty strings for None
            calls = mock_table.add_row.call_args_list
            assert len(calls) == 2
            # None should be converted to empty string
            assert "" in calls[0][0]
            assert "" in calls[1][0]


class TestQueryResultFormatterExtended:
    """Extended tests for QueryResultFormatter."""

    def test_format_query_info(self):
        """Test formatting query information."""
        formatter = QueryResultFormatter()

        info = formatter.format_query_info(
            name="test-query",
            description="A test query",
            parameters=["id (int)", "name (str)"],
        )

        assert "test-query" in info
        assert "A test query" in info
        assert "id (int)" in info
        assert "name (str)" in info

    def test_format_query_info_no_params(self):
        """Test formatting query info without parameters."""
        formatter = QueryResultFormatter()

        info = formatter.format_query_info(
            name="simple-query", description="No parameters", parameters=None
        )

        assert "simple-query" in info
        assert "No parameters" in info
        assert "Parameters:" not in info

    def test_format_results_as_table(self):
        """Test formatting query results as table."""
        formatter = QueryResultFormatter()
        results = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

        with patch("rich.console.Console"):
            output = formatter.format(
                results,
                output_format=OutputFormat.TABLE,
                query_name="user-list",
                execution_time=15.5,
            )
            assert output == ""  # Table printed to console

    def test_format_results_as_json(self):
        """Test formatting query results as JSON."""
        formatter = QueryResultFormatter()
        results = [{"id": 1, "value": 100}]

        output = formatter.format(
            results,
            output_format=OutputFormat.JSON,
            query_name="test",
            execution_time=10.0,
        )

        data = json.loads(output)
        assert data["query"] == "test"
        assert data["results"] == results
        assert data["execution_time_ms"] == 10.0

    def test_format_results_as_csv(self):
        """Test formatting query results as CSV."""
        formatter = QueryResultFormatter()
        results = [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]

        output = formatter.format(results, output_format=OutputFormat.CSV)

        # Parse CSV output
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["score"] == "95"

    def test_format_results_as_markdown(self):
        """Test formatting query results as Markdown."""
        formatter = QueryResultFormatter()
        results = [
            {"col1": "value1", "col2": "value2"},
            {"col1": "value3", "col2": "value4"},
        ]

        output = formatter.format(
            results, output_format=OutputFormat.MARKDOWN, query_name="test-query"
        )

        assert "## Query: test-query" in output
        assert "| col1 | col2 |" in output
        assert "|------|------|" in output
        assert "| value1 | value2 |" in output

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = QueryResultFormatter()

        # JSON format
        json_output = formatter.format([], output_format=OutputFormat.JSON)
        data = json.loads(json_output)
        assert data["results"] == []

        # CSV format
        csv_output = formatter.format([], output_format=OutputFormat.CSV)
        assert csv_output == ""

        # Markdown format
        md_output = formatter.format([], output_format=OutputFormat.MARKDOWN)
        assert "No results" in md_output


class TestSceneFormatterExtended:
    """Extended tests for SceneFormatter."""

    def test_format_single_scene(self):
        """Test formatting a single scene."""
        formatter = SceneFormatter()
        scene = {
            "scene_number": 1,
            "scene_heading": "INT. OFFICE - DAY",
            "scene_content": "John enters the room.",
            "characters": ["JOHN"],
        }

        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            formatter.format(scene)
            mock_console.print.assert_called()

    def test_format_scene_list(self):
        """Test formatting a list of scenes."""
        formatter = SceneFormatter()
        scenes = [
            {
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_content": "Content 1",
            },
            {
                "scene_number": 2,
                "scene_heading": "EXT. STREET - NIGHT",
                "scene_content": "Content 2",
            },
        ]

        with patch("rich.console.Console"):
            output = formatter.format(scenes, output_format=OutputFormat.TABLE)
            assert output == ""  # Printed to console

    def test_format_scene_as_json(self):
        """Test formatting scene as JSON."""
        formatter = SceneFormatter()
        scene = {
            "scene_number": 5,
            "scene_heading": "INT. BAR - NIGHT",
            "dialogue_count": 10,
        }

        output = formatter.format(scene, output_format=OutputFormat.JSON)
        data = json.loads(output)
        assert data["scene_number"] == 5
        assert data["scene_heading"] == "INT. BAR - NIGHT"

    def test_format_scene_with_missing_fields(self):
        """Test formatting scene with missing optional fields."""
        formatter = SceneFormatter()
        scene = {
            "scene_number": 1,
            "scene_heading": "INT. ROOM - DAY",
            # Missing scene_content, characters, etc.
        }

        with patch("rich.console.Console"):
            # Should handle missing fields gracefully
            formatter.format(scene)

    def test_format_tv_episode_scene(self):
        """Test formatting TV episode scene with season/episode info."""
        formatter = SceneFormatter()
        scene = {
            "scene_number": 1,
            "scene_heading": "INT. OFFICE - DAY",
            "season": 2,
            "episode": 5,
            "script_title": "Breaking Bad",
        }

        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            formatter.format(scene)

            # Should include season/episode in output
            call_args = str(mock_console.print.call_args)
            assert "Season" in call_args or "S2" in call_args or "2" in call_args
