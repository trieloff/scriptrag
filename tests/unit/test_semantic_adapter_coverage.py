"""Extended tests for semantic adapter to improve coverage."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.models import SearchQuery, SearchResult
from scriptrag.search.semantic_adapter import SemanticSearchAdapter


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock(spec=ScriptRAGSettings)
    settings.database_path = "test.db"
    settings.search_vector_similarity_threshold = 0.7
    settings.database_journal_mode = "WAL"
    settings.database_synchronous = "NORMAL"
    settings.database_foreign_keys = True
    return settings


@pytest.fixture
def semantic_adapter(mock_settings):
    """Create semantic adapter instance."""
    with patch("scriptrag.search.semantic_adapter.SemanticSearchService"):
        adapter = SemanticSearchAdapter(mock_settings)
        # Mock the semantic service
        adapter.semantic_service = MagicMock(
            spec=["content", "model", "provider", "usage"]
        )
        adapter.semantic_service.search_similar_scenes = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        adapter.semantic_service.search_similar_bible_content = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        adapter.semantic_service.generate_missing_embeddings = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        adapter.semantic_service.generate_bible_embeddings = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        return adapter


@pytest.fixture
def semantic_adapter_no_settings():
    """Create semantic adapter without explicit settings."""
    with (
        patch("scriptrag.config.get_settings") as mock_get_settings,
        patch("scriptrag.search.semantic_adapter.SemanticSearchService"),
    ):
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.search_vector_similarity_threshold = 0.7
        mock_settings.database_journal_mode = "WAL"
        mock_settings.database_synchronous = "NORMAL"
        mock_settings.database_foreign_keys = True
        mock_get_settings.return_value = mock_settings

        adapter = SemanticSearchAdapter(None)
        adapter.semantic_service = MagicMock(
            spec=["content", "model", "provider", "usage"]
        )
        adapter.semantic_service.search_similar_scenes = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        adapter.semantic_service.search_similar_bible_content = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        return adapter


class TestSemanticAdapterCoverage:
    """Extended tests for semantic adapter coverage."""

    @pytest.mark.asyncio
    async def test_initialization_without_settings(self, semantic_adapter_no_settings):
        """Test adapter initialization without providing settings."""
        assert semantic_adapter_no_settings is not None
        assert semantic_adapter_no_settings.settings is not None
        assert not semantic_adapter_no_settings._initialized

    @pytest.mark.asyncio
    async def test_initialize_method(self, semantic_adapter):
        """Test initialize method."""
        assert not semantic_adapter._initialized

        await semantic_adapter.initialize()

        assert semantic_adapter._initialized

        # Call again to test idempotency
        await semantic_adapter.initialize()
        assert semantic_adapter._initialized

    @pytest.mark.asyncio
    async def test_cleanup_method(self, semantic_adapter):
        """Test cleanup method."""
        # Initialize first
        await semantic_adapter.initialize()
        assert semantic_adapter._initialized

        # Clean up
        await semantic_adapter.cleanup()
        assert not semantic_adapter._initialized

    @pytest.mark.asyncio
    async def test_enhance_results_no_query_text(self, semantic_adapter):
        """Test enhance results with no query text."""
        # Create query with no text fields
        query = SearchQuery(raw_query="")
        query.dialogue = None
        query.action = None
        query.text_query = None

        existing_results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. HOUSE - DAY",
                scene_location="HOUSE",
                scene_time="DAY",
                scene_content="Content",
                match_type="sql",
                relevance_score=1.0,
            )
        ]

        enhanced, bible = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=5
        )

        # Should return original results unchanged
        assert enhanced == existing_results
        assert bible == []

        # Semantic search should not be called
        semantic_adapter.semantic_service.search_similar_scenes.assert_not_called()

    @pytest.mark.asyncio
    async def test_enhance_results_with_error_handling(self, semantic_adapter):
        """Test enhance results handles errors gracefully."""
        query = SearchQuery(raw_query="test dialogue")
        query.dialogue = "test dialogue"

        existing_results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. HOUSE - DAY",
                scene_location="HOUSE",
                scene_time="DAY",
                scene_content="Content",
                match_type="sql",
                relevance_score=1.0,
            )
        ]

        # Make semantic search raise an error
        semantic_adapter.semantic_service.search_similar_scenes.side_effect = Exception(
            "Search failed"
        )

        enhanced, bible = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=5
        )

        # Should return original results on error
        assert enhanced == existing_results
        assert bible == []

    @pytest.mark.asyncio
    async def test_enhance_results_with_bible_search(self, semantic_adapter):
        """Test enhance results with bible search enabled."""
        query = SearchQuery(raw_query="test action")
        query.action = "test action"
        query.include_bible = True

        existing_results = []

        # Mock scene search results
        mock_scene_result = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_scene_result.scene_id = 10
        mock_scene_result.script_id = 1
        mock_scene_result.heading = "Scene Heading"
        mock_scene_result.location = "Location"
        mock_scene_result.content = "Scene content"
        mock_scene_result.similarity_score = 0.9

        semantic_adapter.semantic_service.search_similar_scenes.return_value = [
            mock_scene_result
        ]

        # Mock bible search results
        mock_bible_result = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_bible_result.script_id = 1
        mock_bible_result.bible_id = 1
        mock_bible_result.bible_title = "Test Bible"
        mock_bible_result.chunk_id = 1
        mock_bible_result.heading = "Chapter 1"
        mock_bible_result.level = 1
        mock_bible_result.content = "Bible content"
        mock_bible_result.similarity_score = 0.85

        semantic_adapter.semantic_service.search_similar_bible_content.return_value = [
            mock_bible_result
        ]

        enhanced, bible = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=5
        )

        # Check scene results
        assert len(enhanced) == 1
        assert enhanced[0].scene_id == 10
        assert enhanced[0].match_type == "semantic"
        assert enhanced[0].relevance_score == 0.9

        # Check bible results
        assert len(bible) == 1
        assert bible[0].chunk_id == 1
        assert bible[0].chunk_heading == "Chapter 1"
        assert bible[0].chunk_level == 1
        assert bible[0].chunk_content == "Bible content"
        assert bible[0].match_type == "semantic"

    @pytest.mark.asyncio
    async def test_enhance_results_only_bible_search(self, semantic_adapter):
        """Test enhance results with only_bible flag."""
        query = SearchQuery(raw_query="search text")
        query.text_query = "search text"
        query.only_bible = True

        existing_results = []

        # Mock bible search results with None values for optional fields
        mock_bible_result = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_bible_result.script_id = 1
        mock_bible_result.bible_id = 1
        mock_bible_result.bible_title = None  # Test None handling
        mock_bible_result.chunk_id = 1
        mock_bible_result.heading = "Chapter 1"
        mock_bible_result.level = None  # Test None handling
        mock_bible_result.content = "Bible content"
        mock_bible_result.similarity_score = 0.85

        semantic_adapter.semantic_service.search_similar_bible_content.return_value = [
            mock_bible_result
        ]

        enhanced, bible = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=5
        )

        # Bible search should be called even with only_bible flag
        semantic_adapter.semantic_service.search_similar_bible_content.assert_called_once()

        # Check bible results handle None values
        assert len(bible) == 1
        assert bible[0].bible_title is None  # bible_title stays as None
        assert (
            bible[0].script_title == "Unknown"
        )  # script_title becomes "Unknown" when bible_title is None
        assert bible[0].chunk_level == 0  # None becomes 0

    @pytest.mark.asyncio
    async def test_enhance_results_deduplication(self, semantic_adapter):
        """Test that duplicate scene IDs are not added."""
        query = SearchQuery(raw_query="test")
        query.dialogue = "test"

        # Existing result with scene_id=1
        existing_results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. HOUSE - DAY",
                scene_location="HOUSE",
                scene_time="DAY",
                scene_content="Content",
                match_type="sql",
                relevance_score=1.0,
            )
        ]

        # Mock semantic search returning duplicate and new scenes
        mock_duplicate = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_duplicate.scene_id = 1  # Duplicate
        mock_duplicate.script_id = 1
        mock_duplicate.heading = "Duplicate"
        mock_duplicate.location = "Location"
        mock_duplicate.content = "Content"
        mock_duplicate.similarity_score = 0.95

        mock_new = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_new.scene_id = 2  # New
        mock_new.script_id = 1
        mock_new.heading = "New Scene"
        mock_new.location = "New Location"
        mock_new.content = "New Content"
        mock_new.similarity_score = 0.9

        semantic_adapter.semantic_service.search_similar_scenes.return_value = [
            mock_duplicate,
            mock_new,
        ]

        enhanced, _ = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=5
        )

        # Should have 2 results (original + new, not duplicate)
        assert len(enhanced) == 2
        scene_ids = [r.scene_id for r in enhanced]
        assert scene_ids == [1, 2]

    @pytest.mark.asyncio
    async def test_enhance_results_limit_respected(self, semantic_adapter):
        """Test that the limit parameter is respected."""
        query = SearchQuery(raw_query="test")
        query.dialogue = "test"

        existing_results = []

        # Mock many semantic search results
        mock_results = []
        for i in range(10):
            mock_result = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_result.scene_id = i
            mock_result.script_id = 1
            mock_result.heading = f"Scene {i}"
            mock_result.location = f"Location {i}"
            mock_result.content = f"Content {i}"
            mock_result.similarity_score = 0.9 - (i * 0.01)
            mock_results.append(mock_result)

        semantic_adapter.semantic_service.search_similar_scenes.return_value = (
            mock_results
        )

        # Request only 3 results
        enhanced, _ = await semantic_adapter.enhance_results_with_semantic_search(
            query, existing_results, limit=3
        )

        # Should have exactly 3 results
        assert len(enhanced) == 3
        assert all(r.match_type == "semantic" for r in enhanced)

    @pytest.mark.asyncio
    async def test_ensure_embeddings_generated_basic(self, semantic_adapter):
        """Test basic embedding generation."""
        semantic_adapter.semantic_service.generate_missing_embeddings.return_value = (
            10,
            0,
        )
        semantic_adapter.semantic_service.generate_bible_embeddings.return_value = (
            5,
            0,
        )

        scenes, bible = await semantic_adapter.ensure_embeddings_generated(
            script_id=1, force_regenerate=False
        )

        assert scenes == 10
        assert bible == 5

        semantic_adapter.semantic_service.generate_missing_embeddings.assert_called_once_with(
            script_id=1, batch_size=10
        )
        semantic_adapter.semantic_service.generate_bible_embeddings.assert_called_once_with(
            script_id=1, batch_size=10
        )

    @pytest.mark.asyncio
    async def test_ensure_embeddings_generated_force_regenerate(self, semantic_adapter):
        """Test embedding generation with force_regenerate flag."""
        semantic_adapter.semantic_service.generate_missing_embeddings.return_value = (
            5,
            0,
        )
        semantic_adapter.semantic_service.generate_bible_embeddings.return_value = (
            3,
            0,
        )

        scenes, bible = await semantic_adapter.ensure_embeddings_generated(
            script_id=None, force_regenerate=True
        )

        # Force regenerate is not fully implemented, but should still call generation
        assert scenes == 5
        assert bible == 3

    @pytest.mark.asyncio
    async def test_ensure_embeddings_generated_error_handling(self, semantic_adapter):
        """Test embedding generation error handling."""
        # Make generation methods raise errors
        semantic_adapter.semantic_service.generate_missing_embeddings.side_effect = (
            Exception("Generation failed")
        )
        semantic_adapter.semantic_service.generate_bible_embeddings.side_effect = (
            Exception("Bible generation failed")
        )

        scenes, bible = await semantic_adapter.ensure_embeddings_generated()

        # Should return 0s on error
        assert scenes == 0
        assert bible == 0

    def test_decode_embedding_blob(self, semantic_adapter):
        """Test decoding embedding blob from database."""
        # Create test blob (3 float32 values)
        values = [0.1, 0.2, 0.3]
        blob = struct.pack(f"{len(values)}f", *values)

        result = semantic_adapter.decode_embedding_blob(blob)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 3
        assert np.allclose(result, values)

    def test_cosine_similarity_normal_vectors(self, semantic_adapter):
        """Test cosine similarity with normal vectors."""
        vec1 = np.array([1, 0, 0], dtype=np.float32)
        vec2 = np.array([1, 0, 0], dtype=np.float32)

        # Same vectors should have similarity 1
        similarity = semantic_adapter.cosine_similarity(vec1, vec2)
        assert np.isclose(similarity, 1.0)

        # Orthogonal vectors should have similarity 0
        vec3 = np.array([0, 1, 0], dtype=np.float32)
        similarity = semantic_adapter.cosine_similarity(vec1, vec3)
        assert np.isclose(similarity, 0.0)

        # Opposite vectors should have similarity -1
        vec4 = np.array([-1, 0, 0], dtype=np.float32)
        similarity = semantic_adapter.cosine_similarity(vec1, vec4)
        assert np.isclose(similarity, -1.0)

    def test_cosine_similarity_zero_vectors(self, semantic_adapter):
        """Test cosine similarity with zero vectors."""
        vec1 = np.array([0, 0, 0], dtype=np.float32)
        vec2 = np.array([1, 2, 3], dtype=np.float32)

        # Zero vector should return 0 similarity
        similarity = semantic_adapter.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

        # Both zero vectors should return 0
        similarity = semantic_adapter.cosine_similarity(vec1, vec1)
        assert similarity == 0.0

    def test_cosine_similarity_different_magnitudes(self, semantic_adapter):
        """Test cosine similarity is magnitude-independent."""
        vec1 = np.array([1, 1, 1], dtype=np.float32)
        vec2 = np.array(
            [2, 2, 2], dtype=np.float32
        )  # Same direction, different magnitude

        similarity = semantic_adapter.cosine_similarity(vec1, vec2)
        assert np.isclose(similarity, 1.0)  # Should be 1 despite different magnitudes
