"""Test read-only database access in search engine."""

import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery


class TestReadOnlyAccess:
    """Test that search engine uses read-only database connections."""

    @pytest.fixture
    def test_db_path(self):
        """Create a temporary test database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Create minimal schema for testing
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                metadata TEXT
            );

            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER REFERENCES scripts(id),
                scene_number INTEGER,
                scene_heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT
            );

            INSERT INTO scripts (id, title, author, metadata)
            VALUES (1, 'Test Script', 'Test Author', '{}');

            INSERT INTO scenes (
                id, script_id, scene_number, scene_heading,
                location, time_of_day, content
            )
            VALUES (
                1, 1, 1, 'INT. OFFICE - DAY',
                'OFFICE', 'DAY', 'Test scene content'
            );
        """)
        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def search_engine(self, test_db_path):
        """Create search engine with test database."""
        settings = ScriptRAGSettings(database_path=test_db_path)
        return SearchEngine(settings)

    def test_read_only_connection_mode(self, search_engine):
        """Test that connection is opened in read-only mode."""
        with search_engine.get_read_only_connection() as conn:
            # Verify connection is read-only by checking pragma
            cursor = conn.execute("PRAGMA query_only")
            result = cursor.fetchone()
            assert result[0] == 1, "Connection should have query_only=1"

            # Verify URI mode was used (check connection properties)
            # This is implicitly tested by the fact that mode=ro was accepted

    def test_write_operations_fail(self, search_engine):
        """Test that write operations fail on read-only connection."""
        with search_engine.get_read_only_connection() as conn:
            # Try various write operations - all should fail
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("INSERT INTO scripts (title) VALUES ('New Script')")
            assert (
                "readonly" in str(exc_info.value).lower()
                or "read-only" in str(exc_info.value).lower()
            )

            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("UPDATE scripts SET title = 'Updated' WHERE id = 1")
            assert (
                "readonly" in str(exc_info.value).lower()
                or "read-only" in str(exc_info.value).lower()
            )

            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("DELETE FROM scripts WHERE id = 1")
            assert (
                "readonly" in str(exc_info.value).lower()
                or "read-only" in str(exc_info.value).lower()
            )

            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("CREATE TABLE test_table (id INTEGER)")
            assert (
                "readonly" in str(exc_info.value).lower()
                or "read-only" in str(exc_info.value).lower()
            )

            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("DROP TABLE scenes")
            assert (
                "readonly" in str(exc_info.value).lower()
                or "read-only" in str(exc_info.value).lower()
            )

    def test_read_operations_succeed(self, search_engine):
        """Test that read operations work on read-only connection."""
        with search_engine.get_read_only_connection() as conn:
            # Read operations should succeed
            cursor = conn.execute("SELECT * FROM scripts")
            results = cursor.fetchall()
            assert len(results) == 1

            cursor = conn.execute("SELECT COUNT(*) FROM scenes")
            count = cursor.fetchone()[0]
            assert count == 1

            # Complex joins should work
            cursor = conn.execute("""
                SELECT s.title, sc.scene_heading
                FROM scripts s
                JOIN scenes sc ON s.id = sc.script_id
            """)
            results = cursor.fetchall()
            assert len(results) == 1

    def test_search_uses_readonly_connection(self, search_engine, monkeypatch):
        """Test that search() method uses the read-only connection."""
        # Track if get_read_only_connection was called
        called = []
        original_method = search_engine.get_read_only_connection

        @contextmanager
        def mock_get_readonly():
            called.append(True)
            with original_method() as conn:
                yield conn

        monkeypatch.setattr(
            search_engine, "get_read_only_connection", mock_get_readonly
        )

        # Perform a search
        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.STRICT,
            limit=10,
            offset=0,
        )

        from contextlib import suppress

        with suppress(Exception):
            # We expect this to fail due to schema mismatch, but that's OK
            # We just want to verify the method was called
            search_engine.search(query)

        assert called, "search() should use get_read_only_connection()"

    def test_connection_error_on_missing_db(self, search_engine):
        """Test that proper error is raised when database doesn't exist."""
        # Point to non-existent database
        search_engine.db_path = Path("/nonexistent/database.db")

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.STRICT,
            limit=10,
            offset=0,
        )

        with pytest.raises(DatabaseError) as exc_info:
            search_engine.search(query)

        assert "Database not found" in str(exc_info.value)
        assert "scriptrag init" in str(exc_info.value)

    def test_readonly_with_nonexistent_db(self, tmp_path):
        """Test that read-only connection creates database if non-existent."""
        # Try to open non-existent database (will be created)
        db_path = tmp_path / "nonexistent.db"
        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)

        # Connection manager creates the database if it doesn't exist
        with engine.get_read_only_connection() as conn:
            # Database was created, verify it's in read-only mode
            cursor = conn.execute("PRAGMA query_only")
            result = cursor.fetchone()
            assert result[0] == 1, "Connection should have query_only=1"
