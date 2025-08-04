"""ScriptRAG configuration module."""

from typing import Any

import structlog


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured structlog logger.
    """
    return structlog.get_logger(name)
