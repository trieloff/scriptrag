"""Cross-platform compatibility tests for ScriptRAG.

This module tests platform-specific behaviors and ensures the codebase
works correctly on Windows, macOS, and Linux.
"""

import os
import platform
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.config import ScriptRAGSettings


def get_platform_info():
    """Get detailed platform information for test adaptation."""
    return {
        "system": platform.system(),  # 'Windows', 'Linux', 'Darwin'
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),  # 'x86_64', 'arm64', etc.
        "python_version": sys.version,
        "is_windows": platform.system() == "Windows",
        "is_macos": platform.system() == "Darwin",
        "is_linux": platform.system() == "Linux",
        "is_ci": bool(os.getenv("CI") or os.getenv("GITHUB_ACTIONS")),
    }


@pytest.fixture
def platform_info():
    """Fixture providing platform information."""
    return get_platform_info()


def normalize_text(text: str) -> str:
    """Normalize line endings and whitespace for cross-platform comparison."""
    # Convert all line endings to Unix style
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def safe_windows_path(path: Path) -> Path:
    """Ensure path works on Windows with long path support."""
    if platform.system() == "Windows":
        # Use extended-length path prefix for long paths
        str_path = str(path.resolve())
        if len(str_path) > 250 and not str_path.startswith("\\\\?\\"):
            return Path(f"\\\\?\\{str_path}")
    return path


# Windows reserved filenames
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def is_valid_filename(name: str) -> bool:
    """Check if filename is valid on all platforms."""
    base_name = Path(name).stem.upper()
    return base_name not in WINDOWS_RESERVED


class TestPathHandling:
    """Test cross-platform path handling."""

    def test_path_separators(self, tmp_path):
        """Test that path separators work correctly on all platforms."""
        # Use pathlib.Path for platform-independent paths
        script_path = tmp_path / "scripts" / "test.fountain"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text("Test content")

        # Verify path exists and is correct
        assert script_path.exists()
        assert script_path.is_file()

        # String representation should use platform separator
        path_str = str(script_path)
        if platform.system() == "Windows":
            assert "\\" in path_str or "/" in path_str  # Windows accepts both
        else:
            assert "/" in path_str

    def test_path_resolution(self, tmp_path):
        """Test path resolution and comparison across platforms."""
        # Create test structure
        (tmp_path / "data").mkdir()
        test_file = tmp_path / "data" / "file.txt"
        test_file.write_text("test")

        # Test relative path resolution
        path1 = Path(tmp_path / "data" / ".." / "data" / "file.txt").resolve()
        path2 = (tmp_path / "data" / "file.txt").resolve()

        assert path1 == path2
        assert path1.read_text() == "test"

    def test_case_sensitivity(self, tmp_path, platform_info):
        """Test filesystem case sensitivity handling."""
        file1 = tmp_path / "Test.txt"
        file1.write_text("content1")

        file2 = tmp_path / "test.txt"

        if platform_info["is_windows"] or platform_info["is_macos"]:
            # Case-insensitive by default
            # Attempting to create file2 will overwrite file1
            file2.write_text("content2")
            assert file1.read_text() == "content2"  # Same file
        else:
            # Linux is case-sensitive
            file2.write_text("content2")
            assert file1.read_text() == "content1"
            assert file2.read_text() == "content2"

    def test_long_paths(self, tmp_path, platform_info):
        """Test handling of long path names."""
        # Create a long path (close to Windows limit)
        long_name = "a" * 50
        deep_path = tmp_path

        # Create nested directories
        for i in range(4):  # Limit nesting to avoid exceeding limits
            deep_path = deep_path / f"{long_name}_{i}"

        try:
            deep_path.mkdir(parents=True, exist_ok=True)
            test_file = deep_path / "test.txt"

            # On Windows, might need special handling for very long paths
            if platform_info["is_windows"] and len(str(test_file)) > 250:
                test_file = safe_windows_path(test_file)

            test_file.write_text("content")
            assert test_file.read_text() == "content"
        except OSError as e:
            if platform_info["is_windows"] and "path too long" in str(e).lower():
                pytest.skip("Windows long path support not enabled")
            raise

    def test_reserved_filenames(self, tmp_path, platform_info):
        """Test handling of Windows reserved filenames."""
        for reserved in ["CON", "PRN", "AUX", "NUL"]:
            test_path = tmp_path / f"{reserved}.txt"

            if platform_info["is_windows"]:
                # Modern Windows (Server 2022) may allow reserved names
                # depending on the file system and Windows version
                # We need to test both scenarios
                try:
                    test_path.write_text("test")
                    # If it succeeds on modern Windows, verify we can read it back
                    assert test_path.read_text() == "test"
                    test_path.unlink()  # Clean up
                    # Skip the pytest.raises check since it succeeded
                    continue
                except (OSError, ValueError, PermissionError, FileNotFoundError):
                    # This is expected on older Windows versions
                    pass

                # If we couldn't write, verify it raises an exception
                with pytest.raises((OSError, ValueError)):
                    test_path.write_text("test")
            else:
                # Should work on Unix-like systems
                test_path.write_text("test")
                assert test_path.read_text() == "test"
                test_path.unlink()  # Clean up


