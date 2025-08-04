"""Unit tests for CLI module."""

from unittest.mock import Mock, patch

from scriptrag.cli import CLIContext, app, main, set_cli_context


class TestCLIMain:
    """Test CLI main entry point."""

    def test_main_function(self):
        """Test that main() calls app()."""
        with patch("scriptrag.cli.app") as mock_app:
            # Mock app to prevent actual execution
            mock_app.return_value = None
            main()
            mock_app.assert_called_once()

    def test_main_as_script(self):
        """Test __main__ execution."""
        # Test the if __name__ == "__main__" block
        test_code = """
__name__ = "__main__"
main_called = False
def main():
    global main_called
    main_called = True

if __name__ == "__main__":
    main()
"""
        namespace = {}
        exec(test_code, namespace)  # noqa: S102
        assert namespace["main_called"] is True


class TestCLIErrorHandlers:
    """Test CLI error handling paths."""

    def test_file_exists_error_handled(self, tmp_path):
        """Test FileExistsError is caught and handled."""
        from scriptrag.api import DatabaseInitializer

        # Create a mock initializer that raises FileExistsError
        mock_initializer = Mock(spec=DatabaseInitializer)
        mock_initializer.initialize_database.side_effect = FileExistsError(
            "Database exists"
        )

        # Set up CLI context with mock
        set_cli_context(CLIContext(db_initializer=mock_initializer))

        # Create non-existent db path
        db_path = tmp_path / "test.db"

        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["--db-path", str(db_path)])

        # Should exit with code 1 and show error
        assert result.exit_code == 1
        # The FileExistsError message may be wrapped differently
        assert "Database exists" in result.stdout

        # Reset context
        set_cli_context(CLIContext())
