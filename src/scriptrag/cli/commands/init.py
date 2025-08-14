"""Initialize database command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api import DatabaseInitializer

console = Console()


def init_command(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force initialization, overwriting existing database",
        ),
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
    """Initialize the ScriptRAG SQLite database.

    This command creates a new SQLite database with the ScriptRAG schema.
    If the database already exists, it will fail unless --force is specified.
    """
    # Load settings with proper precedence, including global db_path
    from scriptrag.cli.utils.db_path import get_settings_with_db_override

    settings = get_settings_with_db_override(ctx, config_path=config)

    initializer = DatabaseInitializer()

    try:
        # If force is used and database exists, confirm with user (unless in test mode)
        resolved_path = settings.database_path
        if resolved_path.exists() and force:
            # Check if we're in a test environment (no stdin)
            import sys

            if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
                if not typer.confirm(
                    f"Overwrite existing database at {resolved_path}?"
                ):
                    console.print("[yellow]Initialization cancelled.[/yellow]")
                    raise typer.Exit(0)
            else:
                # In test mode or non-interactive, proceed without asking
                console.print(
                    f"[yellow]Overwriting database at {resolved_path}[/yellow]"
                )

        # Initialize database using API
        console.print("[green]Initializing database...[/green]")
        db_path = initializer.initialize_database(
            db_path=settings.database_path,
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
