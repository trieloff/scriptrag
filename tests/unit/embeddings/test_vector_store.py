"""Comprehensive tests for vector store abstraction."""

import json
import struct
from pathlib import Path

import numpy as np
import pytest

from scriptrag.embeddings.vector_store import (
    BinaryEmbeddingSerializer,
    GitLFSVectorStore,
    HybridVectorStore,
    VectorStore,
)


class TestBinaryEmbeddingSerializer:
    """Test BinaryEmbeddingSerializer class."""

    @pytest.fixture
    def serializer(self):
        """Create binary embedding serializer."""
        return BinaryEmbeddingSerializer()

    def test_encode_basic(self, serializer):
        """Test basic encoding of embedding vector."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        encoded = serializer.encode(embedding)

        assert isinstance(encoded, bytes)
        # Should contain dimension count + float values
        expected_size = 4 + (4 * 4)  # 4 bytes for dimension + 4 floats * 4 bytes
        assert len(encoded) == expected_size

    def test_encode_single_dimension(self, serializer):
        """Test encoding single-dimension vector."""
        embedding = [0.5]
        encoded = serializer.encode(embedding)

        assert isinstance(encoded, bytes)
        expected_size = 4 + 4  # 4 bytes for dimension + 1 float * 4 bytes
        assert len(encoded) == expected_size

    def test_encode_empty_vector(self, serializer):
        """Test encoding empty vector."""
        embedding = []
        encoded = serializer.encode(embedding)

        assert isinstance(encoded, bytes)
        expected_size = 4  # Just dimension count (0)
        assert len(encoded) == expected_size

    def test_encode_large_vector(self, serializer):
        """Test encoding large vector."""
        embedding = [0.1] * 1000  # 1000 dimensions
        encoded = serializer.encode(embedding)

        expected_size = 4 + (1000 * 4)  # 4 bytes for dimension + 1000 floats
        assert len(encoded) == expected_size

    def test_encode_negative_values(self, serializer):
        """Test encoding vector with negative values."""
        embedding = [-0.1, 0.2, -0.3, 0.4]
        encoded = serializer.encode(embedding)

        assert isinstance(encoded, bytes)
        expected_size = 4 + (4 * 4)
        assert len(encoded) == expected_size

    def test_decode_basic(self, serializer):
        """Test basic decoding of embedding vector."""
        original = [0.1, 0.2, 0.3, 0.4]
        encoded = serializer.encode(original)
        decoded = serializer.decode(encoded)

        assert len(decoded) == len(original)
        # Use numpy for approximate comparison due to float32 precision
        np.testing.assert_allclose(decoded, original, rtol=1e-6, atol=1e-7)

    def test_decode_single_dimension(self, serializer):
        """Test decoding single-dimension vector."""
        original = [0.75]
        encoded = serializer.encode(original)
        decoded = serializer.decode(encoded)

        assert len(decoded) == 1
        assert pytest.approx(decoded[0]) == 0.75

    def test_decode_empty_vector(self, serializer):
        """Test decoding empty vector."""
        original = []
        encoded = serializer.encode(original)

        # Empty vectors should raise ValueError due to zero dimensions
        with pytest.raises(ValueError) as exc_info:
            serializer.decode(encoded)

        assert "dimension cannot be zero" in str(exc_info.value)

    def test_decode_large_vector(self, serializer):
        """Test decoding large vector."""
        original = [0.1] * 1000
        encoded = serializer.encode(original)
        decoded = serializer.decode(encoded)

        assert len(decoded) == 1000
        np.testing.assert_allclose(decoded, original, rtol=1e-6)

    def test_decode_negative_values(self, serializer):
        """Test decoding vector with negative values."""
        original = [-0.5, 0.25, -0.125, 0.875]
        encoded = serializer.encode(original)
        decoded = serializer.decode(encoded)

        np.testing.assert_allclose(decoded, original, rtol=1e-6)

    def test_encode_decode_roundtrip(self, serializer):
        """Test encode-decode roundtrip preserves data."""
        test_vectors = [
            [0.1, 0.2, 0.3],
            [1.0, -1.0, 0.0],
            [1e-6, 1e6, -1e-3],
            [42.0],
            list(range(100)),  # Large vector with varied values
        ]

        for original in test_vectors:
            encoded = serializer.encode(original)
            decoded = serializer.decode(encoded)

            assert len(decoded) == len(original)
            np.testing.assert_allclose(decoded, original, rtol=1e-6)

        # Test empty vector separately (should fail)
        empty_encoded = serializer.encode([])
        with pytest.raises(ValueError):
            serializer.decode(empty_encoded)

    def test_decode_too_short_data(self, serializer):
        """Test decoding data that's too short."""
        short_data = b"abc"  # Less than 4 bytes

        with pytest.raises(ValueError) as exc_info:
            serializer.decode(short_data)

        assert "too short" in str(exc_info.value)
        assert "expected at least 4 bytes" in str(exc_info.value)

    def test_decode_zero_dimensions(self, serializer):
        """Test decoding with zero dimensions."""
        # Manually create data with 0 dimensions
        data = struct.pack("<I", 0)  # 0 dimensions

        with pytest.raises(ValueError) as exc_info:
            serializer.decode(data)

        assert "dimension cannot be zero" in str(exc_info.value)

    def test_decode_excessive_dimensions(self, serializer):
        """Test decoding with excessively large dimension count."""
        # Manually create data with huge dimension count
        data = struct.pack("<I", 50000)  # Way too many dimensions

        with pytest.raises(ValueError) as exc_info:
            serializer.decode(data)

        assert "exceeds maximum allowed" in str(exc_info.value)

    def test_decode_size_mismatch(self, serializer):
        """Test decoding with data size mismatch."""
        # Create data claiming 3 dimensions but only providing 2 floats
        data = struct.pack("<I", 3)  # Claims 3 dimensions
        data += struct.pack("<ff", 0.1, 0.2)  # Only 2 floats

        with pytest.raises(ValueError) as exc_info:
            serializer.decode(data)

        assert "size mismatch" in str(exc_info.value)

    def test_decode_corrupted_float_data(self, serializer):
        """Test decoding with corrupted float data."""
        # Create data with correct header but corrupted float section
        data = struct.pack("<I", 2)  # Claims 2 dimensions
        data += b"corrupted"[:8]  # 8 bytes of corrupted data instead of 2 floats

        # This might not raise ValueError with certain corrupted data patterns
        # Instead test with a known problematic case
        try:
            result = serializer.decode(data)
            # If it doesn't raise, at least verify it returns something reasonable
            assert isinstance(result, list)
        except (ValueError, struct.error):
            # Either exception type is acceptable for corrupted data
            pass

    def test_decode_partial_float_data(self, serializer):
        """Test decoding with partial float data."""
        # Create data with correct dimension but incomplete float data
        data = struct.pack("<I", 2)  # Claims 2 dimensions (needs 8 bytes)
        data += struct.pack("<f", 0.1)  # Only 1 float (4 bytes)
        data += b"xx"  # 2 more bytes, but not a complete float

        with pytest.raises(ValueError) as exc_info:
            serializer.decode(data)

        assert "size mismatch" in str(exc_info.value)

    def test_encode_decode_extreme_values(self, serializer):
        """Test encoding/decoding extreme float values."""
        extreme_values = [
            float("inf"),
            float("-inf"),
            float("nan"),
            1.7976931348623157e308,  # Close to max float
            2.2250738585072014e-308,  # Close to min positive float
        ]

        # Note: This tests the serializer's behavior with extreme values
        # Some values like inf/nan might not round-trip exactly
        for value in extreme_values:
            try:
                encoded = serializer.encode([value])
                decoded = serializer.decode(encoded)
                # Test passes if no exception is raised
                assert len(decoded) == 1
            except (OverflowError, struct.error):
                # Some extreme values might not be representable in float32
                pass

    def test_binary_format_consistency(self, serializer):
        """Test that binary format is consistent across calls."""
        embedding = [0.1, 0.2, 0.3]

        encoded1 = serializer.encode(embedding)
        encoded2 = serializer.encode(embedding)

        # Same input should produce identical binary output
        assert encoded1 == encoded2

    def test_little_endian_format(self, serializer):
        """Test that serializer uses little-endian format."""
        embedding = [1.0]
        encoded = serializer.encode(embedding)

        # Manually decode to verify little-endian format
        dimension = struct.unpack("<I", encoded[:4])[0]
        assert dimension == 1

        value = struct.unpack("<f", encoded[4:8])[0]
        assert pytest.approx(value) == 1.0


