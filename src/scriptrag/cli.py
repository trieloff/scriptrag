"""Command-line interface for ScriptRAG.

This module provides a comprehensive CLI for ScriptRAG operations including
script parsing, searching, configuration management, and development utilities.
"""

import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from . import ScriptRAG
from .config import (
    create_default_config,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)

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


# Configuration management commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    rich_markup_mode="rich",
)
app.add_typer(config_app)


@config_app.command("init")
def config_init(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output path for configuration file",
        ),
    ] = Path("config.yaml"),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing configuration file",
        ),
    ] = False,
) -> None:
    """Initialize a new configuration file with default settings."""
    if output.exists() and not force:
        print(f"Configuration file already exists: {output}", file=sys.stderr)
        print("Use --force to overwrite", file=sys.stderr)
        raise typer.Exit(1)

    try:
        create_default_config(output)
        console.print(f"[green]✓[/green] Configuration created: {output}")
        console.print("[dim]Edit the file to customize your settings[/dim]")
    except Exception as e:
        print(f"Error creating configuration: {e}", file=sys.stderr)
        raise typer.Exit(1) from e


@config_app.command("show")
def config_show(
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
        ),
    ] = None,
    section: Annotated[
        str | None,
        typer.Option(
            "--section",
            "-s",
            help="Show only specific section (database, llm, logging, etc.)",
        ),
    ] = None,
) -> None:
    """Display current configuration settings."""
    try:
        settings = load_settings(config_file) if config_file else get_settings()

        if section:
            # Show specific section
            if hasattr(settings, section):
                section_data = getattr(settings, section)
                console.print(f"[bold blue]{section}:[/bold blue]")
                if hasattr(section_data, "model_dump"):
                    # Pydantic model
                    for key, value in section_data.model_dump().items():
                        console.print(f"  {key}: {value}")
                else:
                    # Regular value
                    console.print(f"  {section_data}")
            else:
                available_sections = [
                    attr
                    for attr in dir(settings)
                    if not attr.startswith("_") and attr != "model_dump"
                ]
                console.print(f"[red]Unknown section: {section}[/red]")
                console.print(f"Available sections: {', '.join(available_sections)}")
                raise typer.Exit(1)
        else:
            # Show all configuration
            console.print("[bold blue]Current Configuration:[/bold blue]")
            if hasattr(settings, "model_dump"):
                config_dict = settings.model_dump()
                for section_name, section_data in config_dict.items():
                    console.print(f"\n[bold]{section_name}:[/bold]")
                    if isinstance(section_data, dict):
                        for key, value in section_data.items():
                            console.print(f"  {key}: {value}")
                    else:
                        console.print(f"  {section_data}")

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        raise typer.Exit(1) from e


@config_app.command("validate")
def config_validate(
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file to validate",
        ),
    ] = None,
) -> None:
    """Validate configuration file."""
    try:
        if config_file:
            settings = load_settings(config_file)
            console.print(
                f"[green]✓[/green] Configuration file is valid: {config_file}"
            )
        else:
            settings = get_settings()
            console.print("[green]✓[/green] Default configuration is valid")

        # Additional validation checks
        errors = []

        # Check database path
        if hasattr(settings, "database") and hasattr(settings.database, "path"):
            db_path = Path(settings.database.path)
            if not db_path.parent.exists():
                errors.append(f"Database directory does not exist: {db_path.parent}")

        if errors:
            console.print("[yellow]⚠[/yellow] Configuration warnings:")
            for error in errors:
                console.print(f"  • {error}")
        else:
            console.print("[green]✓[/green] All configuration checks passed")

    except Exception as e:
        print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
        raise typer.Exit(1) from e


# Script management commands
script_app = typer.Typer(
    name="script",
    help="Screenplay parsing and management commands",
    rich_markup_mode="rich",
)
app.add_typer(script_app)


