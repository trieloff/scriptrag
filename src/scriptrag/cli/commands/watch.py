"""CLI command for scriptrag watch - monitor filesystem for Fountain file changes."""

import asyncio
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings

logger = get_logger(__name__)
console = Console()

app = typer.Typer()


class FountainFileHandler(FileSystemEventHandler):
    """Handler for Fountain file changes."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        force: bool = False,
        batch_size: int = 10,
        callback: Any | None = None,
    ) -> None:
        """Initialize the handler.

        Args:
            settings: ScriptRAG settings
            force: Force re-processing
            batch_size: Batch size for indexing
            callback: Callback for status updates
        """
        self.settings = settings
        self.force = force
        self.batch_size = batch_size
        self.callback = callback
        self.processing: set[str] = set()
        self.last_processed: dict[str, float] = {}
        self.debounce_seconds = 2  # Wait 2 seconds after last change

    def should_process(self, path: Path) -> bool:
        """Check if a file should be processed.

        Args:
            path: File path to check

        Returns:
            True if file should be processed
        """
        # Check if it's a Fountain file
        if path.suffix.lower() not in [".fountain", ".spmd"]:
            return False

        # Check if it's already being processed
        if str(path) in self.processing:
            return False

        # Check debounce
        last_time = self.last_processed.get(str(path), 0)
        return time.time() - last_time >= self.debounce_seconds

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events.

        Args:
            event: Filesystem event
        """
        if event.is_directory:
            return

        src_path = event.src_path
        if isinstance(src_path, str):
            path = Path(src_path)
            if self.should_process(path):
                self.process_file(path)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events.

        Args:
            event: Filesystem event
        """
        if event.is_directory:
            return

        src_path = event.src_path
        if isinstance(src_path, str):
            path = Path(src_path)
            if self.should_process(path):
                self.process_file(path)

    def process_file(self, path: Path) -> None:
        """Process a single Fountain file.

        Args:
            path: Path to the Fountain file
        """
        str_path = str(path)
        self.processing.add(str_path)

        try:
            if self.callback:
                self.callback("processing", path)

            # Run the pull workflow for this specific file
            asyncio.run(self._pull_single_file(path))

            self.last_processed[str_path] = time.time()
            if self.callback:
                self.callback("completed", path)

        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            if self.callback:
                self.callback("error", path, str(e))
        finally:
            self.processing.discard(str_path)

    async def _pull_single_file(self, path: Path) -> None:
        """Run pull workflow for a single file.

        Args:
            path: Path to the Fountain file
        """
        # Ensure database exists
        db_ops = DatabaseOperations(self.settings)
        if not db_ops.check_database_exists():
            from scriptrag.api import DatabaseInitializer

            initializer = DatabaseInitializer()
            initializer.initialize_database(settings=self.settings)

        # Analyze the file
        analyze_cmd = AnalyzeCommand.from_config()
        await analyze_cmd.analyze(
            path=path.parent,
            recursive=False,
            force=self.force,
            dry_run=False,
        )

        # Index the file
        index_cmd = IndexCommand.from_config()
        await index_cmd.index(
            path=path.parent,
            recursive=False,
            force=self.force,
            dry_run=False,
            batch_size=self.batch_size,
        )


@app.command()
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
) -> None:
    """Watch for Fountain file changes and automatically pull them.

    This command monitors the filesystem for changes to Fountain files
    and automatically runs the pull workflow (analyze + index) when
    files are created or modified.

    Press Ctrl+C to stop watching.
    """
    try:
        # Load settings
        if config:
            settings = ScriptRAGSettings.from_multiple_sources(
                config_files=[config],
            )
        else:
            settings = get_settings()

        # Resolve watch path
        watch_path = path or Path.cwd()
        if not watch_path.exists():
            console.print(f"[red]Error: Path {watch_path} does not exist[/red]")
            raise typer.Exit(1)

        # Run initial pull if requested
        if initial_pull:
            console.print("[cyan]Running initial pull...[/cyan]")
            from scriptrag.cli.commands.pull import pull_command

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

        # Status tracking
        status_log = []

        def update_status(status: str, path: Path, error: str | None = None) -> None:
            """Update status display.

            Args:
                status: Status type (processing, completed, error)
                path: File path
                error: Error message if any
            """
            try:
                rel_path = path.relative_to(watch_path)
            except ValueError:
                rel_path = path

            timestamp = time.strftime("%H:%M:%S")

            if status == "processing":
                status_log.append(f"[{timestamp}] 🔄 Processing: {rel_path}")
            elif status == "completed":
                status_log.append(f"[{timestamp}] ✅ Updated: {rel_path}")
            elif status == "error":
                status_log.append(f"[{timestamp}] ❌ Error: {rel_path} - {error}")

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

        # Create event handler
        handler = FountainFileHandler(
            settings=settings,
            force=force,
            batch_size=batch_size,
            callback=update_status,
        )

        # Setup observer
        observer = Observer()
        observer.schedule(
            handler,
            str(watch_path),
            recursive=not no_recursive,
        )

        # Start watching
        observer.start()

        # Display initial status
        table = Table(title="File Watch Status", show_header=False)
        table.add_column("Status")
        table.add_row(f"👀 Watching: {watch_path}")
        table.add_row(f"📁 Recursive: {'Yes' if not no_recursive else 'No'}")
        table.add_row(f"🔄 Force mode: {'On' if force else 'Off'}")
        table.add_row("")
        table.add_row("[dim]Waiting for file changes...[/dim]")

        panel = Panel(
            table,
            title="[bold cyan]ScriptRAG Watch[/bold cyan]",
            border_style="cyan",
        )
        console.print(panel)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping file watch...[/yellow]")
            observer.stop()

        observer.join()
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
