"""Unit tests for database connection manager."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection_manager import (
    ConnectionPool,
    DatabaseConnectionManager,
    close_connection_manager,
    get_connection_manager,
)
from scriptrag.exceptions import DatabaseError


@pytest.fixture
def settings(tmp_path: Path) -> ScriptRAGSettings:
    """Create test settings."""
    return ScriptRAGSettings(
        database_path=tmp_path / "test.db",
        database_timeout=1.0,
        database_journal_mode="WAL",
        database_synchronous="NORMAL",
        database_cache_size=-2000,
        database_temp_store="MEMORY",
        database_foreign_keys=True,
    )


@pytest.fixture
def connection_pool(settings: ScriptRAGSettings) -> ConnectionPool:
    """Create a test connection pool."""
    pool = ConnectionPool(
        settings=settings,
        min_size=1,
        max_size=3,
        max_idle_time=1.0,
        enable_vss=False,
    )
    yield pool
    pool.close(force=True)


@pytest.fixture
def connection_manager(settings: ScriptRAGSettings) -> DatabaseConnectionManager:
    """Create a test connection manager."""
    manager = DatabaseConnectionManager(
        settings=settings,
        pool_size=(1, 3),
        enable_vss=False,
    )
    yield manager
    manager.close(force=True)


class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_initialization(self, connection_pool: ConnectionPool) -> None:
        """Test pool initialization."""
        assert connection_pool.min_size == 1
        assert connection_pool.max_size == 3
        assert connection_pool._total_connections >= 1
        assert not connection_pool._closed

    def test_acquire_connection(self, connection_pool: ConnectionPool) -> None:
        """Test acquiring a connection from the pool."""
        conn = connection_pool.acquire()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        assert connection_pool._active_connections == 1
        connection_pool.release(conn)

    def test_release_connection(self, connection_pool: ConnectionPool) -> None:
        """Test releasing a connection back to the pool."""
        conn = connection_pool.acquire()
        initial_active = connection_pool._active_connections
        connection_pool.release(conn)
        assert connection_pool._active_connections == initial_active - 1

    def test_max_connections_limit(self, connection_pool: ConnectionPool) -> None:
        """Test that pool respects max connections limit."""
        connections = []
        for _ in range(connection_pool.max_size):
            connections.append(connection_pool.acquire())

        assert connection_pool._active_connections == connection_pool.max_size
        assert connection_pool._total_connections == connection_pool.max_size

        # Release all connections
        for conn in connections:
            connection_pool.release(conn)

    def test_acquire_timeout(self, connection_pool: ConnectionPool) -> None:
        """Test timeout when all connections are in use."""
        # Acquire all connections
        connections = []
        for _ in range(connection_pool.max_size):
            connections.append(connection_pool.acquire())

        # Try to acquire one more with a short timeout
        with pytest.raises(DatabaseError) as exc_info:
            connection_pool.acquire(timeout=0.1)

        assert "Timeout waiting for database connection" in str(exc_info.value)

        # Release all connections
        for conn in connections:
            connection_pool.release(conn)

    def test_closed_pool_acquire(self, connection_pool: ConnectionPool) -> None:
        """Test acquiring from a closed pool raises error."""
        connection_pool.close()

        with pytest.raises(DatabaseError) as exc_info:
            connection_pool.acquire()

        assert "Connection pool is closed" in str(exc_info.value)

    def test_connection_health_check(self, connection_pool: ConnectionPool) -> None:
        """Test connection health checking."""
        conn = connection_pool.acquire()
        assert connection_pool._is_connection_healthy(conn)

        # Close the connection to make it unhealthy
        conn.close()
        assert not connection_pool._is_connection_healthy(conn)

    def test_get_stats(self, connection_pool: ConnectionPool) -> None:
        """Test getting pool statistics."""
        conn = connection_pool.acquire()
        stats = connection_pool.get_stats()

        assert stats["total_connections"] >= 1
        assert stats["active_connections"] == 1
        assert stats["min_size"] == 1
        assert stats["max_size"] == 3
        assert not stats["closed"]

        connection_pool.release(conn)

    def test_close_pool(self, connection_pool: ConnectionPool) -> None:
        """Test closing the connection pool."""
        conn = connection_pool.acquire()
        connection_pool.release(conn)

        connection_pool.close()
        assert connection_pool._closed

        stats = connection_pool.get_stats()
        assert stats["closed"]


class TestDatabaseConnectionManager:
    """Test DatabaseConnectionManager class."""

    def test_initialization(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test manager initialization."""
        assert connection_manager.db_path.name == "test.db"
        assert connection_manager._pool is not None

    def test_get_connection(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test getting a connection."""
        conn = connection_manager.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        connection_manager.release_connection(conn)

    def test_transaction_context(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test transaction context manager."""
        with connection_manager.transaction() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO test (id) VALUES (1)")

        # Verify the transaction was committed
        result = connection_manager.execute_query("SELECT COUNT(*) FROM test")
        assert result[0][0] == 1

    def test_transaction_rollback(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test transaction rollback on error."""
        # Create table first
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        try:
            with connection_manager.transaction() as conn:
                conn.execute("INSERT INTO test (id) VALUES (1)")
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify the transaction was rolled back
        result = connection_manager.execute_query("SELECT COUNT(*) FROM test")
        assert result[0][0] == 0

    def test_readonly_context(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test read-only context manager."""
        # Create a table first
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        with connection_manager.readonly() as conn:
            # Reading should work
            conn.execute("SELECT * FROM test")

            # Writing should fail
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("INSERT INTO test (id) VALUES (1)")

    def test_readonly_context_exception_handling(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test readonly context handles exceptions and releases connections."""
        # Create a table first
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        # Get initial pool stats
        initial_stats = connection_manager.get_pool_stats()
        initial_active = initial_stats["active_connections"]

        # Test that exception in the context is properly handled
        with pytest.raises(ValueError):
            with connection_manager.readonly() as conn:
                # Verify we're in readonly mode
                conn.execute("SELECT * FROM test")
                # Raise an exception
                raise ValueError("Test exception")

        # Verify connection was released back to pool
        after_stats = connection_manager.get_pool_stats()
        assert after_stats["active_connections"] == initial_active

        # Verify we can still get a connection (pool not exhausted)
        with connection_manager.readonly() as conn:
            result = conn.execute("SELECT * FROM test").fetchall()
            assert result == []

    def test_readonly_context_query_only_reset(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test that query_only pragma is properly reset even after exceptions."""
        # Create a table first
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        # Force an exception in readonly context
        try:
            with connection_manager.readonly() as conn:
                # This will succeed (read operation)
                conn.execute("SELECT * FROM test")
                # Force an exception
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Get the same connection again and verify it's not stuck in readonly mode
        conn = connection_manager.get_connection()
        try:
            # This should succeed if query_only was properly reset
            conn.execute("INSERT INTO test (id) VALUES (1)")
            conn.commit()

            # Verify the insert worked
            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 1
        finally:
            connection_manager.release_connection(conn)

    def test_readonly_context_nested_exceptions(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test that nested finally blocks in readonly context work correctly."""
        # Create a table first
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        # Track pool state
        initial_stats = connection_manager.get_pool_stats()

        # Test multiple exceptions and ensure proper cleanup
        exceptions = [ValueError, TypeError, RuntimeError]
        messages = ["First exception", "Second exception", "Third exception"]

        for exc_type, msg in zip(exceptions, messages, strict=False):
            with pytest.raises(exc_type):
                with connection_manager.readonly() as conn:
                    conn.execute("SELECT * FROM test")
                    raise exc_type(msg)

        # Verify pool is still healthy
        final_stats = connection_manager.get_pool_stats()
        assert final_stats["active_connections"] == initial_stats["active_connections"]

        # Verify we can still use the connection manager normally
        with connection_manager.transaction() as conn:
            conn.execute("INSERT INTO test (id) VALUES (99)")

        result = connection_manager.execute_query("SELECT COUNT(*) FROM test")
        assert result[0][0] == 1

    def test_batch_operation_context(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test batch operation context manager."""
        with connection_manager.batch_operation(batch_size=100) as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            for i in range(100):
                conn.execute("INSERT INTO test (id) VALUES (?)", (i,))

        # Verify all inserts were committed
        result = connection_manager.execute_query("SELECT COUNT(*) FROM test")
        assert result[0][0] == 100

    def test_check_database_exists(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test checking if database exists."""
        # Initially should not exist
        assert not connection_manager.check_database_exists()

        # Create the scripts table
        connection_manager.execute_write(
            "CREATE TABLE scripts (id INTEGER PRIMARY KEY)"
        )

        # Now should exist
        assert connection_manager.check_database_exists()

    def test_execute_query(self, connection_manager: DatabaseConnectionManager) -> None:
        """Test executing queries."""
        connection_manager.execute_write("CREATE TABLE test (id INTEGER, value TEXT)")
        connection_manager.execute_write(
            "INSERT INTO test VALUES (1, 'one'), (2, 'two')"
        )

        # Test fetch all
        results = connection_manager.execute_query("SELECT * FROM test ORDER BY id")
        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["value"] == "one"

        # Test fetch one
        result = connection_manager.execute_query(
            "SELECT * FROM test WHERE id = ?", (2,), fetch_one=True
        )
        assert result["id"] == 2
        assert result["value"] == "two"

    def test_execute_write(self, connection_manager: DatabaseConnectionManager) -> None:
        """Test executing write operations."""
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        # Insert and check rowcount
        rowcount = connection_manager.execute_write(
            "INSERT INTO test (id) VALUES (1), (2), (3)"
        )
        assert rowcount == 3

        # Update and check rowcount
        rowcount = connection_manager.execute_write(
            "UPDATE test SET id = id + 10 WHERE id > 1"
        )
        assert rowcount == 2

    def test_get_pool_stats(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test getting pool statistics."""
        stats = connection_manager.get_pool_stats()
        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "min_size" in stats
        assert "max_size" in stats

    def test_ensure_closed_when_pool_not_closed(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test ensure_closed returns False when pool is not closed."""
        # Get a connection and release it
        conn = connection_manager.get_connection()
        connection_manager.release_connection(conn)

        # Should return False because pool is not closed
        # (even with no active connections)
        assert not connection_manager.ensure_closed()

    def test_ensure_closed_after_close(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test ensure_closed returns True after closing."""
        # Get and release a connection
        conn = connection_manager.get_connection()
        connection_manager.release_connection(conn)

        # Close the manager
        connection_manager.close()

        # Should return True because pool is closed and no connections
        assert connection_manager.ensure_closed()

    def test_ensure_closed_with_force_close(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test ensure_closed after force closing with active connections."""
        # Get a connection and keep it active
        conn = connection_manager.get_connection()

        # Force close the manager
        connection_manager.close(force=True)

        # Should return True because pool is closed and counts are reset
        assert connection_manager.ensure_closed()

    def test_context_manager(self, settings: ScriptRAGSettings) -> None:
        """Test using manager as context manager."""
        with DatabaseConnectionManager(settings, pool_size=(1, 2)) as manager:
            conn = manager.get_connection()
            assert conn is not None
            manager.release_connection(conn)

        # Manager should be closed after exiting context
        assert manager._pool._closed


class TestSingletonManager:
    """Test singleton connection manager functions."""

    def test_get_connection_manager_singleton(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test that get_connection_manager returns singleton."""
        manager1 = get_connection_manager(settings)
        manager2 = get_connection_manager(settings)  # Pass same settings

        assert manager1 is manager2

        close_connection_manager()

    def test_force_new_manager(
        self, settings: ScriptRAGSettings, tmp_path: Path
    ) -> None:
        """Test forcing creation of new manager."""
        manager1 = get_connection_manager(settings)

        # Force new manager
        manager2 = get_connection_manager(settings, force_new=True)

        assert manager1 is not manager2

        close_connection_manager()

    def test_different_db_path_creates_new_manager(
        self, settings: ScriptRAGSettings, tmp_path: Path
    ) -> None:
        """Test that different db_path creates new manager."""
        manager1 = get_connection_manager(settings)

        # Change database path
        settings.database_path = tmp_path / "other.db"
        manager2 = get_connection_manager(settings)

        assert manager1 is not manager2

        close_connection_manager()

    def test_close_connection_manager(self, settings: ScriptRAGSettings) -> None:
        """Test closing the singleton manager."""
        manager = get_connection_manager(settings)
        assert not manager._pool._closed

        close_connection_manager()

        # The manager should be closed
        assert manager._pool._closed


class TestThreadSafety:
    """Test thread safety of connection pool and manager."""

    def test_concurrent_acquire_release(self, connection_pool: ConnectionPool) -> None:
        """Test concurrent connection acquisition and release."""
        results = []
        errors = []

        def worker():
            try:
                for _ in range(5):
                    conn = connection_pool.acquire()
                    time.sleep(0.01)  # Simulate work
                    connection_pool.release(conn)
                results.append("success")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5

    def test_concurrent_transactions(
        self, connection_manager: DatabaseConnectionManager
    ) -> None:
        """Test concurrent transactions."""
        connection_manager.execute_write("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        def worker(worker_id: int):
            with connection_manager.transaction() as conn:
                conn.execute("INSERT INTO test (id) VALUES (?)", (worker_id,))
                time.sleep(0.01)  # Simulate work

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All inserts should have succeeded
        result = connection_manager.execute_query("SELECT COUNT(*) FROM test")
        assert result[0][0] == 5
