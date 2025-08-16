"""Tests for enhanced LLM client error handling and fallback transparency."""

import time

import pytest

from scriptrag.exceptions import (
    LLMFallbackError,
    LLMRetryableError,
    RateLimitError,
)
from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    LLMProvider,
    Model,
)
from scriptrag.llm.registry import ProviderRegistry


def create_mock_provider(name: str, provider_type: LLMProvider):
    """Create a mock provider with a custom class name."""

    class MockProvider:
        """Mock provider for testing error scenarios."""

        def __init__(self):
            self.name = name
            self.provider_type = provider_type

        async def is_available(self) -> bool:
            return True

        async def complete(self, request: CompletionRequest) -> CompletionResponse:
            raise NotImplementedError("Mock provider should be configured")

        async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
            raise NotImplementedError("Mock provider should be configured")

        async def list_models(self) -> list[Model]:
            return [
                Model(
                    id=f"{name}-model",
                    name=f"{name} Model",
                    provider=provider_type,
                    capabilities=["chat", "completion"],
                )
            ]

    # Set the class name
    MockProvider.__name__ = name
    return MockProvider()


@pytest.fixture
def mock_registry():
    """Create a mock registry with test providers."""
    registry = ProviderRegistry()

    # Create mock providers
    claude_provider = create_mock_provider("ClaudeProvider", LLMProvider.CLAUDE_CODE)
    github_provider = create_mock_provider("GitHubProvider", LLMProvider.GITHUB_MODELS)
    openai_provider = create_mock_provider(
        "OpenAIProvider", LLMProvider.OPENAI_COMPATIBLE
    )

    registry.providers = {
        LLMProvider.CLAUDE_CODE: claude_provider,
        LLMProvider.GITHUB_MODELS: github_provider,
        LLMProvider.OPENAI_COMPATIBLE: openai_provider,
    }

    return registry


class TestLLMErrorTypes:
    """Test the new error types."""

    def test_llm_fallback_error_creation(self):
        """Test LLMFallbackError with detailed information."""
        provider_errors = {
            "claude": ValueError("Invalid API key"),
            "github": RateLimitError("Too many requests", retry_after=60.0),
            "openai": ConnectionError("Network error"),
        }

        error = LLMFallbackError(
            message="All providers failed",
            provider_errors=provider_errors,
            attempted_providers=["claude", "github", "openai"],
            fallback_chain=["claude", "github", "openai"],
            debug_info={"request_id": "test-123"},
        )

        assert error.provider_errors == provider_errors
        assert error.attempted_providers == ["claude", "github", "openai"]
        assert error.fallback_chain == ["claude", "github", "openai"]
        assert error.debug_info == {"request_id": "test-123"}

        # Check formatted error message
        error_str = str(error)
        assert "All providers failed" in error_str
        assert "Tried 3 providers" in error_str
        assert "Check provider credentials" in error_str

    def test_llm_retryable_error_creation(self):
        """Test LLMRetryableError with retry information."""
        original_error = ConnectionError("Connection timeout")

        error = LLMRetryableError(
            message="Provider failed after retries",
            provider="github",
            retry_after=5.0,
            attempt=3,
            max_attempts=3,
            original_error=original_error,
        )

        assert error.provider == "github"
        assert error.retry_after == 5.0
        assert error.attempt == 3
        assert error.max_attempts == 3
        assert error.original_error == original_error

        # Check formatted error message
        error_str = str(error)
        assert "Provider failed after retries" in error_str
        assert "Retry after 5.0 seconds" in error_str
        assert "Attempt 3/3" in error_str


