"""Comprehensive tests for the entire embeddings module ecosystem.

The Case of the Untested Embeddings - a complete investigation by Holmes.
Testing all six modules systematically with deductive precision.
"""

import json
import struct
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

# Import all the embedding modules under investigation
from scriptrag.embeddings.batch_processor import (
    BatchItem,
    BatchProcessor,
    BatchResult,
    ChunkedBatchProcessor,
)
from scriptrag.embeddings.cache import (
    CacheEntry,
    EmbeddingCache,
    InvalidationStrategy,
)
from scriptrag.embeddings.dimensions import (
    DimensionManager,
    EmbeddingModel,
    ModelInfo,
)
from scriptrag.embeddings.pipeline import (
    PipelineConfig,
    PreprocessingStep,
    ScreenplayPreprocessor,
    StandardPreprocessor,
)
from scriptrag.embeddings.similarity import (
    SimilarityCalculator,
    SimilarityMetric,
)
from scriptrag.embeddings.vector_store import (
    BinaryEmbeddingSerializer,
    GitLFSVectorStore,
    HybridVectorStore,
    VectorStore,
)
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingRequest, EmbeddingResponse, LLMProvider


class TestBatchProcessor:
    """The Case of the Parallel Processing Evidence."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a reliable witness - our mock LLM client."""
        client = AsyncMock(spec=LLMClient)
        client.embed = AsyncMock()
        return client

    @pytest.fixture
    def sample_embedding_response(self):
        """Create a consistent embedding response for our investigation."""
        return EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )

    @pytest.fixture
    def batch_processor(self, mock_llm_client):
        """The primary suspect - our batch processor."""
        return BatchProcessor(
            llm_client=mock_llm_client,
            batch_size=2,
            max_concurrent=1,
            retry_attempts=2,
            retry_delay=0.1,
        )

    def test_batch_item_dataclass(self):
        """Elementary test - the data structure of our evidence."""
        item = BatchItem(id="test-1", text="Test text", metadata={"source": "test"})
        assert item.id == "test-1"
        assert item.text == "Test text"
        assert item.metadata == {"source": "test"}

    def test_batch_result_dataclass(self):
        """The structure of our conclusions."""
        result = BatchResult(
            id="test-1",
            embedding=[0.1, 0.2, 0.3],
            error=None,
            metadata={"processed": True},
        )
        assert result.id == "test-1"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.error is None
        assert result.metadata == {"processed": True}

    def test_batch_processor_initialization(self, mock_llm_client):
        """The moment of creation - every parameter must be precise."""
        processor = BatchProcessor(
            llm_client=mock_llm_client,
            batch_size=5,
            max_concurrent=2,
            retry_attempts=3,
            retry_delay=0.5,
        )
        assert processor.llm_client == mock_llm_client
        assert processor.batch_size == 5
        assert processor.max_concurrent == 2
        assert processor.retry_attempts == 3
        assert processor.retry_delay == 0.5
        assert processor._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_process_batch_success(
        self, batch_processor, mock_llm_client, sample_embedding_response
    ):
        """When the evidence leads to success."""
        mock_llm_client.embed.return_value = sample_embedding_response

        items = [
            BatchItem(id="1", text="First text"),
            BatchItem(id="2", text="Second text"),
        ]

        results = await batch_processor.process_batch(items, "test-model")

        assert len(results) == 2
        assert results[0].id == "1"
        assert results[0].embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert results[0].error is None
        assert results[1].id == "2"
        assert results[1].embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert results[1].error is None

    @pytest.mark.asyncio
    async def test_process_batch_with_dimensions(
        self, batch_processor, mock_llm_client, sample_embedding_response
    ):
        """When dimensional constraints are specified."""
        mock_llm_client.embed.return_value = sample_embedding_response

        items = [BatchItem(id="1", text="Test text")]

        results = await batch_processor.process_batch(
            items, "test-model", dimensions=512
        )

        # Verify the embedding request was properly formed
        call_args = mock_llm_client.embed.call_args[0][0]
        assert isinstance(call_args, EmbeddingRequest)
        assert call_args.model == "test-model"
        assert call_args.input == "Test text"
        assert call_args.dimensions == 512

    @pytest.mark.asyncio
    async def test_process_single_with_retry_success(
        self, batch_processor, mock_llm_client, sample_embedding_response
    ):
        """The persistence of a true investigator - success after initial failure."""
        # First call fails, second succeeds
        mock_llm_client.embed.side_effect = [
            Exception("Temporary failure"),
            sample_embedding_response,
        ]

        item = BatchItem(id="test", text="Test text")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.id == "test"
        assert result.embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert result.error is None
        assert mock_llm_client.embed.call_count == 2

    @pytest.mark.asyncio
    async def test_process_single_with_retry_total_failure(
        self, batch_processor, mock_llm_client
    ):
        """When all attempts fail - the case that cannot be solved."""
        mock_llm_client.embed.side_effect = Exception("Persistent failure")

        item = BatchItem(id="test", text="Test text")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.id == "test"
        assert result.embedding is None
        assert result.error == "Persistent failure"
        assert mock_llm_client.embed.call_count == 2  # retry_attempts

    @pytest.mark.asyncio
    async def test_process_single_empty_response(
        self, batch_processor, mock_llm_client
    ):
        """When the witness provides no testimony."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[],  # Empty data
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        item = BatchItem(id="test", text="Test text")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.id == "test"
        assert result.embedding is None
        assert "No embedding in response" in result.error

    @pytest.mark.asyncio
    async def test_process_single_malformed_response(
        self, batch_processor, mock_llm_client
    ):
        """When the response lacks the crucial evidence."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"not_embedding": "wrong_key"}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        item = BatchItem(id="test", text="Test text")
        result = await batch_processor._process_single_with_retry(
            item, "test-model", None
        )

        assert result.embedding is None
        assert "No embedding in response" in result.error

    @pytest.mark.asyncio
    async def test_process_stream(
        self, batch_processor, mock_llm_client, sample_embedding_response
    ):
        """Processing evidence as it arrives - the streaming investigation."""
        mock_llm_client.embed.return_value = sample_embedding_response

        async def create_stream():
            for i in range(3):
                yield BatchItem(id=str(i), text=f"Text {i}")

        progress_calls = []

        async def progress_callback(count):
            progress_calls.append(count)

        results = []
        async for result in batch_processor.process_stream(
            create_stream(), "test-model", progress_callback=progress_callback
        ):
            results.append(result)

        assert len(results) == 3
        assert all(r.embedding == [0.1, 0.2, 0.3, 0.4, 0.5] for r in results)
        assert progress_calls == [2, 3]  # Called after batch completion

    @pytest.mark.asyncio
    async def test_process_parallel(
        self, batch_processor, mock_llm_client, sample_embedding_response
    ):
        """Parallel investigation - multiple lines of inquiry simultaneously."""
        mock_llm_client.embed.return_value = sample_embedding_response

        items = [BatchItem(id=str(i), text=f"Text {i}") for i in range(5)]

        results = await batch_processor.process_parallel(items, "test-model")

        assert len(results) == 5
        assert all(r.embedding == [0.1, 0.2, 0.3, 0.4, 0.5] for r in results)
        # Should have been split into batches based on batch_size=2

    def test_estimate_tokens(self, batch_processor):
        """Elementary token estimation - approximately 4 characters per token."""
        text = "This is a test"  # 14 characters
        tokens = batch_processor.estimate_tokens(text)
        assert tokens == 3  # 14 // 4

    def test_optimize_batch_size_token_limits(self, batch_processor):
        """Optimizing evidence processing within constraints."""
        items = [
            BatchItem(id="1", text="Short"),  # ~1 token
            BatchItem(id="2", text="A" * 100),  # ~25 tokens
            BatchItem(id="3", text="B" * 200),  # ~50 tokens
            BatchItem(id="4", text="C" * 100),  # ~25 tokens
        ]

        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=50)

        # Should intelligently group based on token count
        assert len(batches) >= 2
        # First batch should not exceed token limit
        first_batch = batches[0]
        total_tokens = sum(
            batch_processor.estimate_tokens(item.text) for item in first_batch
        )
        assert total_tokens <= 50

    def test_optimize_batch_size_max_batch_size(self, batch_processor):
        """Respecting the maximum batch size constraint."""
        items = [BatchItem(id=str(i), text="x") for i in range(10)]

        batches = batch_processor.optimize_batch_size(items, max_tokens_per_batch=1000)

        # Should respect batch_size=2 limit
        assert all(len(batch) <= 2 for batch in batches)
        assert len(batches) == 5  # 10 items / 2 per batch


