"""Database connection management bridge for ScriptRAG.

This module provides a compatibility layer that delegates to the centralized
connection manager while maintaining the existing API.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection_manager import (
    get_connection_manager,
)


class DatabaseConnectionManager:
    """Manages database connections and transactions.

    This class now acts as a facade to the centralized connection manager
    while maintaining backward compatibility.
    """

    def __init__(self, settings: ScriptRAGSettings) -> None:
        """Initialize connection manager with settings.

        Args:
            settings: Configuration settings for database connection
        """
        self.settings = settings
        self.db_path = settings.database_path
        # Use the centralized connection manager
        self._manager = get_connection_manager(settings)

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration.

        Returns:
            Configured SQLite connection from the pool
        """
        return self._manager.get_connection()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a transactional database context.

        Yields:
            Database connection within a transaction context
        """
        with self._manager.transaction() as conn:
            yield conn

    def check_database_exists(self) -> bool:
        """Check if the database exists and is initialized.

        Returns:
            True if database exists and has schema, False otherwise
        """
        return self._manager.check_database_exists()

    def release_connection(self, conn: sqlite3.Connection) -> None:
        """Release a connection back to the pool.

        Args:
            conn: Connection to release
        """
        self._manager.release_connection(conn)
