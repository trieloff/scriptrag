"""Test case-insensitive logging configuration settings."""

import json
import logging

import pytest
import yaml

from scriptrag.config import get_settings, set_settings
from scriptrag.config.logging import configure_logging
from scriptrag.config.settings import ScriptRAGSettings


class TestCaseInsensitiveLoggingSettings:
    """Test that logging settings handle case-insensitive input correctly."""

    @pytest.fixture(autouse=True)
    def reset_settings(self):
        """Reset settings before each test."""
        # Store original settings
        original = get_settings()
        yield
        # Restore original settings
        set_settings(original)

    def test_log_level_lowercase_normalization(self):
        """Test that lowercase log levels are normalized to uppercase."""
        settings = ScriptRAGSettings(log_level="debug")
        assert settings.log_level == "DEBUG"

        settings = ScriptRAGSettings(log_level="info")
        assert settings.log_level == "INFO"

        settings = ScriptRAGSettings(log_level="warning")
        assert settings.log_level == "WARNING"

        settings = ScriptRAGSettings(log_level="error")
        assert settings.log_level == "ERROR"

        settings = ScriptRAGSettings(log_level="critical")
        assert settings.log_level == "CRITICAL"

    def test_log_level_mixed_case_normalization(self):
        """Test that mixed case log levels are normalized to uppercase."""
        settings = ScriptRAGSettings(log_level="Debug")
        assert settings.log_level == "DEBUG"

        settings = ScriptRAGSettings(log_level="InFo")
        assert settings.log_level == "INFO"

        settings = ScriptRAGSettings(log_level="WaRnInG")
        assert settings.log_level == "WARNING"

        settings = ScriptRAGSettings(log_level="ErRoR")
        assert settings.log_level == "ERROR"

        settings = ScriptRAGSettings(log_level="CrItIcAl")
        assert settings.log_level == "CRITICAL"

    def test_log_level_uppercase_unchanged(self):
        """Test that uppercase log levels remain unchanged."""
        settings = ScriptRAGSettings(log_level="DEBUG")
        assert settings.log_level == "DEBUG"

        settings = ScriptRAGSettings(log_level="INFO")
        assert settings.log_level == "INFO"

        settings = ScriptRAGSettings(log_level="WARNING")
        assert settings.log_level == "WARNING"

        settings = ScriptRAGSettings(log_level="ERROR")
        assert settings.log_level == "ERROR"

        settings = ScriptRAGSettings(log_level="CRITICAL")
        assert settings.log_level == "CRITICAL"

    def test_log_format_lowercase_normalization(self):
        """Test that uppercase log formats are normalized to lowercase."""
        settings = ScriptRAGSettings(log_format="CONSOLE")
        assert settings.log_format == "console"

        settings = ScriptRAGSettings(log_format="JSON")
        assert settings.log_format == "json"

        settings = ScriptRAGSettings(log_format="STRUCTURED")
        assert settings.log_format == "structured"

    def test_log_format_mixed_case_normalization(self):
        """Test that mixed case log formats are normalized to lowercase."""
        settings = ScriptRAGSettings(log_format="Console")
        assert settings.log_format == "console"

        settings = ScriptRAGSettings(log_format="Json")
        assert settings.log_format == "json"

        settings = ScriptRAGSettings(log_format="StRuCtUrEd")
        assert settings.log_format == "structured"

    def test_log_format_lowercase_unchanged(self):
        """Test that lowercase log formats remain unchanged."""
        settings = ScriptRAGSettings(log_format="console")
        assert settings.log_format == "console"

        settings = ScriptRAGSettings(log_format="json")
        assert settings.log_format == "json"

        settings = ScriptRAGSettings(log_format="structured")
        assert settings.log_format == "structured"

    def test_invalid_log_level_still_rejected(self):
        """Test that invalid log levels are still rejected after normalization."""
        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_level="invalid")

        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_level="INVALID")

        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_level="trace")

    def test_invalid_log_format_still_rejected(self):
        """Test that invalid log formats are still rejected after normalization."""
        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_format="invalid")

        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_format="INVALID")

        with pytest.raises(ValueError, match="pattern"):
            ScriptRAGSettings(log_format="xml")

    def test_configure_logging_with_lowercase_level(self):
        """Test that configure_logging works with normalized lowercase input."""
        settings = ScriptRAGSettings(log_level="debug")
        configure_logging(settings)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_with_mixed_case_level(self):
        """Test that configure_logging works with mixed case input."""
        settings = ScriptRAGSettings(log_level="WaRnInG")
        configure_logging(settings)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_from_env_with_lowercase_log_level(self, monkeypatch):
        """Test loading settings from environment with lowercase log level."""
        monkeypatch.setenv("SCRIPTRAG_LOG_LEVEL", "debug")
        monkeypatch.setenv("SCRIPTRAG_LOG_FORMAT", "JSON")

        settings = ScriptRAGSettings.from_env()
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "json"

    def test_from_file_yaml_with_mixed_case(self, tmp_path):
        """Test loading settings from YAML with mixed case log settings."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "log_level": "debug",
                    "log_format": "JSON",
                    "database_path": str(tmp_path / "test.db"),
                }
            )
        )

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "json"

    def test_from_file_json_with_mixed_case(self, tmp_path):
        """Test loading settings from JSON with mixed case log settings."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "log_level": "InFo",
                    "log_format": "Structured",
                    "database_path": str(tmp_path / "test.db"),
                }
            )
        )

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.log_level == "INFO"
        assert settings.log_format == "structured"

    def test_from_file_toml_with_lowercase(self, tmp_path):
        """Test loading settings from TOML with lowercase log settings."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
log_level = "error"
log_format = "console"
database_path = "/tmp/test.db"
"""
        )

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.log_level == "ERROR"
        assert settings.log_format == "console"

    def test_from_multiple_sources_with_case_variations(self, tmp_path, monkeypatch):
        """Test loading from multiple sources with different case variations."""
        # Config file with lowercase
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "log_level": "info",
                    "log_format": "console",
                    "database_path": str(tmp_path / "config.db"),
                }
            )
        )

        # Environment variable with mixed case (lower precedence than config file)
        monkeypatch.setenv("SCRIPTRAG_LOG_LEVEL", "Warning")
        monkeypatch.setenv("SCRIPTRAG_LOG_FORMAT", "STRUCTURED")

        # CLI args with uppercase (highest precedence)
        cli_args = {"log_format": "JSON"}

        settings = ScriptRAGSettings.from_multiple_sources(
            config_files=[config_file],
            cli_args=cli_args,
        )

        # Config file overrides environment variable for log_level
        assert settings.log_level == "INFO"
        # CLI args should override everything for log_format
        assert settings.log_format == "json"

    def test_all_log_levels_work_after_normalization(self):
        """Test that all valid log levels work after normalization."""
        test_cases = [
            ("debug", logging.DEBUG),
            ("info", logging.INFO),
            ("warning", logging.WARNING),
            ("error", logging.ERROR),
            ("critical", logging.CRITICAL),
            ("Debug", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WaRnInG", logging.WARNING),
            ("ErRoR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for level_str, expected_level in test_cases:
            settings = ScriptRAGSettings(log_level=level_str)
            configure_logging(settings)
            root_logger = logging.getLogger()
            assert root_logger.level == expected_level, (
                f"Failed for log_level={level_str}"
            )

    def test_all_log_formats_work_after_normalization(self):
        """Test that all valid log formats work after normalization."""
        test_cases = [
            "console",
            "json",
            "structured",
            "Console",
            "JSON",
            "STRUCTURED",
            "CoNsOlE",
            "JsOn",
            "StRuCtUrEd",
        ]

        for format_str in test_cases:
            settings = ScriptRAGSettings(log_format=format_str)
            # Should not raise any errors
            configure_logging(settings)
            # Verify the normalized value
            assert settings.log_format in ["console", "json", "structured"]

    def test_backwards_compatibility(self):
        """Test that existing code with uppercase values still works."""
        # This ensures we don't break existing configurations
        settings = ScriptRAGSettings(
            log_level="DEBUG",
            log_format="console",
        )
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "console"

        configure_logging(settings)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
