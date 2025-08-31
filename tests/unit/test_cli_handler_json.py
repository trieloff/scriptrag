"""Tests for CLI handler JSON output functionality."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from scriptrag.cli.utils.cli_handler import CLIHandler, cli_command
from scriptrag.cli.validators.base import ValidationError


class TestCLIHandlerJSONOutput:
    """Test CLIHandler JSON output methods."""

    def test_handle_error_json_output(self):
        """Test JSON error output writes to stdout correctly."""
        handler = CLIHandler()

        # Capture stdout
        captured_output = StringIO()

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
            pytest.raises(typer.Exit) as exc_info,
        ):
            error = Exception("Test error message")
            handler.handle_error(error, json_output=True, exit_code=1)

            # Check that stdout.write was called with JSON
            assert mock_write.called
            call_args = mock_write.call_args[0][0]

            # Parse the JSON to verify it's valid
            json_output = call_args.rstrip("\n")
            parsed = json.loads(json_output)

            assert parsed["success"] is False
            assert "Test error message" in parsed["error"]
            assert mock_flush.called

        assert exc_info.value.exit_code == 1

    def test_handle_error_validation_json_output(self):
        """Test JSON output for validation errors."""
        handler = CLIHandler()

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
            pytest.raises(typer.Exit),
        ):
            error = ValidationError("Validation failed")
            handler.handle_error(error, json_output=True, exit_code=2)

            # Check that stdout.write was called
            assert mock_write.called
            call_args = mock_write.call_args[0][0]

            # Parse the JSON to verify it's valid
            json_output = call_args.rstrip("\n")
            parsed = json.loads(json_output)

            assert parsed["success"] is False
            assert "Validation failed" in parsed["error"]
            assert mock_flush.called

    def test_handle_success_json_output(self):
        """Test JSON success output writes to stdout correctly."""
        handler = CLIHandler()

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
        ):
            handler.handle_success(
                "Operation completed", data={"count": 42}, json_output=True
            )

            # Check that stdout.write was called with JSON
            assert mock_write.called
            call_args = mock_write.call_args[0][0]

            # Parse the JSON to verify it's valid
            json_output = call_args.rstrip("\n")
            parsed = json.loads(json_output)

            assert parsed["success"] is True
            assert parsed["message"] == "Operation completed"
            assert parsed["data"]["count"] == 42
            assert mock_flush.called

    def test_handle_success_json_no_data(self):
        """Test JSON success output without data."""
        handler = CLIHandler()

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
        ):
            handler.handle_success("Simple success", json_output=True)

            # Check that stdout.write was called with JSON
            assert mock_write.called
            call_args = mock_write.call_args[0][0]

            # Parse the JSON to verify it's valid
            json_output = call_args.rstrip("\n")
            parsed = json.loads(json_output)

            assert parsed["success"] is True
            assert parsed["message"] == "Simple success"
            assert mock_flush.called

    def test_handle_error_non_json_output(self):
        """Test that non-JSON error output uses console.print."""
        console = MagicMock(spec=Console)
        handler = CLIHandler(console=console)

        with pytest.raises(typer.Exit):
            error = Exception("Test error")
            handler.handle_error(error, json_output=False)

        # Verify console.print was called with error message
        console.print.assert_called()
        call_args = console.print.call_args[0][0]
        assert "Error: Test error" in call_args

    def test_handle_success_non_json_output(self):
        """Test that non-JSON success output uses console.print."""
        console = MagicMock(spec=Console)
        handler = CLIHandler(console=console)

        handler.handle_success("Success message", json_output=False)

        # Verify console.print was called with success message
        console.print.assert_called()
        call_args = console.print.call_args[0][0]
        assert "Success message" in call_args


class TestCLICommandDecorator:
    """Test the cli_command decorator with JSON output."""

    def test_cli_command_with_json_error(self):
        """Test cli_command decorator handles JSON errors."""

        @cli_command()
        def failing_command(json_output: bool = False):
            raise ValueError("Command failed")

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
            pytest.raises(typer.Exit),
        ):
            failing_command(json_output=True)

        # Check JSON was written
        assert mock_write.called
        call_args = mock_write.call_args[0][0]
        json_output_str = call_args.rstrip("\n")
        parsed = json.loads(json_output_str)
        assert parsed["success"] is False
        assert "Command failed" in parsed["error"]

    def test_cli_command_with_validation_error(self):
        """Test cli_command decorator handles validation errors with JSON."""

        @cli_command()
        def validating_command(json: bool = False):
            raise ValidationError("Invalid input")

        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
            pytest.raises(typer.Exit),
        ):
            validating_command(json=True)

        # Check JSON was written
        assert mock_write.called
        call_args = mock_write.call_args[0][0]
        json_output_str = call_args.rstrip("\n")
        parsed = json.loads(json_output_str)
        assert parsed["success"] is False
        assert "Invalid input" in parsed["error"]
