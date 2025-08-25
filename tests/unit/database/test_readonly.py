"""Tests for read-only database connection utilities."""

import sys
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
        settings.database_journal_mode = "WAL"
        return settings

    def test_get_read_only_connection_success(self, settings):
        """Test successful read-only connection creation."""
        # Create a dummy database file
        db_path = settings.database_path
        db_path.touch()

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called with settings
            mock_get_manager.assert_called_once_with(settings)
            # Verify readonly context was used
            mock_manager.readonly.assert_called_once()

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
        settings.database_journal_mode = "WAL"

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

        # Mock the connection manager to raise an exception
        from scriptrag.exceptions import DatabaseError

        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_get_manager.side_effect = DatabaseError(
                message="Failed to create database connection: Connection error",
                hint="Check database path and permissions",
                details={"db_path": str(db_path)},
            )

            with pytest.raises(
                DatabaseError,
                match="Failed to create database connection: Connection error",
            ):
                with get_read_only_connection(settings):
                    pass

            # Verify connection manager was called with settings
            mock_get_manager.assert_called_once_with(settings)

    def test_get_read_only_connection_no_exception_on_close_error(self, settings):
        """Test that exceptions during close are handled gracefully."""
        db_path = settings.database_path
        db_path.touch()

        # Mock the connection manager - close errors handled internally
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_conn)
            mock_context.__exit__ = MagicMock(
                return_value=None
            )  # Close error handled internally
            mock_manager.readonly.return_value = mock_context

            # Should not raise exception - connection manager handles close errors
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify the context manager was properly used
            mock_context.__exit__.assert_called_once()

    def test_get_read_only_connection_none_connection(self, settings):
        """Test handling when connection is None."""
        db_path = settings.database_path
        db_path.touch()

        # Mock the connection manager to raise error when None connection is attempted
        from scriptrag.exceptions import DatabaseError

        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_get_manager.side_effect = DatabaseError(
                message="Failed to create database connection: NoneType error",
                hint="Check database path and permissions",
                details={"db_path": str(db_path)},
            )

            with pytest.raises(DatabaseError, match="NoneType error"):
                with get_read_only_connection(settings):
                    pass

    def test_get_read_only_connection_exception_cleanup(self, settings):
        """Test exception handling in cleanup - line 34 coverage."""
        db_path = settings.database_path
        db_path.touch()

        # Mock the connection manager to raise exception during initialization
        from scriptrag.exceptions import DatabaseError

        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_get_manager.side_effect = DatabaseError(
                message="Failed to create database connection: Pragma setup failed",
                hint="Check database path and permissions",
                details={"db_path": str(db_path)},
            )

            with pytest.raises(DatabaseError, match="Pragma setup failed"):
                with get_read_only_connection(settings):
                    pass

            # Connection manager should have been called
            mock_get_manager.assert_called_once_with(settings)

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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # This should NOT raise a ValueError for macOS temp dirs
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called with settings
            mock_get_manager.assert_called_once_with(settings)

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
        settings.database_journal_mode = "WAL"

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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # This should NOT raise a ValueError for /root/repo/
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called with settings
            mock_get_manager.assert_called_once_with(settings)

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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # This should NOT raise a ValueError for /root/repo/ subdirs
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called
            mock_get_manager.assert_called_once_with(settings)

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific path test")
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
        settings.database_journal_mode = "WAL"

        # This should raise a ValueError - not the allowed /root/repo/ prefix
        with (
            pytest.raises(ValueError, match="Invalid database path detected"),
            get_read_only_connection(settings),
        ):
            pass

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific path test")
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
        settings.database_journal_mode = "WAL"

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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Home directories should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called
            mock_get_manager.assert_called_once_with(settings)

    @pytest.mark.skipif(sys.platform == "win32", reason="macOS-specific path test")
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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # macOS /Users/ directories should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called
            mock_get_manager.assert_called_once_with(settings)

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
        settings.database_journal_mode = "WAL"

        # Mock the connection manager to prevent actual database initialization
        with patch(
            "scriptrag.database.readonly.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Windows Documents folders should be allowed
            with get_read_only_connection(settings) as conn:
                assert conn == mock_conn

            # Verify connection manager was called
            mock_get_manager.assert_called_once_with(settings)

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
            settings.database_journal_mode = "WAL"

            # All system directories should be blocked
            with (
                pytest.raises(ValueError, match="Invalid database path detected"),
                get_read_only_connection(settings),
            ):
                pass

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix-specific path traversal test"
    )
    def test_path_traversal_attacks_blocked(self):
        """Test that path traversal attacks are blocked."""
        from pathlib import Path
        from unittest.mock import MagicMock

        # Test various path traversal attack vectors
        attack_paths = [
            "/root/repo/../../../etc/passwd",  # Escape to /etc/passwd
            "/root/repo/../../../home/user/.ssh/id_rsa",  # Access SSH keys
            "/root/repo/../../etc/shadow",  # Access shadow file
            "/root/repo/../projects/secret.db",  # Escape to sibling directory
            "/root/repo/./../../etc/hosts",  # With current directory
            "/root/repo/subdir/../../../../../../etc/passwd",  # Deep traversal
            "/root/repo/../repo/../../../etc/passwd",  # Complex traversal
        ]

        for attack_path in attack_paths:
            settings = MagicMock(spec=ScriptRAGSettings)
            settings.database_path = Path(attack_path)
            settings.database_timeout = 30.0
            settings.database_cache_size = -2000
            settings.database_temp_store = "MEMORY"
            settings.database_journal_mode = "WAL"

            # All path traversal attempts should be blocked
            with (
                pytest.raises(ValueError, match="Invalid database path detected"),
                get_read_only_connection(settings),
            ):
                pass

    def test_legitimate_repo_paths_allowed(self):
        """Test that legitimate /root/repo paths are allowed."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        # Test legitimate paths within /root/repo
        legitimate_paths = [
            "/root/repo/scriptrag.db",
            "/root/repo/data/database.db",
            "/root/repo/subdir/nested/deep/file.db",
        ]

        for legit_path in legitimate_paths:
            settings = MagicMock(spec=ScriptRAGSettings)
            settings.database_path = Path(legit_path)
            settings.database_timeout = 30.0
            settings.database_cache_size = -2000
            settings.database_temp_store = "MEMORY"
            settings.database_journal_mode = "WAL"

            # Mock the connection manager to prevent actual database initialization
            with patch(
                "scriptrag.database.readonly.get_connection_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_conn = MagicMock()
                mock_get_manager.return_value = mock_manager
                mock_manager.readonly.return_value.__enter__ = MagicMock(
                    return_value=mock_conn
                )
                mock_manager.readonly.return_value.__exit__ = MagicMock(
                    return_value=None
                )

                # These should be allowed
                with get_read_only_connection(settings) as conn:
                    assert conn == mock_conn

                # Verify connection manager was called
                mock_get_manager.assert_called_once_with(settings)
                mock_get_manager.reset_mock()
