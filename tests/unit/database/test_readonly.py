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

            # Should not raise exception
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            mock_conn.close.assert_called_once()

    def test_get_read_only_connection_none_connection(self, settings):
        """Test handling when connection is None."""
        db_path = settings.database_path
        db_path.touch()

        with patch("sqlite3.connect") as mock_connect:
            # Mock connect returning None
            mock_connect.return_value = None

            with get_read_only_connection(settings) as conn:
                assert conn is None

            # No close should be called on None

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
