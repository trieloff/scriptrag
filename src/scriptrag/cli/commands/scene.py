"""Refactored scene management commands with clean separation of concerns."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api.scene_management import SceneManagementAPI
from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.cli.commands.scene_config import load_config_with_validation
from scriptrag.cli.formatters.base import OutputFormat
from scriptrag.cli.formatters.scene_formatter import SceneFormatter
from scriptrag.cli.utils.cli_handler import CLIHandler, async_cli_command
from scriptrag.cli.validators.project_validator import ProjectValidator
from scriptrag.cli.validators.scene_validator import (
    ScenePositionValidator,
    SceneValidator,
)
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
@async_cli_command
async def read_scene(
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
        scriptrag scene read --project "inception" --bible
        scriptrag scene read --project "inception" --bible-name "world_bible.md"
    """
    # Initialize handlers
    handler = CLIHandler(console)
    formatter = SceneFormatter(console)
    project_validator = ProjectValidator(allow_spaces=True)

    # Validate inputs
    project = project_validator.validate(project)

    # Load settings
    settings = load_config_with_validation(config)

    # Initialize API
    api = SceneManagementAPI(settings=settings)

    # Determine output format
    output_format = OutputFormat.JSON if json_output else OutputFormat.TEXT

    # Handle bible reading
    if bible or bible_name is not None:
        result = await api.read_bible(project, bible_name)
        if not result.success:
            handler.handle_error(Exception(result.error), json_output)
        formatter.print(result, output_format)
        return

    # Handle scene reading
    if scene is None:
        handler.handle_error(
            ValueError("Either --scene or --bible must be specified"),
            json_output,
        )

    # Validate and create scene identifier
    scene_validator = SceneValidator()
    scene_id = scene_validator.validate(
        {
            "project": project,
            "scene_number": scene,
            "season": season,
            "episode": episode,
        }
    )

    # Read scene through API
    scene_result = await api.read_scene(scene_id)

    if not scene_result.success:
        handler.handle_error(Exception(scene_result.error), json_output)

    # Format and output result
    formatter.print(scene_result, output_format)


