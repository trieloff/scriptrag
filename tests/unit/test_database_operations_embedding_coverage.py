"""Extended tests for database operations embedding methods to improve coverage."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = Path(":memory:")
    settings.llm_provider = "test"
    settings.llm_model = "test-model"
    settings.database_timeout = 30.0
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_cache_size = -2000
    settings.database_temp_store = "MEMORY"
    settings.database_foreign_keys = True
    settings.database_enable_fts = True
    return settings


@pytest.fixture
def db_ops_with_embeddings(mock_settings, tmp_path):
    """Create database operations with embedding tables."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    db_ops = DatabaseOperations(mock_settings)

    # Create necessary tables
    with db_ops.get_connection() as conn:
        # Scripts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                script_type TEXT,
                file_path TEXT UNIQUE NOT NULL
            )
        """)

        # Scenes table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL,
                scene_number INTEGER,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)

        # Embeddings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_id, embedding_model)
            )
        """)

        # Add test data
        conn.execute(
            "INSERT INTO scripts (title, author, script_type, file_path) "
            "VALUES (?, ?, ?, ?)",
            ("Test Script", "Test Author", "feature", "/test/path.fountain"),
        )

        conn.execute(
            "INSERT INTO scenes (script_id, scene_number, heading, content) "
            "VALUES (?, ?, ?, ?)",
            (1, 1, "INT. HOUSE - DAY", "Test scene content"),
        )

        conn.execute(
            "INSERT INTO scenes (script_id, scene_number, heading, content) "
            "VALUES (?, ?, ?, ?)",
            (1, 2, "EXT. STREET - NIGHT", "Another test scene"),
        )

        conn.commit()

    return db_ops


