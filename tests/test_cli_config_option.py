"""Tests for --config option in all CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from scriptrag.api.scene_models import (
    AddSceneResult,
    BibleReadResult,
    DeleteSceneResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.main import app
from scriptrag.parser import Scene
from tests.cli_fixtures import CleanCliRunner

runner = CleanCliRunner()


class TestConfigOptionSceneCommands:
    """Test --config option for scene commands."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings")
    def test_scene_read_with_config(self, mock_settings_class, mock_api_class):
        """Test scene read with custom config file."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            config_data = {
                "database": {"path": "/custom/path/database.db"},
                "llm": {"provider": "claude-code"},
            }
            yaml.dump(config_data, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_api = mock_api_class.return_value
            mock_scene = Scene(
                number=1,
                heading="INT. OFFICE - DAY",
                content="INT. OFFICE - DAY\n\nTest content.",
                original_text="INT. OFFICE - DAY\n\nTest content.",
                content_hash="hash123",
            )

            mock_result = ReadSceneResult(
                success=True,
                error=None,
                scene=mock_scene,
                last_read=None,
            )

            mock_api.read_scene = AsyncMock(return_value=mock_result)

            # Run command with config
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
                    config_path,
                ],
            )

            result.assert_success()
            # Verify settings were loaded from config
            mock_settings_class.from_multiple_sources.assert_called_once_with(
                config_files=[Path(config_path)]
            )
            # Verify API was initialized with custom settings
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings")
    def test_scene_add_with_config(self, mock_settings_class, mock_api_class):
        """Test scene add with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as config_file:
            config_file.write('[database]\npath = "/custom/db.db"\n')
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_api = mock_api_class.return_value
            mock_result = AddSceneResult(
                success=True,
                error=None,
                renumbered_scenes=[],
            )

            mock_api.add_scene = AsyncMock(return_value=mock_result)

            # Run command with config
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
                    "INT. NEW SCENE - DAY\n\nNew content",
                    "--config",
                    config_path,
                ],
            )

            result.assert_success()
            # Verify custom settings were used
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings")
    def test_scene_update_with_config(self, mock_settings_class, mock_api_class):
        """Test scene update with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as config_file:
            json.dump({"database": {"path": "/custom/path.db"}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_api = mock_api_class.return_value
            mock_result = UpdateSceneResult(
                success=True,
                error=None,
                validation_errors=[],
            )

            # Mock read_scene to return success (scene exists)
            mock_read_result = ReadSceneResult(
                success=True,
                error=None,
                scene=Scene(
                    number=3,
                    heading="INT. OFFICE - DAY",
                    content="Original content",
                    original_text="Original content",
                    content_hash="original_hash",
                ),
                last_read=None,
            )
            mock_api.read_scene = AsyncMock(return_value=mock_read_result)
            mock_api.update_scene = AsyncMock(return_value=mock_result)

            # Run command with config
            result = runner.invoke(
                app,
                [
                    "scene",
                    "update",
                    "--project",
                    "test",
                    "--scene",
                    "3",
                    "--content",
                    "INT. OFFICE - DAY\n\nUpdated content.",
                    "--config",
                    config_path,
                ],
            )

            result.assert_success()
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings")
    def test_scene_delete_with_config(self, mock_settings_class, mock_api_class):
        """Test scene delete with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            yaml.dump({"fountain": {"max_depth": 5}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_api = mock_api_class.return_value
            mock_result = DeleteSceneResult(
                success=True,
                error=None,
                renumbered_scenes=[],
            )

            mock_api.delete_scene = AsyncMock(return_value=mock_result)

            # Run command with config
            result = runner.invoke(
                app,
                [
                    "scene",
                    "delete",
                    "--project",
                    "test",
                    "--scene",
                    "10",
                    "--force",
                    "--config",
                    config_path,
                ],
            )

            result.assert_success()
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.cli.commands.scene_config.ScriptRAGSettings")
    def test_scene_read_bible_with_config(self, mock_settings_class, mock_api_class):
        """Test reading bible files with custom config."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            yaml.dump({"bible": {"enabled": True}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_api = mock_api_class.return_value
            mock_result = BibleReadResult(
                success=True,
                error=None,
                content="Bible content here",
                bible_files=[],
            )

            mock_api.read_bible = AsyncMock(return_value=mock_result)

            # Run command with config
            result = runner.invoke(
                app,
                [
                    "scene",
                    "read",
                    "--project",
                    "test",
                    "--bible-name",
                    "test.md",
                    "--config",
                    config_path,
                ],
            )

            result.assert_success()
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionAnalyzeCommand:
    """Test --config option for analyze command."""

    @patch("scriptrag.api.analyze.AnalyzeCommand")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    def test_analyze_with_config(self, mock_settings_class, mock_command_class):
        """Test analyze command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            yaml.dump({"analyzer": {"max_workers": 8}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_command = MagicMock()
            mock_result = MagicMock()
            mock_result.total_files_updated = 1
            mock_result.total_scenes_updated = 5
            mock_result.files = []
            mock_result.errors = []

            async def mock_analyze(*args, **kwargs):
                return mock_result

            mock_command.analyze.side_effect = mock_analyze
            mock_command_class.from_config.return_value = mock_command

            # Temporarily override global settings
            with patch("scriptrag.config.settings._settings", mock_settings):
                # Run command with config
                result = runner.invoke(
                    app,
                    ["analyze", "--config", config_path],
                )

                result.assert_success()
                # Verify settings were loaded from config
                mock_settings_class.from_multiple_sources.assert_called_once_with(
                    config_files=[Path(config_path)]
                )
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionListCommand:
    """Test --config option for list command."""

    @patch("scriptrag.api.ScriptLister")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    def test_list_with_config(self, mock_settings_class, mock_command_class):
        """Test list command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as config_file:
            config_file.write('[database]\npath = "/custom/list.db"\n')
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_command = MagicMock()
            mock_result = MagicMock()
            mock_result.projects = ["project1", "project2"]
            mock_result.total_scripts = 2
            mock_result.total_scenes = 100

            async def mock_list(*args, **kwargs):
                return mock_result

            mock_command.list_scripts.side_effect = mock_list
            mock_command_class.return_value = mock_command

            # Temporarily override global settings
            with patch("scriptrag.config.settings._settings", mock_settings):
                # Run command with config
                result = runner.invoke(
                    app,
                    ["list", "--config", config_path],
                )

                result.assert_success()
                mock_settings_class.from_multiple_sources.assert_called_once()
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionIndexCommand:
    """Test --config option for index command."""

    @patch("scriptrag.api.index.IndexCommand")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    def test_index_with_config(self, mock_settings_class, mock_command_class):
        """Test index command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as config_file:
            json.dump({"index": {"batch_size": 50}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_command = MagicMock()
            mock_result = MagicMock()
            mock_result.scripts_indexed = 5
            mock_result.total_scripts_indexed = 5
            mock_result.total_scripts_updated = 0
            mock_result.total_scenes_indexed = 25
            mock_result.total_characters_indexed = 10
            mock_result.total_dialogues_indexed = 30
            mock_result.total_actions_indexed = 20
            mock_result.scripts = []
            mock_result.errors = []

            async def mock_index(*args, **kwargs):
                return mock_result

            mock_command.index.side_effect = mock_index
            mock_command_class.return_value = mock_command

            # Run command with config
            result = runner.invoke(
                app,
                ["index", "test.fountain", "--config", config_path],
            )

            result.assert_success()
            mock_settings_class.from_multiple_sources.assert_called_once_with(
                config_files=[Path(config_path)]
            )
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionQueryCommand:
    """Test --config option for query command."""

    def test_query_with_config(self):
        """Test query command with custom config file - config validation only."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            yaml.dump({"llm": {"model": "claude-3-opus"}}, config_file)
            config_path = config_file.name

        try:
            # Test that config file is validated
            # Query command will fail because no subcommands are defined in test,
            # but it should validate the config file first
            result = runner.invoke(
                app,
                ["query", "--config", config_path, "--help"],
            )

            # Should show help (with available query commands)
            result.assert_contains("Usage:", "query")

            # Test with non-existent config
            result = runner.invoke(
                app,
                ["query", "--config", "/nonexistent.yaml", "--help"],
            )
            # Should still work with --help even with bad config
            result.assert_contains("Usage:")
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_scene_with_nonexistent_config(self):
        """Test scene command with non-existent config file."""
        # Create a path to a non-existent config file
        config_path = Path("/tmp/nonexistent_config.toml")

        # Run command with non-existent config
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test",
                "--scene",
                "1",
                "--config",
                str(config_path),
            ],
        )

        # Should fail with appropriate error
        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")

    def test_scene_add_with_nonexistent_config(self):
        """Test scene add command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_config.toml")

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "test",
                "--after-scene",
                "1",
                "--content",
                "INT. OFFICE - DAY\n\nTest content.",
                "--config",
                str(config_path),
            ],
        )

        # Should fail with config file not found error
        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")

    def test_scene_update_with_nonexistent_config(self):
        """Test scene update command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_config.toml")

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "test",
                "--scene",
                "1",
                "--content",
                "INT. OFFICE - DAY\n\nUpdated content.",
                "--config",
                str(config_path),
            ],
        )

        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")

    def test_scene_delete_with_nonexistent_config(self):
        """Test scene delete command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_config.toml")

        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "test",
                "--scene",
                "1",
                "--force",
                "--config",
                str(config_path),
            ],
        )

        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")

    def test_scene_bible_with_nonexistent_config(self):
        """Test scene read_bible command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_config.toml")

        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "test",
                "--bible",
                "--config",
                str(config_path),
            ],
        )

        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")


class TestConfigOptionSearchCommand:
    """Test --config option for search command."""

    @patch("scriptrag.cli.commands.search.SearchAPI")
    @patch("scriptrag.config.get_settings")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    def test_search_with_config(
        self, mock_settings_class, mock_get_settings, mock_search_api
    ):
        """Test search command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as config_file:
            config_file.write("[search]\nmax_results = 20\n")
            config_path = config_file.name

        try:
            # Create a temporary database file
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
                db_path = Path(db_file.name)

            # Setup mocks
            mock_settings = MagicMock()
            mock_settings.database_path = db_path
            mock_settings_class.from_multiple_sources.return_value = mock_settings
            mock_get_settings.return_value = mock_settings

            # Mock the SearchAPI
            mock_search_instance = MagicMock()
            mock_search_api.return_value = mock_search_instance

            # Mock search result
            mock_result = MagicMock()
            mock_result.results = []
            mock_result.total_found = 0
            mock_result.query = "test query"
            mock_result.mode = "semantic"

            def mock_search(*args, **kwargs):
                return mock_result

            mock_search_instance.search = MagicMock(side_effect=mock_search)

            # Run command with config
            result = runner.invoke(
                app,
                ["search", "--config", config_path, "test query"],
            )

            result.assert_success()
            mock_settings_class.from_multiple_sources.assert_called_once()
        finally:
            Path(config_path).unlink(missing_ok=True)
            db_path.unlink(missing_ok=True)

    def test_search_with_nonexistent_config(self):
        """Test search command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_search_config.toml")

        result = runner.invoke(
            app,
            ["search", "test query", "--config", str(config_path)],
        )

        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")

    def test_analyze_with_nonexistent_config(self):
        """Test analyze command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_analyze_config.toml")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                ["analyze", tmpdir, "--config", str(config_path)],
            )

            result.assert_failure(exit_code=1)
            result.assert_contains("Error: Config file not found")

    def test_index_with_nonexistent_config(self):
        """Test index command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_index_config.toml")

        with tempfile.NamedTemporaryFile(suffix=".fountain", delete=False) as f:
            f.write(b"Title: Test\n\nINT. TEST - DAY\n\nTest scene.")
            fountain_path = f.name

        try:
            result = runner.invoke(
                app,
                ["index", fountain_path, "--config", str(config_path)],
            )

            result.assert_failure(exit_code=1)
            result.assert_contains("Error: Config file not found")
        finally:
            Path(fountain_path).unlink(missing_ok=True)

    def test_init_with_nonexistent_config(self):
        """Test init command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_init_config.toml")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            result = runner.invoke(
                app,
                ["init", "--db-path", str(db_path), "--config", str(config_path)],
            )

            result.assert_failure(exit_code=1)
            result.assert_contains("Error: Config file not found")

    def test_list_with_nonexistent_config(self):
        """Test list command with non-existent config file."""
        config_path = Path("/tmp/nonexistent_list_config.toml")

        result = runner.invoke(
            app,
            ["list", "--config", str(config_path)],
        )

        result.assert_failure(exit_code=1)
        result.assert_contains("Error: Config file not found")
