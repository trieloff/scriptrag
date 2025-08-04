"""Initialize database command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api import DatabaseInitializer
from scriptrag.config import get_settings

console = Console()


def init_command(
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            "-d",
            help="Path to the SQLite database file",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force initialization, overwriting existing database",
        ),
    ] = False,
) -> None:
    """Initialize the ScriptRAG SQLite database.

    This command creates a new SQLite database with the ScriptRAG schema.
    If the database already exists, it will fail unless --force is specified.
    """
    settings = get_settings()
    initializer = DatabaseInitializer()

    try:
        # If force is used and database exists, confirm with user
        resolved_path = db_path or settings.database_path
        if (
            resolved_path.exists()
            and force
            and not typer.confirm(f"Overwrite existing database at {resolved_path}?")
        ):
            console.print("[yellow]Initialization cancelled.[/yellow]")
            raise typer.Exit(0)

        # Initialize database using API
        console.print("[green]Initializing database...[/green]")
        db_path = initializer.initialize_database(
            db_path=db_path,
            force=force,
            settings=settings,
        )
        console.print(
            f"[green]✓[/green] Database initialized successfully at {db_path}"
        )

    except (typer.Exit, typer.Abort):
        # Re-raise Typer control flow exceptions
        raise

    except FileExistsError as e:
        console.print(f"[red]Error:[/red] {e}", style="bold")
        raise typer.Exit(1) from e

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to initialize database: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e