class TestChunkedBatchProcessor:
    """The Case of the Subdivided Evidence - when text must be broken down."""

    @pytest.fixture
    def chunked_processor(self):
        """Our specialized investigator for large texts."""
        mock_client = AsyncMock(spec=LLMClient)
        return ChunkedBatchProcessor(
            llm_client=mock_client,
            chunk_size=20,
            chunk_overlap=5,
            batch_size=2,
        )

    def test_chunked_processor_initialization(self):
        """The specialized investigator's credentials."""
        mock_client = AsyncMock(spec=LLMClient)
        processor = ChunkedBatchProcessor(
            llm_client=mock_client,
            chunk_size=100,
            chunk_overlap=20,
            batch_size=5,
        )
        assert processor.chunk_size == 100
        assert processor.chunk_overlap == 20
        assert processor.batch_size == 5

    def test_chunk_text_short(self, chunked_processor):
        """When the evidence fits in a single piece."""
        text = "Short text"
        chunks = chunked_processor.chunk_text(text)
        assert chunks == ["Short text"]

    def test_chunk_text_long(self, chunked_processor):
        """Breaking down lengthy testimonies."""
        # Text longer than chunk_size=20
        text = "This is a very long piece of text that needs chunking"
        chunks = chunked_processor.chunk_text(text)

        assert len(chunks) > 1
        # Most chunks should respect size limits (last chunk might be shorter)
        assert all(len(chunk) <= 25 for chunk in chunks)  # Allow some flexibility
        # Should have created multiple chunks from long text
        assert len("".join(chunks)) >= len(text)

    def test_chunk_text_sentence_boundaries(self, chunked_processor):
        """Intelligent breaking at natural boundaries."""
        text = "First sentence. Second sentence here. Third one."
        chunks = chunked_processor.chunk_text(text)

        # Should try to break at sentence boundaries when possible
        if len(chunks) > 1:
            assert any("." in chunk for chunk in chunks[:-1])

    @pytest.mark.asyncio
    async def test_process_with_chunking_no_chunking_needed(self, chunked_processor):
        """When the evidence is already the right size."""
        with patch.object(
            chunked_processor, "_process_single_with_retry"
        ) as mock_process:
            mock_process.return_value = BatchResult(
                id="test", embedding=[0.1, 0.2, 0.3]
            )

            items = [BatchItem(id="test", text="Short")]
            results = await chunked_processor.process_with_chunking(items, "model")

            assert len(results) == 1
            assert results[0].embedding == [0.1, 0.2, 0.3]
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_with_chunking_aggregation(self, chunked_processor):
        """When we must piece together the chunked evidence."""
        with (
            patch.object(chunked_processor, "chunk_text") as mock_chunk,
            patch.object(chunked_processor, "process_parallel") as mock_parallel,
        ):
            mock_chunk.return_value = ["chunk1", "chunk2"]
            mock_parallel.return_value = [
                BatchResult(id="test_chunk_0", embedding=[0.1, 0.2]),
                BatchResult(id="test_chunk_1", embedding=[0.3, 0.4]),
            ]

            items = [BatchItem(id="test", text="Long text requiring chunking")]
            results = await chunked_processor.process_with_chunking(
                items, "model", aggregate=True
            )

            assert len(results) == 1
            # Should be averaged: ([0.1, 0.2] + [0.3, 0.4]) / 2 = [0.2, 0.3]
            np.testing.assert_allclose(results[0].embedding, [0.2, 0.3])

    @pytest.mark.asyncio
    async def test_process_with_chunking_no_aggregation(self, chunked_processor):
        """Keeping the evidence separate, not combining it."""
        with (
            patch.object(chunked_processor, "chunk_text") as mock_chunk,
            patch.object(chunked_processor, "process_parallel") as mock_parallel,
        ):
            mock_chunk.return_value = ["chunk1", "chunk2"]
            mock_parallel.return_value = [
                BatchResult(id="test_chunk_0", embedding=[0.1, 0.2]),
                BatchResult(id="test_chunk_1", embedding=[0.3, 0.4]),
            ]

            items = [BatchItem(id="test", text="Long text")]
            results = await chunked_processor.process_with_chunking(
                items, "model", aggregate=False
            )

            assert len(results) == 2  # Individual chunk results
            assert results[0].id == "test_chunk_0"
            assert results[1].id == "test_chunk_1"

    @pytest.mark.asyncio
    async def test_process_with_chunking_failed_chunks(self, chunked_processor):
        """When some pieces of evidence are corrupted."""
        with (
            patch.object(chunked_processor, "chunk_text") as mock_chunk,
            patch.object(chunked_processor, "process_parallel") as mock_parallel,
        ):
            mock_chunk.return_value = ["chunk1", "chunk2"]
            mock_parallel.return_value = [
                BatchResult(id="test_chunk_0", embedding=None, error="Failed"),
                BatchResult(id="test_chunk_1", embedding=[0.3, 0.4]),
            ]

            items = [BatchItem(id="test", text="Text with some failures")]
            results = await chunked_processor.process_with_chunking(
                items, "model", aggregate=True
            )

            assert len(results) == 1
            # Should only use successful chunks in aggregation
            assert results[0].embedding == [0.3, 0.4]


