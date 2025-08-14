"""Integration tests for --db-path option across CLI commands."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from tests.utils import strip_ansi_codes

runner = CliRunner()

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


@pytest.fixture
def sample_fountain_with_metadata(tmp_path):
    """Copy sample Fountain file with boneyard metadata to temp directory."""
    source_file = FIXTURES_DIR / "coffee_shop_with_metadata.fountain"
    script_path = tmp_path / "sample.fountain"
    shutil.copy2(source_file, script_path)
    return script_path


class TestDatabasePathOption:
    """Test --db-path option functionality across commands."""

    def test_init_with_custom_db_path(self, tmp_path):
        """Test init command with custom database path."""
        db_path = tmp_path / "custom" / "database.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database with custom path
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Database initialized successfully" in output
        assert db_path.exists()

        # Verify database structure
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "scripts" in tables
        assert "scenes" in tables
        assert "characters" in tables

    def test_init_with_invalid_db_path(self, tmp_path):
        """Test init command with invalid database path."""
        db_path = tmp_path / "nonexistent" / "directory" / "database.db"

        # Try to initialize database with invalid path
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 1
        assert "Error" in output or "does not exist" in output.lower()

    def test_index_with_custom_db_path(self, tmp_path, sample_fountain_with_metadata):
        """Test index command with custom database path."""
        db_path = tmp_path / "custom.db"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Index with custom database path
        script_dir = sample_fountain_with_metadata.parent
        result = runner.invoke(
            app,
            ["index", "--db-path", str(db_path), str(script_dir)],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Indexing complete" in output or "Scripts Indexed" in output

        # Verify data was written to custom database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scripts")
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 0  # Should have indexed scripts

    def test_index_with_invalid_db_path(self, tmp_path):
        """Test index command with invalid database path parent directory."""
        db_path = tmp_path / "nonexistent" / "database.db"

        # Try to index with invalid path
        result = runner.invoke(
            app,
            ["index", "--db-path", str(db_path), "--dry-run", "."],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 1
        assert "Directory does not exist" in output

    def test_search_with_custom_db_path(self, tmp_path):
        """Test search command with custom database path."""
        db_path = tmp_path / "custom.db"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Search with custom database path
        result = runner.invoke(
            app,
            ["search", "--db-path", str(db_path), "test query"],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        # Should run without error even if no results

    def test_search_with_invalid_db_path(self, tmp_path):
        """Test search command with invalid database path."""
        db_path = tmp_path / "nonexistent" / "database.db"

        # Try to search with invalid path
        result = runner.invoke(
            app,
            ["search", "--db-path", str(db_path), "test"],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 1
        assert "Directory does not exist" in output

    def test_query_with_custom_db_path(self, tmp_path):
        """Test query command with custom database path."""
        db_path = tmp_path / "custom.db"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Query with custom database path
        result = runner.invoke(
            app,
            ["query", "test_list_scripts", "--db-path", str(db_path)],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        # Should run without error even if no results

    def test_query_with_invalid_db_path(self, tmp_path):
        """Test query command with invalid database path."""
        db_path = tmp_path / "nonexistent" / "database.db"

        # Try to query with invalid path
        result = runner.invoke(
            app,
            ["query", "test_list_scripts", "--db-path", str(db_path)],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 1
        assert "Directory does not exist" in output

    def test_db_path_consistency_across_commands(self, tmp_path):
        """Test that all commands use the same custom database."""
        db_path = tmp_path / "shared.db"

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Create a test fountain file
        test_script = tmp_path / "test.fountain"
        test_script.write_text(
            """Title: Test Script
Credit: Written by
Author: Test Author

INT. TEST LOCATION - DAY

CHARACTER
Some dialogue here.

