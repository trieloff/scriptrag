"""ScriptRAG configuration module."""

from typing import Any

import structlog

from scriptrag.config.settings import ScriptRAGSettings, get_settings, set_settings

__all__ = ["ScriptRAGSettings", "get_logger", "get_settings", "set_settings"]


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured structlog logger.
    """
    return structlog.get_logger(name)
