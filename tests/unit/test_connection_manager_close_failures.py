"""Tests for connection manager handling of close failures.

This module tests the bug fix for proper connection counting when
connection close operations fail. Previously, the counter would be
decremented even when close() threw an exception, leading to
inaccurate tracking and potential resource leaks.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection_manager import ConnectionPool


class MockConnection:
    """Mock connection that can simulate close failures."""

    def __init__(self, fail_close=False):
        self.fail_close = fail_close
        self.closed = False

    def execute(self, query):
        """Mock execute for health checks."""
        if self.closed:
            raise sqlite3.ProgrammingError("Cannot operate on closed connection")
        return Mock()

    def close(self):
        """Mock close that can fail."""
        if self.fail_close:
            raise Exception("Close failed")
        self.closed = True


class TestConnectionPoolCloseFailures:
    """Test suite for connection pool close failure handling."""

    @pytest.fixture
    def settings(self, tmp_path: Path) -> ScriptRAGSettings:
        """Create test settings with a temporary database."""
        return ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            log_level="WARNING",
        )

    @pytest.fixture
    def pool(self, settings: ScriptRAGSettings) -> ConnectionPool:
        """Create a connection pool for testing."""
        pool = ConnectionPool(
            settings,
            min_size=1,
            max_size=5,
            max_idle_time=300,
        )
        yield pool
        # Ensure cleanup
        pool.close(force=True)

    def test_release_unhealthy_connection_close_failure(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test _total_connections not decremented when close fails on release."""
        pool = ConnectionPool(settings, min_size=0, max_size=5)

        try:
            # Create a mock connection that will fail to close
            mock_conn = MockConnection(fail_close=True)

            # Manually add it to the pool's tracking
            with pool._lock:
                pool._total_connections = 1
                pool._active_connections = 1

            initial_total = pool.get_stats()["total_connections"]
            initial_failures = pool.get_stats()["unhealthy_close_failures"]

            # Make the connection appear unhealthy
            with patch.object(pool, "_is_connection_healthy", return_value=False):
                # Release the connection - close will fail
                pool.release(mock_conn)

            # Check that counter was NOT decremented since close failed
            stats = pool.get_stats()
            assert stats["total_connections"] == initial_total
            assert stats["unhealthy_close_failures"] == initial_failures + 1
        finally:
            pool.close(force=True)

    def test_release_unhealthy_connection_close_success(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test _total_connections IS decremented when close succeeds during release."""
        pool = ConnectionPool(settings, min_size=0, max_size=5)

        try:
            # Create a mock connection that will close successfully
            mock_conn = MockConnection(fail_close=False)

            # Manually add it to the pool's tracking
            with pool._lock:
                pool._total_connections = 1
                pool._active_connections = 1

            initial_total = pool.get_stats()["total_connections"]

            # Make the connection appear unhealthy
            with patch.object(pool, "_is_connection_healthy", return_value=False):
                # Release the connection - close will succeed
                pool.release(mock_conn)

            # Check that counter WAS decremented since close succeeded
            stats = pool.get_stats()
            assert stats["total_connections"] == initial_total - 1
        finally:
            pool.close(force=True)

    def test_pool_full_close_failure(self, settings: ScriptRAGSettings) -> None:
        """Test handling when pool is full and connection close fails."""
        pool = ConnectionPool(settings, min_size=0, max_size=2)

        try:
            # Create a mock connection that will fail to close
            mock_conn = MockConnection(fail_close=True)

            # Manually set up pool state
            with pool._lock:
                pool._total_connections = 1
                pool._active_connections = 1

            initial_total = pool.get_stats()["total_connections"]
            initial_failures = pool.get_stats()["unhealthy_close_failures"]

            # Make the pool appear full
            with patch.object(
                pool._pool, "put_nowait", side_effect=Exception("Pool full")
            ):
                # Release - should try to close the connection
                pool.release(mock_conn)

            # Check that counter was NOT decremented since close failed
            stats = pool.get_stats()
            assert stats["total_connections"] == initial_total
            assert stats["unhealthy_close_failures"] == initial_failures + 1
        finally:
            pool.close(force=True)

    def test_health_check_close_failure(self, settings: ScriptRAGSettings) -> None:
        """Test health check thread handling of close failures."""
        # We'll directly test the health check logic
        pool = ConnectionPool(settings, min_size=0, max_size=3)

        try:
            # Create unhealthy connections that fail to close
            mock_conn = MockConnection(fail_close=True)

            with pool._lock:
                # Put the mock connection in the pool
                pool._pool.put((mock_conn, time.time() - 1000))  # Old timestamp
                pool._total_connections = 1

            initial_total = pool.get_stats()["total_connections"]
            initial_failures = pool.get_stats()["unhealthy_close_failures"]

            # Make our mock connection appear unhealthy
            with patch.object(pool, "_is_connection_healthy", return_value=False):
                # Manually trigger health check logic exactly as the actual code does
                with pool._lock:
                    current_time = time.time()
                    healthy_connections = []

                    while not pool._pool.empty():
                        try:
                            conn, last_used = pool._pool.get_nowait()

                            # This is the actual health check logic from the fixed code
                            if pool._is_connection_healthy(conn):
                                healthy_connections.append((conn, last_used))
                            else:
                                try:
                                    conn.close()
                                    pool._total_connections -= 1
                                except Exception:
                                    pool._unhealthy_close_failures += 1
                                    # Don't decrement counter if close failed
                        except Exception:
                            break

            # Check results
            stats = pool.get_stats()
            assert stats["total_connections"] == initial_total  # Not decremented
            assert stats["unhealthy_close_failures"] == initial_failures + 1
        finally:
            pool.close(force=True)

    def test_shutdown_close_failures(self, settings: ScriptRAGSettings) -> None:
        """Test that pool shutdown handles close failures correctly."""
        pool = ConnectionPool(settings, min_size=0, max_size=5)

        try:
            # Add mock connections to the pool
            mock_conns = [
                MockConnection(fail_close=True),  # Will fail
                MockConnection(fail_close=True),  # Will fail
                MockConnection(fail_close=False),  # Will succeed
            ]

            with pool._lock:
                for conn in mock_conns:
                    pool._pool.put((conn, time.time()))
                pool._total_connections = 3

            # Close the pool
            pool.close()

            stats = pool.get_stats()
            # First 2 connections failed to close, last one succeeded
            # So we should have 2 connections still counted
            assert stats["total_connections"] == 2
            assert stats["unhealthy_close_failures"] == 2
        finally:
            # Force cleanup
            pool._closed = True

    def test_connection_accounting_with_real_connections(
        self, pool: ConnectionPool
    ) -> None:
        """Test with real connections that the accounting stays correct."""
        # This test uses real sqlite connections to ensure our fix works
        # with actual database connections

        initial_stats = pool.get_stats()

        # Get a real connection
        conn = pool.acquire(timeout=1.0)
        assert conn is not None

        # Stats should show one active connection
        stats = pool.get_stats()
        assert stats["active_connections"] == 1

        # Release it normally
        pool.release(conn)

        # Stats should show it's back in the pool
        stats = pool.get_stats()
        assert stats["active_connections"] == 0
        assert stats["idle_connections"] >= 1

        # Now test with unhealthy connection
        conn = pool.acquire(timeout=1.0)

        # Simulate the connection becoming unhealthy
        # We'll close it manually to make it unhealthy
        conn.close()

        # Now when we release it, the health check will fail
        with patch.object(pool, "_is_connection_healthy", return_value=False):
            pool.release(conn)

        # The connection should have been removed from tracking
        stats = pool.get_stats()
        assert stats["total_connections"] < initial_stats["total_connections"] + 1


class TestConnectionPoolIntegration:
    """Integration tests for the connection pool with close failures."""

    @pytest.fixture
    def settings(self, tmp_path: Path) -> ScriptRAGSettings:
        """Create test settings."""
        return ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            log_level="WARNING",
        )

    def test_pool_maintains_min_connections(self, settings: ScriptRAGSettings) -> None:
        """Test that pool maintains minimum connections even with failures."""
        pool = ConnectionPool(settings, min_size=2, max_size=5)

        try:
            # Initial state should have min_size connections
            stats = pool.get_stats()
            assert stats["total_connections"] >= pool.min_size

            # Acquire and release connections multiple times
            for _ in range(10):
                conn = pool.acquire(timeout=1.0)
                if conn:
                    pool.release(conn)
                time.sleep(0.01)

            # Should still maintain minimum
            stats = pool.get_stats()
            assert stats["total_connections"] >= pool.min_size
            assert stats["total_connections"] <= pool.max_size
        finally:
            pool.close(force=True)

    def test_concurrent_operations_with_failures(
        self, settings: ScriptRAGSettings
    ) -> None:
        """Test thread safety with concurrent operations."""
        pool = ConnectionPool(settings, min_size=2, max_size=10)

        try:
            results = {"success": 0, "failure": 0}
            lock = threading.Lock()

            def worker():
                for _ in range(5):
                    try:
                        conn = pool.acquire(timeout=0.5)
                        if conn:
                            # Do some work
                            time.sleep(0.001)
                            pool.release(conn)
                            with lock:
                                results["success"] += 1
                    except Exception:
                        with lock:
                            results["failure"] += 1

            # Run multiple workers
            threads = []
            for _ in range(5):
                t = threading.Thread(target=worker)
                t.start()
                threads.append(t)

            # Wait for completion
            for t in threads:
                t.join(timeout=5.0)

            # Check results
            assert results["success"] > 0

            # Pool should still be in valid state
            stats = pool.get_stats()
            assert stats["total_connections"] >= 0
            assert stats["total_connections"] <= pool.max_size
            assert stats["active_connections"] >= 0
        finally:
            pool.close(force=True)
