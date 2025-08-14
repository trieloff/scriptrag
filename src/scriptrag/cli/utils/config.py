"""Configuration utilities for CLI commands."""

from pathlib import Path

import typer
from rich.console import Console

from scriptrag.config import get_settings
from scriptrag.config.settings import ScriptRAGSettings

console = Console()


def override_database_path(
    db_path: Path | None, clear_cache: bool = True
) -> ScriptRAGSettings:
    """Override database path in settings with validation.

    Args:
        db_path: Custom database path to use (if provided)
        clear_cache: Whether to clear the settings cache first

    Returns:
        ScriptRAGSettings with database path override applied

    Raises:
        typer.Exit: If the database path parent directory doesn't exist
    """
    if clear_cache:
        # Clear cached settings to ensure fresh configuration
        import scriptrag.config.settings as settings_module

        settings_module._settings = None

    settings = get_settings()

    if db_path is None:
        return settings

    # Validate that parent directory exists
    if not db_path.parent.exists():
        console.print(
            f"[red]Error: Directory does not exist: {db_path.parent}[/red]",
            style="bold",
        )
        console.print(
            "[yellow]Create the directory first or specify a valid path.[/yellow]"
        )
        raise typer.Exit(1)

    # Check if parent directory is writable
    if not db_path.parent.is_dir():
        console.print(
            f"[red]Error: Path is not a directory: {db_path.parent}[/red]",
            style="bold",
        )
        raise typer.Exit(1)

    # Apply db_path override
    updated_data = settings.model_dump()
    updated_data["database_path"] = db_path
    return ScriptRAGSettings(**updated_data)
