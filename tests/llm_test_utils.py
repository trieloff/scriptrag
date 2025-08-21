"""Utilities for testing LLM-dependent code with proper mocking and timeouts.

This module provides:
- Mock LLM providers with configurable delays and responses
- Test fixtures for common LLM operations
- Timeout decorators for different test scenarios
- Retry logic for flaky tests
"""

import asyncio
import functools
import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from tenacity import retry, stop_after_attempt, wait_exponential

from scriptrag.exceptions import LLMProviderError, RateLimitError
from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    Model,
)
from scriptrag.llm.base import BaseLLMProvider

# Test timeout configurations (configurable via environment variables)
# Default: 10 seconds for unit tests
TIMEOUT_UNIT = int(os.getenv("SCRIPTRAG_TEST_TIMEOUT_UNIT", "10"))
# Default: 30 seconds for integration tests
TIMEOUT_INTEGRATION = int(os.getenv("SCRIPTRAG_TEST_TIMEOUT_INTEGRATION", "30"))
# Default: 60 seconds for actual LLM tests
TIMEOUT_LLM = int(os.getenv("SCRIPTRAG_TEST_TIMEOUT_LLM", "60"))
# Default: 120 seconds for long-running LLM tests
TIMEOUT_LLM_LONG = int(os.getenv("SCRIPTRAG_TEST_TIMEOUT_LLM_LONG", "120"))


def timeout_for_test_type(test_type: str = "unit") -> int:
    """Get timeout value based on test type.

    Args:
        test_type: Type of test ("unit", "integration", "llm", "llm_long")

    Returns:
        Timeout value in seconds
    """
    timeouts = {
        "unit": TIMEOUT_UNIT,
        "integration": TIMEOUT_INTEGRATION,
        "llm": TIMEOUT_LLM,
        "llm_long": TIMEOUT_LLM_LONG,
    }
    return timeouts.get(test_type, TIMEOUT_UNIT)