class TestLLMClientErrorHandling:
    """Test enhanced error handling in LLMClient."""

    @pytest.mark.asyncio
    async def test_retry_logic_with_retryable_error(self, mock_registry):
        """Test retry logic with retryable errors."""
        client = LLMClient(
            registry=mock_registry,
            max_retries=3,
            base_retry_delay=0.1,  # Fast retries for testing
            debug_mode=True,
        )

        # Mock provider that fails twice then succeeds
        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]
        call_count = 0

        async def mock_complete(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Temporary network error")
            return CompletionResponse(
                id="test",
                model="claude-model",
                choices=[{"message": {"content": "Success"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )

        provider.complete = mock_complete

        request = CompletionRequest(
            model="claude-model",
            messages=[{"role": "user", "content": "test"}],
        )

        # Should succeed after retries
        response = await client._try_complete_with_provider(provider, request)
        assert response.choices[0]["message"]["content"] == "Success"
        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_retry_logic_with_non_retryable_error(self, mock_registry):
        """Test that non-retryable errors don't get retried."""
        client = LLMClient(
            registry=mock_registry,
            max_retries=3,
            base_retry_delay=0.1,
        )

        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]
        call_count = 0

        async def mock_complete(request):
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid model name")  # Non-retryable error

        provider.complete = mock_complete

        request = CompletionRequest(
            model="claude-model",
            messages=[{"role": "user", "content": "test"}],
        )

        # Should fail immediately without retries
        with pytest.raises(ValueError):
            await client._try_complete_with_provider(provider, request)

        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_retry_logic_with_rate_limit_error(self, mock_registry):
        """Test retry logic respects rate limit retry-after."""
        client = LLMClient(
            registry=mock_registry,
            max_retries=2,
            base_retry_delay=0.1,
        )

        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]
        call_count = 0
        start_time = time.time()

        async def mock_complete(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("Rate limited", retry_after=0.05)  # Shorter delay
            return CompletionResponse(
                id="test",
                model="claude-model",
                choices=[{"message": {"content": "Success"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )

        provider.complete = mock_complete

        request = CompletionRequest(
            model="claude-model",
            messages=[{"role": "user", "content": "test"}],
        )

        response = await client._try_complete_with_provider(provider, request)
        elapsed = time.time() - start_time

        assert response.choices[0]["message"]["content"] == "Success"
        assert call_count == 2
        assert elapsed >= 0.05  # Should have waited for retry_after

    @pytest.mark.asyncio
    async def test_fallback_error_with_detailed_information(self, mock_registry):
        """Test fallback error contains detailed provider failure information."""
        client = LLMClient(
            registry=mock_registry,
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[LLMProvider.GITHUB_MODELS, LLMProvider.OPENAI_COMPATIBLE],
            debug_mode=True,
        )

        # Configure all providers to fail with different errors
        claude_provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]
        github_provider = mock_registry.providers[LLMProvider.GITHUB_MODELS]
        openai_provider = mock_registry.providers[LLMProvider.OPENAI_COMPATIBLE]

        async def claude_fail(request):
            raise ValueError("Invalid API key")

        async def github_fail(request):
            raise RateLimitError("Too many requests", retry_after=0.05)

        async def openai_fail(request):
            raise ConnectionError("Network error")

        claude_provider.complete = claude_fail
        github_provider.complete = github_fail
        openai_provider.complete = openai_fail

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
        )

        with pytest.raises(LLMFallbackError) as exc_info:
            await client._complete_with_fallback(request)

        error = exc_info.value
        assert len(error.provider_errors) == 3
        assert "ClaudeProvider" in error.provider_errors
        assert "GitHubProvider" in error.provider_errors
        assert "OpenAIProvider" in error.provider_errors

        assert error.attempted_providers == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]
        assert error.fallback_chain == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]

        # Debug info should be present
        assert error.debug_info is not None
        # Check that we have debug info for all providers that failed
        # The keys should contain the provider names

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, mock_registry):
        """Test that metrics are properly tracked."""
        client = LLMClient(registry=mock_registry)

        # Initial metrics should be zero
        metrics = client.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
        assert metrics["failed_requests"] == 0

        # Record some successes and failures
        client._record_success("provider1")
        client._record_success("provider1")
        client._record_failure("provider2", ValueError("test error"))
        client._record_retry()
        client._record_fallback_chain(["provider1", "provider2"])

        metrics = client.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["successful_requests"] == 2
        assert metrics["failed_requests"] == 1
        assert metrics["provider_successes"]["provider1"] == 2
        assert len(metrics["provider_failures"]["provider2"]) == 1
        assert metrics["retry_attempts"] == 1
        assert len(metrics["fallback_chains"]) == 1

    @pytest.mark.asyncio
    async def test_embedding_fallback_error(self, mock_registry):
        """Test fallback error for embedding operations."""
        client = LLMClient(registry=mock_registry, debug_mode=True)

        # Configure all providers to fail
        for provider in mock_registry.providers.values():

            async def embed_fail(request):
                raise ValueError("Embedding failed")

            provider.embed = embed_fail

        request = EmbeddingRequest(
            model="test-embedding-model",
            input="test text",
        )

        with pytest.raises(LLMFallbackError) as exc_info:
            await client._embed_with_fallback(request)

        error = exc_info.value
        assert "embedding" in error.message.lower()
        assert len(error.provider_errors) > 0

    def test_retryable_error_detection(self, mock_registry):
        """Test detection of retryable vs non-retryable errors."""
        client = LLMClient(registry=mock_registry)

        # Retryable errors
        assert client._is_retryable_error(RateLimitError("Rate limited"))
        assert client._is_retryable_error(ConnectionError("Connection timeout"))
        assert client._is_retryable_error(Exception("Service unavailable"))
        assert client._is_retryable_error(Exception("Internal server error"))
        assert client._is_retryable_error(Exception("Too many requests"))

        # Non-retryable errors
        assert not client._is_retryable_error(ValueError("Invalid input"))
        assert not client._is_retryable_error(KeyError("Missing key"))
        assert not client._is_retryable_error(Exception("Unauthorized"))

    def test_retry_after_extraction(self, mock_registry):
        """Test extraction of retry-after information from errors."""
        client = LLMClient(registry=mock_registry)

        # From RateLimitError
        rate_error = RateLimitError("Rate limited", retry_after=30.0)
        assert client._extract_retry_after(rate_error) == 30.0

        # From error message
        error_with_retry = Exception("Rate limited. Please retry after 45 seconds")
        assert client._extract_retry_after(error_with_retry) == 45.0

        # No retry information
        normal_error = Exception("Something went wrong")
        assert client._extract_retry_after(normal_error) is None

    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self, mock_registry):
        """Test exponential backoff delay calculation."""
        client = LLMClient(
            registry=mock_registry,
            base_retry_delay=1.0,
            max_retry_delay=8.0,
        )

        # Test exponential growth
        delay1 = client._calculate_retry_delay(1)
        delay2 = client._calculate_retry_delay(2)
        delay3 = client._calculate_retry_delay(3)
        delay4 = client._calculate_retry_delay(4)

        # Should grow exponentially but stay within bounds
        assert 1.0 <= delay1 <= 1.1  # 1 + jitter
        assert 2.0 <= delay2 <= 2.2  # 2 + jitter
        assert 4.0 <= delay3 <= 4.4  # 4 + jitter
        assert delay4 <= 8.8  # Capped at max_retry_delay + jitter

    @pytest.mark.asyncio
    async def test_debug_mode_includes_stack_traces(self, mock_registry):
        """Test that debug mode includes stack traces in error information."""
        client = LLMClient(registry=mock_registry, debug_mode=True)

        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]

        async def failing_complete(request):
            raise ValueError("Test error for stack trace")

        provider.complete = failing_complete

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
        )

        with pytest.raises(LLMFallbackError) as exc_info:
            await client._complete_with_fallback(request)

        error = exc_info.value
        assert error.debug_info is not None
        assert "claude_code_error" in error.debug_info
        assert "stack_trace" in error.debug_info["claude_code_error"]
        assert (
            "ValueError: Test error for stack trace"
            in error.debug_info["claude_code_error"]["stack_trace"]
        )

    @pytest.mark.asyncio
    async def test_no_debug_info_when_debug_disabled(self, mock_registry):
        """Test that debug info is not included when debug mode is disabled."""
        client = LLMClient(registry=mock_registry, debug_mode=False)

        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]

        async def failing_complete(request):
            raise ValueError("Test error")

        provider.complete = failing_complete

        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
        )

        with pytest.raises(LLMFallbackError) as exc_info:
            await client._complete_with_fallback(request)

        error = exc_info.value
        assert error.debug_info is None

    @pytest.mark.asyncio
    async def test_provider_specific_error_with_retry(self, mock_registry):
        """Test specifying a provider that fails with retry logic."""
        client = LLMClient(registry=mock_registry, max_retries=2)

        provider = mock_registry.providers[LLMProvider.CLAUDE_CODE]
        call_count = 0

        async def failing_complete(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ConnectionError("Temporary failure")
            return CompletionResponse(
                id="test",
                model="claude-model",
                choices=[{"message": {"content": "Success after retry"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )

        provider.complete = failing_complete

        # Test with specific provider
        response = await client.complete(
            messages=[{"role": "user", "content": "test"}],
            provider=LLMProvider.CLAUDE_CODE,
        )

        assert response.choices[0]["message"]["content"] == "Success after retry"
        assert call_count == 2  # 1 failure + 1 success
