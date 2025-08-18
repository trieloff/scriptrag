"""Final tests to push coverage above 92% for all touched files."""

import sqlite3
import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.api.index import IndexOperations
from scriptrag.api.semantic_search_vss import SemanticSearchVSSService
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.storage.vss_service import VSSService


class TestVSSServiceFinalCoverage:
    """Final tests to reach 92% coverage for VSS service."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create VSS service."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        with patch("sqlite_vec.load"):
            return VSSService(settings)

    def test_search_bible_chunks_complex_query(self, service):
        """Test Bible chunk search with complex JOIN."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock results with bible path
        mock_cursor.fetchall.return_value = [
            {
                "chunk_id": 1,
                "chunk_number": 1,
                "content": "Bible content",
                "bible_path": "/path/to/bible.md",
                "distance": 0.3,
                "metadata": '{"section": "intro"}',
            }
        ]
        mock_conn.execute.return_value = mock_cursor

        # Test with script_id filter
        results = service.search_similar_bible_chunks(
            query_embedding=[0.1] * 1536,
            model="test-model",
            limit=5,
            script_id=1,
            conn=mock_conn,
        )

        assert len(results) == 1
        assert results[0]["bible_path"] == "/path/to/bible.md"
        assert results[0]["similarity_score"] == 0.85  # 1.0 - (0.3 / 2)

        # Verify the query includes proper JOINs
        call_args = mock_conn.execute.call_args[0]
        query_sql = call_args[0]
        assert "script_bibles" in query_sql or "bible_chunks" in query_sql

    def test_migration_bible_chunks(self, tmp_path):
        """Test migration of bible chunk embeddings."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create necessary tables
        conn.execute("""
            CREATE TABLE embeddings (
                entity_id INTEGER,
                entity_type TEXT,
                embedding BLOB,
                embedding_model TEXT,
                metadata TEXT
            )
        """)
        conn.execute("CREATE TABLE bible_chunks (id INTEGER PRIMARY KEY)")

        # Add bible chunk embedding
        embedding_data = struct.pack(f"{1536}f", *np.random.rand(1536))
        conn.execute(
            "INSERT INTO embeddings VALUES (1, 'bible_chunk', ?, 'model', NULL)",
            (embedding_data,),
        )
        conn.execute("INSERT INTO bible_chunks VALUES (1)")

        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)

        with patch("sqlite_vec.load"):
            service = VSSService(settings)
            migrated, failed = service.migrate_from_blob_storage()

            assert migrated >= 1  # At least the bible chunk

    def test_connection_error_handling_in_search(self, service):
        """Test connection error handling in search methods."""
        with patch.object(service, "get_connection") as mock_get:
            mock_get.side_effect = sqlite3.OperationalError("Cannot connect")

            with pytest.raises(DatabaseError):
                service.search_similar_scenes([0.1] * 1536, "model", 5)


class TestEmbeddingServiceFinalCoverage:
    """Final tests for embedding service coverage."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create embedding service."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.embedding_service.DatabaseOperations"):
            with patch(
                "scriptrag.api.embedding_service.create_llm_client"
            ) as mock_create:
                mock_llm = MagicMock()
                mock_llm.generate_embedding.return_value = [0.1] * 1536
                mock_create.return_value = mock_llm
                return EmbeddingService(settings)

    def test_embedding_generation_batch_processing(self, service):
        """Test batch embedding generation."""
        service.db_ops.get_script_scenes.return_value = [
            {"id": i, "content": f"Scene {i}", "heading": f"SCENE {i}"}
            for i in range(1, 11)  # 10 scenes
        ]

        with patch.object(service.llm_client, "generate_embedding") as mock_gen:
            mock_gen.return_value = [0.1] * 1536

            result = service.generate_scene_embeddings(1, batch_size=5)

            # Should process all 10 scenes
            assert mock_gen.call_count == 10

    def test_verify_embeddings_with_bible(self, service):
        """Test embedding verification including bible chunks."""
        service.db_ops.execute_query.side_effect = [
            [{"scene_count": 10, "embedded_count": 8}],  # Scene stats
            [{"chunk_count": 5, "embedded_count": 5}],  # Bible stats
        ]

        result = service.verify_embeddings(1)

        assert result["scenes"]["total"] == 10
        assert result["scenes"]["embedded"] == 8
        assert result["bible_chunks"]["total"] == 5
        assert result["bible_chunks"]["embedded"] == 5

    def test_embedding_model_check_current_matches(self, service):
        """Test when current model matches existing embeddings."""
        service.db_ops.execute_query.return_value = [
            {"embedding_model": "test-model", "count": 10}
        ]

        service.settings.embedding_model = "test-model"

        result = service.check_embedding_model(1)

        assert result["has_embeddings"] is True
        assert result["needs_regeneration"] is False
        assert result["current_model"] == "test-model"


