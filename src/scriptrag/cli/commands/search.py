"""Search command for ScriptRAG CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api.search import SearchAPI
from scriptrag.cli.utils.error_handler import handle_cli_error
from scriptrag.config import get_logger
from scriptrag.search.formatter import ResultFormatter

logger = get_logger(__name__)
console = Console()


def search_command(
    query: Annotated[
        str,
        typer.Argument(
            help=(
                "Search query (can include quoted dialogue, parentheticals, "
                "and CAPS for characters)"
            )
        ),
    ],
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            "-d",
            help="Path to the SQLite database file",
        ),
    ] = None,
    character: Annotated[
        str | None,
        typer.Option(
            "--character",
            "-c",
            help="Filter by character name",
        ),
    ] = None,
    dialogue: Annotated[
        str | None,
        typer.Option(
            "--dialogue",
            help="Search for specific dialogue",
        ),
    ] = None,
    parenthetical: Annotated[
        str | None,
        typer.Option(
            "--parenthetical",
            "-p",
            help="Search for parenthetical directions",
        ),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            help="Filter by project/script title",
        ),
    ] = None,
    range_filter: Annotated[
        str | None,
        typer.Option(
            "--range",
            "-r",
            help="Episode range (e.g., s1e2-s1e5)",
        ),
    ] = None,
    fuzzy: Annotated[
        bool,
        typer.Option(
            "--fuzzy",
            help="Enable fuzzy/vector search",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Disable vector search, use exact matching only",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of results to return",
        ),
    ] = 5,
    offset: Annotated[
        int,
        typer.Option(
            "--offset",
            "-o",
            help="Skip this many results (for pagination)",
        ),
    ] = 0,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show full scene content",
        ),
    ] = False,
    brief: Annotated[
        bool,
        typer.Option(
            "--brief",
            "-b",
            help="Show brief one-line results",
        ),
    ] = False,
    no_bible: Annotated[
        bool,
        typer.Option(
            "--no-bible",
            help="Exclude bible content from search results",
        ),
    ] = False,
    only_bible: Annotated[
        bool,
        typer.Option(
            "--only-bible",
            help="Search only bible content, exclude script scenes",
        ),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    """Search through indexed screenplays.

    This command searches through all indexed scripts in the database.

    Examples:
        # Simple text search
        scriptrag search "the adventure begins"

        # Search for character dialogue
        scriptrag search --character SARAH "take the notebook"

        # Auto-detect components
        scriptrag search SARAH "take the notebook" "(whisper)"

        # Search within a project
        scriptrag search --project "The Great Adventure" "begins"

        # Search specific episodes
        scriptrag search --range s1e2-s1e5 "coffee"

        # Pagination
        scriptrag search "dialogue" --limit 10 --offset 10

    The search automatically detects:
    - ALL CAPS words as characters or locations
    - "Quoted text" as dialogue
    - (Parenthetical text) as stage directions

    By default, queries longer than 10 words trigger vector search.
    Use --strict to disable this or --fuzzy to always enable it.
    """
    try:
        import copy

        from scriptrag.config import get_settings
        from scriptrag.config.settings import ScriptRAGSettings

        # Load settings with proper precedence
        if config:
            if not config.exists():
                console.print(f"[red]Error: Config file not found: {config}[/red]")
                raise typer.Exit(1)

            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[config],
            )
        else:
            # Use default settings
            settings = get_settings()

        # Apply db_path override if provided
        if db_path:
            # Create a copy with the new db_path
            settings = copy.deepcopy(settings)
            settings.database_path = db_path

        # Initialize search API
        search_api = SearchAPI(settings=settings)

        # Validate conflicting options
        if fuzzy and strict:
            console.print(
                "[red]Error:[/red] Cannot use both --fuzzy and --strict options",
                style="bold",
            )
            raise typer.Exit(1)

        if no_bible and only_bible:
            console.print(
                "[red]Error:[/red] Cannot use both --no-bible and --only-bible options",
                style="bold",
            )
            raise typer.Exit(1)

        # Execute search
        response = search_api.search(
            query=query,
            character=character,
            dialogue=dialogue,
            parenthetical=parenthetical,
            project=project,
            range_str=range_filter,
            fuzzy=fuzzy,
            strict=strict,
            limit=limit,
            offset=offset,
            include_bible=not no_bible,
            only_bible=only_bible,
        )

        # Format and display results
        formatter = ResultFormatter(console)

        if brief:
            # Brief one-line format
            brief_text = formatter.format_brief(response)
            console.print(brief_text)
        else:
            # Full formatted display
            formatter.format_results(response, verbose=verbose)

    except typer.Exit:
        # Re-raise typer.Exit without handling it
        raise
    except Exception as e:
        handle_cli_error(e, verbose=verbose)
