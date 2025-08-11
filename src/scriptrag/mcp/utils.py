"""Shared utilities for MCP operations."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class AsyncAPIWrapper:
    """Wrapper to run synchronous API operations asynchronously."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize async wrapper.

        Args:
            settings: Configuration settings
        """
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.settings = settings

    async def run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run synchronous operation in thread pool.

        Args:
            func: Function to run
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)

    def __del__(self) -> None:
        """Clean up executor on deletion."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


def validate_file_path(path: str) -> Path:
    """Validate and resolve file path.

    Args:
        path: File path string

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is invalid or doesn't exist
    """
    try:
        resolved_path = Path(path).resolve()
        if not resolved_path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        return resolved_path
    except Exception as e:
        raise ValueError(f"Invalid file path: {e}") from e


def format_error_response(error: Exception, operation: str) -> dict[str, Any]:
    """Format error response for MCP tools.

    Args:
        error: The exception that occurred
        operation: The operation that failed

    Returns:
        Formatted error response
    """
    logger.error(f"MCP tool error in {operation}", error=str(error))
    return {
        "success": False,
        "error": str(error),
        "operation": operation,
        "message": f"{operation} failed: {error!s}",
    }


def sanitize_script_title(title: str) -> str:
    """Sanitize script title for safe usage.

    Args:
        title: Script title

    Returns:
        Sanitized title
    """
    # Remove or replace problematic characters
    sanitized = title.strip()
    # Replace path separators and other problematic characters
    for char in ["/", "\\", "..", "~", "|", ":", "*", "?", '"', "<", ">", "\n", "\r"]:
        sanitized = sanitized.replace(char, "_")
    return sanitized or "untitled"


def truncate_content(content: str, max_length: int = 5000) -> tuple[str, bool]:
    """Truncate content if it exceeds maximum length.

    Args:
        content: Content to truncate
        max_length: Maximum allowed length

    Returns:
        Tuple of (truncated content, was_truncated)
    """
    if len(content) <= max_length:
        return content, False

    # Find a good break point near the limit
    break_point = content.rfind("\n", 0, max_length)
    if break_point == -1 or break_point < max_length * 0.8:
        break_point = max_length

    truncated = content[:break_point]
    truncated += f"\n\n... (truncated, {len(content) - break_point} characters omitted)"
    return truncated, True


def parse_scene_heading(heading: str) -> dict[str, str | None]:
    """Parse scene heading into components.

    Args:
        heading: Scene heading text

    Returns:
        Dictionary with location, time_of_day, and setting
    """
    parts = heading.split(" - ")
    result: dict[str, str | None] = {"location": None, "time_of_day": None, "setting": None}

    if parts:
        # First part is usually INT/EXT and location
        first_part = parts[0].strip()
        if first_part.startswith(("INT.", "EXT.", "INT/EXT.")):
            setting_end = first_part.find(".")
            result["setting"] = first_part[:setting_end]
            result["location"] = first_part[setting_end + 1 :].strip()
        else:
            result["location"] = first_part

        # Second part is usually time of day
        if len(parts) > 1:
            result["time_of_day"] = parts[1].strip()

    return result
