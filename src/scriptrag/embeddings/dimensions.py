"""Dimension management for embedding models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)


class EmbeddingModel(Enum):
    """Known embedding models with their dimensions."""

    # OpenAI models
    TEXT_EMBEDDING_3_SMALL = ("text-embedding-3-small", 1536)
    TEXT_EMBEDDING_3_LARGE = ("text-embedding-3-large", 3072)
    TEXT_EMBEDDING_ADA_002 = ("text-embedding-ada-002", 1536)

    # Cohere models
    EMBED_ENGLISH_V3 = ("embed-english-v3.0", 1024)
    EMBED_MULTILINGUAL_V3 = ("embed-multilingual-v3.0", 1024)
    EMBED_ENGLISH_LIGHT_V3 = ("embed-english-light-v3.0", 384)

    # Anthropic models
    CLAUDE_3_EMBED = ("claude-3-embed", 1024)  # Hypothetical

    # Open source models
    ALL_MINILM_L6_V2 = ("all-MiniLM-L6-v2", 384)
    ALL_MPNET_BASE_V2 = ("all-mpnet-base-v2", 768)
    E5_SMALL_V2 = ("e5-small-v2", 384)
    E5_BASE_V2 = ("e5-base-v2", 768)
    E5_LARGE_V2 = ("e5-large-v2", 1024)
    BGE_SMALL_EN = ("bge-small-en", 384)
    BGE_BASE_EN = ("bge-base-en", 768)
    BGE_LARGE_EN = ("bge-large-en", 1024)

    def __init__(self, model_name: str, dimensions: int) -> None:
        """Initialize model enum.

        Args:
            model_name: Name of the model
            dimensions: Number of dimensions
        """
        self.model_name = model_name
        self.dimensions = dimensions


@dataclass
class ModelInfo:
    """Information about an embedding model."""

    name: str
    dimensions: int
    max_tokens: int | None = None
    supports_truncation: bool = True
    supports_custom_dimensions: bool = False
    min_custom_dimensions: int | None = None
    max_custom_dimensions: int | None = None
    metadata: dict[str, Any] | None = None


class DimensionManager:
    """Manager for embedding model dimensions."""

    def __init__(self) -> None:
        """Initialize dimension manager."""
        self._models: dict[str, ModelInfo] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        """Load default model configurations."""
        # OpenAI models
        self.register_model(
            ModelInfo(
                name="text-embedding-3-small",
                dimensions=1536,
                max_tokens=8191,
                supports_custom_dimensions=True,
                min_custom_dimensions=256,
                max_custom_dimensions=1536,
            )
        )
        self.register_model(
            ModelInfo(
                name="text-embedding-3-large",
                dimensions=3072,
                max_tokens=8191,
                supports_custom_dimensions=True,
                min_custom_dimensions=256,
                max_custom_dimensions=3072,
            )
        )
        self.register_model(
            ModelInfo(
                name="text-embedding-ada-002",
                dimensions=1536,
                max_tokens=8191,
                supports_custom_dimensions=False,
            )
        )

        # Load from enum
        for model in EmbeddingModel:
            if not self.has_model(model.model_name):
                self.register_model(
                    ModelInfo(
                        name=model.model_name,
                        dimensions=model.dimensions,
                    )
                )

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a model configuration.

        Args:
            model_info: Model information
        """
        self._models[model_info.name] = model_info
        logger.debug(f"Registered model: {model_info.name} ({model_info.dimensions}D)")

    def has_model(self, model_name: str) -> bool:
        """Check if a model is registered.

        Args:
            model_name: Name of the model

        Returns:
            True if model is registered
        """
        return model_name in self._models

    def get_model_info(self, model_name: str) -> ModelInfo | None:
        """Get information about a model.

        Args:
            model_name: Name of the model

        Returns:
            Model information if found, None otherwise
        """
        return self._models.get(model_name)

    def get_dimensions(self, model_name: str) -> int | None:
        """Get default dimensions for a model.

        Args:
            model_name: Name of the model

        Returns:
            Number of dimensions if known, None otherwise
        """
        model_info = self._models.get(model_name)
        return model_info.dimensions if model_info else None

    def validate_dimensions(
        self, model_name: str, dimensions: int
    ) -> tuple[bool, str | None]:
        """Validate dimensions for a model.

        Args:
            model_name: Name of the model
            dimensions: Requested dimensions

        Returns:
            Tuple of (is_valid, error_message)
        """
        model_info = self._models.get(model_name)

        if not model_info:
            # Unknown model, can't validate
            return True, None

        if not model_info.supports_custom_dimensions:
            # Must use default dimensions
            if dimensions != model_info.dimensions:
                return False, (
                    f"Model {model_name} requires exactly "
                    f"{model_info.dimensions} dimensions"
                )
        else:
            # Check custom dimension range
            min_dim = model_info.min_custom_dimensions
            if min_dim and dimensions < min_dim:
                return False, (
                    f"Model {model_name} requires at least "
                    f"{model_info.min_custom_dimensions} dimensions"
                )
            max_dim = model_info.max_custom_dimensions
            if max_dim and dimensions > max_dim:
                return False, (
                    f"Model {model_name} supports at most "
                    f"{model_info.max_custom_dimensions} dimensions"
                )

        return True, None

    def normalize_vector(
        self, vector: list[float], target_dimensions: int
    ) -> list[float]:
        """Normalize vector to target dimensions.

        Args:
            vector: Input vector
            target_dimensions: Target number of dimensions

        Returns:
            Normalized vector

        Raises:
            ValueError: If normalization is not possible
        """
        current_dimensions = len(vector)

        if current_dimensions == target_dimensions:
            return vector

        if current_dimensions < target_dimensions:
            # Pad with zeros
            padding = [0.0] * (target_dimensions - current_dimensions)
            return vector + padding

        # Truncate
        return vector[:target_dimensions]

    def validate_vector(
        self, vector: list[float], model_name: str | None = None
    ) -> tuple[bool, str | None]:
        """Validate an embedding vector.

        Args:
            vector: Embedding vector
            model_name: Optional model name for validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not vector:
            return False, "Empty vector"

        if not all(isinstance(x, int | float) for x in vector):
            return False, "Vector contains non-numeric values"

        # Check for NaN or Inf
        import math

        if any(math.isnan(x) or math.isinf(x) for x in vector):
            return False, "Vector contains NaN or Inf values"

        # Check dimensions if model is known
        if model_name:
            expected = self.get_dimensions(model_name)
            if expected and len(vector) != expected:
                return False, (
                    f"Dimension mismatch: expected {expected}, "
                    f"got {len(vector)} for model {model_name}"
                )

        return True, None

    def get_all_models(self) -> list[ModelInfo]:
        """Get information about all registered models.

        Returns:
            List of model information
        """
        return list(self._models.values())

    def suggest_model(
        self,
        target_dimensions: int,
        max_tokens: int | None = None,
    ) -> ModelInfo | None:
        """Suggest a model based on requirements.

        Args:
            target_dimensions: Desired dimensions
            max_tokens: Maximum token requirement

        Returns:
            Suggested model info if found
        """
        candidates = []

        for model in self._models.values():
            # Check dimensions
            if model.supports_custom_dimensions:
                min_dim = model.min_custom_dimensions or 0
                max_dim = model.max_custom_dimensions or float("inf")
                if min_dim <= target_dimensions <= max_dim:
                    candidates.append(model)
            elif model.dimensions == target_dimensions:
                candidates.append(model)

        # Filter by token limit if specified
        if max_tokens and candidates:
            candidates = [
                m
                for m in candidates
                if m.max_tokens is None or m.max_tokens >= max_tokens
            ]

        # Return the first candidate (could be improved with scoring)
        return candidates[0] if candidates else None

    def estimate_storage_size(
        self, model_name: str, num_embeddings: int
    ) -> dict[str, Any]:
        """Estimate storage requirements for embeddings.

        Args:
            model_name: Name of the model
            num_embeddings: Number of embeddings

        Returns:
            Dictionary with storage estimates
        """
        dimensions = self.get_dimensions(model_name)
        if not dimensions:
            dimensions = 1536  # Default estimate

        # Assume float32 storage (4 bytes per dimension)
        bytes_per_embedding = dimensions * 4
        total_bytes = bytes_per_embedding * num_embeddings

        return {
            "dimensions": dimensions,
            "bytes_per_embedding": bytes_per_embedding,
            "total_bytes": total_bytes,
            "total_mb": total_bytes / (1024 * 1024),
            "total_gb": total_bytes / (1024 * 1024 * 1024),
        }
