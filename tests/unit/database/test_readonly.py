"""Tests for read-only database connection utilities."""

from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.readonly import get_read_only_connection


class TestGetReadOnlyConnection:
    """Test read-only database connection functionality."""

    @pytest.fixture
    def settings(self, tmp_path):
        """Create test settings."""
        db_path = tmp_path / "test.db"
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = db_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        return settings

    def test_get_read_only_connection_success(self, settings):
        """Test successful read-only connection creation."""
        # Create a dummy database file
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection was opened in read-only mode
            expected_uri = f"file:{db_path.resolve()}?mode=ro"
            mock_connect.assert_called_once_with(
                expected_uri, uri=True, timeout=30.0, check_same_thread=False
            )

            # Verify pragma settings were applied
            mock_conn.execute.assert_any_call("PRAGMA query_only = ON")
            mock_conn.execute.assert_any_call("PRAGMA cache_size = -2000")
            mock_conn.execute.assert_any_call("PRAGMA temp_store = MEMORY")

            # Verify row factory was set
            assert mock_conn.row_factory is not None

            # Verify connection was closed
            mock_conn.close.assert_called_once()

    def test_get_read_only_connection_path_traversal_protection(self, tmp_path):
        """Test path traversal protection."""
        # Create a legitimate base directory
        base_dir = tmp_path / "data"
        base_dir.mkdir()

        # Create settings with path that would traverse outside parent
        settings = MagicMock(spec=ScriptRAGSettings)
        # This creates a path that goes outside the expected parent directory
        traversal_path = base_dir / "../../../etc/passwd"
        settings.database_path = traversal_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        # The test expects a ValueError to be raised by the context manager
        with (
            pytest.raises(ValueError, match="Invalid database path detected"),
            get_read_only_connection(settings),
        ):
            pass

    def test_get_read_only_connection_exception_handling(self, settings):
        """Test exception handling during connection creation."""
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            # Mock connection that raises exception during setup
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.execute.side_effect = RuntimeError("Connection error")

            with (
                pytest.raises(RuntimeError, match="Connection error"),
                get_read_only_connection(settings),
            ):
                pass

            # Connection should still be closed on exception
            mock_conn.close.assert_called_once()

    def test_get_read_only_connection_no_exception_on_close_error(self, settings):
        """Test that exceptions during close are handled gracefully."""
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            # Connection closes with error, but should not propagate
            mock_conn.close.side_effect = RuntimeError("Close error")

            # Should not raise exception during context manager usage
            # The close error should be suppressed in the finally block
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify close was called (even though it raised an error)
            mock_conn.close.assert_called_once()

    def test_get_read_only_connection_none_connection(self, settings):
        """Test handling when connection is None."""
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            # Mock connect returning None
            mock_connect.return_value = None

            # This will fail because the code tries to call execute on None
            # The actual implementation doesn't handle None connections gracefully
            with (
                pytest.raises(AttributeError),
                get_read_only_connection(settings) as conn,
            ):
                assert conn is None

    def test_get_read_only_connection_exception_cleanup(self, settings):
        """Test exception handling in cleanup - line 34 coverage."""
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            # First call returns a connection, but then fails on pragma setup
            mock_connect.return_value = mock_conn
            mock_conn.execute.side_effect = RuntimeError("Pragma setup failed")

            # This should handle the exception and still try to clean up
            with (
                pytest.raises(RuntimeError, match="Pragma setup failed"),
                get_read_only_connection(settings),
            ):
                pass

            # Connection should have been closed in finally block
            mock_conn.close.assert_called_once()

    def test_get_read_only_connection_macos_temp_dirs_allowed(self):
        """Test that macOS temp directories in /private/var/folders/ are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        # Create settings with macOS temporary directory path
        settings = MagicMock(spec=ScriptRAGSettings)
        # Simulate a typical macOS temporary directory path
        macos_temp_path = Path(
            "/private/var/folders/y6/nj790rtn62lfktb1sh__79hc0000gn/T/pytest-of-runner/pytest-0/test_db_path/test.db"
        )
        settings.database_path = macos_temp_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # This should NOT raise a ValueError for macOS temp dirs
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection was opened successfully
            expected_uri = f"file:{macos_temp_path.resolve()}?mode=ro"
            mock_connect.assert_called_once_with(
                expected_uri, uri=True, timeout=30.0, check_same_thread=False
            )

    def test_get_read_only_connection_regular_var_dirs_blocked(self):
        """Test that regular /var/ directories (non-temp) are still blocked."""
        from pathlib import Path
        from unittest.mock import MagicMock

        # Create settings with regular /var directory path
        settings = MagicMock(spec=ScriptRAGSettings)
        var_path = Path("/var/lib/database/test.db")
        settings.database_path = var_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        # This should still raise a ValueError for non-temp /var directories
        with (
            pytest.raises(ValueError, match="Invalid database path detected"),
            get_read_only_connection(settings),
        ):
            pass
