"""Command-line interface for ScriptRAG.

This module provides a comprehensive CLI for ScriptRAG operations including
script parsing, searching, configuration management, and development utilities.
"""

# Standard library imports
import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

# Third-party imports
import requests
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Local imports
from . import ScriptRAG
from .config import (
    create_default_config,
    get_logger,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)
from .database import get_connection
from .database.bible import ScriptBibleOperations
from .database.connection import DatabaseConnection
from .database.continuity import ContinuityValidator
from .database.operations import GraphOperations
from .database.statistics import DatabaseStatistics
from .mentors.base import MentorAnalysis, MentorResult
from .models import SceneOrderType
from .parser.bulk_import import BulkImporter
from .scene_manager import SceneManager
from .search import SearchInterface, SearchType

# Optional imports for server functionality
create_app: Callable[[], Any] | None = None
with contextlib.suppress(ImportError):
    from scriptrag.api.app import create_app

# Create main Typer app
app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()
logger = get_logger(__name__)


def get_latest_script_id(connection: DatabaseConnection) -> tuple[str, str] | None:
    """Get the latest script ID and title from the database.

    Args:
        connection: Database connection instance

    Returns:
        Tuple of (script_id, script_title) or None if no scripts found
    """
    with connection.transaction() as conn:
        result = conn.execute(
            """
            SELECT id, json_extract(properties_json, '$.title') as title
            FROM nodes
            WHERE node_type = 'script'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()

        if result:
            return (result[0], result[1])
        return None


def get_latest_script_id_only(connection: DatabaseConnection) -> str | None:
    """Get only the latest script ID from the database.

    Args:
        connection: Database connection instance

    Returns:
        Script ID or None if no scripts found
    """
    result = get_latest_script_id(connection)
    return result[0] if result else None


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
    logger = get_logger(__name__)

    if output.exists() and not force:
        logger.error("Configuration file already exists", path=str(output))
        console.print(f"[red]Configuration file already exists: {output}[/red]")
        console.print("[yellow]Use --force to overwrite[/yellow]")
        raise typer.Exit(1)

    try:
        create_default_config(output)
        logger.info("Configuration file created", path=str(output))
        console.print(f"[green]✓[/green] Configuration created: {output}")
        console.print("[dim]Edit the file to customize your settings[/dim]")
    except Exception as e:
        logger.error("Error creating configuration", error=str(e))
        console.print(f"[red]Error creating configuration: {e}[/red]")
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
        logger = get_logger(__name__)
        logger.error("Error loading configuration", error=str(e))
        console.print(f"[red]Error loading configuration: {e}[/red]")
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
        logger = get_logger(__name__)
        logger.error("Configuration validation failed", error=str(e))
        console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
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

        # Initialize ScriptRAG and parse with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Parsing fountain file...", total=None)

            scriptrag = ScriptRAG(db_path=str(db_path))
            script = scriptrag.parse_fountain(str(script_path))

            progress.update(task, description="Building graph database...")

        # Show results
        console.print("\n[green]✓[/green] Successfully parsed screenplay")

        # Get script stats from database
        connection = DatabaseConnection(str(db_path))
        with connection.transaction() as conn:
            scene_count = conn.execute(
                """
                SELECT COUNT(*) FROM nodes
                WHERE node_type = 'scene'
                AND id IN (
                    SELECT to_node_id FROM edges
                    WHERE from_node_id = (
                        SELECT id FROM nodes
                        WHERE node_type = 'script'
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) AND edge_type = 'HAS_SCENE'
                )
                """
            ).fetchone()[0]

            char_count = conn.execute(
                """
                SELECT COUNT(*) FROM nodes
                WHERE node_type = 'character'
                AND id IN (
                    SELECT to_node_id FROM edges
                    WHERE from_node_id = (
                        SELECT id FROM nodes
                        WHERE node_type = 'script'
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) AND edge_type = 'HAS_CHARACTER'
                )
                """
            ).fetchone()[0]

        # Import Table locally to avoid scope issues in CI
        from rich.table import Table as RichTable

        # Display summary table
        table = RichTable(show_header=False, box=None)
        table.add_column("", style="dim")
        table.add_column("", style="bold")

        table.add_row("Title:", script.title)
        table.add_row("Scenes:", str(scene_count))
        table.add_row("Characters:", str(char_count))
        if script.author:
            table.add_row("Author:", script.author)

        console.print(table)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error parsing screenplay", error=str(e))
        console.print(f"[red]Error parsing screenplay: {e}[/red]")
        raise typer.Exit(1) from e


@script_app.command("import")
def script_import(
    path_or_pattern: Annotated[
        str,
        typer.Argument(help="Directory path or glob pattern for fountain files"),
    ],
    pattern: Annotated[
        str | None,
        typer.Option(
            "--pattern",
            "-p",
            help="Custom regex pattern for season/episode extraction",
        ),
    ] = None,
    series_name: Annotated[
        str | None,
        typer.Option(
            "--series-name",
            "-s",
            help="Override auto-detected series name",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-d",
            help="Preview what would be imported without actually importing",
        ),
    ] = False,
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing",
            help="Skip files that already exist in database",
        ),
    ] = True,
    update_existing: Annotated[
        bool,
        typer.Option(
            "--update-existing",
            help="Update existing scripts if file is newer",
        ),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of files to process per transaction batch",
        ),
    ] = 10,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Recursively search directories for fountain files",
        ),
    ] = True,
) -> None:
    r"""Import multiple fountain files with TV series support.

    Examples:
        # Import entire TV series
        scriptrag script import "Breaking Bad/**/*.fountain"

        # Import with custom pattern
        scriptrag script import "*.fountain" \\
            --pattern "S(?P<season>\d+)E(?P<episode>\d+)"

        # Preview import
        scriptrag script import "Season*/*.fountain" --dry-run

        # Import from directory
        scriptrag script import ./scripts/
    """
    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        # Ensure database is initialized with schema
        from scriptrag.database import initialize_database

        if not db_path.exists():
            console.print("[blue]Initializing database...[/blue]")
            if not initialize_database(db_path):
                console.print("[red]Failed to initialize database[/red]")
                raise typer.Exit(1)

        # Find fountain files
        file_paths = []
        path = Path(path_or_pattern)

        if path.is_dir():
            # Directory provided - search for fountain files
            if recursive:
                file_paths = list(path.rglob("*.fountain"))
            else:
                file_paths = list(path.glob("*.fountain"))
        else:
            # Assume it's a glob pattern
            # Use Path.glob for pattern matching
            if recursive:
                file_paths = list(Path().rglob(path_or_pattern))
            else:
                file_paths = list(Path().glob(path_or_pattern))

        if not file_paths:
            console.print(
                "[yellow]No fountain files found matching the pattern[/yellow]"
            )
            raise typer.Exit(0)

        console.print(f"[blue]Found {len(file_paths)} fountain files[/blue]")

        # Check bulk import size limit to prevent resource exhaustion
        max_bulk_import_size = 1000
        if len(file_paths) > max_bulk_import_size:
            console.print(
                f"[red]Error: Too many files ({len(file_paths)}). "
                f"Maximum allowed is {max_bulk_import_size}.[/red]"
            )
            console.print(
                "[yellow]Consider importing in smaller batches or "
                "using more specific patterns.[/yellow]"
            )
            raise typer.Exit(1)

        # Initialize database connection and operations
        conn = DatabaseConnection(db_path)
        graph_ops = GraphOperations(conn)

        # Create bulk importer
        importer = BulkImporter(
            graph_ops=graph_ops,
            custom_pattern=pattern,
            skip_existing=skip_existing,
            update_existing=update_existing,
            batch_size=batch_size,
        )

        # Import with progress tracking
        if dry_run:
            console.print("[yellow]DRY RUN MODE - No files will be imported[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Importing files...", total=len(file_paths))

            def update_progress(pct: float, msg: str) -> None:
                progress.update(
                    task, completed=int(pct * len(file_paths)), description=msg
                )

            result = importer.import_files(
                file_paths=file_paths,
                series_name_override=series_name,
                dry_run=dry_run,
                progress_callback=update_progress if not dry_run else None,
            )

        # Display results
        if dry_run:
            console.print("\n[bold]Import Preview:[/bold]")
        else:
            console.print("\n[bold]Import Results:[/bold]")

        # Import Table locally to avoid scope issues in CI
        from rich.table import Table as RichTable

        table = RichTable(show_header=True, header_style="bold blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")

        table.add_row("Total files", str(result.total_files))
        table.add_row(
            "Successful imports", f"[green]{result.successful_imports}[/green]"
        )
        table.add_row("Failed imports", f"[red]{result.failed_imports}[/red]")
        table.add_row("Skipped files", f"[yellow]{result.skipped_files}[/yellow]")

        console.print(table)

        # Show errors if any
        if result.errors:
            console.print("\n[red]Import Errors:[/red]")
            for file_path, error in list(result.errors.items())[:5]:
                console.print(f"  • {file_path}: {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more errors")

        # Show created series
        if result.series_created:
            console.print("\n[green]Created TV Series:[/green]")
            for series_name in result.series_created:
                console.print(f"  • {series_name}")

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error during import", error=str(e))
        console.print(f"[red]Error during import: {e}[/red]")
        raise typer.Exit(1) from e


@script_app.command("info")
def script_info(
    script_path: Annotated[
        Path | None,
        typer.Argument(help="Path to Fountain screenplay file"),
    ] = None,
) -> None:
    """Display information about a screenplay or database."""
    logger = get_logger(__name__)

    if script_path:
        # Show info about a specific script file
        if not script_path.exists():
            logger.error("Script file not found", path=str(script_path))
            console.print(f"[red]Script file not found: {script_path}[/red]")
            raise typer.Exit(1)

        # Basic file info for now
        stat = script_path.stat()
        console.print(f"[bold blue]Screenplay Info:[/bold blue] {script_path}")
        console.print(f"Size: {stat.st_size:,} bytes")
        console.print(f"Modified: {stat.st_mtime}")

        # Log placeholder usage
        logger.warning(
            "info command placeholder - screenplay analysis not implemented",
            script_path=str(script_path),
        )

        # Not yet implemented - tracking in issue #TODO-012
        console.print(
            "[yellow]⚠️  Detailed screenplay analysis not yet implemented[/yellow]"
        )
        console.print(
            "[dim]This feature is planned for a future release. "
            "Track progress at issue #TODO-012[/dim]"
        )
    else:
        # Show info about current database
        settings = get_settings()
        db_path = Path(settings.database.path)

        if db_path.exists():
            console.print(f"[bold blue]Database Info:[/bold blue] {db_path}")

            # Ensure database is initialized with schema
            from scriptrag.database import initialize_database

            if not initialize_database(db_path):
                console.print("[red]Failed to initialize database[/red]")
                raise typer.Exit(1)

            # Get and display database statistics
            with get_connection() as conn:
                stats_collector = DatabaseStatistics(conn)
                stats = stats_collector.get_all_statistics()

                # Import Table locally to avoid scope issues in tests
                from rich.table import Table as RichTable

                # Database Overview
                db_metrics: dict[str, Any] = stats["database"]
                console.print(f"\nSize: {db_metrics['file_size']:,} bytes")

                # Entity Summary Table
                console.print("\n[bold cyan]Entity Summary[/bold cyan]")
                entity_table = RichTable(show_header=True, header_style="bold")
                entity_table.add_column("Entity Type", style="dim")
                entity_table.add_column("Count", justify="right")

                entity_table.add_row("Scripts", f"{db_metrics['total_scripts']:,}")
                entity_table.add_row("Scenes", f"{db_metrics['total_scenes']:,}")
                entity_table.add_row(
                    "Characters", f"{db_metrics['total_characters']:,}"
                )
                entity_table.add_row("Locations", f"{db_metrics['total_locations']:,}")
                entity_table.add_row("Episodes", f"{db_metrics['total_episodes']:,}")
                entity_table.add_row("Seasons", f"{db_metrics['total_seasons']:,}")
                console.print(entity_table)

                # Graph Statistics
                graph_stats: dict[str, Any] = stats["graph"]
                if graph_stats["total_nodes"] > 0:
                    console.print("\n[bold cyan]Graph Statistics[/bold cyan]")
                    graph_table = RichTable(show_header=True, header_style="bold")
                    graph_table.add_column("Metric", style="dim")
                    graph_table.add_column("Value", justify="right")

                    graph_table.add_row(
                        "Total Nodes", f"{graph_stats['total_nodes']:,}"
                    )
                    graph_table.add_row(
                        "Total Edges", f"{graph_stats['total_edges']:,}"
                    )
                    graph_table.add_row(
                        "Average Degree", f"{graph_stats['avg_degree']}"
                    )
                    graph_table.add_row(
                        "Graph Density", f"{graph_stats['graph_density']:.4f}"
                    )
                    console.print(graph_table)

                    # Node types breakdown
                    if graph_stats["node_types"]:
                        console.print("\n[bold]Node Types:[/bold]")
                        for node_type, count in graph_stats["node_types"].items():
                            console.print(f"  • {node_type}: {count:,}")

                    # Edge types breakdown
                    if graph_stats["edge_types"]:
                        console.print("\n[bold]Edge Types:[/bold]")
                        for edge_type, count in graph_stats["edge_types"].items():
                            console.print(f"  • {edge_type}: {count:,}")

                # Embedding Statistics
                embed_stats: dict[str, Any] = stats["embeddings"]
                if embed_stats["total_embeddings"] > 0:
                    console.print("\n[bold cyan]Embedding Coverage[/bold cyan]")
                    embed_table = RichTable(show_header=True, header_style="bold")
                    embed_table.add_column("Metric", style="dim")
                    embed_table.add_column("Value", justify="right")

                    embed_table.add_row(
                        "Total Embeddings", f"{embed_stats['total_embeddings']:,}"
                    )
                    embed_table.add_row(
                        "Embedded Scripts", f"{embed_stats['embedded_scripts']}"
                    )
                    embed_table.add_row(
                        "Embedded Scenes", f"{embed_stats['embedded_scenes']}"
                    )
                    embed_table.add_row(
                        "Coverage", f"{embed_stats['coverage_percentage']:.1f}%"
                    )
                    console.print(embed_table)

                    if embed_stats["embedding_models"]:
                        console.print("\n[bold]Embedding Models:[/bold]")
                        for model, count in embed_stats["embedding_models"].items():
                            console.print(f"  • {model}: {count:,} embeddings")

                # Usage Patterns
                usage: dict[str, Any] = stats["usage"]

                # Most connected characters
                if usage["most_connected_characters"]:
                    console.print("\n[bold cyan]Most Connected Characters[/bold cyan]")
                    char_table = RichTable(show_header=True, header_style="bold")
                    char_table.add_column("Character", style="bold")
                    char_table.add_column("Connections", justify="right")

                    for char in usage["most_connected_characters"][:5]:
                        char_table.add_row(char["name"], str(char["connections"]))
                    console.print(char_table)

                # Longest scripts
                if usage["longest_scripts"]:
                    console.print("\n[bold cyan]Longest Scripts[/bold cyan]")
                    script_table = RichTable(show_header=True, header_style="bold")
                    script_table.add_column("Script", style="bold")
                    script_table.add_column("Scenes", justify="right")

                    for script in usage["longest_scripts"][:5]:
                        script_table.add_row(script["title"], str(script["scenes"]))
                    console.print(script_table)

                # Busiest locations
                if usage["busiest_locations"]:
                    console.print("\n[bold cyan]Busiest Locations[/bold cyan]")
                    loc_table = RichTable(show_header=True, header_style="bold")
                    loc_table.add_column("Location", style="bold")
                    loc_table.add_column("Type", style="dim")
                    loc_table.add_column("Scenes", justify="right")

                    for loc in usage["busiest_locations"][:5]:
                        loc_type = "INT" if loc["interior"] else "EXT"
                        loc_table.add_row(loc["name"], loc_type, str(loc["scenes"]))
                    console.print(loc_table)

                # Time of day distribution
                if usage["common_times_of_day"]:
                    console.print("\n[bold cyan]Scene Times of Day[/bold cyan]")
                    for time, count in list(usage["common_times_of_day"].items())[:5]:
                        console.print(f"  • {time}: {count} scenes")
        else:
            console.print(
                "[yellow]No database found. Use 'scriptrag script parse' "
                "to create one.[/yellow]"
            )


# Scene management commands
scene_app = typer.Typer(
    name="scene",
    help="Scene management and analysis commands",
    rich_markup_mode="rich",
)
app.add_typer(scene_app)


@scene_app.command("list")
def scene_list(
    order: Annotated[
        str,
        typer.Option(
            "--order",
            "-o",
            help="Order type: script (default), temporal, or logical",
        ),
    ] = "script",
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID (uses latest if not specified)",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-n",
            help="Limit number of scenes shown",
        ),
    ] = None,
    show_characters: Annotated[
        bool,
        typer.Option(
            "--characters",
            "-c",
            help="Show characters in each scene",
        ),
    ] = False,
    show_dependencies: Annotated[
        bool,
        typer.Option(
            "--dependencies",
            "-d",
            help="Show scene dependencies",
        ),
    ] = False,
) -> None:
    """List scenes in the specified order."""
    try:
        # Validate order type
        order_type = SceneOrderType(order.lower())
    except ValueError:
        console.print(
            f"[red]Invalid order type: {order}[/red]. "
            "Must be 'script', 'temporal', or 'logical'"
        )
        raise typer.Exit(1) from None

    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Initialize connection and manager
        connection = DatabaseConnection(str(db_path))
        manager = SceneManager(connection)

        # Get script node ID
        if not script_id:
            # Get the latest script
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)

            script_id, script_title = result
            console.print(f"[blue]Script:[/blue] {script_title}")

        # Get scenes
        scenes = manager.operations.get_script_scenes(script_id, order_type)

        if limit:
            if limit < 1:
                console.print("[red]Error: Limit must be a positive number[/red]")
                raise typer.Exit(1)
            scenes = scenes[:limit]

        # Import Table locally to avoid scope issues in CI
        from rich.table import Table as RichTable

        # Create table
        table = RichTable(show_header=True, header_style="bold blue")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Scene", style="green")
        table.add_column("Location", style="yellow")

        if order_type == SceneOrderType.TEMPORAL:
            table.add_column("Time", style="magenta")
        elif order_type == SceneOrderType.LOGICAL:
            table.add_column("Dependencies", style="red")

        if show_characters:
            table.add_column("Characters", style="blue")

        # Batch fetch all locations for scenes to avoid N+1 queries
        scene_ids = [scene.id for scene in scenes]
        locations_map = {}
        if scene_ids:
            with connection.transaction() as conn:
                # Get all AT_LOCATION edges for the scenes in one query
                location_results = conn.execute(
                    f"""
                    SELECT e.from_node_id, e.to_node_id, n.label
                    FROM edges e
                    JOIN nodes n ON e.to_node_id = n.id
                    WHERE e.from_node_id IN ({",".join("?" * len(scene_ids))})
                    AND e.edge_type = 'AT_LOCATION'
                    """,
                    scene_ids,
                ).fetchall()

                for scene_id, _location_id, location_label in location_results:
                    locations_map[scene_id] = location_label or ""

        # Batch fetch all characters for scenes if needed
        characters_map: dict[str, list[str]] = {}
        if show_characters and scene_ids:
            with connection.transaction() as conn:
                # Get all characters appearing in scenes
                char_results = conn.execute(
                    f"""
                    SELECT e.to_node_id, e.from_node_id, n.label
                    FROM edges e
                    JOIN nodes n ON e.from_node_id = n.id
                    WHERE e.to_node_id IN ({",".join("?" * len(scene_ids))})
                    AND e.edge_type = 'APPEARS_IN'
                    AND n.node_type = 'character'
                    """,
                    scene_ids,
                ).fetchall()

                for scene_id, _char_id, char_label in char_results:
                    if scene_id not in characters_map:
                        characters_map[scene_id] = []
                    if char_label:
                        characters_map[scene_id].append(char_label)

        # Add rows
        for idx, scene in enumerate(scenes, 1):
            row = [str(idx)]

            # Scene heading
            heading = scene.properties.get("heading", f"Scene {idx}")
            row.append(heading)

            # Location (use pre-fetched data)
            location = locations_map.get(scene.id, "")
            row.append(location)

            # Order-specific columns
            if order_type == SceneOrderType.TEMPORAL:
                time_of_day = scene.properties.get("time_of_day", "")
                row.append(time_of_day)
            elif order_type == SceneOrderType.LOGICAL:
                if show_dependencies:
                    deps = manager.analyze_scene_dependencies_for_single(scene.id)
                    dep_count = len(deps)
                    row.append(f"{dep_count} deps" if dep_count else "-")
                else:
                    row.append("-")

            # Characters (use pre-fetched data)
            if show_characters:
                char_names = characters_map.get(scene.id, [])
                row.append(
                    ", ".join(char_names[:3]) + ("..." if len(char_names) > 3 else "")
                )

            table.add_row(*row)

        console.print(table)

        # Show summary
        console.print(f"\n[dim]Total scenes: {len(scenes)}[/dim]")

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error listing scenes", error=str(e))
        console.print(f"[red]Error listing scenes: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command("update")
def scene_update(
    scene_number: Annotated[
        int,
        typer.Argument(help="Scene number (in script order)"),
    ],
    location: Annotated[
        str | None,
        typer.Option(
            "--location",
            "-l",
            help="New location (e.g., 'INT. OFFICE - DAY')",
        ),
    ] = None,
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID (uses latest if not specified)",
        ),
    ] = None,
) -> None:
    """Update scene properties."""
    if not location:
        console.print("[red]No updates specified. Use --location to update.[/red]")
        raise typer.Exit(1)

    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Initialize connection and manager
        connection = DatabaseConnection(str(db_path))
        manager = SceneManager(connection)

        # Get script node ID
        if not script_id:
            # Get the latest script
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)

            script_id = result[0]

        # Get scene by number
        scenes = manager.operations.get_script_scenes(script_id, SceneOrderType.SCRIPT)

        if not scenes:
            console.print("[red]No scenes found in the script.[/red]")
            raise typer.Exit(1)

        if scene_number < 1 or scene_number > len(scenes):
            console.print(
                f"[red]Invalid scene number. "
                f"Please specify a number between 1 and {len(scenes)}.[/red]"
            )
            raise typer.Exit(1)

        scene = scenes[scene_number - 1]

        # Update location
        if location:
            if manager.update_scene_location(scene.id, location):
                console.print(
                    f"[green]✓[/green] Updated scene {scene_number} location to: "
                    f"{location}"
                )
            else:
                console.print("[red]Failed to update scene location.[/red]")
                raise typer.Exit(1)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error updating scene", error=str(e))
        console.print(f"[red]Error updating scene: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command("reorder")
def scene_reorder(
    scene_number: Annotated[
        int,
        typer.Argument(help="Scene number to move (in current order)"),
    ],
    position: Annotated[
        int,
        typer.Option(
            "--position",
            "-p",
            help="New position for the scene",
        ),
    ],
    order_type: Annotated[
        str,
        typer.Option(
            "--order",
            "-o",
            help="Order type to modify: script, temporal, or logical",
        ),
    ] = "script",
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID (uses latest if not specified)",
        ),
    ] = None,
) -> None:
    """Reorder a scene to a new position."""
    try:
        # Validate order type
        order_enum = SceneOrderType(order_type.lower())
    except ValueError:
        console.print(
            f"[red]Invalid order type: {order_type}[/red]. "
            "Must be 'script', 'temporal', or 'logical'"
        )
        raise typer.Exit(1) from None

    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Initialize connection and manager
        connection = DatabaseConnection(str(db_path))
        manager = SceneManager(connection)

        # Get script node ID
        if not script_id:
            # Get the latest script
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)

            script_id = result[0]

        # Get scenes in current order
        scenes = manager.operations.get_script_scenes(script_id, order_enum)

        if not scenes:
            console.print("[red]No scenes found in the script.[/red]")
            raise typer.Exit(1)

        if scene_number < 1 or scene_number > len(scenes):
            console.print(
                f"[red]Invalid scene number. "
                f"Please specify a number between 1 and {len(scenes)}.[/red]"
            )
            raise typer.Exit(1)

        if position < 1 or position > len(scenes):
            console.print(
                f"[red]Invalid position. Must be between 1 and {len(scenes)}.[/red]"
            )
            raise typer.Exit(1)

        scene = scenes[scene_number - 1]

        # Perform reorder
        if manager.update_scene_order(scene.id, position, order_enum):
            console.print(
                f"[green]✓[/green] Moved scene {scene_number} to position {position} "
                f"in {order_type} order"
            )

            # Show updated order (first 5 scenes)
            updated_scenes = manager.operations.get_script_scenes(script_id, order_enum)
            console.print("\n[blue]Updated order (first 5 scenes):[/blue]")
            for idx, s in enumerate(updated_scenes[:5], 1):
                heading = s.properties.get("heading", f"Scene {idx}")
                console.print(f"  {idx}. {heading}")
            if len(updated_scenes) > 5:
                console.print(f"  ... ({len(updated_scenes) - 5} more scenes)")
        else:
            console.print("[red]Failed to reorder scene.[/red]")
            raise typer.Exit(1)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error reordering scene", error=str(e))
        console.print(f"[red]Error reordering scene: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command("analyze")
def scene_analyze(
    analysis_type: Annotated[
        str,
        typer.Argument(help="Analysis type: dependencies, temporal, or all"),
    ] = "all",
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID (uses latest if not specified)",
        ),
    ] = None,
) -> None:
    """Analyze scene dependencies and relationships."""
    if analysis_type not in ["dependencies", "temporal", "all"]:
        console.print(
            f"[red]Invalid analysis type: {analysis_type}[/red]. "
            "Must be 'dependencies', 'temporal', or 'all'"
        )
        raise typer.Exit(1)

    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Initialize connection and manager
        connection = DatabaseConnection(str(db_path))
        manager = SceneManager(connection)

        # Get script node ID
        if not script_id:
            # Get the latest script
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)

            script_id, script_title = result
            console.print(f"\n[bold blue]Analyzing:[/bold blue] {script_title}")

        # Perform analysis
        if analysis_type in ["dependencies", "all"]:
            console.print("\n[bold yellow]Scene Dependencies:[/bold yellow]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Analyzing dependencies...", total=None)
                dependencies = manager.analyze_scene_dependencies(script_id)

            # Get scenes for display
            scenes = manager.operations.get_script_scenes(
                script_id, SceneOrderType.SCRIPT
            )
            scene_map = {s.id: s for s in scenes}

            dep_count = 0
            for scene_id, deps in dependencies.items():
                if deps:
                    dep_count += 1
                    scene = scene_map.get(scene_id)
                    if scene:
                        heading = scene.properties.get("heading", "Unknown scene")
                        console.print(f"\n  [green]{heading}[/green]")
                        console.print("  Depends on:")
                        for dep_id in deps:
                            dep_scene = scene_map.get(dep_id)
                            if dep_scene:
                                dep_heading = dep_scene.properties.get(
                                    "heading", "Unknown"
                                )
                                console.print(f"    • {dep_heading}")

            if dep_count == 0:
                console.print("  [dim]No dependencies found[/dim]")
            else:
                console.print(
                    f"\n  [dim]Total scenes with dependencies: {dep_count}[/dim]"
                )

        if analysis_type in ["temporal", "all"]:
            console.print("\n[bold yellow]Temporal Analysis:[/bold yellow]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Inferring temporal order...", total=None)
                temporal_order = manager.infer_temporal_order(script_id)

            if temporal_order:
                # Update the temporal order in the database
                manager.operations.update_scene_order(
                    script_id, temporal_order, SceneOrderType.TEMPORAL
                )

                console.print(
                    f"  [green]✓[/green] Inferred temporal order for "
                    f"{len(temporal_order)} scenes"
                )
                console.print(
                    "  [dim]Use 'scriptrag scene list --order temporal' to view[/dim]"
                )
            else:
                console.print("  [dim]No temporal markers found[/dim]")

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error analyzing scenes", error=str(e))
        console.print(f"[red]Error analyzing scenes: {e}[/red]")
        raise typer.Exit(1) from e


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
    try:
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

    # Import Table locally to avoid scope issues in CI
    from rich.table import Table as RichTable

    table = RichTable(
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
            logger = get_logger(__name__)
            logger.error("Error creating config", error=str(e))
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

    # Import Table locally to avoid scope issues in CI
    from rich.table import Table as RichTable

    table = RichTable(show_header=True, header_style="bold blue")
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
        logger = get_logger(__name__)
        logger.error("LLM test failed", error=str(e))
        console.print(f"[red]✗[/red] LLM test failed: {e}")
        raise typer.Exit(1) from e


# Script Bible commands
bible_app = typer.Typer(
    name="bible",
    help="Script Bible and continuity management commands",
    rich_markup_mode="rich",
)
app.add_typer(bible_app)


@bible_app.command("create")
def bible_create(
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    title: Annotated[str, typer.Option("--title", "-t", help="Bible title")] = "",
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Bible description")
    ] = None,
    bible_type: Annotated[str, typer.Option("--type", help="Bible type")] = "series",
    created_by: Annotated[
        str | None, typer.Option("--created-by", help="Creator name")
    ] = None,
) -> None:
    """Create a new script bible."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Using latest script:[/blue] {script_title}")

            # Use script title as bible title if not provided
            if not title:
                script_row = connection.fetch_one(
                    "SELECT title FROM scripts WHERE id = ?", (script_id,)
                )
                if script_row:
                    title = f"{script_row['title']} - Script Bible"
                else:
                    title = "Script Bible"

            bible_id = bible_ops.create_series_bible(
                script_id=script_id,
                title=title,
                description=description,
                created_by=created_by,
                bible_type=bible_type,
            )

            console.print(f"[green]✓[/green] Created script bible: {bible_id}")
            console.print(f"[dim]Title: {title}[/dim]")
            if description:
                console.print(f"[dim]Description: {description}[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create bible: {e}")
        raise typer.Exit(1) from e


