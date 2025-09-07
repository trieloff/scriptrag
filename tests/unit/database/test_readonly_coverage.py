"""Additional tests to improve coverage for the readonly module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config.settings import ScriptRAGSettings
from scriptrag.database.readonly import (
    _is_allowed_development_path,
    _is_temp_directory,
    get_read_only_connection,
)


class TestIsAllowedDevelopmentPath:
    """Test the _is_allowed_development_path function."""

    @pytest.mark.unit
    def test_allowed_development_paths(self):
        """Test that allowed development paths are correctly identified."""
        # Test allowed paths
        assert _is_allowed_development_path("/root/repo/test.db") is True
        assert _is_allowed_development_path("/root/repo/data/test.db") is True
        assert _is_allowed_development_path("/home/user/project/test.db") is True
        assert _is_allowed_development_path("/home/runner/work/test.db") is True
        assert _is_allowed_development_path("/Users/developer/test.db") is True
        assert _is_allowed_development_path("/Users/john/Documents/test.db") is True

    @pytest.mark.unit
    def test_disallowed_development_paths(self):
        """Test that non-development paths are correctly rejected."""
        assert _is_allowed_development_path("/etc/passwd") is False
        assert _is_allowed_development_path("/usr/bin/test.db") is False
        assert _is_allowed_development_path("/var/lib/test.db") is False
        assert _is_allowed_development_path("/opt/app/test.db") is False
        assert _is_allowed_development_path("/tmp/test.db") is False
        assert _is_allowed_development_path("/mnt/data/test.db") is False

    @pytest.mark.unit
    def test_edge_cases(self):
        """Test edge cases for development path detection."""
        # Empty path
        assert _is_allowed_development_path("") is False

        # Root path
        assert _is_allowed_development_path("/") is False

        # Path that starts with allowed but continues differently
        assert _is_allowed_development_path("/root/other/test.db") is False
        assert _is_allowed_development_path("/homestead/test.db") is False
        assert _is_allowed_development_path("/UserData/test.db") is False


class TestIsTempDirectoryAdditional:
    """Additional tests for _is_temp_directory function."""

    @pytest.mark.unit
    def test_private_var_folders_detection(self):
        """Test detection of macOS private var folders."""
        # Test /private/var/folders/ paths
        assert _is_temp_directory("/private/var/folders/xy/abc/T/test.db") is True
        assert _is_temp_directory("/private/var/folders/test.db") is True

        # Test /private/var/tmp/ paths
        assert _is_temp_directory("/private/var/tmp/test.db") is True
        assert _is_temp_directory("/private/var/tmp/subdir/test.db") is True

    @pytest.mark.unit
    def test_ci_path_startswith(self):
        """Test that CI paths are only detected at the start."""
        # Should detect when at start
        assert _is_temp_directory("/home/runner/work/project/test.db") is True
        assert _is_temp_directory("/github/workspace/project/test.db") is True

        # Should not detect when in middle or end
        assert _is_temp_directory("/var/home/runner/work/test.db") is False
        assert _is_temp_directory("/data/github/workspace/test.db") is False
        assert _is_temp_directory("/path/to/home/runner/work") is False

    @pytest.mark.unit
    def test_combined_conditions(self):
        """Test paths that might match multiple conditions."""
        # Path with both temp indicator and CI path
        assert _is_temp_directory("/home/runner/work/tmp/test.db") is True

        # Private var folders with temp indicators
        assert _is_temp_directory("/private/var/folders/tmp/test.db") is True

        # Non-temp path that looks similar to temp
        assert _is_temp_directory("/private/var/lib/test.db") is False


class TestGetReadOnlyConnectionAdditional:
    """Additional tests for get_read_only_connection function."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_journal_mode = "WAL"
        return settings

    @pytest.mark.unit
    def test_windows_system_paths_blocked(self, mock_settings):
        """Test that Windows system paths are blocked early."""
        windows_paths = [
            "C:\\Windows\\System32\\test.db",
            "C:\\Program Files\\App\\test.db",
            "C:\\System32\\test.db",
            "C:\\System\\test.db",
        ]

        for win_path in windows_paths:
            mock_settings.database_path = Path(win_path)

            with pytest.raises(ValueError, match="Invalid database path detected"):
                with get_read_only_connection(mock_settings):
                    pass

    @pytest.mark.unit
    def test_windows_user_directory_validation(self, mock_settings):
        """Test Windows user directory validation logic."""
        # Test allowed Windows user paths (with development indicators)
        allowed_paths = [
            Path("C:\\Users\\dev\\Documents\\project\\test.db"),
            Path("C:\\Users\\dev\\Desktop\\test.db"),
            Path("C:\\Users\\dev\\Projects\\app\\test.db"),
            Path("C:\\Users\\dev\\repos\\test.db"),
        ]

        for path in allowed_paths:
            mock_settings.database_path = path

            with patch(
                "scriptrag.database.readonly.get_connection_manager"
            ) as mock_mgr:
                mock_manager = MagicMock()
                mock_conn = MagicMock()
                mock_mgr.return_value = mock_manager
                mock_manager.readonly.return_value.__enter__ = MagicMock(
                    return_value=mock_conn
                )
                mock_manager.readonly.return_value.__exit__ = MagicMock(
                    return_value=None
                )

                # Should not raise for allowed paths
                with get_read_only_connection(mock_settings) as conn:
                    assert conn == mock_conn

    @pytest.mark.unit
    def test_windows_user_directory_blocked(self, mock_settings):
        """Test that non-development Windows user paths are blocked."""
        # Path in Windows Users but not in a development directory
        mock_settings.database_path = Path("C:\\Users\\admin\\AppData\\test.db")

        with pytest.raises(ValueError, match="Invalid database path detected"):
            with get_read_only_connection(mock_settings):
                pass

    @pytest.mark.unit
    def test_temp_directory_exceptions(self, mock_settings, tmp_path):
        """Test that temp directories bypass security checks."""
        # Create a path that would normally be blocked but is in temp
        temp_base = tmp_path / "var" / "lib"
        temp_base.mkdir(parents=True)
        temp_db = temp_base / "test.db"
        temp_db.touch()

        mock_settings.database_path = temp_db

        with patch("scriptrag.database.readonly.get_connection_manager") as mock_mgr:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_mgr.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Should be allowed because it's in a temp directory
            with get_read_only_connection(mock_settings) as conn:
                assert conn == mock_conn

    @pytest.mark.unit
    def test_disallowed_components_with_temp_exception(self, mock_settings, tmp_path):
        """Test that disallowed components are allowed in temp directories."""
        # Create temp path with normally disallowed component
        temp_base = tmp_path / "etc"
        temp_base.mkdir()
        temp_db = temp_base / "test.db"
        temp_db.touch()

        mock_settings.database_path = temp_db

        with patch("scriptrag.database.readonly.get_connection_manager") as mock_mgr:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_mgr.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Should be allowed because it's in a temp directory
            with get_read_only_connection(mock_settings) as conn:
                assert conn == mock_conn

    @pytest.mark.unit
    def test_private_var_folders_exception(self, mock_settings):
        """Test that /private/var/folders/ paths bypass /var restriction."""
        mock_settings.database_path = Path("/private/var/folders/xy/abc/T/test.db")

        with patch("scriptrag.database.readonly.get_connection_manager") as mock_mgr:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_mgr.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Should be allowed as macOS temp directory
            with get_read_only_connection(mock_settings) as conn:
                assert conn == mock_conn

    @pytest.mark.unit
    def test_root_path_traversal_detection(self, mock_settings):
        """Test path traversal detection for /root/ paths."""
        # Test path traversal attempt from /root/repo
        mock_settings.database_path = Path("/root/repo/../../../etc/passwd")

        with pytest.raises(ValueError, match="Invalid database path detected"):
            with get_read_only_connection(mock_settings):
                pass

    @pytest.mark.unit
    def test_root_repo_exact_path(self, mock_settings):
        """Test that exact /root/repo path is allowed."""
        mock_settings.database_path = Path("/root/repo")

        with patch("scriptrag.database.readonly.get_connection_manager") as mock_mgr:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_mgr.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Exact /root/repo path should be allowed
            with get_read_only_connection(mock_settings) as conn:
                assert conn == mock_conn

    @pytest.mark.unit
    def test_root_temp_directory_allowed(self, mock_settings):
        """Test that temp directories under /root/ are allowed."""
        mock_settings.database_path = Path("/root/tmp/test.db")

        with patch("scriptrag.database.readonly.get_connection_manager") as mock_mgr:
            mock_manager = MagicMock()
            mock_conn = MagicMock()
            mock_mgr.return_value = mock_manager
            mock_manager.readonly.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_manager.readonly.return_value.__exit__ = MagicMock(return_value=None)

            # Should be allowed as temp directory
            with get_read_only_connection(mock_settings) as conn:
                assert conn == mock_conn
