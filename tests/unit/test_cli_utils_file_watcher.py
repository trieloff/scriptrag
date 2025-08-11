"""Unit tests for the file watcher utility."""

import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchdog.events import FileSystemEvent

from scriptrag.cli.utils.file_watcher import FountainFileHandler, StatusCallback
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = Path("/tmp/test.db")
    return settings


@pytest.fixture
def mock_callback():
    """Create mock callback."""
    return MagicMock(spec=StatusCallback)


@pytest.fixture
def handler(mock_settings, mock_callback):
    """Create a FountainFileHandler instance."""
    return FountainFileHandler(
        settings=mock_settings,
        force=False,
        batch_size=5,
        callback=mock_callback,
        max_queue_size=10,
        batch_timeout=1.0,
    )


class TestFountainFileHandler:
    """Test FountainFileHandler functionality."""

    def test_handler_initialization(self, handler, mock_settings, mock_callback):
        """Test handler initializes correctly."""
        assert handler.settings == mock_settings
        assert handler.force is False
        assert handler.batch_size == 5
        assert handler.callback == mock_callback
        assert handler.event_queue.maxsize == 10  # Check queue's maxsize instead
        assert handler.batch_timeout == 1.0
        assert handler.debounce_seconds == 2.0
        assert len(handler.processing) == 0
        assert len(handler.last_processed) == 0

    def test_should_process_valid_fountain_file(self, handler):
        """Test should_process returns True for valid Fountain files."""
        # Test .fountain extension
        path = Path("/test/script.fountain")
        assert handler.should_process(path) is True

        # Test .spmd extension
        path = Path("/test/script.spmd")
        assert handler.should_process(path) is True

    def test_should_process_invalid_file(self, handler):
        """Test should_process returns False for non-Fountain files."""
        # Test non-Fountain extension
        path = Path("/test/document.txt")
        assert handler.should_process(path) is False

        path = Path("/test/script.pdf")
        assert handler.should_process(path) is False

    def test_should_process_already_processing(self, handler):
        """Test should_process returns False for files being processed."""
        path = Path("/test/script.fountain")
        handler.processing.add(str(path))
        assert handler.should_process(path) is False

    def test_should_process_debounce(self, handler):
        """Test should_process respects debounce timing."""
        path = Path("/test/script.fountain")

        # First check should return True
        assert handler.should_process(path) is True

        # Mark as recently processed
        current_time = time.time()
        handler.last_processed[str(path)] = current_time

        # Immediate check should return False due to debounce
        assert handler.should_process(path) is False

        # Mock time to simulate debounce period passing
        with patch("scriptrag.cli.utils.file_watcher.time.time") as mock_time:
            mock_time.return_value = current_time + 3  # 3 seconds later
            assert handler.should_process(path) is True

    def test_on_modified_with_valid_file(self, handler):
        """Test on_modified handles valid file events."""
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = "/test/script.fountain"

        with patch.object(handler, "_queue_file") as mock_queue:
            handler.on_modified(event)
            mock_queue.assert_called_once_with(Path("/test/script.fountain"))

    def test_on_modified_ignores_directories(self, handler):
        """Test on_modified ignores directory events."""
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = True
        event.src_path = "/test/dir"

        with patch.object(handler, "_queue_file") as mock_queue:
            handler.on_modified(event)
            mock_queue.assert_not_called()

    def test_on_created_with_valid_file(self, handler):
        """Test on_created handles valid file events."""
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = "/test/new_script.fountain"

        with patch.object(handler, "_queue_file") as mock_queue:
            handler.on_created(event)
            mock_queue.assert_called_once_with(Path("/test/new_script.fountain"))

    def test_queue_file_adds_to_queue(self, handler):
        """Test _queue_file adds files to the event queue."""
        path = Path("/test/script.fountain")
        handler._queue_file(path)
        assert handler.event_queue.qsize() == 1
        assert handler.event_queue.get_nowait() == path

    def test_queue_file_handles_full_queue(self, handler):
        """Test _queue_file handles full queue gracefully."""
        # Fill the queue
        for i in range(handler.event_queue.maxsize):
            handler.event_queue.put(Path(f"/test/script{i}.fountain"))

        # Try to add one more
        with patch("scriptrag.cli.utils.file_watcher.logger") as mock_logger:
            path = Path("/test/overflow.fountain")
            handler._queue_file(path)
            mock_logger.warning.assert_called_once()

    def test_start_stop_processing(self, handler):
        """Test starting and stopping the processor thread."""
        # Start processing
        handler.start_processing()
        assert handler.processor_thread is not None
        assert handler.processor_thread.is_alive()

        # Stop processing
        handler.stop_processing(timeout=2.0)
        assert handler.shutdown_event.is_set()

    def test_process_batch_deduplicates_paths(self, handler):
        """Test _process_batch deduplicates paths."""
        paths = [
            Path("/test/script1.fountain"),
            Path("/test/script2.fountain"),
            Path("/test/script1.fountain"),  # Duplicate
        ]

        with patch.object(handler, "_process_file_sync") as mock_process:
            handler._process_batch(paths)
            # Should only process 2 unique files
            assert mock_process.call_count == 2

    def test_process_file_sync_success(self, handler, mock_callback):
        """Test _process_file_sync handles successful processing."""
        path = Path("/test/script.fountain")

        with patch.object(handler, "_pull_single_file") as mock_pull:
            # Create a coroutine that returns None
            async def async_noop():
                return None

            mock_pull.return_value = async_noop()

            handler._process_file_sync(path)

            # Verify callbacks
            assert mock_callback.call_count == 2
            mock_callback.assert_any_call("processing", path)
            mock_callback.assert_any_call("completed", path)

    def test_process_file_sync_error(self, handler, mock_callback):
        """Test _process_file_sync handles errors."""
        path = Path("/test/script.fountain")
        error_msg = "Test error"

        with patch.object(handler, "_pull_single_file") as mock_pull:
            mock_pull.side_effect = Exception(error_msg)

            handler._process_file_sync(path)

            # Verify error callback
            mock_callback.assert_any_call("error", path, error_msg)

    @pytest.mark.asyncio
    async def test_pull_single_file_with_existing_db(self, handler):
        """Test _pull_single_file with existing database."""
        path = Path("/test/script.fountain")

        with (
            patch("scriptrag.cli.utils.file_watcher.DatabaseOperations") as mock_db_ops,
            patch("scriptrag.cli.utils.file_watcher.AnalyzeCommand") as mock_analyze,
            patch("scriptrag.cli.utils.file_watcher.IndexCommand") as mock_index,
        ):
            # Setup mocks
            db_ops = MagicMock()
            db_ops.check_database_exists.return_value = True
            mock_db_ops.return_value = db_ops

            analyze_cmd = MagicMock()
            analyze_cmd.analyze = AsyncMock()
            mock_analyze.from_config.return_value = analyze_cmd

            index_cmd = MagicMock()
            index_cmd.index = AsyncMock()
            mock_index.from_config.return_value = index_cmd

            # Run
            await handler._pull_single_file(path)

            # Verify database was not initialized
            db_ops.check_database_exists.assert_called_once()

            # Verify analyze and index were called with the specific file
            analyze_cmd.analyze.assert_called_once_with(
                path=path,
                recursive=False,
                force=handler.force,
                dry_run=False,
            )
            index_cmd.index.assert_called_once_with(
                path=path,
                recursive=False,
                dry_run=False,
                batch_size=1,
            )

    @pytest.mark.asyncio
    async def test_pull_single_file_initializes_db(self, handler):
        """Test _pull_single_file initializes database if missing."""
        path = Path("/test/script.fountain")

        with (
            patch("scriptrag.cli.utils.file_watcher.DatabaseOperations") as mock_db_ops,
            patch("scriptrag.api.DatabaseInitializer") as mock_init,
            patch("scriptrag.cli.utils.file_watcher.AnalyzeCommand") as mock_analyze,
            patch("scriptrag.cli.utils.file_watcher.IndexCommand") as mock_index,
        ):
            # Setup mocks
            db_ops = MagicMock()
            db_ops.check_database_exists.return_value = False
            mock_db_ops.return_value = db_ops

            initializer = MagicMock()
            mock_init.return_value = initializer

            analyze_cmd = MagicMock()
            analyze_cmd.analyze = AsyncMock()
            mock_analyze.from_config.return_value = analyze_cmd

            index_cmd = MagicMock()
            index_cmd.index = AsyncMock()
            mock_index.from_config.return_value = index_cmd

            # Run
            await handler._pull_single_file(path)

            # Verify database was initialized
            initializer.initialize_database.assert_called_once()

    def test_process_events_batch_processing(self, handler):
        """Test _process_events processes batches correctly."""
        # Add files to queue
        paths = [Path(f"/test/script{i}.fountain") for i in range(3)]
        for path in paths:
            handler.event_queue.put(path)

        with patch.object(handler, "_process_batch") as mock_process:
            # Set shutdown after a short time
            def shutdown_after_delay():
                time.sleep(0.5)
                handler.shutdown_event.set()

            shutdown_thread = threading.Thread(target=shutdown_after_delay)
            shutdown_thread.start()

            # Run process events
            handler._process_events()

            # Verify batch was processed
            mock_process.assert_called()
            shutdown_thread.join()

    def test_process_events_timeout_processing(self, handler):
        """Test _process_events processes on timeout."""
        # Add a single file
        path = Path("/test/script.fountain")
        handler.event_queue.put(path)

        # Set very short batch timeout for testing
        handler.batch_timeout = 0.1

        with patch.object(handler, "_process_batch") as mock_process:
            # Set shutdown after timeout
            def shutdown_after_delay():
                time.sleep(0.3)
                handler.shutdown_event.set()

            shutdown_thread = threading.Thread(target=shutdown_after_delay)
            shutdown_thread.start()

            # Run process events
            handler._process_events()

            # Verify batch was processed due to timeout
            mock_process.assert_called()
            shutdown_thread.join()
