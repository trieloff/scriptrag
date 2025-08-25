"""CLI command for scriptrag watch - monitor filesystem for Fountain file changes."""

import signal
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from watchdog.observers import Observer

from scriptrag.cli.commands.pull import pull_command
from scriptrag.cli.utils.file_watcher import FountainFileHandler
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings

logger = get_logger(__name__)
console = Console()

# Global observer for signal handling
_observer: Any = None
_handler: Any = None


def signal_handler(_signum: int, _frame: Any) -> None:
    """Handle shutdown signals gracefully.

    Args:
        _signum: Signal number (unused)
        _frame: Current stack frame (unused)
    """
    console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    if _observer and _observer.is_alive():
        _observer.stop()
    if _handler:
        _handler.stop_processing(timeout=5.0)
    sys.exit(0)


def watch_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to watch for Fountain file changes (default: current directory)"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-processing on every change"),
    ] = False,
    no_recursive: Annotated[
        bool,
        typer.Option("--no-recursive", help="Don't watch subdirectories"),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of scripts to process in each batch",
        ),
    ] = 10,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (YAML, TOML, or JSON)",
        ),
    ] = None,
    initial_pull: Annotated[
        bool,
        typer.Option(
            "--initial-pull/--no-initial-pull",
            help="Run a full pull before starting to watch",
        ),
    ] = True,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            "-t",
            help="Maximum watch duration in seconds (0 for unlimited)",
        ),
    ] = 0,
) -> None:
    """Watch for Fountain file changes and automatically pull them.

    This command monitors the filesystem for changes to Fountain files
    and automatically runs the pull workflow (analyze + index) when
    files are created or modified.

    Press Ctrl+C to stop watching.
    """
    global _observer, _handler

    try:
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Load settings
        if config:
            if not config.exists():
                console.print(f"[red]Error: Config file not found: {config}[/red]")
                raise typer.Exit(1)

            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[config],
            )
        else:
            settings = get_settings()

        # Resolve and validate watch path
        watch_path = path or Path.cwd()
        if not watch_path.exists():
            console.print(f"[red]Error: Path {watch_path} does not exist[/red]")
            raise typer.Exit(1)

        # Ensure watch_path is absolute for security
        watch_path = watch_path.resolve()

        # Run initial pull if requested
        if initial_pull:
            console.print("[cyan]Running initial pull...[/cyan]")
            pull_command(
                path=watch_path,
                force=force,
                dry_run=False,
                no_recursive=no_recursive,
                batch_size=batch_size,
                config=config,
            )

        # Setup file watching
        console.print(f"\n[green]Watching for changes in: {watch_path}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Status tracking with secure path display
        status_log: list[str] = []
        base_path = watch_path

        def update_status(status: str, path: Path, error: str | None = None) -> None:
            """Update status display with secure path handling.

            Args:
                status: Status type (processing, completed, error)
                path: File path
                error: Error message if any
            """
            # Secure path display - only show relative paths within watch directory
            try:
                if path.is_relative_to(base_path):
                    display_path = path.relative_to(base_path)
                else:
                    # Security: Don't expose paths outside watch directory
                    display_path = Path(path.name)  # Only show filename
            except (ValueError, TypeError):
                display_path = Path(path.name)  # Fallback to filename only

            timestamp = time.strftime("%H:%M:%S")

            if status == "processing":
                status_log.append(f"[{timestamp}] 🔄 Processing: {display_path}")
            elif status == "completed":
                status_log.append(f"[{timestamp}] ✅ Updated: {display_path}")
            elif status == "error":
                # Sanitize error messages
                safe_error = str(error)[:100] if error else "Unknown error"
                msg = f"[{timestamp}] ❌ Error: {display_path} - {safe_error}"
                status_log.append(msg)

            # Keep only last 10 entries
            if len(status_log) > 10:
                status_log.pop(0)

            # Create status table
            table = Table(title="File Watch Status", show_header=False)
            table.add_column("Status")

            for entry in status_log:
                table.add_row(entry)

            # Display in a panel
            panel = Panel(
                table,
                title="[bold cyan]ScriptRAG Watch[/bold cyan]",
                border_style="cyan",
            )
            console.clear()
            console.print(panel)

        # Create event handler with improved configuration
        _handler = FountainFileHandler(
            settings=settings,
            force=force,
            batch_size=batch_size,
            callback=update_status,
            max_queue_size=100,
            batch_timeout=5.0,
        )

        # Start async processor
        _handler.start_processing()

        # Setup observer
        _observer = Observer()
        _observer.schedule(
            _handler,
            str(watch_path),
            recursive=not no_recursive,
        )

        # Start watching
        _observer.start()

        # Display initial status
        table = Table(title="File Watch Status", show_header=False)
        table.add_column("Status")
        table.add_row(f"👀 Watching: {watch_path}")
        table.add_row(f"📁 Recursive: {'Yes' if not no_recursive else 'No'}")
        table.add_row(f"🔄 Force mode: {'On' if force else 'Off'}")
        table.add_row(f"⏱️ Timeout: {timeout}s" if timeout > 0 else "⏱️ Timeout: None")
        table.add_row("")
        table.add_row("[dim]Waiting for file changes...[/dim]")

        panel = Panel(
            table,
            title="[bold cyan]ScriptRAG Watch[/bold cyan]",
            border_style="cyan",
        )
        console.print(panel)

        # Main watch loop with timeout support
        start_time = time.time()
        try:
            while True:
                time.sleep(1)
                if timeout > 0 and (time.time() - start_time) >= timeout:
                    msg = f"\n[yellow]Watch timeout reached ({timeout}s)[/yellow]"
                    console.print(msg)
                    break
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping file watch...[/yellow]")

        # Graceful shutdown
        _observer.stop()
        _handler.stop_processing(timeout=5.0)
        _observer.join(timeout=10.0)

        console.print("[green]✓ Watch stopped[/green]")

    except ImportError as e:
        console.print(f"[red]Error: Required components not available: {e}[/red]")
        console.print(
            "[yellow]Tip: Install watchdog with: pip install watchdog[/yellow]"
        )
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Watch command failed")
        raise typer.Exit(1) from e
    finally:
        # Ensure cleanup
        if _observer and _observer.is_alive():
            _observer.stop()
        if _handler:
            _handler.stop_processing(timeout=2.0)
