"""Comprehensive tests for batch processing utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.embeddings.batch_processor import (
    BatchItem,
    BatchProcessor,
    BatchResult,
    ChunkedBatchProcessor,
)
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LLMClient)
    client.embed = AsyncMock()
    return client


@pytest.fixture
def sample_batch_items():
    """Create sample batch items."""
    return [
        BatchItem(id="1", text="First text", metadata={"type": "scene"}),
        BatchItem(id="2", text="Second text", metadata={"type": "dialogue"}),
        BatchItem(id="3", text="Third text"),
    ]


@pytest.fixture
def batch_processor(mock_llm_client):
    """Create batch processor with mock client."""
    return BatchProcessor(
        llm_client=mock_llm_client,
        batch_size=2,
        max_concurrent=2,
        retry_attempts=3,
        retry_delay=0.1,
    )


class TestBatchItem:
    """Test BatchItem dataclass."""

    def test_init(self):
        """Test BatchItem initialization."""
        item = BatchItem(id="test", text="content")
        assert item.id == "test"
        assert item.text == "content"
        assert item.metadata is None

    def test_init_with_metadata(self):
        """Test BatchItem with metadata."""
        metadata = {"scene_id": 42}
        item = BatchItem(id="test", text="content", metadata=metadata)
        assert item.metadata == metadata


class TestBatchResult:
    """Test BatchResult dataclass."""

    def test_init_success(self):
        """Test successful BatchResult."""
        embedding = [0.1, 0.2, 0.3]
        result = BatchResult(id="test", embedding=embedding, metadata={"key": "value"})
        assert result.id == "test"
        assert result.embedding == embedding
        assert result.error is None
        assert result.metadata == {"key": "value"}

    def test_init_failure(self):
        """Test failed BatchResult."""
        result = BatchResult(id="test", embedding=None, error="Failed to process")
        assert result.id == "test"
        assert result.embedding is None
        assert result.error == "Failed to process"
        assert result.metadata is None


class TestBatchProcessor:
    """Test BatchProcessor class."""

    def test_init(self, mock_llm_client):
        """Test BatchProcessor initialization."""
        processor = BatchProcessor(
            llm_client=mock_llm_client,
            batch_size=5,
            max_concurrent=3,
            retry_attempts=2,
            retry_delay=0.5,
        )
        assert processor.llm_client == mock_llm_client
        assert processor.batch_size == 5
        assert processor.max_concurrent == 3
        assert processor.retry_attempts == 2
        assert processor.retry_delay == 0.5
        assert processor._semaphore._value == 3

    def test_init_defaults(self, mock_llm_client):
        """Test BatchProcessor with default parameters."""
        processor = BatchProcessor(llm_client=mock_llm_client)
        assert processor.batch_size == 10
        assert processor.max_concurrent == 3
        assert processor.retry_attempts == 3
        assert processor.retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_process_batch_success(self, batch_processor, mock_llm_client):
        """Test successful batch processing."""
        # Mock successful response
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        items = [BatchItem(id="1", text="test text")]
        results = await batch_processor.process_batch(items, "test-model")

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].embedding == [0.1, 0.2, 0.3]
        assert results[0].error is None
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_batch_with_dimensions(
        self, batch_processor, mock_llm_client
    ):
        """Test batch processing with custom dimensions."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        items = [BatchItem(id="1", text="test text")]
        results = await batch_processor.process_batch(
            items, "test-model", dimensions=512
        )

        # Check that dimensions were passed in request
        call_args = mock_llm_client.embed.call_args[0][0]
        assert call_args.dimensions == 512
        assert results[0].embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_process_batch_no_embedding_in_response(
        self, batch_processor, mock_llm_client
    ):
        """Test batch processing when response has no embedding."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{}],  # No embedding field
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        items = [BatchItem(id="1", text="test text")]
        results = await batch_processor.process_batch(items, "test-model")

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].embedding is None
        assert "No embedding in response" in results[0].error

    @pytest.mark.asyncio
    async def test_process_batch_empty_data(self, batch_processor, mock_llm_client):
        """Test batch processing when response has empty data."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[],  # Empty data
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        items = [BatchItem(id="1", text="test text")]
        results = await batch_processor.process_batch(items, "test-model")

        assert len(results) == 1
        assert results[0].embedding is None
        assert "No embedding in response" in results[0].error

    @pytest.mark.asyncio
    async def test_process_single_with_retry_success(
        self, batch_processor, mock_llm_client
    ):
        """Test single item processing with retry on first failure."""
        # First call fails, second succeeds
        mock_llm_client.embed.side_effect = [
            Exception("Temporary error"),
            EmbeddingResponse(
                model="test-model",
                data=[{"embedding": [0.1, 0.2, 0.3]}],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            ),
        ]

        item = BatchItem(id="1", text="test")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.id == "1"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.error is None
        assert mock_llm_client.embed.call_count == 2

    @pytest.mark.asyncio
    async def test_process_single_with_retry_all_failures(
        self, batch_processor, mock_llm_client
    ):
        """Test single item processing when all retries fail."""
        mock_llm_client.embed.side_effect = Exception("Persistent error")

        item = BatchItem(id="1", text="test")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.id == "1"
        assert result.embedding is None
        assert "Persistent error" in result.error
        assert mock_llm_client.embed.call_count == 3  # All retry attempts

    @pytest.mark.asyncio
    async def test_process_single_exponential_backoff(
        self, batch_processor, mock_llm_client
    ):
        """Test exponential backoff in retry logic."""
        mock_llm_client.embed.side_effect = Exception("Error")

        with patch("asyncio.sleep") as mock_sleep:
            item = BatchItem(id="1", text="test")
            await batch_processor._process_single_with_retry(item, "test-model", None)

            # Should have called sleep twice (between 3 attempts)
            assert mock_sleep.call_count == 2
            # First sleep: 0.1 * 2^0 = 0.1
            mock_sleep.assert_any_call(0.1)
            # Second sleep: 0.1 * 2^1 = 0.2
            mock_sleep.assert_any_call(0.2)

    @pytest.mark.asyncio
    async def test_process_stream(self, batch_processor, mock_llm_client):
        """Test stream processing."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        async def item_stream():
            for i in range(5):
                yield BatchItem(id=str(i), text=f"text {i}")

        results = []
        async for result in batch_processor.process_stream(item_stream(), "test-model"):
            results.append(result)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.id == str(i)
            assert result.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_process_stream_with_progress_callback(
        self, batch_processor, mock_llm_client
    ):
        """Test stream processing with progress callback."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        progress_calls = []

        async def progress_callback(count):
            progress_calls.append(count)

        async def item_stream():
            for i in range(3):
                yield BatchItem(id=str(i), text=f"text {i}")

        results = []
        async for result in batch_processor.process_stream(
            item_stream(), "test-model", progress_callback=progress_callback
        ):
            results.append(result)

        assert len(results) == 3
        # Progress should be called for each batch (batch_size=2, so 2 calls)
        assert len(progress_calls) >= 1
        assert progress_calls[-1] == 3  # Final count

    @pytest.mark.asyncio
    async def test_process_stream_partial_batch(self, batch_processor, mock_llm_client):
        """Test stream processing with partial final batch."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        async def item_stream():
            # 3 items with batch_size=2 should create one full batch and one partial
            for i in range(3):
                yield BatchItem(id=str(i), text=f"text {i}")

        results = []
        async for result in batch_processor.process_stream(item_stream(), "test-model"):
            results.append(result)

        assert len(results) == 3
        # Should process full batch (2 items) then partial batch (1 item)

    @pytest.mark.asyncio
    async def test_process_parallel(self, batch_processor, mock_llm_client):
        """Test parallel batch processing."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Create 5 items (will be split into 3 batches with batch_size=2)
        items = [BatchItem(id=str(i), text=f"text {i}") for i in range(5)]

        results = await batch_processor.process_parallel(items, "test-model")

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.id == str(i)
            assert result.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_process_parallel_empty(self, batch_processor):
        """Test parallel processing with empty items."""
        results = await batch_processor.process_parallel([], "test-model")
        assert results == []

    def test_estimate_tokens(self, batch_processor):
        """Test token estimation."""
        # Simple estimation: ~4 characters per token
        text = "a" * 100
        tokens = batch_processor.estimate_tokens(text)
        assert tokens == 25  # 100 / 4

        text = "hello world"
        tokens = batch_processor.estimate_tokens(text)
        assert tokens == 2  # 11 / 4, rounded down

        text = ""
        tokens = batch_processor.estimate_tokens(text)
        assert tokens == 0

    def test_optimize_batch_size_simple(self, batch_processor):
        """Test batch size optimization with simple case."""
        items = [
            BatchItem(id="1", text="a" * 100),  # 25 tokens
            BatchItem(id="2", text="b" * 100),  # 25 tokens
            BatchItem(id="3", text="c" * 100),  # 25 tokens
        ]

        # Max 80 tokens per batch should fit all 3 items (75 total)
        # But batch_size=2 limit means we get 2 batches
        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=80)
        assert len(batches) == 2  # Limited by batch_size=2

    def test_optimize_batch_size_overflow(self, batch_processor):
        """Test batch size optimization with token overflow."""
        items = [
            BatchItem(id="1", text="a" * 200),  # 50 tokens
            BatchItem(id="2", text="b" * 200),  # 50 tokens
            BatchItem(id="3", text="c" * 200),  # 50 tokens
        ]

        # With batch_size=2 and token limits, should create 3 batches
        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=80)
        assert len(batches) == 3  # Each item in separate batch due to size

    def test_optimize_batch_size_respects_max_batch_size(self, batch_processor):
        """Test that optimization respects max batch size setting."""
        # Create many small items
        items = [BatchItem(id=str(i), text="small") for i in range(10)]

        # Even with high token limit, should respect batch_size=2
        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=10000)
        assert len(batches) == 5  # 10 items / 2 per batch
        for batch in batches:
            assert len(batch) <= 2

    def test_optimize_batch_size_empty(self, batch_processor):
        """Test batch optimization with empty items."""
        batches = batch_processor.optimize_batch_size([])
        assert batches == []

    def test_optimize_batch_size_single_large_item(self, batch_processor):
        """Test optimization with single item exceeding token limit."""
        items = [BatchItem(id="1", text="a" * 40000)]  # 10000 tokens

        # Item exceeds limit but must be processed
        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=1000)
        assert len(batches) == 1
        assert len(batches[0]) == 1


