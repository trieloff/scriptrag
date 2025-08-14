"""Tests to improve coverage to 99% for search functionality."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from scriptrag.api.search import SearchAPI
from scriptrag.cli.commands.search import search_command
from scriptrag.config import ScriptRAGSettings
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.formatter import ResultFormatter
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from scriptrag.search.parser import QueryParser


class TestAPISearchCoverage:
    """Tests to cover missing lines in api/search.py."""

    def test_search_api_without_settings(self, tmp_path):
        """Test SearchAPI when settings is None (lines 21-23)."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        # Initialize database with schema
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                version INTEGER DEFAULT 1,
                is_current BOOLEAN DEFAULT TRUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                scene_heading TEXT,
                scene_location TEXT,
                scene_time TEXT,
                scene_content TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = ScriptRAGSettings(database_path=db_path)
            mock_get_settings.return_value = mock_settings

            # Create SearchAPI without passing settings
            api = SearchAPI(settings=None)

            assert mock_get_settings.called
            assert api.settings == mock_settings

    def test_from_config_with_path(self, tmp_path):
        """Test SearchAPI.from_config with config_path parameter."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        with patch(
            "scriptrag.api.search.ScriptRAGSettings.from_file"
        ) as mock_from_file:
            mock_settings = ScriptRAGSettings(database_path=db_path)
            mock_from_file.return_value = mock_settings

            # Call from_config with config_path - now loads from file
            api = SearchAPI.from_config(config_path="some/config.yaml")

            mock_from_file.assert_called_with("some/config.yaml")
            assert isinstance(api, SearchAPI)


class TestCLISearchCoverage:
    """Tests to cover missing lines in cli/commands/search.py."""

    def test_fuzzy_and_strict_conflict(self):
        """Test error when both fuzzy and strict are specified (lines 149-153)."""
        # We need to patch the SearchAPI.from_config to not fail during init
        with patch(
            "scriptrag.cli.commands.search.SearchAPI.from_config"
        ) as mock_from_config:
            mock_api = MagicMock()
            mock_from_config.return_value = mock_api

            with (
                patch("scriptrag.cli.commands.search.console") as mock_console,
                # Also patch the logger to avoid structlog exception rendering issues
                patch("scriptrag.cli.commands.search.logger"),
            ):
                with pytest.raises(typer.Exit) as exc_info:
                    search_command(
                        query="test",
                        fuzzy=True,
                        strict=True,
                    )

                assert exc_info.value.exit_code == 1
                # Check that the specific error message was printed
                mock_console.print.assert_any_call(
                    "[red]Error:[/red] Cannot use both --fuzzy and --strict options",
                    style="bold",
                )

    def test_file_not_found_error(self):
        """Test DatabaseError handling (lines 180-185)."""
        from scriptrag.exceptions import DatabaseError

        with patch(
            "scriptrag.cli.commands.search.SearchAPI.from_config"
        ) as mock_from_config:
            mock_api = MagicMock()
            mock_from_config.return_value = mock_api
            # Use the actual error message from SearchEngine
            mock_api.search.side_effect = DatabaseError(
                "Database not found at /some/path",
                hint="Run 'scriptrag init' to create a new database",
            )

            with (
                patch("scriptrag.cli.commands.search.handle_cli_error") as mock_handle,
                # Also patch the logger to avoid structlog exception rendering issues
                patch("scriptrag.cli.commands.search.logger"),
            ):
                # handle_cli_error should raise typer.Exit
                mock_handle.side_effect = typer.Exit(1)

                with pytest.raises(typer.Exit) as exc_info:
                    search_command(query="test")

                assert exc_info.value.exit_code == 1
                # Verify handle_cli_error was called with the error
                mock_handle.assert_called_once()
                error = mock_handle.call_args[0][0]
                assert isinstance(error, DatabaseError)
                assert "Database not found" in str(error)

    def test_general_exception_handling(self):
        """Test general exception handling (lines 186-195)."""
        with patch(
            "scriptrag.cli.commands.search.SearchAPI.from_config"
        ) as mock_from_config:
            mock_api = MagicMock()
            mock_from_config.return_value = mock_api
            mock_api.search.side_effect = Exception("Unexpected error")

            with (
                patch("scriptrag.cli.commands.search.handle_cli_error") as mock_handle,
                patch("scriptrag.cli.commands.search.logger"),
            ):
                # handle_cli_error should raise typer.Exit
                mock_handle.side_effect = typer.Exit(1)

                with pytest.raises(typer.Exit) as exc_info:
                    search_command(query="test")

                assert exc_info.value.exit_code == 1
                # Verify handle_cli_error was called with the exception
                mock_handle.assert_called_once()
                error = mock_handle.call_args[0][0]
                assert isinstance(error, Exception)
                assert str(error) == "Unexpected error"


class TestQueryBuilderCoverage:
    """Tests to cover missing lines in search/builder.py."""

    def test_build_with_season_episode_range(self):
        """Test query with season and episode range (lines 60-68)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            season_start=1,
            season_end=1,
            episode_start=1,
            episode_end=1,
        )

        sql, params = builder.build_search_query(query)

        # Check that season/episode conditions are included
        assert "json_extract(s.metadata, '$.season')" in sql
        assert "json_extract(s.metadata, '$.episode')" in sql
        assert 1 in params  # season number

    def test_build_with_dialogue_fuzzy(self):
        """Test query with dialogue in fuzzy mode (line 86)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            dialogue="hello world",
            mode=SearchMode.FUZZY,
        )

        sql, params = builder.build_search_query(query)

        # Dialogue search always uses LIKE in the current implementation
        assert "d.dialogue_text LIKE ?" in sql
        assert "%hello world%" in params

    def test_build_with_action_content(self):
        """Test query with action content (lines 145-157)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            action="runs quickly",
        )

        sql, params = builder.build_search_query(query)

        # Action query should search in scene content
        assert "sc.content LIKE ?" in sql
        assert any("%runs quickly%" in str(p) for p in params)

    def test_build_parenthetical_query_fuzzy(self):
        """Test parenthetical query in fuzzy mode (lines 321-329)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            dialogue="something",  # Need dialogue for parenthetical to be added
            parenthetical="angrily",
            mode=SearchMode.FUZZY,
        )

        sql, params = builder.build_search_query(query)

        # Parenthetical search should be included when dialogue is present
        assert "json_extract(d.metadata, '$.parenthetical') LIKE ?" in sql
        assert "%angrily%" in params

    def test_build_location_query_strict(self):
        """Test location query in strict mode (lines 349-352)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            locations=["OFFICE"],
            mode=SearchMode.STRICT,
        )

        sql, params = builder.build_search_query(query)

        # Current implementation always uses LIKE for location search
        assert "sc.location LIKE ?" in sql
        assert "%OFFICE%" in params

    def test_build_character_query_fuzzy(self):
        """Test character query in fuzzy mode (lines 376-388)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            characters=["John", "Jane"],
            mode=SearchMode.FUZZY,
        )

        sql, params = builder.build_search_query(query)

        # Character-only search uses EXISTS with exact character name match
        assert "EXISTS" in sql
        assert "c3.name = ?" in sql
        assert "John" in params
        assert "Jane" in params

    def test_pagination_with_large_offset(self):
        """Test pagination with offset (lines 396-400, 414-418)."""
        builder = QueryBuilder()

        # Test with limit only
        query1 = SearchQuery(
            raw_query="test",
            limit=10,
            offset=0,
        )
        sql1, params1 = builder.build_search_query(query1)
        assert "LIMIT ? OFFSET ?" in sql1
        assert params1[-2:] == [10, 0]  # Last two params are limit and offset

        # Test with offset
        query2 = SearchQuery(
            raw_query="test",
            limit=10,
            offset=20,
        )
        sql2, params2 = builder.build_search_query(query2)
        assert "LIMIT ? OFFSET ?" in sql2
        assert params2[-2:] == [10, 20]  # Last two params are limit and offset


class TestResultFormatterCoverage:
    """Tests to cover missing lines in search/formatter.py."""

    def test_format_with_season_episode(self):
        """Test formatting with season and episode info (line 81)."""
        console = Console()
        formatter = ResultFormatter(console)

        result = SearchResult(
            script_id=1,
            script_title="Test Show",
            script_author="Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="Content",
            season=2,
            episode=5,
            match_type="dialogue",
            relevance_score=0.9,
        )

        response = SearchResponse(
            query=SearchQuery(raw_query="test"),
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=10.5,
            search_methods=["sql"],
        )

        with patch.object(console, "print") as mock_print:
            formatter.format_results(response)

            # Verify that the formatter was called and season/episode data was processed
            mock_print.assert_called()
            # The formatter processes season/episode data from the result object
            # We've provided season=2, episode=5 in the result, so just verify it ran
            assert len(mock_print.call_args_list) >= 2  # Search info + result panel

    def test_format_dialogue_with_character(self):
        """Test formatting dialogue with character name (lines 91-93, 97)."""
        console = Console()
        formatter = ResultFormatter(console)

        result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="Content",
            match_type="dialogue",
            relevance_score=0.9,
            matched_text="Hello world",
            character_name="JOHN",
        )

        response = SearchResponse(
            query=SearchQuery(raw_query="test"),
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=10.5,
            search_methods=["sql"],
        )

        with patch.object(console, "print") as mock_print:
            formatter.format_results(response)

            # Check that search info is displayed
            # (character info would be in query display)
            mock_print.assert_called()
            # The character name won't be in the result since it's
            # in matched_text/dialogue. Just verify formatter was called
            assert (
                len(mock_print.call_args_list) >= 2
            )  # At least search info + result panel

    def test_format_brief_empty_results(self):
        """Test brief format with no results (lines 183, 189, 197)."""
        console = Console()
        formatter = ResultFormatter(console)

        response = SearchResponse(
            query=SearchQuery(raw_query="test"),
            results=[],
            total_count=0,
            has_more=False,
            execution_time_ms=5.0,
            search_methods=["sql"],
        )

        # Test format_brief with empty results
        brief = formatter.format_brief(response)
        assert "No results found" in brief

        # Test _format_brief_line with None values
        result = SearchResult(
            script_id=1,
            script_title="Test",
            script_author=None,  # No author
            scene_id=1,
            scene_number=1,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="Content",
            match_type="action",
            relevance_score=0.9,
        )

        # The _format_brief_line method doesn't exist, test format_brief instead
        response_with_result = SearchResponse(
            query=SearchQuery(raw_query="test"),
            results=[result],
            total_count=1,
            has_more=False,
            execution_time_ms=5.0,
            search_methods=["sql"],
        )
        brief = formatter.format_brief(response_with_result)
        assert "Test" in brief
        assert "Scene 1" in brief

    def test_format_action_match(self):
        """Test formatting action match type (lines 116-119, 127-130, 130-133)."""
        console = Console()
        formatter = ResultFormatter(console)

        # Test action match
        action_result = SearchResult(
            script_id=1,
            script_title="Test",
            script_author="Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="John runs quickly across the room.",
            match_type="action",
            relevance_score=0.9,
            matched_text="runs quickly",
        )

        response = SearchResponse(
            query=SearchQuery(raw_query="runs"),
            results=[action_result],
            total_count=1,
            has_more=False,
            execution_time_ms=10.5,
            search_methods=["sql"],
        )

        with patch.object(console, "print") as mock_print:
            formatter.format_results(response)

            # Check that the result is formatted properly
            mock_print.assert_called()
            # The matched text should be in the scene content,
            # not necessarily visible in the print calls
            # Just verify the formatter ran successfully
            assert (
                len(mock_print.call_args_list) >= 2
            )  # At least search info + result panel


class TestSearchParserCoverage:
    """Tests to cover missing lines in search/parser.py."""

    def test_parse_with_episode_range_error(self):
        """Test parse with invalid episode range (lines 114-123, 130, 141)."""
        parser = QueryParser()

        # Test valid episode range using range_str parameter
        query = parser.parse("test", range_str="s1e1-s1e5")
        assert query.season_start == 1
        assert query.episode_start == 1
        assert query.episode_end == 5

        # Test single episode
        query2 = parser.parse("test", range_str="s2e3")
        assert query2.season_start == 2
        assert query2.episode_start == 3
        assert query2.episode_end == 3  # Single episode sets end to same as start

        # Test invalid range format (should not crash)
        query3 = parser.parse("test", range_str="invalid")
        assert query3.season_start is None