@script_app.command("parse")
def script_parse(
    script_path: Annotated[
        Path,
        typer.Argument(
            help="Path to Fountain screenplay file",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    output_db: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output database path (default: from config)",
        ),
    ] = None,
) -> None:
    """Parse a Fountain screenplay into the graph database."""
    try:
        settings = get_settings()
        db_path = output_db or Path(settings.database.path)

        console.print(f"[blue]Parsing screenplay:[/blue] {script_path}")
        console.print(f"[blue]Database:[/blue] {db_path}")

        # Initialize ScriptRAG and parse
        scriptrag = ScriptRAG(db_path=str(db_path))
        scriptrag.parse_fountain(str(script_path))

        console.print("[green]✓[/green] Successfully parsed screenplay")
        console.print(
            "[dim]Detailed parsing results will be available in future versions[/dim]"
        )

    except Exception as e:
        print(f"Error parsing screenplay: {e}", file=sys.stderr)
        raise typer.Exit(1) from e


@script_app.command("info")
def script_info(
    script_path: Annotated[
        Path | None,
        typer.Argument(help="Path to Fountain screenplay file"),
    ] = None,
) -> None:
    """Display information about a screenplay or database."""
    if script_path:
        # Show info about a specific script file
        if not script_path.exists():
            print(f"Script file not found: {script_path}", file=sys.stderr)
            raise typer.Exit(1)

        # Basic file info for now
        stat = script_path.stat()
        console.print(f"[bold blue]Screenplay Info:[/bold blue] {script_path}")
        console.print(f"Size: {stat.st_size:,} bytes")
        console.print(f"Modified: {stat.st_mtime}")

        # TODO: Parse and show more detailed info
        console.print(
            "[dim]Detailed screenplay analysis will be available "
            "in future versions[/dim]"
        )
    else:
        # Show info about current database
        settings = get_settings()
        db_path = Path(settings.database.path)

        if db_path.exists():
            console.print(f"[bold blue]Database Info:[/bold blue] {db_path}")
            console.print(f"Size: {db_path.stat().st_size:,} bytes")

            # TODO: Query database for more info
            console.print(
                "[dim]Database statistics will be available in future versions[/dim]"
            )
        else:
            console.print(
                "[yellow]No database found. Use 'scriptrag script parse' "
                "to create one.[/yellow]"
            )