@bible_app.command("list")
def bible_list(
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
) -> None:
    """List script bibles."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Listing bibles for:[/blue] {script_title}")

            bibles = bible_ops.get_series_bibles_for_script(script_id)

            if not bibles:
                console.print("[yellow]No script bibles found.[/yellow]")
                return

            # Import Table locally to avoid scope issues in CI
            from rich.table import Table as RichTable

            table = RichTable(title="Script Bibles")
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Version")
            table.add_column("Created")

            for bible in bibles:
                table.add_row(
                    str(bible.id)[:8] + "...",
                    bible.title,
                    bible.bible_type,
                    bible.status,
                    str(bible.version),
                    bible.created_at.strftime("%Y-%m-%d"),
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list bibles: {e}")
        raise typer.Exit(1) from e


@bible_app.command("character-profile")
def bible_character_profile(
    character_name: Annotated[str, typer.Argument(help="Character name")],
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    age: Annotated[int | None, typer.Option("--age", help="Character age")] = None,
    occupation: Annotated[
        str | None, typer.Option("--occupation", help="Character occupation")
    ] = None,
    background: Annotated[
        str | None, typer.Option("--background", help="Character background")
    ] = None,
    arc: Annotated[
        str | None, typer.Option("--arc", help="Character development arc")
    ] = None,
    goals: Annotated[
        str | None, typer.Option("--goals", help="Character goals")
    ] = None,
    fears: Annotated[
        str | None, typer.Option("--fears", help="Character fears")
    ] = None,
) -> None:
    """Create or update a character profile."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Using script:[/blue] {script_title}")

            # Find character by name
            char_row = connection.fetch_one(
                "SELECT id FROM characters WHERE script_id = ? AND name LIKE ?",
                (script_id, f"%{character_name}%"),
            )

            if not char_row:
                console.print(f"[red]✗[/red] Character '{character_name}' not found.")
                raise typer.Exit(1)

            character_id = char_row["id"]

            # Create profile data
            profile_data: dict[str, Any] = {}
            if age is not None:
                profile_data["age"] = age
            if occupation:
                profile_data["occupation"] = occupation
            if background:
                profile_data["background"] = background
            if arc:
                profile_data["character_arc"] = arc
            if goals:
                profile_data["goals"] = goals
            if fears:
                profile_data["fears"] = fears

            # Check if profile exists
            existing_profile = bible_ops.get_character_profile(character_id, script_id)

            if existing_profile:
                # Update existing profile (simplified - would need update method)
                console.print(
                    f"[yellow]⚠[/yellow] Profile for '{character_name}' already exists."
                )
                console.print("[dim]Use update command when available.[/dim]")
            else:
                profile_id = bible_ops.create_character_profile(
                    character_id=character_id, script_id=script_id, **profile_data
                )
                console.print(
                    f"[green]✓[/green] Created character profile: {profile_id}"
                )
                console.print(f"[dim]Character: {character_name}[/dim]")
                if profile_data:
                    for key, value in profile_data.items():
                        console.print(f"[dim]{key}: {value}[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create character profile: {e}")
        raise typer.Exit(1) from e


