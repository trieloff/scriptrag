"""File watching utilities for ScriptRAG CLI."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from pathlib import Path
from typing import Protocol

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


class StatusCallback(Protocol):
    """Protocol for status update callbacks."""

    def __call__(self, status: str, path: Path, error: str | None = None) -> None:
        """Update status callback.

        Args:
            status: Status type (processing, completed, error)
            path: File path being processed
            error: Optional error message
        """
        ...


class FountainFileHandler(FileSystemEventHandler):
    """Handler for Fountain file changes with async processing support."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        force: bool = False,
        batch_size: int = 10,
        callback: StatusCallback | None = None,
        max_queue_size: int = 100,
        batch_timeout: float = 5.0,
    ) -> None:
        """Initialize the handler.

        Args:
            settings: ScriptRAG settings
            force: Force re-processing (only affects analyze, not index)
            batch_size: Batch size for indexing
            callback: Callback for status updates
            max_queue_size: Maximum queue size for pending events
            batch_timeout: Timeout for batch processing in seconds
        """
        self.settings = settings
        self.force = force
        self.batch_size = batch_size
        self.callback = callback
        self.processing: set[str] = set()
        self.last_processed: dict[str, float] = {}
        self.debounce_seconds = 2.0

        # Event queue for async processing
        self.event_queue: queue.Queue[Path] = queue.Queue(maxsize=max_queue_size)
        self.batch_timeout = batch_timeout
        self.shutdown_event = threading.Event()
        self.processor_thread: threading.Thread | None = None

    def start_processing(self) -> None:
        """Start the async event processor thread."""
        if self.processor_thread is None or not self.processor_thread.is_alive():
            self.shutdown_event.clear()
            self.processor_thread = threading.Thread(
                target=self._process_events, daemon=True
            )
            self.processor_thread.start()

    def stop_processing(self, timeout: float = 10.0) -> None:
        """Stop the event processor thread gracefully.

        Args:
            timeout: Maximum time to wait for thread shutdown
        """
        self.shutdown_event.set()
        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=timeout)

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
                self._queue_file(path)

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
                self._queue_file(path)

    def _queue_file(self, path: Path) -> None:
        """Queue a file for processing.

        Args:
            path: Path to queue
        """
        try:
            self.event_queue.put_nowait(path)
        except queue.Full:
            logger.warning("Event queue is full, dropping event", path=str(path))

    def _process_events(self) -> None:
        """Process events from the queue in batches."""
        batch: list[Path] = []
        last_batch_time = time.time()

        while not self.shutdown_event.is_set():
            try:
                # Try to get an event with timeout
                path = self.event_queue.get(timeout=0.5)
                batch.append(path)

                # Process batch if it's full or timeout reached
                if batch and (
                    len(batch) >= self.batch_size
                    or time.time() - last_batch_time >= self.batch_timeout
                ):
                    self._process_batch(batch)
                    batch = []
                    last_batch_time = time.time()

            except queue.Empty:
                # Process any remaining batch on timeout
                if batch and time.time() - last_batch_time >= self.batch_timeout:
                    self._process_batch(batch)
                    batch = []
                    last_batch_time = time.time()

        # Process any remaining items on shutdown
        if batch:
            self._process_batch(batch)

    def _process_batch(self, paths: list[Path]) -> None:
        """Process a batch of files.

        Args:
            paths: List of paths to process
        """
        # Deduplicate paths
        unique_paths = list(set(paths))

        for path in unique_paths:
            str_path = str(path)
            if str_path not in self.processing:
                self.processing.add(str_path)
                try:
                    self._process_file_sync(path)
                finally:
                    self.processing.discard(str_path)
                    self.last_processed[str_path] = time.time()

    def _process_file_sync(self, path: Path) -> None:
        """Process a single file synchronously.

        Args:
            path: Path to the Fountain file
        """
        try:
            if self.callback:
                self.callback("processing", path)

            # Run the pull workflow using asyncio.run() for proper event loop management
            # This ensures thread safety and proper cleanup
            asyncio.run(self._pull_single_file(path))

            if self.callback:
                self.callback("completed", path)

        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            if self.callback:
                self.callback("error", path, str(e))

    async def _pull_single_file(self, path: Path) -> None:
        """Run pull workflow for a single file.

        Args:
            path: Path to the specific Fountain file
        """
        # Ensure database exists
        db_ops = DatabaseOperations(self.settings)
        if not db_ops.check_database_exists():
            from scriptrag.api import DatabaseInitializer

            initializer = DatabaseInitializer()
            initializer.initialize_database(settings=self.settings)

        # Process the specific file directly
        analyze_cmd = AnalyzeCommand.from_config()
        await analyze_cmd.analyze(
            path=path,  # Process specific file
            recursive=False,
            force=self.force,
            dry_run=False,
        )

        # Index the specific file
        index_cmd = IndexCommand.from_config()
        await index_cmd.index(
            path=path,  # Process specific file
            recursive=False,
            dry_run=False,
            batch_size=1,  # Single file
        )
