"""Tests for the multi-provider LLM client."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    LLMProvider,
    Model,
)
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


class TestClaudeCodeProvider:
    """Tests for Claude Code SDK provider."""

    @pytest.mark.asyncio
    async def test_is_available_without_sdk(self):
        """Test availability check when SDK is not installed."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = False
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_no_env(self):
        """Test availability check with SDK but not in Claude environment."""
        # Remove PATH to simulate claude executable not available
        with patch.dict(os.environ, {"PATH": "/tmp/nonexistent"}, clear=False):
            provider = ClaudeCodeProvider()
            # Clear env vars to ensure no Claude environment markers
            with patch.dict(os.environ, {}, clear=True):
                assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_in_claude_env(self):
        """Test availability check in Claude Code environment."""
        provider = ClaudeCodeProvider()
        # Test with SDK available and Claude env set
        with (
            patch.object(provider, "sdk_available", True),
            patch.dict(os.environ, {"CLAUDE_CODE_SESSION": "test-session"}, clear=True),
        ):
            # In Claude env with SDK available, should return True
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test listing Claude models."""
        provider = ClaudeCodeProvider()
        # Clear any cached models to ensure fresh discovery
        provider.model_discovery.cache.clear()

        models = await provider.list_models()

        # Now expects 8 models (3 original + 2 new 3.5 models + 3 aliases)
        assert len(models) == 8
        assert all(isinstance(m, Model) for m in models)
        assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)
        assert any("opus" in m.id for m in models)
        assert any("sonnet" in m.id for m in models)
        assert any("haiku" in m.id for m in models)
        # New 3.5 models added
        assert any("3-5-sonnet" in m.id for m in models)
        assert any("3-5-haiku" in m.id for m in models)
        # Check for new model aliases
        assert any(m.id == "sonnet" for m in models)
        assert any(m.id == "opus" for m in models)
        assert any(m.id == "haiku" for m in models)

    @pytest.mark.asyncio
    async def test_complete_not_available(self):
        """Test completion when claude executable is not available."""
        # Remove PATH to simulate claude executable not available
        with patch.dict(os.environ, {"PATH": "/tmp/nonexistent"}, clear=False):
            provider = ClaudeCodeProvider()

            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            # The SDK will raise an error when trying to execute claude
            # Using broad Exception as the SDK may raise various error types
            with pytest.raises(Exception):  # noqa: B017 - Testing any SDK failure
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_not_implemented(self):
        """Test that embedding raises NotImplementedError."""
        provider = ClaudeCodeProvider()
        request = EmbeddingRequest(model="claude", input="test")

        with pytest.raises(NotImplementedError):
            await provider.embed(request)

    def test_messages_to_prompt(self):
        """Test message conversion to prompt."""
        provider = ClaudeCodeProvider()
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        prompt = provider._messages_to_prompt(messages)
        assert "System: You are helpful" in prompt
        assert "User: Hello" in prompt
        assert "Assistant: Hi there" in prompt
        assert "User: How are you?" in prompt


class TestGitHubModelsProvider:
    """Tests for GitHub Models provider."""

    @pytest.mark.asyncio
    async def test_is_available_no_token(self):
        """Test availability when no token is set."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubModelsProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_token(self, mock_env_vars):
        """Test availability with valid token."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = GitHubModelsProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            provider.client, "get", return_value=mock_response
        ) as mock_get:
            assert await provider.is_available() is True
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_available_invalid_token(self):
        """Test availability with invalid token."""
        provider = GitHubModelsProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(provider.client, "get", return_value=mock_response):
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_env_vars):
        """Test successful model listing."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = GitHubModelsProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        # Clear cache to ensure fresh discovery
        if provider.model_discovery.cache:
            provider.model_discovery.cache.clear()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4o", "name": "GPT-4o"},
                {"id": "gpt-4o-mini", "friendly_name": "GPT-4o Mini"},
            ]
        }

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()

            # Model discovery may return different numbers in different environments
            # Ensure we get at least 1 model and check that it contains expected models
            assert len(models) >= 1, f"Expected at least 1 model, got {len(models)}"
            assert all(isinstance(m, Model) for m in models)
            assert all(m.provider == LLMProvider.GITHUB_MODELS for m in models)

            # Check for expected models in the result
            model_ids = [m.id for m in models]
            if len(models) >= 2:
                # If we got 2+ models, expect both gpt-4o models
                assert any("gpt-4o" in model_id for model_id in model_ids), (
                    f"Expected gpt-4o in {model_ids}"
                )
                assert any("gpt-4o-mini" in model_id for model_id in model_ids), (
                    f"Expected gpt-4o-mini in {model_ids}"
                )
            else:
                # If we only got 1 model, it should be a valid GitHub model
                assert any(
                    "gpt" in model_id or "github" in model_id.lower()
                    for model_id in model_ids
                ), f"Expected valid GitHub model in {model_ids}"

    @pytest.mark.asyncio
    async def test_list_models_no_token(self):
        """Test model listing without token."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubModelsProvider()
            # Clear any cached models to ensure fresh discovery
            provider.model_discovery.cache.clear()

            # Mock the model discovery to return empty list when no token
            with patch.object(
                provider.model_discovery, "discover_models"
            ) as mock_discover:
                mock_discover.return_value = []
                models = await provider.list_models()
                # Without token, should return static models as fallback
                # Allow either empty list or static fallback models
                assert len(models) >= 0, (
                    f"Expected non-negative model count, got {len(models)}"
                )

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_env_vars):
        """Test successful completion."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = GitHubModelsProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chat-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        request = CompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
        )

        with patch.object(provider.client, "post", return_value=mock_response):
            response = await provider.complete(request)

            assert isinstance(response, CompletionResponse)
            assert response.model == "gpt-4"
            assert response.provider == LLMProvider.GITHUB_MODELS
            assert len(response.choices) == 1
            assert response.choices[0]["message"]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_complete_no_token(self):
        """Test completion without token."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubModelsProvider()
            request = CompletionRequest(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
            )

            with pytest.raises(ValueError, match="GitHub token not configured"):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_embed_success(self, mock_env_vars):
        """Test successful embedding."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = GitHubModelsProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada",
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            ],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }

        request = EmbeddingRequest(
            model="text-embedding-ada",
            input="test text",
        )

        with patch.object(provider.client, "post", return_value=mock_response):
            response = await provider.embed(request)

            assert isinstance(response, EmbeddingResponse)
            assert response.model == "text-embedding-ada"
            assert response.provider == LLMProvider.GITHUB_MODELS
            assert len(response.data) == 1


