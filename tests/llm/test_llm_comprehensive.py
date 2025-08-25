"""Comprehensive tests for LLM module to achieve 99% coverage."""

import os
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from scriptrag.exceptions import LLMFallbackError
from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    LLMProvider,
    Model,
    ProviderRegistry,
)
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.providers import (
    ClaudeCodeProvider,
    GitHubModelsProvider,
    OpenAICompatibleProvider,
)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("SCRIPTRAG_LLM_ENDPOINT", "https://api.openai.com/v1")
    monkeypatch.setenv("SCRIPTRAG_LLM_API_KEY", "test-api-key")


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_custom_provider(self):
        """Test registering a custom provider class."""
        registry = ProviderRegistry()

        class CustomProvider(BaseLLMProvider):
            provider_type = LLMProvider.CLAUDE_CODE

            async def list_models(self):
                return []

            async def complete(self, request):
                pass

            async def embed(self, request):
                pass

            async def is_available(self):
                return True

        registry.register_provider_class(LLMProvider.CLAUDE_CODE, CustomProvider)
        assert LLMProvider.CLAUDE_CODE in registry._custom_providers

    def test_create_provider_custom(self):
        """Test creating a custom provider."""
        registry = ProviderRegistry()

        class CustomProvider(BaseLLMProvider):
            provider_type = LLMProvider.CLAUDE_CODE

            def __init__(self, custom_arg=None):
                self.custom_arg = custom_arg

            async def list_models(self):
                return []

            async def complete(self, request):
                pass

            async def embed(self, request):
                pass

            async def is_available(self):
                return True

        registry.register_provider_class(LLMProvider.CLAUDE_CODE, CustomProvider)
        provider = registry.create_provider(
            LLMProvider.CLAUDE_CODE, custom_arg="test_value"
        )
        assert isinstance(provider, CustomProvider)
        assert provider.custom_arg == "test_value"

    def test_create_provider_default(self):
        """Test creating default providers."""
        registry = ProviderRegistry()

        claude_provider = registry.create_provider(LLMProvider.CLAUDE_CODE)
        assert isinstance(claude_provider, ClaudeCodeProvider)

        github_provider = registry.create_provider(
            LLMProvider.GITHUB_MODELS,
            token="test",  # noqa: S106
        )
        assert isinstance(github_provider, GitHubModelsProvider)

        openai_provider = registry.create_provider(
            LLMProvider.OPENAI_COMPATIBLE,
            endpoint="test",
            api_key="test",  # pragma: allowlist secret
        )
        assert isinstance(openai_provider, OpenAICompatibleProvider)

    def test_create_provider_unknown(self):
        """Test creating unknown provider raises error."""
        registry = ProviderRegistry()

        with pytest.raises(ValueError, match="Unknown provider type"):
            registry.create_provider("unknown_provider")  # type: ignore[arg-type]

    def test_initialize_default_providers(self, mock_env_vars):
        """Test initializing default providers."""
        registry = ProviderRegistry()
        providers = registry.initialize_default_providers(
            github_token="test-token",  # noqa: S106
            openai_endpoint="https://test.com",
            openai_api_key="test-key",  # pragma: allowlist secret
            timeout=60.0,
        )

        assert len(providers) == 3
        assert LLMProvider.CLAUDE_CODE in providers
        assert LLMProvider.GITHUB_MODELS in providers
        assert LLMProvider.OPENAI_COMPATIBLE in providers

    def test_get_set_remove_provider(self):
        """Test getting, setting, and removing providers."""
        registry = ProviderRegistry()
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.provider_type = LLMProvider.CLAUDE_CODE

        # Initially empty
        assert registry.get_provider(LLMProvider.CLAUDE_CODE) is None

        # Set provider
        registry.set_provider(LLMProvider.CLAUDE_CODE, mock_provider)
        assert registry.get_provider(LLMProvider.CLAUDE_CODE) == mock_provider

        # List providers
        providers = registry.list_providers()
        assert LLMProvider.CLAUDE_CODE in providers

        # Remove provider
        registry.remove_provider(LLMProvider.CLAUDE_CODE)
        assert registry.get_provider(LLMProvider.CLAUDE_CODE) is None

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleaning up provider resources."""
        registry = ProviderRegistry()

        # Create mock providers with client attribute
        mock_provider1 = Mock(spec=BaseLLMProvider)
        mock_provider1.provider_type = LLMProvider.GITHUB_MODELS
        mock_client1 = AsyncMock()
        mock_provider1.client = mock_client1

        mock_provider2 = Mock(spec=BaseLLMProvider)
        mock_provider2.provider_type = LLMProvider.OPENAI_COMPATIBLE
        mock_client2 = AsyncMock()
        mock_provider2.client = mock_client2

        registry.set_provider(LLMProvider.GITHUB_MODELS, mock_provider1)
        registry.set_provider(LLMProvider.OPENAI_COMPATIBLE, mock_provider2)

        await registry.cleanup()

        mock_client1.aclose.assert_called_once()
        mock_client2.aclose.assert_called_once()


class TestClaudeCodeProviderExtended:
    """Extended tests for ClaudeCodeProvider."""

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_import_success(self):
        """Test availability when SDK can be imported."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        # Mock the SDK module in sys.modules
        mock_sdk = MagicMock()
        mock_sdk.ClaudeCodeOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_import_error(self):
        """Test availability when SDK import raises exception."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        # Mock SDK import to raise exception
        with (
            patch("builtins.__import__", side_effect=ImportError("Test error")),
            patch.dict("os.environ", {"CLAUDE_SESSION_ID": "test"}, clear=False),
        ):
            result = await provider.is_available()
            assert result is True  # Falls back to env check

    @pytest.mark.asyncio
    async def test_complete_with_mock_sdk(self):
        """Test complete method with mocked SDK."""
        provider = ClaudeCodeProvider()

        # Mock importing the SDK
        mock_sdk = MagicMock()

        # Create a mock AssistantMessage with proper structure
        mock_text_block = Mock()
        mock_text_block.text = "Test response"

        mock_message = Mock()
        mock_message.__class__.__name__ = "AssistantMessage"
        mock_message.content = [
            mock_text_block
        ]  # Content is a list of TextBlock objects

        async def mock_query(*args, **kwargs):
            for msg in [mock_message]:
                yield msg

        mock_sdk.query = mock_query
        mock_sdk.ClaudeCodeOptions = MagicMock
        mock_sdk.Message = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
                system="Be helpful",
            )

            response = await provider.complete(request)

            assert isinstance(response, CompletionResponse)
            assert response.provider == LLMProvider.CLAUDE_CODE
            assert "Test response" in str(response.choices[0]["message"]["content"])

    def test_messages_to_prompt_edge_cases(self):
        """Test message conversion with edge cases."""
        provider = ClaudeCodeProvider()

        # Empty messages
        assert provider._messages_to_prompt([]) == ""

        # Messages without role/content
        messages = [
            {},
            {"role": "unknown"},
            {"content": "no role"},
        ]
        prompt = provider._messages_to_prompt(messages)
        assert "User: " in prompt  # Defaults to user
        assert "no role" in prompt


class TestGitHubModelsProviderExtended:
    """Extended tests for GitHubModelsProvider."""

    @pytest.mark.asyncio
    async def test_is_available_cache_valid(self):
        """Test availability with valid cache."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        provider._availability_cache = True
        provider._cache_timestamp = time.time()  # Recent timestamp

        # Should return cached value without making request
        result = await provider.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_cache_expired(self):
        """Test availability with expired cache."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106
        provider._availability_cache = False
        provider._cache_timestamp = time.time() - 400  # Expired (>300s)

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", return_value=mock_response):
            result = await provider.is_available()
            assert result is True
            assert provider._availability_cache is True

    @pytest.mark.asyncio
    async def test_is_available_exception(self):
        """Test availability when request raises exception."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        with patch.object(
            provider.client, "get", side_effect=httpx.RequestError("Network error")
        ):
            result = await provider.is_available()
            assert result is False
            assert provider._availability_cache is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        async with provider as p:
            assert p is provider

        # Client should be closed after context exit
        # We can't directly test this without a real client, but the method exists

    @pytest.mark.asyncio
    async def test_list_models_error_status(self):
        """Test list models with error status code."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 500

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            # Falls back to static models on error
            assert len(models) == 2  # Static models
            model_ids = {m.id for m in models}
            assert "gpt-4o" in model_ids
            assert "gpt-4o-mini" in model_ids

    @pytest.mark.asyncio
    async def test_list_models_list_format(self):
        """Test list models with list response format."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "friendly_name": "GPT-4o Mini"},
        ]

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            # Falls back to static models or uses cache
            assert len(models) >= 2  # At least static models
            assert any(m.id == "gpt-4o" or "gpt-4o" in m.id for m in models)

    @pytest.mark.asyncio
    async def test_list_models_empty_data(self):
        """Test list models with empty/invalid data format."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = "invalid"  # Not a list or dict

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            # Falls back to static models on invalid data format
            assert len(models) == 2  # Static models
            model_ids = {m.id for m in models}
            assert "gpt-4o" in model_ids
            assert "gpt-4o-mini" in model_ids

    @pytest.mark.asyncio
    async def test_list_models_exception(self):
        """Test list models with exception."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        with patch.object(
            provider.client, "get", side_effect=RuntimeError("Request failed")
        ):
            models = await provider.list_models()
            # Falls back to static models on exception
            assert len(models) == 2  # Static models
            model_ids = {m.id for m in models}
            assert "gpt-4o" in model_ids
            assert "gpt-4o-mini" in model_ids

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        """Test completion with system prompt."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chat-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response"},
                    "finish_reason": "stop",
                }
            ],
        }

        request = CompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            system="Be concise",
            max_tokens=100,
        )

        with patch.object(
            provider.client, "post", return_value=mock_response
        ) as mock_post:
            await provider.complete(request)

            # Check that system message was prepended
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "Be concise"
            assert payload["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_complete_api_error(self):
        """Test completion with API error."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        request = CompletionRequest(
            model="gpt-4", messages=[{"role": "user", "content": "Hello"}]
        )

        with (
            patch.object(provider.client, "post", return_value=mock_response),
            pytest.raises(ValueError, match="GitHub Models API error"),
        ):
            await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_with_dimensions(self):
        """Test embedding with dimensions."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding",
            "data": [{"embedding": [0.1, 0.2]}],
        }

        request = EmbeddingRequest(model="text-embedding", input="test", dimensions=256)

        with patch.object(
            provider.client, "post", return_value=mock_response
        ) as mock_post:
            await provider.embed(request)

            # Check dimensions were included
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["dimensions"] == 256

    @pytest.mark.asyncio
    async def test_embed_api_error(self):
        """Test embedding with API error."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Model not found"

        request = EmbeddingRequest(model="text-embedding", input="test")

        with (
            patch.object(provider.client, "post", return_value=mock_response),
            pytest.raises(ValueError, match="GitHub Models API error"),
        ):
            await provider.embed(request)


