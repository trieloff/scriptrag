"""Additional tests to improve coverage for various modules."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexingService
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError, ScriptRAGError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.semantic_adapter import SemanticSearchAdapter


class TestIndexingServiceCoverage:
    """Additional tests for IndexingService coverage."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return ScriptRAGSettings()

    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations."""
        db_ops = MagicMock(spec=DatabaseOperations)
        db_ops.transaction = MagicMock()
        db_ops.execute_query = Mock()
        db_ops.fetch_one = Mock()
        db_ops.fetch_all = Mock()
        return db_ops

    @pytest.fixture
    def indexing_service(self, settings, mock_db_ops):
        """Create indexing service with mocks."""
        with patch("scriptrag.api.index.DatabaseOperations", return_value=mock_db_ops):
            service = IndexingService(settings)
            service.db_ops = mock_db_ops
            return service

    @pytest.mark.asyncio
    async def test_index_script_error_handling(self, indexing_service, mock_db_ops):
        """Test error handling in index_script."""
        mock_db_ops.execute_query.side_effect = DatabaseError("Database error")

        with pytest.raises(ScriptRAGError) as exc_info:
            await indexing_service.index_script("test.fountain")

        assert "Failed to index script" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_scene_index_batch_error(self, indexing_service, mock_db_ops):
        """Test error handling in batch scene indexing."""
        scenes = [
            {"id": 1, "content": "Scene 1"},
            {"id": 2, "content": "Scene 2"},
        ]

        # Mock database error during batch update
        mock_db_ops.execute_query.side_effect = DatabaseError("Batch update failed")

        with pytest.raises(ScriptRAGError):
            await indexing_service.update_scene_indices(scenes)

    @pytest.mark.asyncio
    async def test_reindex_all_scripts(self, indexing_service, mock_db_ops):
        """Test reindexing all scripts."""
        # Mock scripts in database
        mock_db_ops.fetch_all.return_value = [
            {"id": 1, "title": "Script 1"},
            {"id": 2, "title": "Script 2"},
        ]

        # Mock successful reindexing
        indexing_service.index_script = AsyncMock(return_value={"scenes": 10})

        result = await indexing_service.reindex_all()

        assert result["scripts_reindexed"] == 2
        assert indexing_service.index_script.call_count == 2

    def test_get_indexing_stats(self, indexing_service, mock_db_ops):
        """Test getting indexing statistics."""
        # Mock statistics
        mock_db_ops.fetch_one.side_effect = [
            {"total_scripts": 5},
            {"total_scenes": 100},
            {"indexed_scenes": 95},
        ]

        stats = indexing_service.get_indexing_stats()

        assert stats["total_scripts"] == 5
        assert stats["total_scenes"] == 100
        assert stats["indexed_scenes"] == 95
        assert stats["coverage"] == 0.95


class TestDatabaseOperationsCoverage:
    """Additional tests for DatabaseOperations coverage."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = ScriptRAGSettings()
        settings.database_path = ":memory:"
        return settings

    @pytest.fixture
    def db_ops(self, settings):
        """Create database operations."""
        return DatabaseOperations(settings)

    def test_transaction_rollback_on_error(self, db_ops):
        """Test transaction rollback on error."""
        with pytest.raises(Exception):  # noqa: B017
            with db_ops.transaction() as conn:
                # Execute some operation
                conn.execute("CREATE TABLE test (id INTEGER)")
                # Raise an error
                raise Exception("Test error")

        # Table should not exist due to rollback
        with db_ops.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
            )
            assert cursor.fetchone() is None

    def test_execute_with_params(self, db_ops):
        """Test executing query with parameters."""
        with db_ops.transaction() as conn:
            # Create test table
            conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")

            # Insert with parameters
            db_ops.execute_query(
                "INSERT INTO test (id, name) VALUES (?, ?)", (1, "Test"), conn
            )

            # Verify
            cursor = conn.execute("SELECT * FROM test WHERE id = ?", (1,))
            row = cursor.fetchone()
            assert row[1] == "Test"

    def test_fetch_all_empty(self, db_ops):
        """Test fetch_all with no results."""
        with db_ops.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            results = db_ops.fetch_all("SELECT * FROM test", conn=conn)
            assert results == []

    def test_connection_error_handling(self, settings):
        """Test handling connection errors."""
        settings.database_path = "/invalid/path/database.db"
        db_ops = DatabaseOperations(settings)

        with pytest.raises(DatabaseError):
            with db_ops.get_connection():
                pass


