"""Additional tests for LLM client module with REAL methods only."""

from unittest.mock import AsyncMock, patch

import pytest

from scriptrag.exceptions import LLMProviderError
from scriptrag.llm import LLMProvider
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    Model,
)


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = AsyncMock(spec=object)
    provider.name = "TestProvider"
    provider.is_available = AsyncMock(return_value=True)
    provider.complete = AsyncMock(
        return_value=CompletionResponse(
            id="test-response-id",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "test response"},
                    "finish_reason": "stop",
                }
            ],
            model="test-model",
            usage={"total_tokens": 10},
            provider=LLMProvider.GITHUB_MODELS,
        )
    )
    provider.embed = AsyncMock(
        return_value=EmbeddingResponse(
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            model="embed-model",
            provider=LLMProvider.GITHUB_MODELS,
        )
    )
    provider.list_models = AsyncMock(
        return_value=[
            Model(
                id="test-model",
                name="Test Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion"],
            )
        ]
    )
    return provider


class TestLLMClientAdditionalCoverage:
    """Additional test cases for achieving 99% coverage."""

    @pytest.mark.asyncio
    async def test_get_current_provider(self, mock_provider):
        """Test get_current_provider method."""
        client = LLMClient()

        # Initially no provider selected
        assert client.get_current_provider() is None

        # After setting current provider
        client.current_provider = mock_provider
        mock_provider.provider_type = LLMProvider.GITHUB_MODELS
        assert client.get_current_provider() == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_provider):
        """Test async context manager functionality."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Mock cleanup
        cleanup_mock = AsyncMock(spec=object)
        client.cleanup = cleanup_mock

        # Test async context manager
        async with client:
            pass

        cleanup_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_provider_with_unavailable_preferred(self, mock_provider):
        """Test provider selection when preferred is unavailable."""
        unavailable_provider = AsyncMock(spec=object)
        unavailable_provider.is_available = AsyncMock(return_value=False)

        client = LLMClient(
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[LLMProvider.GITHUB_MODELS],
        )

        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: unavailable_provider,
            LLMProvider.GITHUB_MODELS: mock_provider,
        }

        await client._select_provider()
        assert client.current_provider == mock_provider

    @pytest.mark.asyncio
    async def test_ensure_provider_already_selected(self, mock_provider):
        """Test ensure_provider when provider is already selected."""
        client = LLMClient()
        client.current_provider = mock_provider

        result = await client.ensure_provider()
        assert result == mock_provider

    @pytest.mark.asyncio
    async def test_list_models_specific_provider_unavailable(self, mock_provider):
        """Test list_models with specific unavailable provider."""
        unavailable_provider = AsyncMock(spec=object)
        unavailable_provider.is_available = AsyncMock(return_value=False)

        client = LLMClient()
        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: unavailable_provider,
            LLMProvider.GITHUB_MODELS: mock_provider,
        }

        models = await client.list_models(provider=LLMProvider.CLAUDE_CODE)
        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_specific_provider_error(self, mock_provider):
        """Test list_models with specific provider that raises error."""
        error_provider = AsyncMock(spec=object)
        error_provider.is_available = AsyncMock(return_value=True)
        error_provider.list_models = AsyncMock(side_effect=RuntimeError("API error"))

        client = LLMClient()
        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: error_provider,
            LLMProvider.GITHUB_MODELS: mock_provider,
        }

        models = await client.list_models(provider=LLMProvider.CLAUDE_CODE)
        assert models == []

    @pytest.mark.asyncio
    async def test_get_provider_for_model_found(self, mock_provider):
        """Test get_provider_for_model when model is found."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        provider = await client.get_provider_for_model("test-model")
        assert provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_get_provider_for_model_not_found(self, mock_provider):
        """Test get_provider_for_model when model is not found."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        provider = await client.get_provider_for_model("nonexistent-model")
        assert provider is None

    @pytest.mark.asyncio
    async def test_complete_provider_error_fallback(self):
        """Test complete with provider error triggering fallback."""
        error_provider = AsyncMock(spec=object)
        error_provider.is_available = AsyncMock(return_value=True)
        error_provider.complete = AsyncMock(side_effect=RuntimeError("API error"))

        fallback_provider = AsyncMock(spec=object)
        fallback_provider.is_available = AsyncMock(return_value=True)
        fallback_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="fallback-response-id",
                choices=[
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "fallback response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                model="fallback-model",
                usage={"total_tokens": 5},
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        client = LLMClient(
            fallback_order=[LLMProvider.CLAUDE_CODE, LLMProvider.GITHUB_MODELS]
        )
        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: error_provider,
            LLMProvider.GITHUB_MODELS: fallback_provider,
        }

        # Mock the fallback handler to use our providers
        with patch.object(
            client.fallback_handler,
            "complete_with_fallback",
            new=AsyncMock(
                return_value=CompletionResponse(
                    id="fallback-response-id",
                    choices=[
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "fallback response",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    model="fallback-model",
                    usage={"total_tokens": 5},
                    provider=LLMProvider.GITHUB_MODELS,
                )
            ),
        ):
            response = await client.complete(
                [{"role": "user", "content": "test prompt"}]
            )
            assert response.content == "fallback response"

    @pytest.mark.asyncio
    async def test_complete_all_providers_fail(self):
        """Test complete when all providers fail."""
        error_provider1 = AsyncMock(spec=object)
        error_provider1.is_available = AsyncMock(return_value=True)
        error_provider1.complete = AsyncMock(
            side_effect=LLMProviderError("API error 1")
        )

        error_provider2 = AsyncMock(spec=object)
        error_provider2.is_available = AsyncMock(return_value=True)
        error_provider2.complete = AsyncMock(
            side_effect=LLMProviderError("API error 2")
        )

        client = LLMClient(
            fallback_order=[LLMProvider.CLAUDE_CODE, LLMProvider.GITHUB_MODELS]
        )
        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: error_provider1,
            LLMProvider.GITHUB_MODELS: error_provider2,
        }

        with patch.object(
            client.fallback_handler,
            "complete_with_fallback",
            new=AsyncMock(side_effect=LLMProviderError("All providers failed")),
        ):
            with pytest.raises(LLMProviderError) as exc_info:
                await client.complete([{"role": "user", "content": "test prompt"}])
            assert "All providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_all_providers_fail(self):
        """Test embed when all providers fail."""
        error_provider1 = AsyncMock(spec=object)
        error_provider1.is_available = AsyncMock(return_value=True)
        error_provider1.embed = AsyncMock(side_effect=LLMProviderError("API error 1"))

        error_provider2 = AsyncMock(spec=object)
        error_provider2.is_available = AsyncMock(return_value=True)
        error_provider2.embed = AsyncMock(side_effect=LLMProviderError("API error 2"))

        client = LLMClient(
            fallback_order=[LLMProvider.CLAUDE_CODE, LLMProvider.GITHUB_MODELS]
        )
        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: error_provider1,
            LLMProvider.GITHUB_MODELS: error_provider2,
        }

        with patch.object(
            client.fallback_handler,
            "embed_with_fallback",
            new=AsyncMock(side_effect=LLMProviderError("All providers failed")),
        ):
            with pytest.raises(LLMProviderError) as exc_info:
                await client.embed("test text")
            assert "All providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_select_best_model_with_cache_hit(self, mock_provider):
        """Test _select_best_model with cache hit."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Pre-populate cache with correct structure
        cache_key = f"{mock_provider.__class__.__name__}:chat"
        client._model_selection_cache[cache_key] = "cached-model"

        model = await client._select_best_model(mock_provider, "chat")
        assert model == "cached-model"

    @pytest.mark.asyncio
    async def test_select_best_model_chat_capability(self, mock_provider):
        """Test _select_best_model finding chat-capable model."""
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="chat-model",
                    name="Chat Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
                Model(
                    id="completion-model",
                    name="Completion Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion"],
                ),
            ]
        )

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        model = await client._select_best_model(mock_provider, "chat")
        assert model == "chat-model"

    @pytest.mark.asyncio
    async def test_select_best_model_embedding_capability(self, mock_provider):
        """Test _select_best_model finding embedding-capable model."""
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="embedding-model",
                    name="Embedding Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                ),
                Model(
                    id="chat-model",
                    name="Chat Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
            ]
        )

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        model = await client._select_best_model(mock_provider, "embedding")
        assert model == "embedding-model"

    @pytest.mark.asyncio
    async def test_select_best_model_fallback_to_first(self, mock_provider):
        """Test _select_best_model fallback when no exact capability match."""
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="completion-only",
                    name="Completion Only",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion"],
                ),
            ]
        )

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Should return first model as fallback
        model = await client._select_best_model(mock_provider, "chat")
        assert model == "completion-only"

    @pytest.mark.asyncio
    async def test_try_complete_with_provider_request_model_update(self, mock_provider):
        """Test _try_complete_with_provider updates request model."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        request = CompletionRequest(
            messages=[{"role": "user", "content": "test"}],
            model="",  # Empty triggers auto-selection
            max_tokens=100,
        )

        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="test-response-id",
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "response"},
                        "finish_reason": "stop",
                    }
                ],
                model="selected-model",
                usage={"total_tokens": 10},
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        # Mock _select_best_model to return a specific model
        with patch.object(
            client, "_select_best_model", new=AsyncMock(return_value="selected-model")
        ):
            response = await client._try_complete_with_provider(mock_provider, request)
            assert response.content == "response"
            # The request model should be updated
            assert request.model == "selected-model"

    @pytest.mark.asyncio
    async def test_try_embed_with_provider_model_auto_selection(self, mock_provider):
        """Test _try_embed_with_provider with model auto-selection logic."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Use default model that triggers auto-selection
        request = EmbeddingRequest(
            input="test",
            model="text-embedding-ada-002",  # This is the default
        )

        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                data=[{"embedding": [0.1, 0.2]}],
                model="embed-model",
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        # Mock settings to ensure auto-selection occurs
        with patch("scriptrag.llm.client.get_settings") as mock_settings:
            mock_config = mock_settings.return_value
            mock_config.llm_embedding_model = None  # Not explicitly configured

            # Mock _select_best_model to return a specific model
            with patch.object(
                client, "_select_best_model", new=AsyncMock(return_value="embed-model")
            ):
                response = await client._try_embed_with_provider(mock_provider, request)
                assert len(response.data) == 1
                # The request model should be updated when auto-selecting
                assert request.model == "embed-model"

    @pytest.mark.asyncio
    async def test_complete_with_specific_provider(self, mock_provider):
        """Test complete with specific provider parameter."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="provider-specific-response",
                choices=[
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "provider specific response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                model="test-model",
                usage={"total_tokens": 10},
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        response = await client.complete(
            [{"role": "user", "content": "test prompt"}],
            provider=LLMProvider.GITHUB_MODELS,
        )
        assert response.content == "provider specific response"

    @pytest.mark.asyncio
    async def test_embed_with_dimensions(self, mock_provider):
        """Test embed with dimensions parameter."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}
        client.current_provider = mock_provider

        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                data=[{"embedding": [0.1, 0.2]}],
                model="embed-model",
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        response = await client.embed("test text", dimensions=512)
        assert len(response.data) == 1
        assert response.data[0]["embedding"] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_switch_provider_success(self, mock_provider):
        """Test successful provider switching."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        success = await client.switch_provider(LLMProvider.GITHUB_MODELS)
        assert success is True
        assert client.current_provider == mock_provider

    @pytest.mark.asyncio
    async def test_switch_provider_unavailable(self):
        """Test switching to unavailable provider."""
        unavailable_provider = AsyncMock(spec=object)
        unavailable_provider.is_available = AsyncMock(return_value=False)

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: unavailable_provider}

        success = await client.switch_provider(LLMProvider.GITHUB_MODELS)
        assert success is False
        assert client.current_provider is None
