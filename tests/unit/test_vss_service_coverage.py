"""Extended unit tests for VSS service to improve coverage."""

import sqlite3
import struct
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
    return settings


@pytest.fixture
def vss_service_no_init(mock_settings, tmp_path):
    """Create VSS service without initialization for testing edge cases."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    # Create service without initializing tables
    with patch("scriptrag.storage.vss_service.sqlite_vec.load"):
        return VSSService(mock_settings, db_path)


@pytest.fixture
def vss_service_with_migration(mock_settings, tmp_path):
    """Create VSS service with migration SQL file."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    # Create migration SQL file
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

    migration_sql = """
    -- Test migration SQL
    CREATE TABLE IF NOT EXISTS scene_embeddings (
        scene_id INTEGER PRIMARY KEY,
        embedding_model TEXT,
        embedding BLOB,
        distance REAL DEFAULT 0
    );

    -- This should be skipped
    .load sqlite_vec;

    CREATE TABLE IF NOT EXISTS bible_embeddings (
        chunk_id INTEGER PRIMARY KEY,
        embedding_model TEXT,
        embedding BLOB,
        distance REAL DEFAULT 0
    );

    -- This will trigger already exists warning
    CREATE TABLE bible_embeddings (
        chunk_id INTEGER PRIMARY KEY
    );
    """

    migration_file.write_text(migration_sql)

    with (
        patch("scriptrag.storage.vss_service.sqlite_vec.load"),
        patch(
            "scriptrag.storage.vss_service.serialize_float32",
            side_effect=mock_serialize_float32,
        ),
    ):
        service = VSSService(mock_settings, db_path)

    # Clean up migration file
    migration_file.unlink()

    return service


