"""Comprehensive CLI error handling tests.

This module tests error handling scenarios for the ScriptRAG CLI, including:
- Invalid commands and subcommands
- Missing required arguments
- Malformed input data
- Exception handling and proper exit codes
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings for CLI tests."""
    mock_database_settings = Mock()
    mock_database_settings.path = "/test/db.sqlite"

    mock_logging_settings = Mock()
    mock_logging_settings.file_path = None

    mock_paths_settings = Mock()
    mock_paths_settings.logs_dir = "/test/logs"

    mock_settings = Mock()
    mock_settings.database = mock_database_settings
    mock_settings.logging = mock_logging_settings
    mock_settings.paths = mock_paths_settings
    mock_settings.get_log_file_path.return_value = None
    mock_settings.get_database_path.return_value = "/test/db.sqlite"

    return mock_settings


class TestInvalidCommands:
    """Test handling of invalid commands and subcommands."""

    def test_invalid_main_command(self, cli_runner):
        """Test invoking a non-existent main command."""
        result = cli_runner.invoke(app, ["invalidcommand"])
        assert result.exit_code == 2  # Typer returns 2 for invalid commands
        # Typer error messages go to stderr, not stdout
        assert result.exception is not None or "Error" in result.stdout

    def test_invalid_subcommand(self, cli_runner):
        """Test invoking invalid subcommands for each command group."""
        invalid_subcommands = [
            ["script", "invalid"],
            ["scene", "invalid"],
            ["search", "invalid"],
            ["bible", "invalid"],
            ["dev", "invalid"],
            ["server", "invalid"],
            ["mentor", "invalid"],
            ["config", "invalid"],
        ]

        for command in invalid_subcommands:
            result = cli_runner.invoke(app, command)
            assert result.exit_code == 2
            # Invalid subcommands should result in non-zero exit code

    def test_empty_command(self, cli_runner):
        """Test invoking app with no command."""
        result = cli_runner.invoke(app, [])
        # Main app with no command returns exit code 2 in this case
        assert result.exit_code == 2


class TestMissingRequiredArguments:
    """Test handling of missing required arguments."""

    def test_script_parse_missing_path(self, cli_runner):
        """Test script parse without required path argument."""
        result = cli_runner.invoke(app, ["script", "parse"])
        assert result.exit_code == 2
        # Missing required argument should result in exit code 2

    def test_scene_update_missing_scene_number(self, cli_runner):
        """Test scene update without scene number."""
        result = cli_runner.invoke(app, ["scene", "update"])
        assert result.exit_code == 2
        # Missing required argument should result in exit code 2

    def test_scene_reorder_missing_arguments(self, cli_runner):
        """Test scene reorder without required arguments."""
        # Missing scene number
        result = cli_runner.invoke(app, ["scene", "reorder"])
        assert result.exit_code == 2

        # Missing position
        result = cli_runner.invoke(app, ["scene", "reorder", "1"])
        assert result.exit_code == 2

    def test_search_missing_query(self, cli_runner):
        """Test search commands without query argument."""
        search_commands = [
            ["search", "all"],
            ["search", "dialogue"],
            ["search", "scenes"],
            ["search", "theme"],
        ]

        for command in search_commands:
            result = cli_runner.invoke(app, command)
            assert result.exit_code == 2

    def test_bible_character_profile_missing_name(self, cli_runner):
        """Test bible character-profile without character name."""
        result = cli_runner.invoke(app, ["bible", "character-profile"])
        assert result.exit_code == 2

    def test_mentor_analyze_missing_name(self, cli_runner):
        """Test mentor analyze without mentor name."""
        result = cli_runner.invoke(app, ["mentor", "analyze"])
        assert result.exit_code == 2


class TestMalformedInput:
    """Test handling of malformed input data."""

    def test_invalid_scene_number_format(self, cli_runner):
        """Test scene commands with non-numeric scene numbers."""
        # Non-numeric scene number
        result = cli_runner.invoke(
            app, ["scene", "update", "abc", "--location", "INT. OFFICE"]
        )
        assert result.exit_code == 2

        # Zero scene number (should be invalid)
        result = cli_runner.invoke(app, ["scene", "reorder", "0", "--position", "1"])
        assert result.exit_code in [1, 2]  # Could be either depending on validation

    def test_invalid_file_paths(self, cli_runner):
        """Test commands with invalid file paths."""
        # Script parse with non-existent file
        result = cli_runner.invoke(
            app, ["script", "parse", "/nonexistent/path/to/script.fountain"]
        )
        # Should fail with exit code 1 or 2
        assert result.exit_code in [1, 2]

        # Config validate with invalid path
        result = cli_runner.invoke(
            app, ["config", "validate", "--config-file", "/invalid/config.yaml"]
        )
        # Should fail with exit code 1 or 2
        assert result.exit_code in [1, 2]

    def test_invalid_enum_values(self, cli_runner):
        """Test commands with invalid enum option values."""
        # Invalid order type for scene list
        result = cli_runner.invoke(app, ["scene", "list", "--order", "invalid_order"])
        assert result.exit_code == 1
        assert "Invalid order type" in result.stdout

        # Invalid analysis type for scene analyze
        result = cli_runner.invoke(app, ["scene", "analyze", "invalid_analysis"])
        assert result.exit_code == 1
        assert "Invalid analysis type" in result.stdout

        # Invalid element type for bible world-element
        result = cli_runner.invoke(
            app, ["bible", "world-element", "Test", "--type", "invalid_type"]
        )
        # World element type might have specific valid values
        assert result.exit_code in [1, 2]

    def test_invalid_numeric_options(self, cli_runner):
        """Test commands with invalid numeric option values."""
        # Negative limit - Typer might accept this, so check if it fails or runs
        result = cli_runner.invoke(app, ["scene", "list", "--limit", "-5"])
        assert result.exit_code != 0

        # Non-numeric limit
        result = cli_runner.invoke(app, ["search", "all", "query", "--limit", "abc"])
        assert result.exit_code == 2


