"""Logging configuration for ScriptRAG."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars
from structlog.processors import (
    CallsiteParameter,
    CallsiteParameterAdder,
    TimeStamper,
    add_log_level,
    dict_tracebacks,
    format_exc_info,
)
from structlog.stdlib import (
    ProcessorFormatter,
    add_logger_name,
    filter_by_level,
    render_to_log_kwargs,
)

from scriptrag.config.settings import ScriptRAGSettings


def configure_logging(settings: ScriptRAGSettings) -> None:
    """Configure logging based on settings.

    Args:
        settings: Application settings containing logging configuration.

    Raises:
        ValueError: If the log level is invalid or not found in the logging module.
    """
    # Configure standard library logging
    # Defensive programming: call .upper() even though the validator should normalize it
    # This ensures we handle cases where validation might be bypassed
    try:
        log_level = getattr(logging, settings.log_level.upper())
    except AttributeError as e:
        # Provide a helpful error message if an invalid log level somehow gets through
        # Use dynamic list from logging module to avoid hard-coding
        valid_levels = [
            name for name in logging._nameToLevel if not name.startswith("_")
        ]
        raise ValueError(
            f"Invalid log level '{settings.log_level}'. "
            f"Valid levels are: {', '.join(sorted(valid_levels))}"
        ) from e

    # Create formatters based on settings
    if settings.log_format == "json":
        # JSON format for production
        formatter = ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=[
                TimeStamper(fmt="iso"),
                add_log_level,
                add_logger_name,
            ],
        )
    elif settings.log_format == "structured":
        # Structured format with key-value pairs
        formatter = ProcessorFormatter(
            processor=structlog.processors.KeyValueRenderer(
                key_order=["timestamp", "level", "logger", "event"],
                drop_missing=True,
            ),
            foreign_pre_chain=[
                TimeStamper(fmt="iso"),
                add_log_level,
                add_logger_name,
            ],
        )
    else:
        # Console format for development
        formatter = ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(
                colors=sys.stderr.isatty(),
                exception_formatter=structlog.dev.rich_traceback,
            ),
            foreign_pre_chain=[
                TimeStamper(fmt="iso"),
                add_log_level,
                add_logger_name,
            ],
        )

    # Configure handlers
    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # File handler if configured
    if settings.log_file:
        # Ensure log directory exists
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,
    )

    # Explicitly ensure root logger level is set correctly
    # This is needed in CI environments where test isolation might not be perfect
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Configure structlog
    processors: list[Any] = [
        merge_contextvars,
        filter_by_level,
        TimeStamper(fmt="iso"),
        add_log_level,
        dict_tracebacks,
    ]

    # Add callsite info in debug mode
    if settings.debug:
        processors.append(
            CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.LINENO,
                    CallsiteParameter.FUNC_NAME,
                ]
            )
        )

    # Detect if we're in a test environment (pytest sets this)
    in_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

    # Add final processors based on format
    if settings.log_format == "json" or settings.log_format == "structured":
        processors.extend(
            [
                format_exc_info,
                render_to_log_kwargs,
                ProcessorFormatter.wrap_for_formatter,
            ]
        )
    else:
        if in_pytest:
            # In test environment: use ProcessorFormatter for caplog compatibility
            processors.extend(
                [
                    format_exc_info,
                    render_to_log_kwargs,
                    ProcessorFormatter.wrap_for_formatter,
                ]
            )
        else:
            # In normal runtime: use console renderer for pretty output
            processors.extend(
                [
                    format_exc_info,
                    structlog.dev.ConsoleRenderer(
                        colors=sys.stderr.isatty(),
                        exception_formatter=structlog.dev.rich_traceback,
                    ),
                ]
            )

    # Performance optimizations
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,  # Cache logger instances for performance
    )

    # Additional performance optimizations for production
    if not settings.debug and settings.log_level != "DEBUG":
        # Disable debug-level logging at the handler level for better performance
        # Only adjust handlers that are set to DEBUG to avoid overriding explicit levels
        for handler in logging.getLogger().handlers:
            if handler.level == logging.DEBUG:
                handler.setLevel(logging.INFO)


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    This function implements logger caching to improve performance by
    reusing logger instances that have already been created. The caching
    is handled by structlog internally when cache_logger_on_first_use=True
    is set in the configuration.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured structlog logger (cached after first use).
    """
    return structlog.get_logger(name)