# Search commands
search_app = typer.Typer(
    name="search",
    help="Search and query commands",
    rich_markup_mode="rich",
)
app.add_typer(search_app)


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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

    try:
        console.print(f"[blue]Searching for:[/blue] {query}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                results = await search.search(
                    query=query,
                    limit=limit,
                    min_score=min_score,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

    try:
        console.print(f"[blue]Searching dialogue for:[/blue] {query}")
        if character:
            console.print(f"[blue]Character filter:[/blue] {character}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                results = await search.search_dialogue(
                    query=query,
                    character=character,
                    limit=limit,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface, SearchType

    try:
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
                results = await search.search(
                    query=query,
                    search_types=[SearchType.SCENE],
                    entity_filter=filters,
                    limit=limit,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

    try:
        console.print(f"[blue]Finding scenes similar to:[/blue] {scene_id}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                results = await search.search_similar_scenes(
                    scene_id=scene_id,
                    limit=limit,
                    min_similarity=min_similarity,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results, show_similarity=True)

    except Exception as e:
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

    try:
        console.print(f"[blue]Searching for theme:[/blue] {theme}")
        if entity_type:
            console.print(f"[blue]Entity type filter:[/blue] {entity_type}")

        async def run_search() -> Any:
            with get_connection() as conn:
                search = SearchInterface(conn)
                results = await search.search_by_theme(
                    theme=theme,
                    entity_type=entity_type,
                    limit=limit,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results, show_similarity=True)

    except Exception as e:
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

    try:
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
                results = await search.search_temporal(
                    time_range=time_range,
                    day_night=day_night,
                    limit=limit,
                )
                await search.close()
                return results

        results = asyncio.run(run_search())
        _display_search_results(results)

    except Exception as e:
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


# Development commands
dev_app = typer.Typer(
    name="dev",
    help="Development and debugging commands",
    rich_markup_mode="rich",
)
app.add_typer(dev_app)


@dev_app.command("init")
def dev_init(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force initialization even if files exist",
        ),
    ] = False,
) -> None:
    """Initialize development environment with sample data."""
    console.print("[blue]Initializing development environment...[/blue]")

    # Create sample directories
    dirs_to_create = [
        "data/scripts",
        "data/databases",
        "logs",
        "temp",
    ]

    for dir_path in dirs_to_create:
        path = Path(dir_path)
        if path.exists() and not force:
            console.print(f"[yellow]Directory exists:[/yellow] {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created:[/green] {path}")

    # Create sample config if it doesn't exist
    config_path = Path("config.yaml")
    if not config_path.exists() or force:
        try:
            create_default_config(config_path)
            console.print(f"[green]Created:[/green] {config_path}")
        except Exception as e:
            console.print(f"[red]Error creating config:[/red] {e}")

    console.print("[green]✓[/green] Development environment initialized")


@dev_app.command("status")
def dev_status() -> None:
    """Show development environment status."""
    console.print("[bold blue]Development Environment Status[/bold blue]")

    # Check key files and directories
    checks = [
        ("Configuration", Path("config.yaml")),
        ("Scripts directory", Path("data/scripts")),
        ("Database directory", Path("data/databases")),
        ("Logs directory", Path("logs")),
    ]

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Path")

    for name, path in checks:
        status = "[green]✓ Exists[/green]" if path.exists() else "[red]✗ Missing[/red]"
        table.add_row(name, status, str(path))

    console.print(table)


@dev_app.command("test-llm")
def dev_test_llm() -> None:
    """Test LLM connection and basic functionality."""
    console.print("[blue]Testing LLM connection...[/blue]")

    try:
        import requests

        settings = get_settings()

        # Test embeddings endpoint
        embed_url = f"{settings.llm.endpoint}/embeddings"
        embed_data = {"input": "test", "model": settings.llm.embedding_model}

        console.print(f"[dim]Testing embeddings: {embed_url}[/dim]")
        embed_response = requests.post(embed_url, json=embed_data, timeout=10)

        if embed_response.status_code == 200:
            console.print("[green]✓[/green] Embeddings endpoint working")
        else:
            console.print(
                f"[red]✗[/red] Embeddings endpoint error: {embed_response.status_code}"
            )

        # Test completion endpoint
        completion_url = f"{settings.llm.endpoint}/chat/completions"
        completion_data = {
            "model": settings.llm.default_model,
            "messages": [{"role": "user", "content": "Say 'test successful'"}],
            "max_tokens": 10,
        }

        console.print(f"[dim]Testing completions: {completion_url}[/dim]")
        completion_response = requests.post(
            completion_url, json=completion_data, timeout=10
        )

        if completion_response.status_code == 200:
            console.print("[green]✓[/green] Completion endpoint working")
            result = completion_response.json()
            if result.get("choices"):
                message = result["choices"][0]["message"]["content"]
                console.print(f"[dim]Response: {message.strip()}[/dim]")
        else:
            console.print(
                f"[red]✗[/red] Completion endpoint error: "
                f"{completion_response.status_code}"
            )

    except Exception as e:
        console.print(f"[red]✗[/red] LLM test failed: {e}")
        raise typer.Exit(1) from e


# Server commands
server_app = typer.Typer(
    name="server",
    help="MCP server commands",
    rich_markup_mode="rich",
)
app.add_typer(server_app)


@server_app.command("start")
def server_start() -> None:
    """Start the MCP server."""
    console.print("[blue]Starting ScriptRAG MCP server...[/blue]")
    console.print("[yellow]⚠[/yellow] MCP server functionality is not yet implemented")
    console.print("This command will be available in Phase 5 of development")


if __name__ == "__main__":
    app()
