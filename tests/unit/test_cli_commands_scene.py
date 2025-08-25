"""Unit tests for scene CLI commands with config option support."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
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


class TestSceneCommandsConfigOption:
    """Test the --config option for scene commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def sample_scene(self) -> Scene:
        """Create a sample scene for testing."""
        return Scene(
            number=1,
            heading="INT. OFFICE - DAY",
            content="Test scene content",
            original_text="Test scene content",
            content_hash="hash123",
        )

    @pytest.fixture
    def mock_scene_api(self) -> Generator[Mock, None, None]:
        """Mock SceneManagementAPI class."""
        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock:
            yield mock

    @pytest.fixture
    def mock_get_settings(self) -> Generator[Mock, None, None]:
        """Mock get_settings function."""
        with patch("scriptrag.cli.commands.scene_config.get_settings") as mock:
            yield mock

    @pytest.fixture
    def mock_scriptrag_settings(self) -> Generator[Mock, None, None]:
        """Mock ScriptRAGSettings class."""
        with patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings") as mock:
            yield mock

    def test_scene_read_with_config_file_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
        sample_scene: Scene,
    ) -> None:
        """Test scene read command with valid config file."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            last_read=None,
        )
        mock_api_instance.read_scene = AsyncMock(return_value=mock_result)

        # Execute command with config file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

    def test_scene_read_with_config_file_not_found(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene read command with non-existent config file."""
        # Use non-existent config file
        config_file = tmp_path / "nonexistent.yaml"

        # Execute command and expect exit
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
                "--config",
                str(config_file),
            ],
        )

        # Verify error handling
        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Error: Config file not found:" in clean_output
        # Check for filename in output (may be wrapped across lines)
        # Remove all whitespace to handle potential line wrapping
        assert "nonexistent.yaml" in clean_output.replace("\n", "").replace(" ", "")

        # Verify config loading was not attempted
        mock_scriptrag_settings.from_multiple_sources.assert_not_called()

    def test_scene_add_with_config_file_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene add command with valid config file."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = AddSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[],
        )
        mock_api_instance.add_scene = AsyncMock(return_value=mock_result)

        # Execute command with config file
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test_project",
                "--after-scene",
                "5",
                "--content",
                "INT. NEW SCENE - DAY\n\nNew content",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

    def test_scene_update_with_config_file_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene update command with valid config file."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = UpdateSceneResult(
            success=True,
            error=None,
            validation_errors=[],
        )
        mock_api_instance.update_scene = AsyncMock(return_value=mock_result)

        # Execute command with config file
        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test_project",
                "--scene",
                "3",
                "--content",
                "INT. OFFICE - DAY\n\nUpdated content.",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

    def test_scene_delete_with_config_file_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene delete command with valid config file."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = DeleteSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[],
        )
        mock_api_instance.delete_scene = AsyncMock(return_value=mock_result)

        # Execute command with config file
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "test_project",
                "--scene",
                "10",
                "--force",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

    def test_scene_read_bible_with_config_file_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene read bible with valid config file."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = BibleReadResult(
            success=True,
            error=None,
            content="Bible content here",
            bible_files=[],
        )
        mock_api_instance.read_bible = AsyncMock(return_value=mock_result)

        # Execute command with config file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--bible-name",
                "test.md",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

    def test_scene_config_loading_exception(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
    ) -> None:
        """Test scene command handles config loading exceptions."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Setup mock to raise exception during config loading
        mock_scriptrag_settings.from_multiple_sources.side_effect = Exception(
            "Config parse error"
        )

        # Execute command and expect exit
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
                "--config",
                str(config_file),
            ],
        )

        # Verify error handling
        assert result.exit_code == 1
        assert "Config parse error" in result.output

    def test_scene_with_config_fallback_to_default_settings(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
        sample_scene: Scene,
    ) -> None:
        """Test scene command falls back to default settings when no config."""
        # Setup mocks
        default_settings = MagicMock()
        default_settings.database_path = Path("/default/test.db")
        mock_get_settings.return_value = default_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            last_read=None,
        )
        mock_api_instance.read_scene = AsyncMock(return_value=mock_result)

        # Execute command without config
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify default settings were used
        mock_get_settings.assert_called_once()
        mock_scriptrag_settings.from_multiple_sources.assert_not_called()

        # Verify API was initialized with default settings
        mock_scene_api.assert_called_once_with(settings=default_settings)

    def test_scene_config_with_json_output(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
        sample_scene: Scene,
    ) -> None:
        """Test scene command with config file and JSON output."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "database_path: /custom/test.db\nscene:\n  output_format: json\n"
        )

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            last_read=None,
        )
        mock_api_instance.read_scene = AsyncMock(return_value=mock_result)

        # Execute command with config and JSON output
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
                "--json",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

        # Verify JSON output format
        assert "success" in result.output
        assert "scene_number" in result.output

    def test_scene_config_with_all_command_options(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_scene_api: Mock,
        mock_get_settings: Mock,
        mock_scriptrag_settings: Mock,
        sample_scene: Scene,
    ) -> None:
        """Test scene command with config file and all options."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "database_path: /custom/test.db\nscene:\n  timeout: 30\n"
        )

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.database_path = Path("/custom/test.db")
        mock_scriptrag_settings.from_multiple_sources.return_value = mock_settings

        mock_api_instance = mock_scene_api.return_value
        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            last_read=None,
        )
        mock_api_instance.read_scene = AsyncMock(return_value=mock_result)

        # Execute command with config and all options
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test_project",
                "--scene",
                "1",
                "--season",
                "2",
                "--episode",
                "5",
                "--config",
                str(config_file),
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify config was loaded
        mock_scriptrag_settings.from_multiple_sources.assert_called_once_with(
            config_files=[config_file]
        )

        # Verify API was initialized with custom settings
        mock_scene_api.assert_called_once_with(settings=mock_settings)

        # Verify scene identifier was created with all parameters
        mock_api_instance.read_scene.assert_called_once()
        call_args = mock_api_instance.read_scene.call_args[0]
        scene_id = call_args[0]
        assert scene_id.project == "test_project"
        assert scene_id.scene_number == 1
        assert scene_id.season == 2
        assert scene_id.episode == 5
