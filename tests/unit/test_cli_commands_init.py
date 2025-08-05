"""Unit tests for init command."""

from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from scriptrag.cli import app
from scriptrag.cli.commands.init import init_command


class TestInitCommand:
    """Test init command function."""

    def test_file_exists_error_handled(self, tmp_path):
        """Test FileExistsError is caught and handled."""
        # Create a mock initializer that raises FileExistsError
        mock_initializer = Mock()
        mock_initializer.initialize_database.side_effect = FileExistsError(
            "Database exists"
        )

        # Patch DatabaseInitializer
        with patch("scriptrag.cli.commands.init.DatabaseInitializer") as mock_class:
            mock_class.return_value = mock_initializer

            runner = CliRunner()
            result = runner.invoke(app, ["--db-path", str(tmp_path / "test.db")])

            # Should exit with code 1 and show error
            assert result.exit_code == 1
            assert "Database exists" in result.stdout

    def test_init_with_force_confirmation_cancelled(self, tmp_path):
        """Test that force confirmation can be cancelled."""
        db_path = tmp_path / "existing.db"
        db_path.touch()

        runner = CliRunner()
        result = runner.invoke(app, ["--db-path", str(db_path), "--force"], input="n\n")

        # Should exit with code 0
        assert result.exit_code == 0
        assert "Initialization cancelled" in result.stdout

    def test_runtime_error_handled(self, tmp_path):
        """Test generic runtime errors are handled."""
        # Create a mock initializer that raises RuntimeError
        mock_initializer = Mock()
        mock_initializer.initialize_database.side_effect = RuntimeError(
            "Something failed"
        )

        # Patch DatabaseInitializer
        with patch("scriptrag.cli.commands.init.DatabaseInitializer") as mock_class:
            mock_class.return_value = mock_initializer

            runner = CliRunner()
            result = runner.invoke(app, ["--db-path", str(tmp_path / "test.db")])

            # Should exit with code 1 and show error
            assert result.exit_code == 1
            assert "Failed to initialize database: Something failed" in result.stdout

    def test_init_command_direct_call(self, tmp_path):
        """Test calling init_command directly."""
        db_path = tmp_path / "test.db"

        # Mock the initializer
        mock_initializer = Mock()
        mock_initializer.initialize_database.return_value = db_path

        with patch("scriptrag.cli.commands.init.DatabaseInitializer") as mock_class:
            mock_class.return_value = mock_initializer

            # Should not raise
            init_command(db_path=db_path, force=False)

            # Verify initializer was called
            mock_initializer.initialize_database.assert_called_once()

    def test_init_with_config_file(self, tmp_path):
        """Test init command with config file parameter."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[scriptrag]
database_path = "/custom/path/from/config.db"
database_timeout = 60.0
log_level = "DEBUG"
""")

        # Mock the initializer
        mock_initializer = Mock()
        mock_initializer.initialize_database.return_value = tmp_path / "test.db"

        # Mock get_settings to capture the settings object
        with (
            patch("scriptrag.cli.commands.init.DatabaseInitializer") as mock_class,
            patch(
                "scriptrag.config.ScriptRAGSettings.from_multiple_sources"
            ) as mock_from_sources,
        ):
            # Create expected settings
            expected_settings = Mock(
                database_timeout=60.0,
                log_level="DEBUG",
                database_path=Path("/custom/path/from/config.db"),
            )
            mock_from_sources.return_value = expected_settings
            mock_class.return_value = mock_initializer

            runner = CliRunner()
            result = runner.invoke(app, ["--config", str(config_file)])

            # Should succeed
            if result.exit_code != 0:
                print(f"Exit code: {result.exit_code}")
                print(f"Stdout: {result.stdout}")
                print(f"Stderr: {result.stderr}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0

            # Verify settings were loaded from config file
            mock_from_sources.assert_called_once()
            call_args = mock_from_sources.call_args
            assert call_args[1]["config_files"] == [config_file]
