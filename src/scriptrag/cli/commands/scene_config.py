"""Configuration loading utility for scene CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from scriptrag.config import get_settings
from scriptrag.config.settings import ScriptRAGSettings

console = Console()


def load_config_with_validation(config: Path | None) -> ScriptRAGSettings:
    """Load settings with proper precedence and validation.

    Args:
        config: Optional path to configuration file

    Returns:
        Loaded settings

    Raises:
        typer.Exit: If config file doesn't exist
    """
    if config:
        if not config.exists():
            console.print(f"[red]Error: Config file not found: {config}[/red]")
            raise typer.Exit(1)

        return ScriptRAGSettings.from_multiple_sources(
            config_files=[config],
        )

    # Use default settings
    return get_settings()
