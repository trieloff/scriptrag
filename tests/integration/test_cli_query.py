"""Integration tests for query CLI command."""

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from tests.utils import strip_ansi_codes


class TestQueryCLI:
    """Test query CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary test database with sample data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Create schema similar to ScriptRAG
        conn.executescript("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                file_path TEXT UNIQUE,
                project_title TEXT,
                series_title TEXT,
                season INTEGER,
                episode INTEGER,
                metadata TEXT
            );

            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER NOT NULL,
                scene_number INTEGER NOT NULL,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            );

            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER NOT NULL,
                character TEXT NOT NULL,
                dialogue TEXT,
                parenthetical TEXT,
                dialogue_order INTEGER,
                FOREIGN KEY (scene_id) REFERENCES scenes(id)
            );

            -- Insert test data
            INSERT INTO scripts (
                id, title, author, file_path, series_title, season, episode, metadata
            ) VALUES
                (1, 'Test Script', 'Test Author', '/tmp/test1.fountain',
                 'Test Series', 1, 1, '{"season": 1, "episode": 1}'),
                (2, 'Another Script', 'Another Author', '/tmp/test2.fountain',
                 'Test Series', 1, 2, '{"season": 1, "episode": 2}');

            INSERT INTO scenes (
                id, script_id, scene_number, heading, location, time_of_day, content
            ) VALUES
                (1, 1, 1, 'INT. OFFICE - DAY', 'Office', 'Day', 'The office is busy.'),
                (
                    2,
                    1,
                    2,
                    'EXT. STREET - NIGHT',
                    'Street',
                    'Night',
                    'The street is empty.'
                ),
                (3, 2, 1, 'INT. HOME - MORNING', 'Home', 'Morning', 'Morning routine.');

            INSERT INTO dialogues (
                id, scene_id, character, dialogue, parenthetical, dialogue_order
            ) VALUES
                (1, 1, 'ALICE', 'Hello, Bob!', NULL, 1),
                (2, 1, 'BOB', 'Hi, Alice!', 'smiling', 2),
                (3, 2, 'ALICE', 'Where are we going?', NULL, 1);
        """)
        conn.commit()
        conn.close()

        return db_path

    @pytest.fixture
    def temp_query_dir(self, tmp_path):
        """Create temporary query directory with test queries."""
        query_dir = tmp_path / "queries"
        query_dir.mkdir()

        # Create test queries
        (query_dir / "list_scenes.sql").write_text("""-- name: list_scenes
-- description: List all scenes
-- param: limit int optional default=10
SELECT
    s.title as script_title,
    sc.scene_number,
    sc.heading as scene_heading,
    sc.content as scene_content
FROM scenes sc
JOIN scripts s ON sc.script_id = s.id
ORDER BY s.id, sc.scene_number
LIMIT :limit""")

        (query_dir / "character_lines.sql").write_text("""-- name: character_lines
-- description: Get dialogue for a character
-- param: character str required help="Character name"
SELECT
    d.character,
    d.dialogue,
    d.parenthetical
FROM dialogues d
WHERE d.character = :character
ORDER BY d.id""")

        return query_dir

    def test_query_help(self, runner, temp_db, temp_query_dir, monkeypatch):
        """Test query command help."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Need to reload the query module to pick up new queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        # Re-import app to get updated commands

        result = runner.invoke(app, ["query", "--help"])
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        assert "Execute SQL queries" in output
        # Check for commands section - may use Unicode box drawing
        assert "Commands" in output or "character_lines" in output

    def test_query_list(self, runner, temp_db, temp_query_dir, monkeypatch):
        """Test listing available queries."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(app, ["query", "list"])
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        assert "Available queries:" in output
        assert "list_scenes" in output
        assert "character_lines" in output

    def test_execute_query_no_params(
        self, runner, temp_db, temp_query_dir, monkeypatch
    ):
        """Test executing a query without parameters."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(app, ["query", "list_scenes", "--limit", "2"])
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        # Check for scene data in output
        assert "Test Script" in output or "Scene" in output

    def test_execute_query_with_params(
        self, runner, temp_db, temp_query_dir, monkeypatch
    ):
        """Test executing a query with required parameters."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(
            app, ["query", "character_lines", "--character", "ALICE"]
        )
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        assert "ALICE" in output or "Hello" in output or "dialogue" in output

    def test_execute_query_json_output(
        self, runner, temp_db, temp_query_dir, monkeypatch
    ):
        """Test executing query with JSON output."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(
            app, ["query", "character_lines", "--character", "BOB", "--json"]
        )
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0

        # Parse JSON output
        data = json.loads(output)
        assert "results" in data
        assert "count" in data
        assert "execution_time_ms" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["character"] == "BOB"

    def test_query_missing_required_param(
        self, runner, temp_db, temp_query_dir, monkeypatch
    ):
        """Test query fails when required parameter is missing."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(app, ["query", "character_lines"])

        # Should fail because character is required
        assert result.exit_code != 0

    def test_query_with_invalid_name(
        self, runner, temp_db, temp_query_dir, monkeypatch
    ):
        """Test executing non-existent query."""
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(app, ["query", "nonexistent"])

        # Should show error for unknown command
        assert result.exit_code != 0

    def test_query_no_database(self, runner, temp_query_dir, tmp_path, monkeypatch):
        """Test query fails when database doesn't exist."""
        nonexistent_db = str(tmp_path / "nonexistent.db")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", nonexistent_db)
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Reload to pick up queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        result = runner.invoke(app, ["query", "list_scenes"])
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 1
        assert "Database not found" in output or "Error" in output

    def test_empty_query_directory(self, runner, temp_db, tmp_path, monkeypatch):
        """Test behavior when custom query directory is empty.

        Note: The current design shows built-in queries even when a custom directory
        is empty. This ensures users always have access to essential queries.
        """
        empty_dir = tmp_path / "empty_queries"
        empty_dir.mkdir()

        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(temp_db))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(empty_dir))

        result = runner.invoke(app, ["query", "list"])
        output = strip_ansi_codes(result.output)

        assert result.exit_code == 0
        # Current behavior: built-in queries are always available to ensure
        # users have access to essential functionality
        assert "Available queries:" in output
