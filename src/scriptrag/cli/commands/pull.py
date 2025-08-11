"""CLI command for scriptrag pull - convenience for init/index/analyze workflow."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings

logger = get_logger(__name__)
console = Console()

app = typer.Typer()


@app.command()
def pull_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to search for Fountain files (default: current directory)"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-processing of all scripts"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be done without making changes",
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
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    """Pull fountain files into the database (init + analyze + index).

    This convenience command performs a complete workflow:
    1. Initializes the database if it doesn't exist
    2. Analyzes Fountain files to update metadata
    3. Indexes the analyzed files into the database

    This is equivalent to running:
        scriptrag init  # if database doesn't exist
        scriptrag analyze [path]
        scriptrag index [path]
    """
    try:
        # Load settings
        if config:
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[config],
            )
        else:
            settings = get_settings()

        # Step 1: Check and initialize database if needed
        db_ops = DatabaseOperations(settings)
        if not db_ops.check_database_exists():
            if not dry_run:
                console.print("[yellow]Database not found. Initializing...[/yellow]")
                from scriptrag.api import DatabaseInitializer

                initializer = DatabaseInitializer()
                db_path = initializer.initialize_database(settings=settings)
                console.print(f"[green]✓[/green] Database initialized at {db_path}")
            else:
                console.print(
                    "[yellow]DRY RUN: Would initialize database "
                    f"at {settings.database_path}[/yellow]"
                )

        # Step 2: Analyze Fountain files
        console.print("\n[cyan]Step 1: Analyzing Fountain files...[/cyan]")
        analyze_cmd = AnalyzeCommand.from_config()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing screenplay files...", total=None)

            def analyze_progress(_pct: float, msg: str) -> None:
                progress.update(task, description=msg)

            analyze_result = asyncio.run(
                analyze_cmd.analyze(
                    path=path,
                    recursive=not no_recursive,
                    force=force,
                    dry_run=dry_run,
                    progress_callback=analyze_progress,
                )
            )

        if analyze_result.total_files_updated > 0 or force:
            console.print(
                f"[green]✓[/green] Analyzed {analyze_result.total_files_updated} "
                f"files ({analyze_result.total_scenes_updated} scenes)"
            )
        else:
            console.print("[dim]No files needed analysis updates[/dim]")

        # Step 3: Index into database
        console.print("\n[cyan]Step 2: Indexing into database...[/cyan]")
        index_cmd = IndexCommand.from_config()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Indexing screenplay files...", total=100)

            def index_progress(pct: float, msg: str) -> None:
                progress.update(task, completed=int(pct * 100), description=msg)

            index_result = asyncio.run(
                index_cmd.index(
                    path=path,
                    recursive=not no_recursive,
                    dry_run=dry_run,
                    batch_size=batch_size,
                    progress_callback=index_progress,
                )
            )

        has_indexed = (
            index_result.total_scripts_indexed > 0
            or index_result.total_scripts_updated > 0
        )
        if has_indexed:
            console.print(
                f"[green]✓[/green] Indexed {index_result.total_scripts_indexed} "
                f"new scripts, updated {index_result.total_scripts_updated}"
            )
            console.print(
                f"  • {index_result.total_scenes_indexed} scenes\n"
                f"  • {index_result.total_characters_indexed} characters\n"
                f"  • {index_result.total_dialogues_indexed} dialogues\n"
                f"  • {index_result.total_actions_indexed} actions"
            )
        else:
            console.print("[dim]No scripts needed indexing[/dim]")

        # Display summary
        if dry_run:
            console.print("\n[yellow]DRY RUN COMPLETE - No changes were made[/yellow]")
        else:
            console.print("\n[green]✓ Pull complete![/green]")

            if has_indexed:
                console.print("\n[dim]Next steps:[/dim]")
                console.print("  • Use 'scriptrag query' to search the indexed data")
                console.print("  • Use 'scriptrag watch' to monitor for changes")

        # Display errors if any
        all_errors = analyze_result.errors + index_result.errors
        if all_errors:
            console.print(f"\n[red]Errors encountered: {len(all_errors)}[/red]")
            for i, error in enumerate(all_errors[:5], 1):
                console.print(f"  {i}. {error}")
            if len(all_errors) > 5:
                console.print(f"  ... and {len(all_errors) - 5} more errors")

    except ImportError as e:
        console.print(f"[red]Error: Required components not available: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Pull command failed")
        raise typer.Exit(1) from e