class TestEmbeddingCache:
    """The Case of the Memory Palace - where we store our deductions."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """A temporary storage location for our investigation."""
        return tmp_path / "test_cache"

    @pytest.fixture
    def embedding_cache(self, temp_cache_dir):
        """Our memory palace - the embedding cache."""
        return EmbeddingCache(
            cache_dir=temp_cache_dir,
            strategy=InvalidationStrategy.LRU,
            max_size=3,
            ttl_seconds=60,
        )

    def test_cache_entry_dataclass(self):
        """The structure of our stored memories."""
        entry = CacheEntry(
            key="test_key",
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
            timestamp=time.time(),
            access_count=5,
            metadata={"source": "test"},
        )
        assert entry.key == "test_key"
        assert entry.embedding == [0.1, 0.2, 0.3]
        assert entry.access_count == 5

    def test_invalidation_strategy_enum(self):
        """The various strategies for forgetting."""
        assert InvalidationStrategy.TTL.value == "ttl"
        assert InvalidationStrategy.LRU.value == "lru"
        assert InvalidationStrategy.LFU.value == "lfu"
        assert InvalidationStrategy.FIFO.value == "fifo"

    def test_cache_initialization(self, temp_cache_dir):
        """Setting up our memory palace."""
        cache = EmbeddingCache(
            cache_dir=temp_cache_dir,
            strategy=InvalidationStrategy.LFU,
            max_size=100,
            ttl_seconds=3600,
        )
        assert cache.cache_dir == temp_cache_dir
        assert cache.strategy == InvalidationStrategy.LFU
        assert cache.max_size == 100
        assert cache.ttl_seconds == 3600
        assert temp_cache_dir.exists()

    def test_cache_initialization_default_dir(self):
        """When no specific location is provided."""
        cache = EmbeddingCache()
        expected_dir = Path.home() / ".scriptrag" / "embeddings_cache"
        assert cache.cache_dir == expected_dir

    def test_get_cache_key(self, embedding_cache):
        """Generating unique identifiers for our memories."""
        key1 = embedding_cache._get_cache_key("test text", "model1")
        key2 = embedding_cache._get_cache_key("test text", "model2")
        key3 = embedding_cache._get_cache_key("different text", "model1")

        assert len(key1) == 64  # SHA256 hex length
        assert key1 != key2  # Different models
        assert key1 != key3  # Different text
        assert key2 != key3

    def test_get_cache_file(self, embedding_cache):
        """The physical location of our stored memories."""
        key = "test_key_123"
        path = embedding_cache._get_cache_file(key)

        expected = embedding_cache.cache_dir / key[:2] / f"{key}.npy"
        assert path == expected

    def test_put_and_get_success(self, embedding_cache):
        """Storing and retrieving memories successfully."""
        text = "test text"
        model = "test-model"
        embedding = [0.1, 0.2, 0.3, 0.4]

        # Store embedding
        embedding_cache.put(text, model, embedding, {"test": "metadata"})

        # Retrieve it
        retrieved = embedding_cache.get(text, model)

        assert retrieved is not None
        np.testing.assert_allclose(retrieved, embedding, rtol=1e-6)

    def test_get_cache_miss(self, embedding_cache):
        """When the memory doesn't exist."""
        result = embedding_cache.get("nonexistent text", "test-model")
        assert result is None

    def test_get_with_ttl_expiration(self, embedding_cache):
        """When memories fade with time."""
        cache = EmbeddingCache(
            cache_dir=embedding_cache.cache_dir,
            strategy=InvalidationStrategy.TTL,
            ttl_seconds=0.1,  # Very short TTL
        )

        text = "test text"
        model = "test-model"
        embedding = [0.1, 0.2, 0.3]

        cache.put(text, model, embedding)

        # Should exist immediately
        assert cache.get(text, model) is not None

        # Wait for expiration
        time.sleep(0.2)

        # Should be expired and removed
        assert cache.get(text, model) is None

    def test_invalidate(self, embedding_cache):
        """Deliberately forgetting specific memories."""
        text = "test text"
        model = "test-model"
        embedding = [0.1, 0.2, 0.3]

        embedding_cache.put(text, model, embedding)
        assert embedding_cache.get(text, model) is not None

        # Invalidate
        result = embedding_cache.invalidate(text, model)
        assert result is True

        # Should no longer exist
        assert embedding_cache.get(text, model) is None

        # Invalidating again should return False
        result = embedding_cache.invalidate(text, model)
        assert result is False

    def test_invalidate_model(self, embedding_cache):
        """Forgetting all memories associated with a particular model."""
        embedding = [0.1, 0.2, 0.3]

        # Store embeddings with different models
        embedding_cache.put("text1", "model-a", embedding)
        embedding_cache.put("text2", "model-a", embedding)
        embedding_cache.put("text3", "model-b", embedding)

        # Invalidate all entries for model-a
        count = embedding_cache.invalidate_model("model-a")
        assert count == 2

        # model-a entries should be gone
        assert embedding_cache.get("text1", "model-a") is None
        assert embedding_cache.get("text2", "model-a") is None

        # model-b entry should remain
        assert embedding_cache.get("text3", "model-b") is not None

    def test_eviction_lru(self, embedding_cache):
        """When the memory palace becomes full - LRU eviction."""
        import time

        embedding = [0.1, 0.2, 0.3]

        # Fill cache to capacity (max_size=3)
        embedding_cache.put("text1", "model", embedding)
        time.sleep(0.001)  # Ensure distinct timestamps
        embedding_cache.put("text2", "model", embedding)
        time.sleep(0.001)
        embedding_cache.put("text3", "model", embedding)
        time.sleep(0.001)

        # Access text1 to make it recently used
        embedding_cache.get("text1", "model")
        time.sleep(0.001)

        # Add one more - should evict text2 (least recently used)
        embedding_cache.put("text4", "model", embedding)

        assert embedding_cache.get("text1", "model") is not None  # Recently used
        assert embedding_cache.get("text2", "model") is None  # Evicted
        assert embedding_cache.get("text3", "model") is not None  # Still there
        assert embedding_cache.get("text4", "model") is not None  # New entry

    def test_eviction_lfu(self, temp_cache_dir):
        """Least Frequently Used eviction strategy."""
        cache = EmbeddingCache(
            cache_dir=temp_cache_dir,
            strategy=InvalidationStrategy.LFU,
            max_size=3,
        )

        embedding = [0.1, 0.2, 0.3]

        # Add entries
        cache.put("text1", "model", embedding)
        cache.put("text2", "model", embedding)
        cache.put("text3", "model", embedding)

        # Access text1 multiple times
        cache.get("text1", "model")
        cache.get("text1", "model")

        # Add one more - should evict text2 (least frequently used)
        cache.put("text4", "model", embedding)

        assert cache.get("text1", "model") is not None  # Frequently used
        assert cache.get("text2", "model") is None  # Evicted (LFU)
        assert cache.get("text3", "model") is not None
        assert cache.get("text4", "model") is not None

    def test_eviction_fifo(self, temp_cache_dir):
        """First In, First Out eviction strategy."""
        cache = EmbeddingCache(
            cache_dir=temp_cache_dir,
            strategy=InvalidationStrategy.FIFO,
            max_size=2,
        )

        embedding = [0.1, 0.2, 0.3]

        # Add entries in order
        cache.put("text1", "model", embedding)  # First
        cache.put("text2", "model", embedding)  # Second

        # Add one more - should evict text1 (first in)
        cache.put("text3", "model", embedding)

        assert cache.get("text1", "model") is None  # Evicted (first in)
        assert cache.get("text2", "model") is not None  # Still there
        assert cache.get("text3", "model") is not None  # New entry

    def test_clear(self, embedding_cache):
        """Clearing the entire memory palace."""
        embedding = [0.1, 0.2, 0.3]

        embedding_cache.put("text1", "model", embedding)
        embedding_cache.put("text2", "model", embedding)

        count = embedding_cache.clear()
        assert count == 2

        assert embedding_cache.get("text1", "model") is None
        assert embedding_cache.get("text2", "model") is None

    def test_get_stats(self, embedding_cache):
        """Analyzing our memory palace statistics."""
        embedding = [0.1, 0.2, 0.3]

        # Empty cache stats
        stats = embedding_cache.get_stats()
        assert stats["entries"] == 0
        assert stats["size_bytes"] == 0
        assert stats["models"] == []

        # Add some entries
        embedding_cache.put("text1", "model-a", embedding)
        embedding_cache.put("text2", "model-b", embedding)

        stats = embedding_cache.get_stats()
        assert stats["entries"] == 2
        assert stats["size_bytes"] > 0
        assert "model-a" in stats["models"]
        assert "model-b" in stats["models"]
        assert stats["strategy"] == "lru"

    def test_cleanup_old(self, embedding_cache):
        """Removing aged memories from the palace."""
        embedding = [0.1, 0.2, 0.3]

        # Add entry and manually adjust timestamp to be old
        embedding_cache.put("old_text", "model", embedding)
        key = embedding_cache._get_cache_key("old_text", "model")

        # Make it appear very old
        embedding_cache._index[key].timestamp = time.time() - (31 * 86400)

        count = embedding_cache.cleanup_old(max_age_days=30)
        assert count == 1

        assert embedding_cache.get("old_text", "model") is None

    def test_context_manager(self, temp_cache_dir):
        """Using the cache as a context manager."""
        embedding = [0.1, 0.2, 0.3]

        with EmbeddingCache(cache_dir=temp_cache_dir) as cache:
            cache.put("test", "model", embedding)
            result = cache.get("test", "model")
            assert result is not None

        # Index should be saved on exit
        index_file = temp_cache_dir / "index.json"
        assert index_file.exists()

    def test_load_existing_index(self, temp_cache_dir):
        """Loading memories from a previous session."""
        # Create a cache and add entry
        cache1 = EmbeddingCache(cache_dir=temp_cache_dir)
        cache1.put("test", "model", [0.1, 0.2, 0.3])
        cache1._save_index()

        # Create new cache instance - should load existing index
        cache2 = EmbeddingCache(cache_dir=temp_cache_dir)
        assert len(cache2._index) == 1

        # Should be able to retrieve the cached embedding
        result = cache2.get("test", "model")
        assert result is not None


