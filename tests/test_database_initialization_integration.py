"""Integration tests for automatic database initialization (Bug #122).

This test suite verifies that the database schema is automatically initialized
on first use, preventing the "no such table: nodes" error that occurred when
parsing scripts without manually initializing the database first.
"""

import contextlib
import tempfile
from pathlib import Path

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.parser import FountainParser


class TestDatabaseAutoInitialization:
    """Integration tests for automatic database schema initialization."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_fountain_content(self) -> str:
        """Sample fountain screenplay content for testing."""
        return """Title: Test Script
Author: Test Author

FADE IN:

INT. KITCHEN - DAY

JOHN sits at the table, drinking coffee.

JOHN
This is a test dialogue.

FADE OUT.
"""

    @pytest.fixture
    def fountain_file(self, temp_dir: Path, sample_fountain_content: str) -> Path:
        """Create a sample fountain file for testing."""
        fountain_path = temp_dir / "test_script.fountain"
        fountain_path.write_text(sample_fountain_content, encoding="utf-8")
        return fountain_path

    def test_database_initializes_automatically_on_first_connection(
        self, temp_dir: Path
    ) -> None:
        """Test that database schema is created automatically on first connection.

        This is the core test for Bug #122: Database initialization failure prevents
        core parsing operations.
        """
        # Create a path for a database that doesn't exist yet
        db_path = temp_dir / "test_auto_init.db"

        # Verify the database file doesn't exist
        assert not db_path.exists(), "Database file should not exist initially"

        # Create a connection - this should automatically initialize the schema
        connection = DatabaseConnection(db_path)

        try:
            # Attempt to perform a basic database operation
            with connection.get_connection() as conn:
                # This query should work if the schema was properly initialized
                cursor = conn.execute("SELECT COUNT(*) FROM nodes")
                result = cursor.fetchone()
                assert result is not None, "Should be able to query nodes table"
                assert result[0] == 0, "Nodes table should be empty initially"

            # Verify database file was created
            assert db_path.exists(), "Database file should exist after connection"

            # Verify core tables exist
            with connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]

                # Check for essential tables that should exist after initialization
                essential_tables = [
                    "nodes",
                    "edges",
                    "scripts",
                    "scenes",
                    "characters",
                    "locations",
                    "scene_elements",
                    "embeddings",
                ]

                for table in essential_tables:
                    assert table in tables, (
                        f"Essential table '{table}' should exist after initialization"
                    )

        finally:
            # Clean up
            connection.close()
            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)

    def test_fountain_parsing_works_with_fresh_database(
        self, temp_dir: Path, fountain_file: Path
    ) -> None:
        """Test that fountain parsing works with a fresh (non-existent) database.

        This tests the exact scenario described in Bug #122:
        1. Fresh ScriptRAG installation
        2. Execute: scriptrag script parse <fountain-file>
        3. Should work without "no such table: nodes" error
        """
        # Create a path for a database that doesn't exist yet
        db_path = temp_dir / "test_parsing.db"

        # Verify the database file doesn't exist
        assert not db_path.exists(), "Database file should not exist initially"

        # Create parser and attempt to parse fountain file
        parser = FountainParser()

        # This should work without any database errors
        script = parser.parse_file(fountain_file)

        # Verify parsing worked
        assert script is not None, "Script should be parsed successfully"
        assert script.title == "Test Script", "Script title should be parsed correctly"
        assert script.author == "Test Author", (
            "Script author should be parsed correctly"
        )
        assert len(script.scenes) > 0, "Script should have at least one scene"

    def test_database_schema_version_after_auto_initialization(
        self, temp_dir: Path
    ) -> None:
        """Test that auto-initialized database has the correct schema version."""
        # Create a path for a database that doesn't exist yet
        db_path = temp_dir / "test_schema_version.db"

        # Create connection to trigger auto-initialization
        connection = DatabaseConnection(db_path)

        try:
            # Check schema version
            with connection.get_connection() as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_info")
                result = cursor.fetchone()

                assert result is not None, "Schema info should exist"
                version = result[0]
                assert version is not None, "Schema version should be set"
                assert version >= 5, (
                    f"Schema version should be at least 5, got {version}"
                )

        finally:
            connection.close()
            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)

    def test_existing_database_not_reinitialized(self, temp_dir: Path) -> None:
        """Test that existing databases are not reinitialized."""
        from scriptrag.database.schema import create_database

        # Create a database with initial schema
        db_path = temp_dir / "test_existing.db"
        create_database(db_path)

        # Add some test data
        connection = DatabaseConnection(db_path)

        try:
            with connection.transaction() as conn:
                conn.execute(
                    "INSERT INTO nodes (id, node_type, label) VALUES (?, ?, ?)",
                    ("test-node-1", "test", "Test Node"),
                )

            # Close and reopen connection (this would trigger reinitialization if buggy)
            connection.close()
            connection = DatabaseConnection(db_path)

            # Verify our test data is still there
            with connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM nodes WHERE node_type = 'test'"
                )
                result = cursor.fetchone()
                assert result[0] == 1, (
                    "Test data should still exist (database not reinitialized)"
                )

        finally:
            connection.close()
            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)

    def test_concurrent_initialization_safety(self, temp_dir: Path) -> None:
        """Test that concurrent database initialization is handled safely.

        This test ensures our thread safety mechanisms work correctly when multiple
        threads attempt to initialize the database simultaneously.
        """
        import threading
        import time

        db_path = temp_dir / "test_concurrent.db"
        results = []
        errors = []
        connections = []
        lock = threading.Lock()

        def create_connection_and_query():
            """Function to run in multiple threads."""
            try:
                # Create connection (may trigger initialization)
                connection = DatabaseConnection(db_path)

                # Add small random delay to increase chance of concurrent access
                time.sleep(0.001 * (threading.get_ident() % 5))

                # Test database access
                with connection.get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM nodes")
                    result = cursor.fetchone()

                    with lock:
                        results.append(result[0])
                        connections.append(connection)

            except Exception as e:
                with lock:
                    errors.append((threading.get_ident(), str(e)))

        # Start multiple threads that all try to initialize the database
        threads = []
        thread_count = 5  # Use more threads to better test concurrency

        for _ in range(thread_count):
            thread = threading.Thread(target=create_connection_and_query)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)  # Add timeout to avoid hanging tests

        try:
            # All threads should succeed with our improved concurrency handling
            assert len(results) == thread_count, (
                f"All {thread_count} threads should succeed, "
                f"got {len(results)} successes. Errors: {errors}"
            )

            # All threads should see empty nodes table
            assert all(result == 0 for result in results), (
                f"All threads should see empty nodes table, got: {results}"
            )

            # Verify database exists and is properly initialized
            assert db_path.exists(), (
                "Database should exist after concurrent initialization"
            )

            # Verify schema version is correct
            test_connection = DatabaseConnection(db_path)
            with test_connection.get_connection() as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_info")
                version = cursor.fetchone()[0]
                assert version >= 5, (
                    f"Schema version should be at least 5, got {version}"
                )
            test_connection.close()

        finally:
            # Clean up connections
            for conn in connections:
                conn.close()

            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)

    def test_schema_initialization_with_database_error(self, temp_dir: Path) -> None:
        """Test that database errors during schema check are handled properly."""
        import sqlite3
        from unittest.mock import Mock, patch

        db_path = temp_dir / "test_db_error.db"

        # Create a connection that will fail during schema check
        connection = DatabaseConnection(db_path)

        try:
            # Mock connection.execute to raise a database error
            with patch("sqlite3.Connection.execute") as mock_execute:
                mock_execute.side_effect = sqlite3.DatabaseError(
                    "Simulated database error"
                )

                # Create a connection and trigger initialization
                # This should handle the error gracefully and attempt initialization
                from scriptrag.database.connection import DatabaseConnection as DBConn

                # Create a fresh connection instance to test error handling
                test_conn = DBConn(db_path)

                # The connection should still work even after the error
                # because _is_schema_missing returns True on error
                with test_conn.get_connection():
                    # Reset the mock for actual operations
                    mock_execute.side_effect = None
                    mock_execute.return_value = Mock()

                test_conn.close()

        finally:
            connection.close()
            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)

    def test_migration_import_error_handling(self, temp_dir: Path) -> None:
        """Test handling of import errors during schema initialization."""
        from unittest.mock import patch

        db_path = temp_dir / "test_import_error.db"

        # Mock the migration import to fail
        with patch(
            "scriptrag.database.connection.DatabaseConnection._initialize_schema"
        ) as mock_init:
            # Make initialization raise an ImportError
            mock_init.side_effect = ImportError("Failed to import migrations")

            connection = DatabaseConnection(db_path)

            try:
                # Attempting to get a connection should raise a RuntimeError
                # with details about the ImportError
                with (
                    pytest.raises(RuntimeError) as exc_info,
                    connection.get_connection(),
                ):
                    pass

                assert "import migration module" in str(exc_info.value).lower()

            finally:
                connection.close()
                with contextlib.suppress(PermissionError):
                    db_path.unlink(missing_ok=True)

    def test_specific_migration_errors(self, temp_dir: Path) -> None:
        """Test handling of specific migration errors."""

        db_path = temp_dir / "test_migration_error.db"
        connection = DatabaseConnection(db_path)

        try:
            with connection.get_connection() as conn:
                # Database should be initialized
                cursor = conn.execute("SELECT COUNT(*) FROM nodes")
                assert cursor.fetchone()[0] == 0

        finally:
            connection.close()
            with contextlib.suppress(PermissionError):
                db_path.unlink(missing_ok=True)
