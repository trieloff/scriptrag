"""Error handling utilities for CLI commands."""

from __future__ import annotations

import traceback

import typer
from rich.console import Console

from scriptrag.config import get_logger
from scriptrag.exceptions import ScriptRAGError

logger = get_logger(__name__)
console = Console()


def handle_cli_error(
    error: Exception, verbose: bool = False, exit_code: int = 1
) -> None:
    """Handle errors in CLI commands with helpful formatting.

    Args:
        error: The exception that was raised
        verbose: Whether to show detailed error information
        exit_code: Exit code to use when exiting
    """
    if isinstance(error, ScriptRAGError):
        # Custom ScriptRAG errors with helpful messages
        console.print(f"[red]✗ {error.message}[/red]")

        if error.hint:
            console.print(f"[yellow]→ {error.hint}[/yellow]")

        if verbose and error.details:
            console.print("\n[dim]Details:[/dim]")
            for key, value in error.details.items():
                console.print(f"  [dim]{key}:[/dim] {value}")

        # Log the full error with structured metadata for debugging
        logger.error(
            "ScriptRAG error occurred",
            error_type=type(error).__name__,
            message=error.message,
            hint=error.hint,
            details=error.details,
            verbose_mode=verbose,
            exit_code=exit_code,
        )

    elif isinstance(error, FileNotFoundError):
        # Standard file not found errors
        console.print(f"[red]✗ File not found: {error}[/red]")
        console.print("[yellow]→ Check that the file path is correct[/yellow]")
        logger.error(
            "File not found",
            error=str(error),
            filename=getattr(error, "filename", None),
            error_type="FileNotFoundError",
            exit_code=exit_code,
        )

    elif isinstance(error, KeyboardInterrupt):
        # User interrupted the operation
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        logger.info(
            "Operation interrupted by user",
            error_type="KeyboardInterrupt",
            exit_code=exit_code,
        )

    else:
        # Unknown/unexpected errors
        console.print(f"[red]✗ Unexpected error: {error!s}[/red]")

        if verbose:
            console.print("\n[dim]Full traceback:[/dim]")
            console.print(traceback.format_exc())
        else:
            console.print("[dim]Run with --verbose for full error details[/dim]")

        # Log full error details with structured metadata
        logger.error(
            "Unexpected error occurred",
            error=str(error),
            error_type=type(error).__name__,
            verbose_mode=verbose,
            exit_code=exit_code,
            exc_info=True,
        )

    raise typer.Exit(exit_code)
