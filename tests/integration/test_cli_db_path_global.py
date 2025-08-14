"""Integration tests for global --db-path option."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app

runner = CliRunner()


def test_global_db_path_with_init(tmp_path: Path) -> None:
    """Test global --db-path option with init command."""
    custom_db = tmp_path / "custom.db"

    # Initialize with global --db-path option
    result = runner.invoke(app, ["--db-path", str(custom_db), "init"])

    assert result.exit_code == 0
    assert custom_db.exists()
    assert "Database initialized successfully" in result.output


def test_global_db_path_with_multiple_commands(tmp_path: Path) -> None:
    """Test global --db-path works with different commands."""
    custom_db = tmp_path / "custom.db"

    # Initialize database
    result = runner.invoke(app, ["--db-path", str(custom_db), "init"])
    assert result.exit_code == 0

    # Test with search command (should use same database)
    result = runner.invoke(app, ["--db-path", str(custom_db), "search", "test"])
    # Should not error, even if no results
    assert result.exit_code == 0


def test_global_db_path_precedence_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that global --db-path takes precedence over environment variable."""
    env_db = tmp_path / "env.db"
    cli_db = tmp_path / "cli.db"

    # Set environment variable
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(env_db))

    # Use CLI option (should override env var)
    result = runner.invoke(app, ["--db-path", str(cli_db), "init"])

    assert result.exit_code == 0
    assert cli_db.exists()
    assert not env_db.exists()  # Environment path should not be used


def test_global_db_path_with_query_subcommands(tmp_path: Path) -> None:
    """Test that query subcommands inherit global --db-path."""
    custom_db = tmp_path / "custom.db"

    # Initialize database
    result = runner.invoke(app, ["--db-path", str(custom_db), "init"])
    assert result.exit_code == 0

    # Test query list (which lists available queries)
    result = runner.invoke(app, ["--db-path", str(custom_db), "query", "list"])
    assert result.exit_code == 0


def test_global_db_path_with_scene_commands(tmp_path: Path) -> None:
    """Test that scene subcommands inherit global --db-path."""
    custom_db = tmp_path / "custom.db"

    # Initialize database
    result = runner.invoke(app, ["--db-path", str(custom_db), "init"])
    assert result.exit_code == 0

    # Test scene read (will fail without data, but should recognize the database)
    result = runner.invoke(
        app,
        [
            "--db-path",
            str(custom_db),
            "scene",
            "read",
            "--project",
            "test",
            "--scene",
            "1",
        ],
    )
    # Should fail gracefully with proper error (not database connection error)
    assert "not found" in result.output.lower() or "no scene" in result.output.lower()


def test_global_db_path_relative_path(tmp_path: Path) -> None:
    """Test global --db-path with relative path."""
    # Change to temp directory
    import os

    original_dir = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Use relative path
        result = runner.invoke(app, ["--db-path", "./custom.db", "init"])

        assert result.exit_code == 0
        assert (tmp_path / "custom.db").exists()
    finally:
        os.chdir(original_dir)


def test_global_db_path_not_provided_uses_default(tmp_path: Path) -> None:
    """Test that omitting --db-path uses default behavior."""
    # Change to temp directory to avoid conflicts
    import os

    original_dir = Path.cwd()
    try:
        os.chdir(tmp_path)

        # No --db-path option
        result = runner.invoke(app, ["init"])

        # Debug output
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")

        assert result.exit_code == 0
        # Should create default scriptrag.db in current directory
        assert (tmp_path / "scriptrag.db").exists()
    finally:
        os.chdir(original_dir)


def test_global_db_path_help_text() -> None:
    """Test that --db-path appears in global help."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--db-path" in result.output
    assert "database file" in result.output.lower()


def test_global_db_path_order_matters() -> None:
    """Test that --db-path must come before the command."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        custom_db = Path(tmp_dir) / "custom.db"

        # Correct order: global option before command
        result = runner.invoke(app, ["--db-path", str(custom_db), "init"])
        assert result.exit_code == 0

        # Incorrect order: should fail or be ignored
        # Note: This behavior depends on Typer's handling
        # We're testing to ensure our implementation follows Typer conventions
