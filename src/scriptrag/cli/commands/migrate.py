"""CLI command for database migrations."""

from typing import Annotated

import typer
from rich.console import Console

from scriptrag.config import get_logger
from scriptrag.database.migration import DatabaseMigrator

logger = get_logger(__name__)
console = Console()

app = typer.Typer()


@app.command()
def migrate_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            "-c",
            help="Check if migrations are needed without applying them",
        ),
    ] = False,
) -> None:
    """Apply database migrations to update the schema.

    This command checks for and applies any pending database migrations
    to keep your ScriptRAG database schema up to date.

    Use --check to see if migrations are needed without applying them.
    """
    try:
        migrator = DatabaseMigrator()

        if check:
            # Just check if migrations are needed
            if migrator.check_migration_needed():
                current_version = migrator.get_current_schema_version()
                available = migrator.get_available_migrations()
                pending = [v for v, _ in available if v > current_version]

                console.print(
                    f"[yellow]Current schema version: {current_version}[/yellow]"
                )
                pending_str = ", ".join(map(str, pending))
                console.print(f"[yellow]Pending migrations: {pending_str}[/yellow]")
                console.print("\nRun 'scriptrag migrate' to apply migrations.")
            else:
                console.print("[green]Database schema is up to date[/green]")
        else:
            # Apply migrations
            if not migrator.db_path.exists():
                console.print(
                    "[red]Database not found. Run 'scriptrag init' first.[/red]"
                )
                raise typer.Exit(1)

            num_applied = migrator.migrate()

            if num_applied > 0:
                console.print(
                    f"[green]Successfully applied {num_applied} migration(s)[/green]"
                )
                new_version = migrator.get_current_schema_version()
                console.print(f"Database schema is now at version {new_version}")
            else:
                console.print("[green]Database schema is already up to date[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Migration command failed")
        raise typer.Exit(1) from e
