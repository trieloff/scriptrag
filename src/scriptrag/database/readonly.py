"""Read-only database connection utilities."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress

from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


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
        # Check if the resolved path is within a reasonable location
        # Prevent paths that resolve outside of typical project directories
        db_path_str = str(db_path_resolved)

        # List of disallowed paths for security (cross-platform)
        # Unix-style paths
        disallowed_prefixes = ["/etc/", "/usr/", "/var/"]
        # Windows-style paths
        windows_disallowed = ["C:\\Windows", "C:\\Program Files", "C:\\System32"]

        # Parse path components for cross-platform checking
        path_parts = db_path_str.replace("\\", "/").split("/")
        path_components_lower = [part.lower() for part in path_parts]

        # Cross-platform disallowed path components (case-insensitive)
        disallowed_components = [
            "etc",
            "usr",
            "var",
            "windows",
            "program files",
            "system32",
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
                if any(
                    temp_indicator in path_components_lower
                    for temp_indicator in ["temp", "tmp", "pytest", "folders"]
                ):
                    continue
                raise ValueError("Invalid database path detected")

        # Additional check: if in /root/ (Unix) or system dirs, must be temp/repo
        # Allow /root/repo as it's a common development location
        if (
            (
                db_path_str.startswith("/root/")
                and "tmp" not in path_parts
                and "repo" not in path_parts
            )
            or (":\\Users" in db_path_str and "Temp" not in path_parts)
        ) and not any(
            temp_indicator in db_path_str.lower()
            for temp_indicator in ["temp", "tmp", "pytest", "repo"]
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