class TestDimensionManager:
    """The Case of the Measured Evidence - ensuring proper dimensionality."""

    @pytest.fixture
    def dimension_manager(self):
        """Our dimensional expert."""
        return DimensionManager()

    def test_embedding_model_enum(self):
        """The catalog of known models and their dimensions."""
        # Test a few key models
        assert (
            EmbeddingModel.TEXT_EMBEDDING_3_SMALL.model_name == "text-embedding-3-small"
        )
        assert EmbeddingModel.TEXT_EMBEDDING_3_SMALL.dimensions == 1536

        assert (
            EmbeddingModel.TEXT_EMBEDDING_3_LARGE.model_name == "text-embedding-3-large"
        )
        assert EmbeddingModel.TEXT_EMBEDDING_3_LARGE.dimensions == 3072

    def test_model_info_dataclass(self):
        """The complete profile of a model."""
        info = ModelInfo(
            name="test-model",
            dimensions=512,
            max_tokens=8000,
            supports_truncation=True,
            supports_custom_dimensions=True,
            min_custom_dimensions=128,
            max_custom_dimensions=1024,
            metadata={"provider": "test"},
        )
        assert info.name == "test-model"
        assert info.dimensions == 512
        assert info.supports_custom_dimensions is True

    def test_dimension_manager_initialization(self, dimension_manager):
        """The expert's initial knowledge."""
        # Should have default models loaded
        assert dimension_manager.has_model("text-embedding-3-small")
        assert dimension_manager.has_model("text-embedding-ada-002")
        assert dimension_manager.get_dimensions("text-embedding-3-small") == 1536

    def test_register_model(self, dimension_manager):
        """Adding new models to our knowledge base."""
        model_info = ModelInfo(
            name="custom-model",
            dimensions=768,
            max_tokens=4000,
        )

        dimension_manager.register_model(model_info)

        assert dimension_manager.has_model("custom-model")
        assert dimension_manager.get_dimensions("custom-model") == 768

        retrieved_info = dimension_manager.get_model_info("custom-model")
        assert retrieved_info.name == "custom-model"
        assert retrieved_info.dimensions == 768

    def test_get_model_info_unknown(self, dimension_manager):
        """When we encounter an unknown model."""
        info = dimension_manager.get_model_info("unknown-model")
        assert info is None

    def test_get_dimensions_unknown(self, dimension_manager):
        """Dimension inquiry for unknown models."""
        dims = dimension_manager.get_dimensions("unknown-model")
        assert dims is None

    def test_validate_dimensions_exact_match_required(self, dimension_manager):
        """When a model requires exact dimensions."""
        # text-embedding-ada-002 doesn't support custom dimensions
        valid, error = dimension_manager.validate_dimensions(
            "text-embedding-ada-002", 1536
        )
        assert valid is True
        assert error is None

        valid, error = dimension_manager.validate_dimensions(
            "text-embedding-ada-002", 512
        )
        assert valid is False
        assert "requires exactly 1536 dimensions" in error

    def test_validate_dimensions_custom_range(self, dimension_manager):
        """When a model supports custom dimensions within a range."""
        # text-embedding-3-small supports custom dimensions
        valid, error = dimension_manager.validate_dimensions(
            "text-embedding-3-small", 512
        )
        assert valid is True
        assert error is None

        # Too small
        valid, error = dimension_manager.validate_dimensions(
            "text-embedding-3-small", 100
        )
        assert valid is False
        assert "requires at least 256 dimensions" in error

        # Too large
        valid, error = dimension_manager.validate_dimensions(
            "text-embedding-3-small", 2000
        )
        assert valid is False
        assert "supports at most 1536 dimensions" in error

    def test_validate_dimensions_unknown_model(self, dimension_manager):
        """When we can't validate an unknown model."""
        valid, error = dimension_manager.validate_dimensions("unknown-model", 512)
        assert valid is True  # Can't invalidate unknown models
        assert error is None

    def test_normalize_vector_same_dimensions(self, dimension_manager):
        """When no normalization is needed."""
        vector = [0.1, 0.2, 0.3, 0.4]
        result = dimension_manager.normalize_vector(vector, 4)
        assert result == vector

    def test_normalize_vector_padding(self, dimension_manager):
        """When we need to add dimensions."""
        vector = [0.1, 0.2]
        result = dimension_manager.normalize_vector(vector, 5)
        expected = [0.1, 0.2, 0.0, 0.0, 0.0]
        assert result == expected

    def test_normalize_vector_truncation(self, dimension_manager):
        """When we need to reduce dimensions."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = dimension_manager.normalize_vector(vector, 3)
        expected = [0.1, 0.2, 0.3]
        assert result == expected

    def test_validate_vector_valid(self, dimension_manager):
        """When the vector passes all tests."""
        vector = [0.1, 0.2, 0.3, 0.4]
        valid, error = dimension_manager.validate_vector(vector)
        assert valid is True
        assert error is None

    def test_validate_vector_empty(self, dimension_manager):
        """When there's no evidence to examine."""
        valid, error = dimension_manager.validate_vector([])
        assert valid is False
        assert error == "Empty vector"

    def test_validate_vector_non_numeric(self, dimension_manager):
        """When the evidence is contaminated."""
        vector = [0.1, "invalid", 0.3]
        valid, error = dimension_manager.validate_vector(vector)
        assert valid is False
        assert "non-numeric values" in error

    def test_validate_vector_nan_inf(self, dimension_manager):
        """When the measurements are impossible."""
        import math

        vector = [0.1, float("nan"), math.inf]
        valid, error = dimension_manager.validate_vector(vector)
        assert valid is False
        assert "NaN or Inf values" in error

    def test_validate_vector_dimension_mismatch(self, dimension_manager):
        """When the vector doesn't match the expected model dimensions."""
        vector = [0.1, 0.2, 0.3]
        valid, error = dimension_manager.validate_vector(
            vector, "text-embedding-ada-002"
        )
        assert valid is False
        assert "Dimension mismatch" in error
        assert "expected 1536, got 3" in error

    def test_get_all_models(self, dimension_manager):
        """Inventory of all known models."""
        models = dimension_manager.get_all_models()
        assert len(models) > 0

        # Should include default models
        model_names = [m.name for m in models]
        assert "text-embedding-3-small" in model_names
        assert "text-embedding-ada-002" in model_names

    def test_suggest_model(self, dimension_manager):
        """Getting recommendations based on requirements."""
        # Find a model that supports 512 dimensions
        suggestion = dimension_manager.suggest_model(target_dimensions=512)
        if suggestion:
            if suggestion.supports_custom_dimensions:
                assert (
                    suggestion.min_custom_dimensions
                    <= 512
                    <= suggestion.max_custom_dimensions
                )
            else:
                assert suggestion.dimensions == 512

    def test_suggest_model_with_token_limit(self, dimension_manager):
        """Model suggestions with token requirements."""
        suggestion = dimension_manager.suggest_model(
            target_dimensions=1536, max_tokens=8000
        )
        if suggestion and suggestion.max_tokens is not None:
            assert suggestion.max_tokens >= 8000

    def test_estimate_storage_size(self, dimension_manager):
        """Calculating storage requirements."""
        estimates = dimension_manager.estimate_storage_size(
            "text-embedding-ada-002", 1000
        )

        assert estimates["dimensions"] == 1536
        assert estimates["bytes_per_embedding"] == 1536 * 4  # float32
        assert estimates["total_bytes"] == 1536 * 4 * 1000
        assert estimates["total_mb"] > 0
        assert estimates["total_gb"] > 0

    def test_estimate_storage_size_unknown_model(self, dimension_manager):
        """Storage estimates for unknown models use defaults."""
        estimates = dimension_manager.estimate_storage_size("unknown-model", 100)

        assert estimates["dimensions"] == 1536  # Default assumption
        assert estimates["total_bytes"] == 1536 * 4 * 100


