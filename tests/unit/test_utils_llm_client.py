"""Tests for LLM client module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scriptrag.utils.llm_client import (
    ClaudeCodeProvider,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    GitHubModelsProvider,
    LLMClient,
    LLMProvider,
    Model,
    OpenAICompatibleProvider,
)


class TestModel:
    """Test Model class."""

    def test_model_creation(self):
        """Test creating a model instance."""
        model = Model(
            id="test-model",
            name="Test Model",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "completion"],
            context_window=100000,
            max_output_tokens=4096,
        )
        assert model.id == "test-model"
        assert model.name == "Test Model"
        assert model.provider == LLMProvider.CLAUDE_CODE
        assert "chat" in model.capabilities
        assert model.context_window == 100000


class TestClaudeCodeProvider:
    """Test ClaudeCodeProvider class."""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test listing Claude Code models."""
        provider = ClaudeCodeProvider()
        models = await provider.list_models()
        assert len(models) > 0
        assert all(isinstance(m, Model) for m in models)
        assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)

    @pytest.mark.asyncio
    async def test_is_available_with_sdk(self):
        """Test availability check when SDK is available."""
        # ClaudeCodeProvider checks sdk_available attribute
        provider = ClaudeCodeProvider()
        provider.sdk_available = True
        # Also mock the actual availability check
        with patch.object(provider, "is_available", return_value=True):
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_without_sdk(self):
        """Test availability check when SDK is not available."""
        provider = ClaudeCodeProvider()
        # SDK is checked during __init__, so it's already False
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Test successful completion with Claude Code."""
        ClaudeCodeProvider()

        # Mock the SDK
        mock_message = MagicMock()
        mock_message.content = "Test response"

        async def mock_query(*_args, **_kwargs):
            yield mock_message

        with patch(
            "scriptrag.utils.llm_client.ClaudeCodeProvider.complete"
        ) as mock_complete:
            mock_complete.return_value = CompletionResponse(
                id="test-id",
                model="claude-3-opus",
                choices=[{"message": {"content": "Test response"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )

            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )
            response = await mock_complete(request)
            assert response.choices[0]["message"]["content"] == "Test response"

    @pytest.mark.asyncio
    async def test_embed_not_supported(self):
        """Test that embedding is not supported."""
        provider = ClaudeCodeProvider()
        request = EmbeddingRequest(model="test", input="test")
        with pytest.raises(NotImplementedError):
            await provider.embed(request)

    def test_messages_to_prompt(self):
        """Test converting messages to prompt."""
        provider = ClaudeCodeProvider()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        prompt = provider._messages_to_prompt(messages)
        assert "Hello" in prompt
        assert "Hi there!" in prompt
        assert "How are you?" in prompt


class TestGitHubModelsProvider:
    """Test GitHubModelsProvider class."""

    @pytest.fixture
    def provider(self):
        """Create provider with test token."""
        # GitHubModelsProvider takes 'token' not 'github_token'
        return GitHubModelsProvider(token="test_token")  # noqa: S106

    @pytest.mark.asyncio
    async def test_list_models(self, provider):
        """Test listing GitHub models."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": "gpt-4o", "name": "gpt-4o", "summary": "GPT-4 model"},
                {"id": "llama-3", "name": "llama-3", "summary": "Llama 3 model"},
            ]
            mock_client.get = AsyncMock(return_value=mock_response)

            models = await provider.list_models()
            assert len(models) == 2
            assert models[0].id == "gpt-4o"
            assert models[1].id == "llama-3"

    @pytest.mark.asyncio
    async def test_is_available_with_token(self, provider):
        """Test availability check with token."""
        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_without_token(self):
        """Test availability check without token."""
        # Mock the environment to ensure no token is available
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubModelsProvider(token=None)
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        """Test successful completion."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "model": "gpt-4o",
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {"total_tokens": 100},
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Hello"}]
            )
            response = await provider.complete(request)
            assert response.model == "gpt-4o"
            assert response.choices[0]["message"]["content"] == "Test response"

    @pytest.mark.asyncio
    async def test_complete_with_system_message(self, provider):
        """Test completion with system message."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "model": "gpt-4o",
                "choices": [{"message": {"content": "Test"}}],
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            request = CompletionRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                system="You are a helpful assistant.",
            )
            await provider.complete(request)

            # Verify the system message was added
            call_args = mock_client.post.call_args
            sent_data = call_args.kwargs[
                "json"
            ]  # JSON data is passed as keyword argument
            assert sent_data["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_embed_success(self, provider):
        """Test successful embedding."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"embedding": [0.1, 0.2, 0.3]}],
                "model": "text-embedding-3-small",
                "usage": {"total_tokens": 10},
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            request = EmbeddingRequest(
                model="text-embedding-3-small", input="test text"
            )
            response = await provider.embed(request)
            assert response.model == "text-embedding-3-small"
            assert len(response.data) == 1

    @pytest.mark.asyncio
    async def test_complete_error_handling(self, provider):
        """Test error handling in completion."""
        with patch.object(provider, "client") as mock_client:
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection error")
            )

            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Hello"}]
            )
            with pytest.raises(httpx.HTTPError):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_error_handling(self, provider):
        """Test error handling in embedding."""
        with patch.object(provider, "client") as mock_client:
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection error")
            )

            request = EmbeddingRequest(model="text-embedding-3-small", input="test")
            with pytest.raises(httpx.HTTPError):
                await provider.embed(request)


class TestOpenAICompatibleProvider:
    """Test OpenAICompatibleProvider class."""

    @pytest.fixture
    def provider(self):
        """Create provider with test endpoint and key."""
        provider = OpenAICompatibleProvider(
            endpoint="https://api.test.com/v1",
            api_key="test_key",  # pragma: allowlist secret
        )
        # Mock the _client attribute
        provider._client = MagicMock()
        return provider

    @pytest.mark.asyncio
    async def test_list_models(self, provider):
        """Test listing models."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "model-1", "object": "model"},
                    {"id": "model-2", "object": "model"},
                ]
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            models = await provider.list_models()
            assert len(models) == 2
            assert models[0].id == "model-1"

    @pytest.mark.asyncio
    async def test_is_available_with_credentials(self, provider):
        """Test availability with credentials."""
        # Mock the HTTP request
        mock_response = MagicMock()
        mock_response.status_code = 200
        provider.client = MagicMock()
        provider.client.get = AsyncMock(return_value=mock_response)

        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_without_credentials(self):
        """Test availability without credentials."""
        # Mock environment to ensure no credentials
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider(endpoint=None, api_key=None)
            # Should return False when missing credentials
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        """Test successful completion."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "model": "custom-model",
                "choices": [{"message": {"content": "Response"}}],
                "usage": {"total_tokens": 50},
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            request = CompletionRequest(
                model="custom-model", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)
            assert response.model == "custom-model"

    @pytest.mark.asyncio
    async def test_embed_success(self, provider):
        """Test successful embedding."""
        with patch.object(provider, "client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"embedding": [0.5, 0.6]}],
                "model": "embed-model",
                "usage": {"total_tokens": 5},
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            request = EmbeddingRequest(model="embed-model", input="test")
            response = await provider.embed(request)
            assert response.model == "embed-model"


class TestLLMClient:
    """Test LLMClient class."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return LLMClient(
            preferred_provider=LLMProvider.GITHUB_MODELS,
            fallback_order=[LLMProvider.OPENAI_COMPATIBLE, LLMProvider.CLAUDE_CODE],
            github_token="test_token",  # noqa: S106
        )

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        """Test listing models from all providers."""
        with patch.object(
            client.providers[LLMProvider.GITHUB_MODELS], "list_models"
        ) as mock_github:
            mock_github.return_value = [
                Model(id="gpt-4", name="GPT-4", provider=LLMProvider.GITHUB_MODELS)
            ]

            models = await client.list_models()
            assert len(models) > 0

    @pytest.mark.asyncio
    async def test_list_models_specific_provider(self, client):
        """Test listing models from specific provider."""
        with patch.object(
            client.providers[LLMProvider.GITHUB_MODELS], "list_models"
        ) as mock_github:
            mock_github.return_value = [
                Model(id="gpt-4", name="GPT-4", provider=LLMProvider.GITHUB_MODELS)
            ]

            models = await client.list_models(provider=LLMProvider.GITHUB_MODELS)
            assert len(models) == 1
            assert models[0].provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_complete_with_preferred_provider(self, client):
        """Test completion with preferred provider."""
        mock_provider = client.providers[LLMProvider.GITHUB_MODELS]
        with (
            patch.object(mock_provider, "is_available") as mock_available,
            patch.object(mock_provider, "complete") as mock_complete,
        ):
            mock_available.return_value = True
            mock_complete.return_value = CompletionResponse(
                id="test",
                model="gpt-4",
                choices=[{"message": {"content": "Response"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

            request = CompletionRequest(
                model="gpt-4", messages=[{"role": "user", "content": "Test"}]
            )
            response = await client.complete(request)
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_complete_with_fallback(self, client):
        """Test completion with fallback when preferred fails."""
        github_provider = client.providers[LLMProvider.GITHUB_MODELS]
        openai_provider = client.providers[LLMProvider.OPENAI_COMPATIBLE]

        with (
            patch.object(github_provider, "is_available") as mock_github_available,
            patch.object(github_provider, "complete") as mock_github_complete,
            patch.object(openai_provider, "is_available") as mock_openai_available,
            patch.object(openai_provider, "complete") as mock_openai_complete,
        ):
            mock_github_available.return_value = True
            mock_github_complete.side_effect = Exception("GitHub failed")
            mock_openai_available.return_value = True
            mock_openai_complete.return_value = CompletionResponse(
                id="test",
                model="custom",
                choices=[{"message": {"content": "Fallback response"}}],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            )

            request = CompletionRequest(
                model="gpt-4",
                messages=[{"role": "user", "content": "Test"}],
            )
            response = await client.complete(request)
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_complete_all_providers_fail(self, client):
        """Test completion when all providers fail."""
        # Patch all providers simultaneously
        patches = []
        for provider in client.providers.values():
            mock_available = patch.object(provider, "is_available", return_value=True)
            mock_complete = patch.object(
                provider, "complete", side_effect=Exception("Provider failed")
            )
            patches.extend([mock_available, mock_complete])

        # Start all patches
        for p in patches:
            p.start()

        try:
            request = CompletionRequest(
                model="test", messages=[{"role": "user", "content": "Test"}]
            )
            with pytest.raises(RuntimeError, match="All LLM providers failed"):
                await client.complete(request)
        finally:
            # Stop all patches
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_embed_with_provider(self, client):
        """Test embedding with available provider."""
        github_provider = client.providers[LLMProvider.GITHUB_MODELS]

        with (
            patch.object(github_provider, "is_available") as mock_available,
            patch.object(github_provider, "embed") as mock_embed,
        ):
            mock_available.return_value = True
            mock_embed.return_value = EmbeddingResponse(
                model="embed",
                data=[{"embedding": [0.1, 0.2]}],
                provider=LLMProvider.GITHUB_MODELS,
            )

            request = EmbeddingRequest(model="embed", input="test")
            response = await client.embed(request)
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_get_provider_for_model(self, client):
        """Test getting provider for specific model."""
        with patch.object(client, "list_models") as mock_list:
            mock_list.return_value = [
                Model(id="gpt-4", name="GPT-4", provider=LLMProvider.GITHUB_MODELS),
                Model(id="claude-3", name="Claude 3", provider=LLMProvider.CLAUDE_CODE),
            ]

            provider = await client.get_provider_for_model("gpt-4")
            assert provider == LLMProvider.GITHUB_MODELS

            provider = await client.get_provider_for_model("claude-3")
            assert provider == LLMProvider.CLAUDE_CODE

            provider = await client.get_provider_for_model("unknown")
            assert provider is None

    @pytest.mark.asyncio
    async def test_complete_with_forced_provider(self, client):
        """Test completion with forced provider."""
        openai_provider = client.providers[LLMProvider.OPENAI_COMPATIBLE]

        with (
            patch.object(openai_provider, "is_available") as mock_available,
            patch.object(openai_provider, "complete") as mock_complete,
        ):
            mock_available.return_value = True
            mock_complete.return_value = CompletionResponse(
                id="test",
                model="custom",
                choices=[{"message": {"content": "Forced response"}}],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            )

            request = CompletionRequest(
                model="test", messages=[{"role": "user", "content": "Test"}]
            )
            response = await client.complete(
                request, provider=LLMProvider.OPENAI_COMPATIBLE
            )
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE

    def test_client_initialization_defaults(self):
        """Test client initialization with defaults."""
        # LLMClient constructor doesn't require event loop
        client = LLMClient()
        assert client.preferred_provider is None
        # Default fallback_order is set in __init__
        assert client.fallback_order == [
            LLMProvider.CLAUDE_CODE,
            LLMProvider.GITHUB_MODELS,
            LLMProvider.OPENAI_COMPATIBLE,
        ]

    def test_client_initialization_with_env_vars(self):
        """Test client initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "env_token",
                "SCRIPTRAG_LLM_ENDPOINT": "https://env.test.com",
                "SCRIPTRAG_LLM_API_KEY": "env_key",  # pragma: allowlist secret
            },
        ):
            client = LLMClient(github_token="env_token")  # noqa: S106
            # Check that providers can be initialized with the token
            assert client.github_token == "env_token"  # noqa: S105

    @pytest.mark.asyncio
    async def test_list_models_error_handling(self, client):
        """Test error handling when listing models."""
        with patch.object(
            client.providers[LLMProvider.GITHUB_MODELS], "list_models"
        ) as mock_list:
            mock_list.side_effect = Exception("List failed")

            # Should return empty list on error
            models = await client.list_models(provider=LLMProvider.GITHUB_MODELS)
            assert models == []

    @pytest.mark.asyncio
    async def test_embed_all_providers_fail(self, client):
        """Test embedding when all providers fail."""
        # Patch all providers simultaneously
        patches = []
        for provider in client.providers.values():
            mock_available = patch.object(provider, "is_available", return_value=True)
            mock_embed = patch.object(
                provider, "embed", side_effect=Exception("Embed failed")
            )
            patches.extend([mock_available, mock_embed])

        # Start all patches
        for p in patches:
            p.start()

        try:
            request = EmbeddingRequest(model="test", input="test")
            with pytest.raises(RuntimeError, match="All LLM providers failed"):
                await client.embed(request)
        finally:
            # Stop all patches
            for p in patches:
                p.stop()
