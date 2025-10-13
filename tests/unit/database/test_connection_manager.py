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
        assert "unhealthy_close_failures" in stats
        assert stats["unhealthy_close_failures"] == 0

        connection_pool.release(conn)

    def test_close_pool(self, connection_pool: ConnectionPool) -> None:
        """Test closing the connection pool."""
        conn = connection_pool.acquire()
        connection_pool.release(conn)

        connection_pool.close()
        assert connection_pool._closed

        stats = connection_pool.get_stats()
        assert stats["closed"]

    def test_unhealthy_connection_metrics_tracking(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test metrics tracking for unhealthy connection close failures."""
        from unittest.mock import MagicMock, patch

        # Initial metrics should be zero
        initial_stats = connection_pool.get_stats()
        assert initial_stats["unhealthy_close_failures"] == 0

        # Create a mock connection that fails to close
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.close.side_effect = sqlite3.Error("Close failed")

        # Put it in the pool
        connection_pool._pool.put((mock_conn, time.time()))
        connection_pool._total_connections += 1

        # Make mock connection appear unhealthy
        original_health_check = connection_pool._is_connection_healthy

        def health_check_wrapper(conn):
            if conn is mock_conn:
                return False
            return original_health_check(conn)

        with patch.object(
            connection_pool, "_is_connection_healthy", side_effect=health_check_wrapper
        ):
            # Try to acquire a connection - should encounter the unhealthy one
            conn = connection_pool.acquire()
            assert conn is not mock_conn  # Should get healthy connection
            connection_pool.release(conn)

        # Check that metrics were properly tracked
        final_stats = connection_pool.get_stats()
        assert final_stats["unhealthy_close_failures"] == 1

        # Verify mock connection had close attempted
        mock_conn.close.assert_called_once()

    def test_unhealthy_connection_release_metrics(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test metrics tracking when unhealthy connections are released."""
        from unittest.mock import MagicMock, patch

        # Get initial metrics
        initial_failures = connection_pool._unhealthy_close_failures

        # Create a mock connection
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.close.side_effect = sqlite3.Error("Close failed during release")

        # Make the mock connection appear unhealthy
        with patch.object(
            connection_pool, "_is_connection_healthy", return_value=False
        ):
            # Release the unhealthy connection
            connection_pool._active_connections = 1  # Simulate it was active
            connection_pool._total_connections = 2  # Simulate we have 2 connections
            connection_pool.release(mock_conn)

        # Verify metrics were updated
        assert connection_pool._unhealthy_close_failures == initial_failures + 1
        assert connection_pool._active_connections == 0
        assert connection_pool._total_connections == 1

        # Verify stats include the metric
        stats = connection_pool.get_stats()
        assert stats["unhealthy_close_failures"] == initial_failures + 1


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

    def test_unhealthy_connection_close_exception(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test pool state remains consistent when close raises exception."""
        from unittest.mock import MagicMock, patch

        # Get initial pool stats
        initial_total = connection_pool._total_connections

        # Create a mock connection that appears unhealthy and raises on close
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.close.side_effect = sqlite3.Error("Connection close failed")

        # Put the mock connection in the pool
        connection_pool._pool.put((mock_conn, time.time()))
        connection_pool._total_connections += 1

        # Mock _is_connection_healthy to return False for our mock connection
        with patch.object(
            connection_pool, "_is_connection_healthy", return_value=False
        ):
            # Try to get a connection - should handle gracefully
            conn = connection_pool.acquire()

            # Should get a new healthy connection
            assert conn is not mock_conn
            assert isinstance(conn, sqlite3.Connection)

            # Pool counter should be consistent
            # The unhealthy connection should have been removed from the count
            assert connection_pool._total_connections == initial_total + 1

            # Clean up
            connection_pool.release(conn)

    def test_unhealthy_connection_cleanup_with_multiple_failures(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test pool handles multiple unhealthy connections with close failures."""
        from unittest.mock import MagicMock, patch

        # Store initial connection count and the original method
        initial_total = connection_pool._total_connections
        original_health_check = connection_pool._is_connection_healthy
        initial_failures = connection_pool._unhealthy_close_failures

        # Create a mock connection that appears unhealthy and raises on close
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.close.side_effect = sqlite3.Error("Close failed")

        # Put the mock connection in the pool
        connection_pool._pool.put((mock_conn, time.time()))
        connection_pool._total_connections += 1

        # Create a counter for health checks
        health_checks = []

        def health_check_wrapper(conn):
            health_checks.append(conn)
            # Return False for our mock connection, True for real ones
            if conn is mock_conn:
                return False
            # Call the original method for real connections
            return original_health_check(conn)

        with patch.object(
            connection_pool, "_is_connection_healthy", side_effect=health_check_wrapper
        ):
            # Get a connection - should skip the unhealthy one and create new
            conn = connection_pool.acquire()

            # Should have checked the mock connection
            assert mock_conn in health_checks

            # Should get a real connection, not the mock
            assert conn is not mock_conn
            assert isinstance(conn, sqlite3.Connection)

            # Mock connection should have had close() called despite exception
            mock_conn.close.assert_called_once()

            # Pool counter should be consistent
            assert connection_pool._total_connections == initial_total + 1

            # Unhealthy close failure counter should have incremented
            assert connection_pool._unhealthy_close_failures == initial_failures + 1

            # Clean up
            connection_pool.release(conn)

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

    def test_close_with_connection_close_failures(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test pool close handles connection.close() failures gracefully."""
        from unittest.mock import MagicMock, patch

        # Create a pool
        pool = ConnectionPool(
            settings=settings,
            min_size=2,
            max_size=3,
            max_idle_time=1.0,
            enable_vss=False,
        )

        # Acquire and release connections to populate the pool
        conns = [pool.acquire() for _ in range(3)]
        for conn in conns:
            pool.release(conn)

        # Mock the pool's internal queue to return connections that fail to close
        mock_connections = []
        for _ in range(3):
            mock_conn = MagicMock(spec=sqlite3.Connection)
            mock_conn.close.side_effect = sqlite3.Error("Close failed")
            mock_connections.append((mock_conn, time.time()))

        # Replace pool contents with mock connections
        while not pool._pool.empty():
            try:
                pool._pool.get_nowait()
            except Exception:
                break

        for mock_conn_tuple in mock_connections:
            pool._pool.put(mock_conn_tuple)

        initial_total = pool._total_connections

        # Close the pool - should handle close failures gracefully
        with patch("scriptrag.database.connection_manager.logger") as mock_logger:
            pool.close()

            # Verify error logging occurred
            assert mock_logger.error.call_count == 3
            for call in mock_logger.error.call_args_list:
                assert "Failed to close connection during pool shutdown" in call[0][0]

            # Verify warning about failures
            mock_logger.warning.assert_any_call(
                "Failed to close 3 connections during shutdown"
            )

        # Verify pool state is consistent
        assert pool._closed
        assert pool._total_connections == 0  # All connections removed from tracking
        assert pool._pool.empty()

    def test_close_with_partial_connection_close_failures(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test pool close with some connections failing to close."""
        from unittest.mock import MagicMock, patch

        # Create a pool
        pool = ConnectionPool(
            settings=settings,
            min_size=2,
            max_size=4,
            max_idle_time=1.0,
            enable_vss=False,
        )

        # Acquire and release connections to populate the pool
        conns = [pool.acquire() for _ in range(4)]
        for conn in conns:
            pool.release(conn)

        # Clear the pool
        mock_connections = []
        while not pool._pool.empty():
            try:
                pool._pool.get_nowait()
            except Exception:
                break

        # Add mix of working and failing connections
        # Two that close successfully
        for _ in range(2):
            mock_conn = MagicMock(spec=sqlite3.Connection)
            mock_conn.close.return_value = None
            mock_connections.append((mock_conn, time.time()))
            pool._pool.put((mock_conn, time.time()))

        # Two that fail to close
        for i in range(2):
            mock_conn = MagicMock(spec=sqlite3.Connection)
            mock_conn.close.side_effect = sqlite3.Error(f"Close failed {i}")
            mock_connections.append((mock_conn, time.time()))
            pool._pool.put((mock_conn, time.time()))

        # Close the pool
        with patch("scriptrag.database.connection_manager.logger") as mock_logger:
            pool.close()

            # Verify we logged 2 errors and 1 warning
            assert mock_logger.error.call_count == 2
            mock_logger.warning.assert_any_call(
                "Failed to close 2 connections during shutdown"
            )

        # Verify pool state is consistent
        assert pool._closed
        assert pool._total_connections == 0
        assert pool._pool.empty()

        # Verify all connections had close() called
        for mock_conn, _ in mock_connections:
            mock_conn.close.assert_called_once()
