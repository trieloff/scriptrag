"""Unified CLI handler for standardized error handling and output."""

import asyncio
import sys
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import typer
from rich.console import Console

from scriptrag.cli.formatters.base import OutputFormat
from scriptrag.cli.formatters.json_formatter import JsonFormatter
from scriptrag.cli.validators.base import ValidationError
from scriptrag.config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CLIHandler:
    """Unified handler for CLI commands."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize CLI handler.

        Args:
            console: Rich console for output
        """
        self.console = console or Console()
        self.json_formatter = JsonFormatter()

    def handle_error(
        self, error: Exception, json_output: bool = False, exit_code: int = 1
    ) -> None:
        """Handle and display errors consistently.

        Args:
            error: Exception to handle
            json_output: Whether to output JSON
            exit_code: Exit code to use
        """
        error_msg = str(error)
        logger.error(f"Command failed: {error_msg}", exc_info=error)

        if json_output:
            self.console.print(
                self.json_formatter.format_error_response(error, exit_code)
            )
        else:
            if isinstance(error, ValidationError):
                self.console.print(f"[red]Validation Error: {error_msg}[/red]")
            else:
                self.console.print(f"[red]Error: {error_msg}[/red]")

        raise typer.Exit(exit_code)

    def handle_success(
        self, message: str, data: Any = None, json_output: bool = False
    ) -> None:
        """Handle success responses consistently.

        Args:
            message: Success message
            data: Optional data to include
            json_output: Whether to output JSON
        """
        if json_output:
            self.console.print(self.json_formatter.format_success(message, data))
        else:
            self.console.print(f"[green]{message}[/green]")

    def get_output_format(
        self,
        json: bool = False,
        csv: bool = False,
        markdown: bool = False,
        table: bool = True,  # noqa: ARG002
    ) -> OutputFormat:
        """Determine output format from flags.

        Args:
            json: JSON output flag
            csv: CSV output flag
            markdown: Markdown output flag
            table: Table output flag (default)

        Returns:
            Selected output format
        """
        if json:
            return OutputFormat.JSON
        if csv:
            return OutputFormat.CSV
        if markdown:
            return OutputFormat.MARKDOWN
        return OutputFormat.TABLE

    def read_stdin(self, required: bool = True) -> str | None:
        """Read content from stdin.

        Args:
            required: Whether stdin content is required

        Returns:
            Content from stdin or None

        Raises:
            typer.Exit: If required and no content available
        """
        if sys.stdin.isatty():
            if required:
                self.console.print(
                    "[red]Error: No input provided. "
                    "Use --content or pipe from stdin[/red]"
                )
                raise typer.Exit(1)
            return None
        return sys.stdin.read()


def cli_command(
    async_func: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for CLI commands with standardized error handling.

    Args:
        async_func: Whether the decorated function is async

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            handler = CLIHandler()
            try:
                # Check if function is async
                if async_func or asyncio.iscoroutinefunction(func):
                    # Run async function
                    result = asyncio.run(func(*args, **kwargs))
                else:
                    # Run sync function
                    result = func(*args, **kwargs)
                return result
            except typer.Exit:
                # Re-raise Typer exits
                raise
            except ValidationError as e:
                # Handle validation errors
                handler.handle_error(e, kwargs.get("json_output", False))
            except Exception as e:
                # Handle all other errors
                handler.handle_error(e, kwargs.get("json_output", False))

        return wrapper

    return decorator


def async_cli_command(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator specifically for async CLI commands.

    Args:
        func: Async function to decorate

    Returns:
        Wrapped function
    """
    return cli_command(async_func=True)(func)
