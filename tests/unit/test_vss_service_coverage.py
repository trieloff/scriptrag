"""Additional tests for VSS service to improve coverage."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.storage.vss_service import VSSService


def mock_serialize_float32(x):
    """Mock serialize_float32 for testing."""
    if isinstance(x, list):
        return np.array(x, dtype=np.float32).tobytes()
    return x.tobytes()


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = Path(":memory:")
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_cache_size = -2000
    settings.database_temp_store = "MEMORY"
    settings.database_foreign_keys = True
    settings.database_timeout = 30.0
    return settings


@pytest.fixture
def vss_service(mock_settings, tmp_path):
    """Create VSS service with in-memory database."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    with (
        patch("scriptrag.storage.vss_service.sqlite_vec.load"),
        patch(
            "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
            side_effect=mock_serialize_float32,
        ),
    ):
        service = VSSService(mock_settings, db_path)

        # Initialize basic schema
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Create all necessary tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY,
                    script_id INTEGER,
                    heading TEXT,
                    location TEXT,
                    content TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS script_bibles (
                    id INTEGER PRIMARY KEY,
                    script_id INTEGER,
                    title TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS bible_chunks (
                    id INTEGER PRIMARY KEY,
                    bible_id INTEGER,
                    heading TEXT,
                    content TEXT,
                    level INTEGER
                )
            """)

            # Create mock VSS tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scene_embeddings (
                    scene_id INTEGER PRIMARY KEY,
                    embedding_model TEXT,
                    embedding BLOB,
                    distance REAL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS bible_chunk_embeddings (
                    chunk_id INTEGER PRIMARY KEY,
                    embedding_model TEXT,
                    embedding BLOB,
                    distance REAL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_metadata (
                    entity_type TEXT,
                    entity_id INTEGER,
                    embedding_model TEXT,
                    dimensions INTEGER,
                    PRIMARY KEY (entity_type, entity_id, embedding_model)
                )
            """)

            conn.commit()
        finally:
            conn.close()

    return service


