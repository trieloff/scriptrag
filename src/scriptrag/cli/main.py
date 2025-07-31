"""Main entry point for ScriptRAG CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.config import (
    get_settings,
    load_settings,
    setup_logging_for_environment,
)

# Import command groups
from .commands.bible import bible_app
from .commands.config import config_app
from .commands.database import db_app
from .commands.dev import dev_app
from .commands.mentor import mentor_app
from .commands.scene import scene_app
from .commands.script import script_app
from .commands.search import search_app
from .commands.server import server_app

# Create main Typer app
app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


@app.callback()
def main(
    config_file: Path | None = None,
    config_file_opt: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress output except errors")
    ] = False,
    environment: Annotated[
        str,
        typer.Option(
            "--env",
            "-e",
            help="Environment (development, testing, production)",
        ),
    ] = "development",
) -> None:
    """ScriptRAG: A Graph-Based Screenwriting Assistant.

    [bold green]Features:[/bold green]
    • Parse screenplays in Fountain format
    • Build and query graph databases
    • Semantic search with local LLMs
    • Scene management and timeline analysis
    • MCP server for AI assistant integration
    """
    try:
        # Set up logging level based on options
        if quiet:
            log_level = "ERROR"
        elif verbose:
            log_level = "DEBUG"
        else:
            log_level = "INFO"

        # Use config_file_opt if provided, otherwise use config_file
        actual_config_file = config_file_opt or config_file
        settings = (
            load_settings(actual_config_file) if actual_config_file else get_settings()
        )

        # Override environment if specified
        settings.environment = environment
        settings.logging.level = log_level

        # Set up logging
        setup_logging_for_environment(
            environment=settings.environment,
            log_file=settings.get_log_file_path(),
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        raise typer.Exit(1) from e


# Add command groups
app.add_typer(config_app)
app.add_typer(db_app)
app.add_typer(script_app)
app.add_typer(scene_app)
app.add_typer(search_app)
app.add_typer(dev_app)
app.add_typer(bible_app)
app.add_typer(server_app)
app.add_typer(mentor_app)


if __name__ == "__main__":
    app()