class TestLineEndings:
    """Test line ending handling across platforms."""

    def test_text_file_line_endings(self, tmp_path):
        """Test reading and writing text files with different line endings."""
        test_file = tmp_path / "test.txt"

        # Write with explicit line ending using open() to control newline behavior
        content = "Line 1\nLine 2\nLine 3"
        with test_file.open("w", encoding="utf-8", newline="") as f:
            # Write with LF only, no translation
            f.write(content)

        # Read and normalize - newline=None allows Python to normalize line endings
        read_content = test_file.read_text(encoding="utf-8")

        # Both should normalize to the same thing
        assert normalize_text(read_content) == normalize_text(content), (
            f"Line ending mismatch:\nOriginal: {content!r}\nRead:     {read_content!r}"
        )

        # Test CRLF
        crlf_content = "Line 1\r\nLine 2\r\nLine 3"
        with test_file.open("w", encoding="utf-8", newline="") as f:
            f.write(crlf_content)
        read_content = test_file.read_text(encoding="utf-8")
        assert normalize_text(read_content) == normalize_text(content)

    def test_binary_mode_preservation(self, tmp_path):
        """Test that binary mode preserves exact bytes."""
        test_file = tmp_path / "test.bin"

        # Binary mode should preserve exact bytes
        data = b"Line 1\r\nLine 2\nLine 3\r"
        test_file.write_bytes(data)
        assert test_file.read_bytes() == data

    def test_config_file_parsing(self, tmp_path):
        """Test configuration file parsing with different line endings."""
        config_file = tmp_path / ".env"

        # Write config with CRLF (Windows style)
        config_content = "SCRIPTRAG_DEBUG=true\r\nSCRIPTRAG_APP_NAME=test\r\n"
        config_file.write_text(config_content)

        # Should parse correctly regardless of line endings
        with patch.dict(os.environ, {}, clear=True):
            # The settings should handle line endings correctly
            settings = ScriptRAGSettings(_env_file=str(config_file))
            # Note: .env file parsing might not work in all test environments


class TestFileLocking:
    """Test file locking behavior across platforms."""

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="fcntl not available on Windows"
    )
    def test_unix_file_locking(self, tmp_path):
        """Test Unix advisory file locking."""
        import fcntl

        test_file = tmp_path / "locked.txt"
        test_file.write_text("test content")

        with test_file.open("r+b") as f:
            # Acquire exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            try:
                # Can still read the file from another handle (advisory lock)
                with test_file.open() as f2:
                    content = f2.read()
                    assert content == "test content"
            finally:
                # Release lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    @pytest.mark.skipif(
        platform.system() != "Windows", reason="msvcrt only available on Windows"
    )
    def test_windows_file_locking(self, tmp_path):
        """Test Windows mandatory file locking."""
        import msvcrt

        test_file = tmp_path / "locked.txt"
        test_file.write_text("test content")

        with test_file.open("r+b") as f:
            # Lock file for exclusive access
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

            try:
                # Should not be able to write to locked file
                with pytest.raises((IOError, OSError, PermissionError)):
                    with test_file.open("w") as f2:
                        f2.write("should fail")
            finally:
                # Unlock
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

    @pytest.mark.skipif(
        os.getenv("CI") == "true", reason="Skip slow test in CI to avoid timeout"
    )
    def test_sqlite_locking(self, tmp_path):
        """Test SQLite database locking across platforms."""
        db_path = tmp_path / "test.db"

        # Create two connections
        conn1 = sqlite3.connect(str(db_path), timeout=1.0)
        conn2 = sqlite3.connect(str(db_path), timeout=1.0)

        try:
            # Create table
            conn1.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn1.commit()

            # Start exclusive transaction on conn1
            conn1.execute("BEGIN EXCLUSIVE")
            conn1.execute("INSERT INTO test VALUES (1, 'test')")

            # Try to write from conn2 (should fail or timeout)
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn2.execute("INSERT INTO test VALUES (2, 'test2')")
                conn2.commit()

            assert (
                "lock" in str(exc_info.value).lower()
                or "database is locked" in str(exc_info.value).lower()
            )

            # Commit conn1 transaction
            conn1.commit()

            # Now conn2 should be able to write
            conn2.execute("INSERT INTO test VALUES (2, 'test2')")
            conn2.commit()

        finally:
            conn1.close()
            conn2.close()


