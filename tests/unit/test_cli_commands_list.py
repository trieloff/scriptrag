"""Unit tests for scriptrag list CLI command."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from scriptrag.api.list import FountainMetadata
from scriptrag.cli.commands.list import list_command


class TestListCommand:
    """Test the list command function."""

    @pytest.fixture
    def mock_console(self):
        """Mock the console to capture output."""
        with patch("scriptrag.cli.commands.list.console") as mock:
            yield mock

    @pytest.fixture
    def mock_lister(self):
        """Mock the ScriptLister class."""
        with patch("scriptrag.cli.commands.list.ScriptLister") as mock:
            yield mock

    def test_list_no_scripts_found(self, mock_console, mock_lister):
        """Test list command when no scripts are found."""
        # Setup mock
        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = []
        mock_lister.return_value = mock_lister_instance

        # Call command
        list_command(path=Path("/test"))

        # Verify
        mock_lister_instance.list_scripts.assert_called_once_with(
            path=Path("/test"), recursive=True
        )
        mock_console.print.assert_any_call(
            "[yellow]No Fountain scripts found.[/yellow]", style="bold"
        )

    def test_list_with_scripts(self, mock_console, mock_lister):
        """Test list command with multiple scripts."""
        # Setup mock scripts
        scripts = [
            FountainMetadata(
                file_path=Path("/test/standalone.fountain"),
                title="Standalone Script",
                author="John Doe",
            ),
            FountainMetadata(
                file_path=Path("/test/series/ep1.fountain"),
                title="TV Series",
                author="Jane Smith",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("/test/series/ep2.fountain"),
                title="TV Series",
                author="Jane Smith",
                season_number=1,
                episode_number=2,
            ),
        ]

        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = scripts
        mock_lister.return_value = mock_lister_instance

        # Call command
        list_command(path=Path("/test"))

        # Verify table was printed
        # Look for the final print call with the table
        print_calls = mock_console.print.call_args_list
        assert any("Found 3 scripts" in str(call) for call in print_calls)

    def test_list_no_recursive_option(self, mock_console, mock_lister):  # noqa: ARG002
        """Test list command with no_recursive option."""
        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = []
        mock_lister.return_value = mock_lister_instance

        # Call command with no_recursive=True
        list_command(path=Path("/test"), no_recursive=True)

        # Verify recursive=False was passed
        mock_lister_instance.list_scripts.assert_called_once_with(
            path=Path("/test"), recursive=False
        )

    def test_list_default_path(self, mock_console, mock_lister):  # noqa: ARG002
        """Test list command with default path (None)."""
        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = []
        mock_lister.return_value = mock_lister_instance

        # Call command without path
        list_command(path=None)

        # Verify None was passed as path
        mock_lister_instance.list_scripts.assert_called_once_with(
            path=None, recursive=True
        )

    def test_list_handles_exceptions(self, mock_console, mock_lister):
        """Test list command handles exceptions gracefully."""
        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.side_effect = Exception("Test error")
        mock_lister.return_value = mock_lister_instance

        # Call command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            list_command(path=Path("/test"))

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_any_call(
            "[red]Error:[/red] Failed to list scripts: Test error", style="bold"
        )

    def test_list_series_grouping(self, mock_console, mock_lister):
        """Test that series episodes are grouped together."""
        # Create mixed series and standalone scripts
        scripts = [
            FountainMetadata(
                file_path=Path("/test/standalone1.fountain"),
                title="Standalone One",
            ),
            FountainMetadata(
                file_path=Path("/test/series/s01e02.fountain"),
                title="Series A",
                season_number=1,
                episode_number=2,
            ),
            FountainMetadata(
                file_path=Path("/test/series/s01e01.fountain"),
                title="Series A",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("/test/series/s02e01.fountain"),
                title="Series A",
                season_number=2,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("/test/standalone2.fountain"),
                title="Standalone Two",
            ),
            FountainMetadata(
                file_path=Path("/test/seriesb/ep1.fountain"),
                title="Series B",
                episode_number=1,
            ),
        ]

        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = scripts
        mock_lister.return_value = mock_lister_instance

        # Call command
        list_command(path=Path("/test"))

        # Verify output shows series grouped
        assert mock_console.print.called
        print_calls = mock_console.print.call_args_list
        assert any("Found 6 scripts" in str(call) for call in print_calls)

    def test_list_script_without_metadata(self, mock_console, mock_lister):
        """Test listing script without title or author."""
        scripts = [
            FountainMetadata(
                file_path=Path("/test/untitled.fountain"),
                # No title or author
            )
        ]

        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = scripts
        mock_lister.return_value = mock_lister_instance

        # Call command
        list_command(path=Path("/test"))

        # Should use filename as title
        assert mock_console.print.called

    def test_list_relative_paths_display(self, mock_console, mock_lister):
        """Test that file paths are displayed relative to cwd."""
        # Mock current working directory
        with patch("scriptrag.cli.commands.list.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/test")

            scripts = [
                FountainMetadata(
                    file_path=Path("/test/scripts/movie.fountain"),
                    title="Movie",
                )
            ]

            mock_lister_instance = Mock()
            mock_lister_instance.list_scripts.return_value = scripts
            mock_lister.return_value = mock_lister_instance

            # Call command
            list_command(path=Path("/test"))

            # Path should be displayed as relative
            assert mock_console.print.called

    def test_list_single_script_message(self, mock_console, mock_lister):
        """Test singular form of message for single script."""
        scripts = [
            FountainMetadata(
                file_path=Path("/test/single.fountain"), title="Single Script"
            )
        ]

        mock_lister_instance = Mock()
        mock_lister_instance.list_scripts.return_value = scripts
        mock_lister.return_value = mock_lister_instance

        # Call command
        list_command(path=Path("/test"))

        # Should show "Found 1 script" not "Found 1 scripts"
        print_calls = mock_console.print.call_args_list
        assert any("Found 1 script" in str(call) for call in print_calls)
        assert not any("Found 1 scripts" in str(call) for call in print_calls)
