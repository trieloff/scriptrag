"""Integration tests for scriptrag init command."""

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app
from scriptrag.config import set_settings


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_scriptrag.db"


class TestInitCommand:
    """Test the scriptrag init command."""

    def test_init_creates_database(self, runner, temp_db_path):
        """Test that init command creates a new database."""
        # Run init command
        result = runner.invoke(app, ["--db-path", str(temp_db_path)])

        # Check command succeeded
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout

        # Check database file exists
        assert temp_db_path.exists()

        # Verify database schema
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "actions",
            "character_relationships",
            "characters",
            "dialogues",
            "embeddings",
            "scene_graph_edges",
            "scenes",
            "schema_version",
            "scripts",
        ]

        # sqlite_sequence is created automatically by SQLite
        tables = [t for t in tables if t != "sqlite_sequence"]
        assert tables == expected_tables

        # Check schema version
        cursor.execute("SELECT version, description FROM schema_version")
        version, description = cursor.fetchone()
        assert version == 1
        assert description == "Initial ScriptRAG database schema"

        conn.close()

    def test_init_fails_if_database_exists(self, runner, temp_db_path):
        """Test that init fails if database already exists."""
        # Create existing database
        temp_db_path.touch()

        # Run init command
        result = runner.invoke(app, ["--db-path", str(temp_db_path)])

        # Check command failed
        assert result.exit_code == 1
        # Normalize whitespace to handle line wrapping on macOS
        import re

        output_normalized = re.sub(r"\s+", " ", result.stdout)
        assert "Database already exists" in output_normalized
        assert "Use --force to overwrite" in output_normalized

    def test_init_force_overwrites_database(self, runner, temp_db_path):
        """Test that init --force overwrites existing database."""
        # Create existing database with dummy content
        conn = sqlite3.connect(str(temp_db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        # Run init command with force, auto-confirm
        result = runner.invoke(
            app, ["--db-path", str(temp_db_path), "--force"], input="y\n"
        )

        # Check command succeeded
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout

        # Verify old table is gone and new schema exists
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dummy'"
        )
        assert cursor.fetchone() is None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scripts'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_init_force_cancel(self, runner, temp_db_path):
        """Test that init --force can be cancelled."""
        # Create existing database
        temp_db_path.touch()

        # Run init command with force, but cancel
        result = runner.invoke(
            app, ["--db-path", str(temp_db_path), "--force"], input="n\n"
        )

        # Check command was cancelled
        assert result.exit_code == 0
        assert "Initialization cancelled" in result.stdout

    def test_init_default_path(self, runner, monkeypatch, tmp_path):
        """Test that init uses default path when not specified."""
        # Change working directory to temp path
        monkeypatch.chdir(tmp_path)

        # Run init command without path
        result = runner.invoke(app, [])

        # Check command succeeded
        if result.exit_code != 0:
            print(f"Output: {result.stdout}")
            print(f"Exception: {result.exception}")
            if result.exception:
                import traceback

                traceback.print_exception(
                    type(result.exception),
                    result.exception,
                    result.exception.__traceback__,
                )
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout

        # Check database created at default location
        default_db = tmp_path / "scriptrag.db"
        assert default_db.exists()

    def test_init_creates_parent_directories(self, runner, tmp_path):
        """Test that init creates parent directories if needed."""
        # Use nested path that doesn't exist
        nested_path = tmp_path / "nested" / "dir" / "scriptrag.db"

        # Run init command
        result = runner.invoke(app, ["--db-path", str(nested_path)])

        # Check command succeeded
        assert result.exit_code == 0
        assert nested_path.exists()

    def test_init_handles_sql_errors(self, runner, temp_db_path, monkeypatch):
        """Test that init handles SQL errors gracefully."""
        # Mock the SQL file to have invalid SQL
        from scriptrag.api.database import DatabaseInitializer

        original_read = DatabaseInitializer._read_sql_file

        def mock_read_sql(self, filename):
            if filename == "init_database.sql":
                return "INVALID SQL STATEMENT;"
            return original_read(self, filename)

        monkeypatch.setattr(DatabaseInitializer, "_read_sql_file", mock_read_sql)

        # Run init command
        result = runner.invoke(app, ["--db-path", str(temp_db_path)])

        # Check command failed
        assert result.exit_code == 1
        assert "Failed to initialize database" in result.stdout

        # Check database was cleaned up
        assert not temp_db_path.exists()

    def test_init_handles_missing_sql_file(self, runner, temp_db_path, monkeypatch):
        """Test that init handles missing SQL file gracefully."""
        # Mock DatabaseInitializer with non-existent SQL directory
        from scriptrag.api.database import DatabaseInitializer

        def mock_init(self, sql_dir=None):  # noqa: ARG001
            self.sql_dir = Path("/nonexistent")

        monkeypatch.setattr(DatabaseInitializer, "__init__", mock_init)

        # Run init command
        result = runner.invoke(app, ["--db-path", str(temp_db_path)])

        # Check command failed
        assert result.exit_code == 1
        assert "Failed to initialize database" in result.stdout
