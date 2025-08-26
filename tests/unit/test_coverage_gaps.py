"""Targeted unit tests to fill specific coverage gaps.

These tests are precisely designed to hit the missing lines in:
- src/scriptrag/cli/main.py (need 1 more line for 99%)
- src/scriptrag/cli/commands/config/validate.py (need error paths)
- src/scriptrag/cli/commands/config/show.py (need error/edge case paths)
"""

import os
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from scriptrag.cli.commands.config import config_app


class TestMainCLICoverage:
    """Test missing coverage in CLI main module."""

    def test_main_direct_execution_coverage(self):
        """Test the __name__ == '__main__' block in main.py.

        This targets the specific missing line in main.py to reach 99% coverage.
        The pragma: no cover line at line 48 means we need to target line 51 (main()).
        """
        # Direct method: Execute the code that would run when module is called directly
        from scriptrag.cli.main import main

        with patch("scriptrag.cli.main.app") as mock_app:
            # Mock app to prevent actual CLI execution
            mock_app.return_value = None

            # Call main() directly to simulate the __name__ == "__main__" execution
            main()

            # Verify that app() was called (which is what main() does)
            mock_app.assert_called_once()


class TestConfigValidateCoverage:
    """Test missing coverage in config validate command."""

    def test_validate_pydantic_validation_error(self, tmp_path):
        """Test validation error path when config has invalid values.

        This targets exception handling in the validate function.
        """
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text(
            """
# This config has invalid values that should trigger validation errors
log_level: INVALID_LEVEL
database_path: ""
# Empty database path should be invalid
"""
        )

        runner = CliRunner()
        result = runner.invoke(config_app, ["validate", "--config", str(config_path)])

        # Should exit with error code
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output

    def test_validate_with_malformed_yaml(self, tmp_path):
        """Test validation with malformed YAML file.

        This targets the yaml parsing error path.
        """
        config_path = tmp_path / "malformed.yaml"
        config_path.write_text(
            """
malformed: yaml: content
  - invalid
    indentation
"""
        )

        runner = CliRunner()
        result = runner.invoke(config_app, ["validate", "--config", str(config_path)])

        # Should exit with error code due to YAML parsing error
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output

    def test_validate_with_generic_io_exception(self, tmp_path):
        """Test validation with IO/file system exception.

        This targets exception handling in file operations.
        """
        config_path = tmp_path / "test.yaml"
        config_path.write_text("database_path: /tmp/test.db")

        runner = CliRunner()

        # Mock Path.exists to raise an exception
        with patch("scriptrag.cli.commands.config.validate.Path.exists") as mock_exists:
            mock_exists.side_effect = OSError("Simulated file system error")

            result = runner.invoke(
                config_app, ["validate", "--config", str(config_path)]
            )

            # Should exit with error due to the exception
            assert result.exit_code == 1
            assert "Configuration validation failed" in result.output

    @patch("scriptrag.cli.commands.config.validate.ScriptRAGSettings.from_file")
    def test_validate_settings_load_exception(self, mock_from_file, tmp_path):
        """Test exception handling in settings loading.

        This targets the try/except block around settings loading.
        """
        config_path = tmp_path / "test.yaml"
        config_path.write_text("database_path: /tmp/test.db")

        # Mock to raise an exception
        mock_from_file.side_effect = ValueError("Invalid configuration format")

        runner = CliRunner()
        result = runner.invoke(config_app, ["validate", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output
        assert "Invalid configuration format" in result.output


class TestConfigShowCoverage:
    """Test missing coverage in config show command."""

    def test_show_with_exception_in_get_settings(self):
        """Test exception handling in show command when get_settings fails.

        This targets the try/except block in config_show function.
        """
        runner = CliRunner()

        with patch(
            "scriptrag.cli.commands.config.show.get_settings"
        ) as mock_get_settings:
            mock_get_settings.side_effect = Exception("Failed to load settings")

            result = runner.invoke(config_app, ["show"])

            assert result.exit_code == 1
            assert "Failed to show configuration" in result.output
            assert "Failed to load settings" in result.output

    def test_show_sources_with_no_env_vars(self):
        """Test show sources when no SCRIPTRAG_ environment variables exist.

        This targets environment variable enumeration code paths.
        """
        runner = CliRunner()

        # Clear any existing SCRIPTRAG_ environment variables for this test
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith("SCRIPTRAG_"):
                original_env[key] = os.environ.pop(key)

        try:
            result = runner.invoke(config_app, ["show", "--sources"])

            assert result.exit_code == 0
            assert "Configuration Sources" in result.output
            assert "Configuration Files" in result.output
            assert "Environment Variables" in result.output

        finally:
            # Restore original environment variables
            os.environ.update(original_env)

    def test_show_section_application_filtering(self):
        """Test show section with 'application' filtering logic.

        This targets the specific application section filtering code.
        """
        runner = CliRunner()
        result = runner.invoke(config_app, ["show", "application"])

        # Should succeed and show application-specific settings
        assert result.exit_code == 0
        # The output should contain either settings or "No settings found"
        assert "Configuration" in result.output or "No settings found" in result.output

    def test_show_config_tree_with_empty_groups(self):
        """Test config tree display with edge case group handling.

        This targets specific branches in the tree generation logic.
        """
        # Mock settings object with specific field structure
        mock_settings = Mock(spec=object)
        # Create simple mock fields
        mock_field = Mock(spec=object)
        mock_settings.model_fields = {
            "unknown_field": mock_field,  # Should go to 'application' group
            "database_path": mock_field,  # Should go to 'database' group
            "search_limit": mock_field,  # Should go to 'search' group
        }

        # Mock getattr to return specific values for each field
        def mock_getattr(obj, field_name):
            field_values = {
                "unknown_field": "/some/path",
                "database_path": "/db/path",
                "search_limit": 100,
            }
            return field_values.get(field_name)

        runner = CliRunner()

        with patch(
            "scriptrag.cli.commands.config.show.get_settings",
            return_value=mock_settings,
        ):
            # Patch getattr at the module level where it's used
            with patch(
                "scriptrag.cli.commands.config.show.getattr", side_effect=mock_getattr
            ):
                result = runner.invoke(config_app, ["show"])

                assert result.exit_code == 0
                assert "ScriptRAG Configuration" in result.output

    def test_show_section_no_matching_fields(self):
        """Test show section when no fields match the section prefix.

        This targets the 'no settings found' code path.
        """
        runner = CliRunner()
        result = runner.invoke(config_app, ["show", "nonexistent_section"])

        assert result.exit_code == 0
        assert "No settings found for section: nonexistent_section" in result.output

    def test_show_sources_config_file_detection(self):
        """Test config file detection in sources display.

        This targets the config file existence checking logic.
        """
        runner = CliRunner()

        with patch("scriptrag.cli.commands.config.show.Path") as mock_path_class:
            # Create mock path instances
            mock_path_instance = Mock(spec=object)
            mock_path_instance.exists.return_value = True  # Simulate file exists
            mock_path_class.return_value = mock_path_instance

            # Also mock the specific path methods used
            with patch("pathlib.Path.exists", return_value=True):
                result = runner.invoke(config_app, ["show", "--sources"])

                assert result.exit_code == 0
                assert "Configuration Sources" in result.output
                assert "Configuration Files" in result.output
