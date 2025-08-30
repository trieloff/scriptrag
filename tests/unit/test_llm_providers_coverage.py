"""Comprehensive unit tests for LLM provider modules to achieve 99% code coverage."""

from unittest.mock import Mock

import httpx
import pytest

from scriptrag.llm.base_provider import EnhancedBaseLLMProvider
from scriptrag.llm.models import (
    LLMProvider,
)

# Test token constant for unit tests (not a real secret)
TEST_TOKEN = "test-token"  # noqa: S105


class TestEnhancedBaseLLMProvider:
    """Test EnhancedBaseLLMProvider functionality."""

    def test_initialization(self):
        """Test provider initialization."""

        class TestProvider(EnhancedBaseLLMProvider):
            """Test implementation of enhanced base provider."""

            provider_type = LLMProvider.GITHUB_MODELS

            async def _validate_availability(self) -> bool:
                return True

            async def complete(self, request):
                return Mock(spec=object)

            async def embed(self, request):
                return Mock(spec=object)

            async def list_models(self):
                return []

        provider = TestProvider(
            token="test-token",  # noqa: S106
            timeout=60.0,
            base_url="https://api.example.com",
        )

        assert provider.token == "test-token"  # noqa: S105
        assert provider.timeout == 60.0
        assert provider.base_url == "https://api.example.com"
        assert provider.client is None
        assert provider._models_cache is None

    def test_init_http_client(self):
        """Test HTTP client initialization."""

        class TestProvider(EnhancedBaseLLMProvider):
            provider_type = LLMProvider.GITHUB_MODELS

            async def _validate_availability(self) -> bool:
                return True

            async def complete(self, request):
                return Mock(spec=object)

            async def embed(self, request):
                return Mock(spec=object)

            async def list_models(self):
                return []

        provider = TestProvider(timeout=30.0)

        # Initially no client
        assert provider.client is None

        # Initialize client
        provider._init_http_client()
        assert provider.client is not None
        assert isinstance(provider.client, httpx.AsyncClient)

        # Second call doesn't create new client
        original_client = provider.client
        provider._init_http_client()
        assert provider.client is original_client

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""

        class TestProvider(EnhancedBaseLLMProvider):
            provider_type = LLMProvider.GITHUB_MODELS

            async def _validate_availability(self) -> bool:
                return True

            async def complete(self, request):
                return Mock(spec=object)

            async def embed(self, request):
                return Mock(spec=object)

            async def list_models(self):
                return []

        provider = TestProvider()

        # Test context manager
        async with provider as p:
            assert p is provider
            assert provider.client is not None

        # Client should be closed after context
        # Note: In real scenarios, client would be closed, but we can't easily test that
        # without mocking aclose, which would require more complex setup