class TestSimilarityCalculator:
    """The Case of the Measured Relationships - comparing evidence."""

    @pytest.fixture
    def calculator(self):
        """Our similarity expert."""
        return SimilarityCalculator(metric=SimilarityMetric.COSINE)

    def test_similarity_metric_enum(self):
        """The various ways to measure similarity."""
        assert SimilarityMetric.COSINE.value == "cosine"
        assert SimilarityMetric.EUCLIDEAN.value == "euclidean"
        assert SimilarityMetric.DOT_PRODUCT.value == "dot_product"
        assert SimilarityMetric.MANHATTAN.value == "manhattan"

    def test_calculator_initialization(self):
        """Setting up our measurement tools."""
        calc = SimilarityCalculator(metric=SimilarityMetric.EUCLIDEAN)
        assert calc.metric == SimilarityMetric.EUCLIDEAN

    def test_calculate_cosine_similarity_identical(self, calculator):
        """When the evidence is identical."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(similarity) == 1.0

    def test_calculate_cosine_similarity_orthogonal(self, calculator):
        """When the evidence is completely different."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(similarity) == 0.0

    def test_calculate_cosine_similarity_opposite(self, calculator):
        """When the evidence is directly contradictory."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]

        similarity = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(similarity) == -1.0

    def test_calculate_euclidean_distance(self, calculator):
        """Measuring straight-line distance."""
        vec1 = [0.0, 0.0]
        vec2 = [3.0, 4.0]

        distance = calculator.calculate(vec1, vec2, SimilarityMetric.EUCLIDEAN)
        assert pytest.approx(distance) == 5.0  # 3-4-5 triangle

    def test_calculate_dot_product(self, calculator):
        """The basic dot product measurement."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]

        dot_product = calculator.calculate(vec1, vec2, SimilarityMetric.DOT_PRODUCT)
        assert pytest.approx(dot_product) == 32.0  # 1*4 + 2*5 + 3*6

    def test_calculate_manhattan_distance(self, calculator):
        """City block distance measurement."""
        vec1 = [1.0, 1.0]
        vec2 = [4.0, 5.0]

        distance = calculator.calculate(vec1, vec2, SimilarityMetric.MANHATTAN)
        assert pytest.approx(distance) == 7.0  # |1-4| + |1-5|

    def test_calculate_dimension_mismatch(self, calculator):
        """When the evidence doesn't match in size."""
        vec1 = [1.0, 2.0]
        vec2 = [3.0, 4.0, 5.0]

        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            calculator.calculate(vec1, vec2)

    def test_calculate_unsupported_metric(self, calculator):
        """When asked to use an unknown measurement."""
        vec1 = [1.0, 2.0]
        vec2 = [3.0, 4.0]

        with pytest.raises(ValueError, match="Unsupported metric"):
            calculator.calculate(vec1, vec2, "unknown_metric")

    def test_cosine_similarity_zero_vector(self, calculator):
        """When one piece of evidence has no magnitude."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]

        similarity = SimilarityCalculator.cosine_similarity(
            np.array(vec1), np.array(vec2)
        )
        assert similarity == 0.0

    def test_find_most_similar_cosine(self, calculator):
        """Finding the most related evidence."""
        query = [1.0, 0.0]
        candidates = [
            (1, [1.0, 0.0]),  # Perfect match
            (2, [0.8, 0.6]),  # Similar direction
            (3, [0.0, 1.0]),  # Orthogonal
            (4, [-1.0, 0.0]),  # Opposite
        ]

        results = calculator.find_most_similar(
            query, candidates, top_k=3, metric=SimilarityMetric.COSINE
        )

        assert len(results) == 3
        assert results[0][0] == 1  # Perfect match should be first
        assert results[0][1] == pytest.approx(1.0)
        assert results[1][0] == 2  # Similar should be second
        assert results[2][0] == 3  # Orthogonal should be third

    def test_find_most_similar_with_threshold(self, calculator):
        """Only accepting evidence above a certain threshold."""
        query = [1.0, 0.0]
        candidates = [
            (1, [1.0, 0.0]),  # similarity = 1.0
            (2, [0.0, 1.0]),  # similarity = 0.0
        ]

        results = calculator.find_most_similar(query, candidates, threshold=0.5)

        assert len(results) == 1
        assert results[0][0] == 1

    def test_find_most_similar_distance_conversion(self, calculator):
        """Converting distance metrics to similarity scores."""
        query = [0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0]),  # distance = 1.0
            (2, [2.0, 0.0]),  # distance = 2.0
        ]

        results = calculator.find_most_similar(
            query, candidates, metric=SimilarityMetric.EUCLIDEAN
        )

        # Closer point (smaller distance) should have higher similarity
        assert results[0][0] == 1
        assert results[0][1] > results[1][1]

    def test_batch_similarity_matrix(self, calculator):
        """Creating a complete similarity matrix."""
        embeddings = [
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
        ]

        matrix = calculator.batch_similarity(embeddings)

        assert matrix.shape == (3, 3)
        assert matrix[0, 0] == pytest.approx(1.0)  # Self-similarity
        assert matrix[1, 1] == pytest.approx(1.0)  # Self-similarity
        assert matrix[0, 2] == pytest.approx(1.0)  # Same vectors
        assert matrix[0, 1] == pytest.approx(0.0)  # Orthogonal

    def test_rerank_results(self, calculator):
        """Re-examining evidence with different criteria."""
        query = [1.0, 0.0]
        results = [
            (1, {"title": "First"}, [1.0, 0.0]),
            (2, {"title": "Second"}, [0.0, 1.0]),
        ]

        reranked = calculator.rerank_results(query, results, SimilarityMetric.COSINE)

        assert len(reranked) == 2
        assert reranked[0][0] == 1  # Better match should be first
        assert reranked[0][1] > reranked[1][1]
        assert reranked[0][2]["title"] == "First"

    def test_normalize_embeddings(self, calculator):
        """Converting evidence to unit vectors."""
        embeddings = [
            [3.0, 4.0],  # magnitude = 5
            [1.0, 0.0],  # magnitude = 1
            [0.0, 0.0],  # zero vector
        ]

        normalized = calculator.normalize_embeddings(embeddings)

        # First vector should be normalized
        np.testing.assert_allclose(normalized[0], [0.6, 0.8])
        # Second vector already normalized
        np.testing.assert_allclose(normalized[1], [1.0, 0.0])
        # Zero vector remains zero
        np.testing.assert_allclose(normalized[2], [0.0, 0.0])

    def test_centroid(self, calculator):
        """Finding the center point of evidence."""
        embeddings = [
            [1.0, 0.0],
            [0.0, 1.0],
            [-1.0, 0.0],
            [0.0, -1.0],
        ]

        centroid = calculator.centroid(embeddings)

        # Should be at origin
        np.testing.assert_allclose(centroid, [0.0, 0.0])

    def test_centroid_empty_list(self, calculator):
        """When there's no evidence to find the center of."""
        with pytest.raises(ValueError, match="Cannot calculate centroid of empty list"):
            calculator.centroid([])


