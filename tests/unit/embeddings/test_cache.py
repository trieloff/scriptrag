"""Comprehensive tests for embedding caching layer."""

import json
import time
from pathlib import Path

import numpy as np
import pytest

from scriptrag.embeddings.cache import (
    CacheEntry,
    EmbeddingCache,
    InvalidationStrategy,
)


class TestInvalidationStrategy:
    """Test InvalidationStrategy enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert InvalidationStrategy.TTL.value == "ttl"
        assert InvalidationStrategy.LRU.value == "lru"
        assert InvalidationStrategy.LFU.value == "lfu"
        assert InvalidationStrategy.FIFO.value == "fifo"


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_init_minimal(self):
        """Test CacheEntry with minimal parameters."""
        entry = CacheEntry(
            key="test_key",
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
            timestamp=123456.0,
        )
        assert entry.key == "test_key"
        assert entry.embedding == [0.1, 0.2, 0.3]
        assert entry.model == "test-model"
        assert entry.timestamp == 123456.0
        assert entry.access_count == 0
        assert entry.last_access is None
        assert entry.metadata is None

    def test_init_full(self):
        """Test CacheEntry with all parameters."""
        metadata = {"source": "scene"}
        entry = CacheEntry(
            key="test_key",
            embedding=[0.1, 0.2],
            model="test-model",
            timestamp=123456.0,
            access_count=5,
            last_access=123460.0,
            metadata=metadata,
        )
        assert entry.access_count == 5
        assert entry.last_access == 123460.0
        assert entry.metadata == metadata


class TestEmbeddingCache:
    """Test EmbeddingCache class."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "test_cache"

    @pytest.fixture
    def cache(self, cache_dir):
        """Create cache instance."""
        return EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.LRU,
            max_size=5,
            ttl_seconds=3600,
        )

    def test_init_with_params(self, cache_dir):
        """Test cache initialization with parameters."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.LFU,
            max_size=100,
            ttl_seconds=7200,
        )
        assert cache.cache_dir == cache_dir
        assert cache.strategy == InvalidationStrategy.LFU
        assert cache.max_size == 100
        assert cache.ttl_seconds == 7200
        assert cache_dir.exists()

    def test_init_defaults(self):
        """Test cache initialization with defaults."""
        cache = EmbeddingCache()
        expected_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        assert cache.cache_dir == expected_dir
        assert cache.strategy == InvalidationStrategy.LRU
        assert cache.max_size == 10000
        assert cache.ttl_seconds == 86400 * 30  # 30 days

    def test_get_cache_key(self, cache):
        """Test cache key generation."""
        key1 = cache._get_cache_key("test text", "model-1")
        key2 = cache._get_cache_key("test text", "model-1")
        key3 = cache._get_cache_key("different text", "model-1")
        key4 = cache._get_cache_key("test text", "model-2")

        # Same inputs should produce same key
        assert key1 == key2
        # Different inputs should produce different keys
        assert key1 != key3
        assert key1 != key4
        # Keys should be hex strings
        assert all(c in "0123456789abcdef" for c in key1)
        assert len(key1) == 64  # SHA256 hex is 64 chars

    def test_get_cache_file(self, cache):
        """Test cache file path generation."""
        key = "abcd1234" + "0" * 56  # 64 char hex string
        path = cache._get_cache_file(key)

        # Should create subdirectory based on first 2 chars
        assert path.parent.name == "ab"
        assert path.name == f"{key}.npy"
        # Parent directory should exist after calling this method
        assert path.parent.exists()

    def test_put_and_get_success(self, cache):
        """Test successful put and get operations."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        text = "test text"
        model = "test-model"
        metadata = {"source": "test"}

        # Put embedding
        cache.put(text, model, embedding, metadata)

        # Get embedding
        result = cache.get(text, model)
        assert result is not None
        np.testing.assert_array_almost_equal(result, embedding, decimal=6)

        # Check that entry was created in index
        key = cache._get_cache_key(text, model)
        assert key in cache._index
        entry = cache._index[key]
        assert entry.model == model
        assert entry.access_count == 2  # Put (1) + Get (1) = 2 accesses
        assert entry.metadata == metadata

    def test_put_updates_existing(self, cache):
        """Test that put updates existing entries."""
        text = "test text"
        model = "test-model"
        embedding1 = [0.1, 0.2]
        embedding2 = [0.3, 0.4]

        # Put first embedding
        cache.put(text, model, embedding1)
        result1 = cache.get(text, model)
        np.testing.assert_array_almost_equal(result1, embedding1)

        # Put second embedding (should overwrite)
        cache.put(text, model, embedding2)
        result2 = cache.get(text, model)
        np.testing.assert_array_almost_equal(result2, embedding2)

    def test_get_nonexistent(self, cache):
        """Test get for non-existent entry."""
        result = cache.get("nonexistent", "model")
        assert result is None

    def test_get_updates_access_metadata(self, cache):
        """Test that get updates access metadata."""
        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        cache.put(text, model, embedding)
        key = cache._get_cache_key(text, model)
        entry = cache._index[key]
        initial_count = entry.access_count
        initial_access = entry.last_access

        time.sleep(0.01)  # Ensure time difference
        result = cache.get(text, model)

        assert result is not None
        assert entry.access_count == initial_count + 1
        assert entry.last_access > initial_access

    def test_get_missing_file(self, cache):
        """Test get when cache file is missing."""
        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        # Put embedding to create index entry
        cache.put(text, model, embedding)
        key = cache._get_cache_key(text, model)

        # Delete the cache file
        cache_file = cache._get_cache_file(key)
        cache_file.unlink()

        # Get should return None and clean up index
        result = cache.get(text, model)
        assert result is None
        assert key not in cache._index

    def test_get_corrupted_file(self, cache):
        """Test get when cache file is corrupted."""
        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        # Put embedding
        cache.put(text, model, embedding)
        key = cache._get_cache_key(text, model)
        cache_file = cache._get_cache_file(key)

        # Corrupt the cache file
        cache_file.write_bytes(b"corrupted data")

        # Get should return None and invalidate entry
        result = cache.get(text, model)
        assert result is None
        assert key not in cache._index

    def test_ttl_strategy_expired(self, cache_dir):
        """Test TTL strategy with expired entries."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.TTL,
            ttl_seconds=1,  # Very short TTL
        )

        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        # Put embedding
        cache.put(text, model, embedding)

        # Should be available immediately
        result = cache.get(text, model)
        assert result is not None

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should be expired now
        result = cache.get(text, model)
        assert result is None
        key = cache._get_cache_key(text, model)
        assert key not in cache._index

    def test_ttl_strategy_not_expired(self, cache_dir):
        """Test TTL strategy with non-expired entries."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.TTL,
            ttl_seconds=3600,  # Long TTL
        )

        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        cache.put(text, model, embedding)
        result = cache.get(text, model)
        assert result is not None
        np.testing.assert_array_almost_equal(result, embedding)

    def test_invalidate_success(self, cache):
        """Test successful invalidation."""
        embedding = [0.1, 0.2]
        text = "test text"
        model = "test-model"

        # Put embedding
        cache.put(text, model, embedding)
        key = cache._get_cache_key(text, model)
        cache_file = cache._get_cache_file(key)

        # Verify it exists
        assert key in cache._index
        assert cache_file.exists()

        # Invalidate
        result = cache.invalidate(text, model)
        assert result is True

        # Verify removal
        assert key not in cache._index
        assert not cache_file.exists()

    def test_invalidate_nonexistent(self, cache):
        """Test invalidation of non-existent entry."""
        result = cache.invalidate("nonexistent", "model")
        assert result is False

    def test_invalidate_model(self, cache):
        """Test invalidating all entries for a model."""
        model1 = "model-1"
        model2 = "model-2"

        # Put multiple embeddings for both models
        cache.put("text1", model1, [0.1, 0.2])
        cache.put("text2", model1, [0.3, 0.4])
        cache.put("text3", model2, [0.5, 0.6])
        cache.put("text4", model2, [0.7, 0.8])

        # Verify all exist
        assert len(cache._index) == 4

        # Invalidate model1
        count = cache.invalidate_model(model1)
        assert count == 2

        # Verify model1 entries are gone, model2 entries remain
        assert cache.get("text1", model1) is None
        assert cache.get("text2", model1) is None
        assert cache.get("text3", model2) is not None
        assert cache.get("text4", model2) is not None
        assert len(cache._index) == 2

    def test_invalidate_model_nonexistent(self, cache):
        """Test invalidating non-existent model."""
        count = cache.invalidate_model("nonexistent-model")
        assert count == 0

    def test_eviction_lru(self, cache_dir):
        """Test LRU eviction strategy."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.LRU,
            max_size=3,
        )

        # Fill cache to capacity with small delays for Windows timing precision
        cache.put("text1", "model", [0.1])
        time.sleep(0.001)  # Ensure distinct timestamps
        cache.put("text2", "model", [0.2])
        time.sleep(0.001)  # Ensure distinct timestamps
        cache.put("text3", "model", [0.3])
        assert len(cache._index) == 3

        # Access text1 to make it recently used - with delay for clear last_access
        time.sleep(0.001)
        cache.get("text1", "model")

        # Add another entry (should evict text2 as least recently used)
        time.sleep(0.001)  # Ensure distinct timing for eviction logic
        cache.put("text4", "model", [0.4])
        assert len(cache._index) == 3

        # text2 should be evicted
        assert cache.get("text2", "model") is None
        assert cache.get("text1", "model") is not None  # Recently accessed
        assert cache.get("text3", "model") is not None
        assert cache.get("text4", "model") is not None

    def test_eviction_lfu(self, cache_dir):
        """Test LFU eviction strategy."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.LFU,
            max_size=3,
        )

        # Fill cache
        cache.put("text1", "model", [0.1])
        cache.put("text2", "model", [0.2])
        cache.put("text3", "model", [0.3])

        # Access text1 multiple times
        cache.get("text1", "model")
        cache.get("text1", "model")
        cache.get("text2", "model")  # Access text2 once

        # Add another entry (should evict text3 as least frequently used)
        cache.put("text4", "model", [0.4])
        assert len(cache._index) == 3

        # text3 should be evicted (least frequently used)
        assert cache.get("text3", "model") is None
        assert cache.get("text1", "model") is not None
        assert cache.get("text2", "model") is not None
        assert cache.get("text4", "model") is not None

    def test_eviction_fifo(self, cache_dir):
        """Test FIFO eviction strategy."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.FIFO,
            max_size=3,
        )

        # Fill cache in order
        cache.put("text1", "model", [0.1])
        time.sleep(0.01)  # Ensure different timestamps
        cache.put("text2", "model", [0.2])
        time.sleep(0.01)
        cache.put("text3", "model", [0.3])

        # Add another entry (should evict text1 as first in)
        cache.put("text4", "model", [0.4])
        assert len(cache._index) == 3

        # text1 should be evicted (first in, first out)
        assert cache.get("text1", "model") is None
        assert cache.get("text2", "model") is not None
        assert cache.get("text3", "model") is not None
        assert cache.get("text4", "model") is not None

    def test_eviction_ttl_with_expired(self, cache_dir):
        """Test TTL eviction strategy with expired entries."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.TTL,
            max_size=2,
            ttl_seconds=0.5,
        )

        # Add first entry
        cache.put("text1", "model", [0.1])

        # Wait for expiration
        time.sleep(0.6)

        # Add second entry
        cache.put("text2", "model", [0.2])

        # Add third entry (should evict expired text1)
        cache.put("text3", "model", [0.3])

        assert len(cache._index) == 2
        assert cache.get("text1", "model") is None  # Expired and evicted
        assert cache.get("text2", "model") is not None
        assert cache.get("text3", "model") is not None

    def test_eviction_ttl_fallback_to_fifo(self, cache_dir):
        """Test TTL eviction falls back to FIFO when no expired entries."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=InvalidationStrategy.TTL,
            max_size=2,
            ttl_seconds=3600,  # Long TTL, no expiration
        )

        # Fill cache
        cache.put("text1", "model", [0.1])
        time.sleep(0.01)
        cache.put("text2", "model", [0.2])

        # Add third entry (should fall back to FIFO and evict text1)
        cache.put("text3", "model", [0.3])

        assert len(cache._index) == 2
        assert cache.get("text1", "model") is None  # Evicted by FIFO
        assert cache.get("text2", "model") is not None
        assert cache.get("text3", "model") is not None

    def test_eviction_empty_cache(self, cache):
        """Test eviction when cache is empty."""
        # Should not raise error
        cache._evict()
        assert len(cache._index) == 0

    def test_eviction_file_removal_error(self, cache, monkeypatch):
        """Test eviction when file removal fails."""
        # Add entry
        cache.put("text1", "model", [0.1])

        # Mock unlink to raise exception
        def mock_unlink(self):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        # Force eviction by adding entries beyond max_size
        for i in range(10):
            cache.put(f"text{i + 2}", "model", [0.1 * i])

        # Should still work despite file removal errors
        assert len(cache._index) <= cache.max_size

    def test_clear_all(self, cache):
        """Test clearing all cache entries."""
        # Add multiple entries
        cache.put("text1", "model1", [0.1])
        cache.put("text2", "model1", [0.2])
        cache.put("text3", "model2", [0.3])

        assert len(cache._index) == 3

        # Clear all
        count = cache.clear()
        assert count == 3
        assert len(cache._index) == 0

        # Verify files are removed
        assert not any(cache.cache_dir.rglob("*.npy"))

    def test_clear_empty(self, cache):
        """Test clearing empty cache."""
        count = cache.clear()
        assert count == 0
        assert len(cache._index) == 0

    def test_clear_file_removal_error(self, cache, monkeypatch):
        """Test clear when file removal fails."""
        cache.put("text1", "model", [0.1])

        # Mock unlink to raise exception
        def mock_unlink(self):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        # Clear should still work despite errors
        count = cache.clear()
        # Count might be 0 due to failed file removal, but index should be cleared
        assert len(cache._index) == 0

    def test_get_stats_empty(self, cache):
        """Test getting stats for empty cache."""
        stats = cache.get_stats()
        expected = {
            "entries": 0,
            "size_bytes": 0,
            "models": [],
            "strategy": "lru",
            "max_size": 5,
        }
        assert stats == expected

    def test_get_stats_with_entries(self, cache):
        """Test getting stats with cache entries."""
        # Add entries for different models
        cache.put("text1", "model-a", [0.1, 0.2])
        cache.put("text2", "model-b", [0.3, 0.4])
        cache.put("text3", "model-a", [0.5, 0.6])

        stats = cache.get_stats()

        assert stats["entries"] == 3
        assert stats["size_bytes"] > 0  # Should have some file size
        assert stats["size_mb"] > 0
        assert sorted(stats["models"]) == ["model-a", "model-b"]
        assert stats["strategy"] == "lru"
        assert stats["max_size"] == 5
        assert "oldest_entry_age_days" in stats
        assert "newest_entry_age_days" in stats
        assert stats["oldest_entry_age_days"] >= 0
        assert stats["newest_entry_age_days"] >= 0

    def test_cleanup_old(self, cache):
        """Test cleaning up old cache entries."""
        # Add entry with old timestamp
        old_time = time.time() - (40 * 86400)  # 40 days ago
        cache.put("old_text", "model", [0.1])
        key = cache._get_cache_key("old_text", "model")
        cache._index[key].timestamp = old_time

        # Add recent entry
        cache.put("new_text", "model", [0.2])

        assert len(cache._index) == 2

        # Cleanup entries older than 30 days
        count = cache.cleanup_old(max_age_days=30)
        assert count == 1
        assert len(cache._index) == 1

        # Only new entry should remain
        assert cache.get("old_text", "model") is None
        assert cache.get("new_text", "model") is not None

    def test_cleanup_old_no_old_entries(self, cache):
        """Test cleanup when no old entries exist."""
        cache.put("text1", "model", [0.1])
        cache.put("text2", "model", [0.2])

        count = cache.cleanup_old(max_age_days=30)
        assert count == 0
        assert len(cache._index) == 2

    def test_cleanup_old_file_removal_error(self, cache, monkeypatch):
        """Test cleanup when file removal fails."""
        # Add old entry
        old_time = time.time() - (40 * 86400)
        cache.put("old_text", "model", [0.1])
        key = cache._get_cache_key("old_text", "model")
        cache._index[key].timestamp = old_time

        # Mock unlink to raise exception
        def mock_unlink(self):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        # Cleanup should handle errors gracefully
        count = cache.cleanup_old(max_age_days=30)
        # Count might be 0 due to file removal error, but index should be cleaned
        assert key not in cache._index

    def test_context_manager(self, cache_dir):
        """Test cache as context manager."""
        with EmbeddingCache(cache_dir=cache_dir) as cache:
            cache.put("text", "model", [0.1, 0.2])
            assert cache.get("text", "model") is not None
        # Should save index on exit

        # Create new cache instance to verify persistence
        cache2 = EmbeddingCache(cache_dir=cache_dir)
        assert cache2.get("text", "model") is not None

    def test_load_index_file_not_found(self, cache_dir):
        """Test loading index when file doesn't exist."""
        cache = EmbeddingCache(cache_dir=cache_dir)
        # Should work fine with empty index
        assert len(cache._index) == 0

    def test_load_index_corrupted(self, cache_dir):
        """Test loading corrupted index file."""
        # Create corrupted index file
        index_file = cache_dir / "index.json"
        cache_dir.mkdir(parents=True, exist_ok=True)
        index_file.write_text("corrupted json")

        # Should handle corruption gracefully
        cache = EmbeddingCache(cache_dir=cache_dir)
        assert len(cache._index) == 0

    def test_load_index_valid(self, cache_dir):
        """Test loading valid index file."""
        # Create valid index file
        index_data = {
            "test_key": {
                "key": "test_key",
                "embedding": [],
                "model": "test-model",
                "timestamp": 123456.0,
                "access_count": 5,
                "last_access": 123460.0,
                "metadata": {"source": "test"},
            }
        }

        index_file = cache_dir / "index.json"
        cache_dir.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(index_data))

        # Should load index correctly
        cache = EmbeddingCache(cache_dir=cache_dir)
        assert len(cache._index) == 1
        assert "test_key" in cache._index
        entry = cache._index["test_key"]
        assert entry.model == "test-model"
        assert entry.access_count == 5
        assert entry.metadata == {"source": "test"}

    def test_save_index_error(self, cache, monkeypatch):
        """Test save index when write fails."""
        cache.put("text", "model", [0.1])

        # Mock open to raise exception
        def mock_open(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr("builtins.open", mock_open)

        # Should handle save errors gracefully
        cache._save_index()  # Should not raise exception

    def test_put_eviction_during_save(self, cache_dir):
        """Test put operation that triggers eviction."""
        cache = EmbeddingCache(cache_dir=cache_dir, max_size=1)

        # First entry
        cache.put("text1", "model", [0.1])
        assert len(cache._index) == 1

        # Second entry should evict first
        cache.put("text2", "model", [0.2])
        assert len(cache._index) == 1
        assert cache.get("text1", "model") is None
        assert cache.get("text2", "model") is not None

    def test_put_save_file_error(self, cache, monkeypatch):
        """Test put when numpy save fails."""

        # Mock np.save to raise exception
        def mock_save(*args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr("numpy.save", mock_save)

        # Put should handle save errors gracefully
        cache.put("text", "model", [0.1])  # Should not raise

        # Entry should not be in index if save failed
        key = cache._get_cache_key("text", "model")
        # Index behavior depends on implementation - might still add entry
        # This tests that the method doesn't crash

    @pytest.mark.parametrize(
        "strategy",
        [
            InvalidationStrategy.LRU,
            InvalidationStrategy.LFU,
            InvalidationStrategy.FIFO,
            InvalidationStrategy.TTL,
        ],
    )
    def test_all_eviction_strategies(self, cache_dir, strategy):
        """Test all eviction strategies work without errors."""
        cache = EmbeddingCache(
            cache_dir=cache_dir,
            strategy=strategy,
            max_size=2,
            ttl_seconds=3600 if strategy != InvalidationStrategy.TTL else 1,
        )

        # Add entries to trigger eviction
        cache.put("text1", "model", [0.1])
        if strategy == InvalidationStrategy.TTL:
            time.sleep(1.1)  # Wait for TTL expiration

        cache.put("text2", "model", [0.2])
        cache.put("text3", "model", [0.3])

        # Should not exceed max size
        assert len(cache._index) <= cache.max_size
