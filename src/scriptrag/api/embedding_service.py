"""Embedding service for generating and managing scene embeddings."""

import hashlib
import struct
from pathlib import Path

import numpy as np

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import ScriptRAGError
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingRequest

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

        # Setup cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Git LFS directory for embeddings
        self.lfs_dir = Path(".embeddings")

        # Default embedding model (can be overridden)
        self.default_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536  # Default for text-embedding-3-small

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for embedding.

        Args:
            text: Text to embed
            model: Model used for embedding

        Returns:
            Cache key string
        """
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> list[float] | None:
        """Load embedding from cache.

        Args:
            cache_key: Cache key for the embedding

        Returns:
            Embedding vector if cached, None otherwise
        """
        cache_file = self.cache_dir / f"{cache_key}.npy"
        if cache_file.exists():
            try:
                # Use numpy's native format for better security and compatibility
                embedding = np.load(cache_file, allow_pickle=False)
                logger.debug(f"Loaded embedding from cache: {cache_key}")
                result: list[float] = embedding.tolist()
                return result
            except Exception as e:
                logger.warning(f"Failed to load cached embedding: {e}")
        return None

    def _save_to_cache(self, cache_key: str, embedding: list[float]) -> None:
        """Save embedding to cache.

        Args:
            cache_key: Cache key for the embedding
            embedding: Embedding vector to cache
        """
        cache_file = self.cache_dir / f"{cache_key}.npy"
        try:
            # Use numpy's native format for better security and compatibility
            np_embedding = np.array(embedding, dtype=np.float32)
            np.save(cache_file, np_embedding)
            logger.debug(f"Saved embedding to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

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

        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(text, model)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return cached

        try:
            # Generate embedding using LLM client
            request = EmbeddingRequest(
                model=model,
                input=text,
                dimensions=self.embedding_dimensions,
            )

            response = await self.llm_client.embed(request)

            # Extract embedding from response
            if not response.data:
                raise ScriptRAGError(
                    message="No embedding data in response",
                    hint="The LLM provider may not support embeddings",
                )

            embedding = response.data[0].get("embedding", [])
            if not embedding:
                raise ScriptRAGError(
                    message="Empty embedding in response",
                    hint="The LLM provider returned invalid embedding data",
                )

            # Cache the result
            if use_cache:
                self._save_to_cache(cache_key, embedding)

            logger.debug(
                "Generated embedding for text",
                model=model,
                dimensions=len(embedding),
            )

            return list(embedding)

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
        # Create LFS directory structure
        model_dir = self.lfs_dir / model.replace("/", "_") / entity_type
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save as binary for efficiency
        embedding_file = model_dir / f"{entity_id}.npy"
        np_array = np.array(embedding, dtype=np.float32)
        np.save(embedding_file, np_array)

        # Ensure .gitattributes is set up for LFS
        gitattributes_path = self.lfs_dir / ".gitattributes"
        if not gitattributes_path.exists():
            gitattributes_path.write_text("*.npy filter=lfs diff=lfs merge=lfs -text\n")

        logger.debug(
            "Saved embedding to LFS",
            path=str(embedding_file),
            entity_type=entity_type,
            entity_id=entity_id,
        )

        return embedding_file

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
        model_dir = self.lfs_dir / model.replace("/", "_") / entity_type
        embedding_file = model_dir / f"{entity_id}.npy"

        if embedding_file.exists():
            try:
                np_array = np.load(embedding_file)
                return list(np_array.tolist())
            except Exception as e:
                logger.warning(f"Failed to load embedding from LFS: {e}")

        return None

    def encode_embedding_for_db(self, embedding: list[float]) -> bytes:
        """Encode embedding vector for database storage.

        Args:
            embedding: Embedding vector

        Returns:
            Binary representation of embedding
        """
        # Use struct for efficient binary encoding
        # Format: little-endian, dimension count, then floats
        dimension = len(embedding)
        format_str = f"<I{dimension}f"  # I = unsigned int, f = float
        return struct.pack(format_str, dimension, *embedding)

    def decode_embedding_from_db(self, data: bytes) -> list[float]:
        """Decode embedding vector from database storage.

        Args:
            data: Binary embedding data

        Returns:
            Embedding vector

        Raises:
            ValueError: If data is malformed or corrupted
        """
        # Validate minimum data length
        if len(data) < 4:
            raise ValueError(
                f"Embedding data too short: expected at least 4 bytes, got {len(data)}"
            )

        # First 4 bytes are the dimension count
        dimension = struct.unpack("<I", data[:4])[0]

        # Validate dimension is reasonable (embeddings typically 128-4096 dimensions)
        max_dimension = 10000  # Safety limit to prevent memory issues
        if dimension == 0:
            raise ValueError("Embedding dimension cannot be zero")
        if dimension > max_dimension:
            raise ValueError(
                f"Embedding dimension {dimension} exceeds "
                f"maximum allowed {max_dimension}"
            )

        # Validate data length matches expected size
        expected_size = 4 + dimension * 4  # 4 bytes for dimension + 4 bytes per float
        if len(data) != expected_size:
            raise ValueError(
                f"Embedding data size mismatch: expected exactly "
                f"{expected_size} bytes, got {len(data)}"
            )

        # Unpack the float values
        format_str = f"<{dimension}f"
        try:
            values = struct.unpack(format_str, data[4 : 4 + dimension * 4])
            return list(values)
        except struct.error as e:
            raise ValueError(f"Failed to decode embedding data: {e}") from e

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        np_vec1 = np.array(vec1)
        np_vec2 = np.array(vec2)

        # Normalize vectors
        norm1 = np.linalg.norm(np_vec1)
        norm2 = np.linalg.norm(np_vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(np_vec1, np_vec2) / (norm1 * norm2)
        return float(similarity)

    def find_similar_embeddings(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[tuple[int, list[float]]],
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
        similarities = []

        for entity_id, embedding in candidate_embeddings:
            similarity = self.cosine_similarity(query_embedding, embedding)
            if similarity >= threshold:
                similarities.append((entity_id, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top k results
        return similarities[:top_k]

    def clear_cache(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of cache files removed
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.npy"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")

        logger.info(f"Cleared {count} cached embeddings")
        return count

    def get_cache_size(self) -> tuple[int, int]:
        """Get cache statistics.

        Returns:
            Tuple of (number of cached items, total size in bytes)
        """
        if not self.cache_dir.exists():
            return 0, 0

        count = 0
        total_size = 0
        for cache_file in self.cache_dir.glob("*.npy"):
            count += 1
            total_size += cache_file.stat().st_size

        return count, total_size

    def cleanup_old_cache(self, max_age_days: int = 30) -> int:
        """Remove cache files older than specified age.

        Args:
            max_age_days: Maximum age of cache files in days

        Returns:
            Number of cache files removed
        """
        if not self.cache_dir.exists():
            return 0

        import time

        max_age_seconds = max_age_days * 24 * 60 * 60
        current_time = time.time()
        count = 0

        for cache_file in self.cache_dir.glob("*.npy"):
            try:
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > max_age_seconds:
                    cache_file.unlink()
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to check/remove cache file {cache_file}: {e}")

        if count > 0:
            logger.info(f"Removed {count} old cache files (>{max_age_days} days)")
        return count