@bible_app.command("world-element")
def bible_world_element(
    name: Annotated[str, typer.Argument(help="Element name")],
    element_type: Annotated[
        str, typer.Option("--type", "-t", help="Element type")
    ] = "location",
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Element description")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", help="Element category")
    ] = None,
    importance: Annotated[
        int, typer.Option("--importance", help="Importance level (1-5)")
    ] = 1,
    rules: Annotated[
        str | None, typer.Option("--rules", help="Rules and constraints")
    ] = None,
) -> None:
    """Create a world building element."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Using script:[/blue] {script_title}")

            element_data = {
                "description": description,
                "category": category,
                "importance_level": importance,
                "rules_and_constraints": rules,
            }

            element_id = bible_ops.create_world_element(
                script_id=script_id,
                element_type=element_type,
                name=name,
                **element_data,
            )

            console.print(f"[green]✓[/green] Created world element: {element_id}")
            console.print(f"[dim]Name: {name}[/dim]")
            console.print(f"[dim]Type: {element_type}[/dim]")
            if category:
                console.print(f"[dim]Category: {category}[/dim]")
            console.print(f"[dim]Importance: {importance}/5[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create world element: {e}")
        raise typer.Exit(1) from e


@bible_app.command("timeline")
def bible_timeline(
    name: Annotated[str, typer.Argument(help="Timeline name")],
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    timeline_type: Annotated[
        str, typer.Option("--type", "-t", help="Timeline type")
    ] = "main",
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Timeline description")
    ] = None,
    start_date: Annotated[
        str | None, typer.Option("--start", help="Start date")
    ] = None,
    end_date: Annotated[str | None, typer.Option("--end", help="End date")] = None,
) -> None:
    """Create a story timeline."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Using script:[/blue] {script_title}")

            timeline_data = {
                "description": description,
                "start_date": start_date,
                "end_date": end_date,
            }

            timeline_id = bible_ops.create_story_timeline(
                script_id=script_id,
                name=name,
                timeline_type=timeline_type,
                **timeline_data,
            )

            console.print(f"[green]✓[/green] Created timeline: {timeline_id}")
            console.print(f"[dim]Name: {name}[/dim]")
            console.print(f"[dim]Type: {timeline_type}[/dim]")
            if start_date or end_date:
                console.print(
                    f"[dim]Period: {start_date or '?'} to {end_date or '?'}[/dim]"
                )

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create timeline: {e}")
        raise typer.Exit(1) from e


