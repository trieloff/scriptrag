"""Additional tests to achieve 99% coverage for LLM client module."""

from unittest.mock import AsyncMock, patch

import pytest

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
    provider = AsyncMock()
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
            embeddings=[[0.1, 0.2, 0.3]],  # This is a computed field
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
    async def test_set_default_models_all_provided(self, mock_provider):
        """Test set_default_models when all models are provided."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        client.set_default_models(
            chat_model="chat-model",
            completion_model="completion-model",
            embedding_model="embedding-model",
        )

        assert client.default_chat_model == "chat-model"
        assert client.default_completion_model == "completion-model"
        assert client.default_embedding_model == "embedding-model"

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, mock_provider):
        """Test context manager exit cleanup."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Test normal exit
        client.__exit__(None, None, None)

        # Test exit with exception
        client.__exit__(Exception, Exception("test"), None)

    @pytest.mark.asyncio
    async def test_select_provider_with_unavailable_preferred(self, mock_provider):
        """Test provider selection when preferred is unavailable."""
        unavailable_provider = AsyncMock()
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
        unavailable_provider = AsyncMock()
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
        error_provider = AsyncMock()
        error_provider.is_available = AsyncMock(return_value=True)
        error_provider.list_models = AsyncMock(side_effect=Exception("API error"))

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
        error_provider = AsyncMock()
        error_provider.is_available = AsyncMock(return_value=True)
        error_provider.complete = AsyncMock(side_effect=Exception("API error"))

        fallback_provider = AsyncMock()
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
            response = await client.complete("test prompt")
            assert response.content == "fallback response"

    @pytest.mark.asyncio
    async def test_complete_all_providers_fail(self):
        """Test complete when all providers fail."""
        error_provider1 = AsyncMock()
        error_provider1.is_available = AsyncMock(return_value=True)
        error_provider1.complete = AsyncMock(side_effect=Exception("API error 1"))

        error_provider2 = AsyncMock()
        error_provider2.is_available = AsyncMock(return_value=True)
        error_provider2.complete = AsyncMock(side_effect=Exception("API error 2"))

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
            new=AsyncMock(side_effect=Exception("All providers failed")),
        ):
            with pytest.raises(Exception) as exc_info:
                await client.complete("test prompt")
            assert "All providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_all_providers_fail(self):
        """Test embed when all providers fail."""
        error_provider1 = AsyncMock()
        error_provider1.is_available = AsyncMock(return_value=True)
        error_provider1.embed = AsyncMock(side_effect=Exception("API error 1"))

        error_provider2 = AsyncMock()
        error_provider2.is_available = AsyncMock(return_value=True)
        error_provider2.embed = AsyncMock(side_effect=Exception("API error 2"))

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
            new=AsyncMock(side_effect=Exception("All providers failed")),
        ):
            with pytest.raises(Exception) as exc_info:
                await client.embed("test text")
            assert "All providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_select_best_model_with_cache_hit(self, mock_provider):
        """Test _select_best_model with cache hit."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        # Pre-populate cache
        client.model_cache.set("best_chat_github_models", "cached-model")

        model = await client._select_best_model(
            mock_provider, capabilities=["chat"], prefer_model=None
        )
        assert model == "cached-model"

    @pytest.mark.asyncio
    async def test_select_best_model_prefer_model_available(self, mock_provider):
        """Test _select_best_model when preferred model is available."""
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="preferred-model",
                    name="Preferred Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
                Model(
                    id="other-model",
                    name="Other Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
            ]
        )

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        model = await client._select_best_model(
            mock_provider, capabilities=["chat"], prefer_model="preferred-model"
        )
        assert model == "preferred-model"

    @pytest.mark.asyncio
    async def test_select_best_model_prefer_model_not_available(self, mock_provider):
        """Test _select_best_model when preferred model is not available."""
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="other-model",
                    name="Other Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                ),
            ]
        )

        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        model = await client._select_best_model(
            mock_provider, capabilities=["chat"], prefer_model="nonexistent-model"
        )
        assert model == "other-model"

    @pytest.mark.asyncio
    async def test_select_best_model_no_matching_capabilities(self, mock_provider):
        """Test _select_best_model when no models have required capabilities."""
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

        model = await client._select_best_model(
            mock_provider, capabilities=["chat"], prefer_model=None
        )
        assert model is None

    @pytest.mark.asyncio
    async def test_try_complete_with_provider_request_model_update(self, mock_provider):
        """Test _try_complete_with_provider updates request model."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        request = CompletionRequest(
            prompt="test",
            model="auto-select",
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
    async def test_try_embed_with_provider_request_model_update(self, mock_provider):
        """Test _try_embed_with_provider updates request model."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}

        request = EmbeddingRequest(
            input="test",
            model="auto-select",
        )

        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                data=[{"embedding": [0.1, 0.2]}],
                model="embed-model",
                provider=LLMProvider.GITHUB_MODELS,
                embeddings=[[0.1, 0.2]],
            )
        )

        # Mock _select_best_model to return a specific model
        with patch.object(
            client, "_select_best_model", new=AsyncMock(return_value="embed-model")
        ):
            response = await client._try_embed_with_provider(mock_provider, request)
            assert len(response.embeddings) == 1
            # The request model should be updated
            assert request.model == "embed-model"

    @pytest.mark.asyncio
    async def test_complete_with_json_response_format(self, mock_provider):
        """Test complete with JSON response format."""
        client = LLMClient()
        client.registry.providers = {LLMProvider.GITHUB_MODELS: mock_provider}
        client.current_provider = mock_provider

        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="json-response-id",
                choices=[
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"result": "test"}',
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
            "test prompt", response_format={"type": "json_object"}
        )
        assert response.content == '{"result": "test"}'

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
                embeddings=[[0.1, 0.2]],
            )
        )

        response = await client.embed("test text", dimensions=512)
        assert len(response.embeddings) == 1
