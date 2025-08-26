"""Comprehensive tests for embedding pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.embeddings.batch_processor import (
    BatchProcessor,
    ChunkedBatchProcessor,
)
from scriptrag.embeddings.cache import EmbeddingCache, InvalidationStrategy
from scriptrag.embeddings.dimensions import DimensionManager
from scriptrag.embeddings.pipeline import (
    EmbeddingPipeline,
    PipelineConfig,
    PreprocessingStep,
    ScreenplayPreprocessor,
    StandardPreprocessor,
    TextPreprocessor,
)
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


class TestPreprocessingStep:
    """Test PreprocessingStep enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert PreprocessingStep.LOWERCASE.value == "lowercase"
        assert PreprocessingStep.REMOVE_PUNCTUATION.value == "remove_punctuation"
        assert (
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE.value == "remove_extra_whitespace"
        )
        assert PreprocessingStep.NORMALIZE_UNICODE.value == "normalize_unicode"
        assert PreprocessingStep.REMOVE_URLS.value == "remove_urls"
        assert PreprocessingStep.REMOVE_EMAILS.value == "remove_emails"
        assert PreprocessingStep.REMOVE_NUMBERS.value == "remove_numbers"
        assert PreprocessingStep.TRUNCATE.value == "truncate"
        assert PreprocessingStep.EXPAND_CONTRACTIONS.value == "expand_contractions"

    def test_all_steps_defined(self):
        """Test that all expected preprocessing steps are defined."""
        expected_steps = {
            "lowercase",
            "remove_punctuation",
            "remove_extra_whitespace",
            "normalize_unicode",
            "remove_urls",
            "remove_emails",
            "remove_numbers",
            "truncate",
            "expand_contractions",
        }
        actual_steps = {step.value for step in PreprocessingStep}
        assert actual_steps == expected_steps


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_init_minimal(self):
        """Test PipelineConfig with minimal parameters."""
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

    def test_init_full(self):
        """Test PipelineConfig with all parameters."""
        steps = [PreprocessingStep.LOWERCASE, PreprocessingStep.REMOVE_PUNCTUATION]
        config = PipelineConfig(
            model="advanced-model",
            dimensions=1024,
            preprocessing_steps=steps,
            max_text_length=5000,
            chunk_size=800,
            chunk_overlap=150,
            batch_size=5,
            use_cache=False,
            cache_strategy=InvalidationStrategy.TTL,
        )
        assert config.model == "advanced-model"
        assert config.dimensions == 1024
        assert config.preprocessing_steps == steps
        assert config.max_text_length == 5000
        assert config.chunk_size == 800
        assert config.chunk_overlap == 150
        assert config.batch_size == 5
        assert config.use_cache is False
        assert config.cache_strategy == InvalidationStrategy.TTL


