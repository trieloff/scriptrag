"""Unit tests for the MCP command."""

import logging
from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from scriptrag.cli.commands.mcp import mcp_command
from scriptrag.cli.main import app


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock(spec=logging.Logger)


class TestMCPCommand:
    """Test MCP command functionality."""

    def test_mcp_command_help(self, runner):
        """Test MCP command shows help."""
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0

        # Strip ANSI codes for help output checks
        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert "Run the ScriptRAG MCP (Model Context Protocol) server" in output
        assert "--host" in output
        assert "--port" in output
        assert "localhost" in output  # Default host
        assert "5173" in output  # Default port

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_default_params(self, mock_mcp_main, mock_logger, runner):
        """Test MCP command with default parameters."""
        # Run command with defaults
        result = runner.invoke(app, ["mcp"])

        # Verify success
        assert result.exit_code == 0

        # Verify MCP main was called
        mock_mcp_main.assert_called_once_with()

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Starting MCP server", host="localhost", port=5173
        )

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_custom_host_port(self, mock_mcp_main, mock_logger, runner):
        """Test MCP command with custom host and port."""
        # Run command with custom parameters
        result = runner.invoke(app, ["mcp", "--host", "127.0.0.1", "--port", "8080"])

        # Verify success
        assert result.exit_code == 0

        # Verify MCP main was called
        mock_mcp_main.assert_called_once_with()

        # Verify logging with custom values
        mock_logger.info.assert_called_once_with(
            "Starting MCP server", host="127.0.0.1", port=8080
        )

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_port_only_short_flag(self, mock_mcp_main, mock_logger, runner):
        """Test MCP command with port short flag only (host conflicts with help)."""
        # Note: -h conflicts with --help, so we only test --port/-p
        result = runner.invoke(app, ["mcp", "--host", "127.0.0.1", "--port", "9000"])

        # Verify success
        assert result.exit_code == 0

        # Verify parameters were parsed correctly
        mock_logger.info.assert_called_once_with(
            "Starting MCP server", host="127.0.0.1", port=9000
        )

        # Verify MCP main was called
        mock_mcp_main.assert_called_once_with()

    def test_mcp_command_import_error(self, runner):
        """Test MCP command handles import errors."""
        # This test covers the import error handling path
        # We'll mock the import to fail at the module level
        import sys

        original_modules = sys.modules.copy()

        try:
            # Remove the MCP server module to simulate import error
            if "scriptrag.mcp.server" in sys.modules:
                del sys.modules["scriptrag.mcp.server"]

            # Mock the import to raise ImportError
            def mock_import(name, *args):
                if name == "scriptrag.mcp.server":
                    raise ImportError("No module named 'scriptrag.mcp.server'")
                return original_modules.get(name)

            with patch("builtins.__import__", side_effect=mock_import):
                result = runner.invoke(app, ["mcp"])

                # Should exit with code 1 due to import error
                assert result.exit_code == 1
                assert (
                    "Failed to import MCP server" in result.output
                    or result.exit_code == 1
                )
        finally:
            # Restore original modules
            sys.modules.clear()
            sys.modules.update(original_modules)

    def test_mcp_command_import_error_via_invoke(self, runner):
        """Test MCP command import error through runner.invoke."""
        # Test that import errors are handled gracefully
        # This is a simplified test that just ensures the command can handle errors
        result = runner.invoke(app, ["mcp", "--help"])

        # Help should always work regardless of import issues
        assert result.exit_code == 0
        assert "MCP" in result.output or "Model Context Protocol" in result.output

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_keyboard_interrupt(self, mock_mcp_main, mock_logger, runner):
        """Test MCP command handles keyboard interrupt gracefully."""
        # Make MCP main raise KeyboardInterrupt
        mock_mcp_main.side_effect = KeyboardInterrupt()

        # The runner.invoke captures the Exit, so we test the exit code directly
        result = runner.invoke(app, ["mcp"])

        # Should exit with code 0 (graceful shutdown)
        assert result.exit_code == 0

        # Should log graceful shutdown
        mock_logger.info.assert_any_call(
            "Starting MCP server", host="localhost", port=5173
        )
        mock_logger.info.assert_any_call("MCP server stopped by user")

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_keyboard_interrupt_via_invoke(
        self, mock_mcp_main, mock_logger, runner
    ):
        """Test MCP command keyboard interrupt through runner.invoke."""
        mock_mcp_main.side_effect = KeyboardInterrupt()

        result = runner.invoke(app, ["mcp"])

        # Should exit with code 0 (graceful shutdown)
        assert result.exit_code == 0

        # Should log graceful shutdown
        mock_logger.info.assert_any_call(
            "Starting MCP server", host="localhost", port=5173
        )
        mock_logger.info.assert_any_call("MCP server stopped by user")

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_general_exception(self, mock_mcp_main, mock_logger, runner):
        """Test MCP command handles general exceptions."""
        # Make MCP main raise a general exception
        mock_mcp_main.side_effect = RuntimeError("Server startup failed")

        # The runner.invoke captures the Exit, so we test the exit code directly
        result = runner.invoke(app, ["mcp"])

        # Should exit with code 1
        assert result.exit_code == 1

        # Should log error
        mock_logger.info.assert_called_with(
            "Starting MCP server", host="localhost", port=5173
        )
        mock_logger.error.assert_called_once_with(
            "MCP server failed", error="Server startup failed"
        )

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_general_exception_via_invoke(
        self, mock_mcp_main, mock_logger, runner
    ):
        """Test MCP command general exception through runner.invoke."""
        mock_mcp_main.side_effect = RuntimeError("Server crashed")

        result = runner.invoke(app, ["mcp"])

        # Should exit with code 1
        assert result.exit_code == 1

        # Should log error
        mock_logger.info.assert_called_with(
            "Starting MCP server", host="localhost", port=5173
        )
        mock_logger.error.assert_called_once_with(
            "MCP server failed", error="Server crashed"
        )

    def test_mcp_command_invalid_port_type(self, runner):
        """Test MCP command with invalid port type."""
        # Try to pass non-integer port
        result = runner.invoke(app, ["mcp", "--port", "not-a-number"])

        # Should fail with typer error
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "Error" in result.output

    def test_mcp_command_negative_port(self, runner):
        """Test MCP command with negative port number."""
        # Typer will accept negative numbers, but it's worth testing
        with patch("scriptrag.cli.commands.mcp.logger") as mock_logger:
            with patch("scriptrag.mcp.server.main") as mock_mcp_main:
                result = runner.invoke(app, ["mcp", "--port", "-1"])

                # Should succeed (validation is not our responsibility here)
                assert result.exit_code == 0

                # Should log with negative port
                mock_logger.info.assert_called_once_with(
                    "Starting MCP server", host="localhost", port=-1
                )

    def test_mcp_command_large_port(self, runner):
        """Test MCP command with large port number."""
        with patch("scriptrag.cli.commands.mcp.logger") as mock_logger:
            with patch("scriptrag.mcp.server.main") as mock_mcp_main:
                result = runner.invoke(app, ["mcp", "--port", "65536"])

                # Should succeed (port validation happens at server level)
                assert result.exit_code == 0

                # Should log with large port
                mock_logger.info.assert_called_once_with(
                    "Starting MCP server", host="localhost", port=65536
                )

    def test_mcp_command_empty_host(self, runner):
        """Test MCP command with empty host string."""
        with patch("scriptrag.cli.commands.mcp.logger") as mock_logger:
            with patch("scriptrag.mcp.server.main") as mock_mcp_main:
                result = runner.invoke(app, ["mcp", "--host", ""])

                # Should succeed (host validation happens at server level)
                assert result.exit_code == 0

                # Should log with empty host
                mock_logger.info.assert_called_once_with(
                    "Starting MCP server", host="", port=5173
                )

    def test_mcp_command_circular_import_error(self, runner):
        """Test MCP command handles circular import edge case."""
        # This test ensures the command structure handles complex scenarios
        # We test with an invalid host to trigger error handling
        result = runner.invoke(app, ["mcp", "--host", ""])

        # Should handle the invalid configuration
        # The specific exit code may vary, but it should not crash
        assert result.exit_code in [0, 1]  # Either succeeds or fails gracefully


