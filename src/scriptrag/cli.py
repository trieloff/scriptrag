"""ScriptRAG Command Line Interface."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.api import DatabaseInitializer

app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    pretty_exceptions_enable=False,
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=True,
)
console = Console()


class CLIContext:
    """CLI context for dependency injection."""

    def __init__(self, db_initializer: DatabaseInitializer | None = None) -> None:
        """Initialize CLI context.

        Args:
            db_initializer: Database initializer instance.
        """
        self.db_initializer = db_initializer or DatabaseInitializer()


# Global context for dependency injection
_context = CLIContext()


def set_cli_context(context: CLIContext) -> None:
    """Set CLI context for dependency injection.

    Args:
        context: CLI context to use.
    """
    global _context
    _context = context


@app.command(name="init")
def init(
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
    # Default database path
    if db_path is None:
        db_path = Path.cwd() / "scriptrag.db"

    # Resolve to absolute path
    db_path = db_path.resolve()

    try:
        # Check if database exists
        if db_path.exists() and not force:
            console.print(
                f"[red]Error:[/red] Database already exists at {db_path}\n"
                "Use --force to overwrite the existing database.",
                style="bold",
            )
            raise typer.Exit(1)

        # Confirm if force is used
        if (
            db_path.exists()
            and force
            and not typer.confirm(f"Overwrite existing database at {db_path}?")
        ):
            console.print("[yellow]Initialization cancelled.[/yellow]")
            raise typer.Exit(0)

        # Initialize database
        console.print(f"[green]Initializing database at {db_path}...[/green]")
        _context.db_initializer.initialize_database(db_path, force=force)
        console.print("[green]✓[/green] Database initialized successfully!")

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


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
