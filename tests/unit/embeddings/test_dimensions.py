"""Comprehensive tests for dimension management."""

import pytest

from scriptrag.embeddings.dimensions import (
    DimensionManager,
    EmbeddingModel,
    ModelInfo,
)


class TestEmbeddingModel:
    """Test EmbeddingModel enum."""

    def test_enum_values(self):
        """Test that enum values have correct attributes."""
        model = EmbeddingModel.TEXT_EMBEDDING_3_SMALL
        assert model.model_name == "text-embedding-3-small"
        assert model.dimensions == 1536

    def test_all_models_have_attributes(self):
        """Test that all models have required attributes."""
        for model in EmbeddingModel:
            assert hasattr(model, "model_name")
            assert hasattr(model, "dimensions")
            assert isinstance(model.model_name, str)
            assert isinstance(model.dimensions, int)
            assert model.dimensions > 0

    def test_model_name_uniqueness(self):
        """Test that model names are unique."""
        names = [model.model_name for model in EmbeddingModel]
        assert len(names) == len(set(names))

    def test_specific_models(self):
        """Test specific model configurations."""
        # OpenAI models
        assert EmbeddingModel.TEXT_EMBEDDING_3_SMALL.dimensions == 1536
        assert EmbeddingModel.TEXT_EMBEDDING_3_LARGE.dimensions == 3072
        assert EmbeddingModel.TEXT_EMBEDDING_ADA_002.dimensions == 1536

        # Cohere models
        assert EmbeddingModel.EMBED_ENGLISH_V3.dimensions == 1024
        assert EmbeddingModel.EMBED_MULTILINGUAL_V3.dimensions == 1024
        assert EmbeddingModel.EMBED_ENGLISH_LIGHT_V3.dimensions == 384

        # Open source models
        assert EmbeddingModel.ALL_MINILM_L6_V2.dimensions == 384
        assert EmbeddingModel.BGE_LARGE_EN.dimensions == 1024


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_init_minimal(self):
        """Test ModelInfo with minimal parameters."""
        info = ModelInfo(name="test-model", dimensions=512)
        assert info.name == "test-model"
        assert info.dimensions == 512
        assert info.max_tokens is None
        assert info.supports_truncation is True
        assert info.supports_custom_dimensions is False
        assert info.min_custom_dimensions is None
        assert info.max_custom_dimensions is None
        assert info.metadata is None

    def test_init_full(self):
        """Test ModelInfo with all parameters."""
        metadata = {"provider": "openai"}
        info = ModelInfo(
            name="advanced-model",
            dimensions=1024,
            max_tokens=8000,
            supports_truncation=False,
            supports_custom_dimensions=True,
            min_custom_dimensions=256,
            max_custom_dimensions=2048,
            metadata=metadata,
        )
        assert info.name == "advanced-model"
        assert info.dimensions == 1024
        assert info.max_tokens == 8000
        assert info.supports_truncation is False
        assert info.supports_custom_dimensions is True
        assert info.min_custom_dimensions == 256
        assert info.max_custom_dimensions == 2048
        assert info.metadata == metadata