class TestSemanticSearchVSSFinalCoverage:
    """Final tests for semantic search VSS coverage."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create semantic search VSS service."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        with patch("scriptrag.api.semantic_search_vss.VSSService"):
            with patch("scriptrag.api.semantic_search_vss.DatabaseOperations"):
                return SemanticSearchVSSService(settings)

    def test_hybrid_search_vss_only_success(self, service):
        """Test hybrid search when only VSS succeeds."""
        service.vss_service = MagicMock()
        service.vss_service.search_similar_scenes.return_value = [
            {"scene_id": 1, "content": "Scene 1", "similarity_score": 0.9}
        ]

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            result = service.hybrid_search("query", script_id=1)

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["method"] == "hybrid"

    def test_fallback_search_success(self, service):
        """Test fallback keyword search success."""
        service.db_ops.execute_query.return_value = [
            {"id": 1, "content": "Test scene", "heading": "INT. ROOM"}
        ]

        results = service._fallback_keyword_search("test", script_id=1, limit=5)

        assert len(results) == 1
        assert results[0]["content"] == "Test scene"

    def test_search_scenes_with_embeddings(self, service):
        """Test scene search with successful embedding generation."""
        service.vss_service = MagicMock()
        service.vss_service.search_similar_scenes.return_value = [
            {"scene_id": 1, "content": "Scene", "similarity_score": 0.85}
        ]

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            result = service.search_scenes("query text", limit=10)

            assert result["success"] is True
            assert len(result["results"]) == 1


class TestIndexOperationsFinalCoverage:
    """Final tests for index operations coverage."""

    @pytest.fixture
    def index_ops(self, tmp_path):
        """Create index operations."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        with patch("scriptrag.api.index.DatabaseOperations"):
            with patch("scriptrag.api.index.FountainParser"):
                return IndexOperations(settings)

    def test_get_script_stats(self, index_ops):
        """Test getting script statistics."""
        index_ops.db_ops.execute_query.return_value = [
            {
                "script_id": 1,
                "title": "Test Script",
                "scene_count": 10,
                "character_count": 5,
            }
        ]

        stats = index_ops.get_script_stats(1)

        assert stats["script_id"] == 1
        assert stats["scene_count"] == 10

    def test_update_scene_indices(self, index_ops):
        """Test updating scene indices."""
        index_ops.db_ops.execute_query.return_value = []

        result = index_ops.update_scene_indices(1)

        assert result is True

    def test_validate_script_structure(self, index_ops):
        """Test script structure validation."""
        index_ops.db_ops.get_script_scenes.return_value = [
            {"scene_number": 1, "heading": "INT. ROOM"},
            {"scene_number": 2, "heading": "EXT. STREET"},
        ]

        result = index_ops.validate_script_structure(1)

        assert result["valid"] is True
        assert result["scene_count"] == 2


class TestSearchEngineFinalCoverage:
    """Final tests for search engine coverage."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create search engine."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        with patch("scriptrag.search.engine.DatabaseOperations"):
            return SearchEngine(settings)

    def test_search_with_complex_query(self, engine):
        """Test search with complex query parameters."""
        engine.db_ops.execute_query.return_value = [
            {"id": 1, "content": "Test", "heading": "INT. ROOM", "score": 0.9}
        ]

        from scriptrag.search.models import SearchQuery

        query = SearchQuery(
            text="test", scene_type="INT", character="JOHN", min_scene=1, max_scene=10
        )

        results = engine.search_with_filters(query)

        assert results["total"] == 1
        assert results["results"][0]["id"] == 1

    def test_search_empty_query(self, engine):
        """Test search with empty query."""
        results = engine.search("", limit=10)

        assert results == []

    def test_search_special_characters(self, engine):
        """Test search with special characters."""
        engine.db_ops.execute_query.return_value = []

        results = engine.search('test\'s "quote" & more', limit=5)

        assert results == []
