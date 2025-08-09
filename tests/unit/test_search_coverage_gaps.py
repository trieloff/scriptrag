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
                author TEXT
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
        """Test SearchAPI.from_config with config_path parameter (line 103)."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = ScriptRAGSettings(database_path=db_path)
            mock_get_settings.return_value = mock_settings

            # Call from_config with config_path (currently a no-op pass)
            api = SearchAPI.from_config(config_path="some/config.yaml")

            assert mock_get_settings.called
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

            with patch("scriptrag.cli.commands.search.console") as mock_console:
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
        """Test FileNotFoundError handling (lines 180-185)."""
        with patch("scriptrag.cli.commands.search.SearchAPI") as mock_search_api:
            mock_api = MagicMock()
            mock_search_api.return_value = mock_api
            mock_api.search.side_effect = FileNotFoundError("Database not found")

            with patch("scriptrag.cli.commands.search.console") as mock_console:
                with pytest.raises(typer.Exit) as exc_info:
                    search_command(query="test")

                assert exc_info.value.exit_code == 1
                mock_console.print.assert_called()
                call_args = str(mock_console.print.call_args)
                assert "Database not found" in call_args

    def test_general_exception_handling(self):
        """Test general exception handling (lines 186-195)."""
        with patch("scriptrag.cli.commands.search.SearchAPI") as mock_search_api:
            mock_api = MagicMock()
            mock_search_api.return_value = mock_api
            mock_api.search.side_effect = Exception("Unexpected error")

            with (
                patch("scriptrag.cli.commands.search.console") as mock_console,
                patch("scriptrag.cli.commands.search.logger") as mock_logger,
            ):
                with pytest.raises(typer.Exit) as exc_info:
                    search_command(query="test")

                assert exc_info.value.exit_code == 1
                mock_logger.error.assert_called()
                mock_console.print.assert_called()
                call_args = str(mock_console.print.call_args)
                assert "Search operation failed" in call_args


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

        sql, params = builder.build_sql_query(query)

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

        sql, params = builder.build_dialogue_query(query)

        # In fuzzy mode, dialogue should use LIKE
        assert "d.text LIKE ?" in sql
        assert "%hello world%" in params

    def test_build_with_action_content(self):
        """Test query with action content (lines 145-157)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            action="runs quickly",
        )

        sql, params = builder.build_action_query(query)

        # Action query should search in scene_content
        assert "scene_content" in sql.lower()
        assert "runs quickly" in params[0] if params else False

    def test_build_parenthetical_query_fuzzy(self):
        """Test parenthetical query in fuzzy mode (lines 321-329)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            parenthetical="angrily",
            mode=SearchMode.FUZZY,
        )

        sql, params = builder.build_parenthetical_query(query)

        # In fuzzy mode, should use LIKE
        assert "LIKE" in sql
        assert "%angrily%" in params[0] if params else False

    def test_build_location_query_strict(self):
        """Test location query in strict mode (lines 349-352)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            locations=["OFFICE"],
            mode=SearchMode.STRICT,
        )

        sql, params = builder.build_location_query(query)

        # In strict mode, should use exact match
        assert "scene_location = ?" in sql
        assert "OFFICE" in params

    def test_build_character_query_fuzzy(self):
        """Test character query in fuzzy mode (lines 376-388)."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            characters=["John", "Jane"],
            mode=SearchMode.FUZZY,
        )

        sql, params = builder.build_character_query(query)

        # In fuzzy mode, should use LIKE
        assert "LIKE" in sql
        assert any("%John%" in str(p) for p in params)
        assert any("%Jane%" in str(p) for p in params)

    def test_pagination_with_large_offset(self):
        """Test pagination with offset (lines 396-400, 414-418)."""
        builder = QueryBuilder()

        # Test with limit only
        query1 = SearchQuery(
            raw_query="test",
            limit=10,
            offset=0,
        )
        sql1, _ = builder.build_sql_query(query1)
        assert "LIMIT 10" in sql1

        # Test with offset
        query2 = SearchQuery(
            raw_query="test",
            limit=10,
            offset=20,
        )
        sql2, _ = builder.build_sql_query(query2)
        assert "LIMIT 10 OFFSET 20" in sql2


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

            # Check that season/episode is included in output
            printed_text = str(mock_print.call_args_list)
            assert "S02E05" in printed_text or "Season 2" in printed_text

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

            # Check that character name is included
            printed_text = str(mock_print.call_args_list)
            assert "JOHN" in printed_text

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

        line = formatter._format_brief_line(result, 1)
        assert "Test" in line
        assert "#1" in line

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

            printed_text = str(mock_print.call_args_list)
            assert "runs quickly" in printed_text or "Action" in printed_text


class TestSearchParserCoverage:
    """Tests to cover missing lines in search/parser.py."""

    def test_parse_with_episode_range_error(self):
        """Test parse with invalid episode range (lines 114-123, 130, 141)."""
        parser = QueryParser()

        # Test valid episode range
        query = parser.parse("test range:S01E01-E05")
        assert query.season_start == 1
        assert query.episode_start == 1
        assert query.episode_end == 5

        # Test single episode
        query2 = parser.parse("test range:S02E03")
        assert query2.season_start == 2
        assert query2.episode_start == 3

        # Test invalid range format (should not crash)
        query3 = parser.parse("test range:invalid")
        assert query3.season_start is None