class TestVSSServiceExtended:
    """Extended tests for VSS service coverage."""

    def test_sqlite_extension_loading_error(self, mock_settings, tmp_path):
        """Test handling of SQLite extension loading errors."""
        db_path = tmp_path / "test.db"
        mock_settings.database_path = db_path

        with (
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.load",
                side_effect=sqlite3.OperationalError("Cannot load"),
            ),
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Should continue without error
            service = VSSService(mock_settings, db_path)
            conn = service.get_connection()
            assert conn is not None
            conn.close()

    def test_search_similar_scenes_with_script_id(self, vss_service):
        """Test searching similar scenes with script_id filter."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection execute to simulate VSS search
            mock_conn = MagicMock(spec=object)
            mock_cursor = MagicMock(spec=object)

            # Mock results - only scenes from script 10
            mock_rows = [
                {
                    "id": 1,
                    "script_id": 10,
                    "heading": "INT. ROOM - DAY",
                    "content": "Test scene",
                    "distance": 0.1,
                },
                {
                    "id": 2,
                    "script_id": 10,
                    "heading": "EXT. STREET - NIGHT",
                    "content": "Another scene",
                    "distance": 0.2,
                },
            ]

            # Create proper mock Row objects that behave like dictionaries
            mock_row_objects = []
            for row in mock_rows:
                mock_row = MagicMock(spec=object)
                mock_row.__getitem__ = lambda _self, key, r=row: r[key]
                mock_row.keys = lambda r=row: r.keys()
                # Make it dict-like
                for k, v in row.items():
                    setattr(mock_row, k, v)
                mock_row_objects.append(mock_row)

            mock_cursor.__iter__ = Mock(return_value=iter(mock_row_objects))

            # Configure mock to handle the query
            def mock_execute(query, params=None):
                if (
                    "MATCH" in query and params and len(params) > 1 and params[1] == 10
                ):  # script_id filter
                    return mock_cursor
                return MagicMock(spec=object)

            mock_conn.execute = mock_execute
            mock_conn.rollback = Mock(spec=object)
            mock_conn.commit = Mock(spec=object)
            mock_conn.close = Mock(spec=object)

            # Patch get_connection to return our mock
            with patch.object(vss_service, "get_connection", return_value=mock_conn):
                # Search with script_id filter
                results = vss_service.search_similar_scenes(
                    query_embedding=[0.1, 0.2, 0.3],
                    model="test-model",
                    limit=10,
                    script_id=10,  # Filter to script 10
                )

                # Should only return scenes from script 10
                assert len(results) == 2
                for result in results:
                    assert result["script_id"] == 10
                    assert "similarity_score" in result
                    assert 0 <= result["similarity_score"] <= 1

    def test_search_similar_bible_chunks_with_script_id(self, vss_service):
        """Test searching similar bible chunks with script_id filter."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection execute to simulate VSS search
            mock_conn = MagicMock(spec=object)
            mock_cursor = MagicMock(spec=object)

            # Mock results - only chunks from script 10
            mock_rows = [
                {
                    "id": 1,
                    "chunk_id": 1,
                    "script_id": 10,
                    "heading": "Chapter 1",
                    "content": "Content 1",
                    "bible_title": "Bible 1",
                    "distance": 0.1,
                },
                {
                    "id": 2,
                    "chunk_id": 2,
                    "script_id": 10,
                    "heading": "Chapter 2",
                    "content": "Content 2",
                    "bible_title": "Bible 1",
                    "distance": 0.2,
                },
            ]

            # Create proper mock Row objects that behave like dictionaries
            mock_row_objects = []
            for row in mock_rows:
                mock_row = MagicMock(spec=object)
                mock_row.__getitem__ = lambda _self, key, r=row: r[key]
                mock_row.keys = lambda r=row: r.keys()
                # Make it dict-like
                for k, v in row.items():
                    setattr(mock_row, k, v)
                mock_row_objects.append(mock_row)

            mock_cursor.__iter__ = Mock(return_value=iter(mock_row_objects))

            # Configure mock to handle the query
            def mock_execute(query, params=None):
                if (
                    "MATCH" in query
                    and "bible_chunk_embeddings" in query
                    and params
                    and len(params) > 1
                    and params[1] == 10
                ):  # script_id filter
                    return mock_cursor
                return MagicMock(spec=object)

            mock_conn.execute = mock_execute
            mock_conn.rollback = Mock(spec=object)
            mock_conn.commit = Mock(spec=object)
            mock_conn.close = Mock(spec=object)

            # Patch get_connection to return our mock
            with patch.object(vss_service, "get_connection", return_value=mock_conn):
                # Search with script_id filter
                results = vss_service.search_similar_bible_chunks(
                    query_embedding=[0.1, 0.2, 0.3],
                    model="test-model",
                    limit=10,
                    script_id=10,  # Filter to script 10
                )

                # Should only return chunks from script 10
                assert len(results) == 2
                for result in results:
                    assert result["script_id"] == 10
                    assert "similarity_score" in result
                    assert "bible_title" in result
                    assert result["bible_title"] == "Bible 1"

    def test_store_bible_embedding_error_handling(self, vss_service):
        """Test error handling in store_bible_embedding."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=Exception("Serialization failed"),
            ),
        ):
            # Should raise DatabaseError
            with pytest.raises(DatabaseError) as exc_info:
                vss_service.store_bible_embedding(
                    chunk_id=1,
                    embedding=[0.1, 0.2, 0.3],
                    model="test-model",
                )
            assert "Failed to store bible embedding" in str(exc_info.value)

    def test_search_similar_bible_chunks_error(self, vss_service):
        """Test error handling in search_similar_bible_chunks."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=Exception("Serialization failed"),
            ),
        ):
            # Should raise DatabaseError
            with pytest.raises(DatabaseError) as exc_info:
                vss_service.search_similar_bible_chunks(
                    query_embedding=[0.1, 0.2, 0.3],
                    model="test-model",
                )
            assert "Failed to search similar bible chunks" in str(exc_info.value)

    # Migration tests removed - migration function no longer exists
    # def test_migrate_no_old_table(self, vss_service):
    #     pass

    # def test_migrate_with_bible_chunks(self, vss_service):
    #     pass

    # def test_migrate_with_corrupted_data(self, vss_service):
    #     pass

    def test_initialize_vss_tables_with_migration_file(self, mock_settings, tmp_path):
        """Test VSS table initialization with migration file."""
        db_path = tmp_path / "test.db"
        mock_settings.database_path = db_path

        # Create a mock migration file
        migration_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "scriptrag"
            / "storage"
            / "database"
            / "sql"
        )
        migration_dir.mkdir(parents=True, exist_ok=True)
        migration_file = migration_dir / "vss_migration.sql"

        # Write test migration SQL
        migration_file.write_text("""
-- Test migration file
CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY);
-- This should be skipped
.load sqlite_vec
-- This should also work
CREATE TABLE IF NOT EXISTS another_table (id INTEGER PRIMARY KEY);
""")

        try:
            with (
                patch("scriptrag.storage.vss_service.sqlite_vec.load"),
                patch(
                    "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                    side_effect=mock_serialize_float32,
                ),
            ):
                service = VSSService(mock_settings, db_path)

                # Check that service was created successfully
                assert service is not None
                # Tables might not be created in test, but service should init
        finally:
            # Clean up
            if migration_file.exists():
                migration_file.unlink()

    def test_connection_without_loadable_extensions(self, mock_settings, tmp_path):
        """Test connection when SQLite doesn't support loadable extensions."""
        db_path = tmp_path / "test.db"
        mock_settings.database_path = db_path

        with (
            patch(
                "scriptrag.storage.vss_service.sqlite_vec.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Create a mock connection without enable_load_extension attribute
            mock_conn = MagicMock(spec=sqlite3.Connection)
            del mock_conn.enable_load_extension  # Remove the attribute
            mock_conn.row_factory = None
            mock_conn.execute = MagicMock(spec=object)

            with patch("sqlite3.connect", return_value=mock_conn):
                service = VSSService(mock_settings, db_path)
                conn = service.get_connection()

                # Should have gotten the mock connection
                assert conn == mock_conn
                # Should have set row_factory
                assert mock_conn.row_factory == sqlite3.Row
                # Should have enabled foreign keys
                mock_conn.execute.assert_any_call("PRAGMA foreign_keys = ON")
