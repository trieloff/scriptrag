"""Scene management commands for AI-friendly editing."""

import sys
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
    scene: Annotated[int, typer.Option("--scene", "-s", help="Scene number")],
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Read a scene and get a session token for updates.

    The session token is valid for 10 minutes and must be used for updates.

    Examples:
        scriptrag scene read --project "breaking_bad" --season 1 --episode 1 --scene 3
        scriptrag scene read --project "inception" --scene 42
    """
    try:
        # Create scene identifier
        scene_id = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Initialize API
        api = SceneManagementAPI()

        # Read scene (run async operation)
        import asyncio

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
                    "session_token": result.session_token,
                    "expires_at": result.expires_at.isoformat()
                    if result.expires_at
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

            # Display session info
            console.print(f"\n[green]Session Token:[/green] {result.session_token}")
            if result.expires_at:
                console.print(
                    f"[yellow]Expires at:[/yellow] {result.expires_at.isoformat()}"
                )
            console.print(
                "\n[dim]Use this token with 'scriptrag scene update' "
                "within 10 minutes[/dim]"
            )

    except Exception as e:
        logger.error(f"Failed to read scene: {e}")
        console.print(f"[red]Failed to read scene: {e}[/red]")
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
        typer.Option("--content", "-c", help="Scene content (or pipe from stdin)"),
    ] = None,
) -> None:
    """Add a new scene with automatic renumbering.

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

        # Initialize API
        api = SceneManagementAPI()

        # Add scene
        import asyncio

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
    token: Annotated[
        str, typer.Option("--token", "-t", help="Session token from read command")
    ],
    season: Annotated[
        int | None, typer.Option("--season", help="Season number (for TV)")
    ] = None,
    episode: Annotated[
        int | None, typer.Option("--episode", "-e", help="Episode number (for TV)")
    ] = None,
    content: Annotated[
        str | None,
        typer.Option("--content", "-c", help="New scene content (or pipe from stdin)"),
    ] = None,
) -> None:
    """Update a scene using a valid session token.

    Requires a session token from a recent 'scene read' command (within 10 minutes).
    Content must be valid Fountain format.

    Examples:
        scriptrag scene update --project "inception" --scene 42 --token "xyz789"

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

        # Initialize API
        api = SceneManagementAPI()

        # Update scene
        import asyncio

        result = asyncio.run(api.update_scene(scene_id, content, token))

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
) -> None:
    """Delete a scene with automatic renumbering.

    Requires --confirm flag to prevent accidental deletions.
    Automatically renumbers subsequent scenes.

    Examples:
        scriptrag scene delete --project "inception" --scene 42 --confirm
    """
    try:
        if not confirm:
            console.print(
                "[yellow]Warning: This will permanently delete the scene.[/yellow]"
            )
            console.print("Add --confirm flag to proceed with deletion.")
            raise typer.Exit(0)

        # Create scene identifier
        scene_id = SceneIdentifier(
            project=project,
            scene_number=scene,
            season=season,
            episode=episode,
        )

        # Initialize API
        api = SceneManagementAPI()

        # Delete scene
        import asyncio

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
