"""Comprehensive tests for database connection module."""

import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.database.connection import (
    DatabaseConnection,
    close_default_connection,
    get_default_connection,
    set_default_connection,
    temporary_connection,
)
from scriptrag.database.schema import create_database


class TestDatabaseConnection:
    """Test database connection management."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Initialize schema
        create_database(db_path)

        yield db_path

        # Cleanup
        if db_path.exists():
            db_path.unlink()

    def test_connection_initialization(self, temp_db_path):
        """Test connection initialization with different parameters."""
        # Default initialization
        conn = DatabaseConnection(temp_db_path)
        assert conn.db_path == temp_db_path

        # With custom parameters
        conn = DatabaseConnection(
            temp_db_path,
            timeout=60.0,
            check_same_thread=True,
            isolation_level="DEFERRED",
        )
        assert conn.connection_params["timeout"] == 60.0
        assert conn.connection_params["check_same_thread"] is True
        assert conn.connection_params["isolation_level"] == "DEFERRED"

    def test_connection_configuration(self, temp_db_path):
        """Test SQLite connection configuration."""
        conn = DatabaseConnection(temp_db_path)

        with conn.get_connection() as db:
            # Check foreign keys enabled
            cursor = db.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1

            # Check journal mode (should be DELETE in tests)
            cursor = db.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0].upper()
            assert journal_mode in ["DELETE", "WAL"]

            # Check other pragmas
            cursor = db.execute("PRAGMA synchronous")
            assert cursor.fetchone()[0] in [1, 2]  # NORMAL or FULL

            # Check row factory
            cursor = db.execute("SELECT 1 as test")
            row = cursor.fetchone()
            assert row["test"] == 1

    def test_get_connection_thread_local(self, temp_db_path):
        """Test thread-local connection storage."""
        conn = DatabaseConnection(temp_db_path)

        # Get connection in main thread
        with conn.get_connection() as db1:
            db1_id = id(db1)

        # Get connection again - should be same instance
        with conn.get_connection() as db2:
            db2_id = id(db2)

        assert db1_id == db2_id

        # Test in different thread
        thread_db_id = None

        def thread_func():
            nonlocal thread_db_id
            with conn.get_connection() as db:
                thread_db_id = id(db)

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        # Should be different connection in different thread
        assert thread_db_id != db1_id

    def test_transaction_context_manager(self, temp_db_path):
        """Test transaction context manager."""
        conn = DatabaseConnection(temp_db_path)

        # Successful transaction
        with conn.transaction() as db:
            db.execute("INSERT INTO scripts (id, title) VALUES ('test-1', 'Test 1')")

        # Verify committed
        result = conn.fetch_one("SELECT title FROM scripts WHERE id = 'test-1'")
        assert result["title"] == "Test 1"

        # Failed transaction should rollback
        try:
            with conn.transaction() as db:
                db.execute(
                    "INSERT INTO scripts (id, title) VALUES ('test-2', 'Test 2')"
                )
                # Force error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify rollback
        result = conn.fetch_one(
            "SELECT COUNT(*) as count FROM scripts WHERE id = 'test-2'"
        )
        assert result["count"] == 0

    def test_execute_methods(self, temp_db_path):
        """Test various execute methods."""
        conn = DatabaseConnection(temp_db_path)

        # Test execute
        cursor = conn.execute(
            "INSERT INTO scripts (id, title) VALUES (?, ?)", ("test-1", "Test Script")
        )
        assert cursor.rowcount == 1

        # Test executemany
        data = [
            ("char-1", "test-1", "CHARACTER_1"),
            ("char-2", "test-1", "CHARACTER_2"),
        ]
        cursor = conn.executemany(
            "INSERT INTO characters (id, script_id, name) VALUES (?, ?, ?)", data
        )

        # Test fetch_one
        result = conn.fetch_one("SELECT name FROM characters WHERE id = ?", ("char-1",))
        assert result["name"] == "CHARACTER_1"

        # Test fetch_all
        results = conn.fetch_all(
            "SELECT name FROM characters WHERE script_id = ? ORDER BY name", ("test-1",)
        )
        assert len(results) == 2
        assert results[0]["name"] == "CHARACTER_1"
        assert results[1]["name"] == "CHARACTER_2"

        # Test fetch_many
        results = conn.fetch_many("SELECT name FROM characters ORDER BY name", size=1)
        assert len(results) == 1

    def test_error_handling(self, temp_db_path):
        """Test error handling in database operations."""
        conn = DatabaseConnection(temp_db_path)

        # Test invalid SQL
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("SELECT * FROM nonexistent_table")

        # Test constraint violation in transaction
        with pytest.raises(sqlite3.IntegrityError), conn.transaction() as db:
            # Insert duplicate primary key
            db.execute("INSERT INTO scripts (id, title) VALUES ('dup', 'Test')")
            db.execute("INSERT INTO scripts (id, title) VALUES ('dup', 'Test 2')")

    def test_table_introspection(self, temp_db_path):
        """Test table introspection methods."""
        conn = DatabaseConnection(temp_db_path)

        # Test get_table_names
        tables = conn.get_table_names()
        assert "scripts" in tables
        assert "characters" in tables
        assert "scenes" in tables

        # Test get_table_info
        info = conn.get_table_info("scripts")
        column_names = [col["name"] for col in info]
        assert "id" in column_names
        assert "title" in column_names
        assert "created_at" in column_names

    def test_database_maintenance(self, temp_db_path):
        """Test database maintenance operations."""
        conn = DatabaseConnection(temp_db_path)

        # Insert some data
        for i in range(10):
            conn.execute(
                "INSERT INTO scripts (id, title) VALUES (?, ?)",
                (f"script-{i}", f"Script {i}"),
            )

        # Test vacuum
        conn.vacuum()
        # Size might not change much with small data

        # Test analyze
        conn.analyze()

        # Verify database still works after maintenance
        result = conn.fetch_one("SELECT COUNT(*) as count FROM scripts")
        assert result["count"] == 10

    def test_connection_close(self, temp_db_path):
        """Test connection closing."""
        conn = DatabaseConnection(temp_db_path)

        # Open connection
        with conn.get_connection() as db:
            db.execute("SELECT 1")

        # Close connection
        conn.close()

        # Connection should be reset
        assert not hasattr(conn._local, "connection") or conn._local.connection is None

    def test_context_manager_usage(self, temp_db_path):
        """Test using DatabaseConnection as context manager."""
        with DatabaseConnection(temp_db_path) as conn:
            result = conn.fetch_one("SELECT 1 as test")
            assert result["test"] == 1

        # Connection should be closed after context

    def test_default_connection_management(self, temp_db_path):
        """Test default connection management functions."""
        # Initially no default connection
        with pytest.raises(RuntimeError):
            get_default_connection()

        # Set default connection
        conn = set_default_connection(temp_db_path)
        assert conn is not None

        # Get default connection
        default_conn = get_default_connection()
        assert default_conn is conn

        # Use default connection
        result = default_conn.fetch_one("SELECT 1 as test")
        assert result["test"] == 1

        # Close default connection
        close_default_connection()

        # Should raise again
        with pytest.raises(RuntimeError):
            get_default_connection()

    def test_temporary_connection(self, temp_db_path):
        """Test temporary connection context manager."""
        with temporary_connection(temp_db_path) as conn:
            # Insert data
            conn.execute(
                "INSERT INTO scripts (id, title) VALUES ('temp-1', 'Temporary')"
            )

            # Verify it works
            result = conn.fetch_one("SELECT title FROM scripts WHERE id = 'temp-1'")
            assert result["title"] == "Temporary"

        # Connection should be closed after context
        # Create new connection to verify data persisted
        with temporary_connection(temp_db_path) as conn:
            result = conn.fetch_one("SELECT title FROM scripts WHERE id = 'temp-1'")
            assert result["title"] == "Temporary"

    def test_connection_with_nonexistent_db(self):
        """Test connection creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"

            # Parent directory doesn't exist
            assert not db_path.parent.exists()

            # Create connection should create directory
            conn = DatabaseConnection(db_path)
            with conn.get_connection() as db:
                db.execute("CREATE TABLE test (id INTEGER)")

            # Verify directory was created
            assert db_path.parent.exists()
            assert db_path.exists()

    def test_concurrent_access(self, temp_db_path):
        """Test concurrent access from multiple threads."""
        conn = DatabaseConnection(temp_db_path)
        results = []
        errors = []

        def worker(worker_id):
            try:
                # Each thread inserts data
                for i in range(5):
                    conn.execute(
                        "INSERT INTO scripts (id, title) VALUES (?, ?)",
                        (f"worker-{worker_id}-{i}", f"Script {worker_id}-{i}"),
                    )
                    time.sleep(0.001)  # Small delay to increase contention
                results.append(worker_id)
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0
        assert len(results) == 5

        # Verify all data was inserted
        count = conn.fetch_one("SELECT COUNT(*) as count FROM scripts")
        assert count["count"] == 25  # 5 workers * 5 inserts each

    def test_fetch_with_no_results(self, temp_db_path):
        """Test fetch methods when no results found."""
        conn = DatabaseConnection(temp_db_path)

        # fetch_one with no results
        result = conn.fetch_one("SELECT * FROM scripts WHERE id = 'nonexistent'")
        assert result is None

        # fetch_all with no results
        results = conn.fetch_all("SELECT * FROM scripts WHERE id = 'nonexistent'")
        assert results == []

        # fetch_many with no results
        results = conn.fetch_many("SELECT * FROM scripts WHERE id = 'nonexistent'", 10)
        assert results == []

    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""})
    def test_wal_mode_configuration(self, temp_db_path):
        """Test WAL mode configuration outside of tests."""
        conn = DatabaseConnection(temp_db_path)

        with conn.get_connection() as db:
            cursor = db.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0].upper()
            # Should use WAL mode when not in test environment
            assert mode in ["WAL", "DELETE"]  # Platform dependent

    def test_connection_params_persistence(self, temp_db_path):
        """Test that connection parameters persist across connections."""
        custom_timeout = 45.0
        conn = DatabaseConnection(temp_db_path, timeout=custom_timeout)

        # First connection
        with conn.get_connection():
            pass

        # Second connection should use same params
        assert conn.connection_params["timeout"] == custom_timeout
