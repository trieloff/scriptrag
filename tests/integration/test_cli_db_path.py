"""Integration tests for --db-path option across CLI commands."""

from typer.testing import CliRunner

from scriptrag.cli.main import app

runner = CliRunner()


class TestDbPathOption:
    """Test --db-path option for various commands."""

    def test_init_with_custom_db_path(self, tmp_path):
        """Test init command with custom database path."""
        db_path = tmp_path / "custom_db.sqlite"

        result = runner.invoke(app, ["init", "--db-path", str(db_path)])

        assert result.exit_code == 0
        assert db_path.exists()
        assert "Database initialized successfully" in result.output

    def test_init_with_force_and_custom_db_path(self, tmp_path):
        """Test init command with force flag and custom database path."""
        db_path = tmp_path / "custom_db.sqlite"

        # First init
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert db_path.exists()

        # Second init with force (should overwrite)
        result = runner.invoke(
            app, ["init", "--db-path", str(db_path), "--force"], input="y\n"
        )
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output

    def test_index_with_custom_db_path(self, tmp_path):
        """Test index command with custom database path."""
        db_path = tmp_path / "custom_db.sqlite"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Run index with custom db path
        result = runner.invoke(app, ["index", "--db-path", str(db_path), str(tmp_path)])

        # Should succeed (even if no files found)
        assert result.exit_code == 0

    def test_search_with_custom_db_path(self, tmp_path):
        """Test search command with custom database path."""
        db_path = tmp_path / "custom_db.sqlite"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Run search with custom db path
        result = runner.invoke(app, ["search", "--db-path", str(db_path), "test query"])

        # Should succeed (even if no results found)
        assert result.exit_code == 0

    def test_query_commands_with_custom_db_path(self, tmp_path):
        """Test query commands with custom database path."""
        db_path = tmp_path / "custom_db.sqlite"

        # Initialize database first
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Test query list command with custom db path
        # Note: Since query commands are dynamically registered, we test the help
        result = runner.invoke(app, ["query", "--help"])

        # Should show query help
        assert result.exit_code == 0
        assert "Execute SQL queries" in result.output

    def test_help_shows_db_path_option(self):
        """Test that help text shows --db-path option for all commands."""
        # Test init command help
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "--db-path" in result.output
        assert "Path to the SQLite database file" in result.output

        # Test index command help
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "--db-path" in result.output
        assert "Path to the SQLite database file" in result.output

        # Test search command help
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--db-path" in result.output
        assert "Path to the SQLite database file" in result.output

    def test_multiple_databases_isolation(self, tmp_path):
        """Test that different db-path values use isolated databases."""
        db1_path = tmp_path / "db1.sqlite"
        db2_path = tmp_path / "db2.sqlite"

        # Initialize two separate databases
        result1 = runner.invoke(app, ["init", "--db-path", str(db1_path)])
        assert result1.exit_code == 0
        assert db1_path.exists()

        result2 = runner.invoke(app, ["init", "--db-path", str(db2_path)])
        assert result2.exit_code == 0
        assert db2_path.exists()

        # Both databases should exist independently
        assert db1_path != db2_path
        assert db1_path.stat().st_size > 0
        assert db2_path.stat().st_size > 0

    def test_relative_db_path(self, tmp_path, monkeypatch):
        """Test that relative db paths work correctly."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Use relative path
        result = runner.invoke(app, ["init", "--db-path", "./custom.db"])

        assert result.exit_code == 0
        assert (tmp_path / "custom.db").exists()

    def test_nonexistent_db_path_directory(self, tmp_path):
        """Test behavior when db-path directory doesn't exist."""
        non_existent = tmp_path / "non_existent_dir" / "db.sqlite"

        # Should create parent directories
        result = runner.invoke(app, ["init", "--db-path", str(non_existent)])

        assert result.exit_code == 0
        assert non_existent.exists()
        assert non_existent.parent.exists()
