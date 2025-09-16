"""Comprehensive tests for connection_manager.py to achieve 99% coverage."""

import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection_manager import (
    ConnectionManager,
    ConnectionPool,
    ThreadLocalConnectionManager,
)
from scriptrag.exceptions import DatabaseError


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def settings(temp_db):
    """Create test settings."""
    return ScriptRAGSettings(
        database_path=temp_db, database_pool_size=5, database_timeout=30.0
    )


@pytest.fixture
def connection_pool(settings):
    """Create connection pool."""
    return ConnectionPool(settings)


@pytest.fixture
def connection_manager(settings):
    """Create connection manager."""
    return ConnectionManager(settings)


class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_init(self, settings):
        """Test initialization."""
        pool = ConnectionPool(settings, min_size=2, max_size=10)
        assert pool.settings == settings
        assert pool.min_size == 2
        assert pool.max_size == 10
        assert pool._connections.maxsize == 10

    def test_create_connection(self, connection_pool):
        """Test creating a connection."""
        conn = connection_pool._create_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_create_connection_with_vss(self, settings):
        """Test creating connection with VSS enabled."""
        pool = ConnectionPool(settings, enable_vss=True)

        with patch("sqlite_vec.load_extension") as mock_load:
            conn = pool._create_connection()
            mock_load.assert_called_once()
            conn.close()

    def test_create_connection_vss_failure(self, settings):
        """Test VSS loading failure handling."""
        pool = ConnectionPool(settings, enable_vss=True)

        with patch("sqlite_vec.load_extension", side_effect=Exception("VSS error")):
            with patch.object(pool, "logger") as mock_logger:
                conn = pool._create_connection()
                mock_logger.warning.assert_called()
                conn.close()

    def test_get_connection(self, connection_pool):
        """Test getting a connection from pool."""
        with connection_pool.get_connection() as conn:
            assert conn is not None
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_get_connection_creates_new(self, connection_pool):
        """Test getting connection creates new when pool empty."""
        assert connection_pool._connections.qsize() == 0

        with connection_pool.get_connection() as conn:
            assert conn is not None

        # Connection should be returned to pool
        assert connection_pool._connections.qsize() == 1

    def test_get_connection_reuses(self, connection_pool):
        """Test connection reuse."""
        # First use
        with connection_pool.get_connection() as conn1:
            conn1.execute("CREATE TABLE test (id INTEGER)")

        # Second use should get same connection
        with connection_pool.get_connection() as conn2:
            cursor = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "test" in tables

    def test_get_connection_max_pool(self, settings):
        """Test max pool size enforcement."""
        pool = ConnectionPool(settings, max_size=2)

        # Get two connections
        ctx1 = pool.get_connection()
        conn1 = ctx1.__enter__()

        ctx2 = pool.get_connection()
        conn2 = ctx2.__enter__()

        # Pool should be at max
        assert pool._active_connections == 2

        # Cleanup
        ctx1.__exit__(None, None, None)
        ctx2.__exit__(None, None, None)

    def test_validate_connection_healthy(self, connection_pool):
        """Test validating healthy connection."""
        conn = connection_pool._create_connection()
        assert connection_pool._validate_connection(conn)
        conn.close()

    def test_validate_connection_closed(self, connection_pool):
        """Test validating closed connection."""
        conn = connection_pool._create_connection()
        conn.close()
        assert not connection_pool._validate_connection(conn)

    def test_validate_connection_error(self, connection_pool):
        """Test validating connection with error."""
        conn = Mock()
        conn.execute.side_effect = sqlite3.Error("Connection error")
        assert not connection_pool._validate_connection(conn)

    def test_close_connection_safely(self, connection_pool):
        """Test safe connection closing."""
        conn = connection_pool._create_connection()
        connection_pool._close_connection_safely(conn)

        # Should handle double close
        connection_pool._close_connection_safely(conn)

    def test_close_connection_safely_with_error(self, connection_pool):
        """Test closing connection with error."""
        conn = Mock()
        conn.close.side_effect = Exception("Close error")

        with patch.object(connection_pool, "logger") as mock_logger:
            connection_pool._close_connection_safely(conn)
            mock_logger.error.assert_called()

    def test_cleanup_idle_connections(self, settings):
        """Test cleaning up idle connections."""
        pool = ConnectionPool(settings, max_idle_time=0.1)

        # Add connection to pool
        conn = pool._create_connection()
        pool._connections.put((time.time() - 1, conn))
        pool._idle_connections[id(conn)] = time.time() - 1

        # Run cleanup
        closed = pool.cleanup_idle_connections()
        assert closed == 1
        assert pool._connections.qsize() == 0

    def test_close(self, connection_pool):
        """Test closing pool."""
        # Add some connections
        with connection_pool.get_connection():
            pass

        assert connection_pool._connections.qsize() > 0

        # Close pool
        connection_pool.close()
        assert connection_pool._connections.qsize() == 0
        assert connection_pool._closed

    def test_close_unhealthy_connections(self, connection_pool):
        """Test closing unhealthy connections."""
        # Create healthy and unhealthy connections
        healthy = connection_pool._create_connection()
        unhealthy = connection_pool._create_connection()
        unhealthy.close()  # Make it unhealthy

        # Add to pool
        connection_pool._connections.put((time.time(), healthy))
        connection_pool._connections.put((time.time(), unhealthy))

        # Close unhealthy
        closed = connection_pool.close_unhealthy_connections()
        assert closed == 1
        assert connection_pool._connections.qsize() == 1

        # Cleanup
        healthy.close()

    def test_context_manager_error_handling(self, connection_pool):
        """Test context manager error handling."""
        with pytest.raises(ValueError):
            with connection_pool.get_connection() as conn:
                raise ValueError("Test error")

        # Pool should still be functional
        with connection_pool.get_connection() as conn:
            assert conn is not None

    def test_get_stats(self, connection_pool):
        """Test getting pool statistics."""
        with connection_pool.get_connection():
            stats = connection_pool.get_stats()

        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "idle_connections" in stats
        assert "connections_created" in stats
        assert "connections_closed" in stats
        assert "unhealthy_closed" in stats

    def test_thread_safety(self, connection_pool):
        """Test thread safety of connection pool."""
        results = []

        def worker():
            with connection_pool.get_connection() as conn:
                cursor = conn.execute("SELECT 1")
                results.append(cursor.fetchone()[0])

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r == 1 for r in results)


