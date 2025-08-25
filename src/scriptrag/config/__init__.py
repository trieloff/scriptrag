"""ScriptRAG configuration module."""

from typing import Any

from scriptrag.config.logging import configure_logging
from scriptrag.config.logging import get_logger as _get_logger
from scriptrag.config.settings import (
    ScriptRAGSettings,
    clear_settings_cache,
    get_settings,
    set_settings,
)

__all__ = [
    "ScriptRAGSettings",
    "clear_settings_cache",
    "configure_logging",
    "get_logger",
    "get_settings",
    "set_settings",
]

# Initialize logging when settings are first accessed
_logging_initialized = False


def _ensure_logging_configured() -> None:
    """Ensure logging is configured."""
    global _logging_initialized
    if not _logging_initialized:
        settings = get_settings()
        configure_logging(settings)
        _logging_initialized = True


# Override get_logger to ensure logging is configured
# Store reference to original function


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured structlog logger.
    """
    _ensure_logging_configured()
    return _get_logger(name)
