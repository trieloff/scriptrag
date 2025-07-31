"""Search and query commands for ScriptRAG CLI."""

import asyncio
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from scriptrag.config import get_logger
from scriptrag.database import get_connection
from scriptrag.search import SearchInterface, SearchType

# Create search app
search_app = typer.Typer(
    name="search",
    help="Search and query commands",
    rich_markup_mode="rich",
)

console = Console()


@search_app.command("all")
def search_all(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
    min_score: Annotated[
        float, typer.Option("--min-score", help="Minimum relevance score")
    ] = 0.1,
) -> None:
    """Search across all content types."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        console.print(f"[blue]Searching for:[/blue] {query}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search(
                        query=query,
                        limit=limit,
                        min_score=min_score,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@search_app.command("dialogue")
def search_dialogue(
    query: Annotated[str, typer.Argument(help="Search query")],
    character: Annotated[
        str | None, typer.Option("--character", "-c", help="Filter by character")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
) -> None:
    """Search dialogue content."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        console.print(f"[blue]Searching dialogue for:[/blue] {query}")
        if character:
            console.print(f"[blue]Character filter:[/blue] {character}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search_dialogue(
                        query=query,
                        character=character,
                        limit=limit,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Dialogue search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@search_app.command("scenes")
def search_scenes(
    query: Annotated[str, typer.Argument(help="Search query")],
    character: Annotated[
        str | None, typer.Option("--character", "-c", help="Filter by character")
    ] = None,
    location: Annotated[
        str | None, typer.Option("--location", "-l", help="Filter by location")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
) -> None:
    """Search scenes by content or filters."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        console.print(f"[blue]Searching scenes for:[/blue] {query}")
        if character:
            console.print(f"[blue]Character filter:[/blue] {character}")
        if location:
            console.print(f"[blue]Location filter:[/blue] {location}")

        filters = {}
        if character:
            filters["character"] = character
        if location:
            filters["location"] = location

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search(
                        query=query,
                        search_types=[SearchType.SCENE],
                        entity_filter=filters,
                        limit=limit,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Scene search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@search_app.command("similar")
def search_similar(
    scene_id: Annotated[
        str, typer.Argument(help="Scene ID to find similar scenes for")
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
    min_similarity: Annotated[
        float, typer.Option("--min-similarity", help="Minimum similarity score")
    ] = 0.3,
) -> None:
    """Find scenes similar to a given scene using embeddings."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        console.print(f"[blue]Finding scenes similar to:[/blue] {scene_id}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search_similar_scenes(
                        scene_id=scene_id,
                        limit=limit,
                        min_similarity=min_similarity,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results, show_similarity=True)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Similar search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@search_app.command("theme")
def search_theme(
    theme: Annotated[str, typer.Argument(help="Theme or mood to search for")],
    entity_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by entity type")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
) -> None:
    """Search for content matching a theme or mood using semantic search."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        console.print(f"[blue]Searching for theme:[/blue] {theme}")
        if entity_type:
            console.print(f"[blue]Entity type filter:[/blue] {entity_type}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search_by_theme(
                        theme=theme,
                        entity_type=entity_type,
                        limit=limit,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results, show_similarity=True)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Theme search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@search_app.command("temporal")
def search_temporal(
    day_night: Annotated[
        str | None, typer.Option("--day-night", help="Filter by DAY or NIGHT")
    ] = None,
    start_time: Annotated[
        str | None, typer.Option("--start-time", help="Story time range start")
    ] = None,
    end_time: Annotated[
        str | None, typer.Option("--end-time", help="Story time range end")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of results")
    ] = 10,
) -> None:
    """Search based on temporal criteria."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        if day_night:
            console.print(f"[blue]Time of day:[/blue] {day_night}")
        if start_time or end_time:
            console.print(
                f"[blue]Time range:[/blue] "
                f"{start_time or 'beginning'} to {end_time or 'end'}"
            )

        time_range = None
        if start_time or end_time:
            time_range = (start_time, end_time)

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                try:
                    return await search.search_temporal(
                        time_range=time_range,
                        day_night=day_night,
                        limit=limit,
                    )
                finally:
                    await search.close()

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Temporal search error", error=str(e))
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


def _display_search_results(results: list, show_similarity: bool = False) -> None:
    """Display search results in a formatted table."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(
        title=f"Search Results ({len(results)} found)",
        show_header=True,
        header_style="bold blue",
    )

    table.add_column("Type", style="cyan", width=12)
    table.add_column("Content", style="white", width=50)
    if show_similarity:
        table.add_column("Score", style="green", width=8)
    table.add_column("Details", style="dim", width=30)

    for result in results:
        # Format content with highlights
        content = result["content"]
        if result.get("highlights"):
            content = result["highlights"][0]

        # Truncate long content
        if len(content) > 50:
            content = content[:47] + "..."

        # Format metadata
        metadata = result.get("metadata", {})
        details = []
        if "character" in metadata:
            details.append(f"Character: {metadata['character']}")
        if "scene_heading" in metadata:
            scene = metadata["scene_heading"]
            if len(scene) > 25:
                scene = scene[:22] + "..."
            details.append(f"Scene: {scene}")

        detail_str = "\n".join(details) if details else ""

        if show_similarity:
            score = f"{result['score']:.3f}"
            table.add_row(result["type"], content, score, detail_str)
        else:
            table.add_row(result["type"], content, detail_str)

    console.print(table)
