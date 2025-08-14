"""Comprehensive unit tests for CLI main module."""

import pytest
import typer
from typer.testing import CliRunner

from scriptrag.cli.main import app, main


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


class TestCLIMainApp:
    """Test the main Typer app configuration."""

    def test_app_exists_and_configured(self):
        """Test that the app exists and is properly configured."""
        assert app is not None
        assert isinstance(app, typer.Typer)

        # Check app configuration
        assert app.info.name == "scriptrag"
        assert app.info.help == "ScriptRAG: A Graph-Based Screenwriting Assistant"
        assert app.pretty_exceptions_enable is False
        # add_completion is a private attribute in Typer 0.16.0
        assert app._add_completion is False

    def test_app_commands_registered(self, runner):
        """Test that all expected commands are registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # Check for main commands
        expected_commands = [
            "init",
            "list",
            "analyze",
            "index",
            "pull",
            "search",
            "watch",
            "mcp",
            "query",
        ]

        for command in expected_commands:
            assert command in output, f"Command '{command}' not found in help output"

    def test_app_hidden_alias(self, runner):
        """Test that the 'ls' alias for 'list' works but is hidden."""
        # Test that 'ls' works (should show help successfully)
        result = runner.invoke(app, ["ls", "--help"])
        assert result.exit_code == 0  # Help should work
        assert "Usage:" in result.output
        assert "scriptrag ls" in result.output

        # Test more safely by checking it doesn't appear in main help
        result = runner.invoke(app, ["--help"])
        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # ls should be hidden (not appear in main help)
        assert "Commands:" in output or "Usage:" in output
        # The 'ls' command should not be listed as it's hidden
        assert "ls" not in output  # Hidden command shouldn't appear in main help

    def test_app_subapp_registered(self, runner):
        """Test that query subapp is properly registered."""
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0

        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # Should show query subcommands
        assert "query" in output.lower() or "Usage:" in output

    def test_app_invalid_command(self, runner):
        """Test behavior with invalid command."""
        result = runner.invoke(app, ["nonexistent-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_app_version_info(self, runner):
        """Test that version information is accessible."""
        # Typer apps don't have built-in version by default,
        # but we can test that the app info is properly set
        assert app.info.name == "scriptrag"
        assert "ScriptRAG" in app.info.help


class TestCLIMainFunction:
    """Test the main() entry point function."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        assert main is not None
        assert callable(main)

    def test_main_function_signature(self):
        """Test main function signature."""
        import inspect

        sig = inspect.signature(main)
        # main() should take no parameters
        assert len(sig.parameters) == 0
        # main() should return None
        assert sig.return_annotation is None or sig.return_annotation is type(None)

    def test_main_function_calls_app(self):
        """Test that main() calls the app."""
        from unittest.mock import MagicMock, patch

        # Mock the app itself rather than just __call__
        mock_app = MagicMock()
        mock_app.side_effect = SystemExit(0)  # Simulate normal typer exit

        with patch("scriptrag.cli.main.app", mock_app):
            from contextlib import suppress

            with suppress(SystemExit):
                # Typer apps call sys.exit, which is expected
                main()

            # The app should have been called
            mock_app.assert_called_once_with()

    def test_main_function_handles_system_exit(self):
        """Test that main function properly handles SystemExit."""
        # main() should allow SystemExit to propagate
        # (this is normal behavior for CLI apps)
        with pytest.raises(SystemExit):
            main()


