"""Utility functions for MCP server."""

from typing import Any

from scriptrag.config import ScriptRAGSettings, get_settings


def get_api_settings() -> ScriptRAGSettings:
    """Get settings for API initialization.

    Returns:
        Configuration settings
    """
    return get_settings()


def format_error(error: Exception) -> dict[str, Any]:
    """Format an exception as an MCP error response.

    Args:
        error: The exception to format

    Returns:
        Dictionary with error information
    """
    return {
        "success": False,
        "error": str(error),
        "error_type": type(error).__name__,
    }


def format_success(data: Any, **metadata: Any) -> dict[str, Any]:
    """Format successful response data.

    Args:
        data: The response data
        **metadata: Additional metadata fields

    Returns:
        Dictionary with success response
    """
    response = {
        "success": True,
        "data": data,
    }
    response.update(metadata)
    return response
