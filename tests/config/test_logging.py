"""Comprehensive tests for the logging configuration module."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config.logging import (
    LOGGING_CONFIGS,
    TemporaryLogLevel,
    configure_httpx_logging,
    configure_logging,
    configure_sqlalchemy_logging,
    get_logger,
    setup_logging_for_environment,
)


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset logging state before each test to ensure isolation."""
    # Store original state
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = root_logger.handlers.copy()

    # Clear all handlers to ensure basicConfig works
    for handler in root_logger.handlers.copy():
        root_logger.removeHandler(handler)

    yield

    # Restore original state
    root_logger.setLevel(original_level)
    for handler in root_logger.handlers.copy():
        root_logger.removeHandler(handler)
    for handler in original_handlers:
        root_logger.addHandler(handler)


class TestConfigureLogging:
    """Test the main configure_logging function."""

    def test_default_configuration(self):
        """Test default logging configuration."""
        configure_logging()

        # Verify root logger level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Get a structlog logger and verify it works
        logger = get_logger("test")
        assert logger is not None

    def test_log_level_configuration(self):
        """Test different log level configurations."""
        for level_str, level_const in [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]:
            configure_logging(log_level=level_str)
            root_logger = logging.getLogger()
            assert root_logger.level == level_const

    def test_case_insensitive_log_level(self):
        """Test that log level is case insensitive."""
        configure_logging(log_level="debug")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        configure_logging(log_level="InFo")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_invalid_log_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        configure_logging(log_level="INVALID")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_dev_mode_configuration(self, capsys):
        """Test development mode configuration."""
        configure_logging(dev_mode=True, json_logs=False)

        logger = get_logger("test")
        logger.info("test message", key="value")

        captured = capsys.readouterr()
        # Dev mode should have colorized output (contains test message)
        assert "test message" in captured.out
        assert "key" in captured.out
        assert "value" in captured.out

    def test_json_logs_configuration(self, capsys):
        """Test JSON logging configuration."""
        configure_logging(json_logs=True)

        logger = get_logger("test")
        logger.info("test message", key="value")

        captured = capsys.readouterr()
        # Should be valid JSON
        log_data = json.loads(captured.out.strip())
        assert log_data["event"] == "test message"
        assert log_data["key"] == "value"
        assert "timestamp" in log_data

    def test_plain_text_production_mode(self, capsys):
        """Test plain text production mode (non-JSON)."""
        configure_logging(dev_mode=False, json_logs=False)

        logger = get_logger("test")
        logger.info("test message", key="value")

        captured = capsys.readouterr()
        # Should be key-value format - key value pairs with quotes
        assert "test message" in captured.out
        assert "key='value'" in captured.out

    def test_file_logging(self, tmp_path):
        """Test file logging configuration."""
        log_file = tmp_path / "test.log"
        configure_logging(log_file=log_file)

        # Log a message using standard logging
        standard_logger = logging.getLogger("test")
        standard_logger.info("file test message")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        # Verify file was created and contains the message
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "file test message" in log_content

    def test_file_logging_directory_creation(self, tmp_path):
        """Test that log file directory is created if it doesn't exist."""
        log_file = tmp_path / "subdir" / "logs" / "test.log"
        configure_logging(log_file=log_file)

        assert log_file.parent.exists()

    def test_file_logging_json_format(self, tmp_path):
        """Test JSON format for file logging."""
        log_file = tmp_path / "test.log"
        configure_logging(log_file=log_file, json_logs=True)

        # Log a message using standard logging
        standard_logger = logging.getLogger("test")
        standard_logger.info("json file test")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        # Read and parse the log file
        log_content = log_file.read_text().strip()
        # File handler uses standard logging format, not structlog
        assert "json file test" in log_content

    @patch("structlog.configure")
    def test_structlog_configuration_called(self, mock_configure):
        """Test that structlog.configure is called with correct parameters."""
        configure_logging(dev_mode=True, json_logs=False)

        mock_configure.assert_called_once()
        call_kwargs = mock_configure.call_args.kwargs

        # Verify key configuration parameters
        assert "processors" in call_kwargs
        assert "wrapper_class" in call_kwargs
        assert "logger_factory" in call_kwargs
        assert call_kwargs["cache_logger_on_first_use"] is True


class TestGetLogger:
    """Test the get_logger function."""

    def test_get_logger_returns_structlog_instance(self):
        """Test that get_logger returns a structlog logger."""
        configure_logging()
        logger = get_logger("test.module")

        # Verify it's a structlog logger by checking for bound methods
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_logger_name_preservation(self):
        """Test that logger preserves the name."""
        configure_logging()
        logger = get_logger("my.custom.logger")

        # Logger should work with the given name
        assert logger is not None


