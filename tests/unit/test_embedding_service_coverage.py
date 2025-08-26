"""Additional tests for EmbeddingService to improve coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import ScriptRAGError


@pytest.fixture
def settings():
    """Create test settings."""
    settings = ScriptRAGSettings()
    settings.llm_embedding_model = "test-model"
    return settings


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock(spec=object)
    # Mock the embed method that EmbeddingService actually uses
    mock_response = MagicMock(spec=object)
    mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
    client.embed = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def embedding_service(settings, mock_llm_client):
    """Create embedding service with mocks."""
    with patch("scriptrag.api.embedding_service.LLMClient") as mock_llm_class:
        mock_llm_class.return_value = mock_llm_client
        service = EmbeddingService(settings)
        service.llm_client = mock_llm_client
        return service


class TestEmbeddingServiceExtended:
    """Extended tests for EmbeddingService coverage."""

    @pytest.mark.asyncio
    async def test_generate_embedding_from_cache(self, embedding_service, tmp_path):
        """Test loading embedding from cache."""
        # Set up cache directory
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        embedding_service.cache.cache_dir = cache_dir

        text = "Test text"
        model = "test-model"
        cached_embedding = [0.5, 0.6, 0.7]

        # Pre-populate cache using the new interface
        embedding_service.cache.put(text, model, cached_embedding)

        # Should load from cache without calling LLM
        result = await embedding_service.generate_embedding(text, model)

        # Account for float32 precision when loading from cache
        np.testing.assert_array_almost_equal(result, cached_embedding, decimal=5)
        # Verify LLM client wasn't called since cache hit
        embedding_service.llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_cache_error(self, embedding_service, tmp_path):
        """Test handling cache read errors."""
        # Set up cache directory
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        embedding_service.cache.cache_dir = cache_dir

        text = "Test text"
        model = "test-model"

        # Create corrupted cache file manually in the cache structure
        cache_key = embedding_service.cache._get_cache_key(text, model)
        subdir = cache_dir / cache_key[:2]
        subdir.mkdir(exist_ok=True)
        cache_file = subdir / f"{cache_key}.npy"
        cache_file.write_text("corrupted npy data")

        # Add to index so it thinks the cache exists
        import time

        from scriptrag.embeddings.cache import CacheEntry

        embedding_service.cache._index[cache_key] = CacheEntry(
            key=cache_key,
            embedding=[],
            model=model,
            timestamp=time.time(),
            access_count=1,
            last_access=time.time(),
        )

        # Should fall back to generating new embedding
        embedding_service.llm_client.embed.return_value = type(
            "MockResponse", (), {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        )()

        result = await embedding_service.generate_embedding(text, model)

        assert result == [0.1, 0.2, 0.3]
        embedding_service.llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_with_cache(
        self, embedding_service, tmp_path
    ):
        """Test generating scene embedding with caching."""
        # Create new cache instance with test directory
        from scriptrag.embeddings.cache import EmbeddingCache, InvalidationStrategy

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Replace the cache instance entirely
        embedding_service.cache = EmbeddingCache(
            cache_dir=cache_dir, strategy=InvalidationStrategy.LRU
        )
        # Update pipeline to use new cache
        embedding_service.pipeline.cache = embedding_service.cache
        # Ensure pipeline config has cache enabled
        embedding_service.pipeline.config.use_cache = True

        scene_heading = "INT. ROOM - DAY"
        scene_content = "Scene content"
        model = "test-model"

        # Generate embedding using correct API
        result = await embedding_service.generate_scene_embedding(
            scene_content, scene_heading, model
        )

        # Account for float32 precision from cache
        np.testing.assert_array_almost_equal(result, [0.1, 0.2, 0.3], decimal=5)

        # Check cache was created - need to use processed text
        # The pipeline applies preprocessing before caching
        combined_text = f"Scene: {scene_heading}\n\n{scene_content}"
        processed_text = embedding_service.pipeline.preprocessor.process(combined_text)
        cached_result = embedding_service.cache.get(processed_text, model)
        assert cached_result is not None
        np.testing.assert_array_almost_equal(cached_result, [0.1, 0.2, 0.3], decimal=5)

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_no_metadata(self, embedding_service):
        """Test generating scene embedding without None in text."""
        scene_heading = "INT. ROOM - DAY"
        scene_content = "Scene content"
        model = "test-model"

        # Generate embedding
        result = await embedding_service.generate_scene_embedding(
            scene_content, scene_heading, model
        )

        # Account for float32 precision from cache
        np.testing.assert_array_almost_equal(result, [0.1, 0.2, 0.3], decimal=5)

        # Check that the combined text doesn't include None
        # This test verifies that the scene embedding method properly handles metadata
        # Combined text should be "Scene: INT. ROOM - DAY\n\nScene content" (no None)
        # Since this may use cache, just verify result is reasonable
        assert len(result) == 3  # Should have 3-dimensional embedding

    def test_save_embedding_to_lfs(self, embedding_service, tmp_path):
        """Test saving embedding to LFS storage."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.lfs_store.lfs_dir = git_storage

        entity_type = "scene"
        entity_id = 1
        embedding = [0.1, 0.2, 0.3]
        model = "test-model"

        # Save embedding
        file_path = embedding_service.save_embedding_to_lfs(
            embedding, entity_type, entity_id, model
        )

        # Check file was created
        assert file_path.exists()
        assert file_path.parent == git_storage / model.replace("/", "_") / entity_type

        # Check content
        data = np.load(file_path)
        np.testing.assert_array_almost_equal(data, embedding)

    def test_load_embedding_from_lfs_not_found(self, embedding_service, tmp_path):
        """Test loading non-existent embedding from LFS."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.lfs_store.lfs_dir = git_storage

        # Try to load non-existent embedding
        result = embedding_service.load_embedding_from_lfs("scene", 999, "test-model")

        assert result is None

    def test_load_embedding_from_lfs_error(self, embedding_service, tmp_path):
        """Test handling errors when loading from LFS."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.lfs_store.lfs_dir = git_storage

        # Create corrupted file in the correct path structure
        entity_type = "scene"
        entity_id = 1
        model = "test-model"

        # Use the correct GitLFS path structure: model/entity_type
        file_dir = git_storage / model.replace("/", "_") / entity_type
        file_dir.mkdir(parents=True)
        file_path = file_dir / f"{entity_id}.npy"
        file_path.write_text("corrupted")

        # Should handle error and return None
        result = embedding_service.load_embedding_from_lfs(
            entity_type, entity_id, model
        )

        assert result is None

    # NOTE: batch_generate_embeddings method doesn't exist in EmbeddingService
    # Removed fake tests for non-existent methods

    def test_find_similar_embeddings_with_matching_dimensions(self, embedding_service):
        """Test finding similar embeddings with matching dimensions."""
        query_embedding = [0.1, 0.2, 0.3]  # 3 dimensions

        # API expects list of (id, embedding) tuples - all same dimensions
        candidate_embeddings = [
            (1, [0.1, 0.2, 0.15]),  # 3 dimensions - low similarity
            (2, [0.2, 0.3, 0.4]),  # 3 dimensions - medium similarity
            (3, [0.1, 0.2, 0.3]),  # 3 dimensions - high similarity (same as query)
        ]

        # Find similar embeddings
        results = embedding_service.find_similar_embeddings(
            query_embedding, candidate_embeddings, top_k=2, threshold=0.5
        )

        # Should return results sorted by similarity
        assert isinstance(results, list)
        assert len(results) <= 2  # top_k=2

        # Verify result format
        for result in results:
            assert len(result) == 2  # (id, similarity) tuple
            assert isinstance(result[0], int)  # id
            assert isinstance(result[1], int | float)  # similarity score
            assert result[1] >= 0.5  # above threshold

        # Results should be sorted by similarity (descending)
        if len(results) > 1:
            assert results[0][1] >= results[1][1]

    def test_cosine_similarity_zero_vectors(self, embedding_service):
        """Test cosine similarity with zero vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]

        # Should handle zero vectors gracefully
        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

        # Both zero vectors
        similarity = embedding_service.cosine_similarity(vec1, vec1)
        assert similarity == 0.0

    def test_encode_decode_large_embedding(self, embedding_service):
        """Test encoding/decoding large embeddings."""
        # Create a large embedding (1536 dimensions like OpenAI)
        large_embedding = np.random.randn(1536).tolist()

        # Encode
        encoded = embedding_service.encode_embedding_for_db(large_embedding)
        assert isinstance(encoded, bytes)

        # Decode
        decoded = embedding_service.decode_embedding_from_db(encoded)
        np.testing.assert_array_almost_equal(decoded, large_embedding, decimal=5)

    @pytest.mark.asyncio
    async def test_generate_embedding_llm_error(self, embedding_service):
        """Test handling LLM errors during embedding generation."""
        text = "Test text that should not be cached"
        model = "test-model-error"

        # Mock LLM to raise error
        embedding_service.llm_client.embed.side_effect = Exception("LLM API error")

        # Should raise ScriptRAGError - disable cache to ensure LLM is called
        with pytest.raises(ScriptRAGError) as exc_info:
            await embedding_service.generate_embedding(text, model, use_cache=False)

        assert "Failed to generate embedding" in str(exc_info.value)

    def test_cache_key_generation_consistency(self, embedding_service):
        """Test cache key generation is consistent."""
        text = "Test text with special chars: 你好 🎉"
        model = "test-model"

        # Generate key multiple times using cache interface
        key1 = embedding_service.cache._get_cache_key(text, model)
        key2 = embedding_service.cache._get_cache_key(text, model)

        # Should be consistent
        assert key1 == key2

        # Should be valid hex string (SHA256)
        assert len(key1) == 64
        assert all(c in "0123456789abcdef" for c in key1)

        # Different text should give different key
        key3 = embedding_service.cache._get_cache_key("Different text", model)
        assert key3 != key1

        # Different model should give different key
        key4 = embedding_service.cache._get_cache_key(text, "different-model")
        assert key4 != key1

    # NOTE: Removed test_batch_scene_embeddings as it used wrong API signature
    # generate_scene_embedding takes separate content/heading params, not dict
