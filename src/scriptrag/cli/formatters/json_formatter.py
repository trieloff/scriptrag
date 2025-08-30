"""JSON output formatter for CLI."""

from __future__ import annotations

import json
from typing import Any

from scriptrag.cli.formatters.base import OutputFormat, OutputFormatter


class JsonFormatter(OutputFormatter[Any]):
    """Generic JSON formatter for CLI output."""

    def format(self, data: Any, format_type: OutputFormat = OutputFormat.JSON) -> str:  # noqa: ARG002
        """Format data as JSON.

        Args:
            data: Data to format
            format_type: Output format type (ignored, always JSON)

        Returns:
            JSON string
        """
        # Handle various data types
        if hasattr(data, "model_dump"):
            # Pydantic models
            return json.dumps(data.model_dump(), default=str, indent=2)
        if hasattr(data, "__dict__"):
            # Regular objects
            return json.dumps(data.__dict__, default=str, indent=2)
        if isinstance(data, dict | list | tuple):
            # Native collections
            return json.dumps(data, default=str, indent=2)
        # Primitives or unknown types
        return json.dumps({"value": data}, default=str, indent=2)

    def format_success(self, message: str, data: Any = None) -> str:
        """Format a success response.

        Args:
            message: Success message
            data: Optional additional data

        Returns:
            JSON string
        """
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return json.dumps(response, default=str, indent=2)

    def format_error_response(self, error: str | Exception, code: int = 1) -> str:
        """Format an error response.

        Args:
            error: Error message or exception
            code: Error code

        Returns:
            JSON string
        """
        error_msg = str(error) if isinstance(error, Exception) else error

        response = {"success": False, "error": error_msg, "code": code}
        return json.dumps(response, indent=2)
