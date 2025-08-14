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

    def test_root_repo_path_allowed(self):
        """Test that /root/repo/ paths are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        settings = MagicMock(spec=ScriptRAGSettings)
        # Valid /root/repo path
        repo_path = Path("/root/repo/scriptrag.db")
        settings.database_path = repo_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # This should NOT raise a ValueError for /root/repo/
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection was opened successfully
            expected_uri = f"file:{repo_path.resolve()}?mode=ro"
            mock_connect.assert_called_once()

    def test_root_repo_subdir_allowed(self):
        """Test that subdirectories under /root/repo/ are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        settings = MagicMock(spec=ScriptRAGSettings)
        # Valid /root/repo subdirectory path
        repo_path = Path("/root/repo/data/databases/scriptrag.db")
        settings.database_path = repo_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # This should NOT raise a ValueError for /root/repo/ subdirs
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

    def test_root_malicious_repo_blocked(self):
        """Test that malicious paths with 'repo' in name are blocked."""
        from pathlib import Path
        from unittest.mock import MagicMock

        settings = MagicMock(spec=ScriptRAGSettings)
        # Malicious path that contains 'repo' but not under /root/repo/
        malicious_path = Path("/root/malicious-repo/database.db")
        settings.database_path = malicious_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        # This should raise a ValueError - not the allowed /root/repo/ prefix
        with (
            pytest.raises(ValueError, match="Invalid database path detected"),
            get_read_only_connection(settings),
        ):
            pass

    def test_root_other_dirs_blocked(self):
        """Test that other /root/ directories are blocked."""
        from pathlib import Path
        from unittest.mock import MagicMock

        settings = MagicMock(spec=ScriptRAGSettings)
        # Path in /root/ but not in /root/repo/
        other_path = Path("/root/projects/database.db")
        settings.database_path = other_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        # This should raise a ValueError
        with (
            pytest.raises(ValueError, match="Invalid database path detected"),
            get_read_only_connection(settings),
        ):
            pass

    def test_home_directory_allowed(self):
        """Test that user home directories are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        settings = MagicMock(spec=ScriptRAGSettings)
        home_path = Path("/home/user/projects/scriptrag.db")
        settings.database_path = home_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # Home directories should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

    def test_macos_users_directory_allowed(self):
        """Test that macOS /Users/ directories are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        settings = MagicMock(spec=ScriptRAGSettings)
        users_path = Path("/Users/developer/projects/scriptrag.db")
        settings.database_path = users_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # macOS /Users/ directories should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

    def test_windows_user_documents_allowed(self):
        """Test that Windows user Documents directories are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        settings = MagicMock(spec=ScriptRAGSettings)
        docs_path = Path("C:\\Users\\developer\\Documents\\projects\\scriptrag.db")
        settings.database_path = docs_path
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # Windows Documents folders should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

    def test_system_directories_blocked(self):
        """Test that various system directories are blocked."""
        from pathlib import Path
        from unittest.mock import MagicMock

        blocked_paths = [
            "/etc/passwd",
            "/usr/bin/database.db",
            "/bin/scriptrag.db",
            "/sbin/database.db",
            "C:\\Windows\\System32\\database.db",
            "C:\\Program Files\\App\\database.db",
        ]

        for blocked_path in blocked_paths:
            settings = MagicMock(spec=ScriptRAGSettings)
            settings.database_path = Path(blocked_path)
            settings.database_timeout = 30.0
            settings.database_cache_size = -2000
            settings.database_temp_store = "MEMORY"

            # All system directories should be blocked
            with (
                pytest.raises(ValueError, match="Invalid database path detected"),
                get_read_only_connection(settings),
            ):
                pass
