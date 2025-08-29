"""Tests for semantic search adapter."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.config.settings import ScriptRAGSettings
from scriptrag.search.models import SearchMode, SearchQuery
from scriptrag.search.semantic_adapter import SemanticSearchAdapter


class TestSemanticSearchAdapter:
    """Test SemanticSearchAdapter class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(
            spec=ScriptRAGSettings
        )  # Use spec to prevent mock file artifacts
        settings.llm_embedding_model = "text-embedding-3-small"
        settings.llm_embedding_dimensions = 1536
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.database_path = "/tmp/test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_foreign_keys = True
        return settings

    @pytest.fixture
    def adapter(self, mock_settings):
        """Create a SemanticSearchAdapter instance."""
        with patch(
            "scriptrag.search.semantic_adapter.SemanticSearchService"
        ) as mock_service_class:
            mock_service = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_service_class.return_value = mock_service
            adapter = SemanticSearchAdapter(mock_settings)
            # Ensure the service is properly set up
            adapter.semantic_service = mock_service
            return adapter

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """Test adapter initialization."""
        await adapter.initialize()
        assert adapter._initialized

    @pytest.mark.asyncio
    async def test_cleanup(self, adapter):
        """Test adapter cleanup."""
        await adapter.initialize()
        await adapter.cleanup()
        assert not adapter._initialized

    @pytest.mark.asyncio
    async def test_enhance_results_no_query_text(self, adapter):
        """Test enhance_results with no query text."""
        query = SearchQuery(
            raw_query="",
            mode=SearchMode.FUZZY,
            limit=10,
            offset=0,
        )
        existing_results = []

        enhanced, bible = await adapter.enhance_results_with_semantic_search(
            query=query,
            existing_results=existing_results,
            limit=5,
        )

        assert enhanced == existing_results
        assert bible == []

    @pytest.mark.asyncio
    async def test_enhance_results_with_scenes(self, adapter):
        """Test enhance_results with scene results."""
        # Create mock search results with only the attributes the adapter actually uses
        mock_scene_result = MagicMock(
            spec_set=[
                "scene_id",
                "script_id",
                "heading",
                "location",
                "content",
                "similarity_score",
                "metadata",
            ]
        )
        mock_scene_result.scene_id = 123
        mock_scene_result.script_id = 1
        mock_scene_result.heading = "INT. OFFICE - DAY"
        mock_scene_result.location = "OFFICE"
        mock_scene_result.content = "Test content"
        mock_scene_result.similarity_score = 0.8

        # Mock both semantic service methods with proper async behavior
        adapter.semantic_service.search_similar_scenes = AsyncMock(
            return_value=[mock_scene_result]
        )
        adapter.semantic_service.search_similar_bible_content = AsyncMock(
            return_value=[]
        )

        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.FUZZY,
            limit=10,
            offset=0,
        )
        existing_results = []

        enhanced, bible = await adapter.enhance_results_with_semantic_search(
            query=query,
            existing_results=existing_results,
            limit=5,
        )

        assert len(enhanced) == 1
        assert enhanced[0].scene_id == 123
        assert enhanced[0].match_type == "semantic"
        assert enhanced[0].relevance_score == 0.8

    @pytest.mark.asyncio
    async def test_enhance_results_with_bible(self, adapter):
        """Test enhance_results with bible results."""
        # Create mock bible result with only the attributes the adapter actually uses
        mock_bible_result = MagicMock(
            spec_set=[
                "chunk_id",
                "bible_id",
                "script_id",
                "bible_title",
                "heading",
                "content",
                "similarity_score",
                "level",
                "metadata",
            ]
        )
        mock_bible_result.script_id = 1
        mock_bible_result.bible_id = 1
        mock_bible_result.bible_title = "Test Bible"
        mock_bible_result.chunk_id = 10
        mock_bible_result.heading = "Characters"
        mock_bible_result.level = 1
        mock_bible_result.content = "Character descriptions"
        mock_bible_result.similarity_score = 0.7

        # Mock the semantic service methods with proper async behavior
        adapter.semantic_service.search_similar_scenes = AsyncMock(return_value=[])
        adapter.semantic_service.search_similar_bible_content = AsyncMock(
            return_value=[mock_bible_result]
        )

        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.FUZZY,
            limit=10,
            offset=0,
            include_bible=True,
        )
        existing_results = []

        enhanced, bible = await adapter.enhance_results_with_semantic_search(
            query=query,
            existing_results=existing_results,
            limit=5,
        )

        assert len(enhanced) == 0
        assert len(bible) == 1
        assert bible[0].chunk_id == 10
        assert bible[0].match_type == "semantic"
        assert bible[0].relevance_score == 0.7

    @pytest.mark.asyncio
    async def test_enhance_results_deduplication(self, adapter):
        """Test that duplicate results are not added."""
        # Create existing result
        from scriptrag.search.models import SearchResult

        existing_result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=123,
            scene_number=1,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="Test content",
        )

        # Create mock scene that duplicates existing with only adapter attributes
        mock_scene_result = MagicMock(
            spec_set=[
                "scene_id",
                "script_id",
                "heading",
                "location",
                "content",
                "similarity_score",
                "metadata",
            ]
        )
        mock_scene_result.scene_id = 123  # Same as existing
        mock_scene_result.script_id = 1
        mock_scene_result.heading = "INT. OFFICE - DAY"
        mock_scene_result.location = "OFFICE"
        mock_scene_result.content = "Test content"
        mock_scene_result.similarity_score = 0.8

        # Mock both semantic service methods with proper async behavior
        adapter.semantic_service.search_similar_scenes = AsyncMock(
            return_value=[mock_scene_result]
        )
        adapter.semantic_service.search_similar_bible_content = AsyncMock(
            return_value=[]
        )

        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.FUZZY,
            limit=10,
            offset=0,
        )
        existing_results = [existing_result]

        enhanced, bible = await adapter.enhance_results_with_semantic_search(
            query=query,
            existing_results=existing_results,
            limit=5,
        )

        # Should not add duplicate
        assert len(enhanced) == 1
        assert enhanced[0].scene_id == 123

    @pytest.mark.asyncio
    async def test_enhance_results_error_handling(self, adapter):
        """Test error handling in enhance_results."""
        # Mock the semantic service to raise an error
        adapter.semantic_service.search_similar_scenes = AsyncMock(
            side_effect=Exception("API error")
        )

        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.FUZZY,
            limit=10,
            offset=0,
        )
        existing_results = []

        enhanced, bible = await adapter.enhance_results_with_semantic_search(
            query=query,
            existing_results=existing_results,
            limit=5,
        )

        # Should return original results on error
        assert enhanced == existing_results
        assert bible == []

    @pytest.mark.asyncio
    async def test_ensure_embeddings_generated(self, adapter):
        """Test ensure_embeddings_generated method."""
        # Mock the semantic service methods
        adapter.semantic_service.generate_missing_embeddings = AsyncMock(
            return_value=(10, 5)  # (generated, total)
        )
        adapter.semantic_service.generate_bible_embeddings = AsyncMock(
            return_value=(3, 8)  # (generated, total)
        )

        scenes_gen, bible_gen = await adapter.ensure_embeddings_generated(
            script_id=1,
            force_regenerate=False,
        )

        assert scenes_gen == 10
        assert bible_gen == 3

        # Verify calls were made
        adapter.semantic_service.generate_missing_embeddings.assert_called_once_with(
            script_id=1,
            batch_size=10,
        )
        adapter.semantic_service.generate_bible_embeddings.assert_called_once_with(
            script_id=1,
            batch_size=10,
        )

    def test_decode_embedding_blob(self, adapter):
        """Test decode_embedding_blob compatibility method."""
        # Create a sample float array
        floats = [0.1, 0.2, 0.3, 0.4]
        blob = struct.pack(f"{len(floats)}f", *floats)

        result = adapter.decode_embedding_blob(blob)

        assert isinstance(result, np.ndarray)
        assert len(result) == 4
        np.testing.assert_array_almost_equal(result, floats)

    def test_cosine_similarity(self, adapter):
        """Test cosine_similarity compatibility method."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([1, 0, 0])

        similarity = adapter.cosine_similarity(vec1, vec2)
        assert similarity == 1.0

        vec3 = np.array([0, 1, 0])
        similarity = adapter.cosine_similarity(vec1, vec3)
        assert similarity == 0.0

        # Test with zero vector
        vec4 = np.array([0, 0, 0])
        similarity = adapter.cosine_similarity(vec1, vec4)
        assert similarity == 0.0
