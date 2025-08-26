"""Additional tests to improve CLI module coverage."""

import asyncio
from io import StringIO
from unittest.mock import Mock, patch

import pytest
import typer
from rich.console import Console

from scriptrag.api.scene_models import (
    BibleReadResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.formatters.base import OutputFormat, OutputFormatter
from scriptrag.cli.formatters.scene_formatter import SceneFormatter
from scriptrag.cli.utils.cli_handler import CLIHandler, async_cli_command, cli_command
from scriptrag.cli.validators.base import ValidationError
from scriptrag.cli.validators.file_validator import FileValidator
from scriptrag.parser import Scene


class TestSceneFormatterExtended:
    """Extended tests for scene formatter to improve coverage."""

    @pytest.fixture
    def formatter(self):
        """Create a scene formatter."""
        return SceneFormatter()

    @pytest.fixture
    def sample_scene(self):
        """Create a sample scene."""
        return Scene(
            number="1",
            heading="INT. OFFICE - DAY",
            content="A busy office scene.",
            original_text="INT. OFFICE - DAY\n\nA busy office scene.",
            content_hash="fake_hash_12345",
        )

    def test_format_update_result_with_errors_json(self, formatter):
        """Test formatting update result with validation errors in JSON."""
        result = UpdateSceneResult(
            success=False,
            error="Update failed",
            updated_scene=None,
            validation_errors=["Invalid format", "Missing heading"],
        )

        output = formatter._format_update_result(result, OutputFormat.JSON)
        assert "Update failed" in output

    def test_format_update_result_with_warnings_text(self, formatter, sample_scene):
        """Test formatting update result with warnings in text format."""
        result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=sample_scene,
            validation_errors=["Minor warning"],
        )

        output = formatter._format_update_result(result, OutputFormat.TEXT)
        assert "Warning: Validation errors" in output
        assert "Scene updated successfully" in output

    def test_format_update_result_success_no_warnings(self, formatter, sample_scene):
        """Test formatting successful update without warnings."""
        result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=sample_scene,
            validation_errors=[],
        )

        output = formatter._format_update_result(result, OutputFormat.TEXT)
        assert output == "[green]Scene updated successfully[/green]"

    def test_format_bible_result_error(self, formatter):
        """Test formatting bible result with error."""
        result = BibleReadResult(
            success=False,
            error="Bible not found",
            content=None,
            bible_files=[],
        )

        output = formatter._format_bible_result(result, OutputFormat.TEXT)
        assert "Bible not found" in output

    def test_format_bible_result_with_content_json(self, formatter):
        """Test formatting bible result with content in JSON."""
        result = BibleReadResult(
            success=True,
            error=None,
            content="# Character Bible\n\nJohn - Main character",
            bible_files=[],
        )

        output = formatter._format_bible_result(result, OutputFormat.JSON)
        assert '"content"' in output
        assert "Character Bible" in output

    def test_format_bible_result_with_files_json(self, formatter):
        """Test formatting bible result with file list in JSON."""
        result = BibleReadResult(
            success=True,
            error=None,
            content=None,
            bible_files=[
                {"name": "character.md", "path": "/path/to/character.md", "size": 1024},
                {"name": "scene.md", "path": "/path/to/scene.md", "size": 2048},
            ],
        )

        output = formatter._format_bible_result(result, OutputFormat.JSON)
        assert '"bible_files"' in output
        assert "character.md" in output

    def test_format_bible_result_with_files_text(self, formatter):
        """Test formatting bible result with file list in text."""
        result = BibleReadResult(
            success=True,
            error=None,
            content=None,
            bible_files=[
                {"name": "character.md", "path": "/path/to/character.md", "size": 1024},
                {"name": "scene.md", "path": "/path/to/scene.md", "size": 2048},
            ],
        )

        output = formatter._format_bible_result(result, OutputFormat.TEXT)
        assert "Available bible files:" in output
        assert "character.md" in output
        assert "1.0 KB" in output

    def test_format_generic_data(self, formatter):
        """Test formatting generic data that doesn't match specific types."""
        data = {"custom": "data", "value": 42}
        output = formatter.format(data, OutputFormat.TEXT)
        assert "custom" in output
        assert "42" in output

    def test_format_read_result_no_scene(self, formatter):
        """Test formatting read result with no scene."""
        result = ReadSceneResult(
            success=True,
            error=None,
            scene=None,
            last_read=None,
        )

        output = formatter._format_read_result(result, OutputFormat.TEXT)
        assert output == ""

    def test_format_read_result_json_no_scene(self, formatter):
        """Test formatting read result with no scene in JSON."""
        result = ReadSceneResult(
            success=True,
            error=None,
            scene=None,
            last_read=None,
        )

        output = formatter._format_read_result(result, OutputFormat.JSON)
        assert '"scene_number": null' in output


