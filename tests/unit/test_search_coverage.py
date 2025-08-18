"""Comprehensive tests to improve coverage for search-related modules."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexOperations
from scriptrag.api.semantic_search import SemanticSearchService
from scriptrag.api.semantic_search_vss import SemanticSearchVSSService
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError, SearchError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchQuery


class TestSemanticSearchVSSCoverage:
    """Tests to improve semantic_search_vss.py coverage from 89.43% to 92%+."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create VSS search service."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        with patch("scriptrag.api.semantic_search_vss.VSSService"):
            with patch("scriptrag.api.semantic_search_vss.DatabaseOperations"):
                return SemanticSearchVSSService(settings)

    def test_search_scenes_vss_not_available(self, service):
        """Test search when VSS is not available."""
        service.vss_service = None

        result = service.search_scenes("query", limit=5)

        assert result["success"] is False
        assert "VSS service not available" in result["error"]
        assert result["results"] == []

    def test_search_scenes_no_embedding(self, service):
        """Test search when embedding generation fails."""
        service.vss_service = MagicMock()

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = None

            result = service.search_scenes("query", limit=5)

            assert result["success"] is False
            assert "Failed to generate embedding" in result["error"]

    def test_search_scenes_vss_error(self, service):
        """Test VSS search error handling."""
        service.vss_service = MagicMock()
        service.vss_service.search_similar_scenes.side_effect = Exception("VSS Error")

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            with patch("scriptrag.api.semantic_search_vss.logger") as mock_logger:
                result = service.search_scenes("query", script_id=1)

                assert result["success"] is False
                assert "VSS Error" in result["error"]
                mock_logger.error.assert_called()

    def test_search_bible_chunks_vss_not_available(self, service):
        """Test bible search when VSS is not available."""
        service.vss_service = None

        result = service.search_bible_chunks("query", script_id=1)

        assert result["success"] is False
        assert "VSS service not available" in result["error"]

    def test_search_bible_chunks_error_handling(self, service):
        """Test bible search error handling."""
        service.vss_service = MagicMock()
        service.vss_service.search_similar_bible_chunks.side_effect = Exception(
            "Search failed"
        )

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            result = service.search_bible_chunks("query", script_id=1)

            assert result["success"] is False
            assert "Search failed" in result["error"]

    def test_hybrid_search_both_methods_fail(self, service):
        """Test hybrid search when both VSS and fallback fail."""
        service.vss_service = MagicMock()
        service.vss_service.search_similar_scenes.side_effect = Exception("VSS failed")

        with patch.object(service, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            with patch.object(service, "_fallback_keyword_search") as mock_fallback:
                mock_fallback.return_value = []

                result = service.hybrid_search("query", script_id=1)

                assert (
                    result["success"] is True
                )  # Hybrid search returns empty results, not error
                assert result["results"] == []
                assert result["method"] == "hybrid"

    def test_fallback_keyword_search_error(self, service):
        """Test fallback search error handling."""
        with patch.object(service.db_ops, "execute_query") as mock_query:
            mock_query.side_effect = sqlite3.OperationalError("Query failed")

            with patch("scriptrag.api.semantic_search_vss.logger") as mock_logger:
                results = service._fallback_keyword_search("test", script_id=1)

                assert results == []
                mock_logger.error.assert_called()

    def test_get_query_embedding_llm_error(self, service):
        """Test embedding generation with LLM error."""
        with patch(
            "scriptrag.api.semantic_search_vss.create_llm_client"
        ) as mock_create:
            mock_llm = MagicMock()
            mock_llm.generate_embedding.side_effect = Exception("LLM Error")
            mock_create.return_value = mock_llm

            with patch("scriptrag.api.semantic_search_vss.logger") as mock_logger:
                embedding = service._get_query_embedding("test query")

                assert embedding is None
                mock_logger.error.assert_called()


class TestSearchEngineCoverage:
    """Tests to improve search/engine.py coverage from 71.42% to 92%+."""

    def test_search_no_results(self, tmp_path):
        """Test search with no results."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db_instance = MagicMock()
            mock_db_instance.execute_query.return_value = []
            mock_db.return_value = mock_db_instance

            engine = SearchEngine(settings)
            results = engine.search("nonexistent", limit=10)

            assert results == []

    def test_search_database_error(self, tmp_path):
        """Test search with database error."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db_instance = MagicMock()
            mock_db_instance.execute_query.side_effect = DatabaseError("DB Error")
            mock_db.return_value = mock_db_instance

            engine = SearchEngine(settings)

            with pytest.raises(SearchError, match="Database error during search"):
                engine.search("test")

    def test_search_with_filters_no_matches(self, tmp_path):
        """Test filtered search with no matches."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db_instance = MagicMock()
            mock_db_instance.execute_query.return_value = []
            mock_db.return_value = mock_db_instance

            engine = SearchEngine(settings)

            query = SearchQuery(text="test", scene_type="INT", character="JOHN")

            results = engine.search_with_filters(query)

            assert results["results"] == []
            assert results["total"] == 0

    def test_format_results_empty(self, tmp_path):
        """Test result formatting with empty results."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db.return_value = MagicMock()

            engine = SearchEngine(settings)
            formatted = engine._format_results([])

            assert formatted == []

    def test_validate_limit_edge_cases(self, tmp_path):
        """Test limit validation edge cases."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db.return_value = MagicMock()

            engine = SearchEngine(settings)

            # Test with negative limit
            assert engine._validate_limit(-1) == 10

            # Test with zero limit
            assert engine._validate_limit(0) == 10

            # Test with very large limit
            assert engine._validate_limit(1000) == 100

    def test_build_search_query_complex(self, tmp_path):
        """Test complex query building."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.search.engine.DatabaseOperations") as mock_db:
            mock_db.return_value = MagicMock()

            engine = SearchEngine(settings)

            query = SearchQuery(
                text="test",
                scene_type="INT",
                character="JOHN",
                min_scene=10,
                max_scene=20,
            )

            sql, params = engine._build_search_query(query)

            assert "scene_type" in sql
            assert "character" in sql
            assert "scene_number >=" in sql
            assert "scene_number <=" in sql
            assert len(params) >= 4


