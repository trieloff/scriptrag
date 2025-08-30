"""Batch processing utilities for efficient embedding generation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from scriptrag.config import get_logger
from scriptrag.exceptions import EmbeddingResponseError
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingRequest

logger = get_logger(__name__)


@dataclass
class BatchItem:
    """Item in a batch processing queue."""

    id: str
    text: str
    metadata: dict[str, Any] | None = None


@dataclass
class BatchResult:
    """Result from batch processing."""

    id: str
    embedding: list[float] | None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BatchProcessor:
    """Batch processor for efficient embedding generation."""

    def __init__(
        self,
        llm_client: LLMClient,
        batch_size: int = 10,
        max_concurrent: int = 3,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize batch processor.

        Args:
            llm_client: LLM client for generating embeddings
            batch_size: Number of items per batch
            max_concurrent: Maximum concurrent batch requests
            retry_attempts: Number of retry attempts for failed items
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.llm_client = llm_client
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(
        self,
        items: list[BatchItem],
        model: str,
        dimensions: int | None = None,
    ) -> list[BatchResult]:
        """Process a batch of items.

        Args:
            items: Items to process
            model: Embedding model to use
            dimensions: Optional embedding dimensions

        Returns:
            List of batch results
        """
        results = []

        async with self._semaphore:
            for item in items:
                result = await self._process_single_with_retry(item, model, dimensions)
                results.append(result)

        return results

    async def _process_single_with_retry(
        self,
        item: BatchItem,
        model: str,
        dimensions: int | None,
    ) -> BatchResult:
        """Process a single item with retry logic.

        Args:
            item: Item to process
            model: Embedding model to use
            dimensions: Optional embedding dimensions

        Returns:
            Batch result
        """
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                # Generate embedding
                request = EmbeddingRequest(
                    model=model,
                    input=item.text,
                    dimensions=dimensions,
                )

                response = await self.llm_client.embed(request)

                if response.data and response.data[0].get("embedding"):
                    embedding = response.data[0]["embedding"]
                    return BatchResult(
                        id=item.id,
                        embedding=list(embedding),
                        metadata=item.metadata,
                    )
                raise EmbeddingResponseError(
                    message="No embedding in response",
                    hint="Check that the LLM provider supports embeddings",
                    details={"model": model, "item_id": item.id},
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self.retry_attempts,
                    item.id,
                    e,
                )

                # Exponential backoff
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        # All attempts failed
        return BatchResult(
            id=item.id,
            embedding=None,
            error=last_error,
            metadata=item.metadata,
        )

    async def process_stream(
        self,
        items: AsyncIterator[BatchItem],
        model: str,
        dimensions: int | None = None,
        progress_callback: Any | None = None,
    ) -> AsyncIterator[BatchResult]:
        """Process items from an async stream.

        Args:
            items: Async iterator of items
            model: Embedding model to use
            dimensions: Optional embedding dimensions
            progress_callback: Optional callback for progress updates

        Yields:
            Batch results as they complete
        """
        batch: list[BatchItem] = []
        total_processed = 0

        async for item in items:
            batch.append(item)

            if len(batch) >= self.batch_size:
                # Process full batch
                results = await self.process_batch(batch, model, dimensions)
                for result in results:
                    yield result
                    total_processed += 1

                if progress_callback:
                    await progress_callback(total_processed)

                batch = []

        # Process remaining items
        if batch:
            results = await self.process_batch(batch, model, dimensions)
            for result in results:
                yield result
                total_processed += 1

            if progress_callback:
                await progress_callback(total_processed)

    async def process_parallel(
        self,
        items: list[BatchItem],
        model: str,
        dimensions: int | None = None,
    ) -> list[BatchResult]:
        """Process items in parallel batches.

        Args:
            items: Items to process
            model: Embedding model to use
            dimensions: Optional embedding dimensions

        Returns:
            List of all batch results
        """
        # Split into batches
        batches = [
            items[i : i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        # Process batches in parallel
        tasks = [self.process_batch(batch, model, dimensions) for batch in batches]

        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        results = []
        for batch_result in batch_results:
            results.extend(batch_result)

        return results

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    def optimize_batch_size(
        self,
        items: list[BatchItem],
        max_tokens_per_batch: int = 8000,
    ) -> list[list[BatchItem]]:
        """Optimize batch sizes based on token limits.

        Args:
            items: Items to batch
            max_tokens_per_batch: Maximum tokens per batch

        Returns:
            List of optimized batches
        """
        batches = []
        current_batch: list[BatchItem] = []
        current_tokens = 0

        for item in items:
            item_tokens = self.estimate_tokens(item.text)

            # Check if adding this item would exceed limit
            if current_tokens + item_tokens > max_tokens_per_batch and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(item)
            current_tokens += item_tokens

            # Also respect max batch size
            if len(current_batch) >= self.batch_size:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

        # Add remaining items
        if current_batch:
            batches.append(current_batch)

        return batches


class ChunkedBatchProcessor(BatchProcessor):
    """Batch processor with text chunking support."""

    def __init__(
        self,
        llm_client: LLMClient,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs: Any,
    ):
        """Initialize chunked batch processor.

        Args:
            llm_client: LLM client for generating embeddings
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
            **kwargs: Additional arguments for BatchProcessor
        """
        super().__init__(llm_client, **kwargs)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end
                for sep in [".", "!", "?", "\n\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + self.chunk_size // 2:
                        end = last_sep + 1
                        break

            chunks.append(text[start:end])

            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break

        return chunks

    async def process_with_chunking(
        self,
        items: list[BatchItem],
        model: str,
        dimensions: int | None = None,
        aggregate: bool = True,
    ) -> list[BatchResult]:
        """Process items with automatic text chunking.

        Args:
            items: Items to process
            model: Embedding model to use
            dimensions: Optional embedding dimensions
            aggregate: Whether to aggregate chunk embeddings

        Returns:
            List of batch results
        """
        results = []

        for item in items:
            chunks = self.chunk_text(item.text)

            if len(chunks) == 1:
                # No chunking needed
                result = await self._process_single_with_retry(item, model, dimensions)
                results.append(result)
            else:
                # Process chunks
                chunk_items = [
                    BatchItem(
                        id=f"{item.id}_chunk_{i}",
                        text=chunk,
                        metadata={"parent_id": item.id, "chunk_index": i},
                    )
                    for i, chunk in enumerate(chunks)
                ]

                chunk_results = await self.process_parallel(
                    chunk_items, model, dimensions
                )

                if aggregate:
                    # Aggregate chunk embeddings
                    embeddings = [
                        r.embedding for r in chunk_results if r.embedding is not None
                    ]

                    if embeddings:
                        # Average pooling
                        import numpy as np

                        avg_embedding = np.mean(embeddings, axis=0).tolist()
                        results.append(
                            BatchResult(
                                id=item.id,
                                embedding=avg_embedding,
                                metadata=item.metadata,
                            )
                        )
                    else:
                        # All chunks failed
                        results.append(
                            BatchResult(
                                id=item.id,
                                embedding=None,
                                error="All chunks failed to generate embeddings",
                                metadata=item.metadata,
                            )
                        )
                else:
                    # Return individual chunk results
                    results.extend(chunk_results)

        return results
