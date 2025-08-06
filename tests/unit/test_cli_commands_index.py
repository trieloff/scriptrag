"""Unit tests for CLI index command."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.api.index import IndexOperationResult, IndexResult
from scriptrag.cli.commands.index import _display_results, app

runner = CliRunner()


@pytest.fixture
def mock_index_result():
    """Create a mock index operation result."""
    return IndexOperationResult(
        scripts=[
            IndexResult(
                path=Path("/test/script1.fountain"),
                script_id=1,
                indexed=True,
                updated=False,
                scenes_indexed=5,
                characters_indexed=10,
                dialogues_indexed=50,
                actions_indexed=30,
            ),
            IndexResult(
                path=Path("/test/script2.fountain"),
                script_id=2,
                indexed=True,
                updated=True,
                scenes_indexed=3,
                characters_indexed=5,
                dialogues_indexed=20,
                actions_indexed=15,
            ),
            IndexResult(
                path=Path("/test/script3.fountain"),
                indexed=False,
                error="Failed to parse",
            ),
        ],
        errors=["Error 1: Something went wrong", "Error 2: Another error"],
    )


@pytest.fixture
def mock_index_command():
    """Create a mock IndexCommand."""
    mock = MagicMock()
    mock.from_config.return_value = mock

    async def mock_index(*_args, **kwargs):
        # Call progress callback if provided
        if kwargs.get("progress_callback"):
            callback = kwargs["progress_callback"]
            callback(0.1, "Discovering Fountain files...")
            callback(0.5, "Processing batch 1/1...")
            callback(1.0, "Indexing complete")
        return IndexOperationResult()

    mock.index = Mock(side_effect=mock_index)
    return mock


class TestIndexCommand:
    """Test index command."""

    def test_index_command_success(self, mock_index_command, mock_index_result):
        """Test successful index command execution."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            mock_index_command.index.side_effect = (
                lambda *_args, **_kwargs: mock_index_result
            )

            result = runner.invoke(app, ["--verbose"])

            assert result.exit_code == 0
            assert "Indexing complete!" in result.stdout
            assert "Index Summary" in result.stdout
            assert "Scripts Indexed" in result.stdout
            mock_index_command.from_config.assert_called_once()

    def test_index_command_with_options(self, mock_index_command):
        """Test index command with various options."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            result = runner.invoke(
                app,
                [
                    "path/to/scripts",
                    "--force",
                    "--dry-run",
                    "--no-recursive",
                    "--batch-size",
                    "20",
                    "--verbose",
                ],
            )

            assert result.exit_code == 0

            # Verify the index method was called with correct parameters
            call_args = mock_index_command.index.call_args
            assert call_args is not None
            kwargs = call_args.kwargs
            assert kwargs["path"] == Path("path/to/scripts")
            assert kwargs["force"] is True
            assert kwargs["dry_run"] is True
            assert kwargs["recursive"] is False
            assert kwargs["batch_size"] == 20

    def test_index_command_dry_run(self, mock_index_command, mock_index_result):
        """Test index command in dry run mode."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            mock_index_command.index.side_effect = (
                lambda *_args, **_kwargs: mock_index_result
            )

            result = runner.invoke(app, ["--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN - No changes were made" in result.stdout
            assert "Would index:" in result.stdout

    def test_index_command_verbose_output(self, mock_index_command, mock_index_result):
        """Test verbose output shows script details."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            mock_index_command.index.side_effect = (
                lambda *_args, **_kwargs: mock_index_result
            )

            result = runner.invoke(app, ["--verbose"])

            assert result.exit_code == 0
            assert "Script Details:" in result.stdout
            # Should show details for indexed scripts
            assert "5 scenes" in result.stdout
            assert "10 characters" in result.stdout
            assert "(updated)" in result.stdout

    def test_index_command_with_errors(self, mock_index_command):
        """Test index command with errors in result."""
        error_result = IndexOperationResult(
            scripts=[],
            errors=[f"Error {i}" for i in range(15)],  # More than 10 errors
        )

        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            mock_index_command.index.side_effect = (
                lambda *_args, **_kwargs: error_result
            )

            result = runner.invoke(app, [])

            assert result.exit_code == 0
            assert "Errors encountered: 15" in result.stdout
            assert "and 5 more errors" in result.stdout

    def test_index_command_exception(self, mock_index_command):
        """Test index command handles exceptions."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            mock_index_command.index.side_effect = Exception(
                "Database connection failed"
            )

            result = runner.invoke(app, [])

            assert result.exit_code == 1
            assert "Error: Database connection failed" in result.stdout

    def test_index_command_import_error(self):
        """Test index command handles import errors."""
        with patch(
            "scriptrag.api.index.IndexCommand",
            side_effect=ImportError("Module not found"),
        ):
            result = runner.invoke(app, [])

            assert result.exit_code == 1
            assert "Required components not available" in result.stdout

    def test_display_results_with_next_steps(self, mock_index_result):
        """Test display results shows next steps for successful indexing."""
        from io import StringIO

        from rich.console import Console

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        with patch("scriptrag.cli.commands.index.console", console):
            _display_results(mock_index_result, dry_run=False, verbose=False)

        output_text = output.getvalue()
        assert "Indexing complete!" in output_text
        assert "Next steps:" in output_text
        assert "scriptrag query" in output_text
        assert "scriptrag stats" in output_text
        assert "scriptrag graph" in output_text

    def test_display_results_verbose_with_errors(self):
        """Test verbose display with script errors."""
        from io import StringIO

        from rich.console import Console

        result = IndexOperationResult(
            scripts=[
                IndexResult(
                    path=Path.cwd() / "script1.fountain",  # Use relative path
                    indexed=True,
                    error="Parse error occurred",
                    scenes_indexed=0,
                    characters_indexed=0,
                    dialogues_indexed=0,
                    actions_indexed=0,
                ),
            ],
            errors=[],
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        with patch("scriptrag.cli.commands.index.console", console):
            _display_results(result, dry_run=False, verbose=True)

        output_text = output.getvalue()
        assert "Script Details:" in output_text
        assert "script1.fountain" in output_text
        assert "Parse error occurred" in output_text

    def test_display_results_no_scripts_indexed(self):
        """Test display when no scripts were indexed."""
        from io import StringIO

        from rich.console import Console

        result = IndexOperationResult(scripts=[], errors=[])

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        with patch("scriptrag.cli.commands.index.console", console):
            _display_results(result, dry_run=False, verbose=False)

        output_text = output.getvalue()
        assert "Scripts Indexed" in output_text
        assert "0" in output_text
        # Should not show next steps when nothing indexed
        assert "Next steps:" not in output_text

    def test_progress_callback_integration(self, mock_index_command):
        """Test that progress callback is properly integrated."""
        with patch("scriptrag.api.index.IndexCommand", mock_index_command):
            result = runner.invoke(app, [])

            assert result.exit_code == 0
            # Progress messages should appear in output
            assert "Indexing screenplay files..." in result.stdout

            # Verify progress_callback was passed to index method
            call_args = mock_index_command.index.call_args
            assert "progress_callback" in call_args.kwargs
            assert call_args.kwargs["progress_callback"] is not None
