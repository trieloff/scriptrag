"""Database path utilities for CLI commands."""

from pathlib import Path
from typing import Any

import typer

from scriptrag.config import ScriptRAGSettings


def get_db_path_from_context(ctx: typer.Context) -> Path | None:
    """Extract database path from typer context if available.

    Args:
        ctx: Typer context object

    Returns:
        Database path from context or None if not set
    """
    if ctx and ctx.obj and isinstance(ctx.obj, dict):
        db_path = ctx.obj.get("db_path")
        return (
            db_path if db_path is None or isinstance(db_path, Path) else Path(db_path)
        )
    return None


def get_settings_with_db_override(
    ctx: typer.Context | None = None,
    config_path: Path | None = None,
    extra_cli_args: dict[str, Any] | None = None,
) -> ScriptRAGSettings:
    """Get settings with database path override from context.

    This function handles the precedence of database path settings:
    1. Global --db-path option (from context)
    2. Config file settings
    3. Environment variables
    4. Default values

    Args:
        ctx: Typer context object containing global options
        config_path: Optional path to configuration file
        extra_cli_args: Additional CLI arguments to override settings

    Returns:
        ScriptRAGSettings instance with proper overrides applied
    """
    from scriptrag.config import get_settings

    # Start with CLI args dict
    cli_args = extra_cli_args.copy() if extra_cli_args else {}

    # Get db_path from context (global option)
    db_path = get_db_path_from_context(ctx) if ctx else None
    if db_path is not None:
        cli_args["database_path"] = db_path

    # If we have any CLI args or a config file, use from_multiple_sources
    if cli_args or config_path:
        config_files: list[Path | str] | None = [config_path] if config_path else None
        settings = ScriptRAGSettings.from_multiple_sources(
            config_files=config_files,
            cli_args=cli_args,
        )
    else:
        # Use default settings
        settings = get_settings()

    return settings
