"""Simplified unit tests for VSS service."""

import sqlite3
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.storage.vss_service import VSSService


def mock_serialize_float32(x):
    """Mock serialize_float32 for testing."""
    if isinstance(x, list):
        return np.array(x, dtype=np.float32).tobytes()
    return x.tobytes()


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = tmp_path / "test.db"
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_cache_size = -2000
    settings.database_temp_store = "MEMORY"
    settings.database_foreign_keys = True
    settings.database_timeout = 30.0
    return settings


@pytest.fixture
def vss_service(mock_settings):
    """Create VSS service with mocked sqlite_vec."""
    with patch("scriptrag.storage.vss_service.sqlite_vec") as mock_vec:
        mock_vec.load = Mock(spec=object)
        mock_vec.serialize_float32 = mock_serialize_float32

        # Create database with necessary tables
        conn = sqlite3.connect(mock_settings.database_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER NOT NULL,
                scene_number INTEGER NOT NULL,
                heading TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS script_bibles (
                id INTEGER PRIMARY KEY,
                script_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bible_chunks (
                id INTEGER PRIMARY KEY,
                bible_id INTEGER NOT NULL,
                chunk_number INTEGER NOT NULL,
                heading TEXT,
                content TEXT,
                FOREIGN KEY (bible_id) REFERENCES script_bibles(id)
            )
        """)
        # Create embedding tables that VSS service expects
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scene_embeddings (
                scene_id INTEGER PRIMARY KEY,
                embedding_model TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bible_chunk_embeddings (
                chunk_id INTEGER PRIMARY KEY,
                embedding_model TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chunk_id) REFERENCES bible_chunks(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_id, embedding_model)
            )
        """)
        conn.commit()
        conn.close()

        service = VSSService(mock_settings, mock_settings.database_path)
        service.vss_extension_available = True
        return service


class TestVSSService:
    """Test VSS service functionality."""

    def test_store_scene_embedding(self, vss_service):
        """Test storing scene embedding."""
        service = vss_service

        # Add test data
        with service.get_connection() as conn:
            conn.execute(
                "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
                (1, "Test Script", "Test Author"),
            )
            conn.execute(
                "INSERT INTO scenes (id, script_id, scene_number, heading, content) "
                "VALUES (?, ?, ?, ?, ?)",
                (1, 1, 1, "INT. OFFICE - DAY", "Test content"),
            )

            # Store embedding
            embedding = [0.1, 0.2, 0.3]
            service.store_scene_embedding(1, embedding, "text-embedding-3-small", conn)

            # Verify embedding was stored
            cursor = conn.execute(
                "SELECT scene_id, embedding_model "
                "FROM scene_embeddings WHERE scene_id = ?",
                (1,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["scene_id"] == 1
            assert result["embedding_model"] == "text-embedding-3-small"

    def test_store_bible_embedding(self, vss_service):
        """Test storing bible embedding."""
        service = vss_service

        # Add test data
        with service.get_connection() as conn:
            conn.execute(
                "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
                (1, "Test Script", "Test Author"),
            )
            conn.execute(
                "INSERT INTO script_bibles (id, script_id, title, content) "
                "VALUES (?, ?, ?, ?)",
                (1, 1, "Test Bible", "Test content"),
            )
            conn.execute(
                "INSERT INTO bible_chunks "
                "(id, bible_id, chunk_number, heading, content) "
                "VALUES (?, ?, ?, ?, ?)",
                (1, 1, 1, "Test Heading", "Test chunk content"),
            )
            conn.commit()

        # Store embedding without connection (should create its own)
        embedding = [0.4, 0.5, 0.6]
        service.store_bible_embedding(1, embedding, "text-embedding-3-small")

        # Verify embedding was stored
        with service.get_connection() as conn:
            cursor = conn.execute(
                "SELECT chunk_id, embedding_model "
                "FROM bible_chunk_embeddings WHERE chunk_id = ?",
                (1,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["chunk_id"] == 1
            assert result["embedding_model"] == "text-embedding-3-small"

    def test_get_embedding_stats(self, vss_service):
        """Test getting embedding statistics."""
        service = vss_service

        # Add test data
        with service.get_connection() as conn:
            conn.execute(
                "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
                (1, "Test Script", "Test Author"),
            )

            # Add scenes and embeddings
            for i in range(1, 4):
                conn.execute(
                    "INSERT INTO scenes "
                    "(id, script_id, scene_number, heading, content) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (i, 1, i, f"INT. OFFICE {i} - DAY", f"Test content {i}"),
                )
                embedding = [0.1 * i, 0.2 * i, 0.3 * i]
                service.store_scene_embedding(
                    i, embedding, "text-embedding-3-small", conn
                )

            # Add bible data
            conn.execute(
                "INSERT INTO script_bibles (id, script_id, title, content) "
                "VALUES (?, ?, ?, ?)",
                (1, 1, "Test Bible", "Test content"),
            )

            for i in range(1, 3):
                conn.execute(
                    "INSERT INTO bible_chunks "
                    "(id, bible_id, chunk_number, heading, content) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (i, 1, i, f"Heading {i}", f"Chunk content {i}"),
                )
                embedding = [0.4 * i, 0.5 * i, 0.6 * i]
                service.store_bible_embedding(
                    i, embedding, "text-embedding-3-small", conn
                )

            conn.commit()

        # Get stats without connection
        stats = service.get_embedding_stats()

        assert stats is not None
        assert "scene_embeddings" in stats
        assert "bible_chunk_embeddings" in stats
        assert "metadata" in stats

        # Check scene embeddings
        assert "text-embedding-3-small" in stats["scene_embeddings"]
        assert stats["scene_embeddings"]["text-embedding-3-small"] == 3

        # Check bible chunk embeddings
        assert "text-embedding-3-small" in stats["bible_chunk_embeddings"]
        assert stats["bible_chunk_embeddings"]["text-embedding-3-small"] == 2

        # Check metadata
        assert "scene" in stats["metadata"]
        assert stats["metadata"]["scene"]["count"] == 3
        assert "bible_chunk" in stats["metadata"]
        assert stats["metadata"]["bible_chunk"]["count"] == 2
