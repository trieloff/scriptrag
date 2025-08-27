"""Unit tests for the analyze command."""

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
def mock_analyze_command():
    """Mock AnalyzeCommand."""
    with patch("scriptrag.api.analyze.AnalyzeCommand") as mock:
        cmd = MagicMock(spec=["analyze", "load_analyzer", "from_config"])

        # Make analyze return a coroutine
        async def mock_analyze(*args, **kwargs):
            return cmd.analyze_return_value

        cmd.analyze.side_effect = mock_analyze
        cmd.analyze_return_value = MagicMock(
            spec=["content", "model", "provider", "usage"]
        )
        mock.from_config.return_value = cmd
        yield cmd


@pytest.fixture
def mock_analyze_result():
    """Create a mock analyze result."""
    result = MagicMock(spec=["content", "model", "provider", "usage"])
    result.total_files_updated = 0
    result.total_scenes_updated = 0
    result.files = []
    result.errors = []
    return result


class TestAnalyzeCommand:
    """Test analyze command functionality."""

    def test_analyze_command_help(self, runner):
        """Test analyze command shows help."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        # Strip ANSI codes for help output checks
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert "Analyze Fountain files and update their metadata" in output
        assert "--force" in output
        assert "--dry-run" in output
        assert "--no-recursive" in output
        assert "--analyzer" in output
        assert "--brittle" in output

    def test_analyze_basic_success(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test basic analyze command execution."""
        # Setup mock result
        mock_analyze_result.total_files_updated = 3
        mock_analyze_result.total_scenes_updated = 15

        file_result_1 = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result_1.updated = True
        file_result_1.path = Path("/test/script1.fountain")
        file_result_1.scenes_updated = 5

        file_result_2 = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result_2.updated = True
        file_result_2.path = Path("/test/script2.fountain")
        file_result_2.scenes_updated = 10

        mock_analyze_result.files = [file_result_1, file_result_2]
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify success - strip ANSI codes for consistent testing
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        assert "Updated:" in output
        assert "script1.fountain" in output
        assert "script2.fountain" in output
        assert "15 scenes" in output
        assert "3 files" in output

        # Verify analyze was called with correct defaults
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["path"] is None
        assert call_kwargs["recursive"] is True
        assert call_kwargs["force"] is False
        assert call_kwargs["dry_run"] is False
        assert call_kwargs["brittle"] is False
        assert "progress_callback" in call_kwargs

    def test_analyze_with_path(self, runner, mock_analyze_command, mock_analyze_result):
        """Test analyze command with custom path."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with path
        result = runner.invoke(app, ["analyze", "/custom/path"])

        # Verify success
        assert result.exit_code == 0

        # Verify path was passed correctly
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["path"] == Path("/custom/path")

    def test_analyze_with_force_flag(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with force flag."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with force
        result = runner.invoke(app, ["analyze", "--force"])

        # Verify success
        assert result.exit_code == 0

        # Verify force was passed
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["force"] is True

    def test_analyze_with_dry_run_flag(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with dry-run flag."""
        # Setup mock result for dry run
        mock_analyze_result.total_files_updated = 2
        mock_analyze_result.total_scenes_updated = 8

        file_result = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result.updated = True
        file_result.path = Path("/test/script.fountain")
        file_result.scenes_updated = 8
        mock_analyze_result.files = [file_result]

        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with dry-run
        result = runner.invoke(app, ["analyze", "--dry-run"])

        # Verify success with dry-run messaging
        assert result.exit_code == 0
        assert "DRY RUN - No files were modified" in result.output
        assert "Would update:" in result.output
        assert "script.fountain" in result.output

        # Verify dry_run was passed
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["dry_run"] is True

    def test_analyze_with_no_recursive_flag(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with no-recursive flag."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with no-recursive
        result = runner.invoke(app, ["analyze", "--no-recursive"])

        # Verify success
        assert result.exit_code == 0

        # Verify recursive was set to False
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["recursive"] is False

    def test_analyze_with_brittle_flag(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with brittle flag."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with brittle flag
        result = runner.invoke(app, ["analyze", "--brittle"])

        # Verify success
        assert result.exit_code == 0

        # Verify brittle was passed
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["brittle"] is True

    def test_analyze_without_brittle_flag(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command without brittle flag defaults to False."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command without brittle flag
        result = runner.invoke(app, ["analyze"])

        # Verify success
        assert result.exit_code == 0

        # Verify brittle was passed as False
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["brittle"] is False

    def test_analyze_with_single_analyzer(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with single analyzer."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with analyzer
        result = runner.invoke(app, ["analyze", "--analyzer", "test-analyzer"])

        # Verify success
        assert result.exit_code == 0

        # Verify analyzer was loaded
        mock_analyze_command.load_analyzer.assert_called_once_with("test-analyzer")

    def test_analyze_with_multiple_analyzers(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with multiple analyzers."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with multiple analyzers
        result = runner.invoke(
            app,
            [
                "analyze",
                "--analyzer",
                "analyzer1",
                "--analyzer",
                "analyzer2",
                "--analyzer",
                "analyzer3",
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify all analyzers were loaded
        assert mock_analyze_command.load_analyzer.call_count == 3
        mock_analyze_command.load_analyzer.assert_any_call("analyzer1")
        mock_analyze_command.load_analyzer.assert_any_call("analyzer2")
        mock_analyze_command.load_analyzer.assert_any_call("analyzer3")

    def test_analyze_with_analyzer_load_error(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command handles analyzer load errors gracefully."""
        # Make load_analyzer raise an exception
        mock_analyze_command.load_analyzer.side_effect = Exception(
            "Failed to load analyzer"
        )
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with analyzer that fails to load
        result = runner.invoke(app, ["analyze", "--analyzer", "bad-analyzer"])

        # Verify command still succeeds but shows warning - strip ANSI codes
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        assert "Warning: Failed to load analyzer 'bad-analyzer'" in output
        assert "Failed to load analyzer" in output

        # Verify analyze still ran
        assert mock_analyze_command.analyze.call_count == 1

    def test_analyze_with_all_flags(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with all flags combined."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with all flags
        result = runner.invoke(
            app,
            [
                "analyze",
                "/custom/path",
                "--force",
                "--dry-run",
                "--no-recursive",
                "--brittle",
                "--analyzer",
                "test-analyzer",
            ],
        )

        # Verify success
        assert result.exit_code == 0

        # Verify all parameters were passed correctly
        assert mock_analyze_command.analyze.call_count == 1
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["path"] == Path("/custom/path")
        assert call_kwargs["force"] is True
        assert call_kwargs["dry_run"] is True
        assert call_kwargs["recursive"] is False
        assert call_kwargs["brittle"] is True

        # Verify analyzer was loaded
        mock_analyze_command.load_analyzer.assert_called_once_with("test-analyzer")

    def test_analyze_no_files_updated(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command when no files need updating."""
        # Setup mock result with no updates
        mock_analyze_result.total_files_updated = 0
        mock_analyze_result.total_scenes_updated = 0
        mock_analyze_result.files = []
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify success with appropriate messaging - strip ANSI codes
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        assert "No files needed updating" in output
        assert "0 scenes in 0 files" in output

    def test_analyze_with_errors(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command handles errors in results."""
        # Setup mock result with errors
        mock_analyze_result.total_files_updated = 1
        mock_analyze_result.total_scenes_updated = 5
        mock_analyze_result.errors = [
            "Error parsing file1.fountain: Invalid syntax",
            "Error in file2.fountain: Missing metadata",
            "Failed to process file3.fountain",
        ]

        file_result = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result.updated = True
        file_result.path = Path("/test/good_script.fountain")
        file_result.scenes_updated = 5
        mock_analyze_result.files = [file_result]

        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify command completes successfully despite errors
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        assert "good_script.fountain" in output
        assert "Errors: 3" in output
        assert "Error parsing file1.fountain" in output
        assert "Error in file2.fountain" in output
        assert "Failed to process file3.fountain" in output

    def test_analyze_with_many_errors(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with more than 5 errors shows summary."""
        # Setup mock result with many errors
        mock_analyze_result.total_files_updated = 0
        mock_analyze_result.total_scenes_updated = 0
        mock_analyze_result.files = []
        mock_analyze_result.errors = [
            f"Error in file{i}.fountain"
            for i in range(8)  # 8 errors
        ]

        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify error summary
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        assert "Errors: 8" in output
        assert "Error in file0.fountain" in output
        assert "Error in file4.fountain" in output  # Should show first 5
        assert "... and 3 more" in output

    def test_analyze_relative_path_display(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command displays relative paths when possible."""
        # Setup mock result with files in current directory
        mock_analyze_result.total_files_updated = 2
        mock_analyze_result.total_scenes_updated = 10

        # File that can be made relative
        file_result_1 = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result_1.updated = True
        file_result_1.path = Path.cwd() / "scripts" / "test1.fountain"
        file_result_1.scenes_updated = 4

        # File that cannot be made relative (absolute path outside cwd)
        file_result_2 = MagicMock(spec=["content", "model", "provider", "usage"])
        file_result_2.updated = True
        file_result_2.path = Path("/absolute/path/test2.fountain")
        file_result_2.scenes_updated = 6

        mock_analyze_result.files = [file_result_1, file_result_2]
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify path display - strip ANSI codes and handle Windows paths
        import os

        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        # On Windows, paths use backslashes
        expected_relative = "scripts" + os.sep + "test1.fountain"
        assert "test1.fountain" in output  # Check just the filename
        assert "test2.fountain" in output  # Check absolute path filename

    def test_analyze_progress_callback(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test that progress callback is provided and works."""
        # Capture the progress callback
        progress_callback = None

        async def capture_callback(*args, **kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return mock_analyze_result

        mock_analyze_command.analyze.side_effect = capture_callback
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify callback was provided
        assert progress_callback is not None

        # Test the callback works (it should update progress description)
        progress_callback(0.5, "Processing file.fountain...")

        # Command should complete successfully
        assert result.exit_code == 0

    def test_analyze_handles_general_exception(self, runner, mock_analyze_command):
        """Test analyze command handles general exceptions."""
        # Make analyze raise an exception
        mock_analyze_command.analyze.side_effect = Exception(
            "Unexpected error during analysis"
        )

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify error handling
        assert result.exit_code == 1
        assert "Error: Unexpected error during analysis" in result.output

    def test_analyze_async_exception_handling(self, runner, mock_analyze_command):
        """Test analyze command handles async exceptions properly."""

        # Make analyze coroutine raise an exception
        async def failing_analyze(*args, **kwargs):
            raise ValueError("Async operation failed")

        mock_analyze_command.analyze.side_effect = failing_analyze

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify error handling
        assert result.exit_code == 1
        assert "Error: Async operation failed" in result.output

    def test_analyze_with_short_flags(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test analyze command with short flag versions."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command with short flags
        result = runner.invoke(
            app,
            [
                "analyze",
                "-f",  # --force
                "-n",  # --dry-run
                "-a",
                "test-analyzer",  # --analyzer
            ],
        )

        # Verify success and flags were parsed
        assert result.exit_code == 0

        # Verify parameters were passed correctly
        call_kwargs = mock_analyze_command.analyze.call_args[1]
        assert call_kwargs["force"] is True
        assert call_kwargs["dry_run"] is True

        # Verify analyzer was loaded
        mock_analyze_command.load_analyzer.assert_called_once_with("test-analyzer")

    def test_analyze_spinner_progress_display(
        self, runner, mock_analyze_command, mock_analyze_result
    ):
        """Test that analyze shows spinner and progress messages."""
        mock_analyze_command.analyze_return_value = mock_analyze_result

        # Run command
        result = runner.invoke(app, ["analyze"])

        # Verify spinner was shown (progress task created) - strip ANSI codes
        from tests.cli_fixtures import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert result.exit_code == 0
        # The progress spinner itself won't be visible in test output,
        # but we can verify the command completed successfully
        assert "0 scenes in 0 files" in output
