"""Unit tests for embedding service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import ScriptRAGError
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


@pytest.fixture
def settings():
    """Create test settings."""
    return ScriptRAGSettings()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=object)
    client.embed = AsyncMock(spec=object)
    return client


@pytest.fixture
def embedding_service(settings, mock_llm_client, tmp_path):
    """Create embedding service with mocks."""
    cache_dir = tmp_path / "cache"
    service = EmbeddingService(
        settings=settings,
        llm_client=mock_llm_client,
        cache_dir=cache_dir,
    )
    # Update lfs_store for testing
    service.lfs_store.lfs_dir = tmp_path / ".embeddings"
    return service


class TestEmbeddingService:
    """Test EmbeddingService class."""

    def test_init(self, settings):
        """Test embedding service initialization."""
        service = EmbeddingService(settings)
        assert service.settings == settings
        assert service.cache.cache_dir.exists()
        assert service.lfs_store.lfs_dir == Path(".embeddings")
        assert service.default_model == "text-embedding-3-small"
        assert service.embedding_dimensions == 1536

    def test_cache_key_generation(self, embedding_service):
        """Test cache key generation."""
        key1 = embedding_service.cache._get_cache_key("test text", "model-1")
        key2 = embedding_service.cache._get_cache_key("test text", "model-1")
        key3 = embedding_service.cache._get_cache_key("different text", "model-1")
        key4 = embedding_service.cache._get_cache_key("test text", "model-2")

        # Same text and model should produce same key
        assert key1 == key2
        # Different text should produce different key
        assert key1 != key3
        # Different model should produce different key
        assert key1 != key4

    def test_cache_save_and_load(self, embedding_service):
        """Test saving and loading embeddings from cache."""
        import numpy as np

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        text = "test text"
        model = "test-model"

        # Save to cache using new interface
        embedding_service.cache.put(text, model, embedding)

        # Load from cache using new interface
        loaded = embedding_service.cache.get(text, model)

        # Compare with tolerance due to float32 precision
        np.testing.assert_allclose(loaded, embedding, rtol=1e-6, atol=1e-7)

        # Non-existent text/model returns None
        assert embedding_service.cache.get("nonexistent", model) is None

    @pytest.mark.asyncio
    async def test_generate_embedding(self, embedding_service, mock_llm_client):
        """Test embedding generation."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": expected_embedding}],
            provider=LLMProvider.CLAUDE_CODE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Generate embedding
        result = await embedding_service.generate_embedding("test text")

        assert result == expected_embedding
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_with_cache(
        self, embedding_service, mock_llm_client
    ):
        """Test embedding generation with caching."""
        import numpy as np

        expected_embedding = [0.1, 0.2, 0.3]
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": expected_embedding}],
            provider=LLMProvider.CLAUDE_CODE,
        )
        mock_llm_client.embed.return_value = mock_response

        # First call - should hit LLM
        result1 = await embedding_service.generate_embedding(
            "test text", use_cache=True
        )
        np.testing.assert_allclose(result1, expected_embedding, rtol=1e-6, atol=1e-7)
        assert mock_llm_client.embed.call_count == 1

        # Second call - should hit cache
        result2 = await embedding_service.generate_embedding(
            "test text", use_cache=True
        )
        np.testing.assert_allclose(result2, expected_embedding, rtol=1e-6, atol=1e-7)
        assert mock_llm_client.embed.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_generate_embedding_error(self, embedding_service, mock_llm_client):
        """Test embedding generation error handling."""
        mock_llm_client.embed.side_effect = Exception("API error")

        with pytest.raises(ScriptRAGError) as exc_info:
            await embedding_service.generate_embedding("test text")

        assert "Failed to generate embedding" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_scene_embedding(self, embedding_service, mock_llm_client):
        """Test scene embedding generation."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": expected_embedding}],
            provider=LLMProvider.CLAUDE_CODE,
        )
        mock_llm_client.embed.return_value = mock_response

        result = await embedding_service.generate_scene_embedding(
            "Scene content", "INT. ROOM - DAY"
        )

        assert result == expected_embedding
        # Check that heading and content were combined
        call_args = mock_llm_client.embed.call_args[0][0]
        assert "Scene: INT. ROOM - DAY" in call_args.input
        assert "Scene content" in call_args.input

    def test_save_embedding_to_lfs(self, embedding_service, tmp_path):
        """Test saving embeddings to LFS directory."""
        embedding_service.lfs_store.lfs_dir = tmp_path / ".embeddings"
        # Ensure .gitattributes is created after changing the directory
        embedding_service.lfs_store._ensure_gitattributes()
        embedding = [0.1, 0.2, 0.3]

        path = embedding_service.save_embedding_to_lfs(
            embedding, "scene", 123, "test-model"
        )

        assert path.exists()
        assert path.suffix == ".npy"
        assert "test-model" in str(path)
        assert "scene" in str(path)
        assert "123.npy" in str(path)

        # Load and verify
        loaded = np.load(path)
        np.testing.assert_array_almost_equal(loaded, embedding)

        # Check .gitattributes was created
        gitattributes = embedding_service.lfs_store.lfs_dir / ".gitattributes"
        assert gitattributes.exists()
        assert "*.npy filter=lfs" in gitattributes.read_text()

    def test_load_embedding_from_lfs(self, embedding_service, tmp_path):
        """Test loading embeddings from LFS directory."""
        embedding_service.lfs_store.lfs_dir = tmp_path / ".embeddings"
        embedding = [0.1, 0.2, 0.3]

        # Save first
        path = embedding_service.save_embedding_to_lfs(
            embedding, "scene", 123, "test-model"
        )

        # Load back
        loaded = embedding_service.load_embedding_from_lfs("scene", 123, "test-model")
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded, embedding)

        # Non-existent embedding returns None
        assert (
            embedding_service.load_embedding_from_lfs("scene", 999, "test-model")
            is None
        )

    def test_encode_decode_embedding(self, embedding_service):
        """Test encoding and decoding embeddings for database storage."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Encode
        encoded = embedding_service.encode_embedding_for_db(embedding)
        assert isinstance(encoded, bytes)

        # Decode
        decoded = embedding_service.decode_embedding_from_db(encoded)
        assert len(decoded) == len(embedding)
        np.testing.assert_array_almost_equal(decoded, embedding)

    def test_cosine_similarity(self, embedding_service):
        """Test cosine similarity calculation."""
        # Identical vectors
        vec1 = [1.0, 0.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec1)
        assert pytest.approx(similarity) == 1.0

        # Orthogonal vectors
        vec2 = [0.0, 1.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert pytest.approx(similarity) == 0.0

        # Opposite vectors
        vec3 = [-1.0, 0.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec3)
        assert pytest.approx(similarity) == -1.0

        # Zero vector
        vec_zero = [0.0, 0.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec_zero)
        assert similarity == 0.0

    def test_find_similar_embeddings(self, embedding_service):
        """Test finding similar embeddings."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0, 0.0]),  # Identical
            (2, [0.9, 0.1, 0.0]),  # Very similar
            (3, [0.0, 1.0, 0.0]),  # Orthogonal
            (4, [0.5, 0.5, 0.0]),  # Somewhat similar
            (5, [-1.0, 0.0, 0.0]),  # Opposite
        ]

        # Find top 3 with threshold 0.5
        results = embedding_service.find_similar_embeddings(
            query, candidates, top_k=3, threshold=0.5
        )

        assert len(results) == 3  # Three meet threshold (1, 2, 4)
        assert results[0][0] == 1  # ID 1 should be first (identical)
        assert results[0][1] == pytest.approx(1.0)
        assert results[1][0] == 2  # ID 2 should be second
        assert results[2][0] == 4  # ID 4 should be third

    def test_find_similar_embeddings_empty(self, embedding_service):
        """Test finding similar embeddings with no candidates."""
        query = [1.0, 0.0, 0.0]
        candidates = []

        results = embedding_service.find_similar_embeddings(query, candidates)
        assert results == []

    def test_find_similar_embeddings_high_threshold(self, embedding_service):
        """Test finding similar embeddings with high threshold."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            (1, [0.5, 0.5, 0.0]),  # Not similar enough
            (2, [0.6, 0.4, 0.0]),  # Not similar enough
        ]

        results = embedding_service.find_similar_embeddings(
            query, candidates, threshold=0.9
        )
        assert results == []  # None meet high threshold