class TestDimensionManager:
    """Test DimensionManager class."""

    @pytest.fixture
    def manager(self):
        """Create dimension manager."""
        return DimensionManager()

    def test_init(self, manager):
        """Test dimension manager initialization."""
        assert isinstance(manager._models, dict)
        assert len(manager._models) > 0  # Should have loaded default models

    def test_default_models_loaded(self, manager):
        """Test that default models are loaded."""
        # Check some known models
        assert manager.has_model("text-embedding-3-small")
        assert manager.has_model("text-embedding-3-large")
        assert manager.has_model("text-embedding-ada-002")

        # Check enum models are loaded
        for model in EmbeddingModel:
            assert manager.has_model(model.model_name)

    def test_register_model(self, manager):
        """Test registering a new model."""
        info = ModelInfo(
            name="custom-model",
            dimensions=768,
            max_tokens=4000,
        )

        assert not manager.has_model("custom-model")
        manager.register_model(info)
        assert manager.has_model("custom-model")

        retrieved = manager.get_model_info("custom-model")
        assert retrieved is not None
        assert retrieved.name == "custom-model"
        assert retrieved.dimensions == 768
        assert retrieved.max_tokens == 4000

    def test_register_model_overwrites(self, manager):
        """Test that registering overwrites existing model."""
        original = manager.get_model_info("text-embedding-3-small")
        assert original is not None
        original_dimensions = original.dimensions

        # Register with different dimensions
        new_info = ModelInfo(
            name="text-embedding-3-small",
            dimensions=original_dimensions + 100,
        )
        manager.register_model(new_info)

        updated = manager.get_model_info("text-embedding-3-small")
        assert updated is not None
        assert updated.dimensions == original_dimensions + 100

    def test_has_model(self, manager):
        """Test model existence check."""
        assert manager.has_model("text-embedding-3-small")
        assert not manager.has_model("nonexistent-model")

    def test_get_model_info_exists(self, manager):
        """Test getting info for existing model."""
        info = manager.get_model_info("text-embedding-3-small")
        assert info is not None
        assert info.name == "text-embedding-3-small"
        assert info.dimensions == 1536
        assert info.supports_custom_dimensions is True

    def test_get_model_info_nonexistent(self, manager):
        """Test getting info for non-existent model."""
        info = manager.get_model_info("nonexistent-model")
        assert info is None

    def test_get_dimensions_exists(self, manager):
        """Test getting dimensions for existing model."""
        dimensions = manager.get_dimensions("text-embedding-3-small")
        assert dimensions == 1536

        dimensions = manager.get_dimensions("text-embedding-3-large")
        assert dimensions == 3072

    def test_get_dimensions_nonexistent(self, manager):
        """Test getting dimensions for non-existent model."""
        dimensions = manager.get_dimensions("nonexistent-model")
        assert dimensions is None

    def test_validate_dimensions_unknown_model(self, manager):
        """Test dimension validation for unknown model."""
        valid, error = manager.validate_dimensions("unknown-model", 512)
        assert valid is True
        assert error is None

    def test_validate_dimensions_fixed_model_correct(self, manager):
        """Test validation for fixed-dimension model with correct dimensions."""
        valid, error = manager.validate_dimensions("text-embedding-ada-002", 1536)
        assert valid is True
        assert error is None

    def test_validate_dimensions_fixed_model_incorrect(self, manager):
        """Test validation for fixed-dimension model with incorrect dimensions."""
        valid, error = manager.validate_dimensions("text-embedding-ada-002", 512)
        assert valid is False
        assert error is not None
        assert "requires exactly 1536 dimensions" in error

    def test_validate_dimensions_custom_model_valid_range(self, manager):
        """Test validation for custom-dimension model within range."""
        # text-embedding-3-small supports 256-1536 dimensions
        valid, error = manager.validate_dimensions("text-embedding-3-small", 512)
        assert valid is True
        assert error is None

        valid, error = manager.validate_dimensions("text-embedding-3-small", 256)
        assert valid is True
        assert error is None

        valid, error = manager.validate_dimensions("text-embedding-3-small", 1536)
        assert valid is True
        assert error is None

    def test_validate_dimensions_custom_model_below_min(self, manager):
        """Test validation for custom-dimension model below minimum."""
        valid, error = manager.validate_dimensions("text-embedding-3-small", 128)
        assert valid is False
        assert error is not None
        assert "requires at least 256 dimensions" in error

    def test_validate_dimensions_custom_model_above_max(self, manager):
        """Test validation for custom-dimension model above maximum."""
        valid, error = manager.validate_dimensions("text-embedding-3-small", 2048)
        assert valid is False
        assert error is not None
        assert "supports at most 1536 dimensions" in error

    def test_validate_dimensions_custom_model_no_limits(self, manager):
        """Test validation for custom model with no dimension limits."""
        # Register a model with custom dimensions but no limits
        info = ModelInfo(
            name="unlimited-model",
            dimensions=512,
            supports_custom_dimensions=True,
            # No min/max specified
        )
        manager.register_model(info)

        # Should accept any dimensions
        valid, error = manager.validate_dimensions("unlimited-model", 100)
        assert valid is True
        assert error is None

        valid, error = manager.validate_dimensions("unlimited-model", 5000)
        assert valid is True
        assert error is None

    def test_normalize_vector_same_dimensions(self, manager):
        """Test vector normalization when dimensions match target."""
        vector = [0.1, 0.2, 0.3]
        result = manager.normalize_vector(vector, 3)
        assert result == vector

    def test_normalize_vector_pad_with_zeros(self, manager):
        """Test vector normalization by padding with zeros."""
        vector = [0.1, 0.2]
        result = manager.normalize_vector(vector, 5)
        expected = [0.1, 0.2, 0.0, 0.0, 0.0]
        assert result == expected

    def test_normalize_vector_truncate(self, manager):
        """Test vector normalization by truncation."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = manager.normalize_vector(vector, 3)
        expected = [0.1, 0.2, 0.3]
        assert result == expected

    def test_normalize_vector_empty(self, manager):
        """Test vector normalization with empty input."""
        vector = []
        result = manager.normalize_vector(vector, 3)
        expected = [0.0, 0.0, 0.0]
        assert result == expected

    def test_normalize_vector_target_zero(self, manager):
        """Test vector normalization to zero dimensions."""
        vector = [0.1, 0.2, 0.3]
        result = manager.normalize_vector(vector, 0)
        assert result == []

    def test_validate_vector_valid(self, manager):
        """Test validation of valid vector."""
        vector = [0.1, 0.2, 0.3, -0.1]
        valid, error = manager.validate_vector(vector)
        assert valid is True
        assert error is None

    def test_validate_vector_empty(self, manager):
        """Test validation of empty vector."""
        valid, error = manager.validate_vector([])
        assert valid is False
        assert error == "Empty vector"

    def test_validate_vector_non_numeric(self, manager):
        """Test validation of vector with non-numeric values."""
        vector = [0.1, "string", 0.3]
        valid, error = manager.validate_vector(vector)
        assert valid is False
        assert error == "Vector contains non-numeric values"

        vector = [0.1, None, 0.3]
        valid, error = manager.validate_vector(vector)
        assert valid is False
        assert error == "Vector contains non-numeric values"

    def test_validate_vector_nan_values(self, manager):
        """Test validation of vector with NaN values."""
        vector = [0.1, float("nan"), 0.3]
        valid, error = manager.validate_vector(vector)
        assert valid is False
        assert error == "Vector contains NaN or Inf values"

    def test_validate_vector_inf_values(self, manager):
        """Test validation of vector with infinite values."""
        vector = [0.1, float("inf"), 0.3]
        valid, error = manager.validate_vector(vector)
        assert valid is False
        assert error == "Vector contains NaN or Inf values"

        vector = [0.1, float("-inf"), 0.3]
        valid, error = manager.validate_vector(vector)
        assert valid is False
        assert error == "Vector contains NaN or Inf values"

    def test_validate_vector_with_model_correct_dimensions(self, manager):
        """Test vector validation with model and correct dimensions."""
        vector = [0.1] * 1536  # Correct size for text-embedding-3-small
        valid, error = manager.validate_vector(vector, "text-embedding-3-small")
        assert valid is True
        assert error is None

    def test_validate_vector_with_model_wrong_dimensions(self, manager):
        """Test vector validation with model and wrong dimensions."""
        vector = [0.1] * 512  # Wrong size for text-embedding-3-small
        valid, error = manager.validate_vector(vector, "text-embedding-3-small")
        assert valid is False
        assert "Dimension mismatch" in error
        assert "expected 1536" in error
        assert "got 512" in error

    def test_validate_vector_with_unknown_model(self, manager):
        """Test vector validation with unknown model."""
        vector = [0.1, 0.2, 0.3]
        valid, error = manager.validate_vector(vector, "unknown-model")
        assert valid is True
        assert error is None

    def test_validate_vector_mixed_numeric_types(self, manager):
        """Test validation of vector with mixed int/float types."""
        vector = [1, 2.0, 3, 4.5, 5]  # Mix of int and float
        valid, error = manager.validate_vector(vector)
        assert valid is True
        assert error is None

    def test_get_all_models(self, manager):
        """Test getting all registered models."""
        models = manager.get_all_models()
        assert isinstance(models, list)
        assert len(models) > 0

        # Should include default models
        model_names = [m.name for m in models]
        assert "text-embedding-3-small" in model_names
        assert "text-embedding-3-large" in model_names

        # All should be ModelInfo instances
        for model in models:
            assert isinstance(model, ModelInfo)
            assert hasattr(model, "name")
            assert hasattr(model, "dimensions")

    def test_suggest_model_exact_match(self, manager):
        """Test model suggestion with exact dimension match."""
        suggested = manager.suggest_model(target_dimensions=1536)
        assert suggested is not None
        # Should suggest a model that supports 1536 dimensions
        if suggested.supports_custom_dimensions:
            assert (suggested.min_custom_dimensions or 0) <= 1536
            assert (suggested.max_custom_dimensions or float("inf")) >= 1536
        else:
            assert suggested.dimensions == 1536

    def test_suggest_model_custom_dimensions(self, manager):
        """Test model suggestion for custom dimensions."""
        suggested = manager.suggest_model(target_dimensions=512)
        assert suggested is not None
        # Should find a model that supports 512 dimensions

    def test_suggest_model_with_token_limit(self, manager):
        """Test model suggestion with token limit requirement."""
        suggested = manager.suggest_model(target_dimensions=1536, max_tokens=8000)
        assert suggested is not None
        # If model has max_tokens, it should be >= 8000
        if suggested.max_tokens is not None:
            assert suggested.max_tokens >= 8000

    def test_suggest_model_no_match(self, manager):
        """Test model suggestion when no model matches."""
        # Request impossible dimension count
        suggested = manager.suggest_model(target_dimensions=50000)
        assert suggested is None

    def test_suggest_model_impossible_token_limit(self, manager):
        """Test model suggestion with impossible token limit."""
        suggested = manager.suggest_model(
            target_dimensions=1536,
            max_tokens=100000,  # Very high token limit
        )
        # Might return None if no model supports this many tokens
        # Or might return a model with no token limit specified
        if suggested is not None:
            assert suggested.max_tokens is None or suggested.max_tokens >= 100000

    def test_estimate_storage_size(self, manager):
        """Test storage size estimation for known model."""
        estimate = manager.estimate_storage_size("text-embedding-3-small", 1000)

        assert estimate["dimensions"] == 1536
        assert estimate["bytes_per_embedding"] == 1536 * 4  # float32 = 4 bytes
        assert estimate["total_bytes"] == 1536 * 4 * 1000
        assert estimate["total_mb"] == (1536 * 4 * 1000) / (1024 * 1024)
        assert estimate["total_gb"] == (1536 * 4 * 1000) / (1024 * 1024 * 1024)

        # Check values are reasonable
        assert estimate["total_mb"] > 0
        assert estimate["total_gb"] > 0
        assert estimate["total_mb"] > estimate["total_gb"]

    def test_estimate_storage_size_unknown_model(self, manager):
        """Test storage size estimation for unknown model."""
        estimate = manager.estimate_storage_size("unknown-model", 1000)

        # Should use default dimension estimate
        assert estimate["dimensions"] == 1536  # Default
        assert estimate["bytes_per_embedding"] == 1536 * 4
        assert estimate["total_bytes"] == 1536 * 4 * 1000

    def test_estimate_storage_size_zero_embeddings(self, manager):
        """Test storage size estimation with zero embeddings."""
        estimate = manager.estimate_storage_size("text-embedding-3-small", 0)

        assert estimate["total_bytes"] == 0
        assert estimate["total_mb"] == 0
        assert estimate["total_gb"] == 0
        assert estimate["bytes_per_embedding"] > 0  # Should still be positive

    def test_estimate_storage_size_large_numbers(self, manager):
        """Test storage size estimation with large numbers."""
        estimate = manager.estimate_storage_size("text-embedding-3-small", 1000000)

        assert estimate["total_bytes"] == 1536 * 4 * 1000000
        assert estimate["total_mb"] > 1000  # Should be substantial
        assert estimate["total_gb"] > 1  # Should be multiple GB

    def test_load_default_models_openai_specifics(self, manager):
        """Test that OpenAI models are loaded with correct configurations."""
        # Test text-embedding-3-small
        small_model = manager.get_model_info("text-embedding-3-small")
        assert small_model is not None
        assert small_model.dimensions == 1536
        assert small_model.max_tokens == 8191
        assert small_model.supports_custom_dimensions is True
        assert small_model.min_custom_dimensions == 256
        assert small_model.max_custom_dimensions == 1536

        # Test text-embedding-3-large
        large_model = manager.get_model_info("text-embedding-3-large")
        assert large_model is not None
        assert large_model.dimensions == 3072
        assert large_model.max_tokens == 8191
        assert large_model.supports_custom_dimensions is True
        assert large_model.min_custom_dimensions == 256
        assert large_model.max_custom_dimensions == 3072

        # Test text-embedding-ada-002
        ada_model = manager.get_model_info("text-embedding-ada-002")
        assert ada_model is not None
        assert ada_model.dimensions == 1536
        assert ada_model.max_tokens == 8191
        assert ada_model.supports_custom_dimensions is False

    def test_load_default_models_enum_integration(self, manager):
        """Test that enum models are properly integrated."""
        # All enum models should be available
        for model_enum in EmbeddingModel:
            info = manager.get_model_info(model_enum.model_name)
            assert info is not None
            assert info.dimensions == model_enum.dimensions

    def test_load_default_models_no_duplicates(self):
        """Test that default model loading doesn't create duplicates."""
        manager = DimensionManager()

        # Count initial models
        initial_count = len(manager._models)

        # Load defaults again (shouldn't increase count much)
        manager._load_default_models()
        final_count = len(manager._models)

        # Should be same or only slightly different due to explicit registrations
        assert final_count >= initial_count
        # Should not have doubled the count
        assert final_count < initial_count * 1.5

    def test_edge_case_zero_dimensions(self, manager):
        """Test edge case with zero dimensions."""
        # Register model with zero dimensions (edge case)
        info = ModelInfo(name="zero-dim-model", dimensions=0)
        manager.register_model(info)

        assert manager.get_dimensions("zero-dim-model") == 0

        # Validation should allow zero if that's what the model specifies
        valid, error = manager.validate_dimensions("zero-dim-model", 0)
        assert valid is True
        assert error is None

        # But non-zero should fail
        valid, error = manager.validate_dimensions("zero-dim-model", 1)
        assert valid is False

    def test_edge_case_very_large_dimensions(self, manager):
        """Test edge case with very large dimensions."""
        large_dims = 100000
        info = ModelInfo(
            name="large-dim-model",
            dimensions=large_dims,
            supports_custom_dimensions=True,
            min_custom_dimensions=1000,
            max_custom_dimensions=large_dims,
        )
        manager.register_model(info)

        # Should handle large dimensions
        assert manager.get_dimensions("large-dim-model") == large_dims

        # Storage estimation should work
        estimate = manager.estimate_storage_size("large-dim-model", 100)
        assert estimate["dimensions"] == large_dims
        assert estimate["bytes_per_embedding"] == large_dims * 4

    def test_normalize_vector_edge_cases(self, manager):
        """Test vector normalization edge cases."""
        # Large vector to small target
        large_vector = list(range(1000))
        result = manager.normalize_vector(large_vector, 3)
        assert result == [0, 1, 2]

        # Small vector to large target
        small_vector = [1, 2]
        result = manager.normalize_vector(small_vector, 5)
        assert result == [1, 2, 0.0, 0.0, 0.0]