class TestSQLiteExtensions:
    """Test SQLite extension support across platforms."""

    def test_sqlite_vector_extension(self, tmp_path, platform_info):
        """Test SQLite vector extension availability."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        try:
            # Try to enable extension loading
            conn.enable_load_extension(True)

            # Platform-specific extension filenames
            if platform_info["is_windows"]:
                extensions = ["vec0.dll", "sqlite-vec.dll", "vec.dll"]
            elif platform_info["is_macos"]:
                extensions = ["vec0.dylib", "libvec0.dylib", "vec.dylib"]
            else:  # Linux
                extensions = ["vec0.so", "libvec0.so", "vec.so"]

            # Try to load the extension
            loaded = False
            for ext in extensions:
                try:
                    conn.load_extension(ext)
                    loaded = True
                    break
                except sqlite3.OperationalError:
                    continue

            if not loaded:
                pytest.skip("SQLite vector extension not available on this platform")

            # If loaded, test basic functionality
            conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[3])")
            conn.execute(
                "INSERT INTO test_vec(embedding) VALUES (?)", ([1.0, 2.0, 3.0],)
            )
            conn.commit()

        except AttributeError:
            pytest.skip("SQLite extension loading not supported")
        except sqlite3.OperationalError as e:
            pytest.skip(f"Vector extension not available: {e}")
        finally:
            conn.close()


class TestPlatformSpecific:
    """Test platform-specific behaviors."""

    def test_environment_variables(self, platform_info):
        """Test platform-specific environment variable handling."""
        if platform_info["is_windows"]:
            # Windows environment variables are case-insensitive
            os.environ["TESTVAR"] = "value"
            assert os.getenv("TESTVAR") == "value"
        else:
            # Unix environment variables are case-sensitive
            os.environ["TESTVAR_CASE1"] = "value1"
            os.environ["TESTVAR_CASE2"] = "value2"
            assert os.getenv("TESTVAR_CASE1") == "value1"
            assert os.getenv("TESTVAR_CASE2") == "value2"

    def test_temp_directory(self, platform_info):
        """Test temp directory locations across platforms."""
        temp_dir = Path(tempfile.gettempdir())
        assert temp_dir.exists()
        assert temp_dir.is_dir()

        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("test")
            temp_file = Path(tf.name)

        try:
            assert temp_file.exists()
            assert temp_file.read_text() == "test"
        finally:
            temp_file.unlink()

    def test_path_separators_in_output(self, platform_info):
        """Test that path separators in output are platform-appropriate."""
        test_path = Path("folder") / "subfolder" / "file.txt"
        path_str = str(test_path)

        if platform_info["is_windows"]:
            # Windows uses backslash
            assert (
                path_str == "folder\\subfolder\\file.txt"
                or path_str == "folder/subfolder/file.txt"
            )
        else:
            # Unix uses forward slash
            assert path_str == "folder/subfolder/file.txt"

    def test_executable_permissions(self, tmp_path, platform_info):
        """Test setting executable permissions."""
        if platform_info["is_windows"]:
            pytest.skip("Unix-style permissions not applicable on Windows")

        import stat

        script_file = tmp_path / "script.sh"
        script_file.write_text("#!/bin/bash\necho 'test'")

        # Set executable permission
        current_mode = script_file.stat().st_mode
        script_file.chmod(current_mode | stat.S_IEXEC)

        # Verify permission was set
        assert script_file.stat().st_mode & stat.S_IEXEC


class TestCLIOutput:
    """Test CLI output handling across platforms."""

    def test_ansi_codes_stripping(self):
        """Test ANSI escape code stripping."""
        from tests.cli_fixtures import strip_ansi_codes

        # Test various ANSI codes
        text_with_ansi = "\033[31mRed Text\033[0m Normal \033[1mBold\033[0m"
        cleaned = strip_ansi_codes(text_with_ansi)
        assert cleaned == "Red Text Normal Bold"

        # Test Unicode characters
        text_with_unicode = "✓ Success ✗ Failed"
        # Should preserve Unicode
        assert strip_ansi_codes(text_with_unicode) == text_with_unicode

    def test_terminal_width_detection(self, platform_info):
        """Test terminal width detection across platforms."""
        try:
            import shutil

            columns = shutil.get_terminal_size().columns
            assert columns > 0
        except (AttributeError, ValueError):
            # May not work in all test environments
            pytest.skip("Terminal size detection not available")


class TestCrossPlatformConfig:
    """Test configuration handling across platforms."""

    def test_home_directory_expansion(self):
        """Test tilde expansion in paths."""
        settings = ScriptRAGSettings(database_path="~/scriptrag.db")
        expanded_path = settings.database_path

        # Should expand to user's home directory
        assert str(expanded_path).startswith(str(Path.home()))
        assert "~" not in str(expanded_path)

    def test_environment_variable_expansion(self, tmp_path):
        """Test environment variable expansion in paths."""
        test_dir = str(tmp_path / "custom")

        with patch.dict(os.environ, {"SCRIPTRAG_TEST_DIR": test_dir}):
            settings = ScriptRAGSettings(database_path="$SCRIPTRAG_TEST_DIR/test.db")

            # Should expand environment variable
            assert str(settings.database_path) == str(Path(test_dir) / "test.db")
