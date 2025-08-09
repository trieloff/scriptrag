"""Shared helper for read-only SQLite connections.

This mirrors SearchEngine.get_read_only_connection behavior so other
components (like dynamic query runner) can reuse the exact same
read-only connection semantics.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from scriptrag.config import ScriptRAGSettings


@contextmanager
def get_read_only_connection(
    settings: ScriptRAGSettings, db_path: Path | None = None
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a read-only SQLite connection.

    Args:
        settings: App settings instance
        db_path: Optional explicit database path; defaults to settings.database_path

    Yields:
        sqlite3.Connection configured for read-only access
    """
    conn: sqlite3.Connection | None = None
    try:
        dbp = (db_path or settings.database_path).resolve()

        # Basic path traversal guard: ensure path is within its parent dir
        if not str(dbp).startswith(str(settings.database_path.parent.resolve())):
            raise ValueError("Invalid database path detected")

        # Read-only URI with same timeout and pragmas as search engine
        uri = f"file:{dbp}?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=settings.database_timeout,
            check_same_thread=False,
        )

        # Read-only and performance pragmas
        conn.execute("PRAGMA query_only = ON")
        conn.execute(f"PRAGMA cache_size = {settings.database_cache_size}")
        conn.execute(f"PRAGMA temp_store = {settings.database_temp_store}")

        # Row factory for dict-like access
        conn.row_factory = sqlite3.Row

        yield conn
    finally:
        if conn:
            conn.close()