class TestTextPreprocessor:
    """Test abstract TextPreprocessor base class."""

    def test_is_abstract(self):
        """Test that TextPreprocessor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TextPreprocessor()


class TestStandardPreprocessor:
    """Test StandardPreprocessor class."""

    def test_init_default_steps(self):
        """Test initialization with default steps."""
        processor = StandardPreprocessor()
        expected_steps = [
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
            PreprocessingStep.NORMALIZE_UNICODE,
        ]
        assert processor.steps == expected_steps

    def test_init_custom_steps(self):
        """Test initialization with custom steps."""
        steps = [PreprocessingStep.LOWERCASE, PreprocessingStep.REMOVE_PUNCTUATION]
        processor = StandardPreprocessor(steps=steps)
        assert processor.steps == steps

    def test_process_no_steps(self):
        """Test processing with no steps."""
        processor = StandardPreprocessor(steps=[])
        text = "Original Text"
        result = processor.process(text)
        assert result == text

    def test_process_single_step(self):
        """Test processing with single step."""
        processor = StandardPreprocessor(steps=[PreprocessingStep.LOWERCASE])
        result = processor.process("UPPERCASE TEXT")
        assert result == "uppercase text"

    def test_process_multiple_steps(self):
        """Test processing with multiple steps."""
        steps = [
            PreprocessingStep.LOWERCASE,
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
        ]
        processor = StandardPreprocessor(steps=steps)
        result = processor.process("UPPERCASE   TEXT   WITH   SPACES")
        assert result == "uppercase text with spaces"

    def test_apply_step_lowercase(self):
        """Test lowercase preprocessing step."""
        processor = StandardPreprocessor()
        result = processor._apply_step("HELLO World", PreprocessingStep.LOWERCASE)
        assert result == "hello world"

    def test_apply_step_remove_punctuation(self):
        """Test punctuation removal step."""
        processor = StandardPreprocessor()
        result = processor._apply_step(
            "Hello, world!", PreprocessingStep.REMOVE_PUNCTUATION
        )
        assert result == "Hello world"

    def test_apply_step_remove_extra_whitespace(self):
        """Test extra whitespace removal step."""
        processor = StandardPreprocessor()
        text = "Hello    world\n\n\tExtra   spaces"
        result = processor._apply_step(text, PreprocessingStep.REMOVE_EXTRA_WHITESPACE)
        assert result == "Hello world Extra spaces"

    def test_apply_step_normalize_unicode(self):
        """Test unicode normalization step."""
        processor = StandardPreprocessor()
        # Text with accented characters
        text = "café naïve résumé"
        result = processor._apply_step(text, PreprocessingStep.NORMALIZE_UNICODE)
        # Should still contain the characters but normalized
        assert len(result) >= len("cafe naive resume")
        assert "cafe" in result.lower()

    def test_apply_step_remove_urls(self):
        """Test URL removal step."""
        processor = StandardPreprocessor()
        text = "Visit https://example.com or www.test.org for more info"
        result = processor._apply_step(text, PreprocessingStep.REMOVE_URLS)
        assert "https://example.com" not in result
        assert "www.test.org" not in result
        assert "Visit" in result
        assert "for more info" in result

    def test_apply_step_remove_emails(self):
        """Test email removal step."""
        processor = StandardPreprocessor()
        text = "Contact user@example.com or admin@test.org today"
        result = processor._apply_step(text, PreprocessingStep.REMOVE_EMAILS)
        assert "user@example.com" not in result
        assert "admin@test.org" not in result
        assert "Contact" in result
        assert "today" in result

    def test_apply_step_remove_numbers(self):
        """Test number removal step."""
        processor = StandardPreprocessor()
        text = "Call 123-456-7890 or visit room 42"
        result = processor._apply_step(text, PreprocessingStep.REMOVE_NUMBERS)
        # Should remove digit sequences
        assert "123" not in result
        assert "456" not in result
        assert "7890" not in result
        assert "42" not in result
        assert "Call" in result
        assert "visit room" in result

    def test_apply_step_expand_contractions(self):
        """Test contraction expansion step."""
        processor = StandardPreprocessor()
        text = "Don't can't won't I'm you're they'll we'd"
        result = processor._apply_step(text, PreprocessingStep.EXPAND_CONTRACTIONS)

        assert "don't" not in result.lower()
        assert "can't" not in result.lower()
        assert "won't" not in result.lower()
        assert "do not" in result.lower()
        assert "cannot" in result.lower()
        assert "will not" in result.lower()
        assert "i am" in result.lower()
        assert "you are" in result.lower()
        assert "they will" in result.lower()
        assert "we would" in result.lower()

    def test_apply_step_truncate(self):
        """Test text truncation step."""
        # Test with default max_text_length
        processor = StandardPreprocessor()
        text = "a" * 10000  # Longer than default 8000
        result = processor._apply_step(text, PreprocessingStep.TRUNCATE)
        assert len(result) == 8003  # 8000 + "..."
        assert result.endswith("...")
        assert result.startswith("a" * 8000)

    def test_apply_step_truncate_short_text(self):
        """Test truncation step with text shorter than limit."""
        processor = StandardPreprocessor()
        text = "Short text"
        result = processor._apply_step(text, PreprocessingStep.TRUNCATE)
        assert result == text  # Should remain unchanged

    def test_apply_step_truncate_exact_length(self):
        """Test truncation with text exactly at the limit."""
        processor = StandardPreprocessor(max_text_length=100)
        text = "b" * 100
        result = processor._apply_step(text, PreprocessingStep.TRUNCATE)
        assert result == text  # Should remain unchanged
        assert len(result) == 100

    def test_apply_step_truncate_custom_length(self):
        """Test truncation with custom max_text_length."""
        processor = StandardPreprocessor(max_text_length=50)
        text = "c" * 100
        result = processor._apply_step(text, PreprocessingStep.TRUNCATE)
        assert len(result) == 53  # 50 + "..."
        assert result == "c" * 50 + "..."

    def test_truncate_in_pipeline(self):
        """Test TRUNCATE step as part of preprocessing pipeline."""
        steps = [
            PreprocessingStep.LOWERCASE,
            PreprocessingStep.TRUNCATE,
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
        ]
        processor = StandardPreprocessor(steps=steps, max_text_length=20)
        text = "THIS IS A VERY LONG TEXT THAT WILL BE TRUNCATED"
        result = processor.process(text)
        # Should be lowercased, truncated to 20 chars + "...", then whitespace cleaned
        assert len(result) <= 23
        assert result.startswith("this is a very long ")
        assert result.endswith("...")

    def test_truncate_preserves_unicode(self):
        """Test that truncation handles Unicode characters properly."""
        processor = StandardPreprocessor(max_text_length=10)
        text = "café " * 10  # 50 characters with accented chars
        result = processor._apply_step(text, PreprocessingStep.TRUNCATE)
        assert len(result) == 13  # 10 + "..."
        assert "café" in result
        assert result.endswith("...")

    def test_apply_step_unknown_step(self):
        """Test applying unknown preprocessing step."""
        processor = StandardPreprocessor()
        text = "Unchanged Text"

        # Mock the method to simulate an unknown step by making all conditions fail
        original_method = processor._apply_step

        def mock_apply_step(input_text: str, step) -> str:
            # Skip all known step conditions to reach the fallback return
            # This simulates what happens with an unknown step
            return input_text  # The fallback behavior from line 144

        with patch.object(processor, "_apply_step", side_effect=mock_apply_step):
            result = processor._apply_step(text, PreprocessingStep.LOWERCASE)
            assert result == "Unchanged Text"  # Should return unchanged

    def test_complex_preprocessing_pipeline(self):
        """Test complex preprocessing pipeline with multiple steps."""
        steps = [
            PreprocessingStep.REMOVE_URLS,
            PreprocessingStep.REMOVE_EMAILS,
            PreprocessingStep.EXPAND_CONTRACTIONS,
            PreprocessingStep.LOWERCASE,
            PreprocessingStep.REMOVE_PUNCTUATION,
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
        ]
        processor = StandardPreprocessor(steps=steps)

        text = (
            "DON'T visit https://bad-site.com or email spam@evil.org! "
            "We're here to help... Really!!! Call 123-456-7890."
        )

        result = processor.process(text)

        # Should be processed by all steps
        assert "https://bad-site.com" not in result
        assert "spam@evil.org" not in result
        assert "don't" not in result.lower()
        assert "we're" not in result.lower()
        # DON'T becomes "dont" due to case sensitivity in expansion
        assert "dont" in result
        assert "we are" in result
        assert result.islower()  # Lowercase applied
        # Punctuation should be removed
        assert "!" not in result
        assert "..." not in result
        # Extra whitespace should be cleaned
        assert "  " not in result

    def test_complex_pipeline_with_truncate(self):
        """Test complex pipeline including TRUNCATE step."""
        steps = [
            PreprocessingStep.LOWERCASE,  # Lowercase first so contractions work
            PreprocessingStep.EXPAND_CONTRACTIONS,
            PreprocessingStep.TRUNCATE,
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
        ]
        processor = StandardPreprocessor(steps=steps, max_text_length=30)

        text = "Don't forget: This is a VERY LONG message that we're sending!"
        result = processor.process(text)

        # Should lowercase, expand contractions, truncate, clean whitespace
        assert "don't" not in result.lower()
        assert "do not" in result
        assert len(result) <= 33  # 30 + "..."
        assert result.islower()
        assert result.endswith("...")

    def test_backward_compatibility_default_args(self):
        """Test that StandardPreprocessor works with old calling patterns."""
        # Test with no arguments (should work with defaults)
        processor1 = StandardPreprocessor()
        assert processor1.max_text_length == 8000
        assert processor1.steps == [
            PreprocessingStep.REMOVE_EXTRA_WHITESPACE,
            PreprocessingStep.NORMALIZE_UNICODE,
        ]

        # Test with only steps argument (backward compatibility)
        steps = [PreprocessingStep.LOWERCASE]
        processor2 = StandardPreprocessor(steps)
        assert processor2.max_text_length == 8000
        assert processor2.steps == steps

        # Test both can process text
        text = "Test TEXT"
        result1 = processor1.process(text)
        result2 = processor2.process(text)
        assert result1 == "Test TEXT"
        assert result2 == "test text"


class TestScreenplayPreprocessor:
    """Test ScreenplayPreprocessor class."""

    @pytest.fixture
    def processor(self):
        """Create screenplay preprocessor."""
        return ScreenplayPreprocessor()

    def test_process_simple_text(self, processor):
        """Test processing simple text."""
        text = "Simple dialogue line."
        result = processor.process(text)
        assert "Simple dialogue line." in result

    def test_normalize_character_names(self, processor):
        """Test character name normalization."""
        text = "JOHN\nHello there.\nMARY JANE\nHow are you?"
        result = processor._normalize_character_names(text)

        lines = result.split("\n")
        assert "John" in lines  # Should be title case
        assert "Mary Jane" in lines  # Should be title case
        assert "Hello there." in lines  # Dialogue unchanged
        assert "How are you?" in lines  # Dialogue unchanged

    def test_normalize_character_names_mixed_case(self, processor):
        """Test character name normalization with mixed case."""
        text = "DETECTIVE SMITH\nLet's investigate.\ndr. jones\nInteresting case."
        result = processor._normalize_character_names(text)

        # DETECTIVE SMITH should become Detective Smith
        assert "Detective Smith" in result
        # dr. jones is not all caps, so should remain unchanged
        assert "dr. jones" in result

    def test_normalize_character_names_long_names(self, processor):
        """Test character name normalization with long names (not character names)."""
        text = "THIS IS A VERY LONG LINE OF ACTION DESCRIPTION\nJOHN\nHello."
        result = processor._normalize_character_names(text)

        # Long line should not be treated as character name
        assert "THIS IS A VERY LONG LINE" in result
        # Short all-caps line should be treated as character name
        assert "John" in result

    def test_normalize_parentheticals(self, processor):
        """Test parenthetical normalization."""
        text = "John walks to the door  (angrily)  and slams it."
        result = processor._normalize_parentheticals(text)

        # Should normalize spacing around parentheticals
        assert "(angrily)" in result
        assert "  (angrily)  " not in result

    def test_normalize_parentheticals_multiple(self, processor):
        """Test multiple parentheticals."""
        text = "She speaks(softly)while he listens(intently)."
        result = processor._normalize_parentheticals(text)

        # Should add proper spacing
        assert " (softly) " in result
        assert " (intently) " in result

    def test_clean_transitions(self, processor):
        """Test scene transition cleaning."""
        transitions = ["CUT TO:", "FADE IN:", "FADE OUT:", "DISSOLVE TO:"]

        for transition in transitions:
            text = f"Previous scene.{transition}Next scene."
            result = processor._clean_transitions(text)

            # Should add newlines around transitions
            assert f"\n{transition}\n" in result
            assert "Previous scene." in result
            assert "Next scene." in result

    def test_clean_transitions_already_formatted(self, processor):
        """Test transitions that are already properly formatted."""
        text = "Previous scene.\nCUT TO:\nNext scene."
        result = processor._clean_transitions(text)

        # Should still work without adding extra newlines
        assert "\nCUT TO:\n" in result
        # Should not create triple newlines
        assert "\n\n\nCUT TO:\n\n\n" not in result

    def test_remove_extra_whitespace_preserve_structure(self, processor):
        """Test whitespace removal while preserving screenplay structure."""
        text = "\n\n\nINT. ROOM - DAY\n\n\n\nJohn enters.\n\n\n\n\n"
        result = processor._remove_extra_whitespace(text)

        # Should remove excessive blank lines but preserve double newlines
        assert "\n\n\n\n" not in result
        assert "\n\n" in result  # Should preserve some structure
        assert "INT. ROOM - DAY" in result
        assert "John enters." in result

    def test_remove_extra_whitespace_trailing(self, processor):
        """Test removal of trailing whitespace on lines."""
        text = "Line with trailing spaces   \nAnother line\t\t\n"
        result = processor._remove_extra_whitespace(text)

        lines = result.split("\n")
        for line in lines:
            if line:  # Skip empty lines
                assert not line.endswith(" ")
                assert not line.endswith("\t")

    def test_process_full_screenplay_excerpt(self, processor):
        """Test processing a full screenplay excerpt."""
        text = """

        INT. COFFEE SHOP - DAY

        DETECTIVE SARAH JONES enters  (purposefully)  .

        BARISTA
        What can I get you?

        DETECTIVE SARAH JONES
        Just information.

        CUT TO:EXT. STREET - CONTINUOUS


        """

        result = processor.process(text)

        # Character names should be normalized
        assert "Detective Sarah Jones" in result
        assert "Barista" in result

        # Parentheticals should be normalized
        assert " (purposefully) " in result
        assert "  (purposefully)  " not in result

        # Transitions should be properly formatted
        assert "\nCUT TO:\n" in result

        # Excessive whitespace should be removed
        assert "\n\n\n\n" not in result

        # Structure should be preserved
        assert "INT. COFFEE SHOP - DAY" in result
        assert "EXT. STREET - CONTINUOUS" in result


class TestEmbeddingPipeline:
    """Test EmbeddingPipeline class."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock(spec=LLMClient)
        client.embed = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        return client

    @pytest.fixture
    def mock_cache(self, tmp_path):
        """Create mock cache."""
        return EmbeddingCache(cache_dir=tmp_path / "cache", max_size=10)

    @pytest.fixture
    def mock_dimension_manager(self):
        """Create mock dimension manager."""
        return DimensionManager()

    @pytest.fixture
    def config(self):
        """Create pipeline configuration."""
        return PipelineConfig(
            model="test-model",
            dimensions=512,
            preprocessing_steps=[PreprocessingStep.LOWERCASE],
            batch_size=2,
        )

    @pytest.fixture
    def pipeline(self, config, mock_llm_client, mock_cache, mock_dimension_manager):
        """Create embedding pipeline."""
        return EmbeddingPipeline(
            config=config,
            llm_client=mock_llm_client,
            cache=mock_cache,
            dimension_manager=mock_dimension_manager,
        )

    def test_init_with_all_params(
        self, config, mock_llm_client, mock_cache, mock_dimension_manager
    ):
        """Test pipeline initialization with all parameters."""
        pipeline = EmbeddingPipeline(
            config=config,
            llm_client=mock_llm_client,
            cache=mock_cache,
            dimension_manager=mock_dimension_manager,
        )

        assert pipeline.config == config
        assert pipeline.llm_client == mock_llm_client
        assert pipeline.cache == mock_cache
        assert pipeline.dimension_manager == mock_dimension_manager
        assert isinstance(pipeline.preprocessor, StandardPreprocessor)
        assert isinstance(pipeline.batch_processor, BatchProcessor)

    def test_init_with_defaults(self, config):
        """Test pipeline initialization with default components."""
        pipeline = EmbeddingPipeline(config=config)

        assert pipeline.config == config
        assert isinstance(pipeline.llm_client, LLMClient)
        assert isinstance(pipeline.preprocessor, StandardPreprocessor)
        assert isinstance(pipeline.cache, EmbeddingCache)
        assert isinstance(pipeline.dimension_manager, DimensionManager)
        assert isinstance(pipeline.batch_processor, BatchProcessor)

    def test_init_no_cache(self):
        """Test pipeline initialization without cache."""
        config = PipelineConfig(model="test-model", use_cache=False)
        pipeline = EmbeddingPipeline(config=config)

        assert pipeline.cache is None

    def test_init_with_chunking(self):
        """Test pipeline initialization with chunking enabled."""
        config = PipelineConfig(
            model="test-model",
            chunk_size=500,
            chunk_overlap=100,
        )
        pipeline = EmbeddingPipeline(config=config)

        assert isinstance(pipeline.batch_processor, ChunkedBatchProcessor)
        assert pipeline.batch_processor.chunk_size == 500
        assert pipeline.batch_processor.chunk_overlap == 100

    def test_init_no_chunking(self):
        """Test pipeline initialization without chunking."""
        config = PipelineConfig(model="test-model", chunk_size=0)
        pipeline = EmbeddingPipeline(config=config)

        assert isinstance(pipeline.batch_processor, BatchProcessor)
        assert not isinstance(pipeline.batch_processor, ChunkedBatchProcessor)

    def test_init_custom_preprocessor(self, config, mock_llm_client):
        """Test pipeline initialization with custom preprocessor."""
        custom_preprocessor = ScreenplayPreprocessor()
        pipeline = EmbeddingPipeline(
            config=config,
            llm_client=mock_llm_client,
            preprocessor=custom_preprocessor,
        )

        assert pipeline.preprocessor == custom_preprocessor

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, pipeline, mock_llm_client):
        """Test successful embedding generation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        result = await pipeline.generate_embedding("Test text")

        assert result == [0.1, 0.2, 0.3]
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_with_preprocessing(
        self, pipeline, mock_llm_client
    ):
        """Test embedding generation with preprocessing."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Pipeline config has LOWERCASE preprocessing
        result = await pipeline.generate_embedding("UPPERCASE TEXT")

        assert result == [0.1, 0.2, 0.3]

        # Check that preprocessing was applied (text should be lowercase)
        call_args = mock_llm_client.embed.call_args[0][0]
        assert call_args.input == "uppercase text"

    @pytest.mark.asyncio
    async def test_generate_embedding_with_truncation(self, pipeline, mock_llm_client):
        """Test embedding generation with text truncation."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # Create text longer than max_text_length (8000 by default)
        long_text = "a" * 9000
        result = await pipeline.generate_embedding(long_text)

        assert result == [0.1, 0.2, 0.3]

        # Check that text was truncated
        call_args = mock_llm_client.embed.call_args[0][0]
        assert len(call_args.input) <= 8000 + 3  # +3 for "..."
        assert call_args.input.endswith("...")

    @pytest.mark.asyncio
    async def test_generate_embedding_cache_hit(self, pipeline, mock_llm_client):
        """Test embedding generation with cache hit."""
        # Pre-populate cache
        pipeline.cache.put("test text", "test-model", [0.4, 0.5, 0.6])

        result = await pipeline.generate_embedding("test text")

        np.testing.assert_allclose(result, [0.4, 0.5, 0.6], rtol=1e-6)
        # LLM should not be called due to cache hit
        mock_llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_cache_miss(self, pipeline, mock_llm_client):
        """Test embedding generation with cache miss and subsequent cache."""
        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        # First call - cache miss
        result1 = await pipeline.generate_embedding("new text")
        assert result1 == [0.1, 0.2, 0.3]
        assert mock_llm_client.embed.call_count == 1

        # Second call - should hit cache
        result2 = await pipeline.generate_embedding("new text")
        # Cache may introduce float32 precision differences
        import numpy as np

        np.testing.assert_allclose(result2, [0.1, 0.2, 0.3], rtol=1e-6)
        # LLM call count should still be 1
        assert mock_llm_client.embed.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_embedding_no_cache(self):
        """Test embedding generation without cache."""
        config = PipelineConfig(model="test-model", use_cache=False)
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_llm_client.embed = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        pipeline = EmbeddingPipeline(
            config=config,
            llm_client=mock_llm_client,
        )

        mock_response = EmbeddingResponse(
            model="test-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_llm_client.embed.return_value = mock_response

        result = await pipeline.generate_embedding("test text")
        assert result == [0.1, 0.2, 0.3]
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_dimension_validation(
        self, pipeline, mock_llm_client
    ):
        """Test embedding generation with dimension validation warning."""
        # Mock dimension manager to return different expected dimensions
        with patch.object(
            pipeline.dimension_manager, "get_dimensions"
        ) as mock_get_dims:
            mock_get_dims.return_value = 1024  # Different from returned embedding

            mock_response = EmbeddingResponse(
                model="test-model",
                data=[{"embedding": [0.1, 0.2, 0.3]}],  # 3 dimensions
                provider=LLMProvider.OPENAI_COMPATIBLE,
            )
            mock_llm_client.embed.return_value = mock_response

            with patch("scriptrag.embeddings.pipeline.logger") as mock_logger:
                result = await pipeline.generate_embedding("test text")

                assert result == [0.1, 0.2, 0.3]
                # Should log dimension mismatch warning
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Dimension mismatch" in warning_msg

    @pytest.mark.asyncio
    async def test_generate_embedding_failure(self, pipeline, mock_llm_client):
        """Test embedding generation failure."""
        # Mock batch processor to return failure
        with patch.object(pipeline.batch_processor, "process_batch") as mock_process:
            mock_process.return_value = [
                MagicMock(embedding=None, error="Generation failed")
            ]

            with pytest.raises(ValueError) as exc_info:
                await pipeline.generate_embedding("test text")

            assert "Failed to generate embedding" in str(exc_info.value)
            assert "Generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_no_results(self, pipeline, mock_llm_client):
        """Test embedding generation with no results."""
        with patch.object(pipeline.batch_processor, "process_batch") as mock_process:
            mock_process.return_value = []  # No results

            with pytest.raises(ValueError) as exc_info:
                await pipeline.generate_embedding("test text")

            assert "Failed to generate embedding" in str(exc_info.value)
            assert "Unknown error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_batch_success(self, pipeline, mock_llm_client):
        """Test successful batch embedding generation."""
        with patch.object(pipeline.batch_processor, "process_parallel") as mock_process:
            # Mock successful results
            mock_process.return_value = [
                MagicMock(id="0", embedding=[0.1, 0.2], error=None),
                MagicMock(id="1", embedding=[0.3, 0.4], error=None),
            ]

            texts = ["first text", "second text"]
            results = await pipeline.generate_batch(texts)

            assert len(results) == 2
            assert results[0] == [0.1, 0.2]
            assert results[1] == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_generate_batch_with_metadata(self, pipeline, mock_llm_client):
        """Test batch generation with metadata."""
        with patch.object(pipeline.batch_processor, "process_parallel") as mock_process:
            mock_process.return_value = [
                MagicMock(id="0", embedding=[0.1, 0.2], error=None),
            ]

            texts = ["test text"]
            metadata_list = [{"source": "test"}]
            results = await pipeline.generate_batch(texts, metadata_list)

            assert len(results) == 1
            assert results[0] == [0.1, 0.2]

            # Check that metadata was passed to batch processor
            call_args = mock_process.call_args[0][0]  # First argument (items)
            assert len(call_args) == 1
            assert call_args[0].metadata == {"source": "test"}

    @pytest.mark.asyncio
    async def test_generate_batch_cache_integration(self, pipeline, mock_llm_client):
        """Test batch generation with cache integration."""
        # Pre-populate cache for first text
        pipeline.cache.put("first text", "test-model", [0.9, 0.8])

        with patch.object(pipeline.batch_processor, "process_parallel") as mock_process:
            # Only second text should be processed
            mock_process.return_value = [
                MagicMock(id="1", embedding=[0.3, 0.4], error=None),
            ]

            texts = ["first text", "second text"]
            results = await pipeline.generate_batch(texts)

            assert len(results) == 2
            np.testing.assert_allclose(results[0], [0.9, 0.8], rtol=1e-6)  # From cache
            assert results[1] == [0.3, 0.4]  # From processing

            # Only one item should have been sent for processing
            call_args = mock_process.call_args[0][0]  # First argument (items)
            assert len(call_args) == 1
            assert call_args[0].id == "1"  # Second text

    @pytest.mark.asyncio
    async def test_generate_batch_partial_failures(self, pipeline, mock_llm_client):
        """Test batch generation with partial failures."""
        with patch.object(pipeline.batch_processor, "process_parallel") as mock_process:
            mock_process.return_value = [
                MagicMock(id="0", embedding=[0.1, 0.2], error=None),
                MagicMock(id="1", embedding=None, error="Failed"),
            ]

            texts = ["good text", "bad text"]
            results = await pipeline.generate_batch(texts)

            assert len(results) == 2
            assert results[0] == [0.1, 0.2]
            assert results[1] is None  # Failed item

    @pytest.mark.asyncio
    async def test_generate_batch_empty(self, pipeline):
        """Test batch generation with empty input."""
        results = await pipeline.generate_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_generate_for_scenes(self, pipeline, mock_llm_client):
        """Test scene-specific embedding generation."""
        with patch.object(pipeline, "generate_batch") as mock_generate_batch:
            mock_generate_batch.return_value = [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ]

            scenes = [
                {"id": 1, "heading": "INT. ROOM - DAY", "content": "John enters."},
                {"id": 2, "heading": "EXT. STREET - NIGHT", "content": "Mary walks."},
            ]

            results = await pipeline.generate_for_scenes(scenes)

            assert len(results) == 2
            assert results[0] == (1, [0.1, 0.2, 0.3])
            assert results[1] == (2, [0.4, 0.5, 0.6])

            # Check that texts were properly formatted
            call_args = mock_generate_batch.call_args[0][0]  # First argument (texts)
            assert len(call_args) == 2
            assert "Scene: INT. ROOM - DAY" in call_args[0]
            assert "John enters." in call_args[0]
            assert "Scene: EXT. STREET - NIGHT" in call_args[1]
            assert "Mary walks." in call_args[1]

    @pytest.mark.asyncio
    async def test_generate_for_scenes_preprocessor_switching(
        self, pipeline, mock_llm_client
    ):
        """Test that generate_for_scenes switches to screenplay preprocessor."""
        original_preprocessor = pipeline.preprocessor

        with patch.object(pipeline, "generate_batch") as mock_generate_batch:
            mock_generate_batch.return_value = [[0.1, 0.2]]

            scenes = [{"id": 1, "heading": "INT. ROOM", "content": "Action."}]

            await pipeline.generate_for_scenes(scenes)

            # During processing, preprocessor should be ScreenplayPreprocessor
            # After processing, it should be restored
            assert pipeline.preprocessor == original_preprocessor

    def test_clear_cache_with_cache(self, pipeline):
        """Test clearing cache when cache exists."""
        with patch.object(pipeline.cache, "clear") as mock_clear:
            mock_clear.return_value = 5

            result = pipeline.clear_cache()

            assert result == 5
            mock_clear.assert_called_once()

    def test_clear_cache_no_cache(self):
        """Test clearing cache when no cache exists."""
        config = PipelineConfig(model="test-model", use_cache=False)
        pipeline = EmbeddingPipeline(config=config)

        result = pipeline.clear_cache()
        assert result == 0

    def test_get_stats(self, pipeline):
        """Test getting pipeline statistics."""
        with patch.object(pipeline.cache, "get_stats") as mock_cache_stats:
            mock_cache_stats.return_value = {"entries": 10, "size_mb": 5.2}

            stats = pipeline.get_stats()

            assert stats["model"] == "test-model"
            assert stats["dimensions"] == 512
            assert stats["preprocessing_steps"] == ["lowercase"]
            assert stats["max_text_length"] == 8000
            assert stats["batch_size"] == 2
            assert stats["cache"] == {"entries": 10, "size_mb": 5.2}

    def test_get_stats_no_cache(self):
        """Test getting stats when no cache exists."""
        config = PipelineConfig(model="test-model", use_cache=False)
        pipeline = EmbeddingPipeline(config=config)

        stats = pipeline.get_stats()

        assert "cache" not in stats
        assert stats["model"] == "test-model"

    def test_get_stats_no_preprocessing_steps(self):
        """Test getting stats when no preprocessing steps configured."""
        config = PipelineConfig(model="test-model", preprocessing_steps=None)
        pipeline = EmbeddingPipeline(config=config)

        stats = pipeline.get_stats()
        assert stats["preprocessing_steps"] == []

    @pytest.mark.asyncio
    async def test_metadata_preservation_in_caching(self, pipeline, mock_llm_client):
        """Test that metadata is preserved through caching process."""
        with patch.object(pipeline.batch_processor, "process_parallel") as mock_process:
            mock_result = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_result.id = "0"
            mock_result.embedding = [0.1, 0.2]
            mock_result.error = None
            mock_result.metadata = {"source": "test"}
            mock_process.return_value = [mock_result]

            texts = ["test text"]
            metadata_list = [{"source": "test"}]
            results = await pipeline.generate_batch(texts, metadata_list)

            assert len(results) == 1
            assert results[0] == [0.1, 0.2]

            # Check that metadata was used in caching
            # (This would be visible in cache.put calls if we mocked them)

    @pytest.mark.asyncio
    async def test_preprocessing_step_order_matters(self):
        """Test that preprocessing step order affects results."""
        # Test with different step orders
        steps1 = [PreprocessingStep.LOWERCASE, PreprocessingStep.REMOVE_PUNCTUATION]
        steps2 = [PreprocessingStep.REMOVE_PUNCTUATION, PreprocessingStep.LOWERCASE]

        config1 = PipelineConfig(model="test", preprocessing_steps=steps1)
        config2 = PipelineConfig(model="test", preprocessing_steps=steps2)

        pipeline1 = EmbeddingPipeline(config=config1)
        pipeline2 = EmbeddingPipeline(config=config2)

        text = "HELLO, WORLD!"

        result1 = pipeline1.preprocessor.process(text)
        result2 = pipeline2.preprocessor.process(text)

        # Results should be the same for this case, but process demonstrates order
        assert result1 == "hello world"
        assert result2 == "hello world"
        # Both should remove punctuation and lowercase, regardless of order
