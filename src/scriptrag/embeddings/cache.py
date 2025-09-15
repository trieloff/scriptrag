"""Caching layer for embeddings with invalidation strategies."""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from scriptrag.config import get_logger

logger = get_logger(__name__)


class InvalidationStrategy(Enum):
    """Cache invalidation strategies."""

    TTL = "ttl"  # Time-to-live
    LRU = "lru"  # Least recently used
    LFU = "lfu"  # Least frequently used
    FIFO = "fifo"  # First in, first out


@dataclass
class CacheEntry:
    """Entry in the embedding cache."""

    key: str
    embedding: list[float]
    model: str
    timestamp: float
    access_count: int = 0
    last_access: float | None = None
    metadata: dict[str, Any] | None = None


class EmbeddingCache:
    """Cache for embedding vectors with various invalidation strategies."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        strategy: InvalidationStrategy = InvalidationStrategy.LRU,
        max_size: int = 10000,
        ttl_seconds: int = 86400 * 30,  # 30 days default
    ):
        """Initialize embedding cache.

        Args:
            cache_dir: Directory for cache storage
            strategy: Invalidation strategy to use
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (for TTL strategy)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.strategy = strategy
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        # In-memory index for fast lookups
        self._index: dict[str, CacheEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load cache index from disk."""
        index_file = self.cache_dir / "index.json"
        if index_file.exists():
            try:
                with index_file.open() as f:
                    data = json.load(f)
                    for key, entry_data in data.items():
                        self._index[key] = CacheEntry(**entry_data)
                logger.debug(f"Loaded {len(self._index)} cache entries")
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
                self._index = {}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        index_file = self.cache_dir / "index.json"
        try:
            data = {}
            for key, entry in self._index.items():
                data[key] = {
                    "key": entry.key,
                    "embedding": [],  # Don't store embeddings in index
                    "model": entry.model,
                    "timestamp": entry.timestamp,
                    "access_count": entry.access_count,
                    "last_access": entry.last_access,
                    "metadata": entry.metadata,
                }
            with index_file.open("w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache index: {e}")

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model.

        Args:
            text: Text to embed
            model: Model used for embedding

        Returns:
            Cache key string
        """
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_file(self, key: str) -> Path:
        """Get path to cache file for a key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Use subdirectories to avoid too many files in one directory
        subdir = self.cache_dir / key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{key}.npy"

    def get(self, text: str, model: str) -> list[float] | None:
        """Get embedding from cache.

        Args:
            text: Text that was embedded
            model: Model used for embedding

        Returns:
            Embedding vector if cached, None otherwise
        """
        key = self._get_cache_key(text, model)

        if key not in self._index:
            return None

        entry = self._index[key]

        # Check TTL if using TTL strategy
        if self.strategy == InvalidationStrategy.TTL:
            age = time.time() - entry.timestamp
            if age > self.ttl_seconds:
                logger.debug(f"Cache entry expired: {key}")
                self.invalidate(text, model)
                return None

        # Load embedding from file
        cache_file = self._get_cache_file(key)
        if not cache_file.exists():
            logger.warning(f"Cache file missing for key: {key}")
            del self._index[key]
            return None

        try:
            embedding = np.load(cache_file, allow_pickle=False)

            # Update access metadata
            entry.access_count += 1
            # Ensure last_access is always later than timestamp for deterministic LRU
            new_access_time = time.time()
            if new_access_time <= entry.timestamp:
                new_access_time = entry.timestamp + 0.001
            entry.last_access = new_access_time

            logger.debug(f"Cache hit: {key}")
            result: list[float] = embedding.tolist()
            return result

        except Exception as e:
            logger.warning(f"Failed to load cached embedding: {e}")
            self.invalidate(text, model)
            return None

    def put(
        self,
        text: str,
        model: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store embedding in cache.

        Args:
            text: Text that was embedded
            model: Model used for embedding
            embedding: Embedding vector
            metadata: Optional metadata to store
        """
        key = self._get_cache_key(text, model)

        # Check if we need to evict entries
        if len(self._index) >= self.max_size:
            self._evict()

        # Save embedding to file
        cache_file = self._get_cache_file(key)
        try:
            np_embedding = np.array(embedding, dtype=np.float32)
            np.save(cache_file, np_embedding)

            # Update index with current time
            current_time = time.time()
            self._index[key] = CacheEntry(
                key=key,
                embedding=[],  # Don't keep in memory
                model=model,
                timestamp=current_time,
                access_count=1,
                last_access=current_time,
                metadata=metadata,
            )

            logger.debug(f"Cached embedding: {key}")

            # Save index to disk after adding new entry
            self._save_index()

        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def invalidate(self, text: str, model: str) -> bool:
        """Invalidate a cache entry.

        Args:
            text: Text that was embedded
            model: Model used for embedding

        Returns:
            True if entry was invalidated, False if not found
        """
        key = self._get_cache_key(text, model)

        if key not in self._index:
            return False

        # Remove from index
        del self._index[key]

        # Remove file
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove cache file: {e}")

        logger.debug(f"Invalidated cache entry: {key}")

        # Save index to disk after invalidation
        self._save_index()

        return True

    def invalidate_model(self, model: str) -> int:
        """Invalidate all entries for a model.

        Args:
            model: Model to invalidate

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [
            key for key, entry in self._index.items() if entry.model == model
        ]

        count = 0
        for key in keys_to_remove:
            # Remove file
            cache_file = self._get_cache_file(key)
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file: {e}")

            # Remove from index
            del self._index[key]

        logger.info(f"Invalidated {count} cache entries for model {model}")

        # Save index to disk after bulk invalidation
        if count > 0:
            self._save_index()

        return count

    def _evict(self) -> None:
        """Evict entries based on the configured strategy."""
        if not self._index:
            return

        # Determine which entry to evict
        if self.strategy == InvalidationStrategy.LRU:
            # Evict least recently used
            # Use timestamp as fallback if last_access is None for consistent ordering
            # Sort by (last_access, timestamp, key) for cross-platform determinism
            key = min(
                self._index.keys(),
                key=lambda k: (
                    self._index[k].last_access or self._index[k].timestamp,
                    self._index[k].timestamp,
                    k,  # Use key as final tiebreaker for deterministic behavior
                ),
            )
        elif self.strategy == InvalidationStrategy.LFU:
            # Evict least frequently used (with tiebreakers for determinism)
            key = min(
                self._index.keys(),
                key=lambda k: (
                    self._index[k].access_count,
                    self._index[k].timestamp,
                    k,  # Key as final tiebreaker for full determinism
                ),
            )
        elif self.strategy == InvalidationStrategy.FIFO:
            # Evict oldest
            key = min(self._index.keys(), key=lambda k: self._index[k].timestamp)
        elif self.strategy == InvalidationStrategy.TTL:
            # Evict expired entries first
            current_time = time.time()
            expired = [
                k
                for k, e in self._index.items()
                if current_time - e.timestamp > self.ttl_seconds
            ]
            if expired:
                key = expired[0]
            else:
                # Fall back to FIFO if no expired entries
                key = min(self._index.keys(), key=lambda k: self._index[k].timestamp)
        else:
            # Default to FIFO
            key = min(self._index.keys(), key=lambda k: self._index[k].timestamp)

        # Remove the entry
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove cache file during eviction: {e}")

        del self._index[key]
        logger.debug(f"Evicted cache entry: {key}")

        # Save index to disk after eviction
        self._save_index()

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = 0

        # Remove all cache files
        for cache_file in self.cache_dir.rglob("*.npy"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")

        # Clear index
        self._index.clear()
        self._save_index()

        logger.info(f"Cleared {count} cache entries")
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self._index:
            return {
                "entries": 0,
                "size_bytes": 0,
                "models": [],
                "strategy": self.strategy.value,
                "max_size": self.max_size,
            }

        # Calculate statistics
        total_size = 0
        models = set()
        oldest_timestamp = float("inf")
        newest_timestamp = 0.0

        for entry in self._index.values():
            models.add(entry.model)
            oldest_timestamp = min(oldest_timestamp, entry.timestamp)
            newest_timestamp = max(newest_timestamp, entry.timestamp)

            # Get file size
            cache_file = self._get_cache_file(entry.key)
            if cache_file.exists():
                total_size += cache_file.stat().st_size

        return {
            "entries": len(self._index),
            "size_bytes": total_size,
            "size_mb": total_size / (1024 * 1024),
            "models": sorted(models),
            "strategy": self.strategy.value,
            "max_size": self.max_size,
            "oldest_entry_age_days": (time.time() - oldest_timestamp) / 86400
            if oldest_timestamp != float("inf")
            else 0,
            "newest_entry_age_days": (time.time() - newest_timestamp) / 86400
            if newest_timestamp > 0
            else 0,
        }

    def cleanup_old_entries(self, max_age_days: int = 30) -> int:
        """Remove cache entries older than specified age.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of entries removed
        """
        max_age_seconds = max_age_days * 86400
        current_time = time.time()
        count = 0

        keys_to_remove = [
            key
            for key, entry in self._index.items()
            if current_time - entry.timestamp > max_age_seconds
        ]

        for key in keys_to_remove:
            cache_file = self._get_cache_file(key)
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove old cache file: {e}")

            del self._index[key]

        if count > 0:
            logger.info(f"Removed {count} cache entries older than {max_age_days} days")
            self._save_index()

        return count

    def __enter__(self) -> EmbeddingCache:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - save index."""
        self._save_index()

    def __del__(self) -> None:
        """Destructor - ensure index is saved when object is garbage collected."""
        # Silently ignore errors during cleanup to avoid issues during shutdown
        with contextlib.suppress(Exception):
            self._save_index()
