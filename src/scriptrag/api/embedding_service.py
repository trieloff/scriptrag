"""Embedding service for generating and managing scene embeddings."""

from pathlib import Path
from typing import Any

import numpy as np

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.embeddings import (
    EmbeddingCache,
    EmbeddingPipeline,
    SimilarityCalculator,
    VectorStore,
)
from scriptrag.embeddings.batch_processor import BatchProcessor
from scriptrag.embeddings.cache import InvalidationStrategy
from scriptrag.embeddings.dimensions import DimensionManager
from scriptrag.embeddings.pipeline import PipelineConfig
from scriptrag.embeddings.similarity import SimilarityMetric
from scriptrag.embeddings.vector_store import (
    BinaryEmbeddingSerializer,
    GitLFSVectorStore,
)
from scriptrag.exceptions import ScriptRAGError
from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating and managing embeddings for screenplay content."""

    def __init__(
        self,
        settings: ScriptRAGSettings,
        llm_client: LLMClient | None = None,
        cache_dir: Path | None = None,
    ):
        """Initialize embedding service.

        Args:
            settings: Configuration settings
            llm_client: Optional LLM client for generating embeddings
            cache_dir: Optional directory for caching embeddings
        """
        self.settings = settings
        self.llm_client = llm_client or LLMClient()

        # Default embedding model (can be overridden)
        self.default_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536  # Default for text-embedding-3-small

        # Initialize new architecture components
        self.dimension_manager = DimensionManager()
        self.similarity_calculator = SimilarityCalculator(SimilarityMetric.COSINE)
        self.serializer = BinaryEmbeddingSerializer()

        # Setup cache
        if cache_dir is None:
            cache_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        self.cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.LRU,
        )

        # Setup vector stores
        self.lfs_store = GitLFSVectorStore(Path(".embeddings"))
        self.vector_store: VectorStore = self.lfs_store

        # Setup batch processor
        self.batch_processor = BatchProcessor(
            self.llm_client,
            batch_size=10,
            max_concurrent=3,
        )

        # Setup pipeline config
        self.pipeline_config = PipelineConfig(
            model=self.default_model,
            dimensions=self.embedding_dimensions,
            use_cache=True,
        )

        # Initialize pipeline
        self.pipeline = EmbeddingPipeline(
            config=self.pipeline_config,
            llm_client=self.llm_client,
            cache=self.cache,
            dimension_manager=self.dimension_manager,
        )

    async def generate_embedding(
        self, text: str, model: str | None = None, use_cache: bool = True
    ) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed
            model: Model to use (defaults to service default)
            use_cache: Whether to use caching

        Returns:
            Embedding vector

        Raises:
            ScriptRAGError: If embedding generation fails
        """
        model = model or self.default_model

        # Update pipeline config if needed
        if model != self.pipeline_config.model:
            self.pipeline_config.model = model
            # Get dimensions for model
            dimensions = self.dimension_manager.get_dimensions(model)
            if dimensions:
                self.pipeline_config.dimensions = dimensions

        self.pipeline_config.use_cache = use_cache

        try:
            # Use pipeline for generation
            embedding = await self.pipeline.generate_embedding(text)

            logger.debug(
                "Generated embedding for text",
                model=model,
                dimensions=len(embedding),
            )

            return embedding

        except Exception as e:
            raise ScriptRAGError(
                message=f"Failed to generate embedding: {e}",
                hint="Check LLM provider configuration and API limits",
                details={"model": model, "text_length": len(text)},
            ) from e

    async def generate_scene_embedding(
        self, scene_content: str, scene_heading: str, model: str | None = None
    ) -> list[float]:
        """Generate embedding for a scene.

        Args:
            scene_content: Full scene content
            scene_heading: Scene heading for context
            model: Model to use (defaults to service default)

        Returns:
            Embedding vector for the scene
        """
        # Combine heading and content for richer embedding
        combined_text = f"Scene: {scene_heading}\n\n{scene_content}"

        # Truncate if too long (most models have token limits)
        max_length = 8000  # Conservative limit for most models
        if len(combined_text) > max_length:
            combined_text = combined_text[:max_length] + "..."

        return await self.generate_embedding(combined_text, model)

    def save_embedding_to_lfs(
        self, embedding: list[float], entity_type: str, entity_id: int, model: str
    ) -> Path:
        """Save embedding to Git LFS-tracked directory.

        Args:
            embedding: Embedding vector
            entity_type: Type of entity (e.g., 'scene')
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Path to the saved embedding file
        """
        # Use vector store
        self.lfs_store.store(entity_type, entity_id, embedding, model)

        # Return path for compatibility
        return self.lfs_store._get_path(entity_type, entity_id, model)

    def load_embedding_from_lfs(
        self, entity_type: str, entity_id: int, model: str
    ) -> list[float] | None:
        """Load embedding from Git LFS-tracked directory.

        Args:
            entity_type: Type of entity (e.g., 'scene')
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Embedding vector if found, None otherwise
        """
        return self.lfs_store.retrieve(entity_type, entity_id, model)

    def encode_embedding_for_db(self, embedding: list[float]) -> bytes:
        """Encode embedding vector for database storage.

        Args:
            embedding: Embedding vector

        Returns:
            Binary representation of embedding
        """
        return self.serializer.encode(embedding)

    def decode_embedding_from_db(self, data: bytes) -> list[float]:
        """Decode embedding vector from database storage.

        Args:
            data: Binary embedding data

        Returns:
            Embedding vector

        Raises:
            ValueError: If data is malformed or corrupted
        """
        return self.serializer.decode(data)

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        return self.similarity_calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)

    def find_similar_embeddings(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[tuple[int, list[float] | np.ndarray]],
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[tuple[int, float]]:
        """Find most similar embeddings to a query.

        Args:
            query_embedding: Query vector
            candidate_embeddings: List of (id, embedding) tuples
            top_k: Number of top results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (id, similarity_score) tuples, sorted by similarity
        """
        return self.similarity_calculator.find_most_similar(
            query_embedding,
            candidate_embeddings,
            top_k=top_k,
            threshold=threshold,
        )

    def clear_cache(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of cache files removed
        """
        return self.cache.clear()

    def get_cache_size(self) -> tuple[int, int]:
        """Get cache statistics.

        Returns:
            Tuple of (number of cached items, total size in bytes)
        """
        stats = self.cache.get_stats()
        return stats["entries"], stats["size_bytes"]

    def cleanup_old_cache(self, max_age_days: int = 30) -> int:
        """Remove cache files older than specified age.

        Args:
            max_age_days: Maximum age of cache files in days

        Returns:
            Number of cache files removed
        """
        return self.cache.cleanup_old(max_age_days)

    async def generate_batch_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float] | None]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            model: Model to use (defaults to service default)

        Returns:
            List of embeddings (None for failed items)
        """
        model = model or self.default_model

        # Update pipeline config
        if model != self.pipeline_config.model:
            self.pipeline_config.model = model
            dimensions = self.dimension_manager.get_dimensions(model)
            if dimensions:
                self.pipeline_config.dimensions = dimensions

        # Use pipeline for batch generation
        return await self.pipeline.generate_batch(texts)

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get comprehensive embedding statistics.

        Returns:
            Dictionary with embedding stats
        """
        return {
            "cache": self.cache.get_stats(),
            "pipeline": self.pipeline.get_stats(),
            "models": [
                {
                    "name": m.name,
                    "dimensions": m.dimensions,
                    "max_tokens": m.max_tokens,
                }
                for m in self.dimension_manager.get_all_models()
            ],
        }