class TestConnectionManager:
    """Test ConnectionManager class."""

    def test_init(self, settings):
        """Test initialization."""
        manager = ConnectionManager(settings)
        assert manager.settings == settings
        assert manager._pool is not None
        assert not manager._closed

    def test_get_connection(self, connection_manager):
        """Test getting connection."""
        with connection_manager.get_connection() as conn:
            assert conn is not None
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_execute(self, connection_manager):
        """Test executing query."""
        connection_manager.execute("CREATE TABLE test (id INTEGER)")
        connection_manager.execute("INSERT INTO test VALUES (1)")

        cursor = connection_manager.execute("SELECT * FROM test")
        result = cursor.fetchone()
        assert result[0] == 1

    def test_execute_with_params(self, connection_manager):
        """Test executing query with parameters."""
        connection_manager.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        connection_manager.execute("INSERT INTO test VALUES (?, ?)", (1, "test"))

        cursor = connection_manager.execute("SELECT * FROM test WHERE id = ?", (1,))
        result = cursor.fetchone()
        assert result[0] == 1
        assert result[1] == "test"

    def test_executemany(self, connection_manager):
        """Test executing many queries."""
        connection_manager.execute("CREATE TABLE test (id INTEGER)")

        data = [(1,), (2,), (3,)]
        connection_manager.executemany("INSERT INTO test VALUES (?)", data)

        cursor = connection_manager.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 3

    def test_transaction_commit(self, connection_manager):
        """Test transaction commit."""
        connection_manager.execute("CREATE TABLE test (id INTEGER)")

        with connection_manager.transaction():
            connection_manager.execute("INSERT INTO test VALUES (1)")

        cursor = connection_manager.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 1

    def test_transaction_rollback(self, connection_manager):
        """Test transaction rollback."""
        connection_manager.execute("CREATE TABLE test (id INTEGER)")

        try:
            with connection_manager.transaction():
                connection_manager.execute("INSERT INTO test VALUES (1)")
                raise ValueError("Force rollback")
        except ValueError:
            pass

        cursor = connection_manager.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 0

    def test_close(self, connection_manager):
        """Test closing manager."""
        connection_manager.execute("SELECT 1")
        connection_manager.close()

        assert connection_manager._closed

        # Should handle double close
        connection_manager.close()

    def test_cleanup_on_del(self, settings):
        """Test cleanup on deletion."""
        manager = ConnectionManager(settings)
        pool = manager._pool

        with patch.object(pool, "close") as mock_close:
            del manager
            mock_close.assert_called_once()

    def test_error_handling(self, connection_manager):
        """Test error handling."""
        with pytest.raises(DatabaseError):
            connection_manager.execute("INVALID SQL")


class TestThreadLocalConnectionManager:
    """Test ThreadLocalConnectionManager class."""

    def test_init(self, settings):
        """Test initialization."""
        manager = ThreadLocalConnectionManager(settings)
        assert manager.settings == settings
        assert hasattr(manager._local, "__dict__")

    def test_get_connection_thread_local(self, settings):
        """Test thread-local connections."""
        manager = ThreadLocalConnectionManager(settings)

        # Get connection in main thread
        conn1 = manager.get_connection()
        conn2 = manager.get_connection()
        assert conn1 is conn2

        # Different connection in different thread
        conn_in_thread = []

        def worker():
            conn_in_thread.append(manager.get_connection())

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        assert conn_in_thread[0] is not conn1

    def test_execute(self, settings):
        """Test executing queries."""
        manager = ThreadLocalConnectionManager(settings)

        manager.execute("CREATE TABLE test (id INTEGER)")
        manager.execute("INSERT INTO test VALUES (1)")

        cursor = manager.execute("SELECT * FROM test")
        assert cursor.fetchone()[0] == 1

    def test_close(self, settings):
        """Test closing connections."""
        manager = ThreadLocalConnectionManager(settings)

        conn = manager.get_connection()
        manager.close()

        # Should get new connection after close
        new_conn = manager.get_connection()
        assert new_conn is not conn

    def test_close_all(self, settings):
        """Test closing all connections."""
        manager = ThreadLocalConnectionManager(settings)

        # Create connections in multiple threads
        connections = []

        def worker():
            conn = manager.get_connection()
            connections.append(conn)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Close all
        with patch.object(manager, "_close_connection") as mock_close:
            manager.close_all()
            assert mock_close.call_count >= len(connections)
