"""Unit tests for embedding analyzer dict/object handling bug fix."""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.llm.models import EmbeddingResponse


class TestEmbeddingDataHandling:
    """Test proper handling of embedding data as dicts vs objects."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create analyzer with mock client."""
        analyzer = SceneEmbeddingAnalyzer(
            config={
                "embedding_model": "test-model",
                "dimensions": 5,
                "lfs_path": "embeddings",
                "base_path": str(tmp_path),
                "repo_path": str(tmp_path),
            }
        )
        analyzer.llm_client = Mock()
        return analyzer

    @pytest.mark.asyncio
    async def test_embedding_response_as_dict(self, analyzer):
        """Test handling of embedding response as a dictionary."""
        # Setup mock response with dict data
        mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        embedding_dict = {
            "embedding": mock_embedding,
            "object": "embedding",
            "index": 0,
        }

        response = Mock(spec=EmbeddingResponse)
        response.data = [embedding_dict]  # Dict response

        analyzer.llm_client.embed = AsyncMock(return_value=response)

        # Create test scene dict
        scene = {
            "number": 1,
            "heading": "INT. TEST LOCATION - DAY",
            "content": "Test scene content",
            "location": "TEST LOCATION",
            "time_of_day": "DAY",
        }

        # Generate embedding
        result = await analyzer._generate_embedding(scene)

        # Verify result
        assert isinstance(result, np.ndarray)
        expected = np.array(mock_embedding, dtype=np.float32)
        np.testing.assert_array_equal(result, expected)

    @pytest.mark.asyncio
    async def test_embedding_response_as_object(self, analyzer):
        """Test handling of embedding response as an object with attribute."""
        # Setup mock response with object data
        mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Create object with embedding attribute
        class EmbeddingData:
            def __init__(self):
                self.embedding = mock_embedding
                self.object = "embedding"
                self.index = 0

        embedding_obj = EmbeddingData()

        response = Mock(spec=EmbeddingResponse)
        response.data = [embedding_obj]  # Object response

        analyzer.llm_client.embed = AsyncMock(return_value=response)

        # Create test scene dict
        scene = {
            "number": 1,
            "heading": "INT. TEST LOCATION - DAY",
            "content": "Test scene content",
            "location": "TEST LOCATION",
            "time_of_day": "DAY",
        }

        # Generate embedding
        result = await analyzer._generate_embedding(scene)

        # Verify result
        assert isinstance(result, np.ndarray)
        expected = np.array(mock_embedding, dtype=np.float32)
        np.testing.assert_array_equal(result, expected)

    @pytest.mark.asyncio
    async def test_embedding_response_missing_key(self, analyzer):
        """Test handling when embedding key is missing from dict."""
        # Setup mock response with dict missing embedding key
        embedding_dict = {
            "object": "embedding",
            "index": 0,
            # Missing 'embedding' key
        }

        response = Mock(spec=EmbeddingResponse)
        response.data = [embedding_dict]

        analyzer.llm_client.embed = AsyncMock(return_value=response)

        # Create test scene dict
        scene = {
            "number": 1,
            "heading": "INT. TEST LOCATION - DAY",
            "content": "Test scene content",
            "location": "TEST LOCATION",
            "time_of_day": "DAY",
        }

        # Should raise EmbeddingGenerationError (which wraps the KeyError)
        from scriptrag.exceptions import EmbeddingGenerationError

        with pytest.raises(
            EmbeddingGenerationError, match="Failed to generate embedding"
        ):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_embedding_response_mixed_formats(self, analyzer):
        """Test that analyzer can handle different response formats."""
        test_cases = [
            # Dict with embedding
            ({"embedding": [0.1, 0.2], "index": 0}, True),
            # Dict without embedding
            ({"index": 0}, False),
        ]

        for data, should_succeed in test_cases:
            response = Mock(spec=EmbeddingResponse)
            response.data = [data]

            analyzer.llm_client.embed = AsyncMock(return_value=response)

            scene = {
                "number": 1,
                "heading": "INT. TEST - DAY",
                "content": "Test content",
                "location": "TEST",
                "time_of_day": "DAY",
            }

            if should_succeed:
                result = await analyzer._generate_embedding(scene)
                assert isinstance(result, np.ndarray)
            else:
                from scriptrag.exceptions import EmbeddingGenerationError

                with pytest.raises(EmbeddingGenerationError):
                    await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_empty_embedding_data(self, analyzer):
        """Test handling of empty embedding data."""
        response = Mock(spec=EmbeddingResponse)
        response.data = []  # Empty data list

        analyzer.llm_client.embed = AsyncMock(return_value=response)

        scene = {
            "number": 1,
            "heading": "INT. TEST - DAY",
            "content": "Test content",
            "location": "TEST",
            "time_of_day": "DAY",
        }

        # Should raise EmbeddingGenerationError (which wraps the RuntimeError)
        from scriptrag.exceptions import EmbeddingGenerationError

        with pytest.raises(
            EmbeddingGenerationError, match="Failed to generate embedding"
        ):
            await analyzer._generate_embedding(scene)
