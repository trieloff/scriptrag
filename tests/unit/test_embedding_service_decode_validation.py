"""Test exact size validation for embedding decoding."""

import struct
from pathlib import Path

import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def embedding_service(tmp_path: Path) -> EmbeddingService:
    """Create an embedding service for testing."""
    settings = ScriptRAGSettings()
    return EmbeddingService(settings, cache_dir=tmp_path / "cache")


class TestEmbeddingDecodeExactSizeValidation:
    """Test decode_embedding_from_db validates exact data size."""

    def test_decode_embedding_exact_size_success(self, embedding_service):
        """Test decoding with exact expected data size succeeds."""
        # Create a valid 3-dimensional embedding
        dimension = 3
        values = [1.0, 2.0, 3.0]
        data = struct.pack(f"<I{dimension}f", dimension, *values)

        result = embedding_service.decode_embedding_from_db(data)
        assert result == values

    def test_decode_embedding_truncated_data_fails(self, embedding_service):
        """Test decoding with truncated data fails."""
        # Create truncated data (missing last float)
        dimension = 3
        values = [1.0, 2.0]  # Should have 3 values
        # Pack with wrong dimension count
        data = struct.pack("<I", dimension) + struct.pack("<2f", *values)

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "size mismatch" in str(exc_info.value)
        assert "expected exactly 16 bytes" in str(exc_info.value)
        assert "got 12" in str(exc_info.value)

    def test_decode_embedding_extra_data_fails(self, embedding_service):
        """Test decoding with extra data at the end fails."""
        # Create data with extra bytes at the end
        dimension = 2
        values = [1.0, 2.0]
        valid_data = struct.pack(f"<I{dimension}f", dimension, *values)
        # Add extra garbage data
        extra_data = b"\x00\x00\x00\x00"  # 4 extra bytes
        data = valid_data + extra_data

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "size mismatch" in str(exc_info.value)
        assert "expected exactly 12 bytes" in str(exc_info.value)
        assert "got 16" in str(exc_info.value)

    def test_decode_embedding_zero_dimension_fails(self, embedding_service):
        """Test decoding with zero dimension fails."""
        data = struct.pack("<I", 0)  # Just dimension = 0

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "dimension cannot be zero" in str(exc_info.value)

    def test_decode_embedding_excessive_dimension_fails(self, embedding_service):
        """Test decoding with excessive dimension fails."""
        # Create data with dimension > max allowed
        dimension = 10001  # Over the 10000 limit
        data = struct.pack("<I", dimension) + b"\x00" * 40  # Some dummy data

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "exceeds maximum allowed" in str(exc_info.value)

    def test_decode_embedding_too_short_data_fails(self, embedding_service):
        """Test decoding with data shorter than 4 bytes fails."""
        data = b"\x01\x00"  # Only 2 bytes

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "too short" in str(exc_info.value)
        assert "expected at least 4 bytes" in str(exc_info.value)

    def test_decode_embedding_various_dimensions(self, embedding_service):
        """Test decoding with various valid dimensions."""
        test_cases = [
            (1, [3.14]),
            (5, [1.0, 2.0, 3.0, 4.0, 5.0]),
            (128, [float(i) for i in range(128)]),  # Small embedding
            (1536, [float(i % 100) for i in range(1536)]),  # OpenAI size
        ]

        for dimension, values in test_cases:
            data = struct.pack(f"<I{dimension}f", dimension, *values)
            result = embedding_service.decode_embedding_from_db(data)
            assert len(result) == dimension
            # Use approximate equality for floats due to precision
            for original, recovered in zip(values, result, strict=False):
                assert abs(original - recovered) < 1e-5

    def test_decode_embedding_boundary_conditions(self, embedding_service):
        """Test boundary conditions for data size validation."""
        # Test with dimension that would cause integer overflow if not careful
        dimension = 1000
        values = [1.0] * dimension

        # Exact size should work
        exact_data = struct.pack(f"<I{dimension}f", dimension, *values)
        result = embedding_service.decode_embedding_from_db(exact_data)
        assert len(result) == dimension

        # One byte less should fail
        truncated_data = exact_data[:-1]
        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(truncated_data)
        assert "size mismatch" in str(exc_info.value)

        # One byte more should fail
        extended_data = exact_data + b"\x00"
        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(extended_data)
        assert "size mismatch" in str(exc_info.value)

    def test_encode_decode_roundtrip(self, embedding_service):
        """Test that encode followed by decode preserves exact data."""
        test_embeddings = [
            [1.0],
            [1.0, 2.0, 3.0],
            [float(i) for i in range(100)],
            [0.1 * i for i in range(1536)],  # Typical embedding size
        ]

        for embedding in test_embeddings:
            encoded = embedding_service.encode_embedding_for_db(embedding)
            decoded = embedding_service.decode_embedding_from_db(encoded)

            assert len(decoded) == len(embedding)
            # Use approximate equality for floats (32-bit float precision)
            for original, recovered in zip(embedding, decoded, strict=False):
                assert abs(original - recovered) < 1e-5

    def test_decode_corrupted_struct_data(self, embedding_service):
        """Test handling of corrupted struct data."""
        # Create data where dimension says 3 but struct unpack would fail
        dimension = 3
        # Create intentionally misaligned data (11 bytes, not 12)
        misaligned_bytes = b"\xff\xfe\xfd\xfc\xfb\xfa\xf9\xf8\xf7\xf6\xf5"
        data = struct.pack("<I", dimension) + misaligned_bytes

        with pytest.raises(ValueError) as exc_info:
            embedding_service.decode_embedding_from_db(data)
        assert "size mismatch" in str(exc_info.value)

    def test_decode_handles_nan_and_inf(self, embedding_service):
        """Test decoding handles special float values correctly."""
        import math

        dimension = 4
        values = [1.0, float("nan"), float("inf"), float("-inf")]
        data = struct.pack(f"<I{dimension}f", dimension, *values)

        result = embedding_service.decode_embedding_from_db(data)
        assert len(result) == dimension
        assert result[0] == 1.0
        assert math.isnan(result[1])
        assert math.isinf(result[2]) and result[2] > 0
        assert math.isinf(result[3]) and result[3] < 0
