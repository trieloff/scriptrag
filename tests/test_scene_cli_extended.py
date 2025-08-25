"""Extended tests for scene CLI commands to improve coverage."""

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from scriptrag.api.scene_models import (
    AddSceneResult,
    BibleReadResult,
    DeleteSceneResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.main import app
from scriptrag.parser import Scene
from tests.cli_fixtures import strip_ansi_codes

runner = CliRunner()


class TestSceneReadBibleCommand:
    """Test scene read --bible functionality."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_bible_list_files(self, mock_api_class):
        """Test listing available bible files."""
        mock_api = mock_api_class.return_value
        mock_result = BibleReadResult(
            success=True,
            error=None,
            bible_files=[
                {"name": "world_bible.md", "path": "world_bible.md", "size": 1024},
                {"name": "characters.md", "path": "docs/characters.md", "size": 2048},
            ],
        )

        mock_api.read_bible = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test_project", "--bible"],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Available bible files" in clean_output
        assert "world_bible.md" in clean_output
        assert "characters.md" in clean_output
        assert "1.0 KB" in clean_output
        assert "2.0 KB" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_bible_specific_file(self, mock_api_class):
        """Test reading specific bible file."""
        mock_api = mock_api_class.return_value
        bible_content = "# World Bible\n\nThis is the world bible content."
        mock_result = BibleReadResult(
            success=True,
            error=None,
            content=bible_content,
        )

        mock_api.read_bible = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--bible-name",
                "world_bible.md",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "World Bible" in clean_output
        assert "world bible content" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_bible_json_output_list(self, mock_api_class):
        """Test bible list with JSON output."""
        mock_api = mock_api_class.return_value
        mock_result = BibleReadResult(
            success=True,
            error=None,
            bible_files=[
                {"name": "world_bible.md", "path": "world_bible.md", "size": 1024},
            ],
        )

        mock_api.read_bible = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test_project", "--bible", "--json"],
        )

        assert result.exit_code == 0
        json_str = strip_ansi_codes(result.output).strip()
        json_output = json.loads(json_str)

        assert json_output["success"] is True
        assert len(json_output["bible_files"]) == 1
        assert json_output["bible_files"][0]["name"] == "world_bible.md"

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_bible_json_output_content(self, mock_api_class):
        """Test bible content with JSON output."""
        mock_api = mock_api_class.return_value
        bible_content = "Bible content here"
        mock_result = BibleReadResult(
            success=True,
            error=None,
            content=bible_content,
        )

        mock_api.read_bible = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--bible-name",
                "world_bible.md",
                "--json",
            ],
        )

        assert result.exit_code == 0
        json_str = strip_ansi_codes(result.output).strip()
        json_output = json.loads(json_str)

        assert json_output["success"] is True
        assert json_output["content"] == bible_content

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_bible_error(self, mock_api_class):
        """Test bible read error handling."""
        mock_api = mock_api_class.return_value
        mock_result = BibleReadResult(
            success=False,
            error="Bible file not found",
        )

        mock_api.read_bible = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--bible-name",
                "nonexistent.md",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Bible file not found" in clean_output

    def test_read_no_scene_or_bible(self):
        """Test read command without --scene or --bible."""
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test_project"],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Either --scene or --bible must be specified" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_scene_with_tv_params(self, mock_api_class):
        """Test reading TV show scene."""
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=5,
            heading="INT. LAB - DAY",
            content="Walter works.",
            original_text="Walter works.",
            content_hash="hash",
        )

        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=mock_scene,
            last_read=None,
        )

        mock_api.read_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "breaking_bad",
                "--season",
                "1",
                "--episode",
                "3",
                "--scene",
                "5",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Walter works" in clean_output
        # Token system eliminated - no longer checking for tokens

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_scene_exception(self, mock_api_class):
        """Test read command with exception."""
        mock_api = mock_api_class.return_value
        mock_api.read_scene = AsyncMock(side_effect=Exception("Unexpected error"))

        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test", "--scene", "1"],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Error: Unexpected error" in clean_output


class TestSceneAddCommandExtended:
    """Extended tests for scene add command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_before(self, mock_api_class):
        """Test adding scene before reference."""
        mock_api = mock_api_class.return_value
        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=Scene(
                number=5,
                heading="INT. NEW - DAY",
                content="New content",
                original_text="New content",
                content_hash="hash",
            ),
            renumbered_scenes=[6, 7, 8],
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--before-scene",
                "5",
                "--content",
                "INT. NEW - DAY\n\nNew content",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene added" in clean_output
        assert "Renumbered scenes: 6, 7, 8" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_from_stdin(self, mock_api_class):
        """Test adding scene with content from stdin."""
        mock_api = mock_api_class.return_value
        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=Scene(
                number=6,
                heading="INT. STDIN - DAY",
                content="From stdin",
                original_text="From stdin",
                content_hash="hash",
            ),
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        # Mock CLIHandler's read_stdin method
        with patch(
            "scriptrag.cli.utils.cli_handler.CLIHandler.read_stdin"
        ) as mock_read_stdin:
            mock_read_stdin.return_value = "INT. STDIN - DAY\n\nFrom stdin"
            result = runner.invoke(
                app,
                ["scene", "add", "--project", "test", "--after-scene", "5"],
            )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene added" in clean_output

    def test_add_scene_no_position(self):
        """Test add without position specified."""
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Must specify either --after-scene or --before-scene" in clean_output

    def test_add_scene_both_positions(self):
        """Test add with both positions specified."""
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "5",
                "--before-scene",
                "6",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Cannot specify both --after-scene and --before-scene" in clean_output

    def test_add_scene_no_content(self):
        """Test add without content."""
        # Don't provide --content and ensure stdin is a tty
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True  # Terminal, not piped

            result = runner.invoke(
                app,
                ["scene", "add", "--project", "test", "--after-scene", "5"],
                input="",  # Provide empty input to simulate tty
            )

            assert result.exit_code == 1
            clean_output = strip_ansi_codes(result.output)
            assert "Validation Error: scene content cannot be empty" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_with_tv_params(self, mock_api_class):
        """Test adding TV show scene."""
        mock_api = mock_api_class.return_value
        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=Scene(
                number=10,
                heading="INT. LAB - DAY",
                content="Lab scene",
                original_text="Lab scene",
                content_hash="hash",
            ),
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "breaking_bad",
                "--season",
                "1",
                "--episode",
                "5",
                "--after-scene",
                "9",
                "--content",
                "INT. LAB - DAY\n\nLab scene",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene added" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_error(self, mock_api_class):
        """Test add scene error handling."""
        mock_api = mock_api_class.return_value
        mock_result = AddSceneResult(
            success=False,
            error="Invalid Fountain format",
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "5",
                "--content",
                "Invalid content",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert (
            "Scene content must start with a valid scene heading" in clean_output
            or "Invalid Fountain format" in clean_output
        )

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_exception(self, mock_api_class):
        """Test add command with exception."""
        mock_api = mock_api_class.return_value
        mock_api.add_scene = AsyncMock(side_effect=Exception("Unexpected error"))

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "5",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Error: Unexpected error" in clean_output


class TestSceneUpdateCommandExtended:
    """Extended tests for scene update command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.utils.cli_handler.CLIHandler.read_stdin")
    def test_update_scene_from_stdin(self, mock_read_stdin, mock_api_class):
        """Test updating scene with content from stdin."""
        mock_api = mock_api_class.return_value
        mock_result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=Scene(
                number=5,
                heading="INT. UPDATED - DAY",
                content="Updated from stdin",
                original_text="Updated from stdin",
                content_hash="hash",
            ),
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        # Mock stdin reading
        mock_read_stdin.return_value = "INT. UPDATED - DAY\n\nUpdated from stdin"

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene updated" in clean_output

    def test_update_scene_no_content(self):
        """Test update without content."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True  # Terminal, not piped

            result = runner.invoke(
                app,
                [
                    "scene",
                    "update",
                    "--project",
                    "test",
                    "--scene",
                    "5",
                    # No safe mode - immediate update
                ],
                input="",  # Provide empty input to simulate tty
            )

            assert result.exit_code == 1
            clean_output = strip_ansi_codes(result.output)
            assert (
                "No content provided" in clean_output
                or "Invalid Fountain format" in clean_output
            )

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_with_tv_params(self, mock_api_class):
        """Test updating TV show scene."""
        mock_api = mock_api_class.return_value
        mock_result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=Scene(
                number=5,
                heading="INT. LAB - NIGHT",
                content="Updated lab",
                original_text="Updated lab",
                content_hash="hash",
            ),
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "breaking_bad",
                "--season",
                "1",
                "--episode",
                "3",
                "--scene",
                "5",
                "--content",
                "INT. LAB - NIGHT\n\nUpdated lab",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene updated" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_with_validation_errors(self, mock_api_class):
        """Test update with validation errors."""
        mock_api = mock_api_class.return_value
        mock_result = UpdateSceneResult(
            success=False,
            error="Validation failed",
            validation_errors=["Missing scene heading", "Invalid format"],
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
                "--content",
                "Invalid",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Validation failed" in clean_output
        assert "Validation errors:" in clean_output
        assert "Missing scene heading" in clean_output
        assert "Invalid format" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_exception(self, mock_api_class):
        """Test update command with exception."""
        mock_api = mock_api_class.return_value
        mock_api.update_scene = AsyncMock(side_effect=Exception("Unexpected error"))

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Failed to update scene" in clean_output
        assert "Unexpected error" in clean_output


class TestSceneDeleteCommandExtended:
    """Extended tests for scene delete command."""

    def test_delete_without_confirm(self):
        """Test delete without confirmation."""
        result = runner.invoke(
            app,
            ["scene", "delete", "--project", "test", "--scene", "5"],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Warning: This will permanently delete the scene" in clean_output
        assert "Add --confirm flag to proceed" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_with_tv_params(self, mock_api_class):
        """Test deleting TV show scene."""
        mock_api = mock_api_class.return_value
        mock_result = DeleteSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[6, 7, 8],
        )

        mock_api.delete_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "breaking_bad",
                "--season",
                "1",
                "--episode",
                "3",
                "--scene",
                "5",
                "--confirm",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene deleted" in clean_output
        assert "Renumbered scenes: 6, 7, 8" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_error(self, mock_api_class):
        """Test delete error handling."""
        mock_api = mock_api_class.return_value
        mock_result = DeleteSceneResult(
            success=False,
            error="Scene not found",
        )

        mock_api.delete_scene = AsyncMock(return_value=mock_result)

        result = runner.invoke(
            app,
            ["scene", "delete", "--project", "test", "--scene", "999", "--confirm"],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Scene not found" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_exception(self, mock_api_class):
        """Test delete command with exception."""
        mock_api = mock_api_class.return_value
        mock_api.delete_scene = AsyncMock(side_effect=Exception("Unexpected error"))

        result = runner.invoke(
            app,
            ["scene", "delete", "--project", "test", "--scene", "5", "--confirm"],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Failed to delete scene" in clean_output
        assert "Unexpected error" in clean_output
