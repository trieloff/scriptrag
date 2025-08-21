"""Test embedding decoding validation in EmbeddingService."""

import struct
from pathlib import Path

import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def embedding_service(tmp_path: Path) -> EmbeddingService:
    """Create an embedding service instance for testing."""
    settings = ScriptRAGSettings()
    return EmbeddingService(settings, cache_dir=tmp_path / "cache")


class TestEmbeddingDecodeValidation:
    """Test decode_embedding_from_db validation."""

    def test_decode_valid_embedding(self, embedding_service: EmbeddingService) -> None:
        """Test decoding a valid embedding."""
        # Create a valid embedding
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        encoded = embedding_service.encode_embedding_for_db(embedding)

        # Decode should work
        decoded = embedding_service.decode_embedding_from_db(encoded)
        assert len(decoded) == len(embedding)
        assert all(
            abs(a - b) < 0.0001 for a, b in zip(decoded, embedding, strict=False)
        )

    def test_decode_empty_data(self, embedding_service: EmbeddingService) -> None:
        """Test decoding empty data raises ValueError."""
        with pytest.raises(ValueError, match="Embedding data too short"):
            embedding_service.decode_embedding_from_db(b"")

    def test_decode_short_data(self, embedding_service: EmbeddingService) -> None:
        """Test decoding data shorter than 4 bytes raises ValueError."""
        with pytest.raises(ValueError, match="Embedding data too short"):
            embedding_service.decode_embedding_from_db(b"abc")

    def test_decode_zero_dimension(self, embedding_service: EmbeddingService) -> None:
        """Test decoding with zero dimension raises ValueError."""
        # Pack dimension=0
        data = struct.pack("<I", 0)
        with pytest.raises(ValueError, match="Embedding dimension cannot be zero"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_excessive_dimension(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding with excessive dimension raises ValueError."""
        # Pack dimension=20000 (exceeds max_dimension=10000)
        data = struct.pack("<I", 20000)
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_truncated_data(self, embedding_service: EmbeddingService) -> None:
        """Test decoding truncated data raises ValueError."""
        # Create data that claims to have 5 floats but only has 3
        dimension = 5
        truncated_floats = [0.1, 0.2, 0.3]
        data = struct.pack("<I", dimension) + struct.pack(
            f"<{len(truncated_floats)}f", *truncated_floats
        )

        with pytest.raises(ValueError, match="Embedding data truncated"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_corrupted_float_data(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding with corrupted float data raises ValueError."""
        # Create data with valid dimension but not enough bytes for floats
        dimension = 2
        data = struct.pack("<I", dimension) + b"invalid"  # Only 7 extra bytes, need 8

        # This will trigger the truncated data check first
        with pytest.raises(ValueError, match="Embedding data truncated"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_large_valid_embedding(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding a large but valid embedding."""
        # Test with a typical large embedding size (1536 dimensions)
        embedding = [0.1] * 1536
        encoded = embedding_service.encode_embedding_for_db(embedding)

        decoded = embedding_service.decode_embedding_from_db(encoded)
        assert len(decoded) == 1536
        assert all(abs(v - 0.1) < 0.0001 for v in decoded)

    def test_decode_negative_dimension_as_unsigned(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test that negative dimension (when interpreted as unsigned) is caught."""
        # -1 as signed int becomes 4294967295 as unsigned int
        data = struct.pack("<i", -1)  # Pack as signed, will be read as unsigned
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_exact_boundary_dimension(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding at the exact maximum dimension boundary."""
        # Test at exactly max_dimension (10000)
        dimension = 10000
        # Create minimal valid data (dimension + one float to avoid truncation error)
        data = (
            struct.pack("<I", dimension)
            + struct.pack("<f", 0.1)
            + b"\x00" * (dimension * 4 - 4)
        )

        # Should work as it's exactly at the limit
        decoded = embedding_service.decode_embedding_from_db(data)
        assert len(decoded) == dimension

    def test_decode_just_over_boundary(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding just over the maximum dimension boundary."""
        # Test at max_dimension + 1 (10001)
        dimension = 10001
        data = struct.pack("<I", dimension)

        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            embedding_service.decode_embedding_from_db(data)

    def test_decode_malformed_struct_data(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test decoding with data that passes length check but fails struct unpack."""
        # Create data with correct length but NaN/Inf values that might cause issues
        dimension = 2
        # Pack dimension + exactly 8 bytes that form invalid floats
        data = struct.pack("<I", dimension) + struct.pack(
            "<ff", float("nan"), float("inf")
        )

        # Should successfully decode even with NaN/Inf (they're valid float values)
        decoded = embedding_service.decode_embedding_from_db(data)
        assert len(decoded) == 2
        # Note: NaN != NaN in Python, so we can't use equality check

    def test_round_trip_various_sizes(
        self, embedding_service: EmbeddingService
    ) -> None:
        """Test encoding and decoding round-trip for various embedding sizes."""
        test_sizes = [1, 128, 256, 512, 768, 1024, 1536, 2048, 3072, 4096]

        for size in test_sizes:
            embedding = [float(i) / size for i in range(size)]
            encoded = embedding_service.encode_embedding_for_db(embedding)
            decoded = embedding_service.decode_embedding_from_db(encoded)

            assert len(decoded) == size
            assert all(
                abs(a - b) < 0.0001 for a, b in zip(decoded, embedding, strict=False)
            )