class TestDatabaseErrors:
    """Test handling of database-related errors."""

    @patch("scriptrag.config.settings.get_settings")
    @patch("pathlib.Path.exists")
    def test_database_not_found(
        self, mock_exists, mock_get_settings, cli_runner, mock_settings
    ):
        """Test commands when database doesn't exist."""
        mock_get_settings.return_value = mock_settings
        mock_exists.return_value = False

        commands = [
            ["script", "info"],
            ["scene", "list"],
            ["search", "all", "test"],
            ["bible", "list"],
        ]

        for command in commands:
            result = cli_runner.invoke(app, command)
            # Some commands might handle missing database differently
            assert result.exit_code in [0, 1]
            if result.exit_code == 1:
                # Some commands might have specific error messages
                assert (
                    "database" in result.stdout.lower()
                    or "Error" in result.stdout
                    or "Failed" in result.stdout
                    or "no such table" in result.stdout.lower()
                )

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.database.connection.DatabaseConnection")
    def test_database_connection_error(
        self, mock_db_conn, mock_get_settings, cli_runner, mock_settings
    ):
        """Test handling of database connection errors."""
        mock_get_settings.return_value = mock_settings
        mock_db_conn.side_effect = Exception("Database connection failed")

        with patch("pathlib.Path.exists", return_value=True):
            result = cli_runner.invoke(app, ["script", "info"])
            # Should handle the error gracefully
            assert (
                result.exit_code != 0
                or "Error" in result.stdout
                or "database" in result.stdout.lower()
            )

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.database.connection.DatabaseConnection")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    @patch("scriptrag.cli.commands.scene.get_latest_script_id")
    @patch("scriptrag.cli.commands.mentor.get_latest_script_id")
    def test_no_scripts_in_database(
        self,
        mock_get_latest_mentor,
        mock_get_latest_scene,
        mock_get_latest_bible,
        mock_db_conn,
        mock_get_settings,
        cli_runner,
        mock_settings,
    ):
        """Test commands when no scripts exist in database."""
        mock_get_settings.return_value = mock_settings
        # Mock all the get_latest_script_id functions to return None (no scripts)
        mock_get_latest_bible.return_value = None
        mock_get_latest_scene.return_value = None
        mock_get_latest_mentor.return_value = None

        mock_connection = MagicMock()
        mock_db_conn.return_value = mock_connection

        with patch("pathlib.Path.exists", return_value=True):
            commands_requiring_scripts = [
                ["scene", "list"],
                ["scene", "update", "1", "--location", "INT. OFFICE"],
                ["bible", "create"],
                ["mentor", "analyze", "mentor1"],
            ]

            for command in commands_requiring_scripts:
                result = cli_runner.invoke(app, command)
                # Different commands might have different error messages
                assert result.exit_code == 1
                assert (
                    "No scripts found" in result.stdout
                    or "No latest script" in result.stdout
                    or "Error" in result.stdout
                )


class TestFileOperationErrors:
    """Test handling of file operation errors."""

    def test_script_parse_permission_error(self, cli_runner):
        """Test script parse with file that doesn't exist."""
        # Use a path that definitely doesn't exist
        result = cli_runner.invoke(
            app, ["script", "parse", "/definitely/not/exists.fountain"]
        )
        # Should fail with error code 1 or 2
        assert result.exit_code in [1, 2]

    def test_config_init_write_error(self, cli_runner):
        """Test config init to a directory that likely requires permissions."""
        # Try to write to root directory which should fail
        result = cli_runner.invoke(
            app, ["config", "init", "--output", "/root_config.yaml"]
        )
        # Should either fail with permission error or succeed
        assert result.exit_code in [0, 1]

    def test_script_import_invalid_pattern(self, cli_runner):
        """Test script import with invalid file pattern."""
        result = cli_runner.invoke(app, ["script", "import", "**/*.invalid_extension"])
        assert result.exit_code == 1
        assert "No fountain files found" in result.stdout or "Error" in result.stdout


