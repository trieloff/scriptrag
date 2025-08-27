"""Unit tests for the pull command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch("scriptrag.cli.commands.pull.get_settings") as mock:
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = Path("/tmp/test.db")
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_db_ops():
    """Mock database operations."""
    with patch("scriptrag.cli.commands.pull.DatabaseOperations") as mock:
        db_ops = MagicMock(
            spec=["check_database_exists", "transaction", "get_connection"]
        )
        mock.return_value = db_ops
        yield db_ops


@pytest.fixture
def mock_analyze_cmd():
    """Mock analyze command."""
    with patch("scriptrag.cli.commands.pull.AnalyzeCommand") as mock:
        cmd = MagicMock(spec=["analyze", "content", "model", "provider", "usage"])

        # Make analyze return a coroutine
        async def mock_analyze(*args, **kwargs):
            return cmd.analyze_return_value

        # Keep cmd.analyze as a MagicMock but with side_effect for async behavior
        cmd.analyze.side_effect = mock_analyze
        cmd.analyze_return_value = MagicMock(
            spec=["content", "model", "provider", "usage"]
        )
        mock.from_config.return_value = cmd
        yield cmd


@pytest.fixture
def mock_index_cmd():
    """Mock index command."""
    with patch("scriptrag.cli.commands.pull.IndexCommand") as mock:
        cmd = MagicMock(spec=["index", "content", "model", "provider", "usage"])

        # Make index return a coroutine
        async def mock_index(*args, **kwargs):
            return cmd.index_return_value

        # Keep cmd.index as a MagicMock but with side_effect for async behavior
        cmd.index.side_effect = mock_index
        cmd.index_return_value = MagicMock(
            spec=["content", "model", "provider", "usage"]
        )
        mock.from_config.return_value = cmd
        yield cmd


@pytest.fixture
def mock_initializer():
    """Mock database initializer."""
    with patch("scriptrag.api.DatabaseInitializer") as mock:
        init = MagicMock(spec=["initialize_database"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 5
        analyze_result.total_scenes_updated = 25
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 5
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 0
        analyze_result.total_scenes_updated = 0
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 10
        analyze_result.total_scenes_updated = 50
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 3
        analyze_result.errors = [
            "Error parsing file1.fountain",
            "Error in file2.fountain",
        ]
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result with errors
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        from tests.cli_fixtures import strip_ansi_codes

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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 2
        analyze_result.total_scenes_updated = 10
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 20
        analyze_result.total_scenes_updated = 100
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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

    def test_pull_with_no_recursive(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd, mock_index_cmd
    ):
        """Test pull command with no-recursive option."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock results
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 5
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
        index_result.total_scripts_indexed = 1
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 5
        index_result.total_characters_indexed = 2
        index_result.total_dialogues_indexed = 10
        index_result.total_actions_indexed = 8
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with no-recursive
        result = runner.invoke(app, ["pull", "--no-recursive"])

        # Verify success
        assert result.exit_code == 0

        # Verify recursive was set to False
        assert mock_analyze_cmd.analyze.call_count == 1
        call_kwargs = mock_analyze_cmd.analyze.call_args[1]
        assert call_kwargs["recursive"] is False

        assert mock_index_cmd.index.call_count == 1
        call_kwargs = mock_index_cmd.index.call_args[1]
        assert call_kwargs["recursive"] is False

    def test_pull_with_custom_config(
        self, runner, mock_db_ops, mock_analyze_cmd, mock_index_cmd, tmp_path
    ):
        """Test pull command with custom config file."""
        # Create a config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /tmp/custom.db\n")

        with patch(
            "scriptrag.cli.commands.pull.ScriptRAGSettings"
        ) as mock_settings_cls:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = Path("/tmp/custom.db")
            mock_settings_cls.from_multiple_sources.return_value = mock_settings

            # Setup mocks
            mock_db_ops.check_database_exists.return_value = True

            # Mock results
            analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
            analyze_result.total_files_updated = 1
            analyze_result.total_scenes_updated = 5
            analyze_result.errors = []
            mock_analyze_cmd.analyze_return_value = analyze_result

            index_result = MagicMock(spec=["content", "model", "provider", "usage"])
            index_result.total_scripts_indexed = 1
            index_result.total_scripts_updated = 0
            index_result.total_scenes_indexed = 5
            index_result.total_characters_indexed = 3
            index_result.total_dialogues_indexed = 10
            index_result.total_actions_indexed = 8
            index_result.errors = []
            mock_index_cmd.index_return_value = index_result

            # Run command with custom config
            result = runner.invoke(app, ["pull", "--config", str(config_file)])

            # Verify success
            assert result.exit_code == 0

            # Verify config was loaded
            mock_settings_cls.from_multiple_sources.assert_called_once()
            call_args = mock_settings_cls.from_multiple_sources.call_args
            assert call_args[1]["config_files"] == [config_file]

    def test_pull_with_no_updates_needed(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd, mock_index_cmd
    ):
        """Test pull command when no files need updates."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock analyze result with no updates
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 0
        analyze_result.total_scenes_updated = 0
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result with no updates
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
        index_result.total_scripts_indexed = 0
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 0
        index_result.total_characters_indexed = 0
        index_result.total_dialogues_indexed = 0
        index_result.total_actions_indexed = 0
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify success
        assert result.exit_code == 0
        assert "No files needed analysis updates" in result.output
        assert "No scripts needed indexing" in result.output

        # Should not show next steps when nothing was indexed
        assert "Next steps:" not in result.output

    def test_pull_handles_import_error(self, runner, mock_settings):
        """Test pull command handles import errors gracefully."""
        # Mock the check_database_exists to raise ImportError
        with patch("scriptrag.cli.commands.pull.DatabaseOperations") as mock_db_ops:
            mock_db_ops.side_effect = ImportError("Missing required library")

            # Run command
            result = runner.invoke(app, ["pull"])

            # Verify error handling
            assert result.exit_code == 1
            assert "Required components not available" in result.output
            assert "Missing required library" in result.output

    def test_pull_handles_general_exception(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd
    ):
        """Test pull command handles general exceptions."""
        # Make analyze raise an exception
        mock_analyze_cmd.analyze.side_effect = Exception("Unexpected error")

        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify error handling
        assert result.exit_code == 1
        assert "Error: Unexpected error" in result.output

    def test_pull_with_many_errors(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd, mock_index_cmd
    ):
        """Test pull command with more than 5 errors."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock analyze result with many errors
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 3
        analyze_result.errors = [
            f"Error {i}"
            for i in range(8)  # 8 errors
        ]
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
        index_result.total_scripts_indexed = 1
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 3
        index_result.total_characters_indexed = 2
        index_result.total_dialogues_indexed = 5
        index_result.total_actions_indexed = 4
        index_result.errors = []  # No index errors
        mock_index_cmd.index_return_value = index_result

        # Run command
        result = runner.invoke(app, ["pull"])

        # Verify error display
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        assert "Errors encountered: 8" in output
        assert "Error 0" in output
        assert "Error 4" in output
        assert "... and 3 more errors" in output  # Should show only first 5 + summary

    def test_pull_progress_callbacks(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd, mock_index_cmd
    ):
        """Test that progress callbacks are properly passed and called."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Capture the progress callbacks
        analyze_callback = None
        index_callback = None

        async def capture_analyze_callback(*args, **kwargs):
            nonlocal analyze_callback
            analyze_callback = kwargs.get("progress_callback")
            return mock_analyze_cmd.analyze_return_value

        async def capture_index_callback(*args, **kwargs):
            nonlocal index_callback
            index_callback = kwargs.get("progress_callback")
            return mock_index_cmd.index_return_value

        mock_analyze_cmd.analyze.side_effect = capture_analyze_callback
        mock_index_cmd.index.side_effect = capture_index_callback

        # Mock results
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 1
        analyze_result.total_scenes_updated = 5
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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

        # Verify callbacks were provided
        assert analyze_callback is not None
        assert index_callback is not None

        # Test the callbacks work
        # The analyze callback doesn't update percentage, just message
        analyze_callback(0.5, "Processing file...")

        # The index callback updates both percentage and message
        index_callback(0.75, "Indexing scenes...")

    def test_pull_dry_run_with_missing_db(
        self, runner, mock_settings, mock_db_ops, mock_analyze_cmd, mock_index_cmd
    ):
        """Test pull command in dry-run mode when database is missing."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = False

        # Mock results (should still run in dry-run mode)
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 0
        analyze_result.total_scenes_updated = 0
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
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
        assert "DRY RUN: Would initialize database" in result.output
        assert "DRY RUN COMPLETE" in result.output

    def test_pull_with_brittle_flag(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command with brittle flag passes it to analyze."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock analyze result
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 3
        analyze_result.total_scenes_updated = 15
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        # Mock index result
        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
        index_result.total_scripts_indexed = 3
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 15
        index_result.total_characters_indexed = 8
        index_result.total_dialogues_indexed = 30
        index_result.total_actions_indexed = 20
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command with brittle flag
        result = runner.invoke(app, ["pull", "--brittle"])

        # Verify success
        assert result.exit_code == 0

        # Verify brittle was passed to analyze command
        assert mock_analyze_cmd.analyze.call_count == 1
        call_kwargs = mock_analyze_cmd.analyze.call_args[1]
        assert call_kwargs["brittle"] is True

        # Verify index was called (but without brittle parameter)
        assert mock_index_cmd.index.call_count == 1
        call_kwargs = mock_index_cmd.index.call_args[1]
        assert "brittle" not in call_kwargs

    def test_pull_without_brittle_flag(
        self,
        runner,
        mock_settings,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
    ):
        """Test pull command without brittle flag defaults to False."""
        # Setup mocks
        mock_db_ops.check_database_exists.return_value = True

        # Mock results
        analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
        analyze_result.total_files_updated = 2
        analyze_result.total_scenes_updated = 8
        analyze_result.errors = []
        mock_analyze_cmd.analyze_return_value = analyze_result

        index_result = MagicMock(spec=["content", "model", "provider", "usage"])
        index_result.total_scripts_indexed = 2
        index_result.total_scripts_updated = 0
        index_result.total_scenes_indexed = 8
        index_result.total_characters_indexed = 4
        index_result.total_dialogues_indexed = 16
        index_result.total_actions_indexed = 12
        index_result.errors = []
        mock_index_cmd.index_return_value = index_result

        # Run command without brittle flag
        result = runner.invoke(app, ["pull"])

        # Verify success
        assert result.exit_code == 0

        # Verify brittle was passed as False to analyze command
        assert mock_analyze_cmd.analyze.call_count == 1
        call_kwargs = mock_analyze_cmd.analyze.call_args[1]
        assert call_kwargs["brittle"] is False

    def test_pull_config_file_not_found(
        self, runner, mock_settings, mock_db_ops, tmp_path
    ):
        """Test pull command with non-existent config file."""
        # Use non-existent config file
        config_file = tmp_path / "nonexistent.yaml"

        # Run command
        result = runner.invoke(app, ["pull", "--config", str(config_file)])

        # Verify error handling
        assert result.exit_code == 1
        # The error message might have formatting/newlines from Rich console
        # Check for both parts separately as they may be on different lines
        assert "Error: Config file not found:" in result.output
        # Check for filename in output (may be wrapped across lines)
        # Remove all whitespace to handle potential line wrapping
        assert "nonexistent.yaml" in result.output.replace("\n", "").replace(" ", "")

    def test_pull_config_loading_exception(
        self, runner, mock_db_ops, mock_analyze_cmd, mock_index_cmd, tmp_path
    ):
        """Test pull command handles config loading exceptions."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        # Mock ScriptRAGSettings to raise exception
        with patch(
            "scriptrag.cli.commands.pull.ScriptRAGSettings"
        ) as mock_settings_cls:
            mock_settings_cls.from_multiple_sources.side_effect = Exception(
                "Config parse error"
            )

            # Run command
            result = runner.invoke(app, ["pull", "--config", str(config_file)])

            # Verify error handling
            assert result.exit_code == 1
            assert "Config parse error" in result.output

    def test_pull_with_config_and_other_options(
        self,
        runner,
        mock_db_ops,
        mock_analyze_cmd,
        mock_index_cmd,
        tmp_path,
    ):
        """Test pull command with config file and other CLI options."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        with patch(
            "scriptrag.cli.commands.pull.ScriptRAGSettings"
        ) as mock_settings_cls:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = Path("/custom/test.db")
            mock_settings_cls.from_multiple_sources.return_value = mock_settings

            # Setup mocks
            mock_db_ops.check_database_exists.return_value = True

            # Mock results
            analyze_result = MagicMock(spec=["content", "model", "provider", "usage"])
            analyze_result.total_files_updated = 3
            analyze_result.total_scenes_updated = 15
            analyze_result.errors = []
            mock_analyze_cmd.analyze_return_value = analyze_result

            index_result = MagicMock(spec=["content", "model", "provider", "usage"])
            index_result.total_scripts_indexed = 3
            index_result.total_scripts_updated = 0
            index_result.total_scenes_indexed = 15
            index_result.total_characters_indexed = 8
            index_result.total_dialogues_indexed = 30
            index_result.total_actions_indexed = 20
            index_result.errors = []
            mock_index_cmd.index_return_value = index_result

            # Run command with config and other options
            result = runner.invoke(
                app,
                [
                    "pull",
                    "/custom/path",
                    "--config",
                    str(config_file),
                    "--force",
                    "--batch-size",
                    "20",
                    "--no-recursive",
                ],
            )

            # Verify success
            assert result.exit_code == 0

            # Verify config was loaded
            mock_settings_cls.from_multiple_sources.assert_called_once_with(
                config_files=[config_file]
            )

            # Verify other options were passed correctly
            assert mock_analyze_cmd.analyze.call_count == 1
            call_kwargs = mock_analyze_cmd.analyze.call_args[1]
            assert call_kwargs["path"] == Path("/custom/path")
            assert call_kwargs["force"] is True
            assert call_kwargs["recursive"] is False

            assert mock_index_cmd.index.call_count == 1
            call_kwargs = mock_index_cmd.index.call_args[1]
            assert call_kwargs["path"] == Path("/custom/path")
            assert call_kwargs["batch_size"] == 20
            assert call_kwargs["recursive"] is False