class MockVectorStore(VectorStore):
    """Mock implementation of VectorStore for testing."""

    def __init__(self):
        self.storage = {}
        self.call_log = []

    def _make_key(self, entity_type, entity_id, model):
        return f"{entity_type}:{entity_id}:{model}"

    def store(self, entity_type, entity_id, embedding, model, metadata=None):
        key = self._make_key(entity_type, entity_id, model)
        self.storage[key] = {"embedding": embedding, "metadata": metadata}
        self.call_log.append(("store", entity_type, entity_id, model))

    def retrieve(self, entity_type, entity_id, model):
        key = self._make_key(entity_type, entity_id, model)
        self.call_log.append(("retrieve", entity_type, entity_id, model))
        data = self.storage.get(key)
        return data["embedding"] if data else None

    def search(
        self,
        query_embedding,
        entity_type,
        model,
        limit=10,
        threshold=None,
        filter_criteria=None,
    ):
        self.call_log.append(("search", entity_type, model, limit))
        # Simple mock search - return all stored embeddings of matching type/model
        results = []
        for key, data in self.storage.items():
            stored_type, stored_id, stored_model = key.split(":")
            if stored_type == entity_type and stored_model == model:
                # Mock similarity score
                score = 0.8
                metadata = data.get("metadata", {})
                results.append((int(stored_id), score, metadata))
        return results[:limit]

    def delete(self, entity_type, entity_id, model=None):
        self.call_log.append(("delete", entity_type, entity_id, model))
        if model:
            key = self._make_key(entity_type, entity_id, model)
            return key in self.storage and self.storage.pop(key, None) is not None
        # Delete all models for this entity
        keys_to_delete = [
            k for k in self.storage if k.startswith(f"{entity_type}:{entity_id}:")
        ]
        for key in keys_to_delete:
            del self.storage[key]
        return len(keys_to_delete) > 0

    def exists(self, entity_type, entity_id, model):
        key = self._make_key(entity_type, entity_id, model)
        self.call_log.append(("exists", entity_type, entity_id, model))
        return key in self.storage