class TestVectorStore:
    """The Case of the Evidence Warehouse - where embeddings are stored."""

    def test_binary_embedding_serializer_encode(self):
        """Converting evidence to binary format."""
        serializer = BinaryEmbeddingSerializer()
        embedding = [0.1, 0.2, 0.3, 0.4]

        encoded = serializer.encode(embedding)

        # Should start with dimension count (4 as unsigned int)
        dimension = struct.unpack("<I", encoded[:4])[0]
        assert dimension == 4

        # Should be followed by float values
        expected_size = 4 + (4 * 4)  # dimension + 4 floats
        assert len(encoded) == expected_size

    def test_binary_embedding_serializer_decode(self):
        """Converting binary evidence back to usable form."""
        serializer = BinaryEmbeddingSerializer()
        original = [0.1, 0.2, 0.3, 0.4]

        encoded = serializer.encode(original)
        decoded = serializer.decode(encoded)

        np.testing.assert_allclose(decoded, original, rtol=1e-6)

    def test_binary_embedding_serializer_decode_too_short(self):
        """When the binary evidence is corrupted - too short."""
        serializer = BinaryEmbeddingSerializer()

        with pytest.raises(ValueError, match="Embedding data too short"):
            serializer.decode(b"ab")  # Only 2 bytes

    def test_binary_embedding_serializer_decode_zero_dimension(self):
        """When the evidence claims to have no dimensions."""
        serializer = BinaryEmbeddingSerializer()
        data = struct.pack("<I", 0)  # Zero dimensions

        with pytest.raises(ValueError, match="Embedding dimension cannot be zero"):
            serializer.decode(data)

    def test_binary_embedding_serializer_decode_huge_dimension(self):
        """When the evidence claims impossible dimensions."""
        serializer = BinaryEmbeddingSerializer()
        data = struct.pack("<I", 20000)  # Way too many dimensions

        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            serializer.decode(data)

    def test_binary_embedding_serializer_decode_size_mismatch(self):
        """When the data size doesn't match the claimed dimensions."""
        serializer = BinaryEmbeddingSerializer()
        # Claim 2 dimensions but only provide data for 1
        data = struct.pack("<If", 2, 0.5)  # Claims 2 dims, only 1 float

        with pytest.raises(ValueError, match="size mismatch"):
            serializer.decode(data)


class TestGitLFSVectorStore:
    """The Case of the Git-Tracked Evidence Storage."""

    @pytest.fixture
    def lfs_store(self, tmp_path):
        """Our Git LFS storage facility."""
        return GitLFSVectorStore(lfs_dir=tmp_path / "embeddings")

    def test_lfs_store_initialization(self, tmp_path):
        """Setting up the evidence storage facility."""
        lfs_dir = tmp_path / "test_lfs"
        store = GitLFSVectorStore(lfs_dir=lfs_dir)

        assert store.lfs_dir == lfs_dir
        assert lfs_dir.exists()

        # Should create .gitattributes
        gitattributes = lfs_dir / ".gitattributes"
        assert gitattributes.exists()
        content = gitattributes.read_text()
        assert "*.npy filter=lfs diff=lfs merge=lfs -text" in content

    def test_lfs_store_default_dir(self):
        """When no specific storage location is provided."""
        store = GitLFSVectorStore()
        assert store.lfs_dir == Path(".embeddings")

    def test_get_path(self, lfs_store):
        """Determining where evidence should be stored."""
        path = lfs_store._get_path("scene", 123, "test-model")
        expected = lfs_store.lfs_dir / "test-model" / "scene" / "123.npy"
        assert path == expected

    def test_get_path_model_with_slash(self, lfs_store):
        """When the model name contains forward slashes."""
        path = lfs_store._get_path("scene", 123, "provider/model")
        expected = lfs_store.lfs_dir / "provider_model" / "scene" / "123.npy"
        assert path == expected

    def test_get_embedding_path_public(self, lfs_store):
        """The public interface for path determination."""
        path = lfs_store.get_embedding_path("scene", 456, "model")
        expected = lfs_store._get_path("scene", 456, "model")
        assert path == expected

    def test_store_and_retrieve(self, lfs_store):
        """Storing and retrieving evidence successfully."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        metadata = {"source": "test"}

        # Store
        lfs_store.store("scene", 123, embedding, "test-model", metadata)

        # Retrieve
        retrieved = lfs_store.retrieve("scene", 123, "test-model")

        assert retrieved is not None
        np.testing.assert_allclose(retrieved, embedding, rtol=1e-6)

        # Check metadata was stored
        path = lfs_store._get_path("scene", 123, "test-model")
        meta_path = path.with_suffix(".json")
        assert meta_path.exists()
        stored_metadata = json.loads(meta_path.read_text())
        assert stored_metadata == metadata

    def test_store_without_metadata(self, lfs_store):
        """Storing evidence without additional information."""
        embedding = [0.1, 0.2, 0.3]

        lfs_store.store("scene", 456, embedding, "test-model")

        retrieved = lfs_store.retrieve("scene", 456, "test-model")
        assert retrieved is not None

        # No metadata file should exist
        path = lfs_store._get_path("scene", 456, "test-model")
        meta_path = path.with_suffix(".json")
        assert not meta_path.exists()

    def test_retrieve_nonexistent(self, lfs_store):
        """When the requested evidence doesn't exist."""
        result = lfs_store.retrieve("scene", 999, "nonexistent-model")
        assert result is None

    def test_retrieve_corrupted_file(self, lfs_store, tmp_path):
        """When the stored evidence is corrupted."""
        # Create a corrupted file
        path = lfs_store._get_path("scene", 123, "test-model")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("corrupted")  # Not a valid numpy file

        result = lfs_store.retrieve("scene", 123, "test-model")
        assert result is None

    def test_search_not_supported(self, lfs_store):
        """LFS storage doesn't support similarity search."""
        with pytest.raises(
            NotImplementedError, match="does not support similarity search"
        ):
            lfs_store.search([0.1, 0.2], "scene", "model")

    def test_delete_specific_model(self, lfs_store):
        """Removing evidence for a specific model."""
        embedding = [0.1, 0.2, 0.3]

        # Store with metadata
        lfs_store.store("scene", 123, embedding, "model1", {"test": "data"})
        lfs_store.store("scene", 123, embedding, "model2")

        # Delete specific model
        deleted = lfs_store.delete("scene", 123, "model1")
        assert deleted is True

        # model1 should be gone, including metadata
        assert lfs_store.retrieve("scene", 123, "model1") is None
        path1 = lfs_store._get_path("scene", 123, "model1")
        meta_path1 = path1.with_suffix(".json")
        assert not meta_path1.exists()

        # model2 should still exist
        assert lfs_store.retrieve("scene", 123, "model2") is not None

    def test_delete_all_models(self, lfs_store):
        """Removing all evidence for an entity."""
        embedding = [0.1, 0.2, 0.3]

        lfs_store.store("scene", 123, embedding, "model1")
        lfs_store.store("scene", 123, embedding, "model2")

        # Delete all models for this entity
        deleted = lfs_store.delete("scene", 123)
        assert deleted is True

        # Both should be gone
        assert lfs_store.retrieve("scene", 123, "model1") is None
        assert lfs_store.retrieve("scene", 123, "model2") is None

    def test_delete_nonexistent(self, lfs_store):
        """Attempting to remove evidence that doesn't exist."""
        deleted = lfs_store.delete("scene", 999, "nonexistent-model")
        assert deleted is False

    def test_exists(self, lfs_store):
        """Checking for the presence of evidence."""
        embedding = [0.1, 0.2, 0.3]

        # Shouldn't exist initially
        assert lfs_store.exists("scene", 123, "test-model") is False

        # Store it
        lfs_store.store("scene", 123, embedding, "test-model")

        # Should exist now
        assert lfs_store.exists("scene", 123, "test-model") is True


