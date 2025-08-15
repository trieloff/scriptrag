"""Scene management commands for AI-friendly editing."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from scriptrag.api.scene_management import SceneIdentifier, SceneManagementAPI
from scriptrag.config import get_logger

logger = get_logger(__name__)
console = Console()

# Create scene subcommand app
scene_app = typer.Typer(
    name="scene",
    help="AI-friendly scene management commands",
    pretty_exceptions_enable=False,
    add_completion=False,
)


@scene_app.command(name="read")
def read_scene(
    project: Annotated[
        str, typer.Option("--project", "-p", help="Project/script name")
    ],
    scene: Annotated[
        int | None, typer.Option("--scene", "-s", help="Scene number")
    ] = None,
    bible: Annotated[
        bool, typer.Option("--bible", "-b", help="Read script bible files")
    ] = False,
    bible_name: Annotated[
        str | None, typer.Option("--bible-name", help="Specific bible file to read")
    ] = None,
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    """Read a scene or script bible content.

    Examples:
        scriptrag scene read --project "breaking_bad" --season 1 --episode 1 --scene 3
        scriptrag scene read --project "inception" --scene 42
        scriptrag scene read --project "inception" --bible  # List available bible files
        scriptrag scene read --project "inception" --bible-name "world_bible.md"
    """
    try:
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

        # Initialize API
        api = SceneManagementAPI(settings=settings)

        # Check if reading bible content
        if bible or bible_name is not None:
            # Reading bible content
            bible_result = asyncio.run(api.read_bible(project, bible_name))

            if not bible_result.success:
                console.print(f"[red]Error: {bible_result.error}[/red]")
                raise typer.Exit(1)

            if json_output:
                if bible_result.content:
                    # Specific bible content
                    output = {
                        "success": True,
                        "content": bible_result.content,
                    }
                else:
                    # List of bible files
                    output = {
                        "success": True,
                        "bible_files": bible_result.bible_files,
                    }
                console.print_json(data=output)
            else:
                if bible_result.content:
                    # Display bible content
                    console.print(
                        Panel(
                            Syntax(bible_result.content, "markdown", theme="monokai"),
                            title=f"Bible: {bible_name or 'Content'}",
                            subtitle=f"Project: {project}",
                        )
                    )
                else:
                    # Display list of available bible files
                    console.print(
                        f"\n[green]Available bible files for "
                        f"project '{project}':[/green]\n"
                    )
                    for bible_file in bible_result.bible_files:
                        size_kb = bible_file["size"] / 1024
                        console.print(
                            f"  • [cyan]{bible_file['name']}[/cyan] "
                            f"({bible_file['path']}) - {size_kb:.1f} KB"
                        )
                    console.print(
                        "\n[dim]Use --bible-name <filename> to read a "
                        "specific bible file[/dim]"
                    )
            return

        # Reading scene content
        if scene is None:
            console.print(
                "[red]Error: Either --scene or --bible must be specified[/red]"
            )
            raise typer.Exit(1)

        # Create scene identifier
        scene_id = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Read scene (run async operation)
        result = asyncio.run(api.read_scene(scene_id))

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        if json_output:
            if result.scene:
                output = {
                    "success": True,
                    "scene_number": result.scene.number,
                    "heading": result.scene.heading,
                    "content": result.scene.content,
                    "last_read": result.last_read.isoformat()
                    if result.last_read
                    else None,
                }
                console.print_json(data=output)
        else:
            # Display scene content
            if result.scene:
                console.print(
                    Panel(
                        Syntax(result.scene.content, "text", theme="monokai"),
                        title=f"Scene {scene_id.key}",
                        subtitle=result.scene.heading,
                    )
                )

            # Display read timestamp
            if result.last_read:
                console.print(
                    f"\n[green]Last read:[/green] {result.last_read.isoformat()}"
                )

    except Exception as e:
        logger.error(f"Failed to read: {e}")
        console.print(f"[red]Failed to read: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command(name="add")
def add_scene(
    project: Annotated[
        str, typer.Option("--project", "-p", help="Project/script name")
    ],
    after_scene: Annotated[
        int | None, typer.Option("--after-scene", help="Add after this scene number")
    ] = None,
    before_scene: Annotated[
        int | None, typer.Option("--before-scene", help="Add before this scene number")
    ] = None,
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    content: Annotated[
        str | None,
        typer.Option("--content", help="Scene content (or pipe from stdin)"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    r"""Add a new scene with automatic renumbering.

    Scene content can be provided via --content or piped from stdin.
    Content must be valid Fountain format starting with a scene heading.

    Examples:
        scriptrag scene add --project "inception" --before-scene 10

    Use --content flag or pipe content via stdin.
    """
    try:
        # Validate position arguments
        if after_scene is None and before_scene is None:
            console.print(
                "[red]Error: Must specify either --after-scene or --before-scene[/red]"
            )
            raise typer.Exit(1)

        if after_scene is not None and before_scene is not None:
            console.print(
                "[red]Error: Cannot specify both --after-scene and --before-scene[/red]"
            )
            raise typer.Exit(1)

        # Get content from stdin if not provided
        if content is None:
            if sys.stdin.isatty():
                console.print(
                    "[red]Error: No content provided. Use --content or "
                    "pipe from stdin[/red]"
                )
                raise typer.Exit(1)
            content = sys.stdin.read()

        # Determine reference scene and position
        if after_scene is not None:
            reference_scene = after_scene
            position = "after"
        else:
            reference_scene = before_scene  # type: ignore[assignment]
            position = "before"

        # Create scene identifier for reference
        scene_id = SceneIdentifier(
            project=project,
            scene_number=reference_scene,
            season=season,
            episode=episode,
        )

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

        # Initialize API
        api = SceneManagementAPI(settings=settings)

        # Add scene
        result = asyncio.run(api.add_scene(scene_id, content, position))

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        # Display success message
        new_scene_id = SceneIdentifier(
            project=project,
            scene_number=(
                reference_scene + 1 if position == "after" else reference_scene
            ),
            season=season,
            episode=episode,
        )
        console.print(f"[green]✓[/green] Scene added: {new_scene_id.key}")

        if result.renumbered_scenes:
            console.print(
                f"[yellow]Renumbered scenes:[/yellow] "
                f"{', '.join(map(str, result.renumbered_scenes))}"
            )

    except Exception as e:
        logger.error(f"Failed to add scene: {e}")
        console.print(f"[red]Failed to add scene: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command(name="update")
def update_scene(
    project: Annotated[
        str, typer.Option("--project", "-p", help="Project/script name")
    ],
    scene: Annotated[int, typer.Option("--scene", "-s", help="Scene number")],
    safe: Annotated[
        bool, typer.Option("--safe", help="Check for conflicts before updating")
    ] = False,
    last_read: Annotated[
        str | None,
        typer.Option(
            "--last-read",
            help="ISO timestamp of when scene was last read (for --safe mode)",
        ),
    ] = None,
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    content: Annotated[
        str | None,
        typer.Option("--content", help="New scene content (or pipe from stdin)"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
) -> None:
    r"""Update a scene with optional conflict checking.

    By default, updates happen immediately without conflict checking.
    Use --safe flag for conflict detection (requires --last-read timestamp).
    Content must be valid Fountain format.

    Examples:
        # Simple update (no conflict checking)
        scriptrag scene update --project "inception" --scene 42

        # Safe update (with conflict checking)
        scriptrag scene update --safe --project "inception" --scene 42 \
            --last-read "2024-01-15T10:30:00"

    Use --content flag or pipe content via stdin.
    """
    try:
        # Get content from stdin if not provided
        if content is None:
            if sys.stdin.isatty():
                console.print(
                    "[red]Error: No content provided. Use --content or "
                    "pipe from stdin[/red]"
                )
                raise typer.Exit(1)
            content = sys.stdin.read()

        # Create scene identifier
        scene_id = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Parse last_read timestamp if provided
        last_read_dt = None
        if safe:
            if not last_read:
                console.print(
                    "[red]Error: --last-read timestamp required "
                    "when using --safe flag[/red]"
                )
                raise typer.Exit(1)
            try:
                last_read_dt = datetime.fromisoformat(last_read)
            except ValueError as e:
                console.print(
                    f"[red]Error: Invalid timestamp format: {last_read}[/red]"
                )
                console.print("[dim]Use ISO format: YYYY-MM-DDTHH:MM:SS[/dim]")
                raise typer.Exit(1) from e

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

        # Initialize API
        api = SceneManagementAPI(settings=settings)

        # Update scene
        result = asyncio.run(
            api.update_scene(
                scene_id, content, check_conflicts=safe, last_read=last_read_dt
            )
        )

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            if result.validation_errors:
                console.print("[red]Validation errors:[/red]")
                for error in result.validation_errors:
                    console.print(f"  • {error}")
            raise typer.Exit(1)

        # Display success message
        console.print(f"[green]✓[/green] Scene updated: {scene_id.key}")

    except Exception as e:
        logger.error(f"Failed to update scene: {e}")
        console.print(f"[red]Failed to update scene: {e}[/red]")
        raise typer.Exit(1) from e


@scene_app.command(name="delete")
def delete_scene(
    project: Annotated[
        str, typer.Option("--project", "-p", help="Project/script name")
    ],
    scene: Annotated[int, typer.Option("--scene", "-s", help="Scene number")],
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Confirm deletion")
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
    r"""Delete a scene with automatic renumbering.

    Requires --confirm flag to prevent accidental deletions.
    Automatically renumbers subsequent scenes.

    Examples:
        scriptrag scene delete --project "inception" --scene 42 --confirm
    """
    if not confirm:
        console.print(
            "[yellow]Warning: This will permanently delete the scene.[/yellow]"
        )
        console.print("Add --confirm flag to proceed with deletion.")
        raise typer.Exit(0)

    try:
        # Create scene identifier
        scene_id = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

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

        # Initialize API
        api = SceneManagementAPI(settings=settings)

        # Delete scene
        result = asyncio.run(api.delete_scene(scene_id, confirm=True))

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        # Display success message
        console.print(f"[green]✓[/green] Scene deleted: {scene_id.key}")

        if result.renumbered_scenes:
            console.print(
                f"[yellow]Renumbered scenes:[/yellow] "
                f"{', '.join(map(str, result.renumbered_scenes))}"
            )

    except Exception as e:
        logger.error(f"Failed to delete scene: {e}")
        console.print(f"[red]Failed to delete scene: {e}[/red]")
        raise typer.Exit(1) from e
