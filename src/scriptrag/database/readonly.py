"""Read-only database connection utilities."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

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
        # Validate database path to prevent path traversal
        db_path_resolved = settings.database_path.resolve()
        if not str(db_path_resolved).startswith(
            str(settings.database_path.parent.resolve())
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
            conn.close()
