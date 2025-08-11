"""Unit tests for the pull command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch("scriptrag.cli.commands.pull.get_settings") as mock:
        settings = MagicMock()
        settings.database_path = Path("/tmp/test.db")
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_db_ops():
    """Mock database operations."""
    with patch("scriptrag.cli.commands.pull.DatabaseOperations") as mock:
        db_ops = MagicMock()
        mock.return_value = db_ops
        yield db_ops


@pytest.fixture
def mock_analyze_cmd():
    """Mock analyze command."""
    with patch("scriptrag.cli.commands.pull.AnalyzeCommand") as mock:
        cmd = MagicMock()

        # Make analyze return a coroutine
        async def mock_analyze(*args, **kwargs):
            return cmd.analyze_return_value

        # Keep cmd.analyze as a MagicMock but with side_effect for async behavior
        cmd.analyze.side_effect = mock_analyze
        cmd.analyze_return_value = MagicMock()
        mock.from_config.return_value = cmd
        yield cmd


@pytest.fixture
def mock_index_cmd():
    """Mock index command."""
    with patch("scriptrag.cli.commands.pull.IndexCommand") as mock:
        cmd = MagicMock()

        # Make index return a coroutine
        async def mock_index(*args, **kwargs):
            return cmd.index_return_value

        # Keep cmd.index as a MagicMock but with side_effect for async behavior
        cmd.index.side_effect = mock_index
        cmd.index_return_value = MagicMock()
        mock.from_config.return_value = cmd
        yield cmd


@pytest.fixture
def mock_initializer():
    """Mock database initializer."""
    with patch("scriptrag.api.DatabaseInitializer") as mock:
        init = MagicMock()
        mock.return_value = init
        yield init


class TestPullCommand:
    """Test pull command functionality."""

    def test_pull_command_help(self, runner):
        """Test pull command shows help."""
        result = runner.invoke(app, ["pull", "--help"])
        assert result.exit_code == 0
        assert "Pull fountain files into the database" in result.output

    def test_pull_with_existing_database(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with existing database."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock analyze result
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 5
        analyze_result.total_scenes_updated = 25
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock()
        index_result.total_scripts_indexed = 3
        index_result.total_scripts_updated = 2
        index_result.total_scenes_indexed = 25
        index_result.total_characters_indexed = 10
        index_result.total_dialogues_indexed = 50
        index_result.total_actions_indexed = 30
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify success
        assert result.exit_code == 0
        assert "Analyzing Fountain files" in result.output
        assert "Indexing into database" in result.output
        assert "Pull complete" in result.output

        # Verify calls
        mock_db_ops.check_database_exists.assert_called_once()
        assert mock_analyze_cmd.analyze.call_count == 1
        assert mock_index_cmd.index.call_count == 1

    def test_pull_initializes_database_if_missing(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
        mock_initializer,
    ):
        """Test pull command initializes database if it doesn't exist."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = False
        mock_initializer.initialize_database.return_value = Path("/tmp/test.db")

        # Mock analyze result
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 5
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock()
        index_result.total_scripts_indexed = 1
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 5
        index_result.total_characters_indexed = 3
        index_result.total_dialogues_indexed = 10
        index_result.total_actions_indexed = 8
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify success
        assert result.exit_code == 0
        assert "Database not found. Initializing" in result.output
        assert "Database initialized" in result.output

        # Verify initialization was called
        mock_initializer.initialize_database.assert_called_once()

    def test_pull_with_dry_run(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with dry-run option."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = False

        # Mock analyze result
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 0
        analyze_result.total_scenes_updated = 0
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock()
        index_result.total_scripts_indexed = 0
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 0
        index_result.total_characters_indexed = 0
        index_result.total_dialogues_indexed = 0
        index_result.total_actions_indexed = 0
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with dry-run
        result = runner.invoke(app, ["pull", "--dry-run"])

        # Verify success
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "No changes were made" in result.output

    def test_pull_with_force_option(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with force option."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock results
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 10
        analyze_result.total_scenes_updated = 50
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock()
        index_result.total_scripts_indexed = 0
        index_result.total_scripts_updated = 10
        index_result.total_scenes_indexed = 50
        index_result.total_characters_indexed = 20
        index_result.total_dialogues_indexed = 100
        index_result.total_actions_indexed = 60
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with force
        result = runner.invoke(app, ["pull", "--force"])

        # Verify success
        assert result.exit_code == 0

        # Verify force was passed to analyze command only
        # (index no longer accepts force)
        assert mock_analyze_cmd.analyze.call_count == 1
        call_kwargs = mock_analyze_cmd.analyze.call_args[1]
        assert call_kwargs["force"] is True

        # Verify index was called (but without force parameter)
        assert mock_index_cmd.index.call_count == 1
        call_kwargs = mock_index_cmd.index.call_args[1]
        assert "force" not in call_kwargs

    def test_pull_handles_errors(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command handles errors gracefully."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock analyze result with errors
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 3
        analyze_result.errors = [
            "Error parsing file1.fountain",
            "Error in file2.fountain",
        ]
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result with errors
        index_result = MagicMock()
        index_result.total_scripts_indexed = 0
        index_result.total_scripts_updated = 1
        index_result.total_scenes_indexed = 3
        index_result.total_characters_indexed = 2
        index_result.total_dialogues_indexed = 5
        index_result.total_actions_indexed = 4
        index_result.errors = ["Database error: constraint violation"]
        mock_index_cmd.index_return_value = index_result

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify completion despite errors
        from scriptrag.tools.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        assert "Errors encountered: 3" in output
        assert "Error parsing file1.fountain" in output

    def test_pull_with_custom_path(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with custom path."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock results
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 2
        analyze_result.total_scenes_updated = 10
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock()
        index_result.total_scripts_indexed = 2
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 10
        index_result.total_characters_indexed = 5
        index_result.total_dialogues_indexed = 20
        index_result.total_actions_indexed = 15
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with custom path
        result = runner.invoke(app, ["pull", "/custom/path"])

        # Verify success
        assert result.exit_code == 0

        # Verify path was passed correctly
        assert mock_analyze_cmd.analyze.call_count == 1
        call_kwargs = mock_analyze_cmd.analyze.call_args[1]
        assert call_kwargs["path"] == Path("/custom/path")

        assert mock_index_cmd.index.call_count == 1
        call_kwargs = mock_index_cmd.index.call_args[1]
        assert call_kwargs["path"] == Path("/custom/path")

    def test_pull_with_batch_size(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with custom batch size."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock results
        analyze_result = MagicMock()
        analyze_result.total_files_updated = 20
        analyze_result.total_scenes_updated = 100
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock()
        index_result.total_scripts_indexed = 20
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 100
        index_result.total_characters_indexed = 40
        index_result.total_dialogues_indexed = 200
        index_result.total_actions_indexed = 150
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with custom batch size
        result = runner.invoke(app, ["pull", "--batch-size", "5"])

        # Verify success
        assert result.exit_code == 0

        # Verify batch size was passed to index command
        assert mock_index_cmd.index.call_count == 1
        call_kwargs = mock_index_cmd.index.call_args[1]
        assert call_kwargs["batch_size"] == 5