class TestVSSServiceCoverage:
    """Extended tests for VSS service coverage."""

    def test_initialization_with_migration_file(self, vss_service_with_migration):
        """Test VSS service initialization with migration SQL file."""
        assert vss_service_with_migration is not None
        assert vss_service_with_migration.db_path.exists()

        # Verify tables were created
        with vss_service_with_migration.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE '%embeddings%'"
            )
            tables = [row[0] for row in cursor]
            # At least one embeddings table should exist
            assert any("embeddings" in t for t in tables)

    def test_initialization_no_migration_file(self, mock_settings, tmp_path):
        """Test VSS service initialization without migration file."""
        db_path = tmp_path / "test_no_migration.db"
        mock_settings.database_path = db_path

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            service = VSSService(mock_settings, db_path)
            assert service is not None

    def test_get_connection_no_extension_support(self, vss_service_no_init):
        """Test getting connection when extension loading is not supported."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock connection without enable_load_extension
            mock_conn = MagicMock(spec=sqlite3.Connection)
            del mock_conn.enable_load_extension  # Remove the attribute
            mock_conn.row_factory = None
            mock_conn.execute.return_value = MagicMock()

            with patch("sqlite3.connect", return_value=mock_conn):
                conn = vss_service_no_init.get_connection()
                assert conn is not None
                # Verify extension loading was not attempted
                assert not hasattr(conn, "enable_load_extension")

    def test_get_connection_extension_load_fails(self, vss_service_no_init):
        """Test getting connection when extension loading fails."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load") as mock_load,
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Make extension loading raise an error
            mock_load.side_effect = sqlite3.OperationalError("Extension load failed")

            conn = vss_service_no_init.get_connection()
            assert conn is not None
            # Connection should still work despite extension load failure

    def test_store_scene_embedding_with_provided_connection(
        self, vss_service_with_migration
    ):
        """Test storing scene embedding with provided connection."""
        scene_id = 100
        embedding = np.random.rand(1536).astype(np.float32)
        model = "test-model"

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service_with_migration.get_connection() as conn:
                # Add required tables for embeddings
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scene_embeddings (
                        scene_id INTEGER PRIMARY KEY,
                        embedding_model TEXT NOT NULL,
                        embedding BLOB NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_type TEXT,
                        entity_id INTEGER,
                        embedding_model TEXT,
                        dimensions INTEGER,
                        UNIQUE (entity_type, entity_id, embedding_model)
                    )
                """)

                # Store embedding with provided connection
                vss_service_with_migration.store_scene_embedding(
                    scene_id, embedding, model, conn
                )

                # Verify it was stored
                cursor = conn.execute(
                    "SELECT * FROM scene_embeddings WHERE scene_id = ?", (scene_id,)
                )
                row = cursor.fetchone()
                assert row is not None

    def test_store_bible_embedding_without_connection(self, vss_service_with_migration):
        """Test storing bible embedding without providing connection."""
        chunk_id = 200
        embedding = [float(i) for i in range(768)]  # List instead of numpy array
        model = "test-model-2"

        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Create metadata table first
            with vss_service_with_migration.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_type TEXT,
                        entity_id INTEGER,
                        embedding_model TEXT,
                        dimensions INTEGER,
                        UNIQUE (entity_type, entity_id, embedding_model)
                    )
                """)

            # Store without providing connection
            vss_service_with_migration.store_bible_embedding(chunk_id, embedding, model)

            # Verify it was stored
            with vss_service_with_migration.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM bible_embeddings WHERE chunk_id = ?", (chunk_id,)
                )
                row = cursor.fetchone()
                assert row is not None

    def test_search_similar_scenes_without_connection(self, vss_service_with_migration):
        """Test searching similar scenes without providing connection."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection's execute to return results
            mock_cursor = MagicMock()
            mock_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {
                            "id": 1,
                            "script_id": 1,
                            "heading": "Scene 1",
                            "location": "Location 1",
                            "content": "Content 1",
                            "scene_id": 1,
                            "distance": 0.1,
                        },
                        {
                            "id": 2,
                            "script_id": 1,
                            "heading": "Scene 2",
                            "location": "Location 2",
                            "content": "Content 2",
                            "scene_id": 2,
                            "distance": 0.2,
                        },
                    ]
                )
            )

            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_cursor
            mock_conn.close.return_value = None

            with patch.object(
                vss_service_with_migration, "get_connection", return_value=mock_conn
            ):
                query_embedding = np.random.rand(1536).astype(np.float32)
                results = vss_service_with_migration.search_similar_scenes(
                    query_embedding, "test-model", limit=5
                )

                assert len(results) == 2
                assert results[0]["similarity_score"] > results[1]["similarity_score"]
                # Verify connection was closed
                mock_conn.close.assert_called_once()

    def test_search_similar_bible_chunks_without_connection(
        self, vss_service_with_migration
    ):
        """Test searching similar bible chunks without providing connection."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock the connection's execute to return results
            mock_cursor = MagicMock()
            mock_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {
                            "id": 1,
                            "bible_id": 1,
                            "heading": "Chapter 1",
                            "content": "Content 1",
                            "bible_title": "Test Bible",
                            "script_id": 1,
                            "chunk_id": 1,
                            "distance": 0.15,
                            "level": 1,
                        },
                    ]
                )
            )

            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_cursor
            mock_conn.close.return_value = None

            with patch.object(
                vss_service_with_migration, "get_connection", return_value=mock_conn
            ):
                query_embedding = [0.1, 0.2, 0.3] * 512  # List instead of numpy array
                results = vss_service_with_migration.search_similar_bible_chunks(
                    query_embedding, "test-model", limit=10, script_id=1
                )

                assert len(results) == 1
                assert results[0]["bible_title"] == "Test Bible"
                assert "similarity_score" in results[0]
                # Verify connection was closed
                mock_conn.close.assert_called_once()

    def test_get_embedding_stats_without_connection(self, vss_service_with_migration):
        """Test getting embedding stats without providing connection."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock multiple cursors for different queries
            scene_cursor = MagicMock()
            scene_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {"embedding_model": "model1", "count": 10},
                        {"embedding_model": "model2", "count": 5},
                    ]
                )
            )

            bible_cursor = MagicMock()
            bible_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {"embedding_model": "model1", "count": 20},
                    ]
                )
            )

            metadata_cursor = MagicMock()
            metadata_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {"entity_type": "scene", "count": 15, "avg_dims": 1536.0},
                        {"entity_type": "bible_chunk", "count": 20, "avg_dims": 768.0},
                    ]
                )
            )

            mock_conn = MagicMock()
            mock_conn.execute.side_effect = [
                scene_cursor,
                bible_cursor,
                metadata_cursor,
            ]
            mock_conn.close.return_value = None

            with patch.object(
                vss_service_with_migration, "get_connection", return_value=mock_conn
            ):
                stats = vss_service_with_migration.get_embedding_stats()

                assert stats["scene_embeddings"]["model1"] == 10
                assert stats["scene_embeddings"]["model2"] == 5
                assert stats["bible_embeddings"]["model1"] == 20
                assert stats["metadata"]["scene"]["count"] == 15
                assert stats["metadata"]["scene"]["avg_dimensions"] == 1536.0
                # Verify connection was closed
                mock_conn.close.assert_called_once()

    def test_migrate_from_blob_storage_no_old_table(self, vss_service_with_migration):
        """Test migration when old embeddings table doesn't exist."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            scenes_migrated, bible_migrated = (
                vss_service_with_migration.migrate_from_blob_storage()
            )
            assert scenes_migrated == 0
            assert bible_migrated == 0

    def test_migrate_from_blob_storage_with_bible_data(
        self, vss_service_with_migration
    ):
        """Test migration with bible chunk embeddings."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service_with_migration.get_connection() as conn:
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

                # Add test data for bible chunks
                dimension = 768
                values = [float(i) / 1000 for i in range(dimension)]
                format_str = f"<I{dimension}f"
                blob_data = struct.pack(format_str, dimension, *values)

                conn.execute(
                    "INSERT INTO embeddings_old "
                    "(entity_type, entity_id, embedding_model, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    ("bible_chunk", 1, "test-model", blob_data),
                )

                # Mock store methods
                vss_service_with_migration.store_scene_embedding = MagicMock()
                vss_service_with_migration.store_bible_embedding = MagicMock()

                scenes_migrated, bible_migrated = (
                    vss_service_with_migration.migrate_from_blob_storage(conn)
                )

                # Verify bible embedding was migrated
                vss_service_with_migration.store_bible_embedding.assert_called_once()
                assert scenes_migrated == 0
                assert bible_migrated == 1

    def test_migrate_from_blob_storage_with_invalid_data(
        self, vss_service_with_migration
    ):
        """Test migration with invalid embedding data."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            with vss_service_with_migration.get_connection() as conn:
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

                # Add invalid data (not enough bytes for dimension)
                invalid_blob = b"invalid"

                conn.execute(
                    "INSERT INTO embeddings_old "
                    "(entity_type, entity_id, embedding_model, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    ("scene", 1, "test-model", invalid_blob),
                )

                # Mock store methods
                vss_service_with_migration.store_scene_embedding = MagicMock()
                vss_service_with_migration.store_bible_embedding = MagicMock()

                scenes_migrated, bible_migrated = (
                    vss_service_with_migration.migrate_from_blob_storage(conn)
                )

                # Migration should handle the error gracefully
                vss_service_with_migration.store_scene_embedding.assert_not_called()
                assert scenes_migrated == 0
                assert bible_migrated == 0

    def test_store_scene_embedding_commit_error(self, vss_service_with_migration):
        """Test error handling when commit fails during store."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock connection to raise error on execute
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.Error("Database locked")
            mock_conn.rollback.return_value = None
            mock_conn.close.return_value = None

            with patch.object(
                vss_service_with_migration, "get_connection", return_value=mock_conn
            ):
                with pytest.raises(DatabaseError) as exc_info:
                    vss_service_with_migration.store_scene_embedding(
                        1, np.random.rand(1536), "test-model"
                    )

                assert "Failed to store scene embedding" in str(exc_info.value)
                mock_conn.rollback.assert_called_once()
                mock_conn.close.assert_called_once()

    def test_store_bible_embedding_rollback_error(self, vss_service_with_migration):
        """Test error handling during bible embedding storage."""
        with (
            patch("scriptrag.storage.vss_service.sqlite_vec.load"),
            patch(
                "scriptrag.storage.vss_service.serialize_float32",
                side_effect=mock_serialize_float32,
            ),
        ):
            # Mock connection to raise error on commit
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock()
            mock_conn.commit.side_effect = sqlite3.Error("Commit failed")
            mock_conn.rollback.return_value = None
            mock_conn.close.return_value = None

            with patch.object(
                vss_service_with_migration, "get_connection", return_value=mock_conn
            ):
                with pytest.raises(DatabaseError) as exc_info:
                    vss_service_with_migration.store_bible_embedding(
                        1, [0.1] * 768, "test-model"
                    )

                assert "Failed to store bible embedding" in str(exc_info.value)
                mock_conn.rollback.assert_called_once()
                mock_conn.close.assert_called_once()