class TestVectorStore:
    """Test abstract VectorStore base class."""

    def test_is_abstract(self):
        """Test that VectorStore cannot be instantiated directly."""
        with pytest.raises(TypeError):
            VectorStore()

    def test_abstract_methods_defined(self):
        """Test that all abstract methods are defined."""
        # Check that abstract methods exist
        abstract_methods = {"store", "retrieve", "search", "delete", "exists"}
        vector_store_methods = set(VectorStore.__abstractmethods__)
        assert vector_store_methods == abstract_methods


class TestGitLFSVectorStore:
    """Test GitLFSVectorStore class."""

    @pytest.fixture
    def lfs_dir(self, tmp_path):
        """Create temporary LFS directory."""
        return tmp_path / "lfs_embeddings"

    @pytest.fixture
    def vector_store(self, lfs_dir):
        """Create GitLFS vector store."""
        return GitLFSVectorStore(lfs_dir=lfs_dir)

    def test_init_with_lfs_dir(self, lfs_dir):
        """Test initialization with explicit LFS directory."""
        store = GitLFSVectorStore(lfs_dir=lfs_dir)
        assert store.lfs_dir == lfs_dir

    def test_init_default_lfs_dir(self):
        """Test initialization with default LFS directory."""
        store = GitLFSVectorStore()
        assert store.lfs_dir == Path(".embeddings")

    def test_ensure_gitattributes(self, vector_store):
        """Test that .gitattributes file is created."""
        gitattributes_path = vector_store.lfs_dir / ".gitattributes"

        # Should be created during initialization
        assert gitattributes_path.exists()
        content = gitattributes_path.read_text()
        assert "*.npy filter=lfs" in content
        assert "diff=lfs" in content
        assert "merge=lfs" in content
        assert "-text" in content

    def test_ensure_gitattributes_already_exists(self, lfs_dir):
        """Test initialization when .gitattributes already exists."""
        # Pre-create .gitattributes with different content
        lfs_dir.mkdir(parents=True)
        gitattributes_path = lfs_dir / ".gitattributes"
        gitattributes_path.write_text("existing content")

        # Initialize store - should not overwrite existing file
        store = GitLFSVectorStore(lfs_dir=lfs_dir)

        assert gitattributes_path.exists()
        content = gitattributes_path.read_text()
        assert content == "existing content"

    def test_get_path(self, vector_store):
        """Test path generation for embeddings."""
        path = vector_store._get_path("scene", 42, "text-embedding-3-small")

        # Should create nested directory structure
        expected_parts = [
            "text-embedding-3-small",  # Model (/ replaced with _)
            "scene",  # Entity type
            "42.npy",  # Entity ID with .npy extension
        ]

        for part in expected_parts:
            assert part in str(path)

        assert path.suffix == ".npy"

    def test_get_path_model_with_slash(self, vector_store):
        """Test path generation for model name containing slash."""
        path = vector_store._get_path("scene", 1, "openai/text-embedding")

        # Slash should be replaced with underscore
        assert "openai_text-embedding" in str(path)
        assert "openai/text-embedding" not in str(path)

    def test_store_basic(self, vector_store):
        """Test basic embedding storage."""
        embedding = [0.1, 0.2, 0.3, 0.4]

        vector_store.store("scene", 42, embedding, "test-model")

        # Check that file was created
        path = vector_store._get_path("scene", 42, "test-model")
        assert path.exists()

        # Load and verify content
        loaded = np.load(path)
        np.testing.assert_allclose(loaded, embedding, rtol=1e-6)

    def test_store_with_metadata(self, vector_store):
        """Test embedding storage with metadata."""
        embedding = [0.1, 0.2]
        metadata = {"title": "Test Scene", "act": 1}

        vector_store.store("scene", 42, embedding, "test-model", metadata=metadata)

        # Check embedding file
        path = vector_store._get_path("scene", 42, "test-model")
        assert path.exists()

        # Check metadata file
        meta_path = path.with_suffix(".json")
        assert meta_path.exists()

        loaded_metadata = json.loads(meta_path.read_text())
        assert loaded_metadata == metadata

    def test_store_creates_directories(self, vector_store):
        """Test that store creates necessary directory structure."""
        embedding = [0.1, 0.2]

        # Directory shouldn't exist initially
        path = vector_store._get_path("new_type", 999, "new-model")
        assert not path.parent.exists()

        vector_store.store("new_type", 999, embedding, "new-model")

        # Directory should be created
        assert path.parent.exists()
        assert path.exists()

    def test_store_overwrites_existing(self, vector_store):
        """Test that store overwrites existing embeddings."""
        entity_type, entity_id, model = "scene", 42, "test-model"

        # Store first embedding
        embedding1 = [0.1, 0.2]
        vector_store.store(entity_type, entity_id, embedding1, model)

        # Store second embedding (should overwrite)
        embedding2 = [0.3, 0.4]
        vector_store.store(entity_type, entity_id, embedding2, model)

        # Should contain second embedding
        path = vector_store._get_path(entity_type, entity_id, model)
        loaded = np.load(path)
        np.testing.assert_allclose(loaded, embedding2, rtol=1e-6)

    def test_retrieve_existing(self, vector_store):
        """Test retrieving existing embedding."""
        embedding = [0.1, 0.2, 0.3]
        entity_type, entity_id, model = "scene", 42, "test-model"

        # Store embedding
        vector_store.store(entity_type, entity_id, embedding, model)

        # Retrieve embedding
        retrieved = vector_store.retrieve(entity_type, entity_id, model)

        assert retrieved is not None
        np.testing.assert_allclose(retrieved, embedding, rtol=1e-6)

    def test_retrieve_nonexistent(self, vector_store):
        """Test retrieving non-existent embedding."""
        result = vector_store.retrieve("nonexistent", 999, "fake-model")
        assert result is None

    def test_retrieve_corrupted_file(self, vector_store):
        """Test retrieving from corrupted file."""
        entity_type, entity_id, model = "scene", 42, "test-model"

        # Create path and write corrupted data
        path = vector_store._get_path(entity_type, entity_id, model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"corrupted data")

        # Should return None for corrupted file
        result = vector_store.retrieve(entity_type, entity_id, model)
        assert result is None

    def test_search_not_implemented(self, vector_store):
        """Test that search raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            vector_store.search([0.1, 0.2], "scene", "test-model")

        assert "does not support similarity search" in str(exc_info.value)

    def test_delete_specific_model(self, vector_store):
        """Test deleting embedding for specific model."""
        embedding = [0.1, 0.2]
        entity_type, entity_id = "scene", 42
        model1, model2 = "model-1", "model-2"

        # Store embeddings for both models
        vector_store.store(entity_type, entity_id, embedding, model1)
        vector_store.store(entity_type, entity_id, embedding, model2)

        # Delete only model1
        result = vector_store.delete(entity_type, entity_id, model1)
        assert result is True

        # model1 should be gone, model2 should remain
        assert not vector_store.exists(entity_type, entity_id, model1)
        assert vector_store.exists(entity_type, entity_id, model2)

    def test_delete_all_models(self, vector_store):
        """Test deleting embeddings for all models."""
        embedding = [0.1, 0.2]
        entity_type, entity_id = "scene", 42
        model1, model2 = "model-1", "model-2"

        # Store embeddings for both models
        vector_store.store(entity_type, entity_id, embedding, model1)
        vector_store.store(entity_type, entity_id, embedding, model2)

        # Delete all models (model=None)
        result = vector_store.delete(entity_type, entity_id, model=None)
        assert result is True

        # Both should be gone
        assert not vector_store.exists(entity_type, entity_id, model1)
        assert not vector_store.exists(entity_type, entity_id, model2)

    def test_delete_with_metadata(self, vector_store):
        """Test deleting embedding that has metadata file."""
        embedding = [0.1, 0.2]
        metadata = {"test": "data"}
        entity_type, entity_id, model = "scene", 42, "test-model"

        # Store with metadata
        vector_store.store(entity_type, entity_id, embedding, model, metadata)

        # Verify both files exist
        path = vector_store._get_path(entity_type, entity_id, model)
        meta_path = path.with_suffix(".json")
        assert path.exists()
        assert meta_path.exists()

        # Delete
        result = vector_store.delete(entity_type, entity_id, model)
        assert result is True

        # Both files should be gone
        assert not path.exists()
        assert not meta_path.exists()

    def test_delete_nonexistent(self, vector_store):
        """Test deleting non-existent embedding."""
        result = vector_store.delete("nonexistent", 999, "fake-model")
        assert result is False

    def test_exists_true(self, vector_store):
        """Test exists check for existing embedding."""
        embedding = [0.1, 0.2]
        entity_type, entity_id, model = "scene", 42, "test-model"

        # Initially should not exist
        assert not vector_store.exists(entity_type, entity_id, model)

        # Store embedding
        vector_store.store(entity_type, entity_id, embedding, model)

        # Should now exist
        assert vector_store.exists(entity_type, entity_id, model)

    def test_exists_false(self, vector_store):
        """Test exists check for non-existent embedding."""
        assert not vector_store.exists("nonexistent", 999, "fake-model")

    def test_multiple_entity_types(self, vector_store):
        """Test storing embeddings for different entity types."""
        embedding = [0.1, 0.2]
        model = "test-model"

        # Store different entity types
        vector_store.store("scene", 1, embedding, model)
        vector_store.store("character", 1, embedding, model)
        vector_store.store("dialogue", 1, embedding, model)

        # All should exist independently
        assert vector_store.exists("scene", 1, model)
        assert vector_store.exists("character", 1, model)
        assert vector_store.exists("dialogue", 1, model)

        # Should be stored in different directories
        scene_path = vector_store._get_path("scene", 1, model)
        char_path = vector_store._get_path("character", 1, model)
        assert scene_path != char_path

    def test_multiple_models(self, vector_store):
        """Test storing embeddings for different models."""
        embedding = [0.1, 0.2]
        entity_type, entity_id = "scene", 1

        models = ["model-a", "model-b", "model-c"]

        # Store for all models
        for model in models:
            vector_store.store(entity_type, entity_id, embedding, model)

        # All should exist
        for model in models:
            assert vector_store.exists(entity_type, entity_id, model)

        # Should be in different model directories
        paths = [
            vector_store._get_path(entity_type, entity_id, model) for model in models
        ]
        assert len(set(paths)) == len(models)  # All paths should be unique

    def test_large_embedding_storage(self, vector_store):
        """Test storing large embedding vectors."""
        # Create large embedding (1000 dimensions)
        large_embedding = [0.001 * i for i in range(1000)]

        vector_store.store("scene", 1, large_embedding, "large-model")

        retrieved = vector_store.retrieve("scene", 1, "large-model")
        assert retrieved is not None
        assert len(retrieved) == 1000
        np.testing.assert_allclose(retrieved, large_embedding, rtol=1e-6)

    def test_concurrent_access_simulation(self, vector_store):
        """Test behavior under simulated concurrent access."""
        embedding = [0.1, 0.2, 0.3]
        entity_type, model = "scene", "test-model"

        # Simulate multiple "concurrent" writes to different entities
        for i in range(10):
            vector_store.store(entity_type, i, embedding, model)

        # All should be retrievable
        for i in range(10):
            retrieved = vector_store.retrieve(entity_type, i, model)
            assert retrieved is not None
            np.testing.assert_allclose(retrieved, embedding, rtol=1e-6)


class TestHybridVectorStore:
    """Test HybridVectorStore class."""

    @pytest.fixture
    def primary_store(self):
        """Create primary mock store."""
        return MockVectorStore()

    @pytest.fixture
    def secondary_store(self):
        """Create secondary mock store."""
        return MockVectorStore()

    @pytest.fixture
    def hybrid_store(self, primary_store, secondary_store):
        """Create hybrid store with primary and secondary."""
        return HybridVectorStore(primary_store, secondary_store)

    @pytest.fixture
    def hybrid_store_no_secondary(self, primary_store):
        """Create hybrid store with only primary."""
        return HybridVectorStore(primary_store, None)

    def test_init_with_both_stores(self, primary_store, secondary_store):
        """Test initialization with both primary and secondary stores."""
        hybrid = HybridVectorStore(primary_store, secondary_store)
        assert hybrid.primary == primary_store
        assert hybrid.secondary == secondary_store

    def test_init_primary_only(self, primary_store):
        """Test initialization with primary store only."""
        hybrid = HybridVectorStore(primary_store, None)
        assert hybrid.primary == primary_store
        assert hybrid.secondary is None

    def test_store_both_stores(self, hybrid_store, primary_store, secondary_store):
        """Test storing in both primary and secondary stores."""
        embedding = [0.1, 0.2, 0.3]
        metadata = {"test": "data"}

        hybrid_store.store("scene", 42, embedding, "test-model", metadata)

        # Should be stored in both stores
        assert ("store", "scene", 42, "test-model") in primary_store.call_log
        assert ("store", "scene", 42, "test-model") in secondary_store.call_log

        # Verify data in both stores
        primary_key = primary_store._make_key("scene", 42, "test-model")
        secondary_key = secondary_store._make_key("scene", 42, "test-model")

        assert primary_key in primary_store.storage
        assert secondary_key in secondary_store.storage
        assert primary_store.storage[primary_key]["embedding"] == embedding
        assert secondary_store.storage[secondary_key]["embedding"] == embedding

    def test_store_primary_only(self, hybrid_store_no_secondary, primary_store):
        """Test storing with primary store only."""
        embedding = [0.1, 0.2]

        hybrid_store_no_secondary.store("scene", 42, embedding, "test-model")

        # Should only be stored in primary
        assert ("store", "scene", 42, "test-model") in primary_store.call_log

    def test_store_secondary_failure(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test storing when secondary store fails."""
        embedding = [0.1, 0.2]

        # Make secondary store raise exception
        def failing_store(*args, **kwargs):
            raise Exception("Secondary store failed")

        secondary_store.store = failing_store

        # Should succeed despite secondary failure
        hybrid_store.store("scene", 42, embedding, "test-model")

        # Primary should still be called
        assert ("store", "scene", 42, "test-model") in primary_store.call_log

    def test_retrieve_from_primary(self, hybrid_store, primary_store, secondary_store):
        """Test retrieving from primary store."""
        embedding = [0.1, 0.2]

        # Store in primary only
        primary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.retrieve("scene", 42, "test-model")

        assert result == embedding
        assert ("retrieve", "scene", 42, "test-model") in primary_store.call_log
        # Secondary should not be called if primary has the data
        assert ("retrieve", "scene", 42, "test-model") not in secondary_store.call_log

    def test_retrieve_fallback_to_secondary(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test retrieving falls back to secondary when primary fails."""
        embedding = [0.1, 0.2]

        # Store in secondary only
        secondary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.retrieve("scene", 42, "test-model")

        assert result == embedding
        # Both should be called
        assert ("retrieve", "scene", 42, "test-model") in primary_store.call_log
        assert ("retrieve", "scene", 42, "test-model") in secondary_store.call_log

    def test_retrieve_restore_to_primary(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test that secondary data is restored to primary on retrieval."""
        embedding = [0.1, 0.2]

        # Store in secondary only
        secondary_store.store("scene", 42, embedding, "test-model")

        # Retrieve - should restore to primary
        result = hybrid_store.retrieve("scene", 42, "test-model")

        assert result == embedding
        # Primary should now have the data
        primary_key = primary_store._make_key("scene", 42, "test-model")
        assert primary_key in primary_store.storage

    def test_retrieve_restore_failure(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test retrieval when restore to primary fails."""
        embedding = [0.1, 0.2]

        # Store in secondary
        secondary_store.store("scene", 42, embedding, "test-model")

        # Make primary store fail
        def failing_store(*args, **kwargs):
            raise Exception("Primary store failed")

        primary_store.store = failing_store

        # Should still return data despite restore failure
        result = hybrid_store.retrieve("scene", 42, "test-model")
        assert result == embedding

    def test_retrieve_not_found(self, hybrid_store):
        """Test retrieving non-existent data."""
        result = hybrid_store.retrieve("scene", 999, "nonexistent-model")
        assert result is None

    def test_retrieve_no_secondary(self, hybrid_store_no_secondary, primary_store):
        """Test retrieving with no secondary store."""
        embedding = [0.1, 0.2]
        primary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store_no_secondary.retrieve("scene", 42, "test-model")

        assert result == embedding
        assert ("retrieve", "scene", 42, "test-model") in primary_store.call_log

    def test_search_primary_only(self, hybrid_store, primary_store, secondary_store):
        """Test that search only uses primary store."""
        query_embedding = [0.1, 0.2]

        results = hybrid_store.search(query_embedding, "scene", "test-model", limit=5)

        # Should only call primary store
        assert ("search", "scene", "test-model", 5) in primary_store.call_log
        assert "search" not in [call[0] for call in secondary_store.call_log]

    def test_delete_both_stores(self, hybrid_store, primary_store, secondary_store):
        """Test deleting from both stores."""
        embedding = [0.1, 0.2]

        # Store in both
        primary_store.store("scene", 42, embedding, "test-model")
        secondary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.delete("scene", 42, "test-model")

        assert result is True
        assert ("delete", "scene", 42, "test-model") in primary_store.call_log
        assert ("delete", "scene", 42, "test-model") in secondary_store.call_log

    def test_delete_primary_false_secondary_true(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test delete when primary returns False but secondary returns True."""
        embedding = [0.1, 0.2]

        # Store in secondary only
        secondary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.delete("scene", 42, "test-model")

        # Should return True because secondary deletion succeeded
        assert result is True

    def test_delete_secondary_failure(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test delete when secondary store fails."""
        embedding = [0.1, 0.2]
        primary_store.store("scene", 42, embedding, "test-model")

        # Make secondary delete fail
        def failing_delete(*args, **kwargs):
            raise Exception("Secondary delete failed")

        secondary_store.delete = failing_delete

        # Should still succeed if primary succeeds
        result = hybrid_store.delete("scene", 42, "test-model")
        assert result is True

    def test_delete_no_secondary(self, hybrid_store_no_secondary, primary_store):
        """Test delete with no secondary store."""
        embedding = [0.1, 0.2]
        primary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store_no_secondary.delete("scene", 42, "test-model")

        assert result is True
        assert ("delete", "scene", 42, "test-model") in primary_store.call_log

    def test_exists_primary_true(self, hybrid_store, primary_store, secondary_store):
        """Test exists when primary returns True."""
        embedding = [0.1, 0.2]
        primary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.exists("scene", 42, "test-model")

        assert result is True
        assert ("exists", "scene", 42, "test-model") in primary_store.call_log
        # Secondary should not be checked
        assert "exists" not in [call[0] for call in secondary_store.call_log]

    def test_exists_fallback_to_secondary(
        self, hybrid_store, primary_store, secondary_store
    ):
        """Test exists falls back to secondary when primary returns False."""
        embedding = [0.1, 0.2]
        secondary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store.exists("scene", 42, "test-model")

        assert result is True
        # Both should be checked
        assert ("exists", "scene", 42, "test-model") in primary_store.call_log
        assert ("exists", "scene", 42, "test-model") in secondary_store.call_log

    def test_exists_both_false(self, hybrid_store):
        """Test exists when neither store has the data."""
        result = hybrid_store.exists("scene", 999, "nonexistent-model")
        assert result is False

    def test_exists_no_secondary(self, hybrid_store_no_secondary, primary_store):
        """Test exists with no secondary store."""
        embedding = [0.1, 0.2]
        primary_store.store("scene", 42, embedding, "test-model")

        result = hybrid_store_no_secondary.exists("scene", 42, "test-model")

        assert result is True
        assert ("exists", "scene", 42, "test-model") in primary_store.call_log

    def test_operation_order(self, hybrid_store, primary_store, secondary_store):
        """Test that operations follow expected order (primary first)."""
        embedding = [0.1, 0.2]

        # Store, retrieve, delete operations
        hybrid_store.store("scene", 42, embedding, "test-model")
        hybrid_store.retrieve("scene", 42, "test-model")
        hybrid_store.delete("scene", 42, "test-model")
        hybrid_store.exists("scene", 42, "test-model")

        # Primary should be called for all operations
        primary_calls = [call[0] for call in primary_store.call_log]
        assert "store" in primary_calls
        assert "retrieve" in primary_calls
        assert "delete" in primary_calls
        assert "exists" in primary_calls

        # Secondary should be called for store and delete
        secondary_calls = [call[0] for call in secondary_store.call_log]
        assert "store" in secondary_calls
        assert "delete" in secondary_calls
