"""Comprehensive tests for VSS service to improve coverage to 92%+."""

import sqlite3
import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import sqlite_vec
from sqlite_vec import serialize_float32

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.storage.vss_service import VSSService


class TestVSSServiceRealSearch:
    """Test real VSS search functionality without heavy mocking."""

    @pytest.fixture
    def real_vss_db(self, tmp_path):
        """Create a real VSS database with test data."""
        db_path = tmp_path / "test_vss.db"
        conn = sqlite3.connect(str(db_path))

        # Try to load sqlite-vec extension - skip if not available in test env
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except (AttributeError, sqlite3.OperationalError):
            # Extension not available in test env, will use mocks
            pass

        # Create tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY,
                title TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                heading TEXT,
                content TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bible_chunks (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                chunk_number INTEGER,
                content TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS script_bibles (
                script_id INTEGER,
                bible_path TEXT
            )
        """)

        # Create VSS tables
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS scene_embeddings USING vec0(
                scene_id INTEGER PRIMARY KEY,
                embedding FLOAT[1536],
                embedding_model TEXT
            )
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS bible_chunk_embeddings USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding FLOAT[1536],
                embedding_model TEXT
            )
        """)

        # Insert test data
        conn.execute("INSERT INTO scripts (id, title) VALUES (1, 'Test Script')")
        conn.execute("""
            INSERT INTO scenes (id, script_id, scene_number, heading, content)
            VALUES (1, 1, 1, 'INT. ROOM - DAY', 'Test scene content')
        """)
        conn.execute("""
            INSERT INTO scenes (id, script_id, scene_number, heading, content)
            VALUES (2, 1, 2, 'EXT. STREET - NIGHT', 'Another test scene')
        """)
        conn.execute("""
            INSERT INTO bible_chunks (id, script_id, chunk_number, content)
            VALUES (1, 1, 1, 'Bible chunk content')
        """)
        conn.execute("""
            INSERT INTO script_bibles (script_id, bible_path)
            VALUES (1, '/path/to/bible.md')
        """)

        # Create test embeddings
        embedding1 = np.random.rand(1536).astype(np.float32)
        embedding2 = np.random.rand(1536).astype(np.float32)
        embedding3 = np.random.rand(1536).astype(np.float32)

        # Insert embeddings
        conn.execute(
            "INSERT INTO scene_embeddings "
            "(scene_id, embedding, embedding_model) VALUES (?, ?, ?)",
            (1, serialize_float32(embedding1), "test-model"),
        )
        conn.execute(
            "INSERT INTO scene_embeddings "
            "(scene_id, embedding, embedding_model) VALUES (?, ?, ?)",
            (2, serialize_float32(embedding2), "test-model"),
        )
        conn.execute(
            "INSERT INTO bible_chunk_embeddings "
            "(chunk_id, embedding, embedding_model) VALUES (?, ?, ?)",
            (1, serialize_float32(embedding3), "test-model"),
        )

        conn.commit()
        conn.close()

        return db_path, embedding1, embedding2, embedding3

    def test_search_similar_scenes_real_execution(self, real_vss_db, tmp_path):
        """Test real VSS search execution with actual sqlite-vec."""
        db_path, emb1, emb2, _ = real_vss_db
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        # Search with a query embedding similar to emb1
        query_embedding = emb1 + np.random.rand(1536).astype(np.float32) * 0.1

        results = service.search_similar_scenes(
            query_embedding=query_embedding.tolist(),
            model="test-model",
            limit=2,
            script_id=1,
        )

        assert len(results) > 0
        assert results[0]["scene_id"] in [1, 2]
        assert "similarity_score" in results[0]
        assert 0 <= results[0]["similarity_score"] <= 1
        assert results[0]["heading"] in ["INT. ROOM - DAY", "EXT. STREET - NIGHT"]

    def test_search_similar_scenes_no_script_filter(self, real_vss_db, tmp_path):
        """Test scene search without script_id filter."""
        db_path, emb1, _, _ = real_vss_db
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        results = service.search_similar_scenes(
            query_embedding=emb1.tolist(), model="test-model", limit=10
        )

        assert len(results) > 0
        assert all("similarity_score" in r for r in results)

    def test_search_similar_bible_chunks_real_execution(self, real_vss_db):
        """Test real Bible chunk VSS search."""
        db_path, _, _, emb3 = real_vss_db
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        # Search with embedding similar to bible chunk
        query_embedding = emb3 + np.random.rand(1536).astype(np.float32) * 0.1

        results = service.search_similar_bible_chunks(
            query_embedding=query_embedding.tolist(),
            model="test-model",
            limit=5,
            script_id=1,
        )

        assert len(results) > 0
        assert results[0]["chunk_id"] == 1
        assert results[0]["content"] == "Bible chunk content"
        assert "similarity_score" in results[0]
        assert results[0]["bible_path"] == "/path/to/bible.md"

    def test_search_similar_bible_chunks_no_filter(self, real_vss_db):
        """Test Bible chunk search without script filter."""
        db_path, _, _, emb3 = real_vss_db
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        results = service.search_similar_bible_chunks(
            query_embedding=emb3.tolist(), model="test-model", limit=10
        )

        assert len(results) > 0
        assert all("similarity_score" in r for r in results)

    def test_distance_to_similarity_conversion(self, real_vss_db):
        """Test the distance to similarity score conversion logic."""
        db_path, emb1, _, _ = real_vss_db
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        # Create an orthogonal embedding (maximum distance)
        orthogonal_emb = np.zeros(1536, dtype=np.float32)
        orthogonal_emb[0] = 1.0

        results = service.search_similar_scenes(
            query_embedding=orthogonal_emb.tolist(), model="test-model", limit=2
        )

        # Verify similarity scores are properly calculated
        for result in results:
            assert "similarity_score" in result
            assert "distance" not in result  # Distance should be removed
            assert 0 <= result["similarity_score"] <= 1


