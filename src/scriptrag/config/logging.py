"""Logging configuration for ScriptRAG.

This module provides structured logging setup using structlog with proper
configuration for different environments (development, production).
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor


def configure_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    json_logs: bool = False,
    dev_mode: bool = True,
) -> None:
    """Configure structured logging for ScriptRAG.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        json_logs: Whether to output logs in JSON format
        dev_mode: Whether to use development-friendly formatting
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    # Build final processors list based on configuration
    final_processors: list[Processor]
    if dev_mode and not json_logs:
        # Development mode: human-readable colorized output
        final_processors = [
            *shared_processors,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    elif json_logs:
        # Production mode: JSON structured logs
        final_processors = [
            *shared_processors,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Production mode: plain text structured logs
        final_processors = [
            *shared_processors,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.KeyValueRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=final_processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure file logging if specified
    if log_file:
        _configure_file_logging(log_file, numeric_level, json_logs)


def _configure_file_logging(
    log_file: Path,
    log_level: int,
    json_format: bool = False,
) -> None:
    """Configure file-based logging.

    Args:
        log_file: Path to the log file
        log_level: Numeric log level
        json_format: Whether to use JSON format for file logs
    """
    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)

    if json_format:
        # JSON formatter for structured logs
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Standard formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    file_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger instance
    """
    return structlog.get_logger(name)


def configure_sqlalchemy_logging(log_level: str = "WARNING") -> None:
    """Configure SQLAlchemy logging to reduce noise.

    Args:
        log_level: Log level for SQLAlchemy loggers
    """
    sqlalchemy_loggers = [
        "sqlalchemy.engine",
        "sqlalchemy.dialects",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
    ]

    numeric_level = getattr(logging, log_level.upper(), logging.WARNING)

    for logger_name in sqlalchemy_loggers:
        logging.getLogger(logger_name).setLevel(numeric_level)


def configure_httpx_logging(log_level: str = "WARNING") -> None:
    """Configure HTTPX logging to reduce noise.

    Args:
        log_level: Log level for HTTPX loggers
    """
    httpx_loggers = [
        "httpx._client",
        "httpcore.connection",
        "httpcore.http11",
    ]

    numeric_level = getattr(logging, log_level.upper(), logging.WARNING)

    for logger_name in httpx_loggers:
        logging.getLogger(logger_name).setLevel(numeric_level)


# Predefined logging configurations
LOGGING_CONFIGS: dict[str, dict[str, Any]] = {
    "development": {
        "log_level": "DEBUG",
        "json_logs": False,
        "dev_mode": True,
    },
    "testing": {
        "log_level": "WARNING",
        "json_logs": False,
        "dev_mode": True,
    },
    "production": {
        "log_level": "INFO",
        "json_logs": True,
        "dev_mode": False,
    },
}


def setup_logging_for_environment(
    environment: str = "development",
    log_file: Path | None = None,
) -> None:
    """Set up logging for a specific environment.

    Args:
        environment: Environment name (development, testing, production)
        log_file: Optional log file path
    """
    config = LOGGING_CONFIGS.get(environment, LOGGING_CONFIGS["development"])

    configure_logging(
        log_level=config["log_level"],
        log_file=log_file,
        json_logs=config["json_logs"],
        dev_mode=config["dev_mode"],
    )

    # Configure third-party library logging
    configure_sqlalchemy_logging()
    configure_httpx_logging()

    # Log the configuration
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        environment=environment,
        log_level=config["log_level"],
        json_logs=config["json_logs"],
        log_file=str(log_file) if log_file else None,
    )


# Context manager for temporary log level changes
class TemporaryLogLevel:
    """Context manager to temporarily change log level."""

    def __init__(self, level: str) -> None:
        """Initialize with target log level."""
        self.level = level
        self.original_level: int = 0

    def __enter__(self) -> "TemporaryLogLevel":
        """Enter context and set new log level."""
        root_logger = logging.getLogger()
        self.original_level = root_logger.level
        root_logger.setLevel(getattr(logging, self.level.upper()))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit context and restore original log level."""
        if self.original_level is not None:
            root_logger = logging.getLogger()
            root_logger.setLevel(self.original_level)
