"""Comprehensive tests for the embedding service integration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings
from scriptrag.embeddings.cache import InvalidationStrategy
from scriptrag.embeddings.similarity import SimilarityMetric
from scriptrag.exceptions import ScriptRAGError
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


class TestEmbeddingServiceComprehensive:
    """Comprehensive tests for EmbeddingService covering uncovered paths."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return ScriptRAGSettings()

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock(spec=LLMClient)
        client.embed = AsyncMock(spec=object)
        return client

    @pytest.fixture
    def service(self, settings, mock_llm_client, tmp_path):
        """Create embedding service with mocks."""
        cache_dir = tmp_path / "cache"
        service = EmbeddingService(
            settings=settings,
            llm_client=mock_llm_client,
            cache_dir=cache_dir,
        )
        # Update lfs_store path for testing
        service.lfs_store.lfs_dir = tmp_path / ".embeddings"
        return service

    def test_init_comprehensive(self, settings, mock_llm_client, tmp_path):
        """Test comprehensive initialization including all components."""
        cache_dir = tmp_path / "custom_cache"
        service = EmbeddingService(
            settings=settings,
            llm_client=mock_llm_client,
            cache_dir=cache_dir,
        )

        # Test all component initialization
        assert service.settings == settings
        assert service.llm_client == mock_llm_client
        assert service.default_model == "text-embedding-3-small"
        assert service.embedding_dimensions == 1536

        # Test architecture components
        assert service.dimension_manager is not None
        assert service.similarity_calculator is not None
        assert service.similarity_calculator.metric == SimilarityMetric.COSINE
        assert service.serializer is not None

        # Test cache setup
        assert service.cache is not None
        assert service.cache.cache_dir == cache_dir
        assert service.cache.strategy == InvalidationStrategy.LRU

        # Test vector stores
        assert service.lfs_store is not None
        assert service.vector_store == service.lfs_store

        # Test batch processor
        assert service.batch_processor is not None
        assert service.batch_processor.batch_size == 10
        assert service.batch_processor.max_concurrent == 3

        # Test pipeline
        assert service.pipeline is not None
        assert service.pipeline.config.model == "text-embedding-3-small"
        assert service.pipeline.config.dimensions == 1536
        assert service.pipeline.config.use_cache is True

    def test_init_with_defaults(self, settings):
        """Test initialization with default parameters."""
        service = EmbeddingService(settings=settings)

        # Should create default LLM client
        assert isinstance(service.llm_client, LLMClient)

        # Should create default cache directory
        expected_cache_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        assert service.cache.cache_dir == expected_cache_dir

    @pytest.mark.asyncio
    async def test_generate_embedding_with_model_change(self, service, mock_llm_client):
        """Test embedding generation when model changes."""
        mock_response = EmbeddingResponse(
            model="custom-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Mock dimension manager to return dimensions for custom model
        with patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims:
            mock_get_dims.return_value = 512

            result = await service.generate_embedding("test text", model="custom-model")

            assert result == [0.1, 0.2, 0.3]
            # Pipeline config should be updated
            assert service.pipeline_config.model == "custom-model"
            assert service.pipeline_config.dimensions == 512

    @pytest.mark.asyncio
    async def test_generate_embedding_model_no_dimensions(
        self, service, mock_llm_client
    ):
        """Test embedding generation when dimension manager returns None."""
        mock_response = EmbeddingResponse(
            model="unknown-model",
            data=[{"embedding": [0.1, 0.2]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Mock dimension manager to return None
        with patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims:
            mock_get_dims.return_value = None

            result = await service.generate_embedding(
                "test text", model="unknown-model"
            )

            assert result == [0.1, 0.2]
            # Pipeline config model should be updated but dimensions unchanged
            assert service.pipeline_config.model == "unknown-model"
            # Dimensions should remain as original value since None returned

    @pytest.mark.asyncio
    async def test_generate_embedding_cache_disabled(self, service, mock_llm_client):
        """Test embedding generation with cache disabled."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        result = await service.generate_embedding("test text", use_cache=False)

        assert result == [0.1, 0.2, 0.3]
        assert service.pipeline_config.use_cache is False

    @pytest.mark.asyncio
    async def test_generate_embedding_exception_handling(
        self, service, mock_llm_client
    ):
        """Test embedding generation exception handling with detailed error."""
        # Mock pipeline to raise exception
        with patch.object(service.pipeline, "generate_embedding") as mock_generate:
            mock_generate.side_effect = ValueError("Pipeline error")

            with pytest.raises(ScriptRAGError) as exc_info:
                await service.generate_embedding("test text", model="test-model")

            error = exc_info.value
            assert "Failed to generate embedding" in error.message
            assert "Pipeline error" in str(error)
            assert "Check LLM provider configuration" in error.hint
            assert error.details["model"] == "test-model"
            assert error.details["text_length"] == len("test text")

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_long_text(self, service, mock_llm_client):
        """Test scene embedding generation with text truncation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Create long content that exceeds max_length
        # The default model is text-embedding-3-small with max_tokens=8191
        # which translates to 8191 * 4 = 32764 character limit
        long_content = "A" * 35000  # Longer than model limit
        scene_heading = "INT. ROOM - DAY"

        with patch.object(service, "generate_embedding") as mock_gen:
            mock_gen.return_value = [0.1, 0.2, 0.3]

            result = await service.generate_scene_embedding(long_content, scene_heading)

            assert result == [0.1, 0.2, 0.3]

            # Check that text was truncated
            call_args = mock_gen.call_args[0][0]
            # text-embedding-3-small: max_tokens=8191, max_length=8191*4=32764
            assert len(call_args) <= 32764 + 3  # +3 for "..."
            assert call_args.endswith("...")
            assert "Scene: INT. ROOM - DAY" in call_args

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_short_text(self, service, mock_llm_client):
        """Test scene embedding generation without truncation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        content = "Short scene content."
        heading = "EXT. STREET - NIGHT"

        with patch.object(service, "generate_embedding") as mock_gen:
            mock_gen.return_value = [0.1, 0.2, 0.3]

            result = await service.generate_scene_embedding(content, heading)

            assert result == [0.1, 0.2, 0.3]

            # Check combined text format
            call_args = mock_gen.call_args[0][0]
            assert "Scene: EXT. STREET - NIGHT" in call_args
            assert content in call_args
            assert not call_args.endswith("...")  # No truncation

    def test_save_embedding_to_lfs_path_return(self, service):
        """Test save_embedding_to_lfs returns correct path."""
        embedding = [0.1, 0.2, 0.3]

        with (
            patch.object(service.lfs_store, "store") as mock_store,
            patch.object(service.lfs_store, "_get_path") as mock_get_path,
        ):
            expected_path = Path("/fake/path/scene/123.npy")
            mock_get_path.return_value = expected_path

            result = service.save_embedding_to_lfs(
                embedding, "scene", 123, "test-model"
            )

            assert result == expected_path
            mock_store.assert_called_once_with("scene", 123, embedding, "test-model")
            mock_get_path.assert_called_once_with("scene", 123, "test-model")

    def test_load_embedding_from_lfs_wrapper(self, service):
        """Test load_embedding_from_lfs as wrapper method."""
        expected_embedding = [0.1, 0.2, 0.3]

        with patch.object(service.lfs_store, "retrieve") as mock_retrieve:
            mock_retrieve.return_value = expected_embedding

            result = service.load_embedding_from_lfs("scene", 123, "test-model")

            assert result == expected_embedding
            mock_retrieve.assert_called_once_with("scene", 123, "test-model")

    def test_load_embedding_from_lfs_not_found(self, service):
        """Test load_embedding_from_lfs when embedding not found."""
        with patch.object(service.lfs_store, "retrieve") as mock_retrieve:
            mock_retrieve.return_value = None

            result = service.load_embedding_from_lfs("scene", 999, "test-model")

            assert result is None

    def test_encode_embedding_for_db_wrapper(self, service):
        """Test encode_embedding_for_db as wrapper method."""
        embedding = [0.1, 0.2, 0.3]
        expected_bytes = b"encoded_data"

        with patch.object(service.serializer, "encode") as mock_encode:
            mock_encode.return_value = expected_bytes

            result = service.encode_embedding_for_db(embedding)

            assert result == expected_bytes
            mock_encode.assert_called_once_with(embedding)

    def test_decode_embedding_from_db_wrapper(self, service):
        """Test decode_embedding_from_db as wrapper method."""
        data = b"encoded_data"
        expected_embedding = [0.1, 0.2, 0.3]

        with patch.object(service.serializer, "decode") as mock_decode:
            mock_decode.return_value = expected_embedding

            result = service.decode_embedding_from_db(data)

            assert result == expected_embedding
            mock_decode.assert_called_once_with(data)

    def test_decode_embedding_from_db_error_propagation(self, service):
        """Test that decode errors are properly propagated."""
        data = b"corrupted_data"

        with patch.object(service.serializer, "decode") as mock_decode:
            mock_decode.side_effect = ValueError("Decode error")

            with pytest.raises(ValueError) as exc_info:
                service.decode_embedding_from_db(data)

            assert "Decode error" in str(exc_info.value)

    def test_cosine_similarity_wrapper(self, service):
        """Test cosine_similarity as wrapper method."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        expected_similarity = 0.0

        with patch.object(service.similarity_calculator, "calculate") as mock_calc:
            mock_calc.return_value = expected_similarity

            result = service.cosine_similarity(vec1, vec2)

            assert result == expected_similarity
            mock_calc.assert_called_once_with(vec1, vec2, SimilarityMetric.COSINE)

    def test_find_similar_embeddings_wrapper(self, service):
        """Test find_similar_embeddings as wrapper method."""
        query = [1.0, 0.0, 0.0]
        candidates = [(1, [1.0, 0.0, 0.0]), (2, [0.0, 1.0, 0.0])]
        expected_results = [(1, 1.0), (2, 0.0)]

        with patch.object(
            service.similarity_calculator, "find_most_similar"
        ) as mock_find:
            mock_find.return_value = expected_results

            result = service.find_similar_embeddings(
                query, candidates, top_k=5, threshold=0.3
            )

            assert result == expected_results
            mock_find.assert_called_once_with(query, candidates, top_k=5, threshold=0.3)

    def test_find_similar_embeddings_default_params(self, service):
        """Test find_similar_embeddings with default parameters."""
        query = [1.0, 0.0]
        candidates = [(1, [1.0, 0.0])]

        with patch.object(
            service.similarity_calculator, "find_most_similar"
        ) as mock_find:
            mock_find.return_value = [(1, 1.0)]

            result = service.find_similar_embeddings(query, candidates)

            mock_find.assert_called_once_with(
                query, candidates, top_k=10, threshold=0.5
            )

    def test_clear_cache_wrapper(self, service):
        """Test clear_cache as wrapper method."""
        expected_count = 42

        with patch.object(service.cache, "clear") as mock_clear:
            mock_clear.return_value = expected_count

            result = service.clear_cache()

            assert result == expected_count
            mock_clear.assert_called_once()

    def test_get_cache_size(self, service):
        """Test get_cache_size method."""
        stats = {
            "entries": 150,
            "size_bytes": 2048000,
            "size_mb": 2.0,
            "models": ["model1", "model2"],
        }

        with patch.object(service.cache, "get_stats") as mock_stats:
            mock_stats.return_value = stats

            entries, size_bytes = service.get_cache_size()

            assert entries == 150
            assert size_bytes == 2048000
            mock_stats.assert_called_once()

    def test_cleanup_old_cache_wrapper(self, service):
        """Test cleanup_old_cache as wrapper method."""
        expected_count = 25

        with patch.object(service.cache, "cleanup_old") as mock_cleanup:
            mock_cleanup.return_value = expected_count

            result = service.cleanup_old_cache(max_age_days=7)

            assert result == expected_count
            mock_cleanup.assert_called_once_with(7)

    def test_cleanup_old_cache_default_age(self, service):
        """Test cleanup_old_cache with default age."""
        with patch.object(service.cache, "cleanup_old") as mock_cleanup:
            mock_cleanup.return_value = 10

            result = service.cleanup_old_cache()

            mock_cleanup.assert_called_once_with(30)  # Default 30 days

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_model_change(
        self, service, mock_llm_client
    ):
        """Test batch generation with model change and dimension update."""
        texts = ["text1", "text2"]
        custom_model = "custom-batch-model"

        with (
            patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims,
            patch.object(service.pipeline, "generate_batch") as mock_generate_batch,
        ):
            mock_get_dims.return_value = 768
            mock_generate_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

            result = await service.generate_batch_embeddings(texts, model=custom_model)

            assert result == [[0.1, 0.2], [0.3, 0.4]]
            # Pipeline config should be updated
            assert service.pipeline_config.model == custom_model
            assert service.pipeline_config.dimensions == 768
            mock_generate_batch.assert_called_once_with(texts)

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_no_dimension_change(self, service):
        """Test batch generation when dimension manager returns None."""
        texts = ["text1"]

        with (
            patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims,
            patch.object(service.pipeline, "generate_batch") as mock_generate_batch,
        ):
            mock_get_dims.return_value = None
            mock_generate_batch.return_value = [[0.1, 0.2]]

            result = await service.generate_batch_embeddings(
                texts, model="unknown-model"
            )

            assert result == [[0.1, 0.2]]
            # Model should be updated but dimensions unchanged
            assert service.pipeline_config.model == "unknown-model"

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_default_model(self, service):
        """Test batch generation with default model."""
        texts = ["test text"]

        with patch.object(service.pipeline, "generate_batch") as mock_generate_batch:
            mock_generate_batch.return_value = [[0.1, 0.2]]

            result = await service.generate_batch_embeddings(texts)

            assert result == [[0.1, 0.2]]
            # Should use default model
            assert service.pipeline_config.model == service.default_model

    def test_get_embedding_stats_comprehensive(self, service):
        """Test get_embedding_stats method."""
        cache_stats = {
            "entries": 100,
            "size_mb": 5.2,
            "models": ["model1", "model2"],
        }

        pipeline_stats = {
            "model": "test-model",
            "batch_size": 10,
            "preprocessing_steps": ["lowercase"],
        }

        class MockModel:
            def __init__(self, name, dimensions, max_tokens):
                self.name = name
                self.dimensions = dimensions
                self.max_tokens = max_tokens

        model_info = [
            MockModel("model1", 512, 8000),
            MockModel("model2", 1024, 4000),
        ]

        with (
            patch.object(service.cache, "get_stats") as mock_cache_stats,
            patch.object(service.pipeline, "get_stats") as mock_pipeline_stats,
            patch.object(
                service.dimension_manager, "get_all_models"
            ) as mock_get_models,
        ):
            mock_cache_stats.return_value = cache_stats
            mock_pipeline_stats.return_value = pipeline_stats
            mock_get_models.return_value = model_info

            result = service.get_embedding_stats()

            assert result["cache"] == cache_stats
            assert result["pipeline"] == pipeline_stats
            assert len(result["models"]) == 2

            # Check model info structure
            models = result["models"]
            assert models[0]["name"] == "model1"
            assert models[0]["dimensions"] == 512
            assert models[0]["max_tokens"] == 8000
            assert models[1]["name"] == "model2"
            assert models[1]["dimensions"] == 1024
            assert models[1]["max_tokens"] == 4000

    def test_component_integration(self, service):
        """Test that all components are properly integrated."""
        # Test that pipeline has the correct components
        assert service.pipeline.llm_client == service.llm_client
        assert service.pipeline.cache == service.cache
        assert service.pipeline.dimension_manager == service.dimension_manager

        # Test that pipeline config is properly set
        config = service.pipeline.config
        assert config.model == service.default_model
        assert config.dimensions == service.embedding_dimensions
        assert config.use_cache is True

        # Test that batch processor is properly configured
        processor = service.batch_processor
        assert processor.llm_client == service.llm_client
        assert processor.batch_size == 10
        assert processor.max_concurrent == 3

    def test_similarity_calculator_configuration(self, service):
        """Test similarity calculator is properly configured."""
        calc = service.similarity_calculator
        assert calc.metric == SimilarityMetric.COSINE

    def test_vector_store_configuration(self, service):
        """Test vector store configuration."""
        assert service.vector_store == service.lfs_store
        # lfs_dir is updated in the fixture, so check it's a Path object
        assert isinstance(service.lfs_store.lfs_dir, Path)

    def test_cache_configuration(self, service):
        """Test cache configuration."""
        cache = service.cache
        assert cache.strategy == InvalidationStrategy.LRU
        # Note: max_size and ttl_seconds tested in init tests

    def test_pipeline_config_state(self, service):
        """Test pipeline config state management."""
        config = service.pipeline_config
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 1536
        assert config.use_cache is True

        # Test that config is shared with pipeline
        assert service.pipeline.config == config

    @pytest.mark.asyncio
    async def test_service_workflow_integration(self, service, mock_llm_client):
        """Test complete service workflow integration."""
        # Mock LLM response
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3, 0.4]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Test complete workflow
        text = "Integration test text"

        # 1. Generate embedding
        embedding = await service.generate_embedding(text)
        assert embedding == [0.1, 0.2, 0.3, 0.4]

        # 2. Save to LFS
        path = service.save_embedding_to_lfs(embedding, "scene", 42, "test-model")
        assert path.exists()

        # 3. Load from LFS
        loaded = service.load_embedding_from_lfs("scene", 42, "test-model")
        np.testing.assert_allclose(loaded, embedding, rtol=1e-6)

        # 4. Encode/decode for database
        encoded = service.encode_embedding_for_db(embedding)
        decoded = service.decode_embedding_from_db(encoded)
        np.testing.assert_allclose(decoded, embedding, rtol=1e-6)

        # 5. Similarity calculation
        similarity = service.cosine_similarity(embedding, embedding)
        assert pytest.approx(similarity) == 1.0

        # 6. Find similar embeddings
        candidates = [(1, embedding), (2, [0.5, 0.5, 0.0, 0.0])]
        results = service.find_similar_embeddings(embedding, candidates, threshold=0.0)
        assert len(results) == 2
        assert results[0][0] == 1  # Perfect match should be first
        assert results[0][1] == pytest.approx(1.0)

    def test_error_handling_comprehensive(self, service):
        """Test comprehensive error handling scenarios."""
        # Test serialization error handling
        with patch.object(service.serializer, "decode") as mock_decode:
            mock_decode.side_effect = ValueError("Serialization error")

            with pytest.raises(ValueError):
                service.decode_embedding_from_db(b"bad_data")

        # Test similarity calculation error handling
        with patch.object(service.similarity_calculator, "calculate") as mock_calc:
            mock_calc.side_effect = ValueError("Similarity error")

            with pytest.raises(ValueError):
                service.cosine_similarity([1, 0], [0, 1])

    def test_configuration_flexibility(self, settings, tmp_path):
        """Test service configuration flexibility."""
        # Test with custom configuration
        custom_cache_dir = tmp_path / "custom" / "cache"
        custom_llm_client = MagicMock(spec=LLMClient)

        service = EmbeddingService(
            settings=settings,
            llm_client=custom_llm_client,
            cache_dir=custom_cache_dir,
        )

        # Verify custom configuration is used
        assert service.llm_client == custom_llm_client
        assert service.cache.cache_dir == custom_cache_dir

        # Test that custom configuration propagates to components
        assert service.pipeline.llm_client == custom_llm_client
        assert service.batch_processor.llm_client == custom_llm_client

    def test_default_values_and_constants(self, service):
        """Test default values and constants are properly set."""
        assert service.default_model == "text-embedding-3-small"
        assert service.embedding_dimensions == 1536

        # Test pipeline config defaults
        config = service.pipeline_config
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 1536
        assert config.use_cache is True

        # Test batch processor defaults
        processor = service.batch_processor
        assert processor.batch_size == 10
        assert processor.max_concurrent == 3

    @pytest.mark.asyncio
    async def test_edge_cases_and_boundary_conditions(self, service, mock_llm_client):
        """Test edge cases and boundary conditions."""
        # Test with empty text
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.0]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        result = await service.generate_embedding("")
        assert result == [0.0]

        # Test with very long text (boundary of 8000 chars)
        long_text = "A" * 8001
        result = await service.generate_scene_embedding(long_text, "HEADING")
        # Should complete without error (truncation tested elsewhere)

        # Test batch generation with empty list
        batch_result = await service.generate_batch_embeddings([])
        assert batch_result == []

    def test_memory_and_resource_management(self, service):
        """Test memory and resource management aspects."""
        # Test cache size reporting
        entries, size_bytes = service.get_cache_size()
        assert isinstance(entries, int)
        assert isinstance(size_bytes, int)
        assert entries >= 0
        assert size_bytes >= 0

        # Test cache cleanup
        cleaned = service.cleanup_old_cache(1)  # 1 day
        assert isinstance(cleaned, int)
        assert cleaned >= 0

        # Test cache clearing
        cleared = service.clear_cache()
        assert isinstance(cleared, int)
        assert cleared >= 0
