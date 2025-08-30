"""Embedding pipeline for preprocessing and generation."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm.client import LLMClient

from .batch_processor import BatchItem, BatchProcessor, ChunkedBatchProcessor
from .cache import EmbeddingCache, InvalidationStrategy
from .dimensions import DimensionManager

logger = get_logger(__name__)


class PreprocessingStep(Enum):
    """Available preprocessing steps."""

    LOWERCASE = "lowercase"
    REMOVE_PUNCTUATION = "remove_punctuation"
    REMOVE_EXTRA_WHITESPACE = "remove_extra_whitespace"
    NORMALIZE_UNICODE = "normalize_unicode"
    REMOVE_URLS = "remove_urls"
    REMOVE_EMAILS = "remove_emails"
    REMOVE_NUMBERS = "remove_numbers"
    TRUNCATE = "truncate"
    EXPAND_CONTRACTIONS = "expand_contractions"


@dataclass
class PipelineConfig:
    """Configuration for embedding pipeline."""

    model: str
    dimensions: int | None = None
    preprocessing_steps: list[PreprocessingStep] | None = None
    max_text_length: int = 8000
    chunk_size: int = 1000
    chunk_overlap: int = 200
    batch_size: int = 10
    use_cache: bool = True
    cache_strategy: InvalidationStrategy = InvalidationStrategy.LRU


class TextPreprocessor(ABC):
    """Abstract base class for text preprocessing."""

    @abstractmethod
    def process(self, text: str) -> str:
        """Process text.

        Args:
            text: Input text

        Returns:
            Processed text
        """
        ...


class StandardPreprocessor(TextPreprocessor):
    """Standard text preprocessor with configurable steps."""

    def __init__(
        self,
        steps: list[PreprocessingStep] | None = None,
        max_text_length: int = 8000,
    ):
        """Initialize preprocessor.

        Args:
            steps: Preprocessing steps to apply
            max_text_length: Maximum text length for truncation
        """
        self.steps = steps or [
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
            PreprocessingStep.NORMALIZE_UNICODE,
        ]
        self.max_text_length = max_text_length

    def process(self, text: str) -> str:
        """Apply preprocessing steps to text.

        Args:
            text: Input text

        Returns:
            Processed text
        """
        for step in self.steps:
            text = self._apply_step(text, step)
        return text

    def _apply_step(self, text: str, step: PreprocessingStep) -> str:
        """Apply a single preprocessing step.

        Args:
            text: Input text
            step: Step to apply

        Returns:
            Processed text
        """
        if step == PreprocessingStep.LOWERCASE:
            return text.lower()

        if step == PreprocessingStep.REMOVE_PUNCTUATION:
            import string

            return text.translate(str.maketrans("", "", string.punctuation))

        if step == PreprocessingStep.REMOVE_EXTRA_WHITESPACE:
            return " ".join(text.split())

        if step == PreprocessingStep.NORMALIZE_UNICODE:
            import unicodedata

            return unicodedata.normalize("NFKD", text)

        if step == PreprocessingStep.REMOVE_URLS:
            url_pattern = r"https?://\S+|www\.\S+"
            return re.sub(url_pattern, "", text)

        if step == PreprocessingStep.REMOVE_EMAILS:
            email_pattern = r"\S+@\S+"
            return re.sub(email_pattern, "", text)

        if step == PreprocessingStep.REMOVE_NUMBERS:
            return re.sub(r"\d+", "", text)

        if step == PreprocessingStep.EXPAND_CONTRACTIONS:
            contractions = {
                "don't": "do not",
                "won't": "will not",
                "can't": "cannot",
                "n't": " not",
                "'re": " are",
                "'ve": " have",
                "'ll": " will",
                "'d": " would",
                "'m": " am",
            }
            for contraction, expansion in contractions.items():
                text = text.replace(contraction, expansion)
            return text

        if step == PreprocessingStep.TRUNCATE:
            # Truncate to max_text_length
            if len(text) > self.max_text_length:
                return text[: self.max_text_length] + "..."
            return text

        return text


class ScreenplayPreprocessor(TextPreprocessor):
    """Specialized preprocessor for screenplay content."""

    def process(self, text: str) -> str:
        """Process screenplay text.

        Args:
            text: Input screenplay text

        Returns:
            Processed text
        """
        # Preserve screenplay formatting elements
        text = self._normalize_character_names(text)
        text = self._normalize_parentheticals(text)
        text = self._clean_transitions(text)
        return self._remove_extra_whitespace(text)

    def _normalize_character_names(self, text: str) -> str:
        """Normalize character names (typically in CAPS)."""
        # Find lines that are likely character names (all caps, possibly with spaces)
        lines = text.split("\n")
        processed = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped.isupper() and len(stripped.split()) <= 3:
                # Likely a character name
                processed.append(stripped.title())
            else:
                processed.append(line)
        return "\n".join(processed)

    def _normalize_parentheticals(self, text: str) -> str:
        """Normalize parentheticals (action descriptions)."""
        # Keep parentheticals but normalize spacing
        return re.sub(r"\s*\([^)]+\)\s*", lambda m: f" {m.group().strip()} ", text)

    def _clean_transitions(self, text: str) -> str:
        """Clean up scene transitions."""
        transitions = ["CUT TO:", "FADE IN:", "FADE OUT:", "DISSOLVE TO:"]
        for transition in transitions:
            text = text.replace(transition, f"\n{transition}\n")
        return text

    def _remove_extra_whitespace(self, text: str) -> str:
        """Remove extra whitespace while preserving structure."""
        # Remove multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing whitespace
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines)


class EmbeddingPipeline:
    """Pipeline for generating embeddings with preprocessing."""

    def __init__(
        self,
        config: PipelineConfig,
        llm_client: LLMClient | None = None,
        preprocessor: TextPreprocessor | None = None,
        cache: EmbeddingCache | None = None,
        dimension_manager: DimensionManager | None = None,
    ):
        """Initialize embedding pipeline.

        Args:
            config: Pipeline configuration
            llm_client: LLM client for generating embeddings
            preprocessor: Text preprocessor
            cache: Embedding cache
            dimension_manager: Dimension manager for validation
        """
        self.config = config
        self.llm_client = llm_client or LLMClient()

        # Initialize components
        self.preprocessor = preprocessor or StandardPreprocessor(
            config.preprocessing_steps, config.max_text_length
        )

        if config.use_cache and cache is None:
            self.cache: EmbeddingCache | None = EmbeddingCache(
                strategy=config.cache_strategy
            )
        else:
            self.cache = cache

        self.dimension_manager = dimension_manager or DimensionManager()

        # Initialize batch processor
        if config.chunk_size > 0:
            self.batch_processor: BatchProcessor = ChunkedBatchProcessor(
                self.llm_client,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                batch_size=config.batch_size,
            )
        else:
            self.batch_processor = BatchProcessor(
                self.llm_client,
                batch_size=config.batch_size,
            )

    async def generate_embedding(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Input text
            metadata: Optional metadata

        Returns:
            Embedding vector
        """
        # Preprocess text
        processed_text = self.preprocessor.process(text)

        # Truncate if needed
        if len(processed_text) > self.config.max_text_length:
            processed_text = processed_text[: self.config.max_text_length] + "..."

        # Check cache
        if self.cache and self.config.use_cache:
            cached = self.cache.get(processed_text, self.config.model)
            if cached is not None:
                return cached

        # Generate embedding
        item = BatchItem(id="single", text=processed_text, metadata=metadata)
        results = await self.batch_processor.process_batch(
            [item],
            self.config.model,
            self.config.dimensions,
        )

        if results and results[0].embedding:
            embedding = results[0].embedding

            # Validate dimensions
            expected_dim = self.dimension_manager.get_dimensions(self.config.model)
            if expected_dim and len(embedding) != expected_dim:
                logger.warning(
                    f"Dimension mismatch: expected {expected_dim}, got {len(embedding)}"
                )

            # Cache result
            if self.cache and self.config.use_cache:
                self.cache.put(processed_text, self.config.model, embedding, metadata)

            return embedding
        error = results[0].error if results else "Unknown error"
        raise ValueError(f"Failed to generate embedding: {error}")

    async def generate_batch(
        self,
        texts: list[str],
        metadata_list: list[dict[str, Any] | None] | None = None,
    ) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts
            metadata_list: Optional list of metadata dicts

        Returns:
            List of embedding vectors (None for failed items)
        """
        if metadata_list is None:
            metadata_list = [None] * len(texts)

        # Prepare batch items
        items = []
        cached_results: dict[int, list[float]] = {}

        for i, (text, metadata) in enumerate(zip(texts, metadata_list, strict=False)):
            # Preprocess
            processed_text = self.preprocessor.process(text)

            # Truncate if needed
            if len(processed_text) > self.config.max_text_length:
                processed_text = processed_text[: self.config.max_text_length] + "..."

            # Check cache
            if self.cache and self.config.use_cache:
                cached = self.cache.get(processed_text, self.config.model)
                if cached is not None:
                    cached_results[i] = cached
                    continue

            items.append(
                BatchItem(
                    id=str(i),
                    text=processed_text,
                    metadata=metadata,
                )
            )

        # Generate embeddings for non-cached items
        if items:
            results = await self.batch_processor.process_parallel(
                items,
                self.config.model,
                self.config.dimensions,
            )

            # Build result map
            result_map = {int(r.id): r for r in results}
        else:
            result_map = {}

        # Combine results
        final_results: list[list[float] | None] = []
        for i in range(len(texts)):
            if i in cached_results:
                final_results.append(cached_results[i])
            elif i in result_map:
                result = result_map[i]
                if result.embedding:
                    # Cache successful result
                    if self.cache and self.config.use_cache:
                        processed_text = self.preprocessor.process(texts[i])
                        self.cache.put(
                            processed_text,
                            self.config.model,
                            result.embedding,
                            result.metadata,
                        )
                    final_results.append(result.embedding)
                else:
                    logger.warning(
                        f"Failed to generate embedding for text {i}: {result.error}"
                    )
                    final_results.append(None)
            else:
                final_results.append(None)

        return final_results

    async def generate_for_scenes(
        self,
        scenes: list[dict[str, Any]],
    ) -> list[tuple[int, list[float] | None]]:
        """Generate embeddings for screenplay scenes.

        Args:
            scenes: List of scene dictionaries with 'id', 'heading', and 'content'

        Returns:
            List of (scene_id, embedding) tuples
        """
        # Use screenplay preprocessor
        original_preprocessor = self.preprocessor
        self.preprocessor = ScreenplayPreprocessor()

        try:
            texts = []
            scene_ids = []

            for scene in scenes:
                # Combine heading and content
                text = f"Scene: {scene['heading']}\n\n{scene['content']}"
                texts.append(text)
                scene_ids.append(scene["id"])

            # Generate embeddings
            embeddings = await self.generate_batch(texts)

            # Combine with IDs
            results = []
            for scene_id, embedding in zip(scene_ids, embeddings, strict=False):
                results.append((scene_id, embedding))

            return results

        finally:
            # Restore original preprocessor
            self.preprocessor = original_preprocessor

    def clear_cache(self) -> int:
        """Clear embedding cache.

        Returns:
            Number of entries cleared
        """
        if self.cache:
            return self.cache.clear()
        return 0

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Dictionary with pipeline stats
        """
        stats: dict[str, Any] = {
            "model": self.config.model,
            "dimensions": self.config.dimensions,
            "preprocessing_steps": [s.value for s in self.config.preprocessing_steps]
            if self.config.preprocessing_steps
            else [],
            "max_text_length": self.config.max_text_length,
            "batch_size": self.config.batch_size,
        }

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        return stats
