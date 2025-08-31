"""Refactored main CLI entry point with clean separation of concerns."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.cli.commands import (
    analyze_command,
    index_command,
    pull_command,
    watch_command,
)
from scriptrag.cli.commands.config import config_app
from scriptrag.cli.commands.init import init_command
from scriptrag.cli.commands.list import list_command
from scriptrag.cli.commands.mcp import mcp_command
from scriptrag.cli.commands.query import get_query_app
from scriptrag.cli.commands.scene import scene_app
from scriptrag.cli.commands.search import search_command
from scriptrag.cli.formatters.json_formatter import JsonFormatter
from scriptrag.cli.utils.cli_handler import CLIHandler
from scriptrag.config import get_logger, get_settings

logger = get_logger(__name__)
console = Console()

# Create main app with improved configuration
app = typer.Typer(
    name="scriptrag",
    help="Git-native screenplay analysis with temporal navigation",
    pretty_exceptions_enable=False,
    add_completion=False,
    rich_markup_mode="rich",
)

# Add subcommands with clean separation
app.command(name="init")(init_command)
app.command(name="index")(index_command)
app.command(name="list")(list_command)
app.command(name="ls")(list_command)  # Alias for list command
app.command(name="search")(search_command)
app.command(name="analyze")(analyze_command)
app.command(name="watch")(watch_command)
app.command(name="pull")(pull_command)
app.command(name="mcp")(mcp_command)

# Register subapps
app.add_typer(config_app, name="config")  # Config management subapp
app.add_typer(get_query_app(), name="query")  # Query subapp - use lazy loading
app.add_typer(scene_app, name="scene")  # Scene subapp


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed status")
    ] = False,
) -> None:
    """Show ScriptRAG status and configuration."""
    handler = CLIHandler(console)
    formatter = JsonFormatter()

    try:
        settings = get_settings()

        # Collect status information
        status_info = {
            "version": "2.0.0",
            "database": str(settings.database_path),
            "database_exists": settings.database_path.exists(),
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
        }

        if verbose and settings.database_path.exists():
            # Add more detailed information
            from scriptrag.api.database_operations import DatabaseOperations

            db_ops = DatabaseOperations(settings)
            with db_ops.transaction() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM scripts")
                script_count = cursor.fetchone()[0]
                cursor = conn.execute("SELECT COUNT(*) FROM scenes")
                scene_count = cursor.fetchone()[0]

                status_info.update(
                    {
                        "scripts": script_count,
                        "scenes": scene_count,
                    }
                )

        # Output status
        if json_output:
            # Output pure JSON without ANSI escape codes
            print(formatter.format(status_info))
        else:
            console.print("[bold cyan]ScriptRAG Status[/bold cyan]\n")
            for key, value in status_info.items():
                formatted_key = key.replace("_", " ").title()
                console.print(f"  {formatted_key}: {value}")

    except Exception as e:
        handler.handle_error(e, json_output)


@app.command()
def version(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show ScriptRAG version."""
    version_info = {
        "name": "ScriptRAG",
        "version": "2.0.0",
        "description": "Git-native screenplay analysis with temporal navigation",
    }

    if json_output:
        formatter = JsonFormatter()
        # Output pure JSON without ANSI escape codes
        print(formatter.format(version_info))
    else:
        console.print(f"ScriptRAG v{version_info['version']}")


@app.callback()
def main_callback(
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            envvar="SCRIPTRAG_CONFIG",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging (INFO level)"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug logging", envvar="SCRIPTRAG_DEBUG"),
    ] = False,
) -> None:
    """Configure global options."""
    # Set logging level based on flags
    if debug:
        import os

        # Set environment variable for debug mode
        os.environ["SCRIPTRAG_LOG_LEVEL"] = "DEBUG"
        os.environ["SCRIPTRAG_DEBUG"] = "true"

        # Force reconfiguration of logging
        from scriptrag.config import (
            clear_settings_cache,
            configure_logging,
            get_settings,
        )

        clear_settings_cache()
        settings = get_settings()
        configure_logging(settings)

        logger.debug("Debug mode enabled")
    elif verbose:
        import os

        # Set environment variable for verbose mode
        os.environ["SCRIPTRAG_LOG_LEVEL"] = "INFO"

        # Force reconfiguration of logging
        from scriptrag.config import (
            clear_settings_cache,
            configure_logging,
            get_settings,
        )

        clear_settings_cache()
        settings = get_settings()
        configure_logging(settings)

        logger.info("Verbose mode enabled")

    if config:
        # Load configuration from file
        from scriptrag.cli.validators.file_validator import ConfigFileValidator

        validator = ConfigFileValidator()
        try:
            config_path = validator.validate(config)
            logger.debug(f"Loading configuration from {config_path}")
            # Configuration loading would happen here
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")


def main() -> None:
    """Main CLI entry point."""
    app()


# Alias for backwards compatibility
cli = main


if __name__ == "__main__":
    main()
