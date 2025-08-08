"""Tests to improve coverage for GitHub Models provider."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.llm.providers.github_models import GitHubModelsProvider

# Test token constant to avoid S106 linting issues
TEST_TOKEN = "test-token"  # noqa: S105


class TestGitHubModelsProviderCoverage:
    """Tests for GitHub Models provider to improve coverage."""

    @pytest.mark.asyncio
    async def test_parse_rate_limit_error_valid(self):
        """Test parsing valid rate limit error response."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 42911 seconds before retrying.",
                }
            }
        )

        wait_seconds = provider._parse_rate_limit_error(error_text)
        assert wait_seconds == 42911

    @pytest.mark.asyncio
    async def test_parse_rate_limit_error_invalid_json(self):
        """Test parsing invalid JSON error response."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        wait_seconds = provider._parse_rate_limit_error("not valid json")
        assert wait_seconds is None

    @pytest.mark.asyncio
    async def test_parse_rate_limit_error_wrong_code(self):
        """Test parsing error with wrong code."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        error_text = json.dumps(
            {"error": {"code": "SomeOtherError", "message": "Different error message"}}
        )

        wait_seconds = provider._parse_rate_limit_error(error_text)
        assert wait_seconds is None

    @pytest.mark.asyncio
    async def test_parse_rate_limit_error_no_wait_time(self):
        """Test parsing rate limit error without wait time."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Rate limit reached, please try again later.",
                }
            }
        )

        wait_seconds = provider._parse_rate_limit_error(error_text)
        assert wait_seconds is None

    @pytest.mark.asyncio
    async def test_is_available_rate_limited(self):
        """Test is_available when rate limited."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)
        provider._rate_limit_reset_time = time.time() + 3600  # 1 hour in future

        result = await provider.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_rate_limit_expired(self):
        """Test is_available when rate limit has expired."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)
        provider._rate_limit_reset_time = time.time() - 1  # 1 second in past
        provider._availability_cache = True
        provider._cache_timestamp = time.time() - 10

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_list_models_rate_limited(self):
        """Test list_models when rate limited."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        # Mock the HTTP client to return 429
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 100 seconds before retrying.",
                }
            }
        )

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            assert models == []
            assert provider._rate_limit_reset_time > time.time()

    @pytest.mark.asyncio
    async def test_list_models_different_response_formats(self):
        """Test list_models with different response formats."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        # Test with list response format
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "gpt-4o-mini", "name": "GPT-4 Mini"},
            {"id": "gpt-4o", "name": "GPT-4"},
        ]

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            assert len(models) == 2
            assert models[0].id == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_list_models_dict_response(self):
        """Test list_models with dict response format."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        # Test with dict response format with "data" key
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4o-mini", "name": "GPT-4 Mini"},
                {"id": "gpt-4o", "friendly_name": "GPT-4"},
            ]
        }

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            assert len(models) == 2

    @pytest.mark.asyncio
    async def test_list_models_unknown_format(self):
        """Test list_models with unknown response format."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "unexpected_string"

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_list_models_with_azure_registry_paths(self):
        """Test list_models with Azure registry paths."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1",
                "name": "GPT-4 Mini",
            },
            {
                "id": "azureml://registries/unmapped/models/unknown/versions/1",
                "name": "Unknown Model",
            },
        ]

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            # Should only include mapped gpt-4o-mini
            assert len(models) == 1
            assert models[0].id == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_complete_rate_limited(self):
        """Test complete when rate limited."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import CompletionRequest

        request = CompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 60 seconds before retrying.",
                }
            }
        )

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(ValueError, match="GitHub Models API error"):
                await provider.complete(request)

            assert provider._rate_limit_reset_time > time.time()

    @pytest.mark.asyncio
    async def test_complete_with_response_format(self):
        """Test complete with response_format parameter."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import CompletionRequest

        request = CompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            response_format={"type": "json_object"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": '{"result": "test"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await provider.complete(request)
            assert response.model == "gpt-4o-mini"

            # Verify response_format was included in payload
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert "response_format" in payload

    @pytest.mark.asyncio
    async def test_complete_with_system_message(self):
        """Test complete with system message."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import CompletionRequest

        request = CompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant.",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": "Hi there!"}}],
            "usage": {},
        }

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await provider.complete(request)

            # Verify system message was prepended
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_embed_rate_limited(self):
        """Test embed when rate limited."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import EmbeddingRequest

        request = EmbeddingRequest(model="text-embedding-ada-002", input="Test text")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 30 seconds before retrying.",
                }
            }
        )

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(ValueError, match="GitHub Models API error"):
                await provider.embed(request)

            assert provider._rate_limit_reset_time > time.time()

    @pytest.mark.asyncio
    async def test_embed_with_dimensions(self):
        """Test embed with dimensions parameter."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import EmbeddingRequest

        request = EmbeddingRequest(
            model="text-embedding-ada-002", input="Test text", dimensions=512
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [{"embedding": [0.1] * 512}],
            "usage": {"total_tokens": 5},
        }

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await provider.embed(request)
            assert response.model == "text-embedding-ada-002"

            # Verify dimensions was included in payload
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        # Mock aclose to prevent actual network calls
        with patch.object(
            provider.client, "aclose", new_callable=AsyncMock
        ) as mock_close:
            async with provider as p:
                assert p is provider
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_non_429_error(self):
        """Test complete with non-429 error status."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        from scriptrag.llm.models import CompletionRequest

        request = CompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch.object(provider.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(ValueError, match="GitHub Models API error"):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_list_models_http_error(self):
        """Test list_models with non-429 HTTP error."""
        provider = GitHubModelsProvider(token=TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(provider.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await provider.list_models()
            assert models == []
