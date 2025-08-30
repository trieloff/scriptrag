"""Vector store abstraction for managing embeddings storage."""

from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from scriptrag.config import get_logger

logger = get_logger(__name__)


class EmbeddingSerializer(Protocol):
    """Protocol for embedding serialization."""

    def encode(self, embedding: list[float]) -> bytes:
        """Encode embedding to bytes."""
        ...

    def decode(self, data: bytes) -> list[float]:
        """Decode bytes to embedding."""
        ...


class BinaryEmbeddingSerializer:
    """Binary serializer for efficient embedding storage."""

    def encode(self, embedding: list[float]) -> bytes:
        """Encode embedding vector for database storage.

        Args:
            embedding: Embedding vector

        Returns:
            Binary representation of embedding
        """
        dimension = len(embedding)
        format_str = f"<I{dimension}f"  # I = unsigned int, f = float
        return struct.pack(format_str, dimension, *embedding)

    def decode(self, data: bytes) -> list[float]:
        """Decode embedding vector from database storage.

        Args:
            data: Binary embedding data

        Returns:
            Embedding vector

        Raises:
            ValueError: If data is malformed or corrupted
        """
        if len(data) < 4:
            raise ValueError(
                f"Embedding data too short: expected at least 4 bytes, got {len(data)}"
            )

        dimension = struct.unpack("<I", data[:4])[0]

        # Validate dimension
        max_dimension = 10000
        if dimension == 0:
            raise ValueError("Embedding dimension cannot be zero")
        if dimension > max_dimension:
            raise ValueError(
                f"Embedding dimension {dimension} exceeds "
                f"maximum allowed {max_dimension}"
            )

        # Validate data length
        expected_size = 4 + dimension * 4
        if len(data) != expected_size:
            raise ValueError(
                f"Embedding data size mismatch: expected exactly "
                f"{expected_size} bytes, got {len(data)}"
            )

        # Unpack values
        format_str = f"<{dimension}f"
        try:
            values = struct.unpack(format_str, data[4 : 4 + dimension * 4])
            return list(values)
        except struct.error as e:
            raise ValueError(f"Failed to decode embedding data: {e}") from e