class TestVSSServiceMigration:
    """Test VSS migration functionality."""

    def test_migrate_from_blob_no_old_table(self, tmp_path):
        """Test migration when old embeddings table doesn't exist."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create only new tables, no old embeddings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                content TEXT
            )
        """)
        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)
            migrated, failed = service.migrate_from_blob_storage()

            assert migrated == 0
            assert failed == 0

    def test_migrate_with_corrupt_embeddings(self, tmp_path):
        """Test migration with corrupted embedding data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create old embeddings table with corrupt data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                entity_id INTEGER,
                entity_type TEXT,
                embedding BLOB,
                embedding_model TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                content TEXT
            )
        """)

        # Insert valid embedding
        valid_embedding = struct.pack(f"{1536}f", *np.random.rand(1536))
        conn.execute(
            """
            INSERT INTO embeddings (entity_id, entity_type, embedding, embedding_model)
            VALUES (1, 'scene', ?, 'model-1')
        """,
            (valid_embedding,),
        )

        # Insert corrupt embedding (wrong size)
        corrupt_embedding = b"corrupt_data"
        conn.execute(
            """
            INSERT INTO embeddings (entity_id, entity_type, embedding, embedding_model)
            VALUES (2, 'scene', ?, 'model-1')
        """,
            (corrupt_embedding,),
        )

        conn.execute("INSERT INTO scenes (id, content) VALUES (1, 'Scene 1')")
        conn.execute("INSERT INTO scenes (id, content) VALUES (2, 'Scene 2')")

        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                service = VSSService(settings)
                migrated, failed = service.migrate_from_blob_storage()

                assert migrated == 1  # Only valid embedding migrated
                assert failed == 1  # Corrupt one failed

                # Check warning was logged for failed migration
                mock_logger.warning.assert_called()
                warning_call = str(mock_logger.warning.call_args)
                assert "Failed to migrate scene embedding" in warning_call

    def test_migrate_individual_failure_handling(self, tmp_path):
        """Test individual embedding migration failure handling."""
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

        conn.execute("""
            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                content TEXT
            )
        """)

        # Add embeddings
        for i in range(3):
            embedding = struct.pack(f"{1536}f", *np.random.rand(1536))
            conn.execute(
                """
                INSERT INTO embeddings
                (entity_id, entity_type, embedding, embedding_model)
                VALUES (?, 'scene', ?, 'model-1')
            """,
                (i + 1, embedding),
            )
            conn.execute(
                "INSERT INTO scenes (id, content) VALUES (?, ?)",
                (i + 1, f"Scene {i + 1}"),
            )

        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)

            # Mock serialize_float32 to fail on second embedding
            original_serialize = serialize_float32
            call_count = [0]

            def mock_serialize(arr):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise ValueError("Serialization error")
                return original_serialize(arr)

            with patch(
                "scriptrag.storage.vss_service.serialize_float32", mock_serialize
            ):
                with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                    migrated, failed = service.migrate_from_blob_storage()

                    assert migrated == 2  # Two successful
                    assert failed == 1  # One failed
                    mock_logger.warning.assert_called()


