"""ScriptRAG configuration module."""

from __future__ import annotations

from typing import Any

from scriptrag.config.logging import configure_logging
from scriptrag.config.logging import get_logger as _get_logger
from scriptrag.config.settings import (
    ScriptRAGSettings,
    clear_settings_cache,
    get_settings,
    set_settings,
)
from scriptrag.config.settings import (
    reset_settings as _reset_settings,
)

__all__ = [
    "ScriptRAGSettings",
    "clear_settings_cache",
    "configure_logging",
    "get_logger",
    "get_settings",
    "reset_settings",
    "set_settings",
]

# Initialize logging when settings are first accessed
_logging_initialized = False
# Cache for logger instances to improve performance
_logger_cache: dict[str, Any] = {}


def _ensure_logging_configured() -> None:
    """Ensure logging is configured.

    This function is optimized to only check the initialization flag
    once logging has been configured, improving performance for
    subsequent logger retrievals.
    """
    global _logging_initialized
    if not _logging_initialized:
        settings = get_settings()
        configure_logging(settings)
        _logging_initialized = True


# Override get_logger to ensure logging is configured
# Store reference to original function


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    This function implements a two-layer caching strategy:
    1. Local cache in this module for fast lookups
    2. Structlog's internal cache for logger instances

    The local cache provides immediate returns for frequently used
    loggers without even calling into structlog, improving performance
    in hot code paths.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured structlog logger (cached after first use).
    """
    # Fast path: return cached logger if available
    if name in _logger_cache:
        return _logger_cache[name]

    # Ensure logging is configured
    _ensure_logging_configured()

    # Get logger and cache it
    logger = _get_logger(name)
    _logger_cache[name] = logger
    return logger


def reset_settings() -> None:
    """Reset settings and clear logger cache.

    This function resets both the settings and the logger cache,
    ensuring a clean state for testing or reconfiguration.
    """
    global _logging_initialized, _logger_cache
    _reset_settings()
    _logging_initialized = False
    _logger_cache.clear()
