"""Command-line interface for ScriptRAG.

This module provides a comprehensive CLI for ScriptRAG operations including
script parsing, searching, configuration management, and development utilities.
"""

# Standard library imports
from pathlib import Path
from typing import Annotated, Any

# Third-party imports
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Local imports
from . import ScriptRAG
from .config import (
    create_default_config,
    get_logger,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)
from .database.connection import DatabaseConnection
from .database.operations import GraphOperations
from .models import SceneOrderType
from .parser.bulk_import import BulkImporter
from .scene_manager import SceneManager

# Create main Typer app
app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


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

        # Display summary table
        table = Table(show_header=False, box=None)
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

        table = Table(show_header=True, header_style="bold blue")
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
            scenes = scenes[:limit]

        # Create table
        table = Table(show_header=True, header_style="bold blue")
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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

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
    import asyncio

    from .database import get_connection
    from .search import SearchInterface

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
        logger = get_logger(__name__)
        logger.error("LLM test failed", error=str(e))
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

    import uvicorn

    from scriptrag.api.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info" if reload else "warning",
    )


if __name__ == "__main__":
    app()
