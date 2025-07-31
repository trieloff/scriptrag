"""Scene management and analysis commands for ScriptRAG CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scriptrag.config import get_logger, get_settings
from scriptrag.database.connection import DatabaseConnection
from scriptrag.models import SceneOrderType
from scriptrag.scene_manager import SceneManager

# Create scene app
scene_app = typer.Typer(
    name="scene",
    help="Scene management and analysis commands",
    rich_markup_mode="rich",
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