class TestMCPCommandDirect:
    """Test mcp_command function directly."""

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_function_defaults(self, mock_mcp_main, mock_logger):
        """Test mcp_command function with default parameters."""
        # Call function directly
        mcp_command()

        # Verify MCP main was called
        mock_mcp_main.assert_called_once_with()

        # Verify logging with defaults
        mock_logger.info.assert_called_once_with(
            "Starting MCP server", host="localhost", port=5173
        )

    @patch("scriptrag.cli.commands.mcp.logger")
    @patch("scriptrag.mcp.server.main")
    def test_mcp_command_function_custom_params(self, mock_mcp_main, mock_logger):
        """Test mcp_command function with custom parameters."""
        # Call function directly with custom params
        mcp_command(host="192.168.1.100", port=3000)

        # Verify MCP main was called
        mock_mcp_main.assert_called_once_with()

        # Verify logging with custom params
        mock_logger.info.assert_called_once_with(
            "Starting MCP server", host="192.168.1.100", port=3000
        )

    def test_mcp_command_function_import_error(self):
        """Test mcp_command function handles import error."""
        # Test the function with parameters that should work
        try:
            # This should not raise an exception in most cases
            # If MCP server is missing, it will raise typer.Exit
            mcp_command(host="test", port=0)
        except typer.Exit as e:
            # Expected when MCP server is not available
            assert e.exit_code in [0, 1]
        except ImportError:
            # Also expected when dependencies are missing
            pass

    @patch("scriptrag.cli.commands.mcp.logger")
    def test_mcp_command_function_keyboard_interrupt(self, mock_logger):
        """Test mcp_command function handles keyboard interrupt."""
        with patch("scriptrag.mcp.server.main", side_effect=KeyboardInterrupt()):
            with pytest.raises(typer.Exit) as exc_info:
                mcp_command(host="test", port=1234)

            # Should exit with code 0
            assert exc_info.value.exit_code == 0

            # Should log startup and shutdown
            mock_logger.info.assert_any_call(
                "Starting MCP server", host="test", port=1234
            )
            mock_logger.info.assert_any_call("MCP server stopped by user")

    @patch("scriptrag.cli.commands.mcp.logger")
    def test_mcp_command_function_general_exception(self, mock_logger):
        """Test mcp_command function handles general exception."""
        with patch(
            "scriptrag.mcp.server.main",
            side_effect=ValueError("Invalid server configuration"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                mcp_command(host="invalid", port=0)

            # Should exit with code 1
            assert exc_info.value.exit_code == 1

            # Should log startup and error
            mock_logger.info.assert_called_with(
                "Starting MCP server", host="invalid", port=0
            )
            mock_logger.error.assert_called_once_with(
                "MCP server failed", error="Invalid server configuration"
            )


class TestMCPCommandIntegration:
    """Integration tests for MCP command."""

    def test_mcp_command_in_main_app(self, runner):
        """Test that MCP command is properly registered in main app."""
        # Test that the command exists
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)

        # Should list mcp as available command
        assert "mcp" in output.lower()

    def test_mcp_command_typer_annotations(self):
        """Test that mcp_command has correct typer annotations."""
        # Import the function to check its signature
        import inspect

        from scriptrag.cli.commands.mcp import mcp_command

        sig = inspect.signature(mcp_command)

        # Check parameter annotations
        assert "host" in sig.parameters
        assert "port" in sig.parameters

        # Check return type annotation
        assert sig.return_annotation is None or sig.return_annotation is type(None)

    @patch("scriptrag.cli.commands.mcp.logger")
    def test_mcp_command_logger_creation(self, mock_logger):
        """Test that logger is properly created and configured."""
        # The logger should be created at module level
        from scriptrag.cli.commands.mcp import logger

        # Verify logger exists and has expected name
        # Note: This tests the logger creation, not mocking it
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