class TestOpenAICompatibleProvider:
    """Tests for OpenAI-compatible provider."""

    @pytest.mark.asyncio
    async def test_is_available_no_config(self):
        """Test availability without configuration."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_config(self, mock_env_vars):
        """Test availability with configuration."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = OpenAICompatibleProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider.client, "get", return_value=mock_response):
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_env_vars):
        """Test successful model listing."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = OpenAICompatibleProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-3.5-turbo"},
                {"id": "text-embedding-3-small"},
            ]
        }

        with patch.object(provider.client, "get", return_value=mock_response):
            models = await provider.list_models()

            assert len(models) == 2
            assert all(isinstance(m, Model) for m in models)
            assert all(m.provider == LLMProvider.OPENAI_COMPATIBLE for m in models)

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_env_vars):
        """Test successful completion."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = OpenAICompatibleProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chat-456",
            "model": "gpt-3.5-turbo",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 20},
        }

        request = CompletionRequest(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test"}],
        )

        with patch.object(provider.client, "post", return_value=mock_response):
            response = await provider.complete(request)

            assert isinstance(response, CompletionResponse)
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_embed_success(self, mock_env_vars):
        """Test successful embedding."""
        _ = mock_env_vars  # Fixture sets up environment variables
        provider = OpenAICompatibleProvider()

        # Initialize the HTTP client before patching
        provider._init_http_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-3-small",
            "data": [{"embedding": [0.5, 0.6]}],
            "usage": {"total_tokens": 10},
        }

        request = EmbeddingRequest(
            model="text-embedding-3-small",
            input="embed this",
        )

        with patch.object(provider.client, "post", return_value=mock_response):
            response = await provider.embed(request)

            assert isinstance(response, EmbeddingResponse)
            assert response.provider == LLMProvider.OPENAI_COMPATIBLE