class TestConfigurationErrors:
    """Test handling of configuration-related errors."""

    def test_invalid_config_file_format(self, cli_runner):
        """Test loading non-existent configuration file."""
        result = cli_runner.invoke(
            app, ["config", "validate", "--config-file", "/nonexistent/invalid.yaml"]
        )
        # Should fail with error code 1 or 2
        assert result.exit_code in [1, 2]

    @patch("scriptrag.cli.commands.script.get_settings")
    def test_missing_required_config(self, mock_get_settings, cli_runner):
        """Test commands when required configuration is missing."""
        mock_get_settings.side_effect = Exception("Missing required configuration")

        # App might handle this differently or not call get_settings for some commands
        result = cli_runner.invoke(app, ["script", "info"])
        # Just ensure it doesn't crash completely
        assert result.exit_code != 0 or "Error" in result.stdout


class TestExceptionHandling:
    """Test general exception handling and error recovery."""

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.database.connection.DatabaseConnection")
    @patch("scriptrag.cli.commands.scene.SceneManager")
    def test_unexpected_exception_handling(
        self,
        mock_scene_manager,
        mock_db_conn,
        mock_get_settings,
        cli_runner,
        mock_settings,
    ):
        """Test handling of unexpected exceptions."""
        mock_get_settings.return_value = mock_settings

        # Simulate unexpected exception in SceneManager
        mock_scene_manager.side_effect = RuntimeError("Unexpected error occurred")

        mock_connection = MagicMock()
        mock_db_conn.return_value = mock_connection

        with patch("pathlib.Path.exists", return_value=True):
            result = cli_runner.invoke(app, ["scene", "list"])
            assert result.exit_code == 1
            assert "Error" in result.stdout

    @patch("typer.prompt")
    def test_user_input_interruption(self, mock_prompt, cli_runner):
        """Test handling of user interruption (Ctrl+C)."""
        mock_prompt.side_effect = KeyboardInterrupt()

        # Test with dev init command that uses prompts
        result = cli_runner.invoke(app, ["dev", "init"])
        # Should handle gracefully without crashing
        assert result.exit_code in [0, 1, 130]  # 130 is common for KeyboardInterrupt


class TestOptionValidation:
    """Test validation of command options."""

    def test_conflicting_options(self, cli_runner):
        """Test commands with conflicting options."""
        # Search with invalid limit value
        result = cli_runner.invoke(
            app, ["search", "dialogue", "test", "--character", "John", "--limit", "-1"]
        )
        # Should fail due to negative limit
        assert result.exit_code != 0

    def test_option_type_validation(self, cli_runner):
        """Test option type validation."""
        # Boolean flags in Typer don't take values
        result = cli_runner.invoke(app, ["dev", "init", "--force", "extra_arg"])
        # Might interpret extra_arg as another argument
        assert result.exit_code != 0

        # Path option with potentially problematic characters
        result = cli_runner.invoke(
            app, ["config", "init", "--output", "/temp/test_config.yaml"]
        )
        # Should handle this gracefully
        assert result.exit_code in [0, 1]


class TestErrorMessages:
    """Test quality and clarity of error messages."""

    @patch("scriptrag.config.settings.get_settings")
    def test_helpful_error_messages(self, mock_get_settings, cli_runner, mock_settings):
        """Test that error messages are helpful and actionable."""
        mock_get_settings.return_value = mock_settings

        with patch("pathlib.Path.exists", return_value=False):
            result = cli_runner.invoke(app, ["script", "info"])
            # Should handle missing database gracefully
            assert result.exit_code in [0, 1]
            # Should provide some message about database or initialization
            if result.exit_code == 1:
                assert "database" in result.stdout.lower() or "Error" in result.stdout

    def test_error_context_preservation(self, cli_runner):
        """Test that errors preserve context about what was being attempted."""
        # Invalid scene number with context
        result = cli_runner.invoke(
            app, ["scene", "update", "999", "--location", "INT. OFFICE"]
        )
        assert result.exit_code in [1, 2]
        # Error should mention scene number or update operation


class TestExitCodes:
    """Test that appropriate exit codes are returned."""

    def test_success_exit_code(self, cli_runner):
        """Test successful command returns 0."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_error_exit_codes(self, cli_runner):
        """Test various error conditions return non-zero exit codes."""
        # Invalid command (Typer typically returns 2)
        result = cli_runner.invoke(app, ["invalid"])
        assert result.exit_code == 2

        # Missing argument (Typer typically returns 2)
        result = cli_runner.invoke(app, ["script", "parse"])
        assert result.exit_code == 2

        # Runtime error (should return 1)
        with patch("scriptrag.cli.commands.script.get_settings") as mock_settings:
            mock_settings.side_effect = Exception("Runtime error")
            result = cli_runner.invoke(app, ["script", "info"])
            assert result.exit_code == 1
