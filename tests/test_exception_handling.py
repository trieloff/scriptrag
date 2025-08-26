"""Tests for specific exception handling in search and LLM modules."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from scriptrag.llm.models import CompletionRequest, EmbeddingRequest
from scriptrag.llm.providers.claude_code import ClaudeCodeProvider
from scriptrag.llm.providers.github_models import GitHubModelsProvider
from scriptrag.llm.providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleExceptions:
    """Test exception handling in OpenAICompatibleProvider."""

    @pytest.mark.asyncio
    async def test_is_available_connect_error(self):
        """Test availability check handles connection errors."""
        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:9999",
            api_key="test",  # pragma: allowlist secret
        )

        with patch.object(
            provider.client,
            "get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_timeout(self):
        """Test availability check handles timeout."""
        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:9999",
            api_key="test",  # pragma: allowlist secret
        )

        with patch.object(
            provider.client,
            "get",
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_list_models_json_error(self):
        """Test list models handles JSON decode errors."""
        import json  # Import at the beginning of the test

        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:8080",
            api_key="test",  # pragma: allowlist secret
        )

        mock_response = Mock(spec=["status_code", "json"])
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_complete_http_error(self):
        """Test completion handles HTTP errors."""
        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:8080",
            api_key="test",  # pragma: allowlist secret
        )

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        with patch.object(
            provider.client,
            "post",
            side_effect=httpx.ConnectError("Connection failed"),
        ):
            with pytest.raises(httpx.ConnectError):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_json_decode_error(self):
        """Test completion handles invalid JSON response."""
        import json  # Import at the beginning of the test

        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:8080",
            api_key="test",  # pragma: allowlist secret
        )

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        mock_response = Mock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid JSON"

        with patch.object(provider.client, "post", return_value=mock_response):
            with pytest.raises(ValueError) as exc_info:
                await provider.complete(request)

            assert "Invalid API response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_key_error(self):
        """Test embedding handles missing fields in response."""
        provider = OpenAICompatibleProvider(
            endpoint="http://localhost:8080",
            api_key="test",  # pragma: allowlist secret
        )

        request = EmbeddingRequest(model="test-model", input="test text")

        mock_response = Mock(spec=["status_code", "json"])
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing expected fields

        with patch.object(provider.client, "post", return_value=mock_response):
            # Should return response with empty data since we're missing fields
            result = await provider.embed(request)
            assert result.data == []


class TestGitHubModelsExceptions:
    """Test exception handling in GitHubModelsProvider."""

    @pytest.mark.asyncio
    async def test_is_available_http_status_error(self):
        """Test availability check handles HTTP status errors."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        # Initialize client to avoid None error
        provider._init_http_client()

        mock_response = Mock(spec=["status_code"])
        mock_response.status_code = 403
        with patch.object(
            provider.client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Forbidden", request=Mock(spec=object), response=mock_response
            ),
        ):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_complete_json_decode_error(self):
        """Test completion handles JSON decode errors."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        # Initialize client to avoid None error
        provider._init_http_client()

        request = CompletionRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        mock_response = Mock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        # Import json locally for JSONDecodeError
        import json

        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid JSON"

        with patch.object(provider.client, "post", return_value=mock_response):
            with pytest.raises(ValueError) as exc_info:
                await provider.complete(request)

            assert "Invalid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_type_error(self):
        """Test completion handles unexpected response structure."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        # Initialize client to avoid None error
        provider._init_http_client()

        request = CompletionRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        mock_response = Mock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        # Return a dict but with wrong structure for choices
        mock_response.json.return_value = {"choices": "not a list"}  # Invalid structure
        mock_response.text = "Invalid response structure"

        with patch.object(provider.client, "post", return_value=mock_response):
            # The provider now sanitizes invalid responses and provides fallback data
            result = await provider.complete(request)
            # Should return a sanitized default response instead of invalid data
            assert isinstance(result.choices, list)
            assert len(result.choices) == 1
            assert result.choices[0]["message"]["content"] == ""
            assert result.choices[0]["message"]["role"] == "assistant"
            assert result.choices[0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_embed_http_error(self):
        """Test embedding handles HTTP errors."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        # Initialize client to avoid None error
        provider._init_http_client()

        request = EmbeddingRequest(model="test-model", input="test text")

        with patch.object(
            provider.client,
            "post",
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            with pytest.raises(httpx.TimeoutException):
                await provider.embed(request)


class TestClaudeCodeExceptions:
    """Test exception handling in ClaudeCodeProvider."""

    def test_sdk_check_import_error(self):
        """Test SDK check handles ImportError."""
        # Mock the specific import that causes the issue - claude_code_sdk
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "claude_code_sdk":
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            provider = ClaudeCodeProvider()
            # The import error should be caught and SDK marked as unavailable
            assert not provider.sdk_available

    @pytest.mark.asyncio
    async def test_is_available_module_not_found(self):
        """Test availability check handles ModuleNotFoundError."""
        provider = ClaudeCodeProvider()

        provider.sdk_available = False  # Simulate SDK not available
        result = await provider.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_timeout_error(self):
        """Test completion handles asyncio.TimeoutError."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        request = CompletionRequest(
            model="claude-3-haiku",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        # Mock the SDK
        mock_query = AsyncMock(
            spec=[
                "complete",
                "cleanup",
                "embed",
                "list_models",
                "is_available",
                "__aiter__",
            ]
        )
        mock_query.__aiter__.side_effect = TimeoutError("Query timeout")

        # Skip these tests since they require the actual SDK to be installed
        pytest.skip("Requires claude_code_sdk to be installed")
        return
        with patch("claude_code_sdk.query", return_value=mock_query):
            with patch("claude_code_sdk.ClaudeCodeOptions"):
                with pytest.raises(TimeoutError):
                    await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_json_validation_error(self):
        """Test completion handles JSON validation errors."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        request = CompletionRequest(
            model="claude-3-haiku",
            messages=[{"role": "user", "content": "Generate JSON"}],
            temperature=0.7,
        )
        request.response_format = {"type": "json_object"}

        # Mock SDK to return invalid JSON
        mock_message = Mock(spec_set=["content", "__class__"])
        # Create a mock class with __name__ attribute
        mock_class = Mock(spec_set=["__name__"])
        mock_class.__name__ = "AssistantMessage"
        mock_message.__class__ = mock_class
        mock_block = Mock(spec_set=["text"])
        mock_block.text = "not valid json"
        mock_message.content = [mock_block]

        mock_query = AsyncMock(
            spec=[
                "complete",
                "cleanup",
                "embed",
                "list_models",
                "is_available",
                "__aiter__",
            ]
        )
        mock_query.__aiter__.return_value = [mock_message].__iter__()

        # Skip these tests since they require the actual SDK to be installed
        pytest.skip("Requires claude_code_sdk to be installed")
        return
        with patch("claude_code_sdk.query", return_value=mock_query):
            with patch("claude_code_sdk.ClaudeCodeOptions"):
                # Should retry up to 3 times for JSON validation
                with pytest.raises(ValueError):
                    await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_attribute_error(self):
        """Test completion handles AttributeError from SDK response."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        request = CompletionRequest(
            model="claude-3-haiku",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )

        # Mock SDK to return object missing expected attributes
        mock_message = Mock(spec_set=["__class__"])
        # Create a mock class with __name__ attribute
        mock_class = Mock(spec_set=["__name__"])
        mock_class.__name__ = "UnknownMessage"
        mock_message.__class__ = mock_class
        # Don't add content attribute to simulate missing attribute

        mock_query = AsyncMock(
            spec=[
                "complete",
                "cleanup",
                "embed",
                "list_models",
                "is_available",
                "__aiter__",
            ]
        )
        mock_query.__aiter__.return_value = [mock_message].__iter__()

        # Skip these tests since they require the actual SDK to be installed
        pytest.skip("Requires claude_code_sdk to be installed")
        return
        with patch("claude_code_sdk.query", return_value=mock_query):
            with patch("claude_code_sdk.ClaudeCodeOptions"):
                # Should complete but return empty response
                result = await provider.complete(request)
                assert result.choices[0]["message"]["content"] == ""
