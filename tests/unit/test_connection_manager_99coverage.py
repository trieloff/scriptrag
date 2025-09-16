"""Comprehensive tests for connection_manager.py to achieve 99% coverage."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from scriptrag.database.connection_manager import (
    ConnectionManager,
    ConnectionPool,
    ConnectionPoolExhausted,
    DatabaseConfig,
    DatabaseError,
    HealthCheck,
    MetricsCollector,
)


@pytest.fixture
def db_config():
    """Create test database config."""
    return DatabaseConfig(
        path=":memory:", pool_size=5, timeout=30.0, check_interval=60, max_retries=3
    )


@pytest.fixture
def connection_manager(db_config):
    """Create connection manager instance."""
    return ConnectionManager(db_config)


@pytest.fixture
def metrics_collector():
    """Create metrics collector."""
    return MetricsCollector()


class TestConnectionManager:
    """Test ConnectionManager class."""

    def test_init(self, db_config):
        """Test initialization."""
        manager = ConnectionManager(db_config)
        assert manager.config == db_config
        assert manager.pool is not None
        assert manager.metrics is not None
        assert manager.health_check is not None

    @pytest.mark.asyncio
    async def test_connect(self, connection_manager):
        """Test connect method."""
        await connection_manager.connect()
        assert connection_manager.is_connected

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager):
        """Test disconnect method."""
        await connection_manager.connect()
        await connection_manager.disconnect()
        assert not connection_manager.is_connected

    @pytest.mark.asyncio
    async def test_execute(self, connection_manager):
        """Test execute method."""
        await connection_manager.connect()
        result = await connection_manager.execute("SELECT 1 as value")
        assert result[0]["value"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_params(self, connection_manager):
        """Test execute with parameters."""
        await connection_manager.connect()
        await connection_manager.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        await connection_manager.execute("INSERT INTO test VALUES (?, ?)", (1, "test"))
        result = await connection_manager.execute(
            "SELECT * FROM test WHERE id = ?", (1,)
        )
        assert result[0]["id"] == 1
        assert result[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_execute_many(self, connection_manager):
        """Test execute_many method."""
        await connection_manager.connect()
        await connection_manager.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        data = [(1, "a"), (2, "b"), (3, "c")]
        await connection_manager.execute_many("INSERT INTO test VALUES (?, ?)", data)
        result = await connection_manager.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 3

    @pytest.mark.asyncio
    async def test_transaction(self, connection_manager):
        """Test transaction context manager."""
        await connection_manager.connect()
        await connection_manager.execute("CREATE TABLE test (id INTEGER)")

        async with connection_manager.transaction():
            await connection_manager.execute("INSERT INTO test VALUES (1)")

        result = await connection_manager.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 1

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, connection_manager):
        """Test transaction rollback on error."""
        await connection_manager.connect()
        await connection_manager.execute("CREATE TABLE test (id INTEGER UNIQUE)")

        with pytest.raises(DatabaseError):
            async with connection_manager.transaction():
                await connection_manager.execute("INSERT INTO test VALUES (1)")
                await connection_manager.execute(
                    "INSERT INTO test VALUES (1)"  # Duplicate
                )

        result = await connection_manager.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 0

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, connection_manager):
        """Test health check when healthy."""
        await connection_manager.connect()
        health = await connection_manager.check_health()
        assert health["status"] == "healthy"
        assert health["connections"]["active"] >= 0
        assert health["connections"]["idle"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, connection_manager):
        """Test health check when unhealthy."""
        # Don't connect - should be unhealthy
        health = await connection_manager.check_health()
        assert health["status"] == "unhealthy"

    def test_get_metrics(self, connection_manager):
        """Test get_metrics method."""
        metrics = connection_manager.get_metrics()
        assert "queries_executed" in metrics
        assert "errors" in metrics
        assert "connections_created" in metrics
        assert "connections_closed" in metrics

    @pytest.mark.asyncio
    async def test_connection_retry(self, connection_manager):
        """Test connection retry logic."""
        with patch.object(
            connection_manager.pool,
            "acquire",
            side_effect=[ConnectionPoolExhausted(), Mock()],
        ):
            await connection_manager.connect()
            assert connection_manager.is_connected

    @pytest.mark.asyncio
    async def test_connection_timeout(self, db_config):
        """Test connection timeout."""
        db_config.timeout = 0.01
        manager = ConnectionManager(db_config)

        with patch.object(manager.pool, "acquire", side_effect=TimeoutError()):
            with pytest.raises(DatabaseError):
                await manager.connect()

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, connection_manager):
        """Test concurrent query execution."""
        await connection_manager.connect()
        await connection_manager.execute("CREATE TABLE test (id INTEGER)")

        async def insert_value(val):
            await connection_manager.execute("INSERT INTO test VALUES (?)", (val,))

        await asyncio.gather(*[insert_value(i) for i in range(10)])

        result = await connection_manager.execute("SELECT COUNT(*) as count FROM test")
        assert result[0]["count"] == 10

    @pytest.mark.asyncio
    async def test_close_unhealthy_connections(self, connection_manager):
        """Test closing unhealthy connections."""
        await connection_manager.connect()

        # Mock unhealthy connection
        mock_conn = Mock()
        mock_conn.ping.side_effect = Exception("Connection dead")

        with patch.object(connection_manager.pool, "connections", [mock_conn]):
            closed = await connection_manager.close_unhealthy_connections()
            assert closed == 1
            assert connection_manager.metrics.unhealthy_connections_closed == 1


class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_init(self, db_config):
        """Test pool initialization."""
        pool = ConnectionPool(db_config)
        assert pool.config == db_config
        assert pool.size == db_config.pool_size
        assert len(pool.available) == 0
        assert len(pool.in_use) == 0

    @pytest.mark.asyncio
    async def test_acquire(self, db_config):
        """Test acquiring connection."""
        pool = ConnectionPool(db_config)
        conn = await pool.acquire()
        assert conn is not None
        assert len(pool.in_use) == 1

    @pytest.mark.asyncio
    async def test_release(self, db_config):
        """Test releasing connection."""
        pool = ConnectionPool(db_config)
        conn = await pool.acquire()
        await pool.release(conn)
        assert len(pool.in_use) == 0
        assert len(pool.available) == 1

    @pytest.mark.asyncio
    async def test_pool_exhaustion(self, db_config):
        """Test pool exhaustion."""
        db_config.pool_size = 2
        pool = ConnectionPool(db_config)

        conn1 = await pool.acquire()
        conn2 = await pool.acquire()

        with pytest.raises(ConnectionPoolExhausted):
            await pool.acquire_nowait()

    @pytest.mark.asyncio
    async def test_connection_reuse(self, db_config):
        """Test connection reuse."""
        pool = ConnectionPool(db_config)

        conn1 = await pool.acquire()
        conn1_id = id(conn1)
        await pool.release(conn1)

        conn2 = await pool.acquire()
        conn2_id = id(conn2)

        assert conn1_id == conn2_id

    @pytest.mark.asyncio
    async def test_close_all(self, db_config):
        """Test closing all connections."""
        pool = ConnectionPool(db_config)

        conn1 = await pool.acquire()
        conn2 = await pool.acquire()
        await pool.release(conn1)

        await pool.close_all()
        assert len(pool.available) == 0
        assert len(pool.in_use) == 0


class TestHealthCheck:
    """Test HealthCheck class."""

    @pytest.mark.asyncio
    async def test_healthy_check(self, connection_manager):
        """Test healthy status check."""
        await connection_manager.connect()
        health = HealthCheck(connection_manager)

        status = await health.check()
        assert status["status"] == "healthy"
        assert status["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_unhealthy_check(self, connection_manager):
        """Test unhealthy status check."""
        health = HealthCheck(connection_manager)

        with patch.object(
            connection_manager, "execute", side_effect=Exception("Database error")
        ):
            status = await health.check()
            assert status["status"] == "unhealthy"
            assert "error" in status

    @pytest.mark.asyncio
    async def test_periodic_check(self, connection_manager):
        """Test periodic health checking."""
        await connection_manager.connect()
        health = HealthCheck(connection_manager, check_interval=0.1)

        await health.start()
        await asyncio.sleep(0.3)
        await health.stop()

        assert health.check_count > 2


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_init(self):
        """Test initialization."""
        metrics = MetricsCollector()
        assert metrics.queries_executed == 0
        assert metrics.errors == 0
        assert metrics.connections_created == 0
        assert metrics.connections_closed == 0
        assert metrics.unhealthy_connections_closed == 0

    def test_increment_queries(self, metrics_collector):
        """Test incrementing query counter."""
        metrics_collector.increment_queries()
        assert metrics_collector.queries_executed == 1

        metrics_collector.increment_queries(5)
        assert metrics_collector.queries_executed == 6

    def test_increment_errors(self, metrics_collector):
        """Test incrementing error counter."""
        metrics_collector.increment_errors()
        assert metrics_collector.errors == 1

    def test_record_query_time(self, metrics_collector):
        """Test recording query time."""
        metrics_collector.record_query_time(0.5)
        metrics_collector.record_query_time(1.5)

        stats = metrics_collector.get_stats()
        assert stats["avg_query_time"] == 1.0
        assert stats["total_query_time"] == 2.0

    def test_get_stats(self, metrics_collector):
        """Test getting statistics."""
        metrics_collector.increment_queries(10)
        metrics_collector.increment_errors(2)
        metrics_collector.record_query_time(0.1)

        stats = metrics_collector.get_stats()
        assert stats["queries_executed"] == 10
        assert stats["errors"] == 2
        assert stats["error_rate"] == 0.2
        assert stats["avg_query_time"] == 0.1

    def test_reset(self, metrics_collector):
        """Test resetting metrics."""
        metrics_collector.increment_queries(10)
        metrics_collector.reset()

        assert metrics_collector.queries_executed == 0
        assert metrics_collector.get_stats()["queries_executed"] == 0


class TestDatabaseConfig:
    """Test DatabaseConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = DatabaseConfig()
        assert config.path == "scriptrag.db"
        assert config.pool_size == 10
        assert config.timeout == 30.0
        assert config.check_interval == 60
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = DatabaseConfig(
            path="/tmp/test.db",
            pool_size=20,
            timeout=60.0,
            check_interval=30,
            max_retries=5,
        )
        assert config.path == "/tmp/test.db"
        assert config.pool_size == 20
        assert config.timeout == 60.0
        assert config.check_interval == 30
        assert config.max_retries == 5

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {"path": "test.db", "pool_size": 15, "timeout": 45.0}
        config = DatabaseConfig.from_dict(data)
        assert config.path == "test.db"
        assert config.pool_size == 15
        assert config.timeout == 45.0

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = DatabaseConfig(path="test.db")
        data = config.to_dict()
        assert data["path"] == "test.db"
        assert data["pool_size"] == 10


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_double_connect(self, connection_manager):
        """Test connecting twice."""
        await connection_manager.connect()
        await connection_manager.connect()  # Should not error
        assert connection_manager.is_connected

    @pytest.mark.asyncio
    async def test_double_disconnect(self, connection_manager):
        """Test disconnecting twice."""
        await connection_manager.connect()
        await connection_manager.disconnect()
        await connection_manager.disconnect()  # Should not error
        assert not connection_manager.is_connected

    @pytest.mark.asyncio
    async def test_query_without_connection(self, connection_manager):
        """Test querying without connection."""
        with pytest.raises(DatabaseError):
            await connection_manager.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_invalid_sql(self, connection_manager):
        """Test invalid SQL query."""
        await connection_manager.connect()
        with pytest.raises(DatabaseError):
            await connection_manager.execute("INVALID SQL")

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self, connection_manager):
        """Test connection cleanup on error."""
        await connection_manager.connect()

        with patch.object(
            connection_manager.pool,
            "acquire",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(DatabaseError):
                await connection_manager.execute("SELECT 1")

        # Should still be able to reconnect
        await connection_manager.disconnect()
        await connection_manager.connect()
        assert connection_manager.is_connected
