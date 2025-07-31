"""Screenplay parsing and management commands for ScriptRAG CLI."""

from collections import Counter
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scriptrag import ScriptRAG
from scriptrag.config import get_logger, get_settings
from scriptrag.database import get_connection, initialize_database
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.database.statistics import DatabaseStatistics
from scriptrag.parser import FountainParser, FountainParsingError
from scriptrag.parser.bulk_import import BulkImporter

# Create script app
script_app = typer.Typer(
    name="script",
    help="Screenplay parsing and management commands",
    rich_markup_mode="rich",
)

console = Console()


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

        # Ensure database is initialized with schema
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
            console.print("\n[red]Errors:[/red]")
            error_items = list(result.errors.items())[:5]  # Show first 5 errors
            for file_path, error in error_items:
                console.print(f"  • {file_path}: {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more errors")

        # Show created series if any
        if result.series_created:
            console.print("\n[green]Created series:[/green]")
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

        # Parse screenplay without importing to database
        try:
            # Temporarily suppress jouvence debug logging
            import logging

            jouvence_logger = logging.getLogger("jouvence")
            original_level = jouvence_logger.level
            jouvence_logger.setLevel(logging.WARNING)

            parser = FountainParser()
            script = parser.parse_file(script_path)

            # Restore original logging level
            jouvence_logger.setLevel(original_level)

            # Basic metrics
            scenes = parser.get_scenes()
            characters = parser.get_characters()

            console.print()
            console.print(
                Panel(
                    f"[bold]{script.title}[/bold]",
                    subtitle=f"by {script.author or 'Unknown'}",
                    style="cyan",
                )
            )

            # Display title page metadata if available
            if script.title_page:
                metadata_items = []
                for key, value in script.title_page.items():
                    if key.lower() not in ["title", "author"] and value:
                        metadata_items.append(f"{key}: {value}")
                if metadata_items:
                    console.print("[dim]" + " | ".join(metadata_items) + "[/dim]")

            console.print()

            # Basic statistics table
            stats_table = Table(title="Screenplay Statistics", style="cyan")
            stats_table.add_column("Metric", style="bright_cyan")
            stats_table.add_column("Value", justify="right")

            # Page count estimate (1 page = ~250 words or ~1 minute of screen time)
            total_words = 0
            total_dialogue_lines = 0
            total_action_lines = 0

            for scene in scenes:
                for element in scene.elements:
                    words = len(element.text.split())
                    total_words += words
                    if hasattr(element, "element_type"):
                        if element.element_type.value == "dialogue":
                            total_dialogue_lines += 1
                        elif element.element_type.value == "action":
                            total_action_lines += 1

            estimated_pages = max(1, round(total_words / 250))
            estimated_minutes = estimated_pages  # 1 page ≈ 1 minute

            stats_table.add_row("Total Scenes", str(len(scenes)))
            stats_table.add_row("Total Characters", str(len(characters)))
            stats_table.add_row("Total Words", f"{total_words:,}")
            stats_table.add_row("Dialogue Lines", f"{total_dialogue_lines:,}")
            stats_table.add_row("Action Lines", f"{total_action_lines:,}")
            stats_table.add_row("Estimated Pages", f"~{estimated_pages}")
            stats_table.add_row("Estimated Runtime", f"~{estimated_minutes} minutes")

            console.print(stats_table)
            console.print()

            # Act structure analysis
            act_breaks = []
            for i, scene in enumerate(scenes):
                # Look for common act break indicators
                if scene.heading:
                    heading_lower = scene.heading.lower()
                    if any(
                        marker in heading_lower
                        for marker in ["act ", "end of act", "fade out", "blackout"]
                    ):
                        act_breaks.append((i, scene.heading))

                # Check for major transitions that might indicate act breaks
                for element in scene.elements:
                    if (
                        hasattr(element, "element_type")
                        and element.element_type.value == "transition"
                        and any(
                            marker in element.text.lower()
                            for marker in ["fade out", "cut to black", "end of act"]
                        )
                    ):
                        act_breaks.append((i, element.text))

            # Estimate acts based on standard structure if no explicit breaks found
            if not act_breaks and len(scenes) > 10:
                # Three-act structure: roughly 25%-50%-25%
                act1_end = int(len(scenes) * 0.25)
                act2_end = int(len(scenes) * 0.75)
                structure_table = Table(title="Estimated Act Structure", style="blue")
                structure_table.add_column("Act", style="bright_blue")
                structure_table.add_column("Scenes", justify="right")
                structure_table.add_column("Percentage", justify="right")

                structure_table.add_row("Act I", f"1-{act1_end}", "25%")
                structure_table.add_row("Act II", f"{act1_end + 1}-{act2_end}", "50%")
                structure_table.add_row(
                    "Act III", f"{act2_end + 1}-{len(scenes)}", "25%"
                )

                console.print(structure_table)
                console.print()

            # Scene length analysis
            scene_lengths = []
            for scene in scenes:
                scene_words = sum(
                    len(element.text.split()) for element in scene.elements
                )
                scene_lengths.append(scene_words)

            if scene_lengths:
                avg_length = sum(scene_lengths) / len(scene_lengths)
                min_length = min(scene_lengths)
                max_length = max(scene_lengths)

                length_table = Table(title="Scene Length Analysis", style="cyan")
                length_table.add_column("Metric", style="bright_cyan")
                length_table.add_column("Words", justify="right")
                length_table.add_column("Est. Pages", justify="right")

                length_table.add_row(
                    "Average Scene", f"{avg_length:.0f}", f"{avg_length / 250:.1f}"
                )
                length_table.add_row(
                    "Shortest Scene", str(min_length), f"{min_length / 250:.1f}"
                )
                length_table.add_row(
                    "Longest Scene", str(max_length), f"{max_length / 250:.1f}"
                )

                console.print(length_table)
                console.print()

            # Scene analysis
            if scenes:
                scene_table = Table(title="Scene Analysis", style="green")
                scene_table.add_column("Type", style="bright_green")
                scene_table.add_column("Count", justify="right")
                scene_table.add_column("Percentage", justify="right")

                # Count INT/EXT scenes
                int_scenes = sum(
                    1 for s in scenes if s.location and s.location.interior
                )
                ext_scenes = sum(
                    1 for s in scenes if s.location and not s.location.interior
                )
                no_location = len(scenes) - int_scenes - ext_scenes

                if int_scenes > 0:
                    scene_table.add_row(
                        "Interior (INT)",
                        str(int_scenes),
                        f"{int_scenes / len(scenes) * 100:.1f}%",
                    )
                if ext_scenes > 0:
                    scene_table.add_row(
                        "Exterior (EXT)",
                        str(ext_scenes),
                        f"{ext_scenes / len(scenes) * 100:.1f}%",
                    )
                if no_location > 0:
                    scene_table.add_row(
                        "No Location",
                        str(no_location),
                        f"{no_location / len(scenes) * 100:.1f}%",
                    )

                # Time of day analysis
                time_counter = Counter()  # type: ignore[var-annotated]
                for scene in scenes:
                    if scene.location and scene.location.time:
                        time_counter[scene.location.time.upper()] += 1

                if time_counter:
                    scene_table.add_row("", "", "")  # Separator
                    for time, count in time_counter.most_common():
                        scene_table.add_row(
                            f"Time: {time}",
                            str(count),
                            f"{count / len(scenes) * 100:.1f}%",
                        )

                console.print(scene_table)
                console.print()

            # Character analysis
            if characters:
                char_table = Table(title="Character Analysis (Top 10)", style="yellow")
                char_table.add_column("Character", style="bright_yellow")
                char_table.add_column("Dialogue Lines", justify="right")
                char_table.add_column("Scene Appearances", justify="right")

                # Count dialogue and appearances per character
                char_stats = {}
                for char in characters:
                    char_stats[char.name] = {
                        "dialogue": 0,
                        "scenes": 0,
                    }

                # Process scenes to count character appearances and dialogue
                for scene in scenes:
                    # Track which characters appear in this scene
                    scene_chars = set()

                    # Parse fountain content to associate dialogue with characters
                    current_character = None
                    for element in scene.elements:
                        # Look for CHARACTER elements in the raw fountain
                        if hasattr(element, "element_type"):
                            if (
                                element.element_type.value == "dialogue"
                                and current_character
                            ):
                                # Count this dialogue for the current character
                                if current_character in char_stats:
                                    char_stats[current_character]["dialogue"] += 1
                                scene_chars.add(current_character)
                            elif element.element_type.value == "action":
                                # Check for character names in action
                                for char in characters:
                                    if char.name in element.text.upper():
                                        scene_chars.add(char.name)

                        # Check if this is a character name (looking at raw text)
                        if hasattr(element, "raw_text"):
                            raw_upper = element.raw_text.strip().upper()
                            # Character names are typically all caps
                            for char in characters:
                                if raw_upper.startswith(char.name):
                                    current_character = char.name
                                    break

                    # Update scene appearances
                    for char_name in scene_chars:
                        if char_name in char_stats:
                            char_stats[char_name]["scenes"] += 1

                # Alternative approach: re-parse to get proper character associations
                if all(stats["dialogue"] == 0 for stats in char_stats.values()):
                    # Fall back to counting based on character names in scenes
                    for scene in scenes:
                        for char in characters:
                            if char.id in scene.characters:
                                char_stats[char.name]["scenes"] += 1
                                # Estimate dialogue based on scene participation
                                # This is a rough estimate when proper parsing fails
                                char_stats[char.name]["dialogue"] += 1

                # Sort by dialogue count and show top 10
                sorted_chars = sorted(
                    char_stats.items(),
                    key=lambda x: (x[1]["dialogue"], x[1]["scenes"]),
                    reverse=True,
                )[:10]

                for char_name, stats in sorted_chars:
                    if stats["dialogue"] > 0 or stats["scenes"] > 0:
                        char_table.add_row(
                            char_name,
                            str(stats["dialogue"]),
                            str(stats["scenes"]),
                        )

                console.print(char_table)
                console.print()

            # Location analysis
            location_counter = Counter()  # type: ignore[var-annotated]
            for scene in scenes:
                if scene.location:
                    location_counter[scene.location.name] += 1

            if location_counter:
                loc_table = Table(title="Most Used Locations (Top 10)", style="magenta")
                loc_table.add_column("Location", style="bright_magenta")
                loc_table.add_column("Scene Count", justify="right")
                loc_table.add_column("Percentage", justify="right")

                for location, count in location_counter.most_common(10):
                    loc_table.add_row(
                        location,
                        str(count),
                        f"{count / len(scenes) * 100:.1f}%",
                    )

                console.print(loc_table)

            # Insights and recommendations
            console.print()
            console.print(
                Panel("[bold]Screenplay Insights[/bold]", style="bright_blue")
            )

            insights = []

            # Page length insight
            if estimated_pages < 90:
                insights.append(
                    "• [yellow]Short screenplay:[/yellow] "
                    "Consider expanding to reach feature length (90-120 pages)"
                )
            elif estimated_pages > 130:
                insights.append(
                    "• [yellow]Long screenplay:[/yellow] "
                    "Consider trimming to standard length (90-120 pages)"
                )
            else:
                insights.append(
                    "• [green]Good length:[/green] "
                    "Screenplay is within standard feature range"
                )

            # Scene distribution insight
            if scenes:
                if int_scenes > ext_scenes * 3:
                    insights.append(
                        "• [cyan]Interior heavy:[/cyan] "
                        "Mostly indoor scenes - good for budget"
                    )
                elif ext_scenes > int_scenes * 2:
                    insights.append(
                        "• [cyan]Exterior heavy:[/cyan] "
                        "Many outdoor scenes - weather dependent"
                    )

                # Character distribution
                if characters and len(characters) > 50:
                    insights.append(
                        "• [yellow]Large cast:[/yellow] "
                        "Consider consolidating minor characters"
                    )
                elif characters and len(characters) < 5:
                    insights.append(
                        "• [cyan]Small cast:[/cyan] Intimate character-driven story"
                    )

                # Scene length variance
                if scene_lengths:
                    avg_length = sum(scene_lengths) / len(scene_lengths)
                    if max(scene_lengths) > avg_length * 3:
                        insights.append(
                            "• [yellow]Pacing note:[/yellow] "
                            "Some very long scenes - check pacing"
                        )

                # Dialogue vs action ratio
                if total_dialogue_lines > 0 and total_action_lines > 0:
                    dialogue_ratio = total_dialogue_lines / (
                        total_dialogue_lines + total_action_lines
                    )
                    if dialogue_ratio > 0.7:
                        insights.append(
                            "• [cyan]Dialogue heavy:[/cyan] "
                            "Consider adding visual storytelling"
                        )
                    elif dialogue_ratio < 0.3:
                        insights.append(
                            "• [cyan]Action heavy:[/cyan] "
                            "Visual storytelling emphasized"
                        )

            for insight in insights:
                console.print(insight)

            if not insights:
                console.print(
                    "[dim]Analysis complete - screenplay appears well-balanced[/dim]"
                )

            # Log successful analysis
            logger.info(
                "screenplay analysis completed",
                script_path=str(script_path),
                scenes=len(scenes),
                characters=len(characters),
                words=total_words,
            )

        except FountainParsingError as e:
            console.print(f"[red]Error parsing screenplay:[/red] {e}")
            logger.error(
                "failed to parse screenplay",
                script_path=str(script_path),
                error=str(e),
            )
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            logger.error(
                "unexpected error during screenplay analysis",
                script_path=str(script_path),
                error=str(e),
            )
    else:
        # Show info about current database
        settings = get_settings()
        db_path = Path(settings.database.path)

        if db_path.exists():
            console.print(f"[bold blue]Database Info:[/bold blue] {db_path}")

            # Ensure database is initialized with schema
            if not initialize_database(db_path):
                console.print("[red]Failed to initialize database[/red]")
                raise typer.Exit(1)

            # Get and display database statistics
            with get_connection() as conn:
                stats_collector = DatabaseStatistics(conn)
                db_stats: dict[str, Any] = stats_collector.get_all_statistics()

                # Database Overview
                db_metrics: dict[str, Any] = db_stats["database"]
                console.print(f"\nSize: {db_metrics['file_size']:,} bytes")

                # Entity Summary Table
                console.print("\n[bold cyan]Entity Summary[/bold cyan]")
                entity_table = Table(show_header=True, header_style="bold")
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
                graph_stats: dict[str, Any] = db_stats["graph"]
                if graph_stats["total_nodes"] > 0:
                    console.print("\n[bold cyan]Graph Statistics[/bold cyan]")
                    graph_table = Table(show_header=True, header_style="bold")
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
                        console.print("\n[bold cyan]Node Types[/bold cyan]")
                        node_types_table = Table(show_header=True, header_style="bold")
                        node_types_table.add_column("Type", style="dim")
                        node_types_table.add_column("Count", justify="right")

                        for node_type, count in graph_stats["node_types"].items():
                            node_types_table.add_row(node_type, f"{count:,}")
                        console.print(node_types_table)

                    # Edge types breakdown
                    if graph_stats["edge_types"]:
                        console.print("\n[bold cyan]Edge Types[/bold cyan]")
                        edge_types_table = Table(show_header=True, header_style="bold")
                        edge_types_table.add_column("Type", style="dim")
                        edge_types_table.add_column("Count", justify="right")

                        for edge_type, count in graph_stats["edge_types"].items():
                            edge_types_table.add_row(edge_type, f"{count:,}")
                        console.print(edge_types_table)

                # Embedding Statistics
                embed_stats: dict[str, Any] = db_stats["embeddings"]
                if embed_stats["total_embeddings"] > 0:
                    console.print("\n[bold cyan]Embedding Coverage[/bold cyan]")
                    embed_table = Table(show_header=True, header_style="bold")
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
                usage: dict[str, Any] = db_stats["usage"]

                # Most connected characters
                if usage["most_connected_characters"]:
                    console.print("\n[bold cyan]Most Connected Characters[/bold cyan]")
                    char_table = Table(show_header=True, header_style="bold")
                    char_table.add_column("Character", style="bold")
                    char_table.add_column("Connections", justify="right")

                    for char in usage["most_connected_characters"][:5]:
                        char_table.add_row(char["name"], str(char["connections"]))
                    console.print(char_table)

                # Longest scripts
                if usage["longest_scripts"]:
                    console.print("\n[bold cyan]Longest Scripts[/bold cyan]")
                    script_table = Table(show_header=True, header_style="bold")
                    script_table.add_column("Script", style="bold")
                    script_table.add_column("Scenes", justify="right")

                    for script in usage["longest_scripts"][:5]:
                        script_table.add_row(script["title"], str(script["scenes"]))
                    console.print(script_table)

                # Busiest locations
                if usage["busiest_locations"]:
                    console.print("\n[bold cyan]Busiest Locations[/bold cyan]")
                    loc_table = Table(show_header=True, header_style="bold")
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
                    time_table = Table(show_header=True, header_style="bold")
                    time_table.add_column("Time of Day", style="dim")
                    time_table.add_column("Scenes", justify="right")

                    for time, count in list(usage["common_times_of_day"].items())[:5]:
                        time_table.add_row(time, str(count))
                    console.print(time_table)
        else:
            console.print(
                "[yellow]No database found. Use 'scriptrag script parse' "
                "to create one.[/yellow]"
            )