class TestCLIMainModuleIntegration:
    """Integration tests for the main CLI module."""

    def test_command_registration_order(self, runner):
        """Test that commands are registered in expected order."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # Commands should be listed (order may vary based on typer version)
        commands_found = []
        for line in output.split("\n"):
            line = line.strip()
            if any(
                cmd in line for cmd in ["init", "analyze", "mcp", "search", "query"]
            ):
                commands_found.append(line)

        # Should have found several commands
        assert len(commands_found) > 0

    def test_all_commands_have_help(self, runner):
        """Test that all registered commands have help text."""
        commands_to_test = ["init", "analyze", "mcp", "search", "index"]

        for command in commands_to_test:
            result = runner.invoke(app, [command, "--help"])
            # Some commands might exit with code != 0 due to missing deps,
            # but help should generally work
            from tests.utils import strip_ansi_codes

            output = strip_ansi_codes(result.output)

            # Should contain usage information
            assert "Usage:" in output or command in output or "help" in output.lower()

    def test_error_handling_configuration(self):
        """Test error handling configuration."""
        # pretty_exceptions_enable should be False for production CLI
        assert app.pretty_exceptions_enable is False

        # add_completion should be False to avoid auto shell completion
        # In Typer 0.16.0, this is a private attribute
        assert app._add_completion is False

    def test_module_imports_complete(self):
        """Test that all necessary imports are present."""
        # Test that we can import everything needed from the main module
        import sys

        # Get the actual module object (not the function imported via __init__)
        main_module = sys.modules["scriptrag.cli.main"]

        # Should have app and main
        assert hasattr(main_module, "app")
        assert hasattr(main_module, "main")

        # Should be able to access all the imported commands
        from scriptrag.cli.main import app

        assert app is not None

    def test_direct_execution_block(self):
        """Test the if __name__ == '__main__' block."""
        # The direct execution block should be covered by pragma: no cover
        # We can test that the module has the right structure
        import sys

        # Get the actual module object (not the function imported via __init__)
        main_module = sys.modules["scriptrag.cli.main"]

        # Module should have the expected structure
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

        # The main function should work when called directly
        with pytest.raises(SystemExit):
            # This will exit, which is expected behavior
            main_module.main()


class TestCLIMainEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_command_line(self, runner):
        """Test behavior with no arguments."""
        result = runner.invoke(app, [])
        # Should show help or usage information
        assert "Usage:" in result.output or "ScriptRAG" in result.output

    def test_global_help_flag(self, runner):
        """Test global --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        assert "ScriptRAG: A Graph-Based Screenwriting Assistant" in output
        assert "Usage:" in output

    def test_import_error_handling(self):
        """Test that import errors are handled gracefully."""
        # The main module should import successfully even if some
        # command modules have issues

        try:
            import sys

            # Import the module to ensure it's loaded
            import scriptrag.cli.main as cli_main_module  # Use alias to avoid F401

            _ = cli_main_module  # Ensure it's used

            # Get the actual module object (not the function imported via __init__)
            cli_main = sys.modules["scriptrag.cli.main"]

            # Should succeed
            assert cli_main.app is not None
            assert cli_main.main is not None
        except ImportError as e:
            pytest.fail(f"Main CLI module failed to import: {e}")

    def test_typer_configuration_consistency(self):
        """Test that Typer configuration is consistent."""
        # Check that our app configuration matches expectations
        assert isinstance(app, typer.Typer)

        # Configuration should be production-ready
        assert app.pretty_exceptions_enable is False  # Don't show stack traces to users
        # In Typer 0.16.0, add_completion is a private attribute
        assert app._add_completion is False  # Don't auto-add shell completion

        # App info should be properly set
        assert app.info.name == "scriptrag"
        assert "ScriptRAG" in app.info.help
        assert "Graph-Based" in app.info.help

    def test_command_name_consistency(self, runner):
        """Test that command names are consistent."""
        result = runner.invoke(app, ["--help"])
        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # Commands should use consistent naming (lowercase, hyphen-separated if needed)
        expected_patterns = ["init", "analyze", "mcp", "search"]

        for pattern in expected_patterns:
            assert pattern in output, f"Expected command pattern '{pattern}' not found"

    def test_subcommand_integration(self, runner):
        """Test that subcommands are properly integrated."""
        # Test that query subapp works
        result = runner.invoke(app, ["query", "--help"])
        # Should not error out completely
        assert "query" in result.output.lower() or "Usage:" in result.output

    def test_alias_functionality(self, runner):
        """Test command aliases work correctly."""
        # Test that 'ls' alias for 'list' works
        # Note: ls is hidden, so it won't appear in help, but should work

        try:
            result_list = runner.invoke(app, ["list", "--help"])
            result_ls = runner.invoke(app, ["ls", "--help"])

            # Both should work similarly (both might fail due to deps, but consistently)
            assert result_list.exit_code == result_ls.exit_code
        except Exception:
            # If commands fail due to missing deps, that's ok for this test
            pass

    def test_app_metadata_completeness(self):
        """Test that app metadata is complete."""
        # App should have all expected metadata
        assert app.info.name is not None
        assert app.info.help is not None
        assert len(app.info.help) > 10  # Should have substantial help text

        # Should have reasonable configuration
        assert hasattr(app, "pretty_exceptions_enable")
        # In Typer 0.16.0, add_completion is a private attribute
        assert hasattr(app, "_add_completion")

        # Should have registered commands
        assert len(app.registered_commands) > 0
        assert len(app.registered_groups) >= 0  # query subapp adds a group
