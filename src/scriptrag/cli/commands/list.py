"""List fountain files command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from scriptrag.api import ScriptLister
from scriptrag.api.list import FountainMetadata

console = Console()


def list_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to search for Fountain files (default: current directory)",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    no_recursive: Annotated[
        bool,
        typer.Option(
            "--no-recursive",
            help="Don't search recursively in subdirectories",
        ),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    """List all Fountain scripts in the specified path.

    This command searches for .fountain files and extracts metadata including:
    - Title
    - Author
    - Episode/Season numbers (for series)
    - File path

    The command will automatically detect series information from the title page
    or filename.
    """
    from scriptrag.config.settings import ScriptRAGSettings

    # Load settings with proper precedence
    if config:
        settings = ScriptRAGSettings.from_multiple_sources(
            config_files=[config],
        )
        # Need to temporarily override the global settings
        import scriptrag.config.settings as settings_module

        settings_module._settings = settings

    lister = ScriptLister()

    try:
        # List scripts
        scripts = lister.list_scripts(path=path, recursive=not no_recursive)

        if not scripts:
            console.print(
                "[yellow]No Fountain scripts found.[/yellow]",
                style="bold",
            )
            return

        # Group scripts by title for series detection
        series_map: dict[str, list[FountainMetadata]] = {}
        standalone_scripts = []

        for script in scripts:
            if script.title and script.is_series:
                series_map.setdefault(script.title, []).append(script)
            else:
                standalone_scripts.append(script)

        # Create output table
        table = Table(title="Fountain Scripts", show_lines=True)
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Author", style="green")
        table.add_column("Episode", style="yellow", justify="center")
        table.add_column("Season", style="yellow", justify="center")
        table.add_column("File", style="blue", no_wrap=False)

        # Add series scripts first (grouped by title)
        for _title, episodes in sorted(series_map.items()):
            # Sort episodes by season and episode number
            episodes.sort(key=lambda x: (x.season_number or 0, x.episode_number or 0))
            for script in episodes:
                table.add_row(
                    script.title or script.file_path.stem,
                    script.author or "-",
                    str(script.episode_number) if script.episode_number else "-",
                    str(script.season_number) if script.season_number else "-",
                    (
                        str(script.file_path.relative_to(Path.cwd()))
                        if script.file_path.is_relative_to(Path.cwd())
                        else str(script.file_path)
                    ),
                )

        # Add standalone scripts
        for script in sorted(standalone_scripts, key=lambda x: x.display_title):
            table.add_row(
                script.title or script.file_path.stem,
                script.author or "-",
                "-",
                "-",
                (
                    str(script.file_path.relative_to(Path.cwd()))
                    if script.file_path.is_relative_to(Path.cwd())
                    else str(script.file_path)
                ),
            )

        console.print(table)
        console.print(
            f"\n[green]Found {len(scripts)} "
            f"script{'s' if len(scripts) != 1 else ''}[/green]"
        )

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to list scripts: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e