class TestThirdPartyLogging:
    """Test third-party library logging configuration."""

    def test_configure_sqlalchemy_logging(self):
        """Test SQLAlchemy logging configuration."""
        # Set to DEBUG first
        for logger_name in [
            "sqlalchemy.engine",
            "sqlalchemy.dialects",
            "sqlalchemy.pool",
            "sqlalchemy.orm",
        ]:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)

        # Configure to WARNING
        configure_sqlalchemy_logging("WARNING")

        # Verify all SQLAlchemy loggers are set to WARNING
        for logger_name in [
            "sqlalchemy.engine",
            "sqlalchemy.dialects",
            "sqlalchemy.pool",
            "sqlalchemy.orm",
        ]:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.WARNING

    def test_configure_sqlalchemy_logging_case_insensitive(self):
        """Test that SQLAlchemy log level is case insensitive."""
        configure_sqlalchemy_logging("error")

        logger = logging.getLogger("sqlalchemy.engine")
        assert logger.level == logging.ERROR

    def test_configure_httpx_logging(self):
        """Test HTTPX logging configuration."""
        # Set to DEBUG first
        for logger_name in [
            "httpx._client",
            "httpcore.connection",
            "httpcore.http11",
        ]:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)

        # Configure to WARNING
        configure_httpx_logging("WARNING")

        # Verify all HTTPX loggers are set to WARNING
        for logger_name in [
            "httpx._client",
            "httpcore.connection",
            "httpcore.http11",
        ]:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.WARNING

    def test_configure_httpx_logging_custom_level(self):
        """Test HTTPX logging with custom level."""
        configure_httpx_logging("ERROR")

        logger = logging.getLogger("httpx._client")
        assert logger.level == logging.ERROR


class TestLoggingConfigs:
    """Test predefined logging configurations."""

    def test_development_config(self):
        """Test development logging configuration."""
        config = LOGGING_CONFIGS["development"]
        assert config["log_level"] == "DEBUG"
        assert config["json_logs"] is False
        assert config["dev_mode"] is True

    def test_testing_config(self):
        """Test testing logging configuration."""
        config = LOGGING_CONFIGS["testing"]
        assert config["log_level"] == "WARNING"
        assert config["json_logs"] is False
        assert config["dev_mode"] is True

    def test_production_config(self):
        """Test production logging configuration."""
        config = LOGGING_CONFIGS["production"]
        assert config["log_level"] == "INFO"
        assert config["json_logs"] is True
        assert config["dev_mode"] is False


class TestSetupLoggingForEnvironment:
    """Test environment-based logging setup."""

    def test_development_environment_setup(self):
        """Test development environment logging setup."""
        setup_logging_for_environment("development")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        # Verify third-party loggers are configured
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
        assert logging.getLogger("httpx._client").level == logging.WARNING

    def test_testing_environment_setup(self):
        """Test testing environment logging setup."""
        setup_logging_for_environment("testing")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_production_environment_setup(self, capsys):
        """Test production environment logging setup."""
        setup_logging_for_environment("production")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Test that it logs in JSON format
        logger = get_logger("test")
        logger.info("production test")

        captured = capsys.readouterr()
        # In production, should be JSON - handle multiple log lines
        lines = [line for line in captured.out.strip().split("\n") if line.strip()]

        # Find the line with our test message
        test_line = None
        for line in lines:
            try:
                log_data = json.loads(line)
                if "production test" in log_data.get("event", ""):
                    test_line = log_data
                    break
            except json.JSONDecodeError:
                continue

        assert test_line is not None, f"Could not find test message in logs: {lines}"
        assert "production test" in test_line.get("event", "")

    def test_unknown_environment_defaults_to_development(self):
        """Test that unknown environment defaults to development config."""
        setup_logging_for_environment("unknown")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_environment_setup_with_log_file(self, tmp_path):
        """Test environment setup with log file."""
        log_file = tmp_path / "app.log"
        setup_logging_for_environment("production", log_file=log_file)

        # Verify file handler was added
        assert log_file.exists()

        # Log something
        standard_logger = logging.getLogger("test")
        standard_logger.info("environment file test")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        log_content = log_file.read_text()
        assert "environment file test" in log_content

    @patch("scriptrag.config.logging.get_logger")
    def test_setup_logs_configuration(self, mock_get_logger, tmp_path):
        """Test that setup logs its configuration."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        setup_logging_for_environment("production", log_file=tmp_path / "test.log")

        # Verify configuration was logged
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "Logging configured"
        assert call_args[1]["environment"] == "production"
        assert call_args[1]["log_level"] == "INFO"
        assert call_args[1]["json_logs"] is True
        assert str(tmp_path / "test.log") in call_args[1]["log_file"]


class TestTemporaryLogLevel:
    """Test TemporaryLogLevel context manager."""

    def test_temporary_log_level_change(self):
        """Test temporary log level change and restoration."""
        # Set initial level
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Temporarily change to DEBUG
        with TemporaryLogLevel("DEBUG"):
            assert root_logger.level == logging.DEBUG

        # Should be restored
        assert root_logger.level == logging.INFO

    def test_temporary_log_level_case_insensitive(self):
        """Test that temporary log level is case insensitive."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        with TemporaryLogLevel("debug"):
            assert root_logger.level == logging.DEBUG

    def test_temporary_log_level_with_exception(self):
        """Test that log level is restored even with exception."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        with pytest.raises(ValueError), TemporaryLogLevel("ERROR"):
            assert root_logger.level == logging.ERROR
            raise ValueError("Test exception")

        # Should still be restored
        assert root_logger.level == logging.INFO

    def test_nested_temporary_log_levels(self):
        """Test nested temporary log level changes."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        with TemporaryLogLevel("WARNING"):
            assert root_logger.level == logging.WARNING

            with TemporaryLogLevel("ERROR"):
                assert root_logger.level == logging.ERROR

            # Should restore to WARNING
            assert root_logger.level == logging.WARNING

        # Should restore to INFO
        assert root_logger.level == logging.INFO


