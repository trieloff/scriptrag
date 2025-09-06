"""Tests for logging configuration using public API only.

This test module ensures we use only public logging module APIs
and avoid accessing private attributes like _nameToLevel.
"""

import logging
import sys
from unittest.mock import patch

import pytest
import structlog

from scriptrag.config import ScriptRAGSettings, configure_logging


@pytest.fixture(autouse=True)
def clean_logging():
    """Reset logging configuration before and after each test."""
    # Reset structlog configuration
    structlog.reset_defaults()

    # Clear all handlers from root logger and reset level
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.WARNING)

    yield

    # Clean up again
    structlog.reset_defaults()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.WARNING)


class TestLoggingPublicAPI:
    """Test that logging configuration uses only public APIs."""

    def test_get_level_names_mapping_is_public_api(self):
        """Verify that getLevelNamesMapping is a public API in Python 3.11+."""
        # This should exist in Python 3.11+
        assert hasattr(logging, "getLevelNamesMapping")

        # It should return a dict
        level_names = logging.getLevelNamesMapping()
        assert isinstance(level_names, dict)

        # It should contain standard levels
        assert "DEBUG" in level_names
        assert "INFO" in level_names
        assert "WARNING" in level_names
        assert "ERROR" in level_names
        assert "CRITICAL" in level_names

    def test_invalid_log_level_uses_public_api(self):
        """Test that invalid log level error uses public API for level names."""
        # Create settings with invalid log level bypassing validation
        settings = ScriptRAGSettings.__new__(ScriptRAGSettings)
        object.__setattr__(settings, "log_level", "FAKE_LEVEL")
        object.__setattr__(settings, "log_format", "console")
        object.__setattr__(settings, "log_file", None)
        object.__setattr__(settings, "debug", False)

        with pytest.raises(ValueError) as exc_info:
            configure_logging(settings)

        error_msg = str(exc_info.value)

        # Should contain the invalid level
        assert "Invalid log level 'FAKE_LEVEL'" in error_msg
        assert "Valid levels are:" in error_msg

        # Should list all valid levels from public API
        public_levels = logging.getLevelNamesMapping()
        for level_name in public_levels:
            if not level_name.startswith("_"):
                assert level_name in error_msg

    def test_valid_levels_sorted_correctly(self):
        """Test that valid levels are listed in sorted order in error messages."""
        settings = ScriptRAGSettings.__new__(ScriptRAGSettings)
        object.__setattr__(settings, "log_level", "INVALID")
        object.__setattr__(settings, "log_format", "console")
        object.__setattr__(settings, "log_file", None)
        object.__setattr__(settings, "debug", False)

        with pytest.raises(ValueError) as exc_info:
            configure_logging(settings)

        error_msg = str(exc_info.value)

        # Extract the levels from the error message
        # Expected format: "Valid levels are: CRITICAL, DEBUG, ERROR, ..."
        levels_part = error_msg.split("Valid levels are: ")[1]
        listed_levels = [level.strip() for level in levels_part.split(",")]

        # They should be in alphabetical order
        assert listed_levels == sorted(listed_levels)

    def test_no_private_api_access_in_logging_module(self):
        """Ensure our logging module doesn't access private _nameToLevel."""
        # Read the logging.py module to check
        import inspect

        import scriptrag.config.logging as logging_module

        # Get the source code
        source = inspect.getsource(logging_module)

        # Should not contain references to private _nameToLevel
        assert "_nameToLevel" not in source, (
            "logging.py should not use private _nameToLevel API"
        )

        # Should use the public API instead
        assert "getLevelNamesMapping" in source, (
            "logging.py should use public getLevelNamesMapping API"
        )

    def test_error_message_completeness(self):
        """Test that error message includes all standard log levels."""
        settings = ScriptRAGSettings.__new__(ScriptRAGSettings)
        object.__setattr__(settings, "log_level", "BOGUS")
        object.__setattr__(settings, "log_format", "console")
        object.__setattr__(settings, "log_file", None)
        object.__setattr__(settings, "debug", False)

        with pytest.raises(ValueError) as exc_info:
            configure_logging(settings)

        error_msg = str(exc_info.value)

        # Standard levels that must be present
        standard_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]
        for level in standard_levels:
            assert level in error_msg, (
                f"Standard level {level} missing from error message"
            )

    def test_public_api_compatibility(self):
        """Test that our usage of getLevelNamesMapping is compatible."""
        # Get levels using the public API
        level_mapping = logging.getLevelNamesMapping()

        # Verify we can filter and sort as expected
        valid_levels = sorted(
            [level for level in level_mapping if not level.startswith("_")]
        )

        # Should have at least the standard levels
        assert len(valid_levels) >= 6  # NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL

        # Should be sortable (all strings)
        assert all(isinstance(level, str) for level in valid_levels)

    @patch("logging.getLevelNamesMapping")
    def test_handles_future_logging_levels(self, mock_get_levels):
        """Test that code handles potential future logging levels gracefully."""
        # Mock a future Python version with additional log levels
        mock_get_levels.return_value = {
            "CRITICAL": 50,
            "ERROR": 40,
            "WARNING": 30,
            "INFO": 20,
            "DEBUG": 10,
            "TRACE": 5,  # Hypothetical future level
            "NOTSET": 0,
        }

        settings = ScriptRAGSettings.__new__(ScriptRAGSettings)
        object.__setattr__(settings, "log_level", "INVALID")
        object.__setattr__(settings, "log_format", "console")
        object.__setattr__(settings, "log_file", None)
        object.__setattr__(settings, "debug", False)

        with pytest.raises(ValueError) as exc_info:
            configure_logging(settings)

        error_msg = str(exc_info.value)

        # Should include the hypothetical TRACE level
        assert "TRACE" in error_msg

        # Should still be sorted
        levels_part = error_msg.split("Valid levels are: ")[1]
        listed_levels = [level.strip() for level in levels_part.split(",")]
        assert listed_levels == sorted(listed_levels)

    def test_python_version_compatibility(self):
        """Verify Python version is 3.11+ for getLevelNamesMapping."""

        # We require Python 3.11+ for getLevelNamesMapping
        assert sys.version_info >= (3, 11), (
            "Python 3.11+ required for getLevelNamesMapping"
        )

        # The API should be available
        assert hasattr(logging, "getLevelNamesMapping")

    def test_logging_module_imports_correctly(self):
        """Test that our logging module can be imported without issues."""
        # This should not raise any errors
        from scriptrag.config import logging as config_logging

        # Should have the configure_logging function
        assert hasattr(config_logging, "configure_logging")
        assert hasattr(config_logging, "get_logger")

        # Should be able to call with valid settings
        settings = ScriptRAGSettings(log_level="INFO")
        config_logging.configure_logging(settings)

        # Root logger should be configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
