"""Unit tests for semantic search VSS service."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from scriptrag.api.semantic_search_vss import (
    BibleSearchResult,
    SceneSearchResult,
    SemanticSearchVSS,
)
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = ":memory:"
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_cache_size = -2000
    settings.database_temp_store = "MEMORY"
    settings.database_foreign_keys = True
    settings.database_timeout = 30.0
    return settings


@pytest.fixture
def mock_vss_service():
    """Create mock VSS service."""
    vss = MagicMock(spec=object)
    vss.get_connection.return_value.__enter__ = MagicMock(spec=object)
    vss.get_connection.return_value.__exit__ = MagicMock(spec=object)
    return vss


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    embedding_service = MagicMock(spec=object)
    embedding_service.default_model = "text-embedding-3-small"
    embedding_service.generate_embedding = AsyncMock(
        return_value=list(np.random.rand(1536))
    )
    embedding_service.generate_scene_embedding = AsyncMock(
        return_value=list(np.random.rand(1536))
    )
    embedding_service.save_embedding_to_lfs = MagicMock(spec=object)
    return embedding_service


@pytest.fixture
def semantic_search_vss(mock_settings, mock_vss_service, mock_embedding_service):
    """Create semantic search VSS service."""
    return SemanticSearchVSS(
        settings=mock_settings,
        vss_service=mock_vss_service,
        embedding_service=mock_embedding_service,
    )


class TestSemanticSearchVSS:
    """Test semantic search VSS functionality."""

    @pytest.mark.asyncio
    async def test_search_similar_scenes(self, semantic_search_vss, mock_vss_service):
        """Test searching for similar scenes."""
        # Mock VSS search results
        mock_vss_service.search_similar_scenes.return_value = [
            {
                "id": 1,
                "script_id": 1,
                "heading": "Scene 1",
                "location": "Location 1",
                "content": "Content 1",
                "similarity_score": 0.9,
                "metadata": {"key": "value"},
            },
            {
                "id": 2,
                "script_id": 1,
                "heading": "Scene 2",
                "location": "Location 2",
                "content": "Content 2",
                "similarity_score": 0.8,
                "metadata": None,
            },
            {
                "id": 3,
                "script_id": 1,
                "heading": "Scene 3",
                "location": None,
                "content": "Content 3",
                "similarity_score": 0.4,  # Below threshold
                "metadata": None,
            },
        ]

        results = await semantic_search_vss.search_similar_scenes(
            query="Test query",
            script_id=1,
            top_k=2,
            threshold=0.5,
        )

        assert len(results) == 2
        assert all(isinstance(r, SceneSearchResult) for r in results)
        assert results[0].scene_id == 1
        assert results[0].similarity_score == 0.9
        assert results[1].scene_id == 2
        assert results[1].similarity_score == 0.8

    @pytest.mark.asyncio
    async def test_search_similar_scenes_no_script_filter(
        self, semantic_search_vss, mock_vss_service
    ):
        """Test searching without script filter."""
        mock_vss_service.search_similar_scenes.return_value = [
            {
                "id": 1,
                "script_id": 1,
                "heading": "Scene 1",
                "location": "Location 1",
                "content": "Content 1",
                "similarity_score": 0.95,
            }
        ]

        results = await semantic_search_vss.search_similar_scenes(
            query="Test query",
            top_k=5,
        )

        # Verify VSS was called without script_id
        mock_vss_service.search_similar_scenes.assert_called_once()
        call_kwargs = mock_vss_service.search_similar_scenes.call_args.kwargs
        assert call_kwargs["script_id"] is None

    @pytest.mark.asyncio
    async def test_find_related_scenes(
        self, semantic_search_vss, mock_vss_service, mock_embedding_service
    ):
        """Test finding related scenes."""
        # Mock database connection and scene lookup
        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchone.return_value = {
            "heading": "Original Scene",
            "content": "Original content",
        }
        mock_conn.execute.return_value = mock_cursor
        mock_vss_service.get_connection.return_value.__enter__.return_value = mock_conn

        # Mock VSS search results
        mock_vss_service.search_similar_scenes.return_value = [
            {
                "id": 1,  # Same as source, should be filtered
                "script_id": 1,
                "heading": "Original Scene",
                "location": None,
                "content": "Original content",
                "similarity_score": 1.0,
            },
            {
                "id": 2,
                "script_id": 1,
                "heading": "Related Scene",
                "location": "Location",
                "content": "Related content",
                "similarity_score": 0.7,
            },
        ]

        results = await semantic_search_vss.find_related_scenes(
            scene_id=1,
            script_id=1,
            top_k=5,
            threshold=0.5,
        )

        # Should filter out the source scene
        assert len(results) == 1
        assert results[0].scene_id == 2
        assert results[0].similarity_score == 0.7

    @pytest.mark.asyncio
    async def test_find_related_scenes_not_found(
        self, semantic_search_vss, mock_vss_service
    ):
        """Test finding related scenes when source scene not found."""
        # Mock scene not found
        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_vss_service.get_connection.return_value.__enter__.return_value = mock_conn

        results = await semantic_search_vss.find_related_scenes(
            scene_id=999,
            top_k=5,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_generate_missing_embeddings(
        self, semantic_search_vss, mock_vss_service, mock_embedding_service
    ):
        """Test generating missing embeddings."""
        # Mock database connection and missing scenes query
        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [
            {"id": 1, "heading": "Scene 1", "content": "Content 1"},
            {"id": 2, "heading": "Scene 2", "content": "Content 2"},
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_vss_service.get_connection.return_value.__enter__.return_value = mock_conn

        (
            scenes_processed,
            embeddings_generated,
        ) = await semantic_search_vss.generate_missing_embeddings(
            script_id=1,
            batch_size=2,
        )

        assert scenes_processed == 2
        assert embeddings_generated == 2

        # Verify embeddings were generated and stored
        assert mock_embedding_service.generate_scene_embedding.call_count == 2
        assert mock_vss_service.store_scene_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_missing_embeddings_with_errors(
        self, semantic_search_vss, mock_vss_service, mock_embedding_service
    ):
        """Test generating embeddings with some failures."""
        # Mock database connection
        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [
            {"id": 1, "heading": "Scene 1", "content": "Content 1"},
            {"id": 2, "heading": "Scene 2", "content": "Content 2"},
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_vss_service.get_connection.return_value.__enter__.return_value = mock_conn

        # Make second embedding generation fail
        mock_embedding_service.generate_scene_embedding.side_effect = [
            list(np.random.rand(1536)),
            Exception("Embedding error"),
        ]

        (
            scenes_processed,
            embeddings_generated,
        ) = await semantic_search_vss.generate_missing_embeddings()

        assert scenes_processed == 2
        assert embeddings_generated == 1  # Only one succeeded

    @pytest.mark.asyncio
    async def test_search_similar_bible_content(
        self, semantic_search_vss, mock_vss_service
    ):
        """Test searching for similar bible content."""
        # Mock VSS search results
        mock_vss_service.search_similar_bible_chunks.return_value = [
            {
                "id": 1,
                "bible_id": 1,
                "script_id": 1,
                "bible_title": "Test Bible",
                "heading": "Chapter 1",
                "content": "Bible content 1",
                "similarity_score": 0.85,
                "level": 1,
                "metadata": None,
            },
            {
                "id": 2,
                "bible_id": 1,
                "script_id": 1,
                "bible_title": "Test Bible",
                "heading": "Chapter 2",
                "content": "Bible content 2",
                "similarity_score": 0.3,  # Below threshold
                "level": 1,
                "metadata": None,
            },
        ]

        results = await semantic_search_vss.search_similar_bible_content(
            query="Test bible query",
            script_id=1,
            top_k=5,
            threshold=0.5,
        )

        assert len(results) == 1
        assert all(isinstance(r, BibleSearchResult) for r in results)
        assert results[0].chunk_id == 1
        assert results[0].similarity_score == 0.85
        assert results[0].bible_title == "Test Bible"

    @pytest.mark.asyncio
    async def test_generate_bible_embeddings(
        self, semantic_search_vss, mock_vss_service, mock_embedding_service
    ):
        """Test generating bible embeddings."""
        # Mock database connection
        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [
            {"id": 1, "heading": "Chapter 1", "content": "Content 1"},
            {"id": 2, "heading": None, "content": "Content 2"},
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_vss_service.get_connection.return_value.__enter__.return_value = mock_conn

        (
            chunks_processed,
            embeddings_generated,
        ) = await semantic_search_vss.generate_bible_embeddings(
            script_id=1,
            batch_size=2,
        )

        assert chunks_processed == 2
        assert embeddings_generated == 2

        # Verify embeddings were generated
        assert mock_embedding_service.generate_embedding.call_count == 2
        assert mock_vss_service.store_bible_embedding.call_count == 2

    @pytest.mark.asyncio
    # Migration test removed - migration function no longer exists
    # async def test_migrate_to_vss(self, semantic_search_vss, mock_vss_service):
    #     pass

    def test_get_embedding_stats(self, semantic_search_vss, mock_vss_service):
        """Test getting embedding statistics."""
        mock_stats = {
            "scene_embeddings": {"model1": 10, "model2": 5},
            "bible_chunk_embeddings": {"model1": 3},
            "metadata": {
                "scene": {"count": 15, "avg_dimensions": 1536},
                "bible_chunk": {"count": 3, "avg_dimensions": 1536},
            },
        }
        mock_vss_service.get_embedding_stats.return_value = mock_stats

        stats = semantic_search_vss.get_embedding_stats()

        assert stats == mock_stats
        mock_vss_service.get_embedding_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_model_usage(
        self, semantic_search_vss, mock_vss_service, mock_embedding_service
    ):
        """Test using custom embedding model."""
        custom_model = "custom-embedding-model"

        mock_vss_service.search_similar_scenes.return_value = []

        await semantic_search_vss.search_similar_scenes(
            query="Test",
            model=custom_model,
        )

        # Verify custom model was used
        mock_embedding_service.generate_embedding.assert_called_with(
            "Test", custom_model
        )
        mock_vss_service.search_similar_scenes.assert_called_once()
        call_kwargs = mock_vss_service.search_similar_scenes.call_args.kwargs
        assert call_kwargs["model"] == custom_model