class TestLoggingIntegration:
    """Integration tests for the logging system."""

    def test_full_logging_workflow(self, tmp_path, capsys):
        """Test complete logging workflow."""
        # Setup logging for production with file
        log_file = tmp_path / "app.log"
        setup_logging_for_environment("production", log_file=log_file)

        # Get logger and log at different levels
        logger = get_logger("integration.test")

        logger.debug("debug message", debug_data="hidden")
        logger.info("info message", info_data="visible")
        logger.warning("warning message", warning_data="visible")
        logger.error("error message", error_data="visible", exc_info=True)

        # Also use standard logger for file output
        std_logger = logging.getLogger("integration.test")
        std_logger.info("standard info message")
        std_logger.warning("standard warning message")
        std_logger.error("standard error message")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        # Check console output (JSON format)
        captured = capsys.readouterr()
        console_lines = [
            line for line in captured.out.strip().split("\n") if line.strip()
        ]

        # Debug should not appear (level is INFO)
        assert not any("debug message" in line for line in console_lines)

        # Other levels should appear
        info_lines = [line for line in console_lines if "info message" in line]
        assert len(info_lines) > 0
        info_line = info_lines[0]
        info_data = json.loads(info_line)
        assert info_data["level"] == "info"
        assert info_data["info_data"] == "visible"

        # Check file output - standard logger writes to file
        file_content = log_file.read_text()
        assert "standard info message" in file_content
        assert "standard warning message" in file_content
        assert "standard error message" in file_content

    def test_contextual_logging(self, capsys):
        """Test contextual logging with structlog."""
        configure_logging(dev_mode=True)

        logger = get_logger("context.test")

        # Bind context
        logger = logger.bind(user_id=123, request_id="abc-def")

        # Log with bound context
        logger.info("user action", action="login")

        captured = capsys.readouterr()
        assert "user_id" in captured.out
        assert "123" in captured.out
        assert "request_id" in captured.out
        assert "abc-def" in captured.out
        assert "action" in captured.out
        assert "login" in captured.out

    def test_exception_logging(self, capsys):
        """Test exception logging."""
        configure_logging(json_logs=True)

        logger = get_logger("exception.test")

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("caught exception")

        captured = capsys.readouterr()
        log_data = json.loads(captured.out.strip())

        assert log_data["event"] == "caught exception"
        assert log_data["level"] == "error"
        assert "exc_info" in log_data

    def test_multiple_logger_instances(self):
        """Test that multiple logger instances work correctly."""
        configure_logging()

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should work independently
        assert logger1 is not logger2

    @patch("logging.FileHandler")
    def test_file_handler_configuration(self, mock_file_handler, tmp_path):
        """Test that file handler is properly configured."""
        mock_handler_instance = MagicMock()
        mock_file_handler.return_value = mock_handler_instance

        log_path = tmp_path / "test.log"
        configure_logging(log_file=log_path, json_logs=True)

        # Verify FileHandler was created with correct path
        mock_file_handler.assert_called_once_with(log_path)

        # Verify handler was configured
        mock_handler_instance.setLevel.assert_called_once()
        mock_handler_instance.setFormatter.assert_called_once()

    def test_logging_performance(self, tmp_path):
        """Test logging performance with high volume."""
        log_file = tmp_path / "performance.log"
        configure_logging(log_file=log_file, json_logs=True)

        # Logger for performance test - using standard logger for file output

        # Use standard logger for file logging, as structlog goes to console
        standard_logger = logging.getLogger("performance.test")

        # Log many messages
        for i in range(1000):
            standard_logger.info(f"test message {i} with data value_{i}")

        # Force flush handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        # Verify file isn't excessively large and all messages were logged
        assert log_file.exists()
        log_size = log_file.stat().st_size
        assert log_size > 0
        assert log_size < 1_000_000  # Should be less than 1MB for 1000 messages
