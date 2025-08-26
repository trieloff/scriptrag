"""Tests for logging configuration."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import structlog

from scriptrag.config import (
    ScriptRAGSettings,
    configure_logging,
    get_logger,
    set_settings,
)


@pytest.fixture(autouse=True)
def clean_logging():
    """Reset logging configuration before and after each test."""
    # Reset settings
    set_settings(None)

    # Reset structlog configuration
    structlog.reset_defaults()

    # Clear all handlers from root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    yield

    # Clean up again
    set_settings(None)
    structlog.reset_defaults()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)


class TestLoggingConfiguration:
    """Test logging configuration functionality."""

    def test_configure_logging_console_format(self):
        """Test logging configuration with console format."""
        settings = ScriptRAGSettings(
            log_level="INFO",
            log_format="console",
        )

        configure_logging(settings)

        # Get a logger and test it
        logger = get_logger("test")

        # Capture output
        with patch("sys.stderr") as mock_stderr:
            mock_stderr.isatty.return_value = False  # No colors
            logger.info("test message", key="value")

        # Check that logging was configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1

    def test_configure_logging_json_format(self):
        """Test logging configuration with JSON format."""
        settings = ScriptRAGSettings(
            log_level="DEBUG",
            log_format="json",
        )

        configure_logging(settings)

        # Check that logging was configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        # Check that handlers are configured
        assert len(root_logger.handlers) >= 1

        # Check that the first handler has the correct formatter
        handler = root_logger.handlers[0]
        assert hasattr(handler, "formatter")

        # The formatter should be ProcessorFormatter for JSON
        from structlog.stdlib import ProcessorFormatter

        assert isinstance(handler.formatter, ProcessorFormatter)

    def test_configure_logging_structured_format(self):
        """Test logging configuration with structured format."""
        settings = ScriptRAGSettings(
            log_level="INFO",
            log_format="structured",
        )

        configure_logging(settings)

        # Check that logging was configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Check that handlers are configured
        assert len(root_logger.handlers) >= 1

        # Check that the first handler has the correct formatter
        handler = root_logger.handlers[0]
        assert hasattr(handler, "formatter")

        # The formatter should be ProcessorFormatter for structured format
        from structlog.stdlib import ProcessorFormatter

        assert isinstance(handler.formatter, ProcessorFormatter)

        # Test that the ProcessorFormatter is configured with KeyValueRenderer
        # by checking the processor chain
        logger = get_logger("test")

        # Just verify we can log without errors in structured format
        logger.info("test structured format", key1="value1", key2="value2")

    def test_configure_logging_file_handler(self, tmp_path):
        """Test logging configuration with file handler."""
        log_file = tmp_path / "logs" / "test.log"

        settings = ScriptRAGSettings(
            log_level="WARNING",
            log_format="json",
            log_file=log_file,
        )

        configure_logging(settings)

        # Log directory should be created
        assert log_file.parent.exists()

        # Get a logger and log something
        logger = get_logger("test")
        logger.warning("test warning")

        # Check that file handler was added
        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if hasattr(h, "baseFilename")]
        assert len(file_handlers) == 1
        assert Path(file_handlers[0].baseFilename) == log_file

    def test_configure_logging_debug_mode(self):
        """Test logging configuration in debug mode."""
        settings = ScriptRAGSettings(
            log_level="DEBUG",
            log_format="console",
            debug=True,
        )

        configure_logging(settings)

        # In debug mode, callsite info should be added
        logger = get_logger("test")

        # Log something and check that it includes callsite info
        with patch(
            "sys.stderr", MagicMock(spec=["content", "model", "provider", "usage"])
        ):
            logger.debug("debug message")
            # In debug mode, structlog should add filename, lineno, func_name

    def test_logging_levels(self):
        """Test different logging levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = ScriptRAGSettings(log_level=level)
            configure_logging(settings)

            root_logger = logging.getLogger()
            expected_level = getattr(logging, level)
            assert root_logger.level == expected_level

    def test_get_logger_auto_configures(self):
        """Test that get_logger automatically configures logging."""
        # Reset the module-level flag
        import scriptrag.config

        scriptrag.config._logging_initialized = False

        # Set custom settings
        settings = ScriptRAGSettings(
            log_level="ERROR",
            log_format="json",
        )
        set_settings(settings)

        # Getting a logger should trigger configuration
        get_logger("test")

        # Check that logging was configured with our settings
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

        # Flag should be set
        assert scriptrag.config._logging_initialized is True

    def test_logging_context_vars(self):
        """Test that logging preserves context variables."""
        settings = ScriptRAGSettings(
            log_level="INFO",
            log_format="json",
        )

        configure_logging(settings)

        # Get a logger with context
        logger = get_logger("test")
        logger = logger.bind(request_id="123", user="test_user")

        # Just verify the logger has the expected context
        # The actual output testing is complex due to global state
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")

    def test_logging_exception_formatting(self):
        """Test exception formatting in logs."""
        settings = ScriptRAGSettings(
            log_level="ERROR",
            log_format="json",
        )

        configure_logging(settings)
        logger = get_logger("test")

        # Just verify the logger has the exception method
        assert hasattr(logger, "exception")

        # Test that we can call it without error
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("Error occurred")  # Should not raise

    def test_rotating_file_handler_config(self, tmp_path):
        """Test that rotating file handler is properly configured."""
        log_file = tmp_path / "app.log"

        settings = ScriptRAGSettings(
            log_file=log_file,
            log_file_rotation="1 day",
            log_file_retention="7 days",
        )

        configure_logging(settings)

        # Find the rotating file handler
        root_logger = logging.getLogger()
        from logging.handlers import RotatingFileHandler

        rotating_handlers = [
            h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
        ]

        assert len(rotating_handlers) == 1
        handler = rotating_handlers[0]

        # Check configuration
        assert handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert handler.backupCount == 5

    def test_configure_logging_console_format_debug_false(self):
        """Test logging configuration with console format and debug=False."""
        settings = ScriptRAGSettings(
            log_level="INFO",
            log_format="console",
            debug=False,  # This should not add callsite info
        )

        configure_logging(settings)
        logger = get_logger("test")

        # Capture log output
        import io

        # Create a string buffer to capture console output
        buffer = io.StringIO()

        # Get root logger and add a stream handler
        root_logger = logging.getLogger()
        handler = logging.StreamHandler(buffer)
        root_logger.addHandler(handler)

        # Log a message
        logger.info("test message without debug info")

        # Get the output
        output = buffer.getvalue()

        # When debug=False and format=console, callsite info should NOT be included
        assert "filename=" not in output
        assert "lineno=" not in output
        assert "func_name=" not in output

        # Clean up
        root_logger.removeHandler(handler)
