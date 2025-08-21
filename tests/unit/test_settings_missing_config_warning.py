"""Test that missing config files emit a warning."""

import logging

from scriptrag.config import ScriptRAGSettings, get_logger


class TestMissingConfigWarning:
    """Test missing config file warning behavior."""

    def setup_method(self):
        """Ensure logger is properly initialized before each test."""
        # Force logger initialization to ensure caplog can capture structlog messages
        # This ensures the logging configuration is applied before tests run
        get_logger(__name__)

        # Ensure the specific logger used by settings is set to the right level
        settings_logger = logging.getLogger("scriptrag.config.settings")
        settings_logger.setLevel(logging.WARNING)

    def test_missing_config_file_logs_warning(self, tmp_path, caplog):
        """Test that missing config files emit a warning log."""
        missing_file = tmp_path / "missing.yml"

        # Ensure the log level captures warnings
        with caplog.at_level(logging.WARNING):
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[missing_file],
            )

        # Should use defaults
        assert settings.app_name == "scriptrag"

        # Check that a warning was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "Configuration file not found" in caplog.records[0].message
        # Check the extra field via __dict__ or the message itself
        assert str(missing_file) in caplog.text

    def test_multiple_missing_files_log_multiple_warnings(self, tmp_path, caplog):
        """Test that multiple missing files each emit their own warning."""
        missing_file1 = tmp_path / "missing1.yml"
        missing_file2 = tmp_path / "missing2.json"
        missing_file3 = tmp_path / "missing3.toml"

        with caplog.at_level(logging.WARNING):
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[missing_file1, missing_file2, missing_file3],
            )

        # Should use defaults
        assert settings.app_name == "scriptrag"

        # Check that warnings were logged for each missing file
        assert len(caplog.records) == 3

        # Check each file is mentioned in the logs
        assert str(missing_file1) in caplog.text
        assert str(missing_file2) in caplog.text
        assert str(missing_file3) in caplog.text

        for record in caplog.records:
            assert record.levelname == "WARNING"
            assert "Configuration file not found" in record.message

    def test_mix_of_existing_and_missing_files(self, tmp_path, caplog):
        """Test behavior with mix of existing and missing config files."""
        # Create one existing file
        existing_file = tmp_path / "existing.yml"
        existing_file.write_text("""
app_name: test-app
database_timeout: 45.0
log_level: DEBUG
""")

        missing_file = tmp_path / "missing.yml"

        with caplog.at_level(logging.WARNING):
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[existing_file, missing_file],
            )

        # Should use values from existing file
        assert settings.app_name == "test-app"
        assert settings.database_timeout == 45.0
        assert settings.log_level == "DEBUG"

        # Check that only one warning was logged (for the missing file)
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "Configuration file not found" in caplog.records[0].message
        assert str(missing_file) in caplog.text

    def test_missing_file_with_higher_precedence_sources(self, tmp_path, caplog):
        """Test that CLI args still override even with missing config files."""
        missing_file = tmp_path / "missing.yml"

        cli_args = {
            "app_name": "cli-app",
            "database_timeout": 60.0,
        }

        with caplog.at_level(logging.WARNING):
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[missing_file],
                cli_args=cli_args,
            )

        # CLI args should take precedence
        assert settings.app_name == "cli-app"
        assert settings.database_timeout == 60.0

        # Warning should still be logged for missing file
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "Configuration file not found" in caplog.records[0].message

    def test_no_warning_when_no_config_files(self, caplog):
        """Test that no warnings are logged when config_files is None or empty."""
        with caplog.at_level(logging.WARNING):
            # Test with None
            settings1 = ScriptRAGSettings.from_multiple_sources(
                config_files=None,
            )

            # Test with empty list
            settings2 = ScriptRAGSettings.from_multiple_sources(
                config_files=[],
            )

        # Should use defaults
        assert settings1.app_name == "scriptrag"
        assert settings2.app_name == "scriptrag"

        # No warnings should be logged
        assert len(caplog.records) == 0
