"""Unit tests for init command."""

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
