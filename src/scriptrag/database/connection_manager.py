"""Centralized database connection management with pooling and lifecycle management.

This module provides a thread-safe connection manager with connection pooling,
automatic health checks, and proper resource cleanup for ScriptRAG's database.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, LifoQueue
from typing import Any, TypeVar

import sqlite_vec

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import DatabaseError

logger = get_logger(__name__)

T = TypeVar("T")


class ConnectionPool:
    """Thread-safe connection pool for SQLite connections."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        db_path: Path | None = None,
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: float = 300,  # 5 minutes
        enable_vss: bool = True,
    ):
        """Initialize the connection pool.

        Args:
            settings: Configuration settings
            db_path: Database path (defaults to settings.database_path)
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections in the pool
            max_idle_time: Maximum idle time before closing a connection (seconds)
            enable_vss: Whether to enable VSS (Vector Similarity Search) support
        """
        self.settings = settings
        self.db_path = db_path or settings.database_path
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.enable_vss = enable_vss

        # Thread-safe pool management
        self._pool: LifoQueue[tuple[sqlite3.Connection, float]] = LifoQueue(
            maxsize=max_size
        )
        self._active_connections = 0
        self._total_connections = 0
        self._lock = threading.RLock()
        self._closed = False

        # Health check thread
        # Use shorter interval in CI to prevent pytest timeout issues
        import os

        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            self._health_check_interval = 10  # seconds (shorter for CI)
        else:
            self._health_check_interval = 60  # seconds (normal for local)
        self._health_check_thread: threading.Thread | None = None
        self._stop_health_check = threading.Event()

        # Initialize minimum connections
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the minimum number of connections in the pool."""
        with self._lock:
            for _ in range(self.min_size):
                try:
                    conn = self._create_connection()
                    self._pool.put((conn, time.time()))
                    self._total_connections += 1
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")

            # Start health check thread
            if (
                not self._health_check_thread
                or not self._health_check_thread.is_alive()
            ):
                self._health_check_thread = threading.Thread(
                    target=self._health_check_loop, daemon=True
                )
                self._health_check_thread.start()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper configuration.

        Returns:
            Configured SQLite connection
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.settings.database_timeout,
            check_same_thread=False,  # Allow multi-threading
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
        else:
            conn.execute("PRAGMA foreign_keys = OFF")

        # Enable JSON support
        conn.row_factory = sqlite3.Row

        # Load VSS extension if requested and supported
        if self.enable_vss and hasattr(conn, "enable_load_extension"):
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except (AttributeError, sqlite3.OperationalError) as e:
                logger.debug(f"SQLite VSS extension loading not available: {e}")

        return conn

    def acquire(self, timeout: float | None = None) -> sqlite3.Connection:
        """Acquire a connection from the pool.

        Args:
            timeout: Maximum time to wait for a connection (None = wait forever)

        Returns:
            Database connection

        Raises:
            DatabaseError: If the pool is closed or connection cannot be acquired
        """
        if self._closed:
            raise DatabaseError(
                message="Connection pool is closed",
                hint="The pool may have been shut down",
            )

        timeout = timeout or self.settings.database_timeout
        deadline = time.time() + timeout if timeout else None

        while True:
            with self._lock:
                # Try to get a connection from the pool
                try:
                    conn, _ = self._pool.get_nowait()
                    if self._is_connection_healthy(conn):
                        self._active_connections += 1
                        return conn
                    # Connection is dead, create a new one
                    self._total_connections -= 1
                    conn.close()
                except Empty:
                    pass

                # Create a new connection if we haven't reached the limit
                if self._total_connections < self.max_size:
                    try:
                        conn = self._create_connection()
                        self._total_connections += 1
                        self._active_connections += 1
                        return conn
                    except Exception as e:
                        raise DatabaseError(
                            message=f"Failed to create database connection: {e}",
                            hint="Check database path and permissions",
                            details={"db_path": str(self.db_path)},
                        ) from e

            # Check timeout
            if deadline and time.time() > deadline:
                raise DatabaseError(
                    message="Timeout waiting for database connection",
                    hint=f"All {self.max_size} connections are in use",
                    details={
                        "active": self._active_connections,
                        "total": self._total_connections,
                    },
                )

            # Wait a bit before retrying
            time.sleep(0.01)

    def release(self, conn: sqlite3.Connection) -> None:
        """Release a connection back to the pool.

        Args:
            conn: Connection to release
        """
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)

            if self._closed:
                conn.close()
                self._total_connections -= 1
                return

            # Check if connection is still healthy
            if not self._is_connection_healthy(conn):
                conn.close()
                self._total_connections -= 1
                return

            # Return to pool if there's space
            try:
                self._pool.put_nowait((conn, time.time()))
            except Exception:
                # Pool is full, close the connection
                conn.close()
                self._total_connections -= 1

    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """Check if a connection is still healthy.

        Args:
            conn: Connection to check

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            conn.execute("SELECT 1")
            return True
        except (sqlite3.Error, sqlite3.ProgrammingError):
            return False

    def _health_check_loop(self) -> None:
        """Background thread that performs periodic health checks."""
        while not self._stop_health_check.wait(self._health_check_interval):
            if self._closed:
                break

            with self._lock:
                # Check idle connections
                current_time = time.time()
                healthy_connections = []

                while not self._pool.empty():
                    try:
                        conn, last_used = self._pool.get_nowait()

                        # Close connections that have been idle too long
                        if current_time - last_used > self.max_idle_time:
                            conn.close()
                            self._total_connections -= 1
                            logger.debug("Closed idle connection")
                        elif self._is_connection_healthy(conn):
                            healthy_connections.append((conn, last_used))
                        else:
                            conn.close()
                            self._total_connections -= 1
                            logger.debug("Closed unhealthy connection")
                    except Empty:
                        break

                # Return healthy connections to pool
                for conn_tuple in healthy_connections:
                    try:
                        self._pool.put_nowait(conn_tuple)
                    except Exception:
                        conn_tuple[0].close()
                        self._total_connections -= 1

                # Ensure minimum connections
                while self._total_connections < self.min_size:
                    try:
                        conn = self._create_connection()
                        self._pool.put((conn, current_time))
                        self._total_connections += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to create connection during health check: {e}"
                        )
                        break

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            return {
                "total_connections": self._total_connections,
                "active_connections": self._active_connections,
                "idle_connections": self._pool.qsize(),
                "min_size": self.min_size,
                "max_size": self.max_size,
                "closed": self._closed,
            }

    def close(self, force: bool = False) -> None:
        """Close all connections in the pool.

        Args:
            force: If True, attempts to close even active connections (use with caution)
        """
        import platform

        with self._lock:
            if self._closed:
                return

            self._closed = True
            self._stop_health_check.set()

            # Wait for health check thread to stop to prevent hanging in pytest cleanup
            # This is critical for CI environments using --timeout-method=thread
            if self._health_check_thread and self._health_check_thread.is_alive():
                # Give the thread a brief moment to see the stop signal and exit cleanly
                self._health_check_thread.join(timeout=0.5)
                if self._health_check_thread.is_alive():
                    logger.warning("Health check thread did not stop within timeout")

            # Close all idle connections
            while not self._pool.empty():
                try:
                    conn, _ = self._pool.get_nowait()
                    conn.close()
                    self._total_connections -= 1
                except Empty:
                    break

            # If force is True and we're on Windows with active connections,
            # reset the counts (connections will be closed when garbage collected)
            if force and self._active_connections > 0:
                logger.warning(
                    "Forcefully closing connection pool with active connections",
                    active=self._active_connections,
                )
                self._active_connections = 0
                self._total_connections = 0

            # Windows needs extra time for file handle cleanup
            if platform.system() == "Windows":
                import gc
                import time

                gc.collect()  # Force garbage collection
                time.sleep(0.2)  # Increase wait time from 0.1 to 0.2

            logger.info("Connection pool closed")


