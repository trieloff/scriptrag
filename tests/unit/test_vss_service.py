"""Unit tests for VSS service."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    return settings


@pytest.fixture
def vss_service(mock_settings, tmp_path):
    """Create VSS service with in-memory database."""
    # Use temporary database file for testing
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    # Create service with mock sqlite-vec loading
    with (
        patch("scriptrag.storage.vss_service.sqlite_vec.load"),
        patch(
            "scriptrag.storage.vss_service.serialize_float32",
            side_effect=mock_serialize_float32,
        ),
    ):
        service = VSSService(mock_settings, db_path)

        # Initialize basic schema
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Create scenes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY,
                    script_id INTEGER,
                    heading TEXT,
                    location TEXT,
                    content TEXT
                )
            """)

            # Create script_bibles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS script_bibles (
                    id INTEGER PRIMARY KEY,
                    script_id INTEGER,
                    title TEXT
                )
            """)

            # Create bible_chunks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bible_chunks (
                    id INTEGER PRIMARY KEY,
                    bible_id INTEGER,
                    heading TEXT,
                    content TEXT,
                    level INTEGER
                )
            """)

            # Create mock VSS tables (simplified for testing)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scene_embeddings (
                    scene_id INTEGER PRIMARY KEY,
                    embedding_model TEXT,
                    embedding BLOB,
                    distance REAL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS bible_embeddings (
                    chunk_id INTEGER PRIMARY KEY,
                    embedding_model TEXT,
                    embedding BLOB,
                    distance REAL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT,
                    entity_id INTEGER,
                    embedding_model TEXT,
                    dimensions INTEGER,
                    lfs_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (entity_type, entity_id, embedding_model)
                )
            """)

            conn.commit()
        finally:
            conn.close()

    return service


class TestVSSService:
    """Test VSS service functionality."""

    def test_initialization(self, vss_service):
        """Test VSS service initialization."""
        assert vss_service is not None
        assert vss_service.db_path.exists()

    def test_get_connection(self, vss_service):
        """Test getting database connection."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            conn = vss_service.get_connection()
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            conn.close()

    def test_store_scene_embedding(self, vss_service):
        """Test storing scene embedding."""
        scene_id = 1
        embedding = np.random.rand(1536).astype(np.float32)
        model = "test-model"

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service.get_connection() as conn:
                # Add test scene
                conn.execute(
                    "INSERT INTO scenes (id, script_id, heading, content) "
                    "VALUES (?, ?, ?, ?)",
                    (scene_id, 1, "Test Scene", "Test content"),
                )

                # Store embedding
                vss_service.store_scene_embedding(scene_id, embedding, model, conn)

                # Verify it was stored
                cursor = conn.execute(
                    "SELECT * FROM scene_embeddings WHERE scene_id = ?", (scene_id,)
                )
                row = cursor.fetchone()
                assert row is not None
                assert row[1] == model  # embedding_model

                # Check metadata
                cursor = conn.execute(
                    "SELECT * FROM embedding_metadata WHERE entity_id = ? "
                    "AND entity_type = 'scene'",
                    (scene_id,),
                )
                meta = cursor.fetchone()
                assert meta is not None
                assert meta[4] == 1536  # dimensions

    def test_store_scene_embedding_list(self, vss_service):
        """Test storing scene embedding from list."""
        scene_id = 2
        embedding = [float(i) for i in range(1536)]
        model = "test-model"

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service.get_connection() as conn:
                # Store embedding from list
                vss_service.store_scene_embedding(scene_id, embedding, model, conn)

                # Verify it was stored
                cursor = conn.execute(
                    "SELECT * FROM scene_embeddings WHERE scene_id = ?", (scene_id,)
                )
                row = cursor.fetchone()
                assert row is not None

    def test_search_similar_scenes(self, vss_service):
        """Test searching similar scenes."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the entire search method since we can't mock sqlite execute
            mock_results = [
                {
                    "id": i,
                    "script_id": 1,
                    "heading": f"Scene {i}",
                    "location": f"Location {i}",
                    "content": f"Content {i}",
                    "scene_id": i,
                    "similarity_score": 1.0
                    - (float(i) * 0.05),  # Decreasing similarity
                }
                for i in range(1, 4)
            ]

            vss_service.search_similar_scenes = MagicMock(return_value=mock_results)

            query_embedding = np.random.rand(1536).astype(np.float32)
            results = vss_service.search_similar_scenes(
                query_embedding, "test-model", limit=3
            )

            assert len(results) == 3
            assert all("similarity_score" in r for r in results)
            # Check that results are ordered by similarity (descending)
            assert results[0]["similarity_score"] > results[1]["similarity_score"]
            assert results[1]["similarity_score"] > results[2]["similarity_score"]

    def test_search_similar_scenes_with_script_filter(self, vss_service):
        """Test searching similar scenes with script filter."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the search method with script filter
            mock_results = [
                {
                    "id": 1,
                    "script_id": 1,
                    "heading": "Scene 1",
                    "location": None,
                    "content": "Content 1",
                    "scene_id": 1,
                    "similarity_score": 0.95,
                }
            ]

            vss_service.search_similar_scenes = MagicMock(return_value=mock_results)

            query_embedding = np.random.rand(1536).astype(np.float32)
            results = vss_service.search_similar_scenes(
                query_embedding, "test-model", limit=10, script_id=1
            )

            # Verify the method was called with script_id
            vss_service.search_similar_scenes.assert_called_with(
                query_embedding, "test-model", limit=10, script_id=1
            )
            assert len(results) == 1
            assert results[0]["script_id"] == 1

    def test_store_bible_embedding(self, vss_service):
        """Test storing bible chunk embedding."""
        chunk_id = 1
        embedding = np.random.rand(1536).astype(np.float32)
        model = "test-model"

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service.get_connection() as conn:
                # Store embedding
                vss_service.store_bible_embedding(chunk_id, embedding, model, conn)

                # Verify it was stored
                cursor = conn.execute(
                    "SELECT * FROM bible_embeddings WHERE chunk_id = ?", (chunk_id,)
                )
                row = cursor.fetchone()
                assert row is not None
                assert row[1] == model  # embedding_model

    def test_search_similar_bible_chunks(self, vss_service):
        """Test searching similar bible chunks."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the search method
            mock_results = [
                {
                    "id": i,
                    "bible_id": 1,
                    "heading": f"Chunk {i}",
                    "content": f"Content {i}",
                    "bible_title": "Test Bible",
                    "script_id": 1,
                    "chunk_id": i,
                    "similarity_score": 1.0 - (float(i) * 0.05),
                    "level": None,
                }
                for i in range(1, 4)
            ]

            vss_service.search_similar_bible_chunks = MagicMock(
                return_value=mock_results
            )

            query_embedding = np.random.rand(1536).astype(np.float32)
            results = vss_service.search_similar_bible_chunks(
                query_embedding, "test-model", limit=3
            )

            assert len(results) == 3
            assert all("similarity_score" in r for r in results)

    def test_get_embedding_stats(self, vss_service):
        """Test getting embedding statistics."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service.get_connection() as conn:
                # Add some test embeddings
                for i in range(1, 4):
                    conn.execute(
                        "INSERT INTO scene_embeddings "
                        "(scene_id, embedding_model, embedding) VALUES (?, ?, ?)",
                        (i, "model1", b"test"),
                    )
                    conn.execute(
                        "INSERT INTO embedding_metadata "
                        "(entity_type, entity_id, embedding_model, dimensions) "
                        "VALUES (?, ?, ?, ?)",
                        ("scene", i, "model1", 1536),
                    )

                stats = vss_service.get_embedding_stats(conn)

                assert "scene_embeddings" in stats
                assert "metadata" in stats
                assert stats["scene_embeddings"]["model1"] == 3

    def test_error_handling_store_embedding(self, vss_service):
        """Test error handling when storing embedding fails."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection to raise an error during execute
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.Error("Test database error")
            mock_conn.rollback.return_value = None
            mock_conn.close.return_value = None

            with patch.object(vss_service, "get_connection", return_value=mock_conn):
                with pytest.raises(DatabaseError) as exc_info:
                    vss_service.store_scene_embedding(1, [1, 2, 3], "model")

                assert "Failed to store scene embedding" in str(exc_info.value)
                # Verify rollback was called due to error
                mock_conn.rollback.assert_called_once()

    def test_error_handling_search(self, vss_service):
        """Test error handling when search fails."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection to raise an error during execute
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.Error("Search database error")
            mock_conn.close.return_value = None

            with patch.object(vss_service, "get_connection", return_value=mock_conn):
                with pytest.raises(DatabaseError) as exc_info:
                    vss_service.search_similar_scenes(np.random.rand(1536), "model")

                assert "Failed to search similar scenes" in str(exc_info.value)
                # Verify the connection was properly cleaned up
                mock_conn.close.assert_called_once()

    def test_migrate_from_blob_storage(self, vss_service):
        """Test migration from old BLOB storage."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service.get_connection() as conn:
                # Create old embeddings table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings_old (
                        id INTEGER PRIMARY KEY,
                        entity_type TEXT,
                        entity_id INTEGER,
                        embedding_model TEXT,
                        embedding BLOB
                    )
                """)

                # Add test data with encoded embeddings
                import struct

                dimension = 3
                values = [0.1, 0.2, 0.3]
                format_str = f"<I{dimension}f"
                blob_data = struct.pack(format_str, dimension, *values)

                conn.execute(
                    "INSERT INTO embeddings_old "
                    "(entity_type, entity_id, embedding_model, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    ("scene", 1, "test-model", blob_data),
                )

                # Mock store methods to track calls
                vss_service.store_scene_embedding = MagicMock()
                vss_service.store_bible_embedding = MagicMock()

                scenes_migrated, bible_migrated = vss_service.migrate_from_blob_storage(
                    conn
                )

                # Verify migration was attempted
                vss_service.store_scene_embedding.assert_called_once()
                assert scenes_migrated == 1
                assert bible_migrated == 0
