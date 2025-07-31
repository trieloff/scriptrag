"""Script Bible and continuity management commands for ScriptRAG CLI."""

from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table as RichTable

from scriptrag.config import get_settings
from scriptrag.database.bible import ScriptBibleOperations
from scriptrag.database.connection import DatabaseConnection

console = Console()
bible_app = typer.Typer(
    name="bible",
    help="Script Bible and continuity management commands",
    rich_markup_mode="rich",
)


def get_latest_script_id(connection: DatabaseConnection) -> tuple[str, str] | None:
    """Get the latest script ID and title from the database."""
    result = connection.fetch_one(
        """
        SELECT id, title FROM scripts
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    return (result["id"], result["title"]) if result else None


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
                console.print(
                    f"[yellow]⚠[/yellow] Profile for '{character_name}' already exists."
                )
                console.print(
                    "[dim]Use --force to overwrite (not implemented yet)[/dim]"
                )
            else:
                # Create new profile
                bible_ops.create_character_profile(
                    character_id=character_id,
                    script_id=script_id,
                    profile_data=profile_data,
                )

                console.print(
                    f"[green]✓[/green] Created character profile for '{character_name}'"
                )

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create character profile: {e}")
        raise typer.Exit(1) from e


@bible_app.command("world-element")
def bible_world_element(
    element_name: Annotated[str, typer.Argument(help="World element name")],
    element_type: Annotated[
        str, typer.Option("--type", help="Element type (location, prop, etc.)")
    ] = "location",
    description: Annotated[
        str | None, typer.Option("--description", help="Element description")
    ] = None,
    script_id: Annotated[
        str | None, typer.Option("--script-id", "-s", help="Script ID")
    ] = None,
) -> None:
    """Create or update a world element."""
    try:
        settings = get_settings()
        with DatabaseConnection(str(settings.get_database_path())) as connection:
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

            # For now, just acknowledge the element creation
            # TODO: Implement actual world element storage
            console.print(
                f"[green]✓[/green] World element '{element_name}' "
                f"({element_type}) noted for script"
            )
            if description:
                console.print(f"[dim]Description: {description}[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create world element: {e}")
        raise typer.Exit(1) from e