class TestOpenAICompatibleProviderExtended:
    """Extended tests for OpenAICompatibleProvider."""

    @pytest.mark.asyncio
    async def test_is_available_cache_valid(self):
        """Test availability with valid cache."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )
        provider._availability_cache = True
        provider._cache_timestamp = time.time()

        result = await provider.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_cache_expired(self):
        """Test availability with expired cache."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )
        provider._availability_cache = False
        provider._cache_timestamp = time.time() - 400

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", return_value=mock_response):
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_exception(self):
        """Test availability when request raises exception."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        with patch.object(
            provider.client, "get", side_effect=httpx.ConnectError("Connection failed")
        ):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        async with provider as p:
            assert p is provider

    @pytest.mark.asyncio
    async def test_list_models_error_status(self):
        """Test list models with error status code."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 403

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_list_models_invalid_format(self):
        """Test list models with invalid response format."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "format"}

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_list_models_exception(self):
        """Test list models with exception."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        with patch.object(
            provider.client, "get", side_effect=RuntimeError("Unexpected error")
        ):
            models = await provider.list_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_complete_with_system(self):
        """Test completion with system message."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "completion-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response"},
                    "finish_reason": "stop",
                }
            ],
        }

        request = CompletionRequest(
            model="gpt-3.5",
            messages=[{"role": "user", "content": "Test"}],
            system="System prompt",
            max_tokens=50,
        )

        with patch.object(
            provider.client, "post", return_value=mock_response
        ) as mock_post:
            await provider.complete(request)

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["messages"][0]["role"] == "system"
            assert payload["max_tokens"] == 50

    @pytest.mark.asyncio
    async def test_complete_api_error(self):
        """Test completion with API error."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        request = CompletionRequest(model="gpt-3.5", messages=[])

        with (
            patch.object(provider.client, "post", return_value=mock_response),
            pytest.raises(ValueError, match="API error"),
        ):
            await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_with_dimensions(self):
        """Test embedding with dimensions."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}

        request = EmbeddingRequest(model="embedding", input="test", dimensions=512)

        with patch.object(
            provider.client, "post", return_value=mock_response
        ) as mock_post:
            await provider.embed(request)

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_embed_api_error(self):
        """Test embedding with API error."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        request = EmbeddingRequest(model="embedding", input="test")

        with (
            patch.object(provider.client, "post", return_value=mock_response),
            pytest.raises(ValueError, match="API error"),
        ):
            await provider.embed(request)


