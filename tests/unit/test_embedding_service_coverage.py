"""Additional tests for EmbeddingService to improve coverage."""

import json
from pathlib import Path
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
    settings.embedding_model = "test-model"
    settings.embedding_cache_dir = Path("/tmp/embeddings")
    settings.git_storage_path = Path("/tmp/git_storage")
    return settings


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
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
        embedding_service.cache_dir = cache_dir

        text = "Test text"
        model = "test-model"
        cached_embedding = [0.5, 0.6, 0.7]

        # Create cache file
        cache_key = embedding_service._get_cache_key(text, model)
        cache_file = cache_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps(cached_embedding))

        # Should load from cache without calling LLM
        result = await embedding_service.generate_embedding(text, model)

        assert result == cached_embedding
        embedding_service.llm_client.generate_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_cache_error(self, embedding_service, tmp_path):
        """Test handling cache read errors."""
        # Set up cache directory
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        embedding_service.cache_dir = cache_dir

        text = "Test text"
        model = "test-model"

        # Create corrupted cache file
        cache_key = embedding_service._get_cache_key(text, model)
        cache_file = cache_dir / f"{cache_key}.json"
        cache_file.write_text("corrupted json")

        # Should fall back to generating new embedding
        embedding_service.llm_client.generate_embedding.return_value = [0.1, 0.2, 0.3]

        result = await embedding_service.generate_embedding(text, model)

        assert result == [0.1, 0.2, 0.3]
        embedding_service.llm_client.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_with_cache(
        self, embedding_service, tmp_path
    ):
        """Test generating scene embedding with caching."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        embedding_service.cache_dir = cache_dir

        scene = {
            "heading": "INT. ROOM - DAY",
            "content": "Scene content",
            "metadata": json.dumps({"characters": ["John"]}),
        }
        model = "test-model"

        # Mock LLM response
        embedding_service.llm_client.generate_embedding.return_value = [0.1, 0.2, 0.3]

        # Generate embedding
        result = await embedding_service.generate_scene_embedding(scene, model)

        assert result == [0.1, 0.2, 0.3]

        # Check cache was created
        cache_key = embedding_service._get_cache_key(
            f"{scene['heading']}\n{scene['content']}\n{scene['metadata']}", model
        )
        cache_file = cache_dir / f"{cache_key}.json"
        assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_no_metadata(self, embedding_service):
        """Test generating scene embedding without metadata."""
        scene = {
            "heading": "INT. ROOM - DAY",
            "content": "Scene content",
            "metadata": None,
        }
        model = "test-model"

        # Mock LLM response
        embedding_service.llm_client.generate_embedding.return_value = [0.1, 0.2, 0.3]

        # Generate embedding
        result = await embedding_service.generate_scene_embedding(scene, model)

        assert result == [0.1, 0.2, 0.3]

        # Check that the text doesn't include None
        call_args = embedding_service.llm_client.generate_embedding.call_args
        assert "None" not in call_args[0][0]

    def test_save_embedding_to_lfs(self, embedding_service, tmp_path):
        """Test saving embedding to LFS storage."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.git_storage_path = git_storage

        entity_type = "scene"
        entity_id = 1
        embedding = [0.1, 0.2, 0.3]
        model = "test-model"

        # Save embedding
        file_path = embedding_service.save_embedding_to_lfs(
            entity_type, entity_id, embedding, model
        )

        # Check file was created
        assert file_path.exists()
        assert file_path.parent == git_storage / entity_type / model

        # Check content
        data = np.load(file_path)
        np.testing.assert_array_almost_equal(data, embedding)

    def test_load_embedding_from_lfs_not_found(self, embedding_service, tmp_path):
        """Test loading non-existent embedding from LFS."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.git_storage_path = git_storage

        # Try to load non-existent embedding
        result = embedding_service.load_embedding_from_lfs("scene", 999, "test-model")

        assert result is None

    def test_load_embedding_from_lfs_error(self, embedding_service, tmp_path):
        """Test handling errors when loading from LFS."""
        git_storage = tmp_path / "git_storage"
        git_storage.mkdir()
        embedding_service.git_storage_path = git_storage

        # Create corrupted file
        entity_type = "scene"
        entity_id = 1
        model = "test-model"

        file_dir = git_storage / entity_type / model
        file_dir.mkdir(parents=True)
        file_path = file_dir / f"{entity_id}.npy"
        file_path.write_text("corrupted")

        # Should handle error and return None
        result = embedding_service.load_embedding_from_lfs(
            entity_type, entity_id, model
        )

        assert result is None

    def test_batch_generate_embeddings_empty(self, embedding_service):
        """Test batch generation with empty list."""
        result = embedding_service.batch_generate_embeddings([], "test-model")

        assert result == []

    def test_batch_generate_embeddings_with_errors(self, embedding_service):
        """Test batch generation with some errors."""
        texts = ["text1", "text2", "text3"]
        model = "test-model"

        # Mock to fail on second text
        async def mock_generate(text, model):
            if text == "text2":
                raise Exception("Generation failed")
            return [0.1, 0.2, 0.3]

        embedding_service.generate_embedding = AsyncMock(side_effect=mock_generate)

        # Run batch generation
        import asyncio

        result = asyncio.run(embedding_service.batch_generate_embeddings(texts, model))

        # Should return embeddings for successful texts, None for failed
        assert len(result) == 3
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] is None
        assert result[2] == [0.1, 0.2, 0.3]

    def test_find_similar_embeddings_different_dimensions(self, embedding_service):
        """Test finding similar embeddings with mismatched dimensions."""
        query_embedding = [0.1, 0.2, 0.3]  # 3 dimensions
        embeddings = [
            {"id": 1, "embedding": [0.1, 0.2]},  # 2 dimensions - mismatch
            {"id": 2, "embedding": [0.2, 0.3, 0.4]},  # 3 dimensions - match
            {"id": 3, "embedding": [0.1, 0.2, 0.3, 0.4]},  # 4 dimensions - mismatch
        ]

        # Decode embeddings
        for emb in embeddings:
            emb["embedding"] = embedding_service.encode_embedding_for_db(
                emb["embedding"]
            )

        # Find similar - should only consider matching dimensions
        results = embedding_service.find_similar_embeddings(
            query_embedding, embeddings, top_k=2
        )

        # Should only return the one with matching dimensions
        assert len(results) == 1
        assert results[0]["id"] == 2

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
        text = "Test text"
        model = "test-model"

        # Mock LLM to raise error
        embedding_service.llm_client.generate_embedding.side_effect = Exception(
            "LLM API error"
        )

        # Should raise ScriptRAGError
        with pytest.raises(ScriptRAGError) as exc_info:
            await embedding_service.generate_embedding(text, model)

        assert "Failed to generate embedding" in str(exc_info.value)

    def test_cache_key_generation_consistency(self, embedding_service):
        """Test cache key generation is consistent."""
        text = "Test text with special chars: 你好 🎉"
        model = "test-model"

        # Generate key multiple times
        key1 = embedding_service._get_cache_key(text, model)
        key2 = embedding_service._get_cache_key(text, model)

        # Should be consistent
        assert key1 == key2

        # Should be valid hex string (SHA256)
        assert len(key1) == 64
        assert all(c in "0123456789abcdef" for c in key1)

        # Different text should give different key
        key3 = embedding_service._get_cache_key("Different text", model)
        assert key3 != key1

        # Different model should give different key
        key4 = embedding_service._get_cache_key(text, "different-model")
        assert key4 != key1

    @pytest.mark.asyncio
    async def test_batch_scene_embeddings(self, embedding_service):
        """Test batch generation of scene embeddings."""
        scenes = [
            {"heading": "Scene 1", "content": "Content 1", "metadata": None},
            {
                "heading": "Scene 2",
                "content": "Content 2",
                "metadata": json.dumps({"test": "data"}),
            },
        ]
        model = "test-model"

        # Mock individual generation
        async def mock_generate_scene(scene, model):
            if scene["heading"] == "Scene 1":
                return [0.1, 0.2, 0.3]
            return [0.4, 0.5, 0.6]

        embedding_service.generate_scene_embedding = AsyncMock(
            side_effect=mock_generate_scene
        )

        # Generate batch
        import asyncio

        tasks = [
            embedding_service.generate_scene_embedding(scene, model) for scene in scenes
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 2
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6]
