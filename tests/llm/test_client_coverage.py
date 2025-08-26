"""Comprehensive tests for LLM Client to achieve 99% coverage."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.exceptions import LLMProviderError, LLMRetryableError
from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    LLMProvider,
    Model,
)
from scriptrag.llm.base import BaseLLMProvider


class TestLLMClientCoverage:
    """Tests to cover missing lines in LLMClient."""

    def test_get_metrics(self):
        """Test get_metrics method (line 114)."""
        client = LLMClient()
        metrics = client.get_metrics()

        assert isinstance(metrics, dict)
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "failed_requests" in metrics

    def test_metrics_callback_with_retryable_error(self):
        """Test metrics callback with retryable error (line 121)."""
        client = LLMClient()

        # Mock retryable error
        error = LLMRetryableError("Rate limited")

        # Mock retry strategy to return True for is_retryable_error
        client.retry_strategy.is_retryable_error = Mock(return_value=True)

        # Call the callback
        client._metrics_callback("test_provider", error)

        # Verify retry was recorded
        metrics = client.get_metrics()
        assert metrics["retry_attempts"] == 1
        assert metrics["failed_requests"] == 1

    def test_providers_property(self):
        """Test providers property (line 128)."""
        client = LLMClient()
        providers = client.providers

        assert isinstance(providers, dict)
        assert all(isinstance(k, LLMProvider) for k in providers)

    @pytest.mark.asyncio
    async def test_select_provider_preferred_available(self):
        """Test preferred provider selection when available (lines 134-140)."""
        client = LLMClient(preferred_provider=LLMProvider.CLAUDE_CODE)

        # Mock preferred provider as available
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        client.registry.providers[LLMProvider.CLAUDE_CODE] = mock_provider
        client.registry.get_provider = Mock(return_value=mock_provider)

        await client._select_provider()

        assert client.current_provider == mock_provider

    @pytest.mark.asyncio
    async def test_select_provider_no_providers_available(self):
        """Test warning when no providers available (line 150)."""
        client = LLMClient()

        # Clear all providers
        client.registry.providers.clear()
        client.registry.get_provider = Mock(return_value=None)

        with patch("scriptrag.llm.client.logger.warning") as mock_warning:
            await client._select_provider()
            mock_warning.assert_called_with("No LLM providers available")

        assert client.current_provider is None

    @pytest.mark.asyncio
    async def test_ensure_provider_no_provider_error(self):
        """Test RuntimeError when no provider available (line 158)."""
        client = LLMClient()
        client.current_provider = None

        # Mock _select_provider to not set any provider
        client._select_provider = AsyncMock(spec=object)

        with pytest.raises(RuntimeError, match="No LLM provider available"):
            await client.ensure_provider()

    @pytest.mark.asyncio
    async def test_list_models_all_providers_with_errors(self):
        """Test list_models error handling for all providers (lines 184-193)."""
        client = LLMClient()

        # Mock providers that fail
        mock_provider1 = Mock(spec=BaseLLMProvider)
        mock_provider1.is_available = AsyncMock(return_value=True)
        mock_provider1.list_models = AsyncMock(
            side_effect=LLMProviderError("API Error")
        )

        mock_provider2 = Mock(spec=BaseLLMProvider)
        mock_provider2.is_available = AsyncMock(return_value=True)
        mock_provider2.list_models = AsyncMock(
            side_effect=LLMProviderError("Network Error")
        )

        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: mock_provider1,
            LLMProvider.GITHUB_MODELS: mock_provider2,
        }

        with patch("scriptrag.llm.client.logger.debug") as mock_debug:
            models = await client.list_models()

            # Should log debug messages for failures
            assert mock_debug.call_count >= 2
            assert models == []  # Should return empty list on all failures

    @pytest.mark.asyncio
    async def test_complete_with_completion_request_object(self):
        """Test complete with CompletionRequest object (line 235)."""
        client = LLMClient()

        request = CompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.8,
        )

        # Mock fallback handler
        mock_response = CompletionResponse(
            id="test",
            model="gpt-4",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hi"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.CLAUDE_CODE,
        )
        client.fallback_handler.complete_with_fallback = AsyncMock(
            return_value=mock_response
        )

        response = await client.complete(request)

        assert response == mock_response
        # Verify the request object was passed through
        call_args = client.fallback_handler.complete_with_fallback.call_args[0]
        assert call_args[0] == request

    @pytest.mark.asyncio
    async def test_model_selection_cache_logging(self):
        """Test model selection cache hit logging (lines 282-287)."""
        client = LLMClient()

        # Pre-populate cache
        client._model_selection_cache["TestProvider:chat"] = "cached-model"

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.__class__.__name__ = "TestProvider"

        with patch("scriptrag.llm.client.logger.debug") as mock_debug:
            result = await client._select_best_model(mock_provider, "chat")

            # Should log cache hit
            mock_debug.assert_called_with(
                "Using cached model selection for TestProvider",
                model="cached-model",
                capability="chat",
            )
            assert result == "cached-model"

    @pytest.mark.asyncio
    async def test_complete_with_debug_mode_error(self):
        """Test error handling with debug mode (lines 379-393)."""
        client = LLMClient(debug_mode=True)

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.__class__.__name__ = "TestProvider"
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
        )

        # Mock the retry strategy to raise an exception
        client.retry_strategy.execute_with_retry = AsyncMock(
            side_effect=LLMProviderError("Test error")
        )

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
        )

        with (
            patch("scriptrag.llm.client.logger.error") as mock_error,
            patch(
                "scriptrag.llm.client.traceback.format_exc",
                return_value="Stack trace",
            ),
            pytest.raises(LLMProviderError, match="Test error"),
        ):
            await client._try_complete_with_provider(mock_provider, request)

            # Should log error with stack trace in debug mode
            mock_error.assert_called_once()
            call_kwargs = mock_error.call_args[1]
            assert "stack_trace" in call_kwargs
            assert call_kwargs["stack_trace"] == "Stack trace"

    @pytest.mark.asyncio
    async def test_embed_with_embedding_request_object(self):
        """Test embed with EmbeddingRequest object (line 415)."""
        client = LLMClient()

        request = EmbeddingRequest(
            model="text-embedding-ada-002",
            input="test text",
            dimensions=512,
        )

        # Mock fallback handler
        mock_response = EmbeddingResponse(
            model="text-embedding-ada-002",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )
        client.fallback_handler.embed_with_fallback = AsyncMock(
            return_value=mock_response
        )

        response = await client.embed(request)

        assert response == mock_response
        # Verify the request object was passed through
        call_args = client.fallback_handler.embed_with_fallback.call_args[0]
        assert call_args[0] == request

    @pytest.mark.asyncio
    async def test_embed_with_model_selection(self):
        """Test embedding model selection (lines 452-454)."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.__class__.__name__ = "TestProvider"
        mock_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="text-embedding",
                    name="Embedding Model",
                    provider=LLMProvider.OPENAI_COMPATIBLE,
                    capabilities=["embedding"],
                )
            ]
        )

        # Mock settings to return default embedding model
        with patch("scriptrag.llm.client.get_settings") as mock_get_settings:
            mock_settings = Mock(spec=object)
            mock_settings.llm_embedding_model = None  # Not explicitly configured
            mock_get_settings.return_value = mock_settings

            request = EmbeddingRequest(
                model="text-embedding-ada-002",  # Default model
                input="test",
            )

            # Mock retry strategy to return success
            mock_response = EmbeddingResponse(
                model="text-embedding",
                data=[],
                provider=LLMProvider.OPENAI_COMPATIBLE,
            )
            client.retry_strategy.execute_with_retry = AsyncMock(
                return_value=mock_response
            )

            response = await client._try_embed_with_provider(mock_provider, request)

            # Model should have been auto-selected
            assert request.model == "text-embedding"
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_embed_with_debug_mode_error(self):
        """Test embed error handling with debug mode (line 481)."""
        client = LLMClient(debug_mode=True)

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.__class__.__name__ = "TestProvider"

        # Mock retry strategy to raise an exception
        client.retry_strategy.execute_with_retry = AsyncMock(
            side_effect=LLMProviderError("Embed error")
        )

        request = EmbeddingRequest(
            model="test-model",
            input="test",
        )

        with (
            patch("scriptrag.llm.client.logger.error") as mock_error,
            patch(
                "scriptrag.llm.client.traceback.format_exc",
                return_value="Embed stack trace",
            ),
            pytest.raises(LLMProviderError, match="Embed error"),
        ):
            await client._try_embed_with_provider(mock_provider, request)

            # Should log error with stack trace in debug mode
            mock_error.assert_called_once()
            call_kwargs = mock_error.call_args[1]
            assert "stack_trace" in call_kwargs
            assert call_kwargs["stack_trace"] == "Embed stack trace"

    def test_get_current_provider(self):
        """Test get_current_provider method (lines 490-492)."""
        client = LLMClient()

        # No provider set
        assert client.get_current_provider() is None

        # With provider set
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.provider_type = LLMProvider.CLAUDE_CODE
        client.current_provider = mock_provider

        assert client.get_current_provider() == LLMProvider.CLAUDE_CODE

    @pytest.mark.asyncio
    async def test_switch_provider_success(self):
        """Test successful provider switch (lines 503-508)."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=True)
        client.registry.get_provider = Mock(return_value=mock_provider)

        with patch("scriptrag.llm.client.logger.info") as mock_info:
            result = await client.switch_provider(LLMProvider.GITHUB_MODELS)

            assert result is True
            assert client.current_provider == mock_provider
            mock_info.assert_called_with("Switched to provider: github_models")

    @pytest.mark.asyncio
    async def test_switch_provider_failure(self):
        """Test failed provider switch (lines 503-508)."""
        client = LLMClient()

        # Provider not available
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.is_available = AsyncMock(return_value=False)
        client.registry.get_provider = Mock(return_value=mock_provider)

        result = await client.switch_provider(LLMProvider.GITHUB_MODELS)

        assert result is False
        assert client.current_provider != mock_provider

    @pytest.mark.asyncio
    async def test_switch_provider_not_found(self):
        """Test provider switch when provider not found."""
        client = LLMClient()

        # Provider not found
        client.registry.get_provider = Mock(return_value=None)

        result = await client.switch_provider(LLMProvider.GITHUB_MODELS)

        assert result is False

    @pytest.mark.asyncio
    async def test_list_models_all_providers_success(self):
        """Test list_models success path with models extension (line 189)."""
        client = LLMClient()

        # Mock successful providers
        mock_provider1 = Mock(spec=BaseLLMProvider)
        mock_provider1.is_available = AsyncMock(return_value=True)
        mock_provider1.list_models = AsyncMock(
            return_value=[
                Model(
                    id="model1",
                    name="Model 1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
        )

        mock_provider2 = Mock(spec=BaseLLMProvider)
        mock_provider2.is_available = AsyncMock(return_value=True)
        mock_provider2.list_models = AsyncMock(
            return_value=[
                Model(
                    id="model2",
                    name="Model 2",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                )
            ]
        )

        client.registry.providers = {
            LLMProvider.CLAUDE_CODE: mock_provider1,
            LLMProvider.GITHUB_MODELS: mock_provider2,
        }

        models = await client.list_models()

        # Should have models from both providers
        assert len(models) == 2
        assert models[0].id == "model1"
        assert models[1].id == "model2"
