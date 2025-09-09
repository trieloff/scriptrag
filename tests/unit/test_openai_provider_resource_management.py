"""Unit tests for OpenAI-compatible provider resource management."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scriptrag.llm.models import CompletionRequest, EmbeddingRequest
from scriptrag.llm.providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAIProviderResourceManagement:
    """Test resource management in OpenAI-compatible provider."""

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self) -> None:
        """Test that HTTP client is initialized lazily."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        # Client should not be initialized yet
        assert provider.client is None

        # First call should initialize the client
        client = await provider._ensure_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert provider.client is client

        # Second call should return the same client
        client2 = await provider._ensure_client()
        assert client2 is client

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self) -> None:
        """Test that context manager properly cleans up resources."""
        async with OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        ) as provider:
            # Initialize client by calling _ensure_client
            client = await provider._ensure_client()
            assert client is not None

        # After exiting context, client should be None
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_explicit_close_cleanup(self) -> None:
        """Test that explicit close() properly cleans up resources."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        # Initialize client
        client = await provider._ensure_client()
        assert client is not None

        # Close should clean up the client
        await provider.close()
        assert provider.client is None

        # Calling close again should be safe
        await provider.close()
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_multiple_operations_share_client(self) -> None:
        """Test that multiple operations share the same client instance."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock responses
            mock_client.get.return_value = AsyncMock(
                status_code=200, json=lambda: {"data": []}
            )
            mock_client.post.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "id": "test",
                    "model": "test-model",
                    "choices": [{"message": {"content": "test"}}],
                    "usage": {},
                },
            )

            # Multiple operations should use the same client
            await provider.is_available()
            await provider.list_models()

            # Client should be created only once
            mock_client_class.assert_called_once()

            # Clean up
            await provider.close()

    @pytest.mark.asyncio
    async def test_no_resource_leak_without_context_manager(self) -> None:
        """Test that resources are properly managed even without context manager."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        # Initialize client
        client = await provider._ensure_client()
        original_client = client

        # Mock the client's aclose method to track if it's called
        close_called = False
        original_aclose = client.aclose

        async def mock_aclose():
            nonlocal close_called
            close_called = True
            await original_aclose()

        client.aclose = mock_aclose

        # Explicitly close should clean up
        await provider.close()
        assert close_called
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_no_destructor_resource_management(self) -> None:
        """Test that provider doesn't use __del__ for resource management.

        Resource management should be handled via async context manager
        or explicit close() calls, not via __del__ which is unreliable.
        """
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        # Initialize client
        await provider._ensure_client()
        assert provider.client is not None

        # Verify that __del__ doesn't exist (correct pattern)
        assert not hasattr(provider, "__del__"), (
            "Provider should not use __del__ for resource management. "
            "Use async context manager or explicit close() instead."
        )

    @pytest.mark.asyncio
    async def test_is_available_initializes_client(self) -> None:
        """Test that is_available properly initializes client."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        assert provider.client is None

        with patch.object(provider, "_ensure_client") as mock_ensure:
            mock_client = AsyncMock()
            mock_client.get.return_value = AsyncMock(status_code=200)
            mock_ensure.return_value = mock_client

            await provider.is_available()

            # Should have called _ensure_client
            mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_initializes_client(self) -> None:
        """Test that complete properly initializes client."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        assert provider.client is None

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
        )

        with patch.object(provider, "_ensure_client") as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "id": "test",
                    "model": "test-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "response"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {},
                },
                text="test response",
            )
            mock_ensure.return_value = mock_client

            await provider.complete(request)

            # Should have called _ensure_client
            mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_initializes_client(self) -> None:
        """Test that embed properly initializes client."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        assert provider.client is None

        request = EmbeddingRequest(
            model="test-model",
            input=["test text"],
        )

        with patch.object(provider, "_ensure_client") as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "model": "test-model",
                    "data": [{"embedding": [0.1, 0.2, 0.3]}],
                    "usage": {},
                },
                text="test response",
            )
            mock_ensure.return_value = mock_client

            await provider.embed(request)

            # Should have called _ensure_client
            mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_models_initializes_client(self) -> None:
        """Test that list_models properly initializes client."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        assert provider.client is None

        with patch.object(provider, "_ensure_client") as mock_ensure:
            mock_client = AsyncMock()
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"data": [{"id": "model1"}, {"id": "model2"}]},
            )
            mock_ensure.return_value = mock_client

            await provider.list_models()

            # Should have called _ensure_client
            mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_operations_safe(self) -> None:
        """Test that concurrent operations safely share the client."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        initialization_count = 0

        # Mock the AsyncClient creation to count initializations
        original_init = httpx.AsyncClient.__init__

        def counting_init(self, *args, **kwargs):
            nonlocal initialization_count
            initialization_count += 1
            original_init(self, *args, **kwargs)

        with patch.object(httpx.AsyncClient, "__init__", counting_init):
            # Create multiple concurrent tasks to initialize the client
            tasks = [
                provider._ensure_client(),
                provider._ensure_client(),
                provider._ensure_client(),
                provider._ensure_client(),
                provider._ensure_client(),
            ]

            # Run all tasks concurrently
            clients = await asyncio.gather(*tasks)

            # All should return the same client instance
            assert all(c is clients[0] for c in clients)

            # Client should be initialized only once despite concurrent access
            assert initialization_count == 1

        # Clean up
        await provider.close()

    @pytest.mark.asyncio
    async def test_reinitialization_after_close(self) -> None:
        """Test that client can be reinitialized after being closed."""
        provider = OpenAICompatibleProvider(
            endpoint="http://test.com/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        # First initialization
        client1 = await provider._ensure_client()
        assert client1 is not None

        # Close the provider
        await provider.close()
        assert provider.client is None

        # Second initialization should create a new client
        client2 = await provider._ensure_client()
        assert client2 is not None
        assert client2 is not client1  # Should be a different instance

        # Clean up
        await provider.close()
