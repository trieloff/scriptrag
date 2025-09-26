"""Tests for strict zip validation in embedding pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.embeddings.batch_processor import BatchResult
from scriptrag.embeddings.pipeline import EmbeddingPipeline, PipelineConfig


class TestStrictZipValidation:
    """Test that zip operations use strict=True for data integrity."""

    @pytest.fixture
    def mock_llm_client(self) -> AsyncMock:
        """Create a mock LLM client."""
        client = AsyncMock()
        client.generate_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]  # 3D embedding
        )
        return client

    @pytest.fixture
    def pipeline(self, mock_llm_client: AsyncMock) -> EmbeddingPipeline:
        """Create an embedding pipeline with mocked LLM client."""
        config = PipelineConfig(
            model="test-model",
            dimensions=3,
            batch_size=2,
            use_cache=False,  # Disable cache for testing
        )
        return EmbeddingPipeline(config, llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_generate_batch_strict_zip_matching_lengths(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test normal case where texts and metadata have matching lengths."""
        texts = ["text1", "text2", "text3"]
        metadata_list = [{"id": 1}, {"id": 2}, {"id": 3}]

        # Mock the batch processor to return BatchResult objects
        mock_results = [
            BatchResult(
                id="0",
                embedding=[0.1, 0.2, 0.3],
                metadata={"id": 1},
                error=None,
            ),
            BatchResult(
                id="1",
                embedding=[0.4, 0.5, 0.6],
                metadata={"id": 2},
                error=None,
            ),
            BatchResult(
                id="2",
                embedding=[0.7, 0.8, 0.9],
                metadata={"id": 3},
                error=None,
            ),
        ]

        with patch.object(
            pipeline.batch_processor,
            "process_parallel",
            return_value=mock_results,
        ):
            result = await pipeline.generate_batch(texts, metadata_list)

        # Should work fine with matching lengths
        assert len(result) == 3
        assert all(emb is not None for emb in result)
        assert result[0] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_generate_batch_strict_zip_mismatched_lengths(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that mismatched lengths between texts and metadata raise ValueError."""
        texts = ["text1", "text2", "text3"]
        metadata_list = [{"id": 1}, {"id": 2}]  # One less metadata

        # Should raise ValueError due to strict=True in zip
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            await pipeline.generate_batch(texts, metadata_list)

    @pytest.mark.asyncio
    async def test_generate_batch_strict_zip_empty_metadata(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that empty metadata list with non-empty texts raises ValueError."""
        texts = ["text1", "text2"]
        metadata_list = []  # Empty metadata

        # Should raise ValueError due to strict=True in zip
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            await pipeline.generate_batch(texts, metadata_list)

    @pytest.mark.asyncio
    async def test_generate_batch_strict_zip_more_metadata(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that more metadata than texts raises ValueError."""
        texts = ["text1"]
        metadata_list = [{"id": 1}, {"id": 2}, {"id": 3}]  # More metadata

        # Should raise ValueError due to strict=True in zip
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            await pipeline.generate_batch(texts, metadata_list)

    @pytest.mark.asyncio
    async def test_generate_for_scenes_strict_zip_matching(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test scene embeddings with matching scene IDs and embeddings."""
        scenes = [
            {"id": 1, "heading": "INT. HOUSE - DAY", "content": "Scene 1 content"},
            {"id": 2, "heading": "EXT. PARK - NIGHT", "content": "Scene 2 content"},
        ]

        # Mock generate_batch to return correct number of embeddings
        expected_embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
        pipeline.generate_batch = AsyncMock(return_value=expected_embeddings)

        result = await pipeline.generate_for_scenes(scenes)

        # Should work fine with matching lengths
        assert len(result) == 2
        assert result[0][0] == 1  # First scene ID
        assert result[1][0] == 2  # Second scene ID
        assert result[0][1] == expected_embeddings[0]
        assert result[1][1] == expected_embeddings[1]

    @pytest.mark.asyncio
    async def test_generate_for_scenes_strict_zip_mismatch(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that mismatched embeddings and scene IDs raise ValueError."""
        scenes = [
            {"id": 1, "heading": "INT. HOUSE - DAY", "content": "Scene 1 content"},
            {"id": 2, "heading": "EXT. PARK - NIGHT", "content": "Scene 2 content"},
            {"id": 3, "heading": "INT. OFFICE - DAY", "content": "Scene 3 content"},
        ]

        # Mock generate_batch to return fewer embeddings (simulating API error)
        pipeline.generate_batch = AsyncMock(
            return_value=[
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                # Missing third embedding
            ]
        )

        # Should raise ValueError due to strict=True in zip
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            await pipeline.generate_for_scenes(scenes)

    @pytest.mark.asyncio
    async def test_generate_for_scenes_api_returns_extra_embeddings(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that extra embeddings from API raise ValueError."""
        scenes = [
            {"id": 1, "heading": "INT. HOUSE - DAY", "content": "Scene 1 content"},
        ]

        # Mock generate_batch to return more embeddings than expected
        pipeline.generate_batch = AsyncMock(
            return_value=[
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],  # Unexpected extra embedding
            ]
        )

        # Should raise ValueError due to strict=True in zip
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            await pipeline.generate_for_scenes(scenes)

    @pytest.mark.asyncio
    async def test_generate_batch_preserves_order(
        self, pipeline: EmbeddingPipeline
    ) -> None:
        """Test that strict zip preserves the order of texts and metadata."""
        texts = ["first", "second", "third"]
        metadata_list = [{"order": 1}, {"order": 2}, {"order": 3}]

        processed_items = []

        # Mock to capture processing order
        def mock_process(text):
            processed_items.append(text)
            return f"processed_{text}"

        pipeline.preprocessor.process = MagicMock(side_effect=mock_process)

        # Mock batch processor with BatchResult objects
        mock_results = [
            BatchResult(
                id="0",
                embedding=[0.1, 0.2, 0.3],
                metadata={"order": 1},
                error=None,
            ),
            BatchResult(
                id="1",
                embedding=[0.4, 0.5, 0.6],
                metadata={"order": 2},
                error=None,
            ),
            BatchResult(
                id="2",
                embedding=[0.7, 0.8, 0.9],
                metadata={"order": 3},
                error=None,
            ),
        ]

        with patch.object(
            pipeline.batch_processor,
            "process_parallel",
            return_value=mock_results,
        ):
            result = await pipeline.generate_batch(texts, metadata_list)

        # Verify order was preserved
        assert processed_items == ["first", "second", "third"]
        assert len(result) == 3

    def test_sync_iteration_behavior(self) -> None:
        """Test that strict=True catches mismatches in synchronous iteration."""
        # This tests the actual Python behavior of strict=True
        list1 = [1, 2, 3]
        list2 = ["a", "b"]

        # Without strict (default behavior before Python 3.10)
        result = list(zip(list1, list2, strict=False))
        assert len(result) == 2  # Silently truncates

        # With strict=True (our fix)
        with pytest.raises(ValueError, match="zip\\(\\) argument"):
            list(zip(list1, list2, strict=True))