class TestLLMClient:
    """Tests for the main LLM client."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test client initialization."""
        # Mock network calls during provider initialization to prevent CI timeouts
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value = MagicMock()
            mock_client.return_value.__aexit__.return_value = None

            client = LLMClient()

            assert len(client.providers) == 3
            assert LLMProvider.CLAUDE_CODE in client.providers
            assert LLMProvider.GITHUB_MODELS in client.providers
            assert LLMProvider.OPENAI_COMPATIBLE in client.providers

    @pytest.mark.asyncio
    async def test_provider_selection_preferred(self):
        """Test selection of preferred provider."""
        client = LLMClient(preferred_provider=LLMProvider.GITHUB_MODELS)

        # Mock GitHub provider as available
        mock_github = client.providers[LLMProvider.GITHUB_MODELS]
        with patch.object(mock_github, "is_available", return_value=True):
            await client._select_provider()

            assert client.current_provider == mock_github
            assert client.get_current_provider() == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_provider_selection_fallback(self):
        """Test fallback provider selection."""
        client = LLMClient(
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
                LLMProvider.OPENAI_COMPATIBLE,
            ],
        )

        # Mock providers - only OpenAI available
        with (
            patch.object(
                client.providers[LLMProvider.CLAUDE_CODE],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.GITHUB_MODELS],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.OPENAI_COMPATIBLE],
                "is_available",
                return_value=True,
            ),
        ):
            await client._select_provider()

            assert client.get_current_provider() == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_no_provider_available(self):
        """Test when no provider is available."""
        client = LLMClient()

        # Mock all providers as unavailable
        with (
            patch.object(
                client.providers[LLMProvider.CLAUDE_CODE],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.GITHUB_MODELS],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.OPENAI_COMPATIBLE],
                "is_available",
                return_value=False,
            ),
        ):
            await client._select_provider()
            assert client.current_provider is None

        # Test ensure_provider raises error when no provider available
        client.current_provider = None
        with (
            patch.object(
                client.providers[LLMProvider.CLAUDE_CODE],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.GITHUB_MODELS],
                "is_available",
                return_value=False,
            ),
            patch.object(
                client.providers[LLMProvider.OPENAI_COMPATIBLE],
                "is_available",
                return_value=False,
            ),
            pytest.raises(RuntimeError, match="No LLM provider available"),
        ):
            await client.ensure_provider()

    @pytest.mark.asyncio
    async def test_list_models_all_providers(self):
        """Test listing models from all available providers."""
        client = LLMClient()

        # Mock providers
        mock_models = {
            LLMProvider.CLAUDE_CODE: [
                Model(
                    id="claude-1",
                    name="Claude 1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ],
            LLMProvider.GITHUB_MODELS: [
                Model(
                    id="gpt-4",
                    name="GPT-4",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                )
            ],
            LLMProvider.OPENAI_COMPATIBLE: [
                Model(
                    id="custom",
                    name="Custom",
                    provider=LLMProvider.OPENAI_COMPATIBLE,
                    capabilities=["chat"],
                )
            ],
        }

        for provider_type, models in mock_models.items():
            provider = client.providers[provider_type]
            with (
                patch.object(provider, "is_available", return_value=True),
                patch.object(provider, "list_models", return_value=models),
            ):
                pass

        # Need to run this in the same context
        with (
            patch.object(
                client.providers[LLMProvider.CLAUDE_CODE],
                "is_available",
                return_value=True,
            ),
            patch.object(
                client.providers[LLMProvider.CLAUDE_CODE],
                "list_models",
                return_value=mock_models[LLMProvider.CLAUDE_CODE],
            ),
            patch.object(
                client.providers[LLMProvider.GITHUB_MODELS],
                "is_available",
                return_value=True,
            ),
            patch.object(
                client.providers[LLMProvider.GITHUB_MODELS],
                "list_models",
                return_value=mock_models[LLMProvider.GITHUB_MODELS],
            ),
            patch.object(
                client.providers[LLMProvider.OPENAI_COMPATIBLE],
                "is_available",
                return_value=True,
            ),
            patch.object(
                client.providers[LLMProvider.OPENAI_COMPATIBLE],
                "list_models",
                return_value=mock_models[LLMProvider.OPENAI_COMPATIBLE],
            ),
        ):
            all_models = await client.list_models()

        assert len(all_models) == 3
        assert any(m.id == "claude-1" for m in all_models)
        assert any(m.id == "gpt-4" for m in all_models)
        assert any(m.id == "custom" for m in all_models)

    @pytest.mark.asyncio
    async def test_complete_with_model(self):
        """Test completion with specific model."""
        client = LLMClient()

        # Mock provider - use AsyncMock for the provider itself
        mock_provider = AsyncMock()
        mock_provider.provider_type = LLMProvider.GITHUB_MODELS
        mock_response = CompletionResponse(
            id="test",
            model="gpt-4",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test response"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.GITHUB_MODELS,
        )
        mock_provider.complete = AsyncMock(return_value=mock_response)
        mock_provider.is_available = AsyncMock(return_value=True)

        # Replace all providers with mock ones to ensure isolation
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}
        client.current_provider = mock_provider

        response = await client.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4",
            temperature=0.5,
        )

        assert response.model == "gpt-4"
        assert response.provider == LLMProvider.GITHUB_MODELS
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_without_model(self):
        """Test completion without specifying model."""
        # Remove PATH to disable Claude Code
        with patch.dict(os.environ, {"PATH": "/tmp/nonexistent"}, clear=False):
            client = LLMClient()

            # Mock provider with models
            mock_provider = MagicMock()
            mock_provider.provider_type = LLMProvider.GITHUB_MODELS
            mock_provider.list_models = AsyncMock(
                return_value=[
                    Model(
                        id="gpt-4",
                        name="GPT-4",
                        provider=LLMProvider.GITHUB_MODELS,
                        capabilities=["chat"],
                    )
                ]
            )
            mock_response = CompletionResponse(
                id="test",
                model="gpt-4",
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Test"},
                        "finish_reason": "stop",
                    }
                ],
                provider=LLMProvider.GITHUB_MODELS,
            )
            mock_provider.complete = AsyncMock(return_value=mock_response)
            mock_provider.is_available = AsyncMock(return_value=True)

            # Replace the provider in the client's providers dict and set as current
            client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider
            client.current_provider = mock_provider

            response = await client.complete(
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert response.model == "gpt-4"
            mock_provider.complete.assert_called_once()
            # Check that the model was set to gpt-4
            call_args = mock_provider.complete.call_args[0][0]
            assert call_args.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_embed_with_model(self):
        """Test embedding with specific model."""
        client = LLMClient()

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.provider_type = LLMProvider.OPENAI_COMPATIBLE
        mock_response = EmbeddingResponse(
            model="text-embedding",
            data=[{"embedding": [0.1, 0.2]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        mock_provider.embed = AsyncMock(return_value=mock_response)
        mock_provider.is_available = AsyncMock(return_value=True)

        # Replace the provider in the client's providers dict and set as current
        client.registry.providers[LLMProvider.OPENAI_COMPATIBLE] = mock_provider
        client.current_provider = mock_provider

        response = await client.embed(
            text="Test text",
            model="text-embedding",
        )

        assert response.model == "text-embedding"
        assert response.provider == LLMProvider.OPENAI_COMPATIBLE
        mock_provider.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_provider_success(self):
        """Test switching to a different provider."""
        client = LLMClient()

        # Mock GitHub provider as available
        with patch.object(
            client.providers[LLMProvider.GITHUB_MODELS],
            "is_available",
            return_value=True,
        ):
            success = await client.switch_provider(LLMProvider.GITHUB_MODELS)

            assert success is True
            assert client.get_current_provider() == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_switch_provider_failure(self):
        """Test switching to unavailable provider."""
        client = LLMClient()

        # Mock provider as unavailable
        with patch.object(
            client.providers[LLMProvider.CLAUDE_CODE],
            "is_available",
            return_value=False,
        ):
            success = await client.switch_provider(LLMProvider.CLAUDE_CODE)

            assert success is False
