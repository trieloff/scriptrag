"""Database connection management for ScriptRAG."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from scriptrag.config import ScriptRAGSettings


class DatabaseConnectionManager:
    """Manages database connections and transactions."""

    def __init__(self, settings: ScriptRAGSettings) -> None:
        """Initialize connection manager with settings.

        Args:
            settings: Configuration settings for database connection
        """
        self.settings = settings
        self.db_path = settings.database_path

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration.

        Returns:
            Configured SQLite connection
        """
        conn = sqlite3.connect(
            str(self.db_path), timeout=self.settings.database_timeout
        )

        # Configure connection pragmas
        pragma_settings = {
            "journal_mode": self.settings.database_journal_mode,
            "synchronous": self.settings.database_synchronous,
            "cache_size": self.settings.database_cache_size,
            "temp_store": self.settings.database_temp_store,
        }

        for pragma, value in pragma_settings.items():
            conn.execute(f"PRAGMA {pragma} = {value}")

        if self.settings.database_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        # Enable JSON support
        conn.row_factory = sqlite3.Row

        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a transactional database context.

        Yields:
            Database connection within a transaction context
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_database_exists(self) -> bool:
        """Check if the database exists and is initialized.

        Returns:
            True if database exists and has schema, False otherwise
        """
        if not self.db_path.exists():
            return False

        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='scripts'"
                )
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
