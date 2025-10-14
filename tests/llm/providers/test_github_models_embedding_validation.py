"""Tests for GitHub Models embedding response validation bug fix."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scriptrag.llm.models import EmbeddingRequest, LLMProvider
from scriptrag.llm.providers.github_models import GitHubModelsProvider


class TestGitHubModelsEmbeddingValidation:
    """Test cases for embedding response validation in GitHub Models provider."""

    @pytest.fixture
    def provider(self):
        """Create a GitHub Models provider instance."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            provider = GitHubModelsProvider()
            provider.token = "test-token"  # noqa: S105
            provider.client = MagicMock(spec=httpx.AsyncClient)
            return provider

    @pytest.mark.asyncio
    async def test_embed_empty_data_array(self, provider):
        """Test that empty data array raises appropriate error."""
        # Mock response with empty data array
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [],  # Empty array - should cause error
            "usage": {"total_tokens": 0},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about empty embedding data
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "empty embedding data" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_missing_embedding_field(self, provider):
        """Test that data entries missing 'embedding' field raise error."""
        # Mock response with invalid data structure
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                {
                    "index": 0,
                    # Missing 'embedding' field
                    "object": "embedding",
                }
            ],
            "usage": {"total_tokens": 5},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about missing embedding field
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "missing 'embedding' field" in str(exc_info.value)
        assert "index 0" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_non_list_embedding(self, provider):
        """Test that non-list embedding values raise error."""
        # Mock response with non-list embedding
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                {
                    "index": 0,
                    "embedding": "not-a-list",  # Should be a list
                    "object": "embedding",
                }
            ],
            "usage": {"total_tokens": 5},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about embedding not being a list
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "'embedding' must be a list" in str(exc_info.value)
        assert "index 0" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_null_data(self, provider):
        """Test that null data field is handled as empty."""
        # Mock response with null data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": None,  # Null data - should be treated as empty
            "usage": {"total_tokens": 0},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about empty embedding data
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "empty embedding data" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_mixed_valid_invalid_data(self, provider):
        """Test that validation checks all entries in data array."""
        # Mock response with mixed valid/invalid entries
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                {
                    "index": 0,
                    "embedding": [0.1, 0.2, 0.3],  # Valid
                    "object": "embedding",
                },
                {
                    "index": 1,
                    # Missing embedding field in second entry
                    "object": "embedding",
                },
            ],
            "usage": {"total_tokens": 10},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about the invalid second entry
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "index 1" in str(exc_info.value)
        assert "missing 'embedding' field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_valid_response(self, provider):
        """Test that valid embedding response passes validation."""
        # Mock valid response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                {
                    "index": 0,
                    "embedding": [0.1, 0.2, 0.3],
                    "object": "embedding",
                }
            ],
            "usage": {"total_tokens": 5},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should succeed without errors
        response = await provider.embed(request)

        assert response.model == "text-embedding-ada-002"
        assert len(response.data) == 1
        assert response.data[0]["embedding"] == [0.1, 0.2, 0.3]
        assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_embed_malformed_json_response(self, provider):
        """Test that malformed JSON responses are handled."""
        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "test", 0)
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about invalid response
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "Invalid embedding response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_non_dict_data_entries(self, provider):
        """Test that non-dict entries in data array are handled."""
        # Mock response with non-dict entries
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                "not-a-dict",  # Should be a dict
            ],
            "usage": {"total_tokens": 5},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise ValueError about invalid data structure
        with pytest.raises(ValueError) as exc_info:
            await provider.embed(request)

        assert "missing 'embedding' field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_empty_embedding_list(self, provider):
        """Test that empty embedding lists are allowed (edge case)."""
        # Mock response with empty embedding list
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [
                {
                    "index": 0,
                    "embedding": [],  # Empty list - technically valid
                    "object": "embedding",
                }
            ],
            "usage": {"total_tokens": 0},
        }
        provider.client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="",  # Empty input might produce empty embedding
        )

        # Should succeed - empty list is still a valid list
        response = await provider.embed(request)

        assert response.model == "text-embedding-ada-002"
        assert len(response.data) == 1
        assert response.data[0]["embedding"] == []

    @pytest.mark.asyncio
    async def test_embed_http_error_handling(self, provider):
        """Test that HTTP errors are properly propagated."""
        # Mock HTTP error
        provider.client.post = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed")
        )

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
        )

        # Should raise the HTTP error
        with pytest.raises(httpx.HTTPError):
            await provider.embed(request)
