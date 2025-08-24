"""Tests for OpenAI-compatible provider."""

import asyncio
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.exceptions import LLMProviderError
from scriptrag.llm.models import CompletionRequest, EmbeddingRequest, LLMProvider
from scriptrag.llm.providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    """Test OpenAI-compatible provider functionality."""

    @pytest.fixture
    def provider(self) -> OpenAICompatibleProvider:
        """Create provider instance with configuration."""
        return OpenAICompatibleProvider(
            endpoint="http://localhost:11434/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

    @pytest.fixture
    def provider_no_config(self) -> OpenAICompatibleProvider:
        """Create provider instance without configuration."""
        with patch.dict(os.environ, {}, clear=True):
            return OpenAICompatibleProvider()

    def test_init_with_params(self) -> None:
        """Test initialization with explicit parameters."""
        provider = OpenAICompatibleProvider(
            endpoint="http://example.com/api",
            api_key="my-key",  # pragma: allowlist secret
            timeout=120.0,
        )
        assert provider.base_url == "http://example.com/api"
        assert provider.api_key == "my-key"  # pragma: allowlist secret
        assert provider.timeout == 120.0
        assert provider.client is not None
        assert provider._availability_cache is None
        assert isinstance(provider._request_semaphore, asyncio.Semaphore)

    def test_init_with_env_vars(self) -> None:
        """Test initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "SCRIPTRAG_LLM_ENDPOINT": "http://env-endpoint",
                "SCRIPTRAG_LLM_API_KEY": "env-key",  # pragma: allowlist secret
            },
        ):
            provider = OpenAICompatibleProvider()
            assert provider.base_url == "http://env-endpoint"
            assert provider.api_key == "env-key"  # pragma: allowlist secret

    def test_init_without_config(self) -> None:
        """Test initialization without any configuration."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider()
            assert provider.base_url == ""
            assert provider.api_key == ""

    def test_provider_type(self, provider: OpenAICompatibleProvider) -> None:
        """Test provider type."""
        assert provider.provider_type == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_is_available_no_endpoint(
        self, provider_no_config: OpenAICompatibleProvider
    ) -> None:
        """Test availability check without endpoint."""
        assert await provider_no_config.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_no_api_key(self) -> None:
        """Test availability check without API key."""
        provider = OpenAICompatibleProvider(endpoint="http://localhost:11434/v1")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_cache_true(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test availability with cached positive result."""
        provider._availability_cache = True
        provider._cache_timestamp = time.time()

        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_with_cache_false(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test availability with cached negative result."""
        provider._availability_cache = False
        provider._cache_timestamp = time.time()

        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_cache_expired(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test availability with expired cache."""
        provider._availability_cache = True
        provider._cache_timestamp = time.time() - 301  # Over 5 minutes old

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", return_value=mock_response):
            result = await provider.is_available()
            assert result is True
            # Cache should be updated
            assert provider._availability_cache is True
            assert time.time() - provider._cache_timestamp < 1

    @pytest.mark.asyncio
    async def test_is_available_api_success(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test successful API availability check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", return_value=mock_response):
            result = await provider.is_available()
            assert result is True
            assert provider._availability_cache is True

    @pytest.mark.asyncio
    async def test_is_available_api_error(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test API error during availability check."""
        with patch.object(
            provider.client, "get", side_effect=RuntimeError("Connection error")
        ):
            result = await provider.is_available()
            assert result is False
            assert provider._availability_cache is False

    @pytest.mark.asyncio
    async def test_is_available_404_error(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test 404 error during availability check."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(provider.client, "get", return_value=mock_response):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_list_models_success(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test successful model listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "qwen/qwen3-30b-a3b-mlx",
                    "object": "model",
                    "created": 1234567890,
                },
                {"id": "llama3:latest", "object": "model", "created": 1234567891},
                {
                    "id": "mlx-community/glm-4-9b-chat-4bit",
                    "object": "model",
                    "created": 1234567892,
                },
            ]
        }

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()

            assert len(models) == 3
            # Check that preferred models are listed first
            assert models[0].id == "qwen/qwen3-30b-a3b-mlx"
            assert models[1].id == "mlx-community/glm-4-9b-chat-4bit"
            assert models[2].id == "llama3:latest"

            # Check model properties
            assert all(m.provider == LLMProvider.OPENAI_COMPATIBLE for m in models)

    @pytest.mark.asyncio
    async def test_list_models_api_error(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test model listing with API error."""
        with patch.object(
            provider.client, "get", side_effect=RuntimeError("API Error")
        ):
            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_list_models_custom_sorting(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test that models are sorted according to preference order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "other-model", "object": "model"},
                {"id": "mlx-community/glm-4-9b-chat-4bit", "object": "model"},
                {"id": "qwen/qwen3-30b-a3b-mlx", "object": "model"},
                {"id": "another-model", "object": "model"},
            ]
        }

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()

            model_ids = [m.id for m in models]
            # Preferred models should come first
            assert model_ids[0] == "qwen/qwen3-30b-a3b-mlx"
            assert model_ids[1] == "mlx-community/glm-4-9b-chat-4bit"
            # Other models follow
            assert "other-model" in model_ids[2:]
            assert "another-model" in model_ids[2:]

    @pytest.mark.asyncio
    async def test_complete_success(self, provider: OpenAICompatibleProvider) -> None:
        """Test successful completion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama3",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="llama3", messages=[{"role": "user", "content": "Hello"}]
            )
            response = await provider.complete(request)

            assert response.id == "chatcmpl-123"
            assert response.model == "llama3"
            assert response.choices[0]["message"]["content"] == "Test response"
            assert response.usage["total_tokens"] == 15
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_complete_with_semaphore(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test that completion uses semaphore for serialization."""
        call_times = []

        async def mock_post(url: str, **kwargs):
            call_times.append(time.time())
            await asyncio.sleep(0.1)  # Simulate processing time

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Response {len(call_times)}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            }
            return mock_response

        with patch.object(provider.client, "post", side_effect=mock_post):
            request = CompletionRequest(
                model="test", messages=[{"role": "user", "content": "Hello"}]
            )

            # Make concurrent requests
            responses = await asyncio.gather(
                provider.complete(request),
                provider.complete(request),
                provider.complete(request),
            )

            # Check responses
            assert len(responses) == 3
            assert responses[0].choices[0]["message"]["content"] == "Response 1"
            assert responses[1].choices[0]["message"]["content"] == "Response 2"
            assert responses[2].choices[0]["message"]["content"] == "Response 3"

            # Check that calls were serialized (not concurrent)
            for i in range(1, len(call_times)):
                time_diff = call_times[i] - call_times[i - 1]
                assert time_diff >= 0.09  # Should wait for previous to complete

    @pytest.mark.asyncio
    async def test_complete_with_system_message(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test completion with system message."""
        captured_json = None

        async def capture_post(url: str, **kwargs):
            nonlocal captured_json
            captured_json = kwargs.get("json")

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            }
            return mock_response

        with patch.object(provider.client, "post", side_effect=capture_post):
            request = CompletionRequest(
                model="test",
                messages=[{"role": "user", "content": "Hello"}],
                system="You are helpful",
            )
            await provider.complete(request)

            # Check that system message was added
            assert len(captured_json["messages"]) == 2
            assert captured_json["messages"][0]["role"] == "system"
            assert captured_json["messages"][0]["content"] == "You are helpful"

    @pytest.mark.asyncio
    async def test_complete_with_response_format(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test completion with response format."""
        captured_json = None

        async def capture_post(url: str, **kwargs):
            nonlocal captured_json
            captured_json = kwargs.get("json")

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"result": "test"}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            }
            return mock_response

        with patch.object(provider.client, "post", side_effect=capture_post):
            request = CompletionRequest(
                model="test",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={"type": "json_object"},
            )
            await provider.complete(request)

            # Check that response_format was passed
            assert captured_json["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_complete_api_error(self, provider: OpenAICompatibleProvider) -> None:
        """Test completion with API error."""
        with patch.object(
            provider.client, "post", side_effect=RuntimeError("API Error")
        ):
            request = CompletionRequest(
                model="test", messages=[{"role": "user", "content": "Hello"}]
            )

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.complete(request)
            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_timeout_handling(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test completion with timeout."""
        with patch.object(
            provider.client, "post", side_effect=TimeoutError("Request timed out")
        ):
            request = CompletionRequest(
                model="test", messages=[{"role": "user", "content": "Hello"}]
            )

            with pytest.raises(asyncio.TimeoutError):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_success(self, provider: OpenAICompatibleProvider) -> None:
        """Test successful embedding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }

        with patch.object(provider.client, "post", return_value=mock_response):
            request = EmbeddingRequest(
                model="text-embedding-ada-002", input="Test text"
            )
            response = await provider.embed(request)

            assert response.model == "text-embedding-ada-002"
            assert len(response.data) == 1
            assert response.data[0]["embedding"] == [0.1, 0.2, 0.3]
            assert response.usage["total_tokens"] == 5
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_embed_api_error(self, provider: OpenAICompatibleProvider) -> None:
        """Test embedding with API error."""
        with patch.object(
            provider.client, "post", side_effect=RuntimeError("API Error")
        ):
            request = EmbeddingRequest(
                model="text-embedding-ada-002", input="Test text"
            )

            with pytest.raises(Exception) as exc_info:
                await provider.embed(request)
            assert "API Error" in str(exc_info.value)

    def test_model_preference_order(self) -> None:
        """Test MODEL_PREFERENCE_ORDER is defined."""
        assert len(OpenAICompatibleProvider.MODEL_PREFERENCE_ORDER) > 0
        assert (
            "qwen/qwen3-30b-a3b-mlx" in OpenAICompatibleProvider.MODEL_PREFERENCE_ORDER
        )

    @pytest.mark.asyncio
    async def test_complete_with_all_parameters(
        self, provider: OpenAICompatibleProvider
    ) -> None:
        """Test completion with all available parameters."""
        captured_json = None

        async def capture_post(url: str, **kwargs):
            nonlocal captured_json
            captured_json = kwargs.get("json")

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 100},
            }
            return mock_response

        with patch.object(provider.client, "post", side_effect=capture_post):
            request = CompletionRequest(
                model="test",
                messages=[{"role": "user", "content": "Test"}],
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9,
                stream=False,
            )
            await provider.complete(request)

            # Check all parameters were passed
            assert captured_json["temperature"] == 0.7
            assert captured_json["max_tokens"] == 1000
            assert captured_json["top_p"] == 0.9
            assert captured_json["stream"] is False