class VectorStore(ABC):
    """Abstract base class for vector storage backends."""

    @abstractmethod
    def store(
        self,
        entity_type: str,
        entity_id: int,
        embedding: list[float],
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store an embedding vector.

        Args:
            entity_type: Type of entity (e.g., 'scene', 'bible_chunk')
            entity_id: ID of the entity
            embedding: Embedding vector
            model: Model used to generate embedding
            metadata: Optional metadata to store with embedding
        """
        ...

    @abstractmethod
    def retrieve(
        self, entity_type: str, entity_id: int, model: str
    ) -> list[float] | None:
        """Retrieve an embedding vector.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Embedding vector if found, None otherwise
        """
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        entity_type: str,
        model: str,
        limit: int = 10,
        threshold: float | None = None,
        filter_criteria: dict[str, Any] | None = None,
    ) -> list[tuple[int, float, dict[str, Any]]]:
        """Search for similar embeddings.

        Args:
            query_embedding: Query vector
            entity_type: Type of entities to search
            model: Model used for embeddings
            limit: Maximum number of results
            threshold: Optional similarity threshold
            filter_criteria: Optional filter criteria

        Returns:
            List of (entity_id, similarity_score, metadata) tuples
        """
        ...

    @abstractmethod
    def delete(
        self, entity_type: str, entity_id: int, model: str | None = None
    ) -> bool:
        """Delete an embedding.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Optional model filter (None = all models)

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    def exists(self, entity_type: str, entity_id: int, model: str) -> bool:
        """Check if an embedding exists.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            True if exists, False otherwise
        """
        ...


class GitLFSVectorStore(VectorStore):
    """Vector store implementation using Git LFS for persistence."""

    def __init__(self, lfs_dir: Path | None = None):
        """Initialize Git LFS vector store.

        Args:
            lfs_dir: Directory for LFS-tracked embeddings
        """
        self.lfs_dir = lfs_dir or Path(".embeddings")
        self._ensure_gitattributes()

    def _ensure_gitattributes(self) -> None:
        """Ensure .gitattributes is set up for LFS."""
        gitattributes_path = self.lfs_dir / ".gitattributes"
        if not gitattributes_path.exists():
            self.lfs_dir.mkdir(parents=True, exist_ok=True)
            gitattributes_path.write_text("*.npy filter=lfs diff=lfs merge=lfs -text\n")

    def _get_path(self, entity_type: str, entity_id: int, model: str) -> Path:
        """Get path for an embedding file.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Path to embedding file
        """
        model_dir = self.lfs_dir / model.replace("/", "_") / entity_type
        return model_dir / f"{entity_id}.npy"

    def get_embedding_path(self, entity_type: str, entity_id: int, model: str) -> Path:
        """Get path for an embedding file (public method).

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Path to embedding file
        """
        return self._get_path(entity_type, entity_id, model)

    def store(
        self,
        entity_type: str,
        entity_id: int,
        embedding: list[float],
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store embedding in Git LFS."""
        path = self._get_path(entity_type, entity_id, model)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save as numpy array
        np_array = np.array(embedding, dtype=np.float32)
        np.save(path, np_array)

        # Save metadata if provided
        if metadata:
            meta_path = path.with_suffix(".json")
            import json

            meta_path.write_text(json.dumps(metadata))

        logger.debug(
            "Stored embedding in Git LFS",
            path=str(path),
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def retrieve(
        self, entity_type: str, entity_id: int, model: str
    ) -> list[float] | None:
        """Retrieve embedding from Git LFS."""
        path = self._get_path(entity_type, entity_id, model)

        if path.exists():
            try:
                np_array = np.load(path)
                return list(np_array.tolist())
            except Exception as e:
                logger.warning(f"Failed to load embedding from {path}: {e}")

        return None

    def search(
        self,
        query_embedding: list[float],
        entity_type: str,
        model: str,
        limit: int = 10,
        threshold: float | None = None,
        filter_criteria: dict[str, Any] | None = None,
    ) -> list[tuple[int, float, dict[str, Any]]]:
        """Search is not supported in Git LFS store."""
        raise NotImplementedError(
            "Git LFS store does not support similarity search. "
            "Use a database-backed store for search operations."
        )

    def delete(
        self, entity_type: str, entity_id: int, model: str | None = None
    ) -> bool:
        """Delete embedding from Git LFS."""
        if model:
            # Delete specific model
            path = self._get_path(entity_type, entity_id, model)
            if path.exists():
                path.unlink()
                # Also delete metadata if exists
                meta_path = path.with_suffix(".json")
                if meta_path.exists():
                    meta_path.unlink()
                return True
        else:
            # Delete all models for this entity
            deleted = False
            for model_dir in self.lfs_dir.glob("*"):
                if model_dir.is_dir():
                    entity_dir = model_dir / entity_type
                    if entity_dir.exists():
                        embedding_file = entity_dir / f"{entity_id}.npy"
                        if embedding_file.exists():
                            embedding_file.unlink()
                            deleted = True
                        meta_file = entity_dir / f"{entity_id}.json"
                        if meta_file.exists():
                            meta_file.unlink()
            return deleted

        return False

    def exists(self, entity_type: str, entity_id: int, model: str) -> bool:
        """Check if embedding exists in Git LFS."""
        path = self._get_path(entity_type, entity_id, model)
        return path.exists()


class HybridVectorStore(VectorStore):
    """Hybrid vector store combining multiple backends."""

    def __init__(self, primary: VectorStore, secondary: VectorStore | None = None):
        """Initialize hybrid vector store.

        Args:
            primary: Primary storage backend (e.g., database)
            secondary: Optional secondary backend (e.g., Git LFS)
        """
        self.primary = primary
        self.secondary = secondary

    def store(
        self,
        entity_type: str,
        entity_id: int,
        embedding: list[float],
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store embedding in all backends."""
        self.primary.store(entity_type, entity_id, embedding, model, metadata)
        if self.secondary:
            try:
                self.secondary.store(entity_type, entity_id, embedding, model, metadata)
            except Exception as e:
                logger.warning(f"Failed to store in secondary backend: {e}")

    def retrieve(
        self, entity_type: str, entity_id: int, model: str
    ) -> list[float] | None:
        """Retrieve from primary, fallback to secondary."""
        result = self.primary.retrieve(entity_type, entity_id, model)
        if result is None and self.secondary:
            result = self.secondary.retrieve(entity_type, entity_id, model)
            # Restore to primary if found in secondary
            if result:
                try:
                    self.primary.store(entity_type, entity_id, result, model)
                except Exception as e:
                    logger.warning(f"Failed to restore to primary: {e}")
        return result

    def search(
        self,
        query_embedding: list[float],
        entity_type: str,
        model: str,
        limit: int = 10,
        threshold: float | None = None,
        filter_criteria: dict[str, Any] | None = None,
    ) -> list[tuple[int, float, dict[str, Any]]]:
        """Search using primary backend only."""
        return self.primary.search(
            query_embedding, entity_type, model, limit, threshold, filter_criteria
        )

    def delete(
        self, entity_type: str, entity_id: int, model: str | None = None
    ) -> bool:
        """Delete from all backends."""
        deleted = self.primary.delete(entity_type, entity_id, model)
        if self.secondary:
            try:
                secondary_deleted = self.secondary.delete(entity_type, entity_id, model)
                deleted = deleted or secondary_deleted
            except Exception as e:
                logger.warning(f"Failed to delete from secondary: {e}")
        return deleted

    def exists(self, entity_type: str, entity_id: int, model: str) -> bool:
        """Check existence in any backend."""
        exists = self.primary.exists(entity_type, entity_id, model)
        if not exists and self.secondary:
            exists = self.secondary.exists(entity_type, entity_id, model)
        return exists
