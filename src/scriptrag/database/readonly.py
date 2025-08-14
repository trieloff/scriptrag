"""Read-only database connection utilities."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress

from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


def _is_allowed_development_path(db_path_str: str) -> bool:
    """Check if path is in an allowed development location.

    Args:
        db_path_str: Resolved database path as string

    Returns:
        True if path is in allowed development location
    """
    # Specific allowed development paths (must be exact prefixes)
    allowed_dev_paths = [
        "/root/repo/",  # Container development
        "/home/",  # User home directories
        "/Users/",  # macOS user directories
    ]

    # Check if path starts with any allowed prefix
    for allowed_prefix in allowed_dev_paths:
        if db_path_str.startswith(allowed_prefix):
            return True

    return False


def _is_temp_directory(db_path_str: str, path_parts: list[str]) -> bool:
    """Check if path is in a temporary directory.

    Args:
        db_path_str: Resolved database path as string
        path_parts: Path components split by /

    Returns:
        True if path is in a temp directory
    """
    _ = path_parts  # Kept for potential future use
    path_lower = db_path_str.lower()
    temp_indicators = ["temp", "tmp", "pytest", ".pytest_cache"]

    # Check for temp indicators in path
    return any(indicator in path_lower for indicator in temp_indicators)


@contextmanager
def get_read_only_connection(
    settings: ScriptRAGSettings,
) -> Generator[sqlite3.Connection, None, None]:
    """Get a read-only database connection with context manager.

    Args:
        settings: Configuration settings

    Yields:
        Read-only SQLite connection

    Raises:
        ValueError: If database path is invalid
    """
    conn = None
    try:
        # SECURITY: Check for path traversal BEFORE resolving
        db_path_original = settings.database_path

        # Check for path traversal components before resolution
        path_parts_original = str(db_path_original).replace("\\", "/").split("/")
        if ".." in path_parts_original:
            raise ValueError("Invalid database path detected")

        # Now resolve the path
        db_path_resolved = db_path_original.resolve()
        db_path_str = str(db_path_resolved)

        # Parse path components for cross-platform checking
        path_parts = db_path_str.replace("\\", "/").split("/")
        path_components_lower = [part.lower() for part in path_parts]

        # List of disallowed paths for security (cross-platform)
        # Unix-style paths
        disallowed_prefixes = ["/etc/", "/usr/", "/var/", "/bin/", "/sbin/"]
        # Windows-style paths
        windows_disallowed = [
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\System32",
            "C:\\System",
        ]

        # Cross-platform disallowed path components (case-insensitive)
        disallowed_components = [
            "etc",
            "usr",
            "var",
            "windows",
            "program files",
            "system32",
            "bin",
            "sbin",
        ]

        # Check if path is in a disallowed location (Unix-style)
        for prefix in disallowed_prefixes:
            if db_path_str.startswith(prefix) or prefix in db_path_str:
                # Exception: Allow macOS temporary directories in /private/var/folders/
                if prefix == "/var/" and "/private/var/folders/" in db_path_str:
                    continue
                raise ValueError("Invalid database path detected")

        # Windows-specific checks
        for prefix in windows_disallowed:
            if db_path_str.startswith(prefix):
                raise ValueError("Invalid database path detected")

        # Cross-platform component check for path traversal attempts
        for disallowed in disallowed_components:
            if disallowed in path_components_lower:
                # Exception: Allow temp directories that contain these components
                if _is_temp_directory(db_path_str, path_parts):
                    continue
                raise ValueError("Invalid database path detected")

        # Special handling for /root/ paths (common in containers)
        if db_path_str.startswith("/root/") and not (
            db_path_str.startswith("/root/repo/")
            or _is_temp_directory(db_path_str, path_parts)
        ):
            raise ValueError("Invalid database path detected")

        # Validate Windows user directories
        if (
            ":\\Users" in db_path_str
            and not _is_temp_directory(db_path_str, path_parts)
            and not any(
                dev_dir in path_parts
                for dev_dir in ["Documents", "Desktop", "Projects", "repos"]
            )
        ):
            raise ValueError("Invalid database path detected")

        # Open connection in read-only mode
        uri = f"file:{db_path_resolved}?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=settings.database_timeout,
            check_same_thread=False,
        )

        # Configure for read-only access
        conn.execute("PRAGMA query_only = ON")
        conn.execute(f"PRAGMA cache_size = {settings.database_cache_size}")
        conn.execute(f"PRAGMA temp_store = {settings.database_temp_store}")

        # Enable JSON support
        conn.row_factory = sqlite3.Row

        yield conn
    finally:
        if conn:
            with suppress(Exception):
                conn.close()
