"""CLI command for scriptrag index."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from scriptrag.api.index import IndexOperationResult
from scriptrag.config import get_logger, get_settings
from scriptrag.config.settings import ScriptRAGSettings

logger = get_logger(__name__)
console = Console()

app = typer.Typer()


@app.command()
def index_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Path to search for analyzed Fountain files "
                "(default: current directory)"
            )
        ),
    ] = None,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            "-d",
            help="Path to the SQLite database file",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be indexed without making changes",
        ),
    ] = False,
    no_recursive: Annotated[
        bool,
        typer.Option(
            "--no-recursive", help="Don't search recursively in subdirectories"
        ),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of scripts to process in each batch",
        ),
    ] = 10,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed information for each script"
        ),
    ] = False,
) -> None:
    """Index analyzed Fountain files into the database.

    This command:
    1. Finds all Fountain files with boneyard metadata
    2. Parses the scripts and extracts structured data
    3. Re-indexes all scripts to ensure data consistency
    4. Stores scripts, scenes, characters, dialogues, and actions in the database
    5. Creates relationships between entities for graph-based queries

    The database must be initialized first with 'scriptrag init'.

    Note: Scripts are always re-indexed to ensure the database reflects the current
    state of the files.
    Scripts should be analyzed first with 'scriptrag analyze' to add metadata.
    """
    try:
        from scriptrag.api.index import IndexCommand

        # Handle custom database path if provided
        if db_path is not None:
            settings = get_settings()
            # Apply db_path override
            updated_data = settings.model_dump()
            updated_data["database_path"] = db_path
            settings = ScriptRAGSettings(**updated_data)
            # Initialize index command with custom settings
            index_cmd = IndexCommand(settings=settings)
        else:
            # Initialize index command with default config
            index_cmd = IndexCommand.from_config()

        # Run with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Indexing screenplay files...", total=100)

            def update_progress(pct: float, msg: str) -> None:
                progress.update(task, completed=int(pct * 100), description=msg)

            result = asyncio.run(
                index_cmd.index(
                    path=path,
                    recursive=not no_recursive,
                    dry_run=dry_run,
                    batch_size=batch_size,
                    progress_callback=update_progress,
                )
            )

        # Display results
        _display_results(result, dry_run, verbose)

    except ImportError as e:  # pragma: no cover
        console.print(f"[red]Error: Required components not available: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Index command failed")
        raise typer.Exit(1) from e


def _display_results(
    result: IndexOperationResult, dry_run: bool, verbose: bool
) -> None:
    """Display indexing results.

    Args:
        result: IndexOperationResult from the index operation
        dry_run: Whether this was a dry run
        verbose: Whether to show detailed information
    """
    if dry_run:
        console.print(
            "\n[yellow]DRY RUN - No changes were made to the database[/yellow]"
        )
        console.print("\nWould index:")
    else:
        console.print("\n[green]Indexing complete![/green]")

    # Create summary table
    table = Table(title="Index Summary" if not dry_run else "Dry Run Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="bold")

    # Add summary rows
    table.add_row("Scripts Indexed", str(result.total_scripts_indexed))
    if result.total_scripts_updated > 0:
        table.add_row("Scripts Updated", str(result.total_scripts_updated))
    table.add_row("Scenes", str(result.total_scenes_indexed))
    table.add_row("Characters", str(result.total_characters_indexed))
    table.add_row("Dialogues", str(result.total_dialogues_indexed))
    table.add_row("Actions", str(result.total_actions_indexed))

    console.print("\n", table)

    # Show detailed script information if verbose
    if verbose and result.scripts:
        console.print("\n[bold]Script Details:[/bold]")
        for script_result in result.scripts:
            if script_result.indexed or script_result.error:
                # Try to make path relative for display
                try:
                    display_path = script_result.path.relative_to(Path.cwd())
                except ValueError:
                    display_path = script_result.path

                status = (
                    "[green]✓[/green]" if not script_result.error else "[red]✗[/red]"
                )
                update_marker = (
                    " [yellow](updated)[/yellow]" if script_result.updated else ""
                )

                console.print(
                    f"  {status} [cyan]{display_path}[/cyan]{update_marker}: "
                    f"{script_result.scenes_indexed} scenes, "
                    f"{script_result.characters_indexed} characters, "
                    f"{script_result.dialogues_indexed} dialogues, "
                    f"{script_result.actions_indexed} actions"
                )

                if script_result.error:
                    console.print(f"    [red]Error: {script_result.error}[/red]")

    # Show errors if any
    if result.errors:
        console.print(f"\n[red]Errors encountered: {len(result.errors)}[/red]")
        for i, error in enumerate(result.errors[:10], 1):  # Show first 10 errors
            console.print(f"  {i}. {error}")
        if len(result.errors) > 10:
            console.print(f"  ... and {len(result.errors) - 10} more errors")

    # Show helpful next steps
    if not dry_run and (
        result.total_scripts_indexed > 0 or result.total_scripts_updated > 0
    ):
        console.print("\n[dim]Next steps:[/dim]")
        console.print("  • Use 'scriptrag query' to search the indexed data")
        console.print("  • Use 'scriptrag stats' to view database statistics")
        console.print("  • Use 'scriptrag graph' to visualize relationships")
