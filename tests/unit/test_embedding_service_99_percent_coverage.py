"""Ultra-comprehensive tests for EmbeddingService to achieve 99% coverage.

This module focuses on edge cases, error scenarios, and branch coverage
to ensure the EmbeddingService is thoroughly tested.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings
from scriptrag.embeddings.cache import InvalidationStrategy
from scriptrag.embeddings.dimensions import ModelInfo
from scriptrag.embeddings.similarity import SimilarityMetric
from scriptrag.exceptions import ScriptRAGError
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


class TestEmbeddingServiceUltraComprehensive:
    """Ultra-comprehensive tests for all EmbeddingService branches and edge cases."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return ScriptRAGSettings()

    @pytest.fixture
    def mock_llm_client(self):
        """Create comprehensive mock LLM client."""
        client = MagicMock(spec=LLMClient)
        client.embed = AsyncMock(spec=object)
        return client

    @pytest.fixture
    def service_with_custom_cache(self, settings, mock_llm_client, tmp_path):
        """Create service with custom cache directory."""
        cache_dir = tmp_path / "custom_cache"
        service = EmbeddingService(
            settings=settings,
            llm_client=mock_llm_client,
            cache_dir=cache_dir,
        )
        service.lfs_store.lfs_dir = tmp_path / ".embeddings"
        return service

    @pytest.fixture
    def service_with_default_cache(self, settings, mock_llm_client):
        """Create service with default cache (None)."""
        return EmbeddingService(
            settings=settings,
            llm_client=mock_llm_client,
            cache_dir=None,  # Force default path
        )

    def test_init_with_none_cache_dir_branch(self, settings, mock_llm_client):
        """Test initialization when cache_dir is None - triggers default path."""
        service = EmbeddingService(
            settings=settings,
            llm_client=mock_llm_client,
            cache_dir=None,
        )

        expected_cache_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        assert service.cache.cache_dir == expected_cache_dir

    def test_init_with_none_llm_client_branch(self, settings):
        """Test initialization when llm_client is None - triggers default creation."""
        service = EmbeddingService(
            settings=settings,
            llm_client=None,  # Force default creation
        )

        assert isinstance(service.llm_client, LLMClient)
        assert service.settings == settings

    @pytest.mark.asyncio
    async def test_generate_embedding_model_change_with_dimensions(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test generate_embedding when model changes and dimensions are found."""
        service = service_with_custom_cache
        mock_response = EmbeddingResponse(
            model="custom-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Mock dimension manager to return dimensions
        with patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims:
            mock_get_dims.return_value = 768

            result = await service.generate_embedding("test", model="custom-model")

            assert result == [0.1, 0.2, 0.3]
            assert service.pipeline_config.model == "custom-model"
            assert service.pipeline_config.dimensions == 768
            mock_get_dims.assert_called_with("custom-model")
            assert (
                mock_get_dims.call_count >= 1
            )  # May be called multiple times in pipeline

    @pytest.mark.asyncio
    async def test_generate_embedding_model_change_no_dimensions(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test generate_embedding when model changes but no dimensions found."""
        service = service_with_custom_cache
        mock_response = EmbeddingResponse(
            model="unknown-model",
            data=[{"embedding": [0.4, 0.5]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Store original dimensions
        original_dims = service.pipeline_config.dimensions

        # Mock dimension manager to return None
        with patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims:
            mock_get_dims.return_value = None

            result = await service.generate_embedding("test", model="unknown-model")

            assert result == [0.4, 0.5]
            assert service.pipeline_config.model == "unknown-model"
            # Dimensions should remain unchanged when None returned
            assert service.pipeline_config.dimensions == original_dims

    @pytest.mark.asyncio
    async def test_generate_embedding_same_model_no_change(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test generate_embedding when model doesn't change - no dimension lookup."""
        service = service_with_custom_cache
        mock_response = EmbeddingResponse(
            model="text-embedding-3-small",  # Same as default
            data=[{"embedding": [0.6, 0.7, 0.8]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        original_dims = service.pipeline_config.dimensions

        # Mock dimension manager - it may still be called in pipeline validation
        with patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims:
            result = await service.generate_embedding("test")  # Use default model

            assert result == [0.6, 0.7, 0.8]
            # Model should remain the default
            assert service.pipeline_config.model == service.default_model
            assert service.pipeline_config.dimensions == original_dims

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_text_truncation_with_model_info(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test scene embedding with text truncation when model info exists."""
        service = service_with_custom_cache
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Create very long content
        long_content = "A" * 10000
        heading = "INT. ROOM - DAY"

        # Mock model info with small max_tokens
        mock_model_info = ModelInfo(name="test-model", dimensions=512, max_tokens=100)
        with patch.object(service.dimension_manager, "get_model_info") as mock_get_info:
            mock_get_info.return_value = mock_model_info

            with patch.object(service, "generate_embedding") as mock_generate:
                mock_generate.return_value = [0.1, 0.2]

                result = await service.generate_scene_embedding(
                    long_content, heading, "test-model"
                )

                assert result == [0.1, 0.2]

                # Check that text was truncated based on max_tokens
                call_args = mock_generate.call_args[0][0]
                max_length = 100 * 4  # max_tokens * 4
                assert len(call_args) <= max_length + 3  # +3 for "..."
                assert call_args.endswith("...")

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_no_model_info_fallback(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test scene embedding fallback when model info is None."""
        service = service_with_custom_cache
        mock_response = EmbeddingResponse(
            model="unknown-model",
            data=[{"embedding": [0.3, 0.4]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Create long content
        long_content = "B" * 9000
        heading = "EXT. STREET - NIGHT"

        # Mock model info to return None
        with patch.object(service.dimension_manager, "get_model_info") as mock_get_info:
            mock_get_info.return_value = None  # No model info available

            with patch.object(service, "generate_embedding") as mock_generate:
                mock_generate.return_value = [0.3, 0.4]

                result = await service.generate_scene_embedding(
                    long_content, heading, "unknown-model"
                )

                assert result == [0.3, 0.4]

                # Should use fallback max_length of 8000
                call_args = mock_generate.call_args[0][0]
                assert len(call_args) <= 8000 + 3  # Fallback + "..."
                assert call_args.endswith("...")

    @pytest.mark.asyncio
    async def test_generate_scene_embedding_short_text_no_truncation(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test scene embedding with short text - no truncation."""
        service = service_with_custom_cache

        short_content = "Short scene."
        heading = "INT. OFFICE - DAY"

        with patch.object(service, "generate_embedding") as mock_generate:
            mock_generate.return_value = [0.5, 0.6]

            result = await service.generate_scene_embedding(short_content, heading)

            assert result == [0.5, 0.6]

            # Text should not be truncated
            call_args = mock_generate.call_args[0][0]
            assert not call_args.endswith("...")
            assert "Scene: INT. OFFICE - DAY" in call_args
            assert short_content in call_args

    def test_save_embedding_to_lfs_path_compatibility(
        self, service_with_custom_cache, tmp_path
    ):
        """Test save_embedding_to_lfs returns correct path for compatibility."""
        service = service_with_custom_cache
        service.lfs_store.lfs_dir = tmp_path / ".embeddings"

        embedding = [0.7, 0.8, 0.9]
        entity_type = "character"
        entity_id = 42
        model = "test-model"

        # Mock the store and get_embedding_path methods
        with (
            patch.object(service.lfs_store, "store") as mock_store,
            patch.object(service.lfs_store, "get_embedding_path") as mock_get_path,
        ):
            expected_path = tmp_path / "expected_path.npy"
            mock_get_path.return_value = expected_path

            result_path = service.save_embedding_to_lfs(
                embedding, entity_type, entity_id, model
            )

            assert result_path == expected_path
            mock_store.assert_called_once_with(entity_type, entity_id, embedding, model)
            mock_get_path.assert_called_once_with(entity_type, entity_id, model)

    def test_decode_embedding_from_db_error_propagation(
        self, service_with_custom_cache
    ):
        """Test that decode errors are properly propagated without catching."""
        service = service_with_custom_cache

        # Mock serializer to raise ValueError
        with patch.object(service.serializer, "decode") as mock_decode:
            mock_decode.side_effect = ValueError("Corrupted data")

            with pytest.raises(ValueError) as exc_info:
                service.decode_embedding_from_db(b"corrupted")

            assert "Corrupted data" in str(exc_info.value)
            mock_decode.assert_called_once_with(b"corrupted")

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_same_model_no_change(
        self, service_with_custom_cache
    ):
        """Test batch generation when model matches current config."""
        service = service_with_custom_cache
        texts = ["text1", "text2"]

        # Ensure current model matches what we'll pass
        service.pipeline_config.model = "text-embedding-3-small"

        with (
            patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims,
            patch.object(service.pipeline, "generate_batch") as mock_generate_batch,
        ):
            mock_generate_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

            result = await service.generate_batch_embeddings(
                texts,
                model="text-embedding-3-small",  # Same as current
            )

            assert result == [[0.1, 0.2], [0.3, 0.4]]
            # get_dimensions should NOT be called since model didn't change
            mock_get_dims.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_with_dimension_update(
        self, service_with_custom_cache
    ):
        """Test batch generation with dimension update."""
        service = service_with_custom_cache
        texts = ["batch1", "batch2", "batch3"]
        custom_model = "custom-batch-model"

        with (
            patch.object(service.dimension_manager, "get_dimensions") as mock_get_dims,
            patch.object(service.pipeline, "generate_batch") as mock_generate_batch,
        ):
            mock_get_dims.return_value = 256
            mock_generate_batch.return_value = [[0.1], [0.2], [0.3]]

            result = await service.generate_batch_embeddings(texts, model=custom_model)

            assert result == [[0.1], [0.2], [0.3]]
            assert service.pipeline_config.model == custom_model
            assert service.pipeline_config.dimensions == 256

    def test_get_embedding_stats_comprehensive_structure(
        self, service_with_custom_cache
    ):
        """Test get_embedding_stats returns complete structure."""
        service = service_with_custom_cache

        # Mock comprehensive stats
        cache_stats = {
            "entries": 500,
            "size_bytes": 1024000,
            "size_mb": 1.0,
            "hit_rate": 0.85,
        }

        pipeline_stats = {
            "total_requests": 1000,
            "cache_hits": 850,
            "model": "text-embedding-3-small",
        }

        class MockModelInfo:
            def __init__(self, name, dimensions, max_tokens):
                self.name = name
                self.dimensions = dimensions
                self.max_tokens = max_tokens

        mock_models = [
            MockModelInfo("model1", 768, 8000),
            MockModelInfo("model2", 1024, 4000),
            MockModelInfo("model3", 1536, 8191),
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
            mock_get_models.return_value = mock_models

            stats = service.get_embedding_stats()

            # Verify structure
            assert stats["cache"] == cache_stats
            assert stats["pipeline"] == pipeline_stats
            assert len(stats["models"]) == 3

            # Verify model info transformation
            models = stats["models"]
            assert models[0]["name"] == "model1"
            assert models[0]["dimensions"] == 768
            assert models[0]["max_tokens"] == 8000

    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline_generation(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test comprehensive error handling in pipeline generation."""
        service = service_with_custom_cache

        # Test various exception types
        test_exceptions = [
            ValueError("Invalid input"),
            RuntimeError("Runtime failure"),
            ConnectionError("Network issue"),
            TimeoutError("Request timeout"),
        ]

        for exception in test_exceptions:
            with patch.object(service.pipeline, "generate_embedding") as mock_pipeline:
                mock_pipeline.side_effect = exception

                with pytest.raises(ScriptRAGError) as exc_info:
                    await service.generate_embedding("test", model="error-model")

                error = exc_info.value
                assert "Failed to generate embedding" in error.message
                assert str(exception) in str(error)
                assert "Check LLM provider configuration" in error.hint
                assert error.details["model"] == "error-model"
                assert error.details["text_length"] == 4  # len("test")

    def test_component_integration_verification(self, service_with_custom_cache):
        """Test that all components are properly integrated and configured."""
        service = service_with_custom_cache

        # Verify pipeline integration
        assert service.pipeline.llm_client is service.llm_client
        assert service.pipeline.cache is service.cache
        assert service.pipeline.dimension_manager is service.dimension_manager
        assert service.pipeline.config is service.pipeline_config

        # Verify batch processor integration
        assert service.batch_processor.llm_client is service.llm_client

        # Verify configuration consistency
        assert service.pipeline_config.model == service.default_model
        assert service.pipeline_config.dimensions == service.embedding_dimensions
        assert service.pipeline_config.use_cache is True

        # Verify cache configuration
        assert service.cache.strategy == InvalidationStrategy.LRU

        # Verify similarity calculator
        assert service.similarity_calculator.metric == SimilarityMetric.COSINE

    @pytest.mark.asyncio
    async def test_model_fallback_scenarios(self, service_with_custom_cache):
        """Test various model fallback scenarios."""
        service = service_with_custom_cache

        # Test with None model (should use default)
        with patch.object(service.pipeline, "generate_embedding") as mock_generate:
            mock_generate.return_value = [0.7, 0.8, 0.9]

            result = await service.generate_embedding("test", model=None)
            assert result == [0.7, 0.8, 0.9]
            # Should use default model
            assert service.pipeline_config.model == service.default_model

    def test_edge_case_similarity_calculations(self, service_with_custom_cache):
        """Test similarity calculations with various edge cases."""
        service = service_with_custom_cache

        edge_cases = [
            # Very small numbers
            ([1e-15, 1e-15], [1e-15, 1e-15]),
            # Mixed large and small
            ([1e10, 1e-10], [1e-10, 1e10]),
            # All zeros (handled by calculator)
            ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
        ]

        for vec1, vec2 in edge_cases:
            with patch.object(service.similarity_calculator, "calculate") as mock_calc:
                mock_calc.return_value = 0.5  # Mock result

                result = service.cosine_similarity(vec1, vec2)
                assert result == 0.5
                mock_calc.assert_called_with(vec1, vec2, SimilarityMetric.COSINE)

    @pytest.mark.asyncio
    async def test_comprehensive_workflow_integration(
        self, service_with_custom_cache, mock_llm_client
    ):
        """Test complete workflow integration with all components."""
        service = service_with_custom_cache

        # Mock all necessary components
        mock_response = EmbeddingResponse(
            model="integration-test",
            data=[{"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Complete workflow test
        text = "Comprehensive integration test"
        model = "integration-test"

        # 1. Generate embedding with model change
        with patch.object(service.dimension_manager, "get_dimensions") as mock_dims:
            mock_dims.return_value = 512

            embedding = await service.generate_embedding(text, model=model)
            assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
            assert service.pipeline_config.model == model
            assert service.pipeline_config.dimensions == 512

        # 2. Test scene embedding with same model (no dimension lookup)
        scene_embedding = await service.generate_scene_embedding(
            "Scene content", "INT. ROOM - DAY", model=model
        )
        assert scene_embedding == [0.1, 0.2, 0.3, 0.4, 0.5]

        # 3. Save to LFS
        service.lfs_store.lfs_dir.mkdir(parents=True, exist_ok=True)
        path = service.save_embedding_to_lfs(embedding, "test", 1, model)
        assert path.exists()

        # 4. Load from LFS
        loaded = service.load_embedding_from_lfs("test", 1, model)
        np.testing.assert_allclose(loaded, embedding, rtol=1e-6)

        # 5. Database encoding/decoding
        encoded = service.encode_embedding_for_db(embedding)
        decoded = service.decode_embedding_from_db(encoded)
        np.testing.assert_allclose(decoded, embedding, rtol=1e-6)

        # 6. Similarity operations
        similarity = service.cosine_similarity(embedding, embedding)
        assert pytest.approx(similarity) == 1.0

        # 7. Batch generation
        batch_texts = ["batch1", "batch2"]
        with patch.object(service.pipeline, "generate_batch") as mock_batch:
            mock_batch.return_value = [embedding, embedding]
            batch_results = await service.generate_batch_embeddings(batch_texts, model)
            assert len(batch_results) == 2

        # 8. Statistics and cache operations
        stats = service.get_embedding_stats()
        assert "cache" in stats
        assert "pipeline" in stats
        assert "models" in stats

        cache_entries, cache_size = service.get_cache_size()
        assert isinstance(cache_entries, int)
        assert isinstance(cache_size, int)

        cleaned = service.cleanup_old_cache(1)
        assert isinstance(cleaned, int)

        cleared = service.clear_cache()
        assert isinstance(cleared, int)

        # Workflow completed successfully - all components integrated
        assert True  # If we reach here, integration test passed
