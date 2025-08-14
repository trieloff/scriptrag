"""Platform-specific test utilities for cross-platform compatibility.

This module provides utilities for handling platform-specific differences
in tests, ensuring ScriptRAG works correctly on Windows, macOS, and Linux.
"""

import contextlib
import os
import platform
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest


def get_platform_info() -> dict[str, Any]:
    """Get comprehensive platform information for test adaptation.

    Returns:
        Dictionary containing platform details and boolean flags
    """
    return {
        "system": platform.system(),  # 'Windows', 'Linux', 'Darwin'
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),  # 'x86_64', 'arm64', etc.
        "python_version": sys.version,
        "python_version_tuple": sys.version_info[:3],
        "is_windows": platform.system() == "Windows",
        "is_macos": platform.system() == "Darwin",
        "is_linux": platform.system() == "Linux",
        "is_unix": platform.system() in ("Linux", "Darwin"),
        "is_ci": bool(os.getenv("CI") or os.getenv("GITHUB_ACTIONS")),
        "is_arm": "arm" in platform.machine().lower(),
        "is_64bit": sys.maxsize > 2**32,
    }


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to Unix style (LF) for consistent comparison.

    Args:
        text: Text with potentially mixed line endings

    Returns:
        Text with normalized Unix-style line endings
    """
    # Convert all line ending variations to Unix style
    text = text.replace("\r\n", "\n")  # Windows CRLF -> LF
    return text.replace("\r", "\n")  # Old Mac CR -> LF


def normalize_path_separators(path_str: str) -> str:
    """Normalize path separators to forward slashes for comparison.

    Args:
        path_str: Path string with platform-specific separators

    Returns:
        Path string with forward slashes
    """
    return path_str.replace("\\", "/")


def compare_paths(path1: Path | str, path2: Path | str) -> bool:
    """Compare two paths in a platform-independent way.

    Handles case sensitivity differences and path resolution.

    Args:
        path1: First path to compare
        path2: Second path to compare

    Returns:
        True if paths refer to the same location
    """
    p1 = Path(path1).resolve()
    p2 = Path(path2).resolve()

    # On case-insensitive filesystems (Windows, default macOS)
    if platform.system() in ("Windows", "Darwin"):
        return str(p1).lower() == str(p2).lower()

    return p1 == p2


def safe_remove_file(path: Path, retries: int = 3, delay: float = 0.1) -> None:
    """Safely remove a file with retries for Windows file locking issues.

    Args:
        path: Path to file to remove
        retries: Number of retry attempts
        delay: Delay between retries in seconds
    """
    import time

    for attempt in range(retries):
        try:
            if path.exists():
                path.unlink()
            return
        except (PermissionError, OSError) as e:
            if attempt == retries - 1:
                raise
            # On Windows, files might be locked briefly
            time.sleep(delay)
            # Force garbage collection to close any open handles
            import gc

            gc.collect()


def get_temp_dir() -> Path:
    """Get the system temp directory in a platform-independent way.

    Returns:
        Path to the temporary directory
    """
    return Path(tempfile.gettempdir())


def is_valid_windows_filename(name: str) -> bool:
    """Check if a filename is valid on Windows.

    Args:
        name: Filename to check

    Returns:
        True if the filename is valid on Windows
    """
    # Windows reserved names
    reserved = {
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

    # Check base name without extension
    base_name = Path(name).stem.upper()
    if base_name in reserved:
        return False

    # Check for invalid characters
    invalid_chars = '<>:"|?*'
    if any(char in name for char in invalid_chars):
        return False

    # Check for trailing dots or spaces (not allowed on Windows)
    return not (name.endswith(".") or name.endswith(" "))


def handle_long_path_windows(path: Path) -> Path:
    """Handle long paths on Windows by using extended-length path prefix.

    Args:
        path: Path that might be too long for Windows

    Returns:
        Path with extended-length prefix if needed
    """
    if platform.system() != "Windows":
        return path

    str_path = str(path.resolve())
    # Windows has a 260 character limit without extended paths
    if len(str_path) > 250 and not str_path.startswith("\\\\?\\"):
        return Path(f"\\\\?\\{str_path}")

    return path


@contextmanager
def temporary_env_var(name: str, value: str):
    """Context manager for temporarily setting an environment variable.

    Args:
        name: Environment variable name
        value: Value to set
    """
    old_value = os.environ.get(name)
    os.environ[name] = value

    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old_value


def check_sqlite_extension_support(extension_name: str = "vec0") -> bool:
    """Check if a SQLite extension is available on the current platform.

    Args:
        extension_name: Base name of the extension (without file extension)

    Returns:
        True if the extension can be loaded
    """
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)

        # Check if extension loading is supported
        try:
            conn.enable_load_extension(True)
        except AttributeError:
            return False

        # Platform-specific extension filenames
        if platform.system() == "Windows":
            extensions = [f"{extension_name}.dll", f"lib{extension_name}.dll"]
        elif platform.system() == "Darwin":
            extensions = [f"{extension_name}.dylib", f"lib{extension_name}.dylib"]
        else:  # Linux
            extensions = [f"{extension_name}.so", f"lib{extension_name}.so"]

        # Try to load the extension
        for ext_file in extensions:
            try:
                conn.load_extension(ext_file)
                return True
            except sqlite3.OperationalError:
                continue

        return False

    except Exception:
        return False
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        Path(db_path).unlink(missing_ok=True)


def skip_on_platform(*platforms: str):
    """Decorator to skip tests on specific platforms.

    Args:
        platforms: Platform names to skip ('Windows', 'Darwin', 'Linux')

    Example:
        @skip_on_platform('Windows')
        def test_unix_only():
            pass
    """
    current_platform = platform.system()
    skip_test = current_platform in platforms

    return pytest.mark.skipif(skip_test, reason=f"Test skipped on {current_platform}")


def require_platform(*platforms: str):
    """Decorator to require specific platforms for a test.

    Args:
        platforms: Platform names required ('Windows', 'Darwin', 'Linux')

    Example:
        @require_platform('Linux', 'Darwin')
        def test_unix_specific():
            pass
    """
    current_platform = platform.system()
    has_platform = current_platform in platforms

    return pytest.mark.skipif(
        not has_platform,
        reason=f"Test requires one of {platforms}, running on {current_platform}",
    )


def get_executable_extension() -> str:
    """Get the platform-specific executable file extension.

    Returns:
        '.exe' on Windows, empty string on Unix
    """
    return ".exe" if platform.system() == "Windows" else ""


def normalize_output_for_comparison(output: str) -> str:
    """Normalize CLI output for cross-platform comparison.

    This handles:
    - Line endings
    - Path separators
    - Unicode normalization
    - Whitespace differences

    Args:
        output: Raw CLI output

    Returns:
        Normalized output suitable for comparison
    """
    # Normalize line endings
    output = normalize_line_endings(output)

    # Normalize path separators in common patterns
    # Convert Windows paths to Unix style for comparison
    import re

    # Match paths like C:\Users\... or .\path\to\file
    windows_path_pattern = re.compile(r"([A-Za-z]:)?[\\]+([^\\s]+[\\]+)*[^\\s]*")
    output = windows_path_pattern.sub(lambda m: m.group(0).replace("\\", "/"), output)

    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in output.split("\n")]
    output = "\n".join(lines)

    # Remove multiple consecutive blank lines
    while "\n\n\n" in output:
        output = output.replace("\n\n\n", "\n\n")

    return output.strip()


class PlatformTestHelper:
    """Helper class for platform-specific test operations."""

    def __init__(self):
        """Initialize the platform test helper."""
        self.info = get_platform_info()

    def skip_if_ci_and_windows(self, reason: str = "Known CI issue on Windows"):
        """Skip test if running in CI on Windows.

        Args:
            reason: Reason for skipping
        """
        if self.info["is_ci"] and self.info["is_windows"]:
            pytest.skip(reason)

    def skip_if_no_sqlite_extension(self, extension: str = "vec0"):
        """Skip test if SQLite extension is not available.

        Args:
            extension: Extension name to check
        """
        if not check_sqlite_extension_support(extension):
            pytest.skip(f"SQLite {extension} extension not available")

    def get_file_lock_timeout(self) -> float:
        """Get appropriate file lock timeout for the platform.

        Returns:
            Timeout in seconds
        """
        # Windows might need longer timeouts for file operations
        return 2.0 if self.info["is_windows"] else 1.0

    def assert_path_equals(self, path1: Path | str, path2: Path | str):
        """Assert two paths are equal in a platform-aware way.

        Args:
            path1: First path
            path2: Second path
        """
        assert compare_paths(path1, path2), (
            f"{path1} != {path2} (platform: {self.info['system']})"
        )


# Create a singleton instance for easy access
platform_helper = PlatformTestHelper()