class TestHybridVectorStore:
    """The Case of the Dual Storage System - primary and backup evidence."""

    @pytest.fixture
    def mock_primary(self):
        """Our primary storage system."""
        return Mock(spec=VectorStore)

    @pytest.fixture
    def mock_secondary(self):
        """Our backup storage system."""
        return Mock(spec=VectorStore)

    @pytest.fixture
    def hybrid_store(self, mock_primary, mock_secondary):
        """The dual storage investigator."""
        return HybridVectorStore(primary=mock_primary, secondary=mock_secondary)

    def test_hybrid_store_initialization(self, mock_primary, mock_secondary):
        """Setting up the dual storage system."""
        store = HybridVectorStore(primary=mock_primary, secondary=mock_secondary)
        assert store.primary == mock_primary
        assert store.secondary == mock_secondary

    def test_hybrid_store_no_secondary(self, mock_primary):
        """When there's only primary storage."""
        store = HybridVectorStore(primary=mock_primary)
        assert store.primary == mock_primary
        assert store.secondary is None

    def test_store_both_systems(self, hybrid_store, mock_primary, mock_secondary):
        """Storing evidence in both systems."""
        embedding = [0.1, 0.2, 0.3]
        metadata = {"test": "data"}

        hybrid_store.store("scene", 123, embedding, "model", metadata)

        # Both systems should be called
        mock_primary.store.assert_called_once_with(
            "scene", 123, embedding, "model", metadata
        )
        mock_secondary.store.assert_called_once_with(
            "scene", 123, embedding, "model", metadata
        )

    def test_store_secondary_failure(self, hybrid_store, mock_primary, mock_secondary):
        """When secondary storage fails, primary should still work."""
        mock_secondary.store.side_effect = Exception("Secondary failed")

        embedding = [0.1, 0.2, 0.3]

        # Should not raise exception
        hybrid_store.store("scene", 123, embedding, "model")

        # Primary should still be called
        mock_primary.store.assert_called_once()

    def test_retrieve_from_primary(self, hybrid_store, mock_primary, mock_secondary):
        """When evidence is available in primary storage."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_primary.retrieve.return_value = expected_embedding

        result = hybrid_store.retrieve("scene", 123, "model")

        assert result == expected_embedding
        mock_primary.retrieve.assert_called_once_with("scene", 123, "model")
        mock_secondary.retrieve.assert_not_called()

    def test_retrieve_from_secondary(self, hybrid_store, mock_primary, mock_secondary):
        """When evidence is only in secondary storage."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_primary.retrieve.return_value = None
        mock_secondary.retrieve.return_value = expected_embedding

        result = hybrid_store.retrieve("scene", 123, "model")

        assert result == expected_embedding
        mock_secondary.retrieve.assert_called_once_with("scene", 123, "model")

        # Should restore to primary
        mock_primary.store.assert_called_once_with(
            "scene", 123, expected_embedding, "model"
        )

    def test_retrieve_restore_failure(self, hybrid_store, mock_primary, mock_secondary):
        """When restoration to primary fails."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_primary.retrieve.return_value = None
        mock_primary.store.side_effect = Exception("Restore failed")
        mock_secondary.retrieve.return_value = expected_embedding

        result = hybrid_store.retrieve("scene", 123, "model")

        # Should still return the embedding despite restore failure
        assert result == expected_embedding

    def test_retrieve_not_found(self, hybrid_store, mock_primary, mock_secondary):
        """When evidence is not in either storage system."""
        mock_primary.retrieve.return_value = None
        mock_secondary.retrieve.return_value = None

        result = hybrid_store.retrieve("scene", 123, "model")

        assert result is None

    def test_search_primary_only(self, hybrid_store, mock_primary):
        """Searching uses only the primary system."""
        expected_results = [(123, 0.95, {"meta": "data"})]
        mock_primary.search.return_value = expected_results

        query = [0.1, 0.2, 0.3]
        results = hybrid_store.search(query, "scene", "model", limit=5)

        assert results == expected_results
        mock_primary.search.assert_called_once_with(
            query, "scene", "model", 5, None, None
        )

    def test_delete_both_systems(self, hybrid_store, mock_primary, mock_secondary):
        """Removing evidence from both storage systems."""
        mock_primary.delete.return_value = True
        mock_secondary.delete.return_value = False

        result = hybrid_store.delete("scene", 123, "model")

        assert result is True  # True if either succeeds
        mock_primary.delete.assert_called_once_with("scene", 123, "model")
        mock_secondary.delete.assert_called_once_with("scene", 123, "model")

    def test_delete_secondary_failure(self, hybrid_store, mock_primary, mock_secondary):
        """When secondary deletion fails."""
        mock_primary.delete.return_value = True
        mock_secondary.delete.side_effect = Exception("Delete failed")

        result = hybrid_store.delete("scene", 123, "model")

        # Should still return True from primary
        assert result is True

    def test_exists_in_primary(self, hybrid_store, mock_primary, mock_secondary):
        """When evidence exists in primary storage."""
        mock_primary.exists.return_value = True

        result = hybrid_store.exists("scene", 123, "model")

        assert result is True
        mock_primary.exists.assert_called_once_with("scene", 123, "model")
        mock_secondary.exists.assert_not_called()

    def test_exists_in_secondary_only(self, hybrid_store, mock_primary, mock_secondary):
        """When evidence exists only in secondary storage."""
        mock_primary.exists.return_value = False
        mock_secondary.exists.return_value = True

        result = hybrid_store.exists("scene", 123, "model")

        assert result is True
        mock_secondary.exists.assert_called_once_with("scene", 123, "model")


class TestStandardPreprocessor:
    """The Case of the Text Cleaning - preparing evidence for analysis."""

    def test_preprocessing_step_enum(self):
        """The catalog of text cleaning operations."""
        assert PreprocessingStep.LOWERCASE.value == "lowercase"
        assert PreprocessingStep.REMOVE_PUNCTUATION.value == "remove_punctuation"
        assert (
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE.value == "remove_extra_whitespace"
        )

    def test_standard_preprocessor_default_steps(self):
        """The default cleaning procedures."""
        preprocessor = StandardPreprocessor()
        expected_steps = [
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
            PreprocessingStep.NORMALIZE_UNICODE,
        ]
        assert preprocessor.steps == expected_steps

    def test_standard_preprocessor_custom_steps(self):
        """Using specific cleaning procedures."""
        steps = [PreprocessingStep.LOWERCASE, PreprocessingStep.REMOVE_PUNCTUATION]
        preprocessor = StandardPreprocessor(steps)
        assert preprocessor.steps == steps

    def test_apply_lowercase(self):
        """Converting evidence to lowercase."""
        preprocessor = StandardPreprocessor([PreprocessingStep.LOWERCASE])
        result = preprocessor.process("UPPERCASE Text")
        assert result == "uppercase text"

    def test_apply_remove_punctuation(self):
        """Removing punctuation from evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.REMOVE_PUNCTUATION])
        result = preprocessor.process("Hello, world! How are you?")
        assert result == "Hello world How are you"

    def test_apply_remove_extra_whitespace(self):
        """Normalizing whitespace in evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.REMOVE_EXTRA_WHITESPACE])
        result = preprocessor.process("Too   much    space\n\nbetween   words")
        assert result == "Too much space between words"

    def test_apply_normalize_unicode(self):
        """Normalizing Unicode characters."""
        preprocessor = StandardPreprocessor([PreprocessingStep.NORMALIZE_UNICODE])
        # Using a character with an accent
        result = preprocessor.process("café")
        # NFKD normalization should decompose the accented character
        assert len(result) >= len("café")

    def test_apply_remove_urls(self):
        """Removing URLs from evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.REMOVE_URLS])
        text = "Visit https://example.com and www.test.org for more info"
        result = preprocessor.process(text)
        assert "https://example.com" not in result
        assert "www.test.org" not in result
        assert result == "Visit  and  for more info"

    def test_apply_remove_emails(self):
        """Removing email addresses from evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.REMOVE_EMAILS])
        text = "Contact us at test@example.com or support@company.org"
        result = preprocessor.process(text)
        assert "test@example.com" not in result
        assert "support@company.org" not in result

    def test_apply_remove_numbers(self):
        """Removing numbers from evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.REMOVE_NUMBERS])
        result = preprocessor.process("I have 123 apples and 45 oranges")
        assert result == "I have  apples and  oranges"

    def test_apply_expand_contractions(self):
        """Expanding contractions in evidence."""
        preprocessor = StandardPreprocessor([PreprocessingStep.EXPAND_CONTRACTIONS])
        result = preprocessor.process("Don't you think we can't do this?")
        assert result == "Do not you think we cannot do this?"

    def test_multiple_steps_chained(self):
        """Applying multiple cleaning procedures in sequence."""
        steps = [
            PreprocessingStep.LOWERCASE,
            PreprocessingStep.REMOVE_PUNCTUATION,
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
        ]
        preprocessor = StandardPreprocessor(steps)
        result = preprocessor.process("HELLO,  WORLD!!!   How  are   you?")
        assert result == "hello world how are you"