class TestLLMClientExtended:
    """Extended tests for LLMClient."""

    @pytest.mark.asyncio
    async def test_client_with_custom_registry(self):
        """Test client with custom registry."""
        mock_registry = Mock(spec=ProviderRegistry)
        mock_registry.providers = {}

        client = LLMClient(registry=mock_registry)

        assert client.registry is mock_registry
        # Should not call initialize_default_providers when registry is provided
        mock_registry.initialize_default_providers.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_provider_creates_provider(self):
        """Test ensure_provider selects provider when none selected."""
        # Remove PATH to disable Claude Code
        with patch.dict(os.environ, {"PATH": "/tmp/nonexistent"}, clear=False):
            client = LLMClient()
            assert client.current_provider is None

            # Mock a provider as available
            mock_provider = Mock(spec=BaseLLMProvider)
            mock_provider.is_available = AsyncMock(return_value=True)
            mock_provider.provider_type = LLMProvider.GITHUB_MODELS
            client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

            provider = await client.ensure_provider()

            assert provider is mock_provider
            assert client.current_provider is mock_provider

    @pytest.mark.asyncio
    async def test_ensure_provider_uses_existing(self):
        """Test ensure_provider uses existing provider."""
        client = LLMClient()
        mock_provider = Mock(spec=BaseLLMProvider)
        client.current_provider = mock_provider

        provider = await client.ensure_provider()

        assert provider is mock_provider

    @pytest.mark.asyncio
    async def test_list_models_specific_provider(self):
        """Test listing models from specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="model1",
                    name="Model 1",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                )
            ]
        )
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        models = await client.list_models(provider=LLMProvider.GITHUB_MODELS)

        assert len(models) == 1
        assert models[0].id == "model1"
        mock_provider.list_models.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_models_specific_provider_unavailable(self):
        """Test listing models from unavailable specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=False)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        models = await client.list_models(provider=LLMProvider.GITHUB_MODELS)

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_specific_provider_error(self):
        """Test listing models from specific provider with error."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.list_models = AsyncMock(side_effect=RuntimeError("API error"))
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        models = await client.list_models(provider=LLMProvider.GITHUB_MODELS)

        assert models == []

    @pytest.mark.asyncio
    async def test_get_provider_for_model(self):
        """Test getting provider for specific model."""
        client = LLMClient()

        # Mock list_models to return known models
        async def mock_list_models():
            return [
                Model(
                    id="claude-3-opus",
                    name="Claude",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                ),
                Model(
                    id="gpt-4",
                    name="GPT-4",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
            ]

        with patch.object(client, "list_models", side_effect=mock_list_models):
            provider = await client.get_provider_for_model("gpt-4")
            assert provider == LLMProvider.GITHUB_MODELS

            provider = await client.get_provider_for_model("unknown-model")
            assert provider is None

    @pytest.mark.asyncio
    async def test_complete_with_specific_provider(self):
        """Test completion with specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="test",
                model="model",
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello response"},
                        "finish_reason": "stop",
                    }
                ],
                provider=LLMProvider.GITHUB_MODELS,
            )
        )
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        response = await client.complete(
            messages=[{"role": "user", "content": "Hello"}],
            provider=LLMProvider.GITHUB_MODELS,
        )

        assert response.provider == LLMProvider.GITHUB_MODELS
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_with_unavailable_provider(self):
        """Test completion with unavailable specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=False)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        with pytest.raises(RuntimeError, match="not available"):
            await client.complete(
                messages=[{"role": "user", "content": "Hello"}],
                provider=LLMProvider.GITHUB_MODELS,
            )

    @pytest.mark.asyncio
    async def test_complete_fallback_all_fail(self):
        """Test completion fallback when all providers fail."""
        client = LLMClient(
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
            ],
        )

        # Mock providers that are available but fail
        for provider_type in [LLMProvider.CLAUDE_CODE, LLMProvider.GITHUB_MODELS]:
            mock_provider = Mock(spec=BaseLLMProvider)
            mock_provider.is_available = AsyncMock(return_value=True)
            mock_provider.complete = AsyncMock(
                side_effect=RuntimeError("Provider error")
            )
            mock_provider.list_models = AsyncMock(return_value=[])
            client.registry.providers[provider_type] = mock_provider

        with pytest.raises(LLMFallbackError, match="All LLM providers failed"):
            await client.complete(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    async def test_complete_with_model_selection(self):
        """Test completion with automatic model selection."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="model-chat",
                    name="Chat Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
                Model(
                    id="model-embed",
                    name="Embed Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                ),
            ]
        )
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="test",
                model="model-chat",
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello response"},
                        "finish_reason": "stop",
                    }
                ],
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        # Test that it doesn't change the model when already specified
        request = CompletionRequest(
            model="gpt-4",  # Already specified
            messages=[{"role": "user", "content": "Hello"}],
        )

        await client._try_complete_with_provider(mock_provider, request)

        assert request.model == "gpt-4"  # Should NOT be updated when already specified
        mock_provider.complete.assert_called_once()

        # Test that it selects a model when not specified
        request_auto = CompletionRequest(
            model="",  # Empty model to trigger auto-selection
            messages=[{"role": "user", "content": "Hello"}],
        )

        mock_provider.complete.reset_mock()
        await client._try_complete_with_provider(mock_provider, request_auto)

        assert request_auto.model == "model-chat"  # Should be auto-selected
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_with_specific_provider(self):
        """Test embedding with specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                model="embed-model",
                data=[],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            )
        )
        client.registry.providers[LLMProvider.OPENAI_COMPATIBLE] = mock_provider

        response = await client.embed(
            text="test", provider=LLMProvider.OPENAI_COMPATIBLE
        )

        assert response.provider == LLMProvider.OPENAI_COMPATIBLE
        mock_provider.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_with_unavailable_provider(self):
        """Test embedding with unavailable specific provider."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=False)
        client.registry.providers[LLMProvider.OPENAI_COMPATIBLE] = mock_provider

        with pytest.raises(RuntimeError, match="not available"):
            await client.embed(text="test", provider=LLMProvider.OPENAI_COMPATIBLE)

    @pytest.mark.asyncio
    async def test_embed_fallback_all_fail(self):
        """Test embedding fallback when all providers fail."""
        client = LLMClient(
            preferred_provider=LLMProvider.GITHUB_MODELS,
            fallback_order=[LLMProvider.GITHUB_MODELS, LLMProvider.OPENAI_COMPATIBLE],
        )

        # Mock providers that are available but fail
        for provider_type in [LLMProvider.GITHUB_MODELS, LLMProvider.OPENAI_COMPATIBLE]:
            mock_provider = Mock(spec=BaseLLMProvider)
            mock_provider.is_available = AsyncMock(return_value=True)
            mock_provider.embed = AsyncMock(side_effect=RuntimeError("Embed error"))
            mock_provider.list_models = AsyncMock(return_value=[])
            client.registry.providers[provider_type] = mock_provider

        with pytest.raises(LLMFallbackError, match="All LLM providers failed"):
            await client.embed(text="test")

    @pytest.mark.asyncio
    async def test_embed_with_model_selection(self):
        """Test embedding with automatic model selection."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="model-chat",
                    name="Chat Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
                Model(
                    id="model-embed",
                    name="Embed Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                ),
            ]
        )
        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                model="model-embed",
                data=[],
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        request = EmbeddingRequest(
            model="text-embedding-ada-002",  # Temporary fallback
            input="test",
        )

        await client._try_embed_with_provider(mock_provider, request)

        assert request.model == "model-embed"  # Should be updated
        mock_provider.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup method."""
        client = LLMClient()

        mock_cleanup = AsyncMock()
        client.registry.cleanup = mock_cleanup

        await client.cleanup()

        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        client = LLMClient()

        mock_cleanup = AsyncMock()
        client.cleanup = mock_cleanup

        async with client as c:
            assert c is client

        mock_cleanup.assert_called_once()


class AsyncMockIterator:
    """Helper class for mocking async iterators."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)
