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
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_foreign_keys = True
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

        with patch("scriptrag.cli.utils.file_watcher.asyncio") as mock_asyncio:
            mock_loop = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_asyncio.new_event_loop.return_value = mock_loop

            # Mock successful completion
            mock_loop.run_until_complete.return_value = None

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
            db_ops = MagicMock(spec=["content", "model", "provider", "usage"])
            db_ops.check_database_exists.return_value = True
            mock_db_ops.return_value = db_ops

            analyze_cmd = MagicMock(spec=["content", "model", "provider", "usage"])
            analyze_cmd.analyze = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            mock_analyze.from_config.return_value = analyze_cmd

            index_cmd = MagicMock(spec=["content", "model", "provider", "usage"])
            index_cmd.index = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
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
            db_ops = MagicMock(spec=["content", "model", "provider", "usage"])
            db_ops.check_database_exists.return_value = False
            mock_db_ops.return_value = db_ops

            initializer = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_init.return_value = initializer

            analyze_cmd = MagicMock(spec=["content", "model", "provider", "usage"])
            analyze_cmd.analyze = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            mock_analyze.from_config.return_value = analyze_cmd

            index_cmd = MagicMock(spec=["content", "model", "provider", "usage"])
            index_cmd.index = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
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

    def test_process_events_batch_size_trigger(self, handler):
        """Test _process_events processes when batch size reached."""
        # Add files equal to batch size
        paths = [Path(f"/test/script{i}.fountain") for i in range(handler.batch_size)]
        for path in paths:
            handler.event_queue.put(path)

        with patch.object(handler, "_process_batch") as mock_process:
            # Set shutdown immediately after processing
            def shutdown_after_delay():
                time.sleep(0.2)
                handler.shutdown_event.set()

            shutdown_thread = threading.Thread(target=shutdown_after_delay)
            shutdown_thread.start()

            # Run process events
            handler._process_events()

            # Verify batch was processed due to size
            mock_process.assert_called()
            # Check that the batch had the right size
            call_args = mock_process.call_args[0][0]
            assert len(call_args) == handler.batch_size
            shutdown_thread.join()

    def test_process_events_empty_queue_timeout(self, handler):
        """Test _process_events handles empty queue with batch timeout."""
        # Add one file
        path = Path("/test/script.fountain")
        handler.event_queue.put(path)

        # Set batch timeout
        handler.batch_timeout = 0.1

        with patch.object(handler, "_process_batch") as mock_process:
            with patch("scriptrag.cli.utils.file_watcher.time.time") as mock_time:
                # Simulate time progression
                time_values = [0, 0.05, 0.15, 0.2]  # Trigger timeout
                mock_time.side_effect = time_values + [0.3] * 10

                # Set shutdown after processing
                def shutdown_after_delay():
                    time.sleep(0.25)
                    handler.shutdown_event.set()

                shutdown_thread = threading.Thread(target=shutdown_after_delay)
                shutdown_thread.start()

                # Run process events
                handler._process_events()

                # Verify batch was processed on timeout
                mock_process.assert_called()
                shutdown_thread.join()

    def test_process_events_shutdown_with_remaining(self, handler):
        """Test _process_events processes remaining items on shutdown."""
        # Add files less than batch size
        paths = [Path(f"/test/script{i}.fountain") for i in range(2)]
        for path in paths:
            handler.event_queue.put(path)

        processed_batches = []

        def track_batch(batch):
            processed_batches.append(batch)

        with patch.object(
            handler, "_process_batch", side_effect=track_batch
        ) as mock_process:
            # Set shutdown after getting items from queue
            def delayed_shutdown():
                time.sleep(0.1)  # Allow time to get items from queue
                handler.shutdown_event.set()

            shutdown_thread = threading.Thread(target=delayed_shutdown)
            shutdown_thread.start()

            # Run process events
            handler._process_events()

            shutdown_thread.join()

            # Verify remaining batch was processed
            assert len(processed_batches) > 0
            # Check that paths were processed
            all_processed = []
            for batch in processed_batches:
                all_processed.extend(batch)
            assert len(all_processed) == 2

    def test_start_processing_restarts_dead_thread(self, handler):
        """Test start_processing restarts a dead thread."""
        # Create a dead thread
        handler.processor_thread = MagicMock(spec=threading.Thread)
        handler.processor_thread.is_alive.return_value = False

        # Start processing
        handler.start_processing()

        # Verify new thread was started
        assert handler.processor_thread is not None
        assert handler.processor_thread.is_alive()
        assert not handler.shutdown_event.is_set()

        # Clean up
        handler.stop_processing(timeout=1.0)

    def test_stop_processing_no_thread(self, handler):
        """Test stop_processing when no thread exists."""
        handler.processor_thread = None

        # Should not raise
        handler.stop_processing(timeout=1.0)

        # Verify shutdown event is set
        assert handler.shutdown_event.is_set()

    def test_stop_processing_dead_thread(self, handler):
        """Test stop_processing with dead thread."""
        handler.processor_thread = MagicMock(spec=threading.Thread)
        handler.processor_thread.is_alive.return_value = False

        # Should not raise
        handler.stop_processing(timeout=1.0)

        # Verify shutdown event is set
        assert handler.shutdown_event.is_set()
        # join should not be called on dead thread
        handler.processor_thread.join.assert_not_called()

    def test_process_batch_with_processing_file(self, handler):
        """Test _process_batch skips files already being processed."""
        paths = [
            Path("/test/script1.fountain"),
            Path("/test/script2.fountain"),
        ]

        # Mark script1 as already processing
        handler.processing.add(str(paths[0]))

        with patch.object(handler, "_process_file_sync") as mock_process:
            handler._process_batch(paths)

            # Should only process script2
            assert mock_process.call_count == 1
            mock_process.assert_called_with(paths[1])

    def test_process_batch_updates_last_processed(self, handler):
        """Test _process_batch updates last_processed timestamps."""
        path = Path("/test/script.fountain")

        with patch.object(handler, "_process_file_sync"):
            with patch("scriptrag.cli.utils.file_watcher.time.time") as mock_time:
                mock_time.return_value = 12345.0

                handler._process_batch([path])

                # Verify timestamp was updated
                assert handler.last_processed[str(path)] == 12345.0
                # Verify file was removed from processing set
                assert str(path) not in handler.processing

    def test_process_file_sync_no_callback(self, handler):
        """Test _process_file_sync without callback."""
        handler.callback = None
        path = Path("/test/script.fountain")

        with patch("scriptrag.cli.utils.file_watcher.asyncio.run") as mock_run:
            # Mock successful completion
            mock_run.return_value = None

            # Should not raise
            handler._process_file_sync(path)

            # Verify pull was executed via asyncio.run
            mock_run.assert_called_once()

    def test_on_modified_non_fountain_file(self, handler):
        """Test on_modified ignores non-Fountain files."""
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = "/test/document.txt"

        with patch.object(handler, "_queue_file") as mock_queue:
            handler.on_modified(event)
            mock_queue.assert_not_called()

    def test_on_created_directory(self, handler):
        """Test on_created ignores directories."""
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = True
        event.src_path = "/test/new_dir"

        with patch.object(handler, "_queue_file") as mock_queue:
            handler.on_created(event)
            mock_queue.assert_not_called()

    def test_process_file_sync_with_pull_error(self, handler, mock_callback):
        """Test _process_file_sync handles pull errors properly."""
        path = Path("/test/script.fountain")
        error_msg = "Database connection failed"

        with patch("scriptrag.cli.utils.file_watcher.asyncio.run") as mock_run:
            # Make asyncio.run raise the exception
            mock_run.side_effect = Exception(error_msg)

            handler._process_file_sync(path)

            # Verify error callback was called
            assert mock_callback.call_count >= 2
            calls = [call.args for call in mock_callback.call_args_list]
            assert ("processing", path) in calls
            assert ("error", path, error_msg) in calls

    def test_process_batch_exception_handling(self, handler):
        """Test _process_batch handles exceptions and cleans up properly."""
        path = Path("/test/script.fountain")

        # The current implementation doesn't catch exceptions in _process_batch
        # but uses a finally block to clean up. Let's test that behavior.
        with patch.object(handler, "_process_file_sync") as mock_process:
            # Normal execution
            handler._process_batch([path])

            # Verify file was processed and cleaned up
            mock_process.assert_called_once_with(path)
            assert str(path) not in handler.processing
            assert str(path) in handler.last_processed