class TestScreenplayPreprocessor:
    """The Case of the Screenplay Formatting - specialized text handling."""

    @pytest.fixture
    def screenplay_preprocessor(self):
        """Our screenplay specialist."""
        return ScreenplayPreprocessor()

    def test_normalize_character_names(self, screenplay_preprocessor):
        """Converting character names to proper format."""
        text = """JOHN
Hello there.

MARY JANE
How are you?

Some regular text here."""

        result = screenplay_preprocessor._normalize_character_names(text)

        # Character names should be converted from ALL CAPS to Title Case
        assert "John" in result
        assert "Mary Jane" in result
        assert "JOHN" not in result
        assert "MARY JANE" not in result
        # Regular text should remain unchanged
        assert "Some regular text here." in result

    def test_normalize_parentheticals(self, screenplay_preprocessor):
        """Cleaning up action descriptions in parentheses."""
        text = "She speaks(loudly)about her day."
        result = screenplay_preprocessor._normalize_parentheticals(text)
        assert result == "She speaks (loudly) about her day."

    def test_clean_transitions(self, screenplay_preprocessor):
        """Formatting scene transitions properly."""
        text = "The scene continues.CUT TO:The next scene begins."
        result = screenplay_preprocessor._clean_transitions(text)
        assert "\nCUT TO:\n" in result

    def test_remove_extra_whitespace_preserving_structure(
        self, screenplay_preprocessor
    ):
        """Removing excess whitespace while keeping screenplay structure."""
        text = """Scene heading


Too many blank lines



Character speaking  """

        result = screenplay_preprocessor._remove_extra_whitespace(text)

        # Should reduce multiple blank lines but preserve some structure
        assert "Scene heading\n\nToo many blank lines\n\nCharacter speaking" in result

    def test_complete_screenplay_processing(self, screenplay_preprocessor):
        """Testing the complete screenplay preprocessing pipeline."""
        screenplay_text = """INT. COFFEE SHOP - DAY

SARAH
(nervous)
One coffee, please.

BARISTA
Coming right up!CUT TO:The next scene."""

        result = screenplay_preprocessor.process(screenplay_text)

        # Should have proper character name formatting
        assert "Sarah" in result
        assert "Barista" in result
        # Should have proper parenthetical formatting
        assert " (nervous) " in result
        # Should have proper transition formatting
        assert "\nCUT TO:\n" in result


class TestPipelineConfig:
    """The Case of the Configuration Evidence."""

    def test_pipeline_config_dataclass(self):
        """The structure of our pipeline configuration."""
        config = PipelineConfig(
            model="test-model",
            dimensions=512,
            preprocessing_steps=[PreprocessingStep.LOWERCASE],
            max_text_length=4000,
            chunk_size=500,
            chunk_overlap=100,
            batch_size=5,
            use_cache=False,
            cache_strategy=InvalidationStrategy.FIFO,
        )

        assert config.model == "test-model"
        assert config.dimensions == 512
        assert config.preprocessing_steps == [PreprocessingStep.LOWERCASE]
        assert config.max_text_length == 4000
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100
        assert config.batch_size == 5
        assert config.use_cache is False
        assert config.cache_strategy == InvalidationStrategy.FIFO

    def test_pipeline_config_defaults(self):
        """The default configuration values."""
        config = PipelineConfig(model="test-model")

        assert config.model == "test-model"
        assert config.dimensions is None
        assert config.preprocessing_steps is None
        assert config.max_text_length == 8000
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.batch_size == 10
        assert config.use_cache is True
        assert config.cache_strategy == InvalidationStrategy.LRU