class TestIndexOperationsCoverage:
    """Tests to improve index.py coverage from 81.08% to 92%+."""

    @pytest.fixture
    def index_ops(self, tmp_path):
        """Create index operations instance."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.index.DatabaseOperations"):
            with patch("scriptrag.api.index.FountainParser"):
                return IndexOperations(settings)

    def test_index_script_file_not_found(self, index_ops):
        """Test indexing non-existent file."""
        with pytest.raises(FileNotFoundError):
            index_ops.index_script("/nonexistent/file.fountain")

    def test_index_script_parse_error(self, index_ops, tmp_path):
        """Test indexing with parse error."""
        script_file = tmp_path / "test.fountain"
        script_file.write_text("Some content")

        index_ops.parser.parse.side_effect = Exception("Parse error")

        with pytest.raises(Exception, match="Parse error"):
            index_ops.index_script(str(script_file))

    def test_reindex_script_not_found(self, index_ops):
        """Test reindexing non-existent script."""
        index_ops.db_ops.get_script.return_value = None

        result = index_ops.reindex_script(999)

        assert result is None

    def test_reindex_script_file_missing(self, index_ops):
        """Test reindexing when file is missing."""
        index_ops.db_ops.get_script.return_value = {
            "id": 1,
            "file_path": "/missing/file.fountain",
        }

        with patch("scriptrag.api.index.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            result = index_ops.reindex_script(1)

            assert result is None

    def test_batch_index_empty_directory(self, index_ops, tmp_path):
        """Test batch indexing empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        results = index_ops.batch_index(str(empty_dir))

        assert results["success"] == []
        assert results["failed"] == []

    def test_batch_index_with_failures(self, index_ops, tmp_path):
        """Test batch indexing with some failures."""
        # Create test files
        (tmp_path / "good.fountain").write_text("Title: Good")
        (tmp_path / "bad.fountain").write_text("Bad content")

        index_ops.parser.parse.side_effect = [
            {"title": "Good", "scenes": []},  # First file succeeds
            Exception("Parse error"),  # Second file fails
        ]

        results = index_ops.batch_index(str(tmp_path))

        assert len(results["success"]) == 1
        assert len(results["failed"]) == 1

    def test_update_script_metadata(self, index_ops):
        """Test metadata update."""
        index_ops.db_ops.update_script_metadata.return_value = True

        result = index_ops.update_script_metadata(1, {"key": "value"})

        assert result is True
        index_ops.db_ops.update_script_metadata.assert_called_once_with(
            1, {"key": "value"}
        )

    def test_delete_script_cascade(self, index_ops):
        """Test script deletion with cascade."""
        index_ops.db_ops.delete_script.return_value = True

        result = index_ops.delete_script(1, cascade=True)

        assert result is True
        index_ops.db_ops.delete_script.assert_called_once_with(1, cascade=True)