class DatabaseConnectionManager:
    """Centralized database connection manager with pooling and lifecycle management."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        db_path: Path | None = None,
        pool_size: tuple[int, int] = (2, 10),
        enable_vss: bool = True,
    ):
        """Initialize the connection manager.

        Args:
            settings: Configuration settings
            db_path: Database path (defaults to settings.database_path)
            pool_size: Tuple of (min_connections, max_connections)
            enable_vss: Whether to enable VSS support
        """
        self.settings = settings
        self.db_path = db_path or settings.database_path
        self.enable_vss = enable_vss

        # Initialize connection pool
        self._pool = ConnectionPool(
            settings=settings,
            db_path=self.db_path,
            min_size=pool_size[0],
            max_size=pool_size[1],
            enable_vss=enable_vss,
        )

        # Thread-local storage for async context awareness
        self._thread_local = threading.local()

    def get_connection(self, timeout: float | None = None) -> sqlite3.Connection:
        """Get a database connection from the pool.

        Args:
            timeout: Maximum time to wait for a connection

        Returns:
            Database connection

        Raises:
            DatabaseError: If connection cannot be acquired
        """
        return self._pool.acquire(timeout)

    def release_connection(self, conn: sqlite3.Connection) -> None:
        """Release a connection back to the pool.

        Args:
            conn: Connection to release
        """
        self._pool.release(conn)

    @contextmanager
    def transaction(
        self, isolation_level: str | None = None
    ) -> Generator[sqlite3.Connection, None, None]:
        """Get a transactional database context.

        Args:
            isolation_level: Optional isolation level for the transaction

        Yields:
            Database connection within a transaction context
        """
        conn = self.get_connection()
        old_isolation = conn.isolation_level

        try:
            if isolation_level is not None:
                conn.isolation_level = isolation_level

            yield conn
            conn.commit()
            # Force a checkpoint in WAL mode to ensure data is visible
            if self.settings.database_journal_mode == "WAL":
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.isolation_level = old_isolation
            self.release_connection(conn)

    @contextmanager
    def readonly(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a read-only database context.

        Yields:
            Database connection in read-only mode
        """
        conn = self.get_connection()
        try:
            # Set to read-only mode using PRAGMA
            conn.execute("PRAGMA query_only = ON")
            yield conn
        finally:
            conn.execute("PRAGMA query_only = OFF")
            self.release_connection(conn)

    @contextmanager
    def batch_operation(
        self, batch_size: int = 1000
    ) -> Generator[sqlite3.Connection, None, None]:
        """Get a connection optimized for batch operations.

        Args:
            batch_size: Expected batch size for operations

        Yields:
            Database connection optimized for batch operations
        """
        conn = self.get_connection()
        try:
            # Optimize for batch operations
            conn.execute(f"PRAGMA cache_size = {batch_size * 2}")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA synchronous = OFF")
            yield conn
            conn.commit()
        finally:
            # Restore normal settings
            conn.execute(f"PRAGMA cache_size = {self.settings.database_cache_size}")
            conn.execute(f"PRAGMA temp_store = {self.settings.database_temp_store}")
            conn.execute(f"PRAGMA synchronous = {self.settings.database_synchronous}")
            self.release_connection(conn)

    def check_database_exists(self) -> bool:
        """Check if the database exists and is initialized.

        Returns:
            True if database exists and has schema, False otherwise
        """
        if not self.db_path.exists():
            return False

        try:
            with self.readonly() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='scripts'"
                )
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False

    def execute_query(
        self,
        query: str,
        params: tuple[Any, ...] | None = None,
        fetch_one: bool = False,
    ) -> list[sqlite3.Row] | sqlite3.Row | None:
        """Execute a query and return results.

        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_one: If True, return only the first row

        Returns:
            Query results
        """
        with self.readonly() as conn:
            cursor = conn.execute(query, params or ())
            if fetch_one:
                row: sqlite3.Row | None = cursor.fetchone()
                return row
            rows: list[sqlite3.Row] = list(cursor.fetchall())
            return rows

    def execute_write(self, query: str, params: tuple[Any, ...] | None = None) -> int:
        """Execute a write operation and return affected rows.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Number of affected rows
        """
        with self.transaction() as conn:
            cursor = conn.execute(query, params or ())
            return cursor.rowcount

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return self._pool.get_stats()

    def close(self, force: bool = False) -> None:
        """Close the connection manager and all connections.

        Args:
            force: If True, forcefully close even active connections
        """
        self._pool.close(force=force)

    def ensure_closed(self) -> bool:
        """Ensure all connections are truly closed (Windows-specific)."""
        return (
            self._pool._closed
            and self._pool._total_connections == 0
            and self._pool._active_connections == 0
        )

    def __enter__(self) -> DatabaseConnectionManager:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()


