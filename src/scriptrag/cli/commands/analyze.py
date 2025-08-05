"""CLI command for scriptrag analyze."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from scriptrag.config import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer()


@app.command()
def analyze_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to search for Fountain files (default: current directory)"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-processing of all scenes"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n",
            help="Show what would be updated without making changes"
        ),
    ] = False,
    no_recursive: Annotated[
        bool,
        typer.Option(
            "--no-recursive",
            help="Don't search recursively in subdirectories"
        ),
    ] = False,
    analyzer: Annotated[
        list[str] | None,
        typer.Option(
            "--analyzer", "-a",
            help="Additional analyzers to run (can be specified multiple times)"
        ),
    ] = None,
) -> None:
    """Analyze Fountain files and update their metadata.

    This command:
    1. Finds all Fountain files in the specified path
    2. Parses scenes and existing boneyard metadata
    3. Runs analyzers to extract semantic information
    4. Updates boneyard sections in the Fountain files
    
    Note: This command does not update the database.
    """
    try:
        from scriptrag.api.analyze import AnalyzeCommand

        # Initialize components
        analyze_cmd = AnalyzeCommand.from_config()

        # Load requested analyzers
        if analyzer:
            for analyzer_name in analyzer:
                try:
                    analyze_cmd.load_analyzer(analyzer_name)
                    logger.debug(f"Loaded analyzer: {analyzer_name}")
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Failed to load analyzer "
                        f"'{analyzer_name}': {e}[/yellow]"
                    )

        # Run with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing screenplay files...", total=None)

            def update_progress(_pct: float, msg: str) -> None:
                progress.update(task, description=msg)

            result = asyncio.run(
                analyze_cmd.analyze(
                    path=path,
                    recursive=not no_recursive,
                    force=force,
                    dry_run=dry_run,
                    progress_callback=update_progress,
                )
            )

        # Display results
        if dry_run:
            console.print("\n[yellow]DRY RUN - No files were modified[/yellow]")
            console.print("\nWould update:")
        else:
            console.print("\n[green]Updated:[/green]")

        if result.files:
            for file_result in result.files:
                if file_result.updated:
                    # Try to make path relative, but fall back to absolute if needed
                    try:
                        display_path = file_result.path.relative_to(Path.cwd())
                    except ValueError:
                        display_path = file_result.path

                    console.print(
                        f"  [cyan]{display_path}[/cyan]: "
                        f"{file_result.scenes_updated} scenes"
                    )
        else:
            console.print("  [dim]No files needed updating[/dim]")

        console.print(
            f"\nTotal: [bold]{result.total_scenes_updated}[/bold] scenes "
            f"in [bold]{result.total_files_updated}[/bold] files"
        )

        if result.errors:
            console.print(f"\n[red]Errors: {len(result.errors)}[/red]")
            for error in result.errors[:5]:  # Show first 5 errors
                console.print(f"  • {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

    except ImportError as e:
        console.print(f"[red]Error: Required components not available: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Analyze command failed")
        raise typer.Exit(1) from e