class TestCLIHandlerExtended:
    """Extended tests for CLI handler to improve coverage."""

    @pytest.fixture
    def handler(self):
        """Create a CLI handler."""
        return CLIHandler()

    @pytest.fixture
    def mock_console(self):
        """Create a mock console."""
        return Mock(spec=Console)

    def test_handle_success_with_data_json(self, handler):
        """Test handling success with data in JSON format."""
        with patch("sys.stdout", new=StringIO()) as captured:
            handler.handle_success(
                "Operation successful",
                data={"result": "value"},
                json_output=True,
            )
            output = captured.getvalue()
            assert '"success": true' in output
            assert '"result"' in output

    def test_handle_success_text_format(self, mock_console):
        """Test handling success in text format."""
        handler = CLIHandler(console=mock_console)
        handler.handle_success("Operation successful", json_output=False)
        mock_console.print.assert_called_with("[green]Operation successful[/green]")

    def test_handle_error_validation_error(self, mock_console):
        """Test handling validation error."""
        handler = CLIHandler(console=mock_console)
        error = ValidationError("Invalid input")

        with pytest.raises(typer.Exit) as exc_info:
            handler.handle_error(error, json_output=False)

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_called_with(
            "[red]Validation Error: Invalid input[/red]"
        )

    def test_handle_error_generic_error(self, mock_console):
        """Test handling generic error."""
        handler = CLIHandler(console=mock_console)
        error = Exception("Something went wrong")

        with pytest.raises(typer.Exit) as exc_info:
            handler.handle_error(error, json_output=False, exit_code=2)

        assert exc_info.value.exit_code == 2
        mock_console.print.assert_called_with("[red]Error: Something went wrong[/red]")

    def test_handle_error_json_output(self, handler):
        """Test handling error with JSON output."""
        error = Exception("Something went wrong")

        with patch("sys.stdout", new=StringIO()) as captured:
            with pytest.raises(typer.Exit):
                handler.handle_error(error, json_output=True)
            output = captured.getvalue()
            assert '"success": false' in output
            assert "Something went wrong" in output

    def test_get_output_format_csv(self, handler):
        """Test getting CSV output format."""
        format_type = handler.get_output_format(csv=True)
        assert format_type == OutputFormat.CSV

    def test_get_output_format_markdown(self, handler):
        """Test getting Markdown output format."""
        format_type = handler.get_output_format(markdown=True)
        assert format_type == OutputFormat.MARKDOWN

    def test_read_stdin_no_input_required(self, handler, monkeypatch):
        """Test reading stdin when no input and required."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        with pytest.raises(typer.Exit) as exc_info:
            handler.read_stdin(required=True)
        assert exc_info.value.exit_code == 1

    def test_read_stdin_no_input_not_required(self, handler, monkeypatch):
        """Test reading stdin when no input and not required."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        result = handler.read_stdin(required=False)
        assert result is None

    def test_read_stdin_with_input(self, handler, monkeypatch):
        """Test reading stdin with input available."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("sys.stdin.read", lambda: "test input")

        result = handler.read_stdin(required=True)
        assert result == "test input"


class TestCLIDecoratorsExtended:
    """Extended tests for CLI decorators."""

    def test_cli_command_sync_success(self):
        """Test CLI command decorator with sync function success."""

        @cli_command()
        def test_func(value: int) -> int:
            return value * 2

        result = test_func(5)
        assert result == 10

    def test_cli_command_sync_validation_error(self):
        """Test CLI command decorator with sync function validation error."""

        @cli_command()
        def test_func(json_output: bool = False) -> None:
            raise ValidationError("Invalid input")

        with patch("scriptrag.cli.utils.cli_handler.CLIHandler.handle_error") as mock:
            test_func(json_output=True)
            mock.assert_called_once()
            error = mock.call_args[0][0]
            assert isinstance(error, ValidationError)

    def test_cli_command_sync_generic_error(self):
        """Test CLI command decorator with sync function generic error."""

        @cli_command()
        def test_func(json: bool = False) -> None:
            raise RuntimeError("Something failed")

        with patch("scriptrag.cli.utils.cli_handler.CLIHandler.handle_error") as mock:
            test_func(json=True)
            mock.assert_called_once()
            error = mock.call_args[0][0]
            assert isinstance(error, RuntimeError)

    def test_cli_command_typer_exit(self):
        """Test CLI command decorator preserves typer.Exit."""

        @cli_command()
        def test_func() -> None:
            raise typer.Exit(3)

        with pytest.raises(typer.Exit) as exc_info:
            test_func()
        assert exc_info.value.exit_code == 3

    def test_cli_command_async_function(self):
        """Test CLI command decorator with async function."""

        @cli_command(async_func=True)
        async def test_func(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 3

        result = test_func(4)
        assert result == 12

    def test_async_cli_command_decorator(self):
        """Test async_cli_command decorator."""

        @async_cli_command
        async def test_func(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 4

        result = test_func(3)
        assert result == 12

    def test_cli_command_auto_detect_async(self):
        """Test CLI command decorator auto-detecting async function."""

        @cli_command()
        async def test_func(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 5

        result = test_func(2)
        assert result == 10

    def test_cli_command_output_json_variant(self):
        """Test CLI command decorator with output_json parameter."""

        @cli_command()
        def test_func(output_json: bool = False) -> None:
            raise ValidationError("Test error")

        with patch("scriptrag.cli.utils.cli_handler.CLIHandler.handle_error") as mock:
            test_func(output_json=True)
            mock.assert_called_once()
            # Check that json_output was set to True
            assert mock.call_args[0][1] is True  # json_output parameter


class TestFileValidatorExtended:
    """Extended tests for file validator to improve coverage."""

    def test_validate_file_must_exist_missing(self, tmp_path):
        """Test validating file that must exist but doesn't."""
        validator = FileValidator(must_exist=True)
        missing_file = tmp_path / "missing.txt"

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(missing_file)
        assert "does not exist" in str(exc_info.value)

    def test_validate_file_not_required_to_exist(self, tmp_path):
        """Test validating file that doesn't need to exist."""
        validator = FileValidator(must_exist=False)
        missing_file = tmp_path / "missing.txt"

        result = validator.validate(missing_file)
        assert result == missing_file

    def test_validate_file_with_invalid_extension(self, tmp_path):
        """Test validating file with invalid extension."""
        validator = FileValidator(extensions=[".py", ".md"])
        file_path = tmp_path / "file.txt"
        file_path.touch()

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(file_path)
        assert "Invalid file extension" in str(exc_info.value)

    def test_validate_file_with_valid_extension(self, tmp_path):
        """Test validating file with valid extension."""
        validator = FileValidator(extensions=[".py", ".md"])
        file_path = tmp_path / "script.py"
        file_path.touch()

        result = validator.validate(file_path)
        assert result == file_path

    def test_validate_file_no_extension_check(self, tmp_path):
        """Test validating file with no extension restrictions."""
        validator = FileValidator(extensions=None)
        file_path = tmp_path / "file.whatever"
        file_path.touch()

        result = validator.validate(file_path)
        assert result == file_path

    def test_validate_not_a_file(self, tmp_path):
        """Test validating path that is not a file."""
        validator = FileValidator(must_be_file=True)
        dir_path = tmp_path / "directory"
        dir_path.mkdir()

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(dir_path)
        assert "not a file" in str(exc_info.value)