class TestDatabaseOperationsEmbeddingCoverage:
    """Extended tests for database operations embedding methods."""

    def test_get_scene_embeddings_with_results(self, db_ops_with_embeddings):
        """Test getting scene embeddings with existing data."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Add test embeddings
            embedding_data = b"test_embedding_data_1"
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 1, "test-model", embedding_data),
            )

            embedding_data_2 = b"test_embedding_data_2"
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 2, "test-model", embedding_data_2),
            )

            # Get embeddings
            results = db_ops_with_embeddings.get_scene_embeddings(conn, 1, "test-model")

            assert len(results) == 2
            assert results[0][0] == 1  # scene_id
            assert results[0][1] == embedding_data  # embedding data
            assert results[1][0] == 2  # scene_id
            assert results[1][1] == embedding_data_2  # embedding data

    def test_get_scene_embeddings_no_results(self, db_ops_with_embeddings):
        """Test getting scene embeddings when none exist."""
        with db_ops_with_embeddings.get_connection() as conn:
            results = db_ops_with_embeddings.get_scene_embeddings(
                conn, 1, "non-existent-model"
            )

            assert len(results) == 0

    def test_get_scene_embeddings_different_model(self, db_ops_with_embeddings):
        """Test getting scene embeddings filters by model."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Add embeddings for different models
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 1, "model-a", b"data_a"),
            )

            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 1, "model-b", b"data_b"),
            )

            # Get embeddings for model-a
            results_a = db_ops_with_embeddings.get_scene_embeddings(conn, 1, "model-a")
            assert len(results_a) == 1
            assert results_a[0][1] == b"data_a"

            # Get embeddings for model-b
            results_b = db_ops_with_embeddings.get_scene_embeddings(conn, 1, "model-b")
            assert len(results_b) == 1
            assert results_b[0][1] == b"data_b"

    def test_get_embedding_found(self, db_ops_with_embeddings):
        """Test getting specific embedding when it exists."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Add test embedding
            embedding_data = b"specific_embedding_data"
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("character", 42, "test-model", embedding_data),
            )

            # Get the embedding
            result = db_ops_with_embeddings.get_embedding(
                conn, "character", 42, "test-model"
            )

            assert result == embedding_data

    def test_get_embedding_not_found(self, db_ops_with_embeddings):
        """Test getting embedding when it doesn't exist."""
        with db_ops_with_embeddings.get_connection() as conn:
            result = db_ops_with_embeddings.get_embedding(
                conn, "scene", 999, "non-existent-model"
            )

            assert result is None

    def test_get_embedding_different_entity_types(self, db_ops_with_embeddings):
        """Test getting embeddings for different entity types."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Add embeddings for different entity types
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 1, "test-model", b"scene_data"),
            )

            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("character", 1, "test-model", b"character_data"),
            )

            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("bible_chunk", 1, "test-model", b"bible_data"),
            )

            # Get embeddings for each entity type
            scene_result = db_ops_with_embeddings.get_embedding(
                conn, "scene", 1, "test-model"
            )
            assert scene_result == b"scene_data"

            character_result = db_ops_with_embeddings.get_embedding(
                conn, "character", 1, "test-model"
            )
            assert character_result == b"character_data"

            bible_result = db_ops_with_embeddings.get_embedding(
                conn, "bible_chunk", 1, "test-model"
            )
            assert bible_result == b"bible_data"

    def test_search_similar_scenes_not_implemented(self, db_ops_with_embeddings):
        """Test that search_similar_scenes raises NotImplementedError."""
        with db_ops_with_embeddings.get_connection() as conn:
            with pytest.raises(NotImplementedError) as exc_info:
                db_ops_with_embeddings.search_similar_scenes(
                    conn, b"query_embedding", "test-model"
                )

            assert "VSS-based similarity search" in str(exc_info.value)

    def test_upsert_embedding_failed_insert_no_lastrowid(self, db_ops_with_embeddings):
        """Test error handling when insert doesn't return lastrowid."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Mock cursor with no lastrowid
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = None
            mock_cursor.fetchone.return_value = None  # No existing embedding

            # Mock connection's execute
            original_execute = conn.execute

            def mock_execute(query, params=None):
                if (
                    "SELECT id FROM embeddings" in query
                    or "INSERT INTO embeddings" in query
                ):
                    return mock_cursor
                return original_execute(query, params)

            conn.execute = mock_execute

            with pytest.raises(DatabaseError) as exc_info:
                db_ops_with_embeddings.upsert_embedding(
                    conn, "scene", 999, "test-model", b"data"
                )

            assert "Failed to get embedding ID" in str(exc_info.value)
            assert exc_info.value.details["entity_type"] == "scene"
            assert exc_info.value.details["entity_id"] == 999

    def test_get_scene_embeddings_null_embeddings(self, db_ops_with_embeddings):
        """Test getting scene embeddings excludes NULL embeddings."""
        with db_ops_with_embeddings.get_connection() as conn:
            # Add embedding with NULL data
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 1, "test-model", None),
            )

            # Add embedding with actual data
            conn.execute(
                "INSERT INTO embeddings "
                "(entity_type, entity_id, embedding_model, embedding) "
                "VALUES (?, ?, ?, ?)",
                ("scene", 2, "test-model", b"valid_data"),
            )

            # Get embeddings
            results = db_ops_with_embeddings.get_scene_embeddings(conn, 1, "test-model")

            # Should only get the one with actual data
            assert len(results) == 1
            assert results[0][0] == 2  # scene_id
            assert results[0][1] == b"valid_data"

    def test_search_similar_scenes_with_script_filter(self, db_ops_with_embeddings):
        """Test that search_similar_scenes with script_id raises NotImplementedError."""
        with db_ops_with_embeddings.get_connection() as conn:
            with pytest.raises(NotImplementedError):
                db_ops_with_embeddings.search_similar_scenes(
                    conn, b"query", "model", script_id=1, limit=5
                )

    def test_search_similar_bible_chunks_not_implemented(self, db_ops_with_embeddings):
        """Test that search_similar_bible_chunks raises NotImplementedError."""
        with db_ops_with_embeddings.get_connection() as conn:
            with pytest.raises(NotImplementedError) as exc_info:
                db_ops_with_embeddings.search_similar_bible_chunks(
                    conn, b"query", "model", limit=10
                )

            assert "VSS-based bible chunk search" in str(exc_info.value)
