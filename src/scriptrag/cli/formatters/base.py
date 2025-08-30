"""Base formatter classes for CLI output."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

from rich.console import Console

T = TypeVar("T")


class OutputFormat(str, Enum):
    """Supported output formats."""

    TEXT = "text"
    JSON = "json"
    TABLE = "table"
    MARKDOWN = "markdown"
    CSV = "csv"


class OutputFormatter(ABC, Generic[T]):
    """Base class for output formatters."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize formatter.

        Args:
            console: Rich console for output. If None, creates new instance.
        """
        self.console = console or Console()

    @abstractmethod
    def format(self, data: T, format_type: OutputFormat = OutputFormat.TEXT) -> str:
        """Format data for output.

        Args:
            data: Data to format
            format_type: Output format type

        Returns:
            Formatted string
        """
        pass

    def print(self, data: T, format_type: OutputFormat = OutputFormat.TEXT) -> None:
        """Format and print data to console.

        Args:
            data: Data to format and print
            format_type: Output format type
        """
        output = self.format(data, format_type)
        if format_type == OutputFormat.JSON:
            self.console.print_json(output)
        else:
            self.console.print(output)

    def format_error(self, error: str | Exception) -> str:
        """Format error message.

        Args:
            error: Error message or exception

        Returns:
            Formatted error string
        """
        error_msg = str(error) if isinstance(error, Exception) else error
        return f"[red]Error: {error_msg}[/red]"

    def print_error(self, error: str | Exception) -> None:
        """Format and print error to console.

        Args:
            error: Error message or exception
        """
        self.console.print(self.format_error(error))