class TestDatabaseOperationsCoverage:
    """Tests to improve database_operations.py coverage from 82.60% to 92%+."""

    @pytest.fixture
    def db_ops(self, tmp_path):
        """Create database operations instance."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        return DatabaseOperations(settings)

    def test_execute_query_connection_error(self, db_ops):
        """Test query execution with connection error."""
        with patch.object(db_ops, "get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.OperationalError("Cannot connect")

            with pytest.raises(DatabaseError, match="Cannot connect"):
                db_ops.execute_query("SELECT 1")

    def test_add_script_duplicate(self, db_ops):
        """Test adding duplicate script."""
        # Add first script
        script_id = db_ops.add_script("test.fountain", "Test Title")
        assert script_id is not None

        # Try to add duplicate
        with pytest.raises(DatabaseError):
            db_ops.add_script("test.fountain", "Test Title")

    def test_update_scene_not_found(self, db_ops):
        """Test updating non-existent scene."""
        result = db_ops.update_scene(999, content="New content")

        assert result is False

    def test_bulk_insert_scenes_rollback(self, db_ops):
        """Test bulk insert with rollback on error."""
        scenes = [
            {"scene_number": 1, "content": "Scene 1"},
            {"scene_number": "invalid", "content": "Scene 2"},  # Will cause error
        ]

        with pytest.raises(DatabaseError):
            db_ops.bulk_insert_scenes(1, scenes)

        # Verify no scenes were inserted due to rollback
        with db_ops.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM scenes WHERE script_id = 1")
            count = cursor.fetchone()[0]
            assert count == 0


class TestSemanticSearchCoverage:
    """Tests to improve semantic_search.py coverage from 97.94% to 100%."""

    @pytest.fixture
    def search_service(self, tmp_path):
        """Create semantic search service."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.semantic_search.DatabaseOperations"):
            return SemanticSearchService(settings)

    def test_calculate_similarity_edge_cases(self, search_service):
        """Test similarity calculation edge cases."""
        # Test with identical embeddings
        emb1 = [1.0, 0.0, 0.0]
        similarity = search_service._calculate_similarity(emb1, emb1)
        assert similarity == 1.0

        # Test with orthogonal embeddings
        emb2 = [0.0, 1.0, 0.0]
        similarity = search_service._calculate_similarity(emb1, emb2)
        assert similarity == 0.0

        # Test with zero vectors
        zero = [0.0, 0.0, 0.0]
        similarity = search_service._calculate_similarity(zero, zero)
        assert similarity == 0.0  # Should handle zero division

    def test_search_similar_embeddings_struct_error(self, search_service):
        """Test embedding unpacking with struct error."""
        search_service.db_ops.get_all_scene_embeddings.return_value = [
            {
                "scene_id": 1,
                "embedding": b"invalid_data",  # Invalid binary data
                "content": "Test",
            }
        ]

        with patch("scriptrag.api.semantic_search.logger") as mock_logger:
            results = search_service.search_similar(
                query_embedding=[0.1, 0.2, 0.3], limit=5
            )

            assert results == []
            mock_logger.error.assert_called()

    def test_search_with_empty_database(self, search_service):
        """Test search with no embeddings in database."""
        search_service.db_ops.get_all_scene_embeddings.return_value = []

        results = search_service.search_similar([0.1, 0.2, 0.3], limit=5)

        assert results == []
