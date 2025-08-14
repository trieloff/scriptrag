"""Unit tests for scriptrag search CLI command."""

from unittest.mock import Mock, patch

import pytest
import typer

from scriptrag.cli.commands.search import search_command
from scriptrag.exceptions import DatabaseError
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class TestSearchCommand:
    """Test the search command function."""

    @pytest.fixture
    def mock_console(self):
        """Mock the console to capture output."""
        with patch("scriptrag.cli.commands.search.console") as mock:
            yield mock

    @pytest.fixture
    def mock_search_api(self):
        """Mock the SearchAPI class."""
        with patch("scriptrag.cli.commands.search.SearchAPI") as mock:
            yield mock

    @pytest.fixture
    def mock_formatter(self):
        """Mock the ResultFormatter class."""
        with patch("scriptrag.cli.commands.search.ResultFormatter") as mock:
            yield mock

    @pytest.fixture
    def mock_logger(self):
        """Mock the logger."""
        with patch("scriptrag.cli.commands.search.logger") as mock:
            yield mock

    @pytest.fixture
    def sample_search_response(self):
        """Create a sample search response."""
        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )
        results = [
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Test Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. TEST SCENE - DAY",
                scene_location="Test Location",
                scene_time="DAY",
                scene_content="This is test scene content.",
                match_type="text",
                relevance_score=0.95,
            )
        ]
        return SearchResponse(
            query=query,
            results=results,
            total_count=1,
            has_more=False,
            execution_time_ms=42.5,
            search_methods=["sql"],
        )

    def test_basic_search_success(
        self, mock_console, mock_search_api, mock_formatter, sample_search_response
    ):
        """Test basic search command with successful results."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command
        search_command("test query")

        # Verify API was called correctly
        mock_search_api.from_config.assert_called_once()
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

        # Verify formatter was called
        mock_formatter.assert_called_once_with(mock_console)
        mock_formatter_instance.format_results.assert_called_once_with(
            sample_search_response, verbose=False
        )

    def test_search_with_all_options(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search command with all possible options."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command with all options
        search_command(
            query="test query",
            character="JOHN",
            dialogue="hello world",
            parenthetical="whisper",
            project="My Script",
            range_filter="s1e2-s1e5",
            fuzzy=True,
            strict=False,
            limit=10,
            offset=5,
            verbose=True,
            brief=False,
        )

        # Verify API was called with all parameters
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character="JOHN",
            dialogue="hello world",
            parenthetical="whisper",
            project="My Script",
            range_str="s1e2-s1e5",
            fuzzy=True,
            strict=False,
            limit=10,
            offset=5,
            include_bible=True,
            only_bible=False,
        )

        # Verify verbose formatting
        mock_formatter_instance.format_results.assert_called_once_with(
            sample_search_response, verbose=True
        )

    def test_search_brief_format(
        self, mock_console, mock_search_api, mock_formatter, sample_search_response
    ):
        """Test search command with brief output format."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_brief.return_value = "Brief result text"
        mock_formatter.return_value = mock_formatter_instance

        # Execute command with brief flag
        search_command("test query", brief=True)

        # Verify brief formatting was used
        mock_formatter_instance.format_brief.assert_called_once_with(
            sample_search_response
        )
        mock_console.print.assert_called_once_with("Brief result text")
        mock_formatter_instance.format_results.assert_not_called()

    def test_fuzzy_and_strict_conflict(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        mock_logger,
    ):
        """Test that fuzzy and strict flags cannot be used together."""
        # Execute command with conflicting flags
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query", fuzzy=True, strict=True)

        # Verify error handling
        assert exc_info.value.exit_code == 1

        # Only one print should happen - the specific conflict error
        assert mock_console.print.call_count == 1
        mock_console.print.assert_called_once_with(
            "[red]Error:[/red] Cannot use both --fuzzy and --strict options",
            style="bold",
        )

        # Logger should not be called for simple validation errors
        mock_logger.error.assert_not_called()

        # Verify SearchAPI.from_config WAS called (happens before validation)
        mock_search_api.from_config.assert_called_once()

        # But search() method should NOT be called
        mock_api_instance = mock_search_api.from_config.return_value
        mock_api_instance.search.assert_not_called()

    @pytest.mark.parametrize(
        "character,dialogue,parenthetical,project,range_filter",
        [
            ("SARAH", None, None, None, None),
            (None, "hello world", None, None, None),
            (None, None, "whisper", None, None),
            (None, None, None, "My Project", None),
            (None, None, None, None, "s1e1-s1e3"),
            ("JOHN", "goodbye", "loudly", "Test Script", "s2e1-s2e10"),
        ],
    )
    def test_search_option_combinations(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
        character,
        dialogue,
        parenthetical,
        project,
        range_filter,
    ):
        """Test various combinations of search options."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command
        search_command(
            query="test query",
            character=character,
            dialogue=dialogue,
            parenthetical=parenthetical,
            project=project,
            range_filter=range_filter,
        )

        # Verify API was called with correct parameters
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=character,
            dialogue=dialogue,
            parenthetical=parenthetical,
            project=project,
            range_str=range_filter,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @pytest.mark.parametrize(
        "limit,offset",
        [
            (1, 0),
            (10, 5),
            (25, 50),
            (100, 0),
        ],
    )
    def test_pagination_options(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
        limit,
        offset,
    ):
        """Test different pagination combinations."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command
        search_command("test query", limit=limit, offset=offset)

        # Verify pagination parameters
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=limit,
            offset=offset,
            include_bible=True,
            only_bible=False,
        )

    @pytest.mark.parametrize(
        "fuzzy,strict",
        [
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_search_mode_options(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
        fuzzy,
        strict,
    ):
        """Test different search mode combinations."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command
        search_command("test query", fuzzy=fuzzy, strict=strict)

        # Verify search mode parameters
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=fuzzy,
            strict=strict,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @pytest.mark.parametrize(
        "verbose,brief",
        [
            (True, False),
            (False, False),
            (False, True),
        ],
    )
    def test_output_format_options(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
        verbose,
        brief,
    ):
        """Test different output format options."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_brief.return_value = "Brief output"
        mock_formatter.return_value = mock_formatter_instance

        # Execute command
        search_command("test query", verbose=verbose, brief=brief)

        # Verify output format handling
        if brief:
            mock_formatter_instance.format_brief.assert_called_once_with(
                sample_search_response
            )
            mock_console.print.assert_called_once_with("Brief output")
            mock_formatter_instance.format_results.assert_not_called()
        else:
            mock_formatter_instance.format_results.assert_called_once_with(
                sample_search_response, verbose=verbose
            )
            mock_formatter_instance.format_brief.assert_not_called()

    @patch("scriptrag.cli.commands.search.handle_cli_error")
    def test_file_not_found_error(
        self, mock_handle_error, mock_console, mock_search_api, mock_formatter
    ):
        """Test handling of DatabaseError (was FileNotFoundError)."""
        # Setup mock to raise DatabaseError
        error = DatabaseError("Database not found")
        mock_search_api.from_config.side_effect = error

        # Setup handle_cli_error to raise Exit
        mock_handle_error.side_effect = typer.Exit(1)

        # Execute command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query")

        # Verify error handling
        assert exc_info.value.exit_code == 1
        # Verify that handle_cli_error was called with the error
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        assert isinstance(args[0], DatabaseError)
        assert str(args[0]) == "Error: Database not found"

    @patch("scriptrag.cli.commands.search.handle_cli_error")
    def test_search_api_initialization_error(
        self,
        mock_handle_error,
        mock_console,
        mock_search_api,
        mock_formatter,
    ):
        """Test handling of SearchAPI initialization error."""
        # Setup mock to raise generic error during initialization
        error = RuntimeError("Config error")
        mock_search_api.from_config.side_effect = error

        # Setup handle_cli_error to raise Exit
        mock_handle_error.side_effect = typer.Exit(1)

        # Execute command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query")

        # Verify error handling
        assert exc_info.value.exit_code == 1
        # Verify that handle_cli_error was called with the error
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        assert isinstance(args[0], RuntimeError)
        assert str(args[0]) == "Config error"

    @patch("scriptrag.cli.commands.search.handle_cli_error")
    def test_search_execution_error(
        self,
        mock_handle_error,
        mock_console,
        mock_search_api,
        mock_formatter,
        mock_logger,
    ):
        """Test handling of search execution error."""
        # Setup mocks
        mock_api_instance = Mock()
        error = RuntimeError("Search failed")
        mock_api_instance.search.side_effect = error
        mock_search_api.from_config.return_value = mock_api_instance

        # Setup handle_cli_error to raise Exit
        mock_handle_error.side_effect = typer.Exit(1)

        # Execute command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query")

        # Verify error handling
        assert exc_info.value.exit_code == 1
        # Verify that handle_cli_error was called with the error
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        assert isinstance(args[0], RuntimeError)
        assert str(args[0]) == "Search failed"

    @patch("scriptrag.cli.commands.search.handle_cli_error")
    def test_formatter_error(
        self,
        mock_handle_error,
        mock_console,
        mock_search_api,
        mock_formatter,
        mock_logger,
        sample_search_response,
    ):
        """Test handling of formatter error."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        error = RuntimeError("Format error")
        mock_formatter_instance.format_results.side_effect = error
        mock_formatter.return_value = mock_formatter_instance

        # Setup handle_cli_error to raise Exit
        mock_handle_error.side_effect = typer.Exit(1)

        # Execute command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query")

        # Verify error handling
        assert exc_info.value.exit_code == 1
        # Verify that handle_cli_error was called with the error
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        assert isinstance(args[0], RuntimeError)
        assert str(args[0]) == "Format error"

    @patch("scriptrag.cli.commands.search.handle_cli_error")
    def test_brief_formatter_error(
        self,
        mock_handle_error,
        mock_console,
        mock_search_api,
        mock_formatter,
        mock_logger,
        sample_search_response,
    ):
        """Test handling of brief formatter error."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        error = RuntimeError("Brief format error")
        mock_formatter_instance.format_brief.side_effect = error
        mock_formatter.return_value = mock_formatter_instance

        # Setup handle_cli_error to raise Exit
        mock_handle_error.side_effect = typer.Exit(1)

        # Execute command and expect Exit
        with pytest.raises(typer.Exit) as exc_info:
            search_command("test query", brief=True)

        # Verify error handling
        assert exc_info.value.exit_code == 1
        # Verify that handle_cli_error was called with the error
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        assert isinstance(args[0], RuntimeError)
        assert str(args[0]) == "Brief format error"

    def test_default_parameters(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test that default parameters are correctly applied."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command with minimal parameters
        search_command("test query")

        # Verify default values were used
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

        # Verify default output format
        mock_formatter_instance.format_results.assert_called_once_with(
            sample_search_response, verbose=False
        )

    def test_empty_query_string(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search with empty query string."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command with empty query
        search_command("")

        # Verify empty query was passed through
        mock_api_instance.search.assert_called_once_with(
            query="",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    def test_special_characters_in_query(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search with special characters in query."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        special_query = 'SARAH "Hello, world!" (whisper) @#$%^&*()'

        # Execute command with special characters
        search_command(special_query)

        # Verify special characters were preserved
        mock_api_instance.search.assert_called_once_with(
            query=special_query,
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    def test_unicode_query(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search with unicode characters."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        unicode_query = "café résumé naïve 中文 русский"

        # Execute command with unicode
        search_command(unicode_query)

        # Verify unicode was preserved
        mock_api_instance.search.assert_called_once_with(
            query=unicode_query,
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    def test_extreme_pagination_values(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search with extreme pagination values."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Execute command with extreme values
        search_command("test query", limit=99999, offset=99999)

        # Verify extreme values were passed through
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            fuzzy=False,
            strict=False,
            limit=99999,
            offset=99999,
            include_bible=True,
            only_bible=False,
        )

    def test_complex_range_filter(
        self,
        mock_console,
        mock_search_api,
        mock_formatter,
        sample_search_response,
    ):
        """Test search with complex range filter."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.search.return_value = sample_search_response
        mock_search_api.from_config.return_value = mock_api_instance

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        complex_range = "s10e15-s12e25"

        # Execute command with complex range
        search_command("test query", range_filter=complex_range)

        # Verify complex range was passed through
        mock_api_instance.search.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=complex_range,
            fuzzy=False,
            strict=False,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )
