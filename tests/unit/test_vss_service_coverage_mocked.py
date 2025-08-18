"""Coverage tests for VSS service with mocked database operations."""

import sqlite3
import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.storage.vss_service import VSSService


class TestVSSServiceSearchCoverage:
    """Test VSS search methods to improve coverage."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create VSS service with mocked connection."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("sqlite_vec.load"):
            return VSSService(settings)

    def test_search_similar_scenes_with_results(self, service):
        """Test scene search with actual results returned."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock query results
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "scene_id": 1,
                "scene_number": 1,
                "heading": "INT. ROOM",
                "content": "Test scene",
                "distance": 0.5,
                "metadata": '{"key": "value"}',
            },
            {
                "id": 2,
                "scene_id": 2,
                "scene_number": 2,
                "heading": "EXT. STREET",
                "content": "Another scene",
                "distance": 0.8,
                "metadata": None,
            },
        ]
        mock_conn.execute.return_value = mock_cursor

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_scenes(
                query_embedding=[0.1] * 1536, model="test-model", limit=2, script_id=1
            )

            assert len(results) == 2
            assert results[0]["similarity_score"] == 0.75  # 1.0 - (0.5 / 2)
            assert results[1]["similarity_score"] == 0.6  # 1.0 - (0.8 / 2)
            assert "distance" not in results[0]  # Should be removed

            # Verify query was executed with correct params
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0]
            assert "script_id" in str(call_args[0]).lower()

    def test_search_similar_scenes_no_script_filter(self, service):
        """Test scene search without script_id filter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "scene_id": 1, "distance": 0.3, "content": "Test"}
        ]
        mock_conn.execute.return_value = mock_cursor

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_scenes(
                query_embedding=np.random.rand(1536).astype(np.float32),
                model="test-model",
                limit=5,
            )

            assert len(results) == 1
            assert results[0]["similarity_score"] == 0.85  # 1.0 - (0.3 / 2)

            # Verify query doesn't include script_id filter
            call_args = mock_conn.execute.call_args[0]
            assert (
                "script_id" not in str(call_args[0]).lower()
                or "AND s.script_id" not in call_args[0]
            )

    def test_search_similar_bible_chunks_with_results(self, service):
        """Test Bible chunk search with results."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "chunk_id": 1,
                "chunk_number": 1,
                "content": "Bible content",
                "bible_path": "/path/to/bible.md",
                "distance": 0.2,
                "metadata": '{"section": "intro"}',
            }
        ]
        mock_conn.execute.return_value = mock_cursor

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_bible_chunks(
                query_embedding=[0.1] * 1536, model="test-model", limit=3, script_id=1
            )

            assert len(results) == 1
            assert results[0]["similarity_score"] == 0.9  # 1.0 - (0.2 / 2)
            assert results[0]["bible_path"] == "/path/to/bible.md"
            assert "distance" not in results[0]

    def test_search_similar_bible_chunks_no_filter(self, service):
        """Test Bible chunk search without script filter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_bible_chunks(
                query_embedding=np.ones(1536, dtype=np.float32),
                model="test-model",
                limit=10,
            )

            assert results == []

            # Verify query was for all chunks
            call_args = mock_conn.execute.call_args[0]
            query_sql = call_args[0]
            # The unfiltered query joins differently
            assert "bible_chunk_embeddings" in query_sql

    def test_distance_to_similarity_conversion_edge_cases(self, service):
        """Test edge cases in distance to similarity conversion."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Test with distance = 0 (identical vectors)
        mock_cursor.fetchall.return_value = [
            {"id": 1, "scene_id": 1, "distance": 0.0, "content": "Identical"}
        ]
        mock_conn.execute.return_value = mock_cursor

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_scenes(
                query_embedding=[1.0] * 1536, model="test", limit=1
            )

            assert results[0]["similarity_score"] == 1.0

        # Test with distance = 2 (maximum distance)
        mock_cursor.fetchall.return_value = [
            {"id": 2, "scene_id": 2, "distance": 2.0, "content": "Opposite"}
        ]

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            results = service.search_similar_scenes(
                query_embedding=[1.0] * 1536, model="test", limit=1
            )

            assert results[0]["similarity_score"] == 0.0

    def test_search_connection_management(self, service):
        """Test that connections are properly managed in search methods."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        # Test with external connection (should not close)
        results = service.search_similar_scenes(
            query_embedding=[0.1] * 1536,
            model="test",
            limit=5,
            conn=mock_conn,  # Provide external connection
        )

        assert results == []
        mock_conn.close.assert_not_called()

        # Test without external connection (should close)
        with patch.object(service, "get_connection") as mock_get:
            mock_conn_auto = MagicMock()
            mock_cursor_auto = MagicMock()
            mock_cursor_auto.fetchall.return_value = []
            mock_conn_auto.execute.return_value = mock_cursor_auto
            mock_get.return_value = mock_conn_auto

            results = service.search_similar_scenes(
                query_embedding=[0.1] * 1536, model="test", limit=5
            )

            mock_conn_auto.close.assert_called_once()

    def test_search_error_handling(self, service):
        """Test error handling in search methods."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("Search failed")

        with patch.object(service, "get_connection") as mock_get:
            mock_get.return_value = mock_conn

            with pytest.raises(DatabaseError, match="Failed to search similar scenes"):
                service.search_similar_scenes(
                    query_embedding=[0.1] * 1536, model="test", limit=5
                )

            # Verify connection was closed despite error
            mock_conn.close.assert_called()