class TestChunkedBatchProcessor:
    """Test ChunkedBatchProcessor class."""

    @pytest.fixture
    def chunked_processor(self, mock_llm_client):
        """Create chunked batch processor."""
        return ChunkedBatchProcessor(
            llm_client=mock_llm_client,
            chunk_size=100,
            chunk_overlap=20,
            batch_size=2,
        )

    def test_init(self, mock_llm_client):
        """Test ChunkedBatchProcessor initialization."""
        processor = ChunkedBatchProcessor(
            llm_client=mock_llm_client,
            chunk_size=500,
            chunk_overlap=50,
            batch_size=5,
        )
        assert processor.chunk_size == 500
        assert processor.chunk_overlap == 50
        assert processor.batch_size == 5

    def test_init_defaults(self, mock_llm_client):
        """Test ChunkedBatchProcessor with default parameters."""
        processor = ChunkedBatchProcessor(llm_client=mock_llm_client)
        assert processor.chunk_size == 1000
        assert processor.chunk_overlap == 200
        assert processor.batch_size == 10  # From parent class

    def test_chunk_text_short(self, chunked_processor):
        """Test chunking text shorter than chunk size."""
        text = "Short text"
        chunks = chunked_processor.chunk_text(text)
        assert chunks == [text]

    def test_chunk_text_long(self, chunked_processor):
        """Test chunking long text."""
        text = "a" * 250  # Longer than chunk_size=100
        chunks = chunked_processor.chunk_text(text)

        assert len(chunks) > 1
        # Each chunk should be close to chunk_size
        for chunk in chunks[:-1]:  # All except last
            assert len(chunk) <= 100
        # Chunks should overlap
        if len(chunks) > 1:
            # Check overlap between first two chunks
            overlap = chunks[0][-20:]  # Last 20 chars of first chunk
            assert chunks[1].startswith(overlap[:-1])  # Should appear in second chunk

    def test_chunk_text_with_sentence_breaks(self, chunked_processor):
        """Test chunking respects sentence boundaries."""
        text = "First sentence. " + "a" * 70 + ". Third sentence. " + "b" * 50
        chunks = chunked_processor.chunk_text(text)

        # Should break at sentence boundaries when possible
        assert len(chunks) > 1
        # First chunk should end with a sentence break
        assert chunks[0].endswith(".")

    def test_chunk_text_various_separators(self, chunked_processor):
        """Test chunking with different separators."""
        # Test with different sentence endings
        text = "Question? " + "a" * 70 + "! Exclamation! " + "b" * 50
        chunks = chunked_processor.chunk_text(text)
        assert len(chunks) > 1

        # Test with paragraph breaks
        text = "First paragraph.\n\n" + "a" * 70 + "\n\nSecond paragraph." + "b" * 50
        chunks = chunked_processor.chunk_text(text)
        assert len(chunks) > 1

    def test_chunk_text_no_good_breaks(self, chunked_processor):
        """Test chunking when no good sentence breaks exist."""
        text = "a" * 250  # No sentence breaks
        chunks = chunked_processor.chunk_text(text)

        assert len(chunks) > 1
        # Should still chunk even without good breaks
        total_length = sum(len(chunk) for chunk in chunks)
        # With overlap, total should be more than original
        assert total_length >= len(text)

    def test_chunk_text_edge_case_boundary(self, chunked_processor):
        """Test chunking at exact boundary conditions."""
        text = "a" * 80 + ". " + "b" * 80  # Sentence break near chunk boundary
        chunks = chunked_processor.chunk_text(text)

        # Should break properly regardless of exact boundary position
        assert len(chunks) >= 1
        # Test that we get reasonable chunk sizes
        for chunk in chunks:
            assert len(chunk) > 0

    @pytest.mark.asyncio
    async def test_process_with_chunking_no_chunking_needed(
        self, chunked_processor, mock_llm_client
    ):
        """Test processing when no chunking is needed."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        items = [BatchItem(id="1", text="Short text")]  # No chunking needed
        results = await chunked_processor.process_with_chunking(
            items, "test-model", aggregate=True
        )

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_process_with_chunking_aggregation(
        self, chunked_processor, mock_llm_client
    ):
        """Test processing with chunking and aggregation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        long_text = "a" * 250  # Will be chunked
        items = [BatchItem(id="1", text=long_text)]

        with patch("numpy.mean") as mock_mean:
            mock_mean.return_value.tolist.return_value = [0.05, 0.1, 0.15]
            results = await chunked_processor.process_with_chunking(
                items, "test-model", aggregate=True
            )

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].embedding == [0.05, 0.1, 0.15]
        mock_mean.assert_called_once()  # Aggregation was performed

    @pytest.mark.asyncio
    async def test_process_with_chunking_no_aggregation(
        self, chunked_processor, mock_llm_client
    ):
        """Test processing with chunking but no aggregation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        long_text = "a" * 250  # Will be chunked
        items = [BatchItem(id="1", text=long_text)]
        results = await chunked_processor.process_with_chunking(
            items, "test-model", aggregate=False
        )

        # Should return individual chunk results
        assert len(results) > 1
        for result in results:
            assert result.id.startswith("1_chunk_")
            assert result.embedding == [0.1, 0.2, 0.3]
            assert result.metadata["parent_id"] == "1"
            assert "chunk_index" in result.metadata

    @pytest.mark.asyncio
    async def test_process_with_chunking_all_chunks_fail(
        self, chunked_processor, mock_llm_client
    ):
        """Test processing when all chunks fail."""
        mock_llm_client.embed.side_effect = Exception("All failed")

        long_text = "a" * 250  # Will be chunked
        items = [BatchItem(id="1", text=long_text)]

        # Mock asyncio.sleep to speed up retries
        with patch("asyncio.sleep", return_value=None):
            results = await chunked_processor.process_with_chunking(
                items, "test-model", aggregate=True
            )

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].embedding is None
        assert "All chunks failed" in results[0].error

    @pytest.mark.asyncio
    async def test_process_with_chunking_some_chunks_fail(
        self, chunked_processor, mock_llm_client
    ):
        """Test processing when some chunks fail."""
        # First call succeeds, second fails, third succeeds
        responses = [
            EmbeddingResponse(
                model="test-model",
                data=[{"embedding": [0.1, 0.2, 0.3]}],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            ),
            Exception("Middle chunk failed"),
            EmbeddingResponse(
                model="test-model",
                data=[{"embedding": [0.4, 0.5, 0.6]}],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            ),
        ]

        def side_effect(*args, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        mock_llm_client.embed.side_effect = side_effect

        # Create text that will generate exactly 3 chunks
        long_text = "a" * 250  # Will be chunked into multiple pieces
        items = [BatchItem(id="1", text=long_text)]

        # Mock asyncio.sleep to speed up retries
        with patch("asyncio.sleep", return_value=None):
            with patch("numpy.mean") as mock_mean:
                mock_mean.return_value.tolist.return_value = [0.25, 0.35, 0.45]
                results = await chunked_processor.process_with_chunking(
                    items, "test-model", aggregate=True
                )

        assert len(results) == 1
        assert results[0].id == "1"
        # Should still aggregate successful chunks
        assert results[0].embedding == [0.25, 0.35, 0.45]

    @pytest.mark.asyncio
    async def test_process_with_chunking_metadata_preserved(
        self, chunked_processor, mock_llm_client
    ):
        """Test that original metadata is preserved through chunking."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        original_metadata = {"scene_type": "action", "importance": "high"}
        long_text = "a" * 250
        items = [BatchItem(id="1", text=long_text, metadata=original_metadata)]

        with patch("numpy.mean") as mock_mean:
            mock_mean.return_value.tolist.return_value = [0.05, 0.1, 0.15]
            results = await chunked_processor.process_with_chunking(
                items, "test-model", aggregate=True
            )

        assert len(results) == 1
        assert results[0].metadata == original_metadata
