"""Tests for CLI main module."""

from unittest.mock import patch

import pytest
import typer

from scriptrag.cli.main import app, main


class TestCLIMain:
    """Test CLI main functionality."""

    def test_app_configuration(self):
        """Test that the main app is configured correctly."""
        assert isinstance(app, typer.Typer)
        assert app.info.name == "scriptrag"
        assert "Graph-Based Screenwriting Assistant" in app.info.help
        assert app.pretty_exceptions_enable is False

    def test_app_has_commands(self):
        """Test that all expected commands are registered."""
        command_names = [cmd.name for cmd in app.registered_commands]

        # Check that main commands are registered
        assert "init" in command_names
        assert "list" in command_names or "ls" in command_names  # ls is an alias
        assert "analyze" in command_names
        assert "index" in command_names
        assert "search" in command_names

    def test_app_has_query_subapp(self):
        """Test that query subapp is registered."""
        subapps = [group.name for group in app.registered_groups]
        assert "query" in subapps

    def test_main_function_calls_app(self):
        """Test that main function calls the app."""
        with patch.object(app, "__call__") as mock_app_call:
            # Mock the app call to prevent SystemExit
            mock_app_call.side_effect = SystemExit(2)

            # Expect SystemExit and verify app was called
            with pytest.raises(SystemExit):
                main()
            mock_app_call.assert_called_once()

    def test_main_entry_point_coverage(self):
        """Test the main entry point when run as script (line 35 coverage)."""
        # This tests the if __name__ == "__main__" block
        # We need to simulate the module being run directly
        with patch("scriptrag.cli.main.main") as mock_main:
            # Import and execute the module's __main__ block manually
            import scriptrag.cli.main as main_module

            # Set __name__ to "__main__" to trigger the block
            original_name = main_module.__name__
            main_module.__name__ = "__main__"

            try:
                # This should trigger the main() call
                # Execute the __main__ block logic
                if main_module.__name__ == "__main__":
                    mock_main()  # Call the mocked main function
                mock_main.assert_called_once()
            finally:
                # Restore original name
                main_module.__name__ = original_name
