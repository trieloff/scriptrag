"""Database management commands for ScriptRAG CLI."""

import re
import sqlite3
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.config import get_logger, get_settings

# Create database app
db_app = typer.Typer(
    name="db",
    help="Database management commands",
    rich_markup_mode="rich",
)

console = Console()


@db_app.command("init")
def db_init(
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Database path (default: from config)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force creation even if database exists",
        ),
    ] = False,
) -> None:
    """Initialize a new database with the latest schema."""
    from scriptrag.database.migrations import initialize_database

    logger = get_logger(__name__)
    settings = get_settings()

    # Use provided path or default from config
    database_path = db_path or Path(settings.database.path)

    # Check if database already exists
    if database_path.exists() and not force:
        console.print(f"[red]Database already exists: {database_path}[/red]")
        console.print(
            "[yellow]Use --force to reinitialize (this will not delete data)[/yellow]"
        )
        raise typer.Exit(1)

    try:
        # Ensure parent directory exists
        database_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        console.print(f"[blue]Initializing database at {database_path}...[/blue]")
        success = initialize_database(database_path)

        if success:
            console.print(
                f"[green]✓[/green] Database initialized successfully: {database_path}"
            )
            logger.info("Database initialized", path=str(database_path))
        else:
            console.print("[red]✗ Database initialization failed[/red]")
            logger.error("Database initialization failed", path=str(database_path))
            raise typer.Exit(1)

    except PermissionError as e:
        logger.error(
            "Permission denied initializing database",
            error=str(e),
            path=str(database_path),
        )
        console.print(
            f"[red]Permission denied: Cannot create database at {database_path}[/red]"
        )
        console.print(
            "[yellow]Check that you have write permissions to the directory[/yellow]"
        )
        raise typer.Exit(1) from e
    except OSError as e:
        if "No space left on device" in str(e):
            logger.error(
                "No disk space for database", error=str(e), path=str(database_path)
            )
            console.print(
                f"[red]Disk full: Cannot create database at {database_path}[/red]"
            )
            console.print("[yellow]Free up disk space and try again[/yellow]")
        else:
            logger.error(
                "OS error initializing database", error=str(e), path=str(database_path)
            )
            console.print(f"[red]System error: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(
            "Unexpected error initializing database",
            error=str(e),
            path=str(database_path),
        )
        console.print(f"[red]Error initializing database: {e}[/red]")
        console.print(
            "[yellow]This may indicate a corrupted database or system issue[/yellow]"
        )
        raise typer.Exit(1) from e


@db_app.command("wipe")
def db_wipe(
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Database path (default: from config)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
) -> None:
    """Drop all data from the database (requires confirmation)."""
    logger = get_logger(__name__)
    settings = get_settings()

    # Use provided path or default from config
    database_path = db_path or Path(settings.database.path)

    # Check if database exists
    if not database_path.exists():
        console.print(f"[red]Database does not exist: {database_path}[/red]")
        raise typer.Exit(1)

    # Confirm with user unless --force is used
    if not force:
        console.print(
            f"[yellow]⚠️  WARNING: This will delete ALL data from "
            f"{database_path}[/yellow]"
        )
        console.print("[yellow]This action cannot be undone![/yellow]")
        confirm = typer.confirm("Are you sure you want to continue?", default=False)
        if not confirm:
            console.print("[blue]Operation cancelled[/blue]")
            raise typer.Exit(0)

    try:
        # Get list of tables to drop (excluding sqlite system tables)
        with sqlite3.connect(database_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                console.print("[yellow]Database is already empty[/yellow]")
                return

            console.print(f"[blue]Dropping {len(tables)} tables...[/blue]")

            # Disable foreign key constraints temporarily
            conn.execute("PRAGMA foreign_keys = OFF")

            # Drop each table with SQL injection protection
            for table in tables:
                # Validate table name contains only allowed characters
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
                    logger.warning(f"Skipping table with invalid name: {table}")
                    console.print(
                        f"  [yellow]Skipped invalid table name: {table}[/yellow]"
                    )
                    continue

                # Use proper identifier quoting for SQLite
                conn.execute(f'DROP TABLE IF EXISTS "{table}"')
                console.print(f"  [dim]Dropped table: {table}[/dim]")

            # Re-enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")

            conn.commit()

        console.print(f"[green]✓[/green] Database wiped successfully: {database_path}")
        logger.info(
            "Database wiped", path=str(database_path), tables_dropped=len(tables)
        )

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error("Database is locked", error=str(e), path=str(database_path))
            console.print(f"[red]Database is locked: {database_path}[/red]")
            console.print(
                "[yellow]Another process may be using the database. "
                "Close it and try again[/yellow]"
            )
        else:
            logger.error(
                "Database operation failed", error=str(e), path=str(database_path)
            )
            console.print(f"[red]Database error: {e}[/red]")
        raise typer.Exit(1) from e
    except PermissionError as e:
        logger.error(
            "Permission denied wiping database", error=str(e), path=str(database_path)
        )
        console.print(
            f"[red]Permission denied: Cannot modify database at {database_path}[/red]"
        )
        console.print(
            "[yellow]Check that you have write permissions to the file[/yellow]"
        )
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(
            "Unexpected error wiping database", error=str(e), path=str(database_path)
        )
        console.print(f"[red]Error wiping database: {e}[/red]")
        raise typer.Exit(1) from e