class TestSearchEngineCoverage:
    """Additional tests for SearchEngine coverage."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return ScriptRAGSettings()

    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations."""
        db_ops = MagicMock()
        db_ops.fetch_all = Mock(return_value=[])
        db_ops.fetch_one = Mock(return_value=None)
        return db_ops

    @pytest.fixture
    def search_engine(self, settings, mock_db_ops):
        """Create search engine with mocks."""
        with patch(
            "scriptrag.search.engine.DatabaseOperations", return_value=mock_db_ops
        ):
            engine = SearchEngine(settings)
            engine.db_ops = mock_db_ops
            return engine

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_engine, mock_db_ops):
        """Test search with various filters."""
        # Mock search results
        mock_db_ops.fetch_all.return_value = [
            {
                "id": 1,
                "heading": "INT. ROOM - DAY",
                "content": "Test scene",
                "rank": 0.9,
            }
        ]

        results = await search_engine.search(
            query="test",
            script_id=1,
            filters={
                "location": "ROOM",
                "time_of_day": "DAY",
            },
        )

        assert len(results) == 1
        # Verify filters were applied
        call_args = mock_db_ops.fetch_all.call_args
        query = call_args[0][0]
        assert "location" in query.lower() or "WHERE" in query

    @pytest.mark.asyncio
    async def test_search_error_handling(self, search_engine, mock_db_ops):
        """Test search error handling."""
        mock_db_ops.fetch_all.side_effect = DatabaseError("Search failed")

        with pytest.raises(ScriptRAGError) as exc_info:
            await search_engine.search("test query")

        assert "Search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, search_engine):
        """Test hybrid search combining keyword and semantic."""
        search_engine.use_semantic_search = True
        search_engine.semantic_adapter = MagicMock()
        search_engine.semantic_adapter.search = AsyncMock(return_value=[])

        results = await search_engine.hybrid_search(
            query="test",
            keyword_weight=0.5,
            semantic_weight=0.5,
        )

        assert results == []
        search_engine.semantic_adapter.search.assert_called_once()


class TestSemanticAdapterCoverage:
    """Additional tests for SemanticSearchAdapter coverage."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return ScriptRAGSettings()

    @pytest.fixture
    def mock_semantic_service(self):
        """Create mock semantic search service."""
        service = MagicMock()
        service.search_similar_scenes = AsyncMock(return_value=[])
        service.find_related_scenes = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def adapter(self, settings, mock_semantic_service):
        """Create semantic adapter with mocks."""
        with patch(
            "scriptrag.search.semantic_adapter.SemanticSearchVSS",
            return_value=mock_semantic_service,
        ):
            adapter = SemanticSearchAdapter(settings)
            adapter.semantic_service = mock_semantic_service
            return adapter

    @pytest.mark.asyncio
    async def test_search_with_results(self, adapter, mock_semantic_service):
        """Test semantic search with results."""
        mock_semantic_service.search_similar_scenes.return_value = [
            {
                "id": 1,
                "heading": "Scene 1",
                "similarity_score": 0.9,
            }
        ]

        results = await adapter.search("test query", limit=5)

        assert len(results) == 1
        assert results[0]["similarity_score"] == 0.9

    @pytest.mark.asyncio
    async def test_search_error_handling(self, adapter, mock_semantic_service):
        """Test semantic search error handling."""
        mock_semantic_service.search_similar_scenes.side_effect = Exception(
            "Search error"
        )

        # Should handle error and return empty results
        results = await adapter.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_find_similar_with_scene_id(self, adapter, mock_semantic_service):
        """Test finding similar scenes by scene ID."""
        mock_semantic_service.find_related_scenes.return_value = [
            {
                "id": 2,
                "heading": "Similar Scene",
                "similarity_score": 0.8,
            }
        ]

        results = await adapter.find_similar(scene_id=1, limit=3)

        assert len(results) == 1
        mock_semantic_service.find_related_scenes.assert_called_once_with(
            scene_id=1,
            query=None,
            limit=3,
        )

    @pytest.mark.asyncio
    async def test_find_similar_with_query(self, adapter, mock_semantic_service):
        """Test finding similar scenes by query."""
        results = await adapter.find_similar(query="test query", limit=3)

        mock_semantic_service.find_related_scenes.assert_called_once_with(
            scene_id=None,
            query="test query",
            limit=3,
        )

    def test_adapter_initialization(self, settings):
        """Test adapter initialization."""
        with patch("scriptrag.search.semantic_adapter.SemanticSearchVSS") as mock_vss:
            adapter = SemanticSearchAdapter(settings)

            assert adapter.settings == settings
            mock_vss.assert_called_once_with(settings)
