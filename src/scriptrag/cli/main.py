"""Main entry point for ScriptRAG CLI.

This module creates the main Typer app and registers all command groups.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.config import get_logger, load_settings, setup_logging_for_environment

from .config import config_app

# Create main Typer app
app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()
logger = get_logger(__name__)


@app.callback()
def main(
    config_file: Path | None = None,
    config_file_opt: Annotated[
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
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging output",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """ScriptRAG: A Graph-Based Screenwriting Assistant.

    This tool provides comprehensive screenplay analysis using graph-based
    retrieval-augmented generation (GraphRAG) techniques.
    """
    # Handle version flag
    if version:
        import scriptrag

        __version__ = scriptrag.__version__

        console.print(f"ScriptRAG version {__version__}")
        raise typer.Exit()

    # Load configuration
    actual_config_file = config_file or config_file_opt
    if actual_config_file:
        try:
            load_settings(actual_config_file)
        except Exception as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            raise typer.Exit(1) from e
    else:
        # Configuration will be loaded on first access
        pass

    # Setup logging
    try:
        setup_logging_for_environment()
        if verbose:
            logger.info("Verbose logging enabled")
    except Exception:
        # Logging errors are non-fatal - silently continue
        logger.debug("Failed to setup logging")


# Register command groups
app.add_typer(config_app)

# Additional command groups would be imported and registered here
# when the full refactoring is complete
