"""Scene management commands for AI-friendly editing."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from scriptrag.api.scene_management import SceneManagementAPI
from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.cli.commands.scene_config import load_config_with_validation
from scriptrag.cli.scene_formatter import SceneFormatter
from scriptrag.config import get_logger

logger = get_logger(__name__)
console = Console()
formatter = SceneFormatter(console)

# Position type for scene operations
PositionType = Literal["after", "before"]

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
        # Load settings with proper precedence
        settings = load_config_with_validation(config)

        # Initialize API
        api: SceneManagementAPI = SceneManagementAPI(settings=settings)

        # Check if reading bible content
        if bible or bible_name is not None:
            # Reading bible content
            from scriptrag.api.scene_models import BibleReadResult

            bible_result: BibleReadResult = asyncio.run(
                api.read_bible(project, bible_name)
            )

            if not bible_result.success:
                console.print(f"[red]Error: {bible_result.error}[/red]")
                raise typer.Exit(1)

            # Use formatter to display bible content
            formatter.format_bible_display(
                bible_result.content,
                bible_result.bible_files,
                project,
                bible_name,
                json_output,
            )
            return

        # Reading scene content
        if scene is None:
            console.print(
                "[red]Error: Either --scene or --bible must be specified[/red]"
            )
            raise typer.Exit(1)

        # Create scene identifier
        scene_id: SceneIdentifier = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Read scene (run async operation)
        from scriptrag.api.scene_models import ReadSceneResult

        result: ReadSceneResult = asyncio.run(api.read_scene(scene_id))

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        # Use formatter to display scene
        if result.scene:
            formatter.format_scene_display(
                result.scene,
                scene_id,
                result.last_read,
                json_output,
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
            reference_scene: int = after_scene
            position: PositionType = "after"
        else:
            # At this point, before_scene must be not None due to validation above
            if before_scene is None:
                raise ValueError(
                    "Internal error: before_scene is None after validation"
                )
            reference_scene = before_scene
            position = "before"

        # Create scene identifier for reference
        scene_id: SceneIdentifier = SceneIdentifier(
            project=project,
            scene_number=reference_scene,
            season=season,
            episode=episode,
        )

        # Load settings with proper precedence
        settings = load_config_with_validation(config)

        # Initialize API
        api: SceneManagementAPI = SceneManagementAPI(settings=settings)

        # Add scene
        from scriptrag.api.scene_models import AddSceneResult

        result: AddSceneResult = asyncio.run(api.add_scene(scene_id, content, position))

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        # Display success message using formatter
        new_scene_id: SceneIdentifier = SceneIdentifier(
            project=project,
            scene_number=(
                reference_scene + 1 if position == "after" else reference_scene
            ),
            season=season,
            episode=episode,
        )
        formatter.format_operation_result(
            "add",
            True,
            new_scene_id,
            details={"renumbered_scenes": result.renumbered_scenes},
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
        scene_id: SceneIdentifier = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Parse last_read timestamp if provided
        last_read_dt: datetime | None = None
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

        # Load settings with proper precedence
        settings = load_config_with_validation(config)

        # Initialize API
        api: SceneManagementAPI = SceneManagementAPI(settings=settings)

        # Update scene
        from scriptrag.api.scene_models import UpdateSceneResult

        result: UpdateSceneResult = asyncio.run(
            api.update_scene(
                scene_id, content, check_conflicts=safe, last_read=last_read_dt
            )
        )

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            if result.validation_errors:
                formatter.format_validation_errors(result.validation_errors)
            raise typer.Exit(1)

        # Display success message using formatter
        formatter.format_operation_result(
            "update",
            True,
            scene_id,
        )

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
        scene_id: SceneIdentifier = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Load settings with proper precedence
        settings = load_config_with_validation(config)

        # Initialize API
        api: SceneManagementAPI = SceneManagementAPI(settings=settings)

        # Delete scene
        from scriptrag.api.scene_models import DeleteSceneResult

        result: DeleteSceneResult = asyncio.run(
            api.delete_scene(scene_id, confirm=True)
        )

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        # Display success message using formatter
        formatter.format_operation_result(
            "delete",
            True,
            scene_id,
            details={"renumbered_scenes": result.renumbered_scenes},
        )

    except Exception as e:
        logger.error(f"Failed to delete scene: {e}")
        console.print(f"[red]Failed to delete scene: {e}[/red]")
        raise typer.Exit(1) from e