class TestOutputFormatterBase:
    """Tests for base output formatter to improve coverage."""

    class ConcreteFormatter(OutputFormatter):
        """Concrete implementation for testing."""

        def format(self, data, format_type: OutputFormat = OutputFormat.TEXT) -> str:
            return str(data)

    def test_format_not_implemented(self):
        """Test that format method must be implemented."""
        # OutputFormatter is abstract, so we test with a concrete implementation
        formatter = self.ConcreteFormatter()
        result = formatter.format("data", OutputFormat.TEXT)
        assert result == "data"

    def test_print_method(self):
        """Test print method with different formats."""
        formatter = self.ConcreteFormatter()
        with patch.object(formatter.console, "print") as mock_print:
            formatter.print("test data", OutputFormat.TEXT)
            mock_print.assert_called_once_with("test data")

    def test_print_method_json(self):
        """Test print method with JSON format."""
        formatter = self.ConcreteFormatter()
        with patch.object(formatter.console, "print_json") as mock_print_json:
            formatter.print('{"key": "value"}', OutputFormat.JSON)
            mock_print_json.assert_called_once()

    def test_format_error_string(self):
        """Test formatting error from string."""
        formatter = self.ConcreteFormatter()
        result = formatter.format_error("Something went wrong")
        assert "Error:" in result
        assert "Something went wrong" in result
        assert "[red]" in result

    def test_format_error_exception(self):
        """Test formatting error from exception."""
        formatter = self.ConcreteFormatter()
        error = ValueError("Invalid value")
        result = formatter.format_error(error)
        assert "Error:" in result
        assert "Invalid value" in result
        assert "[red]" in result

    def test_print_error(self):
        """Test printing error."""
        formatter = self.ConcreteFormatter()
        with patch.object(formatter.console, "print") as mock_print:
            formatter.print_error("Test error")
            mock_print.assert_called_once()
            assert "Error:" in mock_print.call_args[0][0]