class TestVSSServiceExtensionLoading:
    """Test extension loading error scenarios."""

    def test_extension_loading_attribute_error(self, tmp_path):
        """Test when enable_load_extension is not available."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("scriptrag.storage.vss_service.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            # Simulate old SQLite without enable_load_extension
            del mock_conn.enable_load_extension
            mock_connect.return_value.__enter__.return_value = mock_conn

            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                service = VSSService(settings)

                # Should log debug message about extension loading not available
                mock_logger.debug.assert_called()
                debug_msg = str(mock_logger.debug.call_args)
                assert "extension loading not available" in debug_msg.lower()

    def test_extension_loading_operational_error(self, tmp_path):
        """Test when sqlite_vec.load raises OperationalError."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load") as mock_load:
            mock_load.side_effect = sqlite3.OperationalError("Extension load failed")

            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                service = VSSService(settings)

                # Should log debug about extension loading failure
                mock_logger.debug.assert_called()
                debug_msg = str(mock_logger.debug.call_args)
                assert "extension loading not available" in debug_msg.lower()

    def test_get_connection_extension_error_handling(self, tmp_path):
        """Test get_connection when extension loading fails."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        service = VSSService(settings)

        # First call succeeds, second call has extension error
        with patch.object(service, "_load_extensions") as mock_load:
            mock_load.side_effect = [None, AttributeError("No extension support")]

            # First connection works
            with service.get_connection() as conn:
                assert conn is not None

            # Second connection still works despite extension error
            with service.get_connection() as conn:
                assert conn is not None


class TestVSSServiceConnectionManagement:
    """Test connection cleanup and error handling."""

    def test_connection_cleanup_on_search_error(self, tmp_path):
        """Test connection is properly closed on search error."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        with patch.object(service, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.OperationalError("Query failed")
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_get_conn.return_value.__exit__ = MagicMock()

            with pytest.raises(DatabaseError):
                service.search_similar_scenes([0.1] * 1536, 10, "model")

            # Verify connection cleanup was called
            mock_get_conn.return_value.__exit__.assert_called()

    def test_add_embedding_connection_cleanup_on_error(self, tmp_path):
        """Test connection cleanup when adding embedding fails."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)
        service = VSSService(settings)

        with patch.object(service, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.IntegrityError("Constraint failed")
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_get_conn.return_value.__exit__ = MagicMock()

            with pytest.raises(DatabaseError):
                service.add_scene_embedding(1, [0.1] * 1536, "model")

            # Verify cleanup
            mock_get_conn.return_value.__exit__.assert_called()


class TestVSSServiceInitialization:
    """Test VSS initialization edge cases."""

    def test_vss_tables_already_exist_early_exit(self, tmp_path):
        """Test early exit when VSS tables already exist."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create scene_embeddings table
        conn.execute("""
            CREATE TABLE scene_embeddings (
                scene_id INTEGER,
                embedding BLOB
            )
        """)
        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch(
            "scriptrag.storage.vss_service.VSSService._initialize_vss_tables"
        ) as mock_init:
            with patch("sqlite_vec.load"):
                service = VSSService(settings)

                # Should not call _initialize_vss_tables since tables exist
                mock_init.assert_not_called()

    def test_migration_file_not_found(self, tmp_path):
        """Test when VSS migration SQL file doesn't exist."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("scriptrag.storage.vss_service.Path.exists") as mock_exists:
            mock_exists.return_value = False

            with patch("scriptrag.storage.vss_service.logger") as mock_logger:
                with pytest.raises(DatabaseError, match="VSS migration file not found"):
                    service = VSSService(settings)

    def test_migration_sql_execution_error(self, tmp_path):
        """Test SQL execution error during migration."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        # Create mock migration file with invalid SQL
        migration_content = "INVALID SQL STATEMENT;"

        with patch("scriptrag.storage.vss_service.Path.read_text") as mock_read:
            mock_read.return_value = migration_content

            with patch("scriptrag.storage.vss_service.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("sqlite_vec.load"):
                    with pytest.raises(
                        DatabaseError, match="Failed to initialize VSS tables"
                    ):
                        service = VSSService(settings)


class TestVSSServiceHelpers:
    """Test helper methods and edge cases."""

    def test_numpy_array_to_blob_conversion(self, tmp_path):
        """Test numpy array to blob conversion in add methods."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)

            # Test with numpy array input
            np_embedding = np.random.rand(1536).astype(np.float32)

            with patch.object(service, "get_connection") as mock_get_conn:
                mock_conn = MagicMock()
                mock_get_conn.return_value.__enter__.return_value = mock_conn

                service.add_scene_embedding(
                    1, np_embedding, "test-model", {"key": "value"}
                )

                # Verify serialize_float32 was called with numpy array
                call_args = mock_conn.execute.call_args[0]
                assert len(call_args) == 2  # SQL and params
                params = call_args[1]
                assert len(params) == 4  # scene_id, embedding, model, metadata

    def test_list_to_numpy_conversion(self, tmp_path):
        """Test list to numpy array conversion."""
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)

            # Test with list input
            list_embedding = [float(i) / 1536 for i in range(1536)]

            with patch.object(service, "get_connection") as mock_get_conn:
                mock_conn = MagicMock()
                mock_get_conn.return_value.__enter__.return_value = mock_conn

                service.add_scene_embedding(1, list_embedding, "test-model")

                # Verify conversion happened
                assert mock_conn.execute.called