@scene_app.command(name="add")
@async_cli_command
async def add_scene(
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
    """Add a new scene with automatic renumbering.

    Scene content can be provided via --content or piped from stdin.
    Content must be valid Fountain format starting with a scene heading.

    Examples:
        scriptrag scene add --project "inception" --before-scene 10
    """
    # Initialize handlers
    handler = CLIHandler(console)

    # Validate inputs
    project_validator = ProjectValidator(allow_spaces=True)
    project = project_validator.validate(project)

    # Validate position
    position_validator = ScenePositionValidator()
    reference_scene, position = position_validator.validate(
        {"after_scene": after_scene, "before_scene": before_scene}
    )

    # Load settings early to validate config path
    settings = load_config_with_validation(config)

    # Get content (let API perform Fountain validation)
    if content is None:
        content = handler.read_stdin(required=False) or ""

    # Initialize API
    api = SceneManagementAPI(settings=settings)

    # Create scene identifier for reference
    reference_id = SceneIdentifier(
        project=project,
        scene_number=reference_scene,
        season=season,
        episode=episode,
    )

    # Add scene through API
    result = await api.add_scene(reference_id, content, position)

    if not result.success:
        handler.handle_error(Exception(result.error), json_output)

    # Format success message
    if json_output:
        handler.handle_success(
            "Scene added successfully",
            {
                "created_scene": (
                    {"number": result.created_scene.number}
                    if result.created_scene
                    else None
                ),
                "renumbered_scenes": result.renumbered_scenes,
            },
            json_output=True,
        )
    else:
        scene_num = result.created_scene.number if result.created_scene else "unknown"
        renum = (
            f" Renumbered scenes: {', '.join(map(str, result.renumbered_scenes))}"
            if getattr(result, "renumbered_scenes", None)
            else ""
        )
        handler.handle_success(f"Scene added successfully as scene {scene_num}{renum}")


@scene_app.command(name="update")
@async_cli_command
async def update_scene(
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
    content: Annotated[
        str | None,
        typer.Option("--content", help="New scene content (or pipe from stdin)"),
    ] = None,
    check_conflicts: Annotated[
        bool,
        typer.Option(
            "--check-conflicts",
            help="Check if scene was modified since last read",
        ),
    ] = False,
    safe: Annotated[
        bool,
        typer.Option(
            "--safe",
            help="Alias for --check-conflicts (requires --last-read)",
        ),
    ] = False,
    last_read: Annotated[
        str | None,
        typer.Option(
            "--last-read",
            help="Last read timestamp (ISO format) for safe updates",
        ),
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
    """Update an existing scene.

    Content can be provided via --content or piped from stdin.

    Examples:
        scriptrag scene update --project "inception" --scene 42 --content "..."
        echo "New content" | scriptrag scene update --project "inception" --scene 42
    """
    # Initialize handlers
    handler = CLIHandler(console)
    formatter = SceneFormatter(console)

    # Validate inputs
    project_validator = ProjectValidator(allow_spaces=True)
    project = project_validator.validate(project)

    scene_validator = SceneValidator()
    scene_id = scene_validator.validate(
        {
            "project": project,
            "scene_number": scene,
            "season": season,
            "episode": episode,
        }
    )

    # Load settings early to validate config path
    settings = load_config_with_validation(config)

    # Get content (let API perform Fountain validation)
    if content is None:
        content = handler.read_stdin(required=False) or ""

    # Initialize API
    api = SceneManagementAPI(settings=settings)

    # Parse safe/last-read options
    effective_check = bool(check_conflicts or safe)
    parsed_last_read = None
    if last_read:
        from datetime import datetime

        try:
            parsed_last_read = datetime.fromisoformat(last_read)
        except Exception as e:  # pragma: no cover - defensive
            handler.handle_error(
                ValueError(f"Invalid --last-read format: {e}"), json_output
            )
            return

    # Update scene through API
    result = await api.update_scene(
        scene_id,
        content,
        check_conflicts=effective_check,
        last_read=parsed_last_read,
    )

    if not result.success:
        handler.handle_error(Exception(result.error), json_output)

    # Format and output result
    output_format = OutputFormat.JSON if json_output else OutputFormat.TEXT
    formatter.print(result, output_format)


@scene_app.command(name="delete")
@async_cli_command
async def delete_scene(
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
        bool,
        typer.Option(
            "--confirm",
            "--force",
            "-f",
            help="Confirm deletion without interactive prompt",
        ),
    ] = False,
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
    """Delete a scene with automatic renumbering.

    Examples:
        scriptrag scene delete --project "inception" --scene 42 --force
    """
    # Initialize handlers
    handler = CLIHandler(console)

    # Validate inputs
    project_validator = ProjectValidator(allow_spaces=True)
    project = project_validator.validate(project)

    scene_validator = SceneValidator()
    scene_id = scene_validator.validate(
        {
            "project": project,
            "scene_number": scene,
            "season": season,
            "episode": episode,
        }
    )

    # Confirmation handling (non-interactive by default for tests/CI)
    if not confirm:
        if json_output:
            handler.handle_error(
                ValueError("Deletion requires confirmation (--confirm)"), json_output
            )
            return
        handler.handle_success(
            "Warning: Deletion requires confirmation. Re-run with --confirm to proceed"
        )
        return

    # Load settings
    settings = load_config_with_validation(config)

    # Initialize API
    api = SceneManagementAPI(settings=settings)

    # Delete scene through API
    result = await api.delete_scene(scene_id, confirm=True)

    if not result.success:
        handler.handle_error(Exception(result.error), json_output)

    # Format success message
    if json_output:
        handler.handle_success(
            f"Scene {scene_id.key} deleted successfully",
            {
                "deleted_scene": scene_id.key,
                "renumbered_count": len(result.renumbered_scenes),
            },
            json_output=True,
        )
    else:
        msg = f"Scene {scene_id.key} deleted successfully"
        if result.renumbered_scenes:
            msg += f" ({len(result.renumbered_scenes)} scenes renumbered)"
        handler.handle_success(msg)
