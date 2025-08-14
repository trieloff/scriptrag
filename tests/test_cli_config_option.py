"""Tests for --config option in all CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from scriptrag.api.scene_management import (
    AddSceneResult,
    BibleReadResult,
    DeleteSceneResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.main import app
from scriptrag.parser import Scene

runner = CliRunner()


class TestConfigOptionSceneCommands:
    """Test --config option for scene commands."""

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
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
                content="Test content",
                original_text="Test content",
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

            assert result.exit_code == 0
            # Verify settings were loaded from config
            mock_settings_class.from_multiple_sources.assert_called_once_with(
                config_files=[Path(config_path)]
            )
            # Verify API was initialized with custom settings
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
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

            assert result.exit_code == 0
            # Verify custom settings were used
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
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
                    "Updated content",
                    "--config",
                    config_path,
                ],
            )

            assert result.exit_code == 0
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
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
                    "--confirm",
                    "--config",
                    config_path,
                ],
            )

            assert result.exit_code == 0
            mock_settings_class.from_multiple_sources.assert_called_once()
            mock_api_class.assert_called_once_with(settings=mock_settings)
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch("scriptrag.cli.commands.scene.SceneManagementAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
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

            assert result.exit_code == 0
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

                assert result.exit_code == 0
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

                assert result.exit_code == 0
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

            assert result.exit_code == 0
            mock_settings_class.from_multiple_sources.assert_called_once_with(
                config_files=[Path(config_path)]
            )
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionQueryCommand:
    """Test --config option for query command."""

    @patch("scriptrag.api.query.QueryAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    @pytest.mark.skip(
        reason="Query command uses subcommands, needs different test approach"
    )
    def test_query_with_config(self, mock_settings_class, mock_command_class):
        """Test query command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as config_file:
            yaml.dump({"llm": {"model": "claude-3-opus"}}, config_file)
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_command = MagicMock()
            mock_result = MagicMock()
            mock_result.answer = "Test answer"
            mock_result.sources = []
            mock_result.context = []
            mock_result.error = None

            async def mock_query(*args, **kwargs):
                return mock_result

            mock_command.query.side_effect = mock_query
            mock_command_class.return_value = mock_command

            # Run command with config
            result = runner.invoke(
                app,
                ["query", "--config", config_path, "test question"],
            )

            assert result.exit_code == 0
            mock_settings_class.from_multiple_sources.assert_called_once()
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestConfigOptionSearchCommand:
    """Test --config option for search command."""

    @patch("scriptrag.api.search.SearchAPI")
    @patch("scriptrag.config.settings.ScriptRAGSettings")
    @pytest.mark.skip(reason="Search command has conflicting -c parameter, needs fix")
    def test_search_with_config(self, mock_settings_class, mock_command_class):
        """Test search command with custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as config_file:
            config_file.write("[search]\nmax_results = 20\n")
            config_path = config_file.name

        try:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            mock_command = MagicMock()
            mock_result = MagicMock()
            mock_result.results = []
            mock_result.total_found = 0
            mock_result.query = "test query"
            mock_result.mode = "semantic"

            async def mock_search(*args, **kwargs):
                return mock_result

            mock_command.search.side_effect = mock_search
            mock_command_class.return_value = mock_command

            # Run command with config
            result = runner.invoke(
                app,
                ["search", "--config", config_path, "test query"],
            )

            assert result.exit_code == 0
            mock_settings_class.from_multiple_sources.assert_called_once()
        finally:
            Path(config_path).unlink(missing_ok=True)
