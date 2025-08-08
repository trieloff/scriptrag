"""Additional tests to achieve 99% coverage for LLM modules."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.llm import LLMClient, LLMProvider
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.client import CompletionRequest, EmbeddingRequest
from scriptrag.llm.providers import ClaudeCodeProvider


class TestRemainingCoverage:
    """Tests for remaining uncovered lines."""

    @pytest.mark.asyncio
    async def test_client_select_provider_no_preferred(self):
        """Test provider selection without preferred provider."""
        client = LLMClient(preferred_provider=None)

        # Mock all providers as unavailable except one
        for provider_type in LLMProvider:
            provider = client.registry.get_provider(provider_type)
            if provider:
                if provider_type == LLMProvider.OPENAI_COMPATIBLE:
                    provider.is_available = AsyncMock(return_value=True)
                else:
                    provider.is_available = AsyncMock(return_value=False)

        await client._select_provider()
        assert client.current_provider is not None
        assert client.current_provider.provider_type == LLMProvider.OPENAI_COMPATIBLE

    @pytest.mark.asyncio
    async def test_client_complete_fallback_no_preferred(self):
        """Test complete fallback without preferred provider."""
        client = LLMClient(preferred_provider=None)

        # Mock all providers as unavailable
        for provider_type in LLMProvider:
            provider = client.registry.get_provider(provider_type)
            if provider:
                provider.is_available = AsyncMock(return_value=False)

        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "test"}]
        )

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await client._complete_with_fallback(request)

    @pytest.mark.asyncio
    async def test_client_embed_fallback_no_preferred(self):
        """Test embed fallback without preferred provider."""
        client = LLMClient(preferred_provider=None)

        # Mock all providers as unavailable
        for provider_type in LLMProvider:
            provider = client.registry.get_provider(provider_type)
            if provider:
                provider.is_available = AsyncMock(return_value=False)

        request = EmbeddingRequest(model="test", input="test")

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await client._embed_with_fallback(request)

    @pytest.mark.asyncio
    async def test_client_complete_with_fallback_skip_preferred(self):
        """Test complete fallback that skips already-tried preferred provider."""
        client = LLMClient(
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
            ],
        )

        # Mock Claude as unavailable, GitHub as available
        claude_provider = client.registry.get_provider(LLMProvider.CLAUDE_CODE)
        if claude_provider:
            claude_provider.is_available = AsyncMock(return_value=False)

        github_provider = client.registry.get_provider(LLMProvider.GITHUB_MODELS)
        if github_provider:
            github_provider.is_available = AsyncMock(return_value=True)
            github_provider.list_models = AsyncMock(return_value=[])
            mock_response = Mock()
            mock_response.content = "test response"
            mock_response.model = "test"
            mock_response.provider = LLMProvider.GITHUB_MODELS
            github_provider.complete = AsyncMock(return_value=mock_response)

        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "test"}]
        )

        response = await client._complete_with_fallback(request)
        assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_client_embed_with_fallback_skip_preferred(self):
        """Test embed fallback that skips already-tried preferred provider."""
        client = LLMClient(
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
            ],
        )

        # Mock Claude as unavailable, GitHub as available
        claude_provider = client.registry.get_provider(LLMProvider.CLAUDE_CODE)
        if claude_provider:
            claude_provider.is_available = AsyncMock(return_value=False)

        github_provider = client.registry.get_provider(LLMProvider.GITHUB_MODELS)
        if github_provider:
            github_provider.is_available = AsyncMock(return_value=True)
            github_provider.list_models = AsyncMock(return_value=[])
            github_provider.embed = AsyncMock(
                return_value=Mock(provider=LLMProvider.GITHUB_MODELS)
            )

        request = EmbeddingRequest(model="test", input="test")

        response = await client._embed_with_fallback(request)
        assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_client_try_complete_no_models(self):
        """Test _try_complete_with_provider with no models available."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.list_models = AsyncMock(return_value=[])
        mock_response = Mock()
        mock_response.content = "test response"
        mock_response.model = "gpt-4"
        mock_response.provider = LLMProvider.GITHUB_MODELS
        mock_provider.complete = AsyncMock(return_value=mock_response)

        request = CompletionRequest(
            model="gpt-4",  # Will stay as is since no models available
            messages=[{"role": "user", "content": "test"}],
        )

        await client._try_complete_with_provider(mock_provider, request)
        assert request.model == "gpt-4"  # Should not change

    @pytest.mark.asyncio
    async def test_client_try_embed_no_models(self):
        """Test _try_embed_with_provider with no models available."""
        client = LLMClient()

        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.list_models = AsyncMock(return_value=[])
        mock_provider.embed = AsyncMock(return_value=Mock())

        request = EmbeddingRequest(
            model="text-embedding-ada-002",  # Will stay as is since no models available
            input="test",
        )

        await client._try_embed_with_provider(mock_provider, request)
        assert request.model == "text-embedding-ada-002"  # Should not change

    @pytest.mark.asyncio
    async def test_claude_provider_check_sdk_import_error(self):
        """Test _check_sdk when import fails."""
        with patch("builtins.__import__", side_effect=ImportError("Not found")):
            provider = ClaudeCodeProvider()
            assert provider.sdk_available is False

    @pytest.mark.asyncio
    async def test_claude_provider_is_available_sdk_other_exception(self):
        """Test is_available when SDK check raises non-import exception."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = True

        # Mock the SDK to raise a non-import exception
        with (
            patch("builtins.__import__", side_effect=RuntimeError("Other error")),
            patch.dict("os.environ", {}, clear=True),  # No env markers
        ):
            result = await provider.is_available()
            assert result is False  # No fallback env vars

    @pytest.mark.asyncio
    async def test_registry_remove_nonexistent_provider(self):
        """Test removing a provider that doesn't exist."""
        from scriptrag.llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        # Should not raise error
        registry.remove_provider(LLMProvider.CLAUDE_CODE)
        assert registry.get_provider(LLMProvider.CLAUDE_CODE) is None
