"""Tests for scene management CLI commands."""

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from scriptrag.api.scene_management import (
    AddSceneResult,
    DeleteSceneResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.main import app
from scriptrag.parser import Scene
from tests.cli_fixtures import strip_ansi_codes

runner = CliRunner()


class TestSceneReadCommand:
    """Test scene read CLI command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_scene_success(self, mock_api_class):
        """Test successful scene read."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=3,
            heading="INT. COFFEE SHOP - DAY",
            content="Walter enters.",
            original_text="Walter enters.",
            content_hash="hash123",
        )

        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=mock_scene,
            last_read=None,
        )

        # Make read_scene async
        mock_api.read_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "breaking_bad", "--scene", "3"],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Walter enters" in clean_output
        # Token system eliminated - no longer checking for tokens

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_scene_json_output(self, mock_api_class):
        """Test scene read with JSON output."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=3,
            heading="INT. COFFEE SHOP - DAY",
            content="Walter enters.",
            original_text="Walter enters.",
            content_hash="hash123",
        )

        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=mock_scene,
            last_read=None,
        )

        mock_api.read_scene = AsyncMock(return_value=mock_result)

        # Run command with JSON flag
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test", "--scene", "3", "--json"],
        )

        assert result.exit_code == 0

        # Parse JSON output (Rich's print_json outputs multi-line formatted JSON)
        # Join all lines to get the complete JSON string
        json_str = strip_ansi_codes(result.output).strip()
        json_output = json.loads(json_str)

        assert json_output["success"] is True
        assert json_output["scene_number"] == 3
        assert json_output["heading"] == "INT. COFFEE SHOP - DAY"
        # Token system eliminated - no longer checking for session_token

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_scene_not_found(self, mock_api_class):
        """Test reading non-existent scene."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = ReadSceneResult(
            success=False,
            error="Scene not found",
            scene=None,
            last_read=None,
        )

        mock_api.read_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "test", "--scene", "999"],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Scene not found" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_read_tv_scene(self, mock_api_class):
        """Test reading TV show scene."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=5,
            heading="EXT. DESERT - DAY",
            content="The RV sits alone.",
            original_text="The RV sits alone.",
            content_hash="hash456",
        )

        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=mock_scene,
            last_read=None,
        )

        mock_api.read_scene = AsyncMock(return_value=mock_result)

        # Run command with season/episode
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
                "1",
                "--scene",
                "5",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "The RV sits alone" in clean_output
        # Token system eliminated - no longer checking for tokens


class TestSceneAddCommand:
    """Test scene add CLI command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_after(self, mock_api_class):
        """Test adding scene after reference."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=5,
            heading="INT. NEW SCENE - DAY",
            content="New content",
            original_text="New content",
            content_hash="new_hash",
        )

        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=mock_scene,
            renumbered_scenes=[6, 7, 8],
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "4",
                "--content",
                "INT. NEW SCENE - DAY\n\nNew content",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene added" in clean_output
        assert "Renumbered scenes: 6, 7, 8" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_before(self, mock_api_class):
        """Test adding scene before reference."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=10,
            heading="INT. NEW SCENE - DAY",
            content="New content",
            original_text="New content",
            content_hash="new_hash",
        )

        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=mock_scene,
            renumbered_scenes=[11, 12],
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--before-scene",
                "10",
                "--content",
                "INT. NEW SCENE - DAY\n\nNew content",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene added" in clean_output

    def test_add_scene_no_position(self):
        """Test add scene without position."""
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
        """Test add scene with both positions."""
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
                "10",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Cannot specify both" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_add_scene_validation_error(self, mock_api_class):
        """Test adding invalid scene."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = AddSceneResult(
            success=False,
            error="Invalid Fountain format: Missing scene heading",
        )

        mock_api.add_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "4",
                "--content",
                "Not a valid scene",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Invalid Fountain format" in clean_output


class TestSceneUpdateCommand:
    """Test scene update CLI command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_success(self, mock_api_class):
        """Test successful scene update."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_scene = Scene(
            number=5,
            heading="INT. UPDATED - DAY",
            content="Updated content",
            original_text="Updated content",
            content_hash="updated_hash",
        )

        mock_result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=mock_scene,
            validation_errors=[],
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
                "--safe",
                "--last-read",
                "2024-01-15T10:30:00",
                "--content",
                "INT. UPDATED - DAY\n\nUpdated content",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene updated" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_invalid_token(self, mock_api_class):
        """Test update with invalid content validation."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = UpdateSceneResult(
            success=False,
            error="Scene validation failed",
            validation_errors=["INVALID_FORMAT"],
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
                "--safe",
                "--last-read",
                "2024-01-15T10:30:00",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Scene validation failed" in clean_output
        assert "INVALID_FORMAT" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_update_scene_concurrent_modification(self, mock_api_class):
        """Test update with content modification detection."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = UpdateSceneResult(
            success=False,
            error="Scene was modified by another process",
            validation_errors=["CONCURRENT_MODIFICATION"],
        )

        mock_api.update_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "5",
                "--safe",
                "--last-read",
                "2024-01-15T10:30:00",
                "--content",
                "INT. SCENE - DAY\n\nContent",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "modified by another process" in clean_output

    def test_update_scene_no_content(self):
        """Test update without content.

        Note: In test environment, CLI reads empty string from stdin
        instead of detecting TTY mode, so we get validation error
        instead of "No content provided" error.
        """
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
        )

        assert result.exit_code == 1
        # In test environment, empty stdin results in validation error
        # rather than "No content provided"
        clean_output = strip_ansi_codes(result.output)
        assert "Invalid Fountain format" in clean_output


class TestSceneDeleteCommand:
    """Test scene delete CLI command."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_scene_success(self, mock_api_class):
        """Test successful scene deletion."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = DeleteSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[6, 7, 8],
        )

        mock_api.delete_scene = AsyncMock(return_value=mock_result)

        # Run command with confirm
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "test",
                "--scene",
                "5",
                "--confirm",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene deleted" in clean_output
        assert "Renumbered scenes: 6, 7, 8" in clean_output

    def test_delete_scene_no_confirm(self):
        """Test delete without confirmation."""
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "test",
                "--scene",
                "5",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Warning" in clean_output
        assert "--confirm" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_scene_not_found(self, mock_api_class):
        """Test deleting non-existent scene."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = DeleteSceneResult(
            success=False,
            error="Scene not found",
        )

        mock_api.delete_scene = AsyncMock(return_value=mock_result)

        # Run command
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "test",
                "--scene",
                "999",
                "--confirm",
            ],
        )

        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Scene not found" in clean_output

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    def test_delete_tv_scene(self, mock_api_class):
        """Test deleting TV show scene."""
        # Setup mock
        mock_api = mock_api_class.return_value
        mock_result = DeleteSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[],
        )

        mock_api.delete_scene = AsyncMock(return_value=mock_result)

        # Run command with season/episode
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "breaking_bad",
                "--season",
                "2",
                "--episode",
                "3",
                "--scene",
                "10",
                "--confirm",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.output)
        assert "Scene deleted" in clean_output
