"""Search command for ScriptRAG CLI."""

from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api.search import SearchAPI
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
            "-d",
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
        # Initialize search API
        search_api = SearchAPI.from_config()

        # Validate conflicting options
        if fuzzy and strict:
            console.print(
                "[red]Error:[/red] Cannot use both --fuzzy and --strict options",
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

    except FileNotFoundError as e:
        console.print(
            f"[red]Error:[/red] {e}",
            style="bold",
        )
        raise typer.Exit(1) from e
    except Exception as e:
        # Log full error details for debugging
        logger.error("Search failed: %s", str(e), exc_info=True)
        # Show sanitized error message to user
        console.print(
            "[red]Error:[/red] Search operation failed. "
            "Please check the logs for details.",
            style="bold",
        )
        raise typer.Exit(1) from e
