"""Tests for CLI formatters."""

import json

from scriptrag.api.scene_models import ReadSceneResult, SceneData
from scriptrag.cli.formatters.base import OutputFormat
from scriptrag.cli.formatters.json_formatter import JsonFormatter
from scriptrag.cli.formatters.query_formatter import QueryResultFormatter
from scriptrag.cli.formatters.scene_formatter import SceneFormatter
from scriptrag.cli.formatters.table_formatter import TableFormatter


class TestSceneFormatter:
    """Test scene output formatting."""

    def test_format_scene_text(self):
        """Test formatting scene as text."""
        formatter = SceneFormatter()
        scene = SceneData(
            number=1,
            heading="INT. OFFICE - DAY",
            content="INT. OFFICE - DAY\n\nJohn enters.",
        )

        result = formatter.format(scene, OutputFormat.TEXT)
        assert "Scene 1" in result
        assert "INT. OFFICE - DAY" in result

    def test_format_scene_json(self):
        """Test formatting scene as JSON."""
        formatter = SceneFormatter()
        scene = SceneData(
            number=1,
            heading="INT. OFFICE - DAY",
            content="INT. OFFICE - DAY\n\nJohn enters.",
        )

        result = formatter.format(scene, OutputFormat.JSON)
        data = json.loads(result)
        assert data["number"] == 1
        assert data["heading"] == "INT. OFFICE - DAY"
        assert data["content"] == "INT. OFFICE - DAY\n\nJohn enters."

    def test_format_read_result_success(self):
        """Test formatting successful read result."""
        formatter = SceneFormatter()
        scene = SceneData(
            number=42,
            heading="EXT. STREET - NIGHT",
            content="EXT. STREET - NIGHT\n\nRain falls.",
        )
        result = ReadSceneResult(
            success=True,
            error=None,
            scene=scene,
            last_read=None,
        )

        output = formatter.format(result, OutputFormat.TEXT)
        assert "Scene 42" in output
        assert "EXT. STREET - NIGHT" in output

    def test_format_read_result_error(self):
        """Test formatting error read result."""
        formatter = SceneFormatter()
        result = ReadSceneResult(
            success=False,
            error="Scene not found",
            scene=None,
            last_read=None,
        )

        output = formatter.format(result, OutputFormat.TEXT)
        assert "Error" in output
        assert "Scene not found" in output

    def test_format_scene_list(self):
        """Test formatting list of scenes."""
        formatter = SceneFormatter()
        scenes = [
            SceneData(number=1, heading="INT. OFFICE - DAY", content="Content 1"),
            SceneData(number=2, heading="EXT. STREET - NIGHT", content="Content 2"),
        ]

        # Table format
        table_output = formatter.format_scene_list(scenes, OutputFormat.TABLE)
        assert "INT. OFFICE - DAY" in table_output
        assert "EXT. STREET - NIGHT" in table_output

        # JSON format
        json_output = formatter.format_scene_list(scenes, OutputFormat.JSON)
        data = json.loads(json_output)
        assert len(data) == 2
        assert data[0]["number"] == 1


class TestTableFormatter:
    """Test table output formatting."""

    def test_format_table(self):
        """Test formatting data as table."""
        formatter = TableFormatter()
        data = [
            {"name": "John", "age": 30, "city": "New York"},
            {"name": "Jane", "age": 25, "city": "Los Angeles"},
        ]

        result = formatter.format(data, OutputFormat.TABLE)
        assert "John" in result
        assert "Jane" in result
        assert "30" in result

    def test_format_csv(self):
        """Test formatting data as CSV."""
        formatter = TableFormatter()
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25},
        ]

        result = formatter.format(data, OutputFormat.CSV)
        lines = result.strip().split("\n")
        assert "name,age" in lines[0]
        assert "John,30" in lines[1]
        assert "Jane,25" in lines[2]

    def test_format_markdown(self):
        """Test formatting data as Markdown table."""
        formatter = TableFormatter()
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25},
        ]

        result = formatter.format(data, OutputFormat.MARKDOWN)
        assert "| name | age |" in result
        assert "| --- | --- |" in result
        assert "| John | 30 |" in result

    def test_empty_data(self):
        """Test formatting empty data."""
        formatter = TableFormatter()
        data = []

        result = formatter.format(data, OutputFormat.TABLE)
        assert "No data to display" in result

    def test_create_summary_table(self):
        """Test creating summary table."""
        formatter = TableFormatter()
        data = {
            "total_scenes": 42,
            "total_characters": 15,
            "total_locations": 8,
        }

        result = formatter.create_summary_table("Statistics", data)
        assert "Statistics" in result
        assert "Total Scenes" in result
        assert "42" in result


class TestQueryResultFormatter:
    """Test query result formatting."""

    def test_format_query_results(self):
        """Test formatting query results."""
        formatter = QueryResultFormatter()
        data = [
            {"id": 1, "name": "Scene 1", "location": "OFFICE"},
            {"id": 2, "name": "Scene 2", "location": "STREET"},
        ]

        # Table format
        result = formatter.format(data, OutputFormat.TABLE)
        assert "Scene 1" in result
        assert "OFFICE" in result

        # JSON format
        json_result = formatter.format(data, OutputFormat.JSON)
        parsed = json.loads(json_result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == 1

    def test_format_empty_results(self):
        """Test formatting empty query results."""
        formatter = QueryResultFormatter()
        data = []

        result = formatter.format(data, OutputFormat.TABLE)
        assert "No results found" in result

        json_result = formatter.format(data, OutputFormat.JSON)
        assert json.loads(json_result) == []

    def test_format_query_info(self):
        """Test formatting query information."""
        formatter = QueryResultFormatter()

        info = formatter.format_query_info(
            "scene_count",
            "Count total scenes in project",
            ["project_name", "episode"],
        )

        assert "scene_count" in info
        assert "Count total scenes" in info
        assert "project_name" in info
        assert "episode" in info

    def test_format_execution_stats(self):
        """Test formatting execution statistics."""
        formatter = QueryResultFormatter()

        stats = formatter.format_execution_stats(42, 0.123)
        assert "42 rows" in stats
        assert "0.123s" in stats

        stats_single = formatter.format_execution_stats(1, 0.5)
        assert "1 row" in stats_single
        assert "rows" not in stats_single.replace("row", "")


class TestJsonFormatter:
    """Test JSON formatter."""

    def test_format_dict(self):
        """Test formatting dictionary."""
        formatter = JsonFormatter()
        data = {"key": "value", "number": 42}

        result = formatter.format(data)
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_format_list(self):
        """Test formatting list."""
        formatter = JsonFormatter()
        data = [1, 2, 3, "test"]

        result = formatter.format(data)
        parsed = json.loads(result)
        assert parsed == [1, 2, 3, "test"]

    def test_format_pydantic_model(self):
        """Test formatting Pydantic model."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        formatter = JsonFormatter()
        model = TestModel(name="test", value=42)

        result = formatter.format(model)
        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42

    def test_format_success(self):
        """Test formatting success response."""
        formatter = JsonFormatter()

        result = formatter.format_success("Operation completed", {"id": 123})
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["message"] == "Operation completed"
        assert parsed["data"]["id"] == 123

    def test_format_error_response(self):
        """Test formatting error response."""
        formatter = JsonFormatter()

        result = formatter.format_error_response("Something went wrong", code=500)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Something went wrong"
        assert parsed["code"] == 500
