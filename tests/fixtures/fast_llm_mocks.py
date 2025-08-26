"""Fast LLM mocks optimized for test performance."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest import MonkeyPatch

from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    Model,
    Usage,
)

# Constants for test configuration
DEFAULT_EMBEDDING_SIZE = 768  # Standard embedding dimension
DEFAULT_CONTEXT_WINDOW = 4096  # Default context window for tests
TEST_TIMEOUT_UNIT = 1  # Timeout for unit tests in seconds
TEST_TIMEOUT_INTEGRATION = 5  # Timeout for integration tests
TEST_TIMEOUT_LLM = 10  # Timeout for LLM tests


@pytest.fixture
def instant_llm_response() -> CompletionResponse:
    """Create an instant completion response without delays."""
    return CompletionResponse(
        id="test-completion",
        model="test-model",
        text="Test response",
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        finish_reason="stop",
    )


@pytest.fixture
def instant_embedding_response() -> EmbeddingResponse:
    """Create an instant embedding response without delays."""
    return EmbeddingResponse(
        embedding=[0.1] * DEFAULT_EMBEDDING_SIZE,
        model="test-embedding-model",
        usage=Usage(prompt_tokens=10, completion_tokens=0, total_tokens=10),
    )


@pytest.fixture
def fast_mock_llm_client(
    instant_llm_response: CompletionResponse,
    instant_embedding_response: EmbeddingResponse,
) -> MagicMock:
    """Create a fast mock LLM client with no delays.

    This fixture creates synchronous mocks that return immediately,
    avoiding the overhead of async operations in tests that don't need them.
    """
    client = MagicMock(spec=LLMClient)

    # Mock provider with instant responses
    provider = MagicMock(spec=object)
    provider.complete = AsyncMock(return_value=instant_llm_response)
    provider.embed = AsyncMock(return_value=instant_embedding_response)
    provider.list_models = AsyncMock(
        return_value=[
            Model(
                id="test-model",
                name="Test Model",
                provider="mock",
                context_window=4096,
                supports_completion=True,
                supports_embedding=False,
            ),
            Model(
                id="test-embedding-model",
                name="Test Embedding Model",
                provider="mock",
                context_window=8192,
                supports_completion=False,
                supports_embedding=True,
            ),
        ]
    )
    provider.is_available = AsyncMock(return_value=True)

    # Configure client
    client.providers = {"mock": provider}
    client.complete = AsyncMock(return_value=instant_llm_response)
    client.embed = AsyncMock(return_value=instant_embedding_response)
    client.list_models = AsyncMock(return_value=provider.list_models.return_value)
    client.get_provider = MagicMock(return_value=provider)

    return client


@pytest.fixture
def fast_mock_llm_provider():
    """Create a fast mock LLM provider with cached responses.

    This provider uses pre-computed responses to avoid any processing delays.
    """
    from scriptrag.llm.base import BaseLLMProvider

    class FastMockProvider(BaseLLMProvider):
        """Ultra-fast mock provider for testing."""

        def __init__(self):
            self.provider_type = "mock"
            self._models_cache = [
                Model(
                    id="fast-model",
                    name="Fast Model",
                    provider="mock",
                    context_window=DEFAULT_CONTEXT_WINDOW,
                    supports_completion=True,
                    supports_embedding=True,
                )
            ]
            self._completion_cache = CompletionResponse(
                id="cached",
                model="fast-model",
                text="Cached response",
                usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                finish_reason="stop",
            )
            self._embedding_cache = EmbeddingResponse(
                embedding=[0.0] * DEFAULT_EMBEDDING_SIZE,
                model="fast-model",
                usage=Usage(prompt_tokens=1, completion_tokens=0, total_tokens=1),
            )

        async def list_models(self):
            """Return cached models instantly."""
            return self._models_cache

        async def complete(self, request: CompletionRequest):
            """Return cached completion instantly."""
            return self._completion_cache

        async def embed(self, request: EmbeddingRequest):
            """Return cached embedding instantly."""
            return self._embedding_cache

        async def is_available(self):
            """Always available."""
            return True

    return FastMockProvider()


@pytest.fixture(autouse=True)
def disable_llm_delays(monkeypatch: MonkeyPatch) -> None:
    """Automatically disable all LLM delays in tests.

    This fixture runs automatically and sets environment variables
    to minimize timeouts and delays in LLM operations.

    Safety check: Only runs in test environment to prevent accidental
    production configuration changes.
    """
    import os

    # Safety check - ensure we're in a test environment
    if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("TESTING"):
        raise RuntimeError(
            "LLM delay disabling should only run in test environment. "
            "Set TESTING=1 or run via pytest."
        )

    monkeypatch.setenv("SCRIPTRAG_TEST_TIMEOUT_UNIT", str(TEST_TIMEOUT_UNIT))
    monkeypatch.setenv(
        "SCRIPTRAG_TEST_TIMEOUT_INTEGRATION", str(TEST_TIMEOUT_INTEGRATION)
    )
    monkeypatch.setenv("SCRIPTRAG_TEST_TIMEOUT_LLM", str(TEST_TIMEOUT_LLM))
    monkeypatch.setenv("SCRIPTRAG_LLM_TIMEOUT", "1")
    monkeypatch.setenv("SCRIPTRAG_LLM_MAX_RETRIES", "1")
    monkeypatch.setenv("SCRIPTRAG_DISABLE_LLM_CACHE", "1")
    monkeypatch.setenv("TESTING", "1")  # Ensure test environment is marked
