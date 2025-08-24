"""Unit tests for scene formatter."""

from datetime import datetime
from io import StringIO

import pytest
from rich.console import Console

from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.cli.scene_formatter import SceneFormatter
from scriptrag.parser import Scene


class TestSceneFormatter:
    """Test scene formatter functionality."""

    @pytest.fixture
    def console_output(self) -> StringIO:
        """Create string buffer for console output."""
        return StringIO()

    @pytest.fixture
    def formatter(self, console_output: StringIO) -> SceneFormatter:
        """Create formatter with test console."""
        console = Console(file=console_output, force_terminal=True, width=80)
        return SceneFormatter(console)

    @pytest.fixture
    def sample_scene(self) -> Scene:
        """Create sample scene for testing."""
        return Scene(
            number=42,
            heading="INT. OFFICE - DAY",
            content="INT. OFFICE - DAY\n\nJohn enters the office.",
            original_text="INT. OFFICE - DAY\n\nJohn enters the office.",
            content_hash="abc123",
            location="OFFICE",
            time_of_day="DAY",
        )

    @pytest.fixture
    def scene_id(self) -> SceneIdentifier:
        """Create scene identifier."""
        return SceneIdentifier(
            project="test_project",
            scene_number=42,
        )

    def test_format_scene_display_rich(
        self,
        formatter: SceneFormatter,
        sample_scene: Scene,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test rich scene display formatting."""
        last_read = datetime(2024, 1, 15, 10, 30)

        formatter.format_scene_display(
            sample_scene, scene_id, last_read, json_output=False
        )

        output = console_output.getvalue()
        assert "Scene test_project:042" in output
        assert "INT. OFFICE - DAY" in output
        assert "John enters the office" in output
        assert "2024-01-15T10:30:00" in output

    def test_format_scene_display_json(
        self,
        formatter: SceneFormatter,
        sample_scene: Scene,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test JSON scene display formatting."""
        last_read = datetime(2024, 1, 15, 10, 30)

        formatter.format_scene_display(
            sample_scene, scene_id, last_read, json_output=True
        )

        output = console_output.getvalue()
        assert '"success": true' in output
        assert '"scene_number": 42' in output
        assert '"heading": "INT. OFFICE - DAY"' in output
        assert '"scene_id": "test_project:042"' in output

    def test_format_bible_display_content(
        self,
        formatter: SceneFormatter,
        console_output: StringIO,
    ) -> None:
        """Test bible content display."""
        content = "# Character Bible\n\nCharacter details here."
        bible_files = []

        formatter.format_bible_display(
            content, bible_files, "test_project", "bible.md", json_output=False
        )

        output = console_output.getvalue()
        assert "Bible: bible.md" in output
        assert "test_project" in output
        assert "Character Bible" in output

    def test_format_bible_display_list(
        self,
        formatter: SceneFormatter,
        console_output: StringIO,
    ) -> None:
        """Test bible file list display."""
        bible_files = [
            {"name": "characters.md", "path": "bible/characters.md", "size": 2048},
            {"name": "world.md", "path": "bible/world.md", "size": 4096},
        ]

        formatter.format_bible_display(
            None, bible_files, "test_project", None, json_output=False
        )

        output = console_output.getvalue()
        assert "Available bible files" in output
        assert "test_project" in output
        assert "characters.md" in output
        assert "2.0 KB" in output
        assert "world.md" in output
        assert "4.0 KB" in output

    def test_format_operation_result_success(
        self,
        formatter: SceneFormatter,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test successful operation result formatting."""
        details = {"renumbered_scenes": [43, 44, 45]}

        formatter.format_operation_result("add", True, scene_id, details=details)

        output = console_output.getvalue()
        assert "✓" in output
        assert "Scene added: test_project:042" in output
        assert "Renumbered scenes: 43, 44, 45" in output

    def test_format_operation_result_failure(
        self,
        formatter: SceneFormatter,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test failed operation result formatting."""
        formatter.format_operation_result(
            "update", False, scene_id, message="Invalid content"
        )

        output = console_output.getvalue()
        assert "✗" in output
        assert "Failed to update scene" in output
        assert "Invalid content" in output

    def test_format_validation_errors(
        self,
        formatter: SceneFormatter,
        console_output: StringIO,
    ) -> None:
        """Test validation error formatting."""
        errors = ["Missing scene heading", "Invalid format"]
        warnings = ["No content after heading"]
        suggestions = ["Add 'INT. ' or 'EXT. ' prefix"]

        formatter.format_validation_errors(errors, warnings, suggestions)

        output = console_output.getvalue()
        assert "Validation errors:" in output
        assert "Missing scene heading" in output
        assert "Warnings:" in output
        assert "No content after heading" in output
        assert "Suggestions:" in output
        assert "Add 'INT. ' or 'EXT. ' prefix" in output

    def test_format_scene_list(
        self,
        formatter: SceneFormatter,
        console_output: StringIO,
    ) -> None:
        """Test scene list formatting."""
        scenes = [
            {
                "number": 1,
                "heading": "INT. OFFICE - DAY",
                "location": "OFFICE",
                "time_of_day": "DAY",
            },
            {
                "number": 2,
                "heading": "EXT. STREET - NIGHT",
                "location": "STREET",
                "time_of_day": "NIGHT",
            },
        ]

        formatter.format_scene_list(scenes, "test_project", json_output=False)

        output = console_output.getvalue()
        assert "Scenes for test_project" in output
        assert "INT. OFFICE - DAY" in output
        assert "EXT. STREET - NIGHT" in output
        assert "OFFICE" in output
        assert "STREET" in output

    def test_format_scene_list_json(
        self,
        formatter: SceneFormatter,
        console_output: StringIO,
    ) -> None:
        """Test scene list JSON formatting."""
        scenes = [
            {"number": 1, "heading": "INT. OFFICE - DAY"},
        ]

        formatter.format_scene_list(scenes, "test_project", json_output=True)

        output = console_output.getvalue()
        assert '"project": "test_project"' in output
        assert '"scenes":' in output
        assert '"number": 1' in output

    def test_format_conflict_error(
        self,
        formatter: SceneFormatter,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test conflict error formatting."""
        last_modified = datetime(2024, 1, 15, 11, 0)
        last_read = datetime(2024, 1, 15, 10, 30)

        formatter.format_conflict_error(scene_id, last_modified, last_read)

        output = console_output.getvalue()
        assert "Conflict detected" in output
        assert "test_project:042" in output
        assert "2024-01-15T11:00:00" in output
        assert "2024-01-15T10:30:00" in output
        assert "re-read the scene" in output

    def test_formatter_with_no_console(self) -> None:
        """Test formatter creates its own console if none provided."""
        formatter = SceneFormatter()
        assert formatter.console is not None

    def test_format_scene_with_metadata(
        self,
        formatter: SceneFormatter,
        scene_id: SceneIdentifier,
        console_output: StringIO,
    ) -> None:
        """Test scene display with location and time metadata."""
        scene = Scene(
            number=1,
            heading="INT. OFFICE - DAY",
            content="Content here",
            original_text="Content here",
            content_hash="xyz",
            location="OFFICE",
            time_of_day="DAY",
        )

        formatter.format_scene_display(scene, scene_id, None, json_output=False)

        output = console_output.getvalue()
        assert "Location:" in output
        assert "OFFICE" in output
        assert "Time:" in output
        assert "DAY" in output