@bible_app.command("continuity-check")
def bible_continuity_check(
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    create_notes: Annotated[
        bool, typer.Option("--create-notes", help="Create continuity notes")
    ] = False,
    severity_filter: Annotated[
        str | None, typer.Option("--severity", help="Filter by severity")
    ] = None,
) -> None:
    """Run continuity validation and show results."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            validator = ContinuityValidator(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, _ = latest

            console.print("[blue]Running continuity validation...[/blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Validating continuity...", total=None)
                issues = validator.validate_script_continuity(script_id)
                progress.stop()

            # Filter by severity if requested
            if severity_filter:
                issues = [i for i in issues if i.severity == severity_filter]

            if not issues:
                console.print("[green]✓[/green] No continuity issues found!")
                return

            # Group issues by severity
            by_severity: dict[str, list[Any]] = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }
            for issue in issues:
                by_severity[issue.severity].append(issue)

            # Display results
            console.print(f"[yellow]Found {len(issues)} continuity issues:[/yellow]")

            for severity in ["critical", "high", "medium", "low"]:
                if by_severity[severity]:
                    color = {
                        "critical": "red",
                        "high": "orange",
                        "medium": "yellow",
                        "low": "blue",
                    }[severity]
                    console.print(
                        f"\n[{color}]{severity.upper()} "
                        f"({len(by_severity[severity])} issues):[/{color}]"
                    )

                    # Show first 5 of each severity
                    for issue in by_severity[severity][:5]:
                        console.print(f"  • {issue.title}")
                        console.print(f"    {issue.description}")

                    if len(by_severity[severity]) > 5:
                        console.print(
                            f"    ... and {len(by_severity[severity]) - 5} more"
                        )

            # Create notes if requested
            if create_notes:
                console.print("\n[blue]Creating continuity notes...[/blue]")
                note_ids = validator.create_continuity_notes_from_issues(
                    script_id=script_id,
                    issues=issues,
                    reported_by="CLI Continuity Check",
                )
                console.print(
                    f"[green]✓[/green] Created {len(note_ids)} continuity notes"
                )

    except Exception as e:
        console.print(f"[red]✗[/red] Continuity check failed: {e}")
        raise typer.Exit(1) from e


@bible_app.command("notes")
def bible_notes(
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    status: Annotated[
        str | None, typer.Option("--status", help="Filter by status")
    ] = None,
    note_type: Annotated[
        str | None, typer.Option("--type", help="Filter by type")
    ] = None,
    severity: Annotated[
        str | None, typer.Option("--severity", help="Filter by severity")
    ] = None,
) -> None:
    """List continuity notes."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest
                console.print(f"[blue]Continuity notes for:[/blue] {script_title}")

            notes = bible_ops.get_continuity_notes(
                script_id=script_id,
                status=status,
                note_type=note_type,
                severity=severity,
            )

            if not notes:
                console.print("[yellow]No continuity notes found.[/yellow]")
                return

            # Import Table locally to avoid scope issues in CI
            from rich.table import Table as RichTable

            table = RichTable(title="Continuity Notes")
            table.add_column("ID")
            table.add_column("Type")
            table.add_column("Severity")
            table.add_column("Status")
            table.add_column("Title")
            table.add_column("Created")

            for note in notes:
                color = {
                    "critical": "red",
                    "high": "orange",
                    "medium": "yellow",
                    "low": "blue",
                }[note.severity]
                table.add_row(
                    str(note.id)[:8] + "...",
                    note.note_type,
                    f"[{color}]{note.severity}[/{color}]",
                    note.status,
                    note.title[:50] + ("..." if len(note.title) > 50 else ""),
                    note.created_at.strftime("%Y-%m-%d"),
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list notes: {e}")
        raise typer.Exit(1) from e


@bible_app.command("report")
def bible_report(
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
    output_file: Annotated[
        str | None, typer.Option("--output", "-o", help="Output file path")
    ] = None,
) -> None:
    """Generate a comprehensive continuity report."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
            validator = ContinuityValidator(connection)

            # Get script ID if not provided
            if not script_id:
                latest = get_latest_script_id(connection)
                if not latest:
                    console.print(
                        "[red]✗[/red] No scripts found. Please import a script first."
                    )
                    raise typer.Exit(1)
                script_id, script_title = latest

            console.print(
                f"[blue]Generating continuity report for:[/blue] {script_title}"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Generating report...", total=None)
                report = validator.generate_continuity_report(script_id)
                progress.stop()

            # Display summary
            stats = report["validation_results"]["issue_statistics"]
            note_stats = report["existing_notes"]["note_statistics"]

            console.print(
                f"\n[green]Continuity Report for {report['script_title']}[/green]"
            )
            console.print(f"Generated: {report['generated_at']}")
            console.print(
                f"Script Type: {'Series' if report['is_series'] else 'Screenplay'}"
            )

            console.print(f"\n[yellow]Issues Found: {stats['total_issues']}[/yellow]")
            for severity, count in stats["by_severity"].items():
                if count > 0:
                    color = {
                        "critical": "red",
                        "high": "orange",
                        "medium": "yellow",
                        "low": "blue",
                    }[severity]
                    console.print(
                        f"  {severity.capitalize()}: [{color}]{count}[/{color}]"
                    )

            console.print(
                f"\n[yellow]Existing Notes: {note_stats['total_notes']}[/yellow]"
            )
            for status, count in note_stats["by_status"].items():
                if count > 0:
                    console.print(f"  {status.capitalize()}: {count}")

            console.print("\n[blue]Recommendations:[/blue]")
            for rec in report["recommendations"]:
                console.print(f"  • {rec}")

            # Save to file if requested
            if output_file:
                import json

                with Path(output_file).open("w") as f:
                    # Convert objects to serializable format
                    serializable_report = {}
                    for key, value in report.items():
                        if key in ["validation_results", "existing_notes"]:
                            # Skip complex objects for now
                            serializable_report[key] = {"summary": "See console output"}
                        else:
                            serializable_report[key] = value

                    json.dump(serializable_report, f, indent=2, default=str)
                console.print(f"[green]✓[/green] Report saved to: {output_file}")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to generate report: {e}")
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


@server_app.command("api")
def server_api(
    host: Annotated[
        str, typer.Option("--host", "-h", help="API host address")
    ] = "127.0.0.1",  # Use localhost by default for security
    port: Annotated[int, typer.Option("--port", "-p", help="API port number")] = 8000,
    reload: Annotated[
        bool, typer.Option("--reload", "-r", help="Enable auto-reload")
    ] = False,
) -> None:
    """Start the REST API server."""
    console.print("[blue]Starting ScriptRAG REST API server...[/blue]")
    console.print(f"[dim]Host: {host}:{port}[/dim]")
    console.print(f"[dim]Docs: http://{host}:{port}/api/v1/docs[/dim]")

    if create_app is None:
        console.print(
            "[red]Error: API server is not available. Install with 'api' extra.[/red]"
        )
        raise typer.Exit(1)

    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Error: uvicorn is not installed. "
            "Install with 'pip install uvicorn'.[/red]"
        )
        raise typer.Exit(1) from None

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info" if reload else "warning",
    )


# Mentor commands
mentor_app = typer.Typer(
    name="mentor",
    help="Screenplay analysis mentors and automated feedback",
    rich_markup_mode="rich",
)
app.add_typer(mentor_app)


@mentor_app.command("list")
def mentor_list() -> None:
    """List all available mentors."""
    try:
        from .mentors import get_mentor_registry

        registry = get_mentor_registry()
        mentors = registry.list_mentors()

        if not mentors:
            console.print("[yellow]No mentors available.[/yellow]")
            return

        # Import Table locally to avoid scope issues in CI
        from rich.table import Table as RichTable

        table = RichTable(show_header=True, header_style="bold blue")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Description", style="white")

        for mentor in mentors:
            table.add_row(
                str(mentor["name"]),
                str(mentor["type"]),
                str(mentor["version"]),
                (
                    str(mentor["description"])[:60]
                    + ("..." if len(str(mentor["description"])) > 60 else "")
                ),
            )

        console.print(table)
        console.print(f"\n[dim]Total mentors: {len(mentors)}[/dim]")

    except Exception as e:
        console.print(f"[red]Error listing mentors: {e}[/red]")
        raise typer.Exit(1) from e


@mentor_app.command("analyze")
def mentor_analyze(
    mentor_name: Annotated[
        str, typer.Argument(help="Name of the mentor to use for analysis")
    ],
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID to analyze (uses latest if not specified)",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", help="Path to mentor configuration file (JSON/YAML)"
        ),
    ] = None,
    save_results: Annotated[
        bool,
        typer.Option("--save", help="Save analysis results to database"),
    ] = True,
) -> None:
    """Run mentor analysis on a screenplay."""
    import asyncio
    import json
    from pathlib import Path

    try:
        from .database.connection import DatabaseConnection
        from .database.operations import GraphOperations
        from .mentors import MentorDatabaseOperations, get_mentor_registry

        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Get mentor
        registry = get_mentor_registry()
        if not registry.is_registered(mentor_name):
            mentor_list = registry.list_mentors()
            available = ", ".join([str(m["name"]) for m in mentor_list])
            console.print(f"[red]Mentor '{mentor_name}' not found.[/red]")
            console.print(f"Available mentors: {available}")
            raise typer.Exit(1)

        # Load configuration if provided
        config = {}
        if config_file:
            if config_file.suffix.lower() == ".json":
                config = json.loads(config_file.read_text())
            else:
                # Assume YAML
                import yaml

                config = yaml.safe_load(config_file.read_text())

        mentor = registry.get_mentor(mentor_name, config)

        # Get script ID
        connection = DatabaseConnection(str(db_path))
        if not script_id:
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)
            script_id, script_title = result
            console.print(f"[blue]Analyzing script:[/blue] {script_title}")
        else:
            console.print(f"[blue]Analyzing script ID:[/blue] {script_id}")

        # Run analysis
        console.print(f"[blue]Running {mentor_name} analysis...[/blue]")

        async def run_analysis() -> MentorResult:
            graph_ops = GraphOperations(connection)

            def progress_callback(pct: float, msg: str) -> None:
                # Simple progress display
                progress_bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
                console.print(f"\r[{progress_bar}] {msg}", end="")

            try:
                result = await mentor.analyze_script(
                    script_id=UUID(script_id),
                    db_operations=graph_ops,
                    progress_callback=progress_callback,
                )

                console.print("\n")  # New line after progress
                return result

            except Exception as e:
                console.print(f"\n[red]Analysis failed: {e}[/red]")
                raise

        analysis_result = asyncio.run(run_analysis())

        # Display results
        console.print("\n[bold green]Analysis Complete![/bold green]")
        console.print(
            f"[bold]Mentor:[/bold] {analysis_result.mentor_name} "
            f"v{analysis_result.mentor_version}"
        )
        if analysis_result.score is not None:
            console.print(f"[bold]Score:[/bold] {analysis_result.score:.1f}/100")
        console.print(
            f"[bold]Execution Time:[/bold] {analysis_result.execution_time_ms}ms"
        )
        console.print(f"\n[bold]Summary:[/bold]\n{analysis_result.summary}")

        # Show analysis breakdown
        if analysis_result.analyses:
            console.print(
                f"\n[bold blue]Detailed Analysis "
                f"({len(analysis_result.analyses)} findings):[/bold blue]"
            )

            # Group by severity
            by_severity: dict[str, list[MentorAnalysis]] = {}
            for analysis in analysis_result.analyses:
                severity = analysis.severity.value
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(analysis)

            severity_styles = {
                "error": "red",
                "warning": "yellow",
                "suggestion": "blue",
                "info": "green",
            }

            for severity, analyses in by_severity.items():
                style = severity_styles.get(severity, "white")
                console.print(
                    f"\n[bold {style}]{severity.upper()} "
                    f"({len(analyses)}):[/bold {style}]"
                )

                for analysis in analyses[:3]:  # Show first 3 of each type
                    console.print(f"  • [bold]{analysis.title}[/bold]")
                    console.print(f"    {analysis.description}")
                    if analysis.recommendations:
                        console.print(
                            f"    [dim]Recommendations: "
                            f"{analysis.recommendations[0]}[/dim]"
                        )

                if len(analyses) > 3:
                    console.print(
                        f"    [dim]... and {len(analyses) - 3} more {severity} "
                        "findings[/dim]"
                    )

        # Save results if requested
        if save_results:
            mentor_db = MentorDatabaseOperations(connection)
            if mentor_db.store_mentor_result(analysis_result):
                console.print("\n[green]✓[/green] Analysis results saved to database")
            else:
                console.print("\n[yellow]⚠[/yellow] Failed to save analysis results")

    except Exception as e:
        console.print(f"[red]Error during analysis: {e}[/red]")
        raise typer.Exit(1) from e


@mentor_app.command("results")
def mentor_results(
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id", "-s", help="Script ID (uses latest if not specified)"
        ),
    ] = None,
    mentor_name: Annotated[
        str | None,
        typer.Option("--mentor", "-m", help="Filter by mentor name"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Limit number of results"),
    ] = 10,
) -> None:
    """Show previous mentor analysis results."""
    try:
        from .database.connection import DatabaseConnection
        from .mentors import MentorDatabaseOperations

        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        connection = DatabaseConnection(str(db_path))
        mentor_db = MentorDatabaseOperations(connection)

        # Get script ID
        if not script_id:
            latest_script = get_latest_script_id(connection)
            if not latest_script:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)
            script_id, script_title = latest_script
            console.print(f"[blue]Results for script:[/blue] {script_title}")

        # Get results
        results = mentor_db.get_script_mentor_results(UUID(script_id), mentor_name)[
            :limit
        ]

        if not results:
            console.print("[yellow]No analysis results found.[/yellow]")
            return

        # Import Table locally to avoid scope issues in CI
        from rich.table import Table as RichTable

        # Display results table
        table = RichTable(show_header=True, header_style="bold blue")
        table.add_column("Date", style="cyan")
        table.add_column("Mentor", style="green")
        table.add_column("Score", style="yellow")
        table.add_column("Findings", style="white")
        table.add_column("Summary", style="dim")

        for result in results:
            date_str = result.analysis_date.strftime("%Y-%m-%d %H:%M")
            score_str = f"{result.score:.1f}" if result.score else "—"
            findings_str = f"{len(result.analyses)} findings"
            summary_short = result.summary[:50] + (
                "..." if len(result.summary) > 50 else ""
            )

            table.add_row(
                date_str, result.mentor_name, score_str, findings_str, summary_short
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(results)} results[/dim]")

    except Exception as e:
        console.print(f"[red]Error retrieving results: {e}[/red]")
        raise typer.Exit(1) from e


@mentor_app.command("search")
def mentor_search(
    query: Annotated[str, typer.Argument(help="Search query for analysis findings")],
    mentor_name: Annotated[
        str | None,
        typer.Option("--mentor", "-m", help="Filter by mentor name"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by analysis category"),
    ] = None,
    severity: Annotated[
        str | None,
        typer.Option(
            "--severity",
            "-v",
            help="Filter by severity (error, warning, suggestion, info)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Limit number of results"),
    ] = 20,
) -> None:
    """Search mentor analysis findings."""
    try:
        from .database.connection import DatabaseConnection
        from .mentors import AnalysisSeverity, MentorDatabaseOperations

        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        connection = DatabaseConnection(str(db_path))
        mentor_db = MentorDatabaseOperations(connection)

        # Parse severity
        severity_enum = None
        if severity:
            try:
                severity_enum = AnalysisSeverity(severity.lower())
            except ValueError as err:
                console.print(f"[red]Invalid severity: {severity}[/red]")
                console.print("Valid severities: error, warning, suggestion, info")
                raise typer.Exit(1) from err

        # Search analyses
        console.print(f"[blue]Searching for:[/blue] {query}")

        results = mentor_db.search_analyses(
            query=query,
            mentor_name=mentor_name,
            category=category,
            severity=severity_enum,
            limit=limit,
        )

        if not results:
            console.print("[yellow]No matching analysis findings found.[/yellow]")
            return

        # Display results
        console.print(f"\n[bold]Found {len(results)} analysis findings:[/bold]")

        for i, analysis in enumerate(results, 1):
            severity_style = {
                "error": "red",
                "warning": "yellow",
                "suggestion": "blue",
                "info": "green",
            }.get(analysis.severity.value, "white")

            console.print(
                f"\n[bold cyan]{i}.[/bold cyan] [bold]{analysis.title}[/bold]"
            )
            console.print(f"   [bold]Mentor:[/bold] {analysis.mentor_name}")
            console.print(f"   [bold]Category:[/bold] {analysis.category}")
            console.print(
                f"   [bold]Severity:[/bold] [{severity_style}]"
                f"{analysis.severity.value}[/{severity_style}]"
            )
            console.print(f"   [bold]Description:[/bold] {analysis.description}")

            if analysis.recommendations:
                console.print(
                    f"   [bold]Recommendation:[/bold] {analysis.recommendations[0]}"
                )

    except Exception as e:
        console.print(f"[red]Error searching analyses: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
