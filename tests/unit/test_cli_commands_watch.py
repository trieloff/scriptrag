"""Unit tests for the watch command."""

import signal
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        assert "Error: Path /nonexistent/path does not exist" in result.output

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
        assert "Watch timeout reached (3s)" in result.output
        assert "Watch stopped" in result.output

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
            mock_pull_command.assert_called_once()
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
            mock_pull_command.assert_not_called()
            assert "Running initial pull" not in result.output

    def test_watch_with_force_option(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command with force option."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Run command with force
            runner.invoke(app, ["watch", ".", "--force", "--no-initial-pull"])

            # Verify force was passed to handler
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args[1]
            assert call_kwargs["force"] is True

    def test_watch_with_batch_size(
        self,
        runner,
        mock_settings,
        mock_observer,
        mock_handler,
    ):
        """Test watch command with custom batch size."""
        # Setup mock with timeout
        with patch("scriptrag.cli.commands.watch.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            # Run command with custom batch size
            runner.invoke(
                app, ["watch", ".", "--batch-size", "20", "--no-initial-pull"]
            )

            # Verify batch size was passed to handler
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args[1]
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
            mock_observer.schedule.assert_called_once()
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
                mock_signal.assert_any_call(signal.SIGINT, pytest.Any())
                mock_signal.assert_any_call(signal.SIGTERM, pytest.Any())

    def test_watch_handles_import_error(
        self,
        runner,
        mock_settings,
    ):
        """Test watch command handles missing dependencies gracefully."""
        # Mock import error for watchdog
        with patch("scriptrag.cli.commands.watch.Observer") as mock_observer:
            mock_observer.side_effect = ImportError("No module named 'watchdog'")

            # Run command
            result = runner.invoke(app, ["watch", "."])

            # Verify error handling
            assert result.exit_code == 1
            assert "Required components not available" in result.output
            assert "pip install watchdog" in result.output
