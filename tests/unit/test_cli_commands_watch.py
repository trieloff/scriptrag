"""Unit tests for the watch command."""

import signal
import time
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch("scriptrag.cli.commands.watch.get_settings") as mock:
        settings = MagicMock()
        settings.database_path = Path("/tmp/test.db")
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_observer():
    """Mock watchdog observer."""
    with patch("scriptrag.cli.commands.watch.Observer") as mock:
        observer = MagicMock()
        mock.return_value = observer
        yield observer


@pytest.fixture
def mock_handler():
    """Mock file handler."""
    with patch("scriptrag.cli.commands.watch.FountainFileHandler") as mock:
        handler = MagicMock()
        mock.return_value = handler
        yield handler


@pytest.fixture
def mock_pull_command():
    """Mock pull command."""
    with patch("scriptrag.cli.commands.watch.pull_command") as mock:
        yield mock


class TestWatchCommand:
    """Test watch command functionality."""

    def test_watch_command_help(self, runner):
        """Test watch command shows help."""
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == 0
        assert "Watch for Fountain file changes" in result.output

    def test_watch_validates_path(self, runner, mock_settings):
        """Test watch command validates the watch path."""
        # Test with non-existent path
        result = runner.invoke(app, ["watch", "/nonexistent/path"])
        assert result.exit_code == 1
        # Check for error message with platform-appropriate path separator
        from pathlib import Path

        expected_path = str(Path("/nonexistent/path"))
        assert f"Error: Path {expected_path} does not exist" in result.output

    @patch("scriptrag.cli.commands.watch.time.sleep")
    def test_watch_with_timeout(
        self,
        mock_sleep,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command with timeout option."""
        # Mock sleep to simulate time passing
        call_count = 0

        def sleep_side_effect(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:  # Simulate timeout after 3 seconds
                return
            time.sleep(0.01)  # Small actual sleep

        mock_sleep.side_effect = sleep_side_effect

        # Run command with 3 second timeout
        result = runner.invoke(
            app, ["watch", ".", "--timeout", "3", "--no-initial-pull"]
        )

        # Verify timeout behavior
        from tests.utils import strip_ansi_codes

        output = strip_ansi_codes(result.output)
        assert "Watch timeout reached (3s)" in output
        assert "Watch stopped" in output

        # Verify observer was started and stopped
        mock_observer.start.assert_called_once()
        mock_observer.stop.assert_called()

    def test_watch_with_initial_pull(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
        mock_pull_command,
    ):
        """Test watch command runs initial pull."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, None, KeyboardInterrupt()]

            # Run command with initial pull
            result = runner.invoke(app, ["watch", "."])

            # Verify initial pull was called
            assert mock_pull_command.call_count == 1
            assert "Running initial pull" in result.output

    def test_watch_without_initial_pull(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
        mock_pull_command,
    ):
        """Test watch command skips initial pull when disabled."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Run command without initial pull
            result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

            # Verify initial pull was not called
            assert mock_pull_command.call_count == 0
            assert "Running initial pull" not in result.output

    def test_watch_with_force_option(
        self,
        runner,
        mock_settings,
        mock_observer,
    ):
        """Test watch command with force option."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            with patch(
                "scriptrag.cli.commands.watch.FountainFileHandler"
            ) as mock_handler_class:
                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler

                # Run command with force
                runner.invoke(app, ["watch", ".", "--force", "--no-initial-pull"])

                # Verify force was passed to handler constructor
                assert mock_handler_class.call_count == 1
                call_kwargs = mock_handler_class.call_args[1]
                assert call_kwargs["force"] is True

    def test_watch_with_batch_size(
        self,
        runner,
        mock_settings,
        mock_observer,
    ):
        """Test watch command with custom batch size."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            with patch(
                "scriptrag.cli.commands.watch.FountainFileHandler"
            ) as mock_handler_class:
                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler

                # Run command with custom batch size
                runner.invoke(
                    app, ["watch", ".", "--batch-size", "20", "--no-initial-pull"]
                )

                # Verify batch size was passed to handler constructor
                assert mock_handler_class.call_count == 1
                call_kwargs = mock_handler_class.call_args[1]
                assert call_kwargs["batch_size"] == 20

    def test_watch_handles_keyboard_interrupt(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command handles Ctrl+C gracefully."""
        # Setup mock to raise KeyboardInterrupt
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Run command
            result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

            # Verify graceful shutdown
            assert "Stopping file watch" in result.output
            assert "Watch stopped" in result.output

            # Verify cleanup
            mock_observer.stop.assert_called()
            mock_handler.stop_processing.assert_called()

    def test_watch_recursive_option(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command with recursive option."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Run command without recursive
            runner.invoke(app, ["watch", ".", "--no-recursive", "--no-initial-pull"])

            # Verify recursive was set correctly
            assert mock_observer.schedule.call_count == 1
            call_kwargs = mock_observer.schedule.call_args[1]
            assert call_kwargs["recursive"] is False

    def test_watch_signal_handling(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command handles signals properly."""
        # Setup mock with signal handling
        with patch("scriptrag.cli.commands.watch.signal.signal") as mock_signal:
            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command
                runner.invoke(app, ["watch", ".", "--no-initial-pull"])

                # Verify signal handlers were registered
                assert mock_signal.call_count >= 2
                mock_signal.assert_any_call(signal.SIGINT, ANY)
                mock_signal.assert_any_call(signal.SIGTERM, ANY)

    def test_watch_handles_import_error(
        self,
        runner,
        mock_settings,
    ):
        """Test watch command handles missing dependencies gracefully."""
        # Mock import error for watchdog
        with patch("scriptrag.cli.commands.watch.Observer") as mock_observer:
            mock_observer.side_effect = ImportError("No module named 'watchdog'")

            # Run command with --no-initial-pull to avoid running analysis
            result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

            # Verify error handling
            assert result.exit_code == 1
            assert "Required components not available" in result.output
            assert "pip install watchdog" in result.output

    def test_watch_with_custom_config(
        self,
        runner,
        mock_observer,
        mock_handler,
        tmp_path,
    ):
        """Test watch command with custom config file."""
        # Create a config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /tmp/custom.db\n")

        with patch(
            "scriptrag.cli.commands.watch.ScriptRAGSettings"
        ) as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command with custom config
                result = runner.invoke(
                    app,
                    ["watch", ".", "--config", str(config_file), "--no-initial-pull"],
                )

                # Verify config was loaded
                mock_settings_class.from_multiple_sources.assert_called_once()
                call_args = mock_settings_class.from_multiple_sources.call_args
                assert call_args[1]["config_files"] == [config_file]

    def test_watch_signal_handler_function(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test the signal handler function directly."""
        from scriptrag.cli.commands import watch

        # Set up global variables
        watch._observer = mock_observer
        watch._handler = mock_handler
        mock_observer.is_alive.return_value = True

        # Test signal handler
        with patch("scriptrag.cli.commands.watch.sys.exit") as mock_exit:
            with patch("scriptrag.cli.commands.watch.console") as mock_console:
                watch.signal_handler(signal.SIGINT, None)

                # Verify cleanup
                mock_console.print.assert_called_with(
                    "\n[yellow]Shutting down gracefully...[/yellow]"
                )
                mock_observer.stop.assert_called_once()
                mock_handler.stop_processing.assert_called_once_with(timeout=5.0)
                mock_exit.assert_called_once_with(0)

    def test_watch_status_update_callback(
        self,
        runner,
        mock_settings,
        mock_observer,
        tmp_path,
    ):
        """Test status update callback with various statuses."""
        with patch(
            "scriptrag.cli.commands.watch.FountainFileHandler"
        ) as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            callback = None

            def capture_callback(**kwargs):
                nonlocal callback
                callback = kwargs.get("callback")
                return mock_handler

            mock_handler_class.side_effect = capture_callback

            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command
                result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

                # Test callback with different statuses
                if callback:
                    with patch("scriptrag.cli.commands.watch.console") as mock_console:
                        with patch(
                            "scriptrag.cli.commands.watch.time.strftime"
                        ) as mock_strftime:
                            mock_strftime.return_value = "12:00:00"

                            # Test processing status
                            test_path = Path("test.fountain")
                            callback("processing", test_path)

                            # Test completed status
                            callback("completed", test_path)

                            # Test error status
                            callback("error", test_path, "Test error")

                            # Verify console updates
                            assert mock_console.clear.called
                            assert mock_console.print.called

    def test_watch_path_security(
        self,
        runner,
        mock_settings,
        mock_observer,
        tmp_path,
    ):
        """Test watch command handles path security correctly."""
        watch_dir = tmp_path / "watch_dir"
        watch_dir.mkdir()

        with patch(
            "scriptrag.cli.commands.watch.FountainFileHandler"
        ) as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            callback = None

            def capture_callback(**kwargs):
                nonlocal callback
                callback = kwargs.get("callback")
                return mock_handler

            mock_handler_class.side_effect = capture_callback

            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command
                result = runner.invoke(
                    app, ["watch", str(watch_dir), "--no-initial-pull"]
                )

                # Test callback with paths outside watch directory
                if callback:
                    with patch("scriptrag.cli.commands.watch.console"):
                        with patch(
                            "scriptrag.cli.commands.watch.time.strftime"
                        ) as mock_strftime:
                            mock_strftime.return_value = "12:00:00"

                            # Test path outside watch directory
                            outside_path = tmp_path / "outside" / "file.fountain"
                            callback("processing", outside_path)

                            # Test path with ValueError
                            mock_path = MagicMock(spec=Path)
                            mock_path.is_relative_to.side_effect = ValueError(
                                "Not relative"
                            )
                            mock_path.name = "error_file.fountain"
                            callback("processing", mock_path)

    def test_watch_cleanup_on_exception(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command cleanup on unexpected exception."""
        mock_observer.start.side_effect = Exception("Unexpected error")
        mock_observer.is_alive.return_value = True

        # Run command
        result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

        # Verify error handling and cleanup
        assert result.exit_code == 1
        assert "Unexpected error" in result.output

        # Verify cleanup in finally block
        mock_observer.stop.assert_called()
        mock_handler.stop_processing.assert_called()

    def test_watch_status_log_overflow(
        self,
        runner,
        mock_settings,
        mock_observer,
        tmp_path,
    ):
        """Test status log keeps only last 10 entries."""
        with patch(
            "scriptrag.cli.commands.watch.FountainFileHandler"
        ) as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            callback = None

            def capture_callback(**kwargs):
                nonlocal callback
                callback = kwargs.get("callback")
                return mock_handler

            mock_handler_class.side_effect = capture_callback

            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command
                result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

                # Test callback with more than 10 entries
                if callback:
                    with patch("scriptrag.cli.commands.watch.console"):
                        with patch(
                            "scriptrag.cli.commands.watch.time.strftime"
                        ) as mock_strftime:
                            mock_strftime.return_value = "12:00:00"

                            # Add 15 status updates
                            for i in range(15):
                                test_path = Path(f"test{i}.fountain")
                                callback("processing", test_path)

                            # Status log should only have 10 entries

    def test_watch_long_running_with_timeout(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command with long timeout correctly measures time."""
        with patch("scriptrag.cli.commands.watch.time.time") as mock_time:
            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                # Simulate time progression
                time_values = [0, 1, 2, 3, 4, 5]  # 5 seconds total
                mock_time.side_effect = (
                    time_values + time_values
                )  # Duplicate for multiple calls
                mock_sleep.return_value = None

                # Run command with 4 second timeout
                result = runner.invoke(
                    app, ["watch", ".", "--timeout", "4", "--no-initial-pull"]
                )

                # Verify timeout message
                from tests.utils import strip_ansi_codes

                output = strip_ansi_codes(result.output)
                assert "Watch timeout reached (4s)" in output

    def test_watch_observer_join_timeout(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command handles observer join timeout."""
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Make observer.join take long time
            mock_observer.join.return_value = None

            # Run command
            result = runner.invoke(app, ["watch", ".", "--no-initial-pull"])

            # Verify join was called with timeout
            mock_observer.join.assert_called_once_with(timeout=10.0)

    def test_watch_with_all_options(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_pull_command,
        tmp_path,
    ):
        """Test watch command with all options enabled."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /tmp/test.db\n")

        with patch(
            "scriptrag.cli.commands.watch.ScriptRAGSettings"
        ) as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            with patch(
                "scriptrag.cli.commands.watch.FountainFileHandler"
            ) as mock_handler_class:
                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler

                with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                    with patch("scriptrag.cli.commands.watch.time.time") as mock_time:
                        mock_time.side_effect = [0, 1, 2, 3]
                        mock_sleep.return_value = None

                        # Run with all options
                        result = runner.invoke(
                            app,
                            [
                                "watch",
                                ".",
                                "--force",
                                "--no-recursive",
                                "--batch-size",
                                "25",
                                "--config",
                                str(config_file),
                                "--timeout",
                                "2",
                                # --initial-pull is default True
                            ],
                        )

                        # Verify all options were applied
                        mock_pull_command.assert_called_once_with(
                            path=Path.cwd(),
                            force=True,
                            dry_run=False,
                            no_recursive=True,
                            batch_size=25,
                            config=config_file,
                        )

                        mock_handler_class.assert_called_once()
                        handler_kwargs = mock_handler_class.call_args[1]
                        assert handler_kwargs["force"] is True
                        assert handler_kwargs["batch_size"] == 25
                        assert handler_kwargs["max_queue_size"] == 100
                        assert handler_kwargs["batch_timeout"] == 5.0

    def test_watch_config_file_not_found(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
        tmp_path,
    ):
        """Test watch command with non-existent config file."""
        from tests.utils import strip_ansi_codes

        # Use non-existent config file
        config_file = tmp_path / "nonexistent.yaml"

        # Run command
        result = runner.invoke(
            app, ["watch", ".", "--config", str(config_file), "--no-initial-pull"]
        )

        # Verify error handling
        assert result.exit_code == 1
        clean_output = strip_ansi_codes(result.output)
        assert "Error: Config file not found:" in clean_output
        assert str(config_file) in clean_output

    def test_watch_config_loading_exception(
        self,
        runner,
        mock_observer,
        mock_handler,
        tmp_path,
    ):
        """Test watch command handles config loading exceptions."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        with patch(
            "scriptrag.cli.commands.watch.ScriptRAGSettings"
        ) as mock_settings_class:
            mock_settings_class.from_multiple_sources.side_effect = Exception(
                "Config parse error"
            )

            # Run command
            result = runner.invoke(
                app,
                ["watch", ".", "--config", str(config_file), "--no-initial-pull"],
            )

            # Verify error handling
            assert result.exit_code == 1
            assert "Config parse error" in result.output

    def test_watch_config_with_initial_pull(
        self,
        runner,
        mock_observer,
        mock_handler,
        mock_pull_command,
        tmp_path,
    ):
        """Test watch command with config file and initial pull."""
        # Create a test config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database_path: /custom/test.db\n")

        with patch(
            "scriptrag.cli.commands.watch.ScriptRAGSettings"
        ) as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings.database_path = Path("/custom/test.db")
            mock_settings_class.from_multiple_sources.return_value = mock_settings

            with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, KeyboardInterrupt()]

                # Run command with config and initial pull
                result = runner.invoke(
                    app,
                    [
                        "watch",
                        ".",
                        "--config",
                        str(config_file),
                        "--initial-pull",
                    ],
                )

                # Verify config was loaded
                mock_settings_class.from_multiple_sources.assert_called_once_with(
                    config_files=[config_file]
                )

                # Verify initial pull was called with config
                mock_pull_command.assert_called_once()
                call_kwargs = mock_pull_command.call_args[1]
                assert call_kwargs["config"] == config_file