# Singleton instance for the application
_manager_instance: DatabaseConnectionManager | None = None
_manager_lock = threading.Lock()


def get_connection_manager(
    settings: ScriptRAGSettings | None = None,
    force_new: bool = False,
) -> DatabaseConnectionManager:
    """Get or create the singleton connection manager.

    Args:
        settings: Configuration settings (required for first call)
        force_new: Force creation of a new manager instance

    Returns:
        Connection manager instance

    Raises:
        ValueError: If settings not provided on first call
    """
    global _manager_instance

    # Get settings if not provided
    if settings is None:
        from scriptrag.config import get_settings

        settings = get_settings()

    # Check if we need to create a new manager
    needs_new_manager = (
        force_new
        or _manager_instance is None
        or _manager_instance.db_path != settings.database_path
        or _manager_instance.settings.database_foreign_keys
        != settings.database_foreign_keys
    )

    if needs_new_manager:
        with _manager_lock:
            # Double-check with lock held
            if (
                force_new
                or _manager_instance is None
                or _manager_instance.db_path != settings.database_path
                or _manager_instance.settings.database_foreign_keys
                != settings.database_foreign_keys
            ):
                if _manager_instance:
                    _manager_instance.close()

                _manager_instance = DatabaseConnectionManager(settings)

    if _manager_instance is None:
        # This should never happen, but satisfies type checker
        _manager_instance = DatabaseConnectionManager(settings)
    return _manager_instance


def close_connection_manager(force: bool = False) -> None:
    """Close the singleton connection manager.

    Args:
        force: If True, forcefully close even active connections
    """
    global _manager_instance

    with _manager_lock:
        if _manager_instance:
            _manager_instance.close(force=force)
            _manager_instance = None