class TestVSSServiceMigrationCoverage:
    """Test migration functionality for coverage."""

    def test_migrate_no_old_embeddings_table(self, tmp_path):
        """Test migration when old table doesn't exist."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE scenes (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)
            migrated, failed = service.migrate_from_blob_storage()

            assert migrated == 0
            assert failed == 0

    def test_migrate_with_corrupt_data(self, tmp_path):
        """Test migration with corrupted embeddings."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create tables
        conn.execute("""
            CREATE TABLE embeddings (
                entity_id INTEGER,
                entity_type TEXT,
                embedding BLOB,
                embedding_model TEXT,
                metadata TEXT
            )
        """)
        conn.execute("CREATE TABLE scenes (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE bible_chunks (id INTEGER PRIMARY KEY)")

        # Add valid embedding
        valid_blob = struct.pack(f"{1536}f", *np.random.rand(1536))
        conn.execute(
            "INSERT INTO embeddings VALUES (1, 'scene', ?, 'model', NULL)",
            (valid_blob,),
        )

        # Add corrupt embedding
        conn.execute(
            "INSERT INTO embeddings VALUES (2, 'scene', ?, 'model', NULL)",
            (b"corrupt",),
        )

        # Add scenes
        conn.execute("INSERT INTO scenes VALUES (1)")
        conn.execute("INSERT INTO scenes VALUES (2)")

        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                service = VSSService(settings)
                migrated, failed = service.migrate_from_blob_storage()

                assert migrated == 1
                assert failed == 1
                mock_logger.warning.assert_called()

    def test_migrate_serialization_error(self, tmp_path):
        """Test migration with serialization errors."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE embeddings (
                entity_id INTEGER,
                entity_type TEXT,
                embedding BLOB,
                embedding_model TEXT
            )
        """)
        conn.execute("CREATE TABLE scenes (id INTEGER PRIMARY KEY)")

        # Add valid embedding data
        valid_blob = struct.pack(f"{1536}f", *np.random.rand(1536))
        conn.execute(
            "INSERT INTO embeddings VALUES (1, 'scene', ?, 'model')", (valid_blob,)
        )
        conn.execute("INSERT INTO scenes VALUES (1)")

        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch(
                "scriptrag.storage.vss_service.serialize_float32"
            ) as mock_serialize:
                mock_serialize.side_effect = ValueError("Cannot serialize")

                with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                    service = VSSService(settings)
                    migrated, failed = service.migrate_from_blob_storage()

                    assert migrated == 0
                    assert failed == 1
                    mock_logger.warning.assert_called()


class TestVSSServiceInitialization:
    """Test VSS initialization and extension loading."""

    def test_extension_loading_attribute_error(self, tmp_path):
        """Test when SQLite doesn't support extensions."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("scriptrag.storage.vss_service.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            # Remove enable_load_extension to simulate old SQLite
            del mock_conn.enable_load_extension
            mock_connect.return_value = mock_conn

            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                with patch.object(VSSService, "_initialize_vss_tables"):
                    service = VSSService(settings)

                    # Should log debug message
                    mock_logger.debug.assert_called()
                    assert (
                        "extension loading not available"
                        in str(mock_logger.debug.call_args).lower()
                    )

    def test_extension_loading_operational_error(self, tmp_path):
        """Test when sqlite_vec.load fails."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load") as mock_load:
            mock_load.side_effect = sqlite3.OperationalError("Cannot load extension")

            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                with patch.object(VSSService, "_initialize_vss_tables"):
                    service = VSSService(settings)

                    mock_logger.debug.assert_called()
                    assert (
                        "extension loading not available"
                        in str(mock_logger.debug.call_args).lower()
                    )

    def test_vss_tables_exist_skip_init(self, tmp_path):
        """Test skipping initialization when tables exist."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE scene_embeddings (id INTEGER)")
        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch.object(VSSService, "_initialize_vss_tables") as mock_init:
                service = VSSService(settings)

                # Should not initialize since table exists
                mock_init.assert_not_called()

    def test_migration_file_not_found(self, tmp_path):
        """Test when migration SQL file is missing."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch("scriptrag.storage.vss_service.Path.exists") as mock_exists:
                mock_exists.return_value = False

                with pytest.raises(DatabaseError, match="VSS migration file not found"):
                    service = VSSService(settings)

    def test_migration_sql_error(self, tmp_path):
        """Test SQL execution error during migration."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch("scriptrag.storage.vss_service.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("scriptrag.storage.vss_service.Path.read_text") as mock_read:
                    mock_read.return_value = "INVALID SQL STATEMENT;"

                    with pytest.raises(
                        DatabaseError, match="Failed to initialize VSS tables"
                    ):
                        service = VSSService(settings)