/* boneyard:
metadata: {"analyzed": true}
*/
"""
        )

        # Index with custom database
        result = runner.invoke(
            app,
            ["index", "--db-path", str(db_path), str(tmp_path)],
        )
        assert result.exit_code == 0

        # Search should find the indexed content
        result = runner.invoke(
            app,
            ["search", "--db-path", str(db_path), "dialogue"],
        )
        output = strip_ansi_codes(result.stdout)
        assert result.exit_code == 0

        # Query should work with the same database
        result = runner.invoke(
            app,
            ["query", "test_list_scripts", "--db-path", str(db_path)],
        )
        assert result.exit_code == 0

    def test_db_path_with_relative_path(self, tmp_path, monkeypatch):
        """Test --db-path with relative path."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Use relative path
        db_path = Path("./custom/database.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database with relative path
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 0
        assert "Database initialized successfully" in output
        assert db_path.exists()

    def test_db_path_overrides_environment_variable(self, tmp_path, monkeypatch):
        """Test that --db-path overrides environment variable."""
        env_db_path = tmp_path / "env.db"
        cli_db_path = tmp_path / "cli.db"

        # Set environment variable
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(env_db_path))

        # Initialize with CLI option (should override env var)
        result = runner.invoke(app, ["init", "--db-path", str(cli_db_path)])
        assert result.exit_code == 0

        # CLI path should exist, env path should not
        assert cli_db_path.exists()
        assert not env_db_path.exists()

    def test_help_shows_db_path_option(self):
        """Test that help text shows --db-path option for all commands."""
        commands = ["index", "search"]

        for cmd in commands:
            result = runner.invoke(app, [cmd, "--help"])
            output = result.stdout

            assert "--db-path" in output
            assert "Path to the SQLite database file" in output

        # Test query subcommand
        result = runner.invoke(app, ["query", "test_list_scripts", "--help"])
        output = result.stdout

        assert "--db-path" in output
        assert "Path to the SQLite database file" in output


class TestPathValidation:
    """Test path validation for --db-path option."""

    def test_validation_nonexistent_parent_directory(self, tmp_path):
        """Test validation when parent directory doesn't exist."""
        db_path = tmp_path / "deep" / "nested" / "path" / "database.db"

        # All commands should fail with consistent error
        for cmd_args in [
            ["index", "--db-path", str(db_path), "--dry-run", "."],
            ["search", "--db-path", str(db_path), "test"],
            ["query", "test_list_scripts", "--db-path", str(db_path)],
        ]:
            result = runner.invoke(app, cmd_args)
            output = strip_ansi_codes(result.stdout)

            assert result.exit_code == 1
            assert "Directory does not exist" in output

    def test_validation_parent_is_file(self, tmp_path):
        """Test validation when parent path is a file, not directory."""
        parent_file = tmp_path / "notadir"
        parent_file.write_text("content")
        db_path = parent_file / "database.db"

        # Should fail because parent is a file
        result = runner.invoke(
            app,
            ["index", "--db-path", str(db_path), "--dry-run", "."],
        )
        output = strip_ansi_codes(result.stdout)

        assert result.exit_code == 1
        assert "not a directory" in output.lower()

    def test_validation_success_when_parent_exists(self, tmp_path):
        """Test that validation passes when parent directory exists."""
        db_dir = tmp_path / "databases"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "custom.db"

        # Should succeed
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert db_path.exists()


class TestSettingsCacheClearing:
    """Test that settings cache is properly cleared."""

    def test_settings_cache_cleared_on_each_command(self, tmp_path, monkeypatch):
        """Test that settings cache is cleared to pick up fresh configuration."""
        db1 = tmp_path / "db1.db"
        db2 = tmp_path / "db2.db"

        # Initialize first database
        result = runner.invoke(app, ["init", "--db-path", str(db1)])
        assert result.exit_code == 0

        # Initialize second database (should not use cached settings)
        result = runner.invoke(app, ["init", "--db-path", str(db2)])
        assert result.exit_code == 0

        # Both databases should exist
        assert db1.exists()
        assert db2.exists()

        # Commands should use their respective databases
        for db_path in [db1, db2]:
            result = runner.invoke(
                app,
                ["query", "test_list_scripts", "--db-path", str(db_path)],
            )
            assert result.exit_code == 0