def retry_flaky_test(
    max_attempts: int = 3,
    wait_min: float = 1,
    wait_max: float = 10,
):
    """Decorator to retry flaky tests with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        wait_min: Minimum wait time between retries (seconds)
        wait_max: Maximum wait time between retries (seconds)
    """

    def decorator(func):
        @functools.wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
            reraise=True,
        )
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        @functools.wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
            reraise=True,
        )
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing with configurable behavior."""

    def __init__(
        self,
        provider_type: str | None = None,
        response_delay: float = 0.0,
        fail_after_n_calls: int | None = None,
        rate_limit_after_n_calls: int | None = None,
    ) -> None:
        """Initialize mock provider.

        Args:
            provider_type: Provider type identifier (defaults to OPENAI_COMPATIBLE)
            response_delay: Delay before returning response (simulates network latency)
            fail_after_n_calls: Fail after N calls (for testing error handling)
            rate_limit_after_n_calls: Simulate rate limiting after N calls
        """
        from scriptrag.llm import LLMProvider

        self.provider_type = provider_type or LLMProvider.OPENAI_COMPATIBLE
        self.response_delay = response_delay
        self.fail_after_n_calls = fail_after_n_calls
        self.rate_limit_after_n_calls = rate_limit_after_n_calls
        self.call_count = 0
        self._available = True

    async def list_models(self) -> list[Model]:
        """Return mock models."""
        await self._simulate_delay()
        return [
            Model(
                id="mock-model-1",
                name="Mock Model 1",
                provider=self.provider_type,
                context_window=4096,
                supports_completion=True,
                supports_embedding=False,
            ),
            Model(
                id="mock-embedding-model",
                name="Mock Embedding Model",
                provider=self.provider_type,
                context_window=8192,
                supports_completion=False,
                supports_embedding=True,
            ),
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Mock completion request."""
        await self._simulate_delay()
        self.call_count += 1

        # Simulate failures
        if self.fail_after_n_calls and self.call_count > self.fail_after_n_calls:
            raise LLMProviderError(
                message="Mock provider error",
                hint="This is a simulated failure for testing",
                details={
                    "call_count": self.call_count,
                    "fail_threshold": self.fail_after_n_calls,
                },
            )

        # Simulate rate limiting
        if (
            self.rate_limit_after_n_calls
            and self.call_count > self.rate_limit_after_n_calls
        ):
            raise RateLimitError(
                message="Rate limit exceeded",
                retry_after=10.0,
                provider=self.provider_type,
            )

        # Extract user message content for mock response
        user_content = ""
        if request.messages:
            for msg in request.messages:
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")[:50]
                    break

        return CompletionResponse(
            id="mock-completion-1",
            model=request.model,
            provider=self.provider_type,
            choices=[
                {
                    "message": {
                        "role": "assistant",
                        "content": f"Mock response for: {user_content}...",
                    },
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Mock embedding request."""
        await self._simulate_delay()
        self.call_count += 1

        # Simulate failures
        if self.fail_after_n_calls and self.call_count > self.fail_after_n_calls:
            raise LLMProviderError(
                message="Mock provider error",
                hint="This is a simulated failure for testing",
                details={
                    "call_count": self.call_count,
                    "fail_threshold": self.fail_after_n_calls,
                },
            )

        # Simulate rate limiting
        if (
            self.rate_limit_after_n_calls
            and self.call_count > self.rate_limit_after_n_calls
        ):
            raise RateLimitError(
                message="Rate limit exceeded",
                retry_after=10.0,
                provider=self.provider_type,
            )

        # Generate mock embeddings
        embeddings = []
        for text in request.input:
            # Simple mock: generate fixed-size embedding based on text hash
            embedding = [float(hash(text) % 100) / 100.0 for _ in range(5)]
            embeddings.append({"embedding": embedding, "index": len(embeddings)})

        return EmbeddingResponse(
            model=request.model,
            provider=self.provider_type,
            data=embeddings,
            usage={"prompt_tokens": 10, "total_tokens": 10},
        )

    async def is_available(self) -> bool:
        """Check if provider is available."""
        return self._available

    async def _simulate_delay(self) -> None:
        """Simulate network delay."""
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)

    def set_available(self, available: bool) -> None:
        """Set provider availability."""
        self._available = available


# Common test responses
MOCK_SCENE_ANALYSIS: dict[str, Any] = {
    "characters": ["SARAH", "JAMES"],
    "locations": ["COFFEE SHOP"],
    "props": ["laptop", "coffee"],
    "themes": ["creativity", "morning routine"],
    "mood": "energetic",
}

MOCK_CHARACTER_ANALYSIS: dict[str, dict[str, str]] = {
    "SARAH": {
        "age": "30s",
        "occupation": "writer",
        "personality": "creative, focused",
        "arc": "completes screenplay",
    },
    "JAMES": {
        "age": "40s",
        "occupation": "barista",
        "personality": "friendly, helpful",
        "arc": "supports protagonist",
    },
}

MOCK_EMBEDDINGS: dict[str, list[float]] = {
    "scene_1": [0.1, 0.2, 0.3, 0.4, 0.5],
    "scene_2": [0.2, 0.3, 0.4, 0.5, 0.6],
    "scene_3": [0.3, 0.4, 0.5, 0.6, 0.7],
    "character_sarah": [0.4, 0.5, 0.6, 0.7, 0.8],
    "character_james": [0.5, 0.6, 0.7, 0.8, 0.9],
}


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_provider_with_delay() -> MockLLMProvider:
    """Create a mock LLM provider with simulated network delay."""
    return MockLLMProvider(response_delay=0.5)


@pytest.fixture
def mock_llm_provider_with_failures() -> MockLLMProvider:
    """Create a mock LLM provider that fails after 2 calls."""
    return MockLLMProvider(fail_after_n_calls=2)


@pytest.fixture
def mock_llm_provider_with_rate_limit() -> MockLLMProvider:
    """Create a mock LLM provider that rate limits after 3 calls."""
    return MockLLMProvider(rate_limit_after_n_calls=3)


@pytest.fixture
async def mock_llm_client(mock_llm_provider: MockLLMProvider) -> LLMClient:
    """Create a mock LLM client with the mock provider."""
    client = LLMClient()
    await client.add_provider(mock_llm_provider)
    return client


@pytest.fixture
def mock_completion_response() -> CompletionResponse:
    """Create a mock completion response."""
    from scriptrag.llm import LLMProvider

    return CompletionResponse(
        id="test-completion-1",
        model="mock-model-1",
        provider=LLMProvider.OPENAI_COMPATIBLE,
        choices=[
            {
                "text": "This is a mock completion response.",
                "index": 0,
                "finish_reason": "stop",
            }
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
    )


@pytest.fixture
def mock_embedding_response():
    """Create a mock embedding response."""
    from scriptrag.llm import LLMProvider

    return EmbeddingResponse(
        model="mock-embedding-model",
        provider=LLMProvider.OPENAI_COMPATIBLE,
        data=[{"embedding": [0.1, 0.2, 0.3, 0.4, 0.5], "index": 0}],
        usage={"prompt_tokens": 5, "total_tokens": 5},
    )


def create_mock_llm_client_sync(
    completion_response: CompletionResponse | None = None,
    embedding_response: EmbeddingResponse | None = None,
    delay: float = 0.0,
) -> Mock:
    """Create a synchronous mock LLM client for testing.

    Args:
        completion_response: Optional completion response to return
        embedding_response: Optional embedding response to return
        delay: Simulated delay in seconds

    Returns:
        Mock LLM client
    """
    client = Mock(spec=LLMClient)

    # Setup completion mock
    if completion_response:

        async def mock_complete(*args, **kwargs):
            if delay > 0:
                await asyncio.sleep(delay)
            return completion_response

        client.complete = AsyncMock(side_effect=mock_complete)
    else:
        from scriptrag.llm import LLMProvider

        client.complete = AsyncMock(
            return_value=CompletionResponse(
                id="mock-1",
                model="mock",
                provider=LLMProvider.OPENAI_COMPATIBLE,
                choices=[
                    {"text": "Mock response", "index": 0, "finish_reason": "stop"}
                ],
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )
        )

    # Setup embedding mock
    if embedding_response:

        async def mock_embed(*args, **kwargs):
            if delay > 0:
                await asyncio.sleep(delay)
            return embedding_response

        client.embed = AsyncMock(side_effect=mock_embed)
    else:
        from scriptrag.llm import LLMProvider

        client.embed = AsyncMock(
            return_value=EmbeddingResponse(
                model="mock",
                provider=LLMProvider.OPENAI_COMPATIBLE,
                data=[{"embedding": [0.1, 0.2, 0.3], "index": 0}],
                usage={"prompt_tokens": 1, "total_tokens": 1},
            )
        )

    # Setup other methods
    client.list_models = AsyncMock(return_value=[])
    client.add_provider = AsyncMock()
    client.remove_provider = AsyncMock()

    return client


@pytest.fixture
def patch_llm_client():
    """Patch the default LLM client creation."""

    def _patch(
        completion_response: CompletionResponse | None = None,
        embedding_response: EmbeddingResponse | None = None,
        delay: float = 0.0,
    ):
        mock_client = create_mock_llm_client_sync(
            completion_response=completion_response,
            embedding_response=embedding_response,
            delay=delay,
        )
        return patch("scriptrag.utils.get_default_llm_client", return_value=mock_client)

    return _patch
