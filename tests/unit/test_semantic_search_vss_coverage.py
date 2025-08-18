"""Additional tests for SemanticSearchVSS to improve coverage."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from scriptrag.api.semantic_search_vss import SemanticSearchVSS
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def settings():
    """Create test settings."""
    return ScriptRAGSettings()


@pytest.fixture
def mock_db_ops():
    """Create mock database operations."""
    db_ops = MagicMock()
    db_ops.transaction = MagicMock()
    db_ops.execute_query = Mock()
    db_ops.fetch_one = Mock()
    db_ops.fetch_all = Mock()
    return db_ops


@pytest.fixture
def mock_vss_service():
    """Create mock VSS service."""
    service = MagicMock()
    service.store_scene_embedding = Mock()
    service.store_bible_embedding = Mock()
    service.search_similar_scenes = Mock(return_value=[])
    service.search_similar_bible_chunks = Mock(return_value=[])
    service.migrate_from_blob_storage = Mock(return_value=(0, 0))
    service.get_embedding_stats = Mock(return_value={})
    return service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = MagicMock()
    service.default_model = "test-model"
    service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    service.generate_scene_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return service


@pytest.fixture
def search_service(settings, mock_db_ops, mock_vss_service, mock_embedding_service):
    """Create semantic search VSS service with mocks."""
    # Pass mocks directly to constructor
    return SemanticSearchVSS(
        settings, vss_service=mock_vss_service, embedding_service=mock_embedding_service
    )


class TestSemanticSearchVSSExtended:
    """Extended tests for SemanticSearchVSS coverage."""

    @pytest.mark.asyncio
    async def test_search_similar_scenes_with_error(
        self, search_service, mock_vss_service
    ):
        """Test error handling in search_similar_scenes."""
        # Mock VSS service to raise error
        mock_vss_service.search_similar_scenes.side_effect = Exception("VSS error")

        # Should handle error gracefully and return empty list
        results = await search_service.search_similar_scenes(
            query="test query",
            script_id=1,
            limit=10,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_similar_scenes_custom_model(
        self, search_service, mock_embedding_service, mock_vss_service
    ):
        """Test searching with custom embedding model."""
        custom_model = "custom-model"
        query = "test query"

        # Mock results
        mock_vss_service.search_similar_scenes.return_value = [
            {
                "id": 1,
                "heading": "Scene 1",
                "content": "Content 1",
                "similarity_score": 0.9,
            }
        ]

        # Search with custom model
        results = await search_service.search_similar_scenes(
            query=query,
            script_id=None,
            limit=5,
            model=custom_model,
        )

        # Should use custom model
        mock_embedding_service.generate_embedding.assert_called_once_with(
            query, custom_model
        )
        mock_vss_service.search_similar_scenes.assert_called_once()
        call_args = mock_vss_service.search_similar_scenes.call_args
        assert call_args[1]["model"] == custom_model

    @pytest.mark.asyncio
    async def test_find_related_scenes_query_mode(
        self, search_service, mock_embedding_service, mock_vss_service
    ):
        """Test finding related scenes using query mode."""
        query = "test query"

        # Mock results
        mock_vss_service.search_similar_scenes.return_value = [
            {
                "id": 1,
                "heading": "Scene 1",
                "content": "Content 1",
                "similarity_score": 0.9,
            }
        ]

        # Find related scenes with query
        results = await search_service.find_related_scenes(
            scene_id=None,
            query=query,
            limit=5,
        )

        assert len(results) == 1
        mock_embedding_service.generate_embedding.assert_called_once_with(
            query, "test-model"
        )

    @pytest.mark.asyncio
    async def test_find_related_scenes_no_input(self, search_service):
        """Test finding related scenes with no scene_id or query."""
        # Should raise error
        with pytest.raises(ValueError) as exc_info:
            await search_service.find_related_scenes(
                scene_id=None,
                query=None,
            )
        assert "Either scene_id or query must be provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_similar_bible_chunks_with_error(
        self, search_service, mock_vss_service
    ):
        """Test error handling in search_similar_bible_chunks."""
        # Mock VSS service to raise error
        mock_vss_service.search_similar_bible_chunks.side_effect = Exception(
            "VSS error"
        )

        # Should handle error gracefully and return empty list
        results = await search_service.search_similar_bible_chunks(
            query="test query",
            script_id=1,
            limit=10,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_similar_bible_chunks_custom_model(
        self, search_service, mock_embedding_service, mock_vss_service
    ):
        """Test searching bible chunks with custom model."""
        custom_model = "custom-model"
        query = "test query"

        # Mock results
        mock_vss_service.search_similar_bible_chunks.return_value = [
            {
                "id": 1,
                "heading": "Chapter 1",
                "content": "Content 1",
                "similarity_score": 0.9,
            }
        ]

        # Search with custom model
        results = await search_service.search_similar_bible_chunks(
            query=query,
            script_id=None,
            limit=5,
            model=custom_model,
        )

        # Should use custom model
        mock_embedding_service.generate_embedding.assert_called_once_with(
            query, custom_model
        )
        mock_vss_service.search_similar_bible_chunks.assert_called_once()
        call_args = mock_vss_service.search_similar_bible_chunks.call_args
        assert call_args[1]["model"] == custom_model

    def test_get_embedding_stats(self, search_service, mock_vss_service):
        """Test getting embedding statistics."""
        # Mock stats
        mock_stats = {
            "scene_embeddings": {"test-model": 10},
            "bible_embeddings": {"test-model": 5},
        }
        mock_vss_service.get_embedding_stats.return_value = mock_stats

        # Get stats
        stats = search_service.get_embedding_stats()

        assert stats == mock_stats
        mock_vss_service.get_embedding_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_migrate_to_vss_with_error(self, search_service, mock_vss_service):
        """Test migration error handling."""
        # Mock migration error
        mock_vss_service.migrate_from_blob_storage.side_effect = Exception(
            "Migration failed"
        )

        # Should handle error and return (0, 0)
        scenes, bible = await search_service.migrate_to_vss()

        assert scenes == 0
        assert bible == 0
