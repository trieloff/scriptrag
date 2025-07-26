"""Database connection management for ScriptRAG.

This module provides connection management for the SQLite-based graph database,
including transaction support, connection pooling, and error handling.
"""

import contextlib
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from scriptrag.config import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """Manages SQLite database connections for ScriptRAG."""

    def __init__(self, db_path: str | Path, **kwargs: Any) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file
            **kwargs: Additional connection parameters
        """
        self.db_path = Path(db_path)
        self.connection_params = {
            "timeout": kwargs.get("timeout", 30.0),
            "check_same_thread": kwargs.get("check_same_thread", False),
            "isolation_level": kwargs.get("isolation_level"),  # Autocommit mode
        }
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection.

        Returns:
            SQLite connection object
        """
        if not hasattr(self._local, "connection") or self._local.connection is None:
            logger.debug(f"Creating new database connection to {self.db_path}")

            # Ensure database file's parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connection with optimized settings
            conn = sqlite3.connect(str(self.db_path), **self.connection_params)

            # Configure connection for optimal performance and safety
            self._configure_connection(conn)

            self._local.connection = conn

        return cast(sqlite3.Connection, self._local.connection)

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Configure SQLite connection with optimal settings.

        Args:
            conn: SQLite connection to configure
        """
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")

        # Set journal mode to WAL for better concurrency
        # But use DELETE mode in tests or on Windows to avoid file locking issues
        import os
        import platform

        if os.environ.get("PYTEST_CURRENT_TEST") or platform.system() == "Windows":
            conn.execute("PRAGMA journal_mode = DELETE")
        else:
            conn.execute("PRAGMA journal_mode = WAL")

        # Optimize for better performance
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")

        # Enable automatic index creation
        conn.execute("PRAGMA automatic_index = ON")

        # Set row factory for named column access
        conn.row_factory = sqlite3.Row

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection in a context manager.

        Yields:
            SQLite connection object

        Example:
            with db_conn.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM scripts")
                results = cursor.fetchall()
        """
        conn = self._get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            # Don't close the connection here - keep it open for thread
            pass

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Execute operations in a database transaction.

        Yields:
            SQLite connection object in transaction mode

        Example:
            with db_conn.transaction() as conn:
                conn.execute("INSERT INTO scripts ...")
                conn.execute("INSERT INTO scenes ...")
                # Automatically committed if no exception
        """
        conn = self._get_connection()

        # Start transaction
        conn.execute("BEGIN")

        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            conn.rollback()
            raise

    def execute(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> sqlite3.Cursor:
        """Execute a single SQL statement.

        Args:
            sql: SQL statement to execute
            parameters: Parameters for the SQL statement

        Returns:
            Cursor object with query results
        """
        with self.get_connection() as conn:
            if parameters is None:
                return conn.execute(sql)
            return conn.execute(sql, parameters)

    def executemany(
        self, sql: str, parameters_list: list[tuple | dict]
    ) -> sqlite3.Cursor:
        """Execute SQL statement multiple times with different parameters.

        Args:
            sql: SQL statement to execute
            parameters_list: List of parameter sets

        Returns:
            Cursor object
        """
        with self.get_connection() as conn:
            return conn.executemany(sql, parameters_list)

    def fetch_one(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> sqlite3.Row | None:
        """Execute query and fetch one result.

        Args:
            sql: SQL query to execute
            parameters: Parameters for the SQL query

        Returns:
            Single row result or None
        """
        cursor = self.execute(sql, parameters)
        return cast(sqlite3.Row | None, cursor.fetchone())

    def fetch_all(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> list[sqlite3.Row]:
        """Execute query and fetch all results.

        Args:
            sql: SQL query to execute
            parameters: Parameters for the SQL query

        Returns:
            List of row results
        """
        cursor = self.execute(sql, parameters)
        return cursor.fetchall()

    def fetch_many(
        self, sql: str, size: int, parameters: tuple | dict | None = None
    ) -> list[sqlite3.Row]:
        """Execute query and fetch specified number of results.

        Args:
            sql: SQL query to execute
            size: Number of rows to fetch
            parameters: Parameters for the SQL query

        Returns:
            List of row results (up to size)
        """
        cursor = self.execute(sql, parameters)
        return cursor.fetchmany(size)

    def get_table_info(self, table_name: str) -> list[sqlite3.Row]:
        """Get information about a table's structure.

        Args:
            table_name: Name of the table

        Returns:
            List of column information
        """
        return self.fetch_all(f"PRAGMA table_info({table_name})")

    def get_table_names(self) -> list[str]:
        """Get list of all table names in the database.

        Returns:
            List of table names
        """
        cursor = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row["name"] for row in cursor.fetchall()]

    def vacuum(self) -> None:
        """Optimize database by running VACUUM command."""
        logger.info("Running database VACUUM to optimize storage")
        with self.get_connection() as conn:
            conn.execute("VACUUM")

    def analyze(self) -> None:
        """Update query planner statistics."""
        logger.info("Running ANALYZE to update query statistics")
        with self.get_connection() as conn:
            conn.execute("ANALYZE")

    def get_database_size(self) -> int:
        """Get database file size in bytes.

        Returns:
            Database file size in bytes
        """
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            logger.debug("Closing database connection")
            # Ensure all transactions are committed or rolled back
            with contextlib.suppress(Exception):
                self._local.connection.rollback()

            # Close the connection
            with contextlib.suppress(Exception):
                self._local.connection.close()

            self._local.connection = None

            # Force garbage collection to help with Windows file locking
            import gc

            gc.collect()

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry."""
        return self

    def __exit__(
        self, _exc_type: type | None, _exc_val: Exception | None, _exc_tb: Any
    ) -> None:
        """Context manager exit."""
        self.close()


# Global connection instance (can be configured at module level)
_default_connection: DatabaseConnection | None = None


def get_default_connection() -> DatabaseConnection:
    """Get the default database connection.

    Returns:
        Default DatabaseConnection instance

    Raises:
        RuntimeError: If no default connection is configured
    """
    if _default_connection is None:
        raise RuntimeError(
            "No default database connection configured. "
            "Call set_default_connection() first."
        )
    return _default_connection


def set_default_connection(db_path: str | Path, **kwargs: Any) -> DatabaseConnection:
    """Set the default database connection.

    Args:
        db_path: Path to SQLite database file
        **kwargs: Additional connection parameters

    Returns:
        DatabaseConnection instance
    """
    global _default_connection
    _default_connection = DatabaseConnection(db_path, **kwargs)
    return _default_connection


def close_default_connection() -> None:
    """Close the default database connection."""
    global _default_connection
    if _default_connection:
        _default_connection.close()
        _default_connection = None


@contextmanager
def temporary_connection(
    db_path: str | Path, **kwargs: Any
) -> Generator[DatabaseConnection, None, None]:
    """Create a temporary database connection.

    Args:
        db_path: Path to SQLite database file
        **kwargs: Additional connection parameters

    Yields:
        DatabaseConnection instance

    Example:
        with temporary_connection("test.db") as conn:
            results = conn.fetch_all("SELECT * FROM scripts")
    """
    conn = DatabaseConnection(db_path, **kwargs)
    try:
        yield conn
    finally:
        conn.close()
