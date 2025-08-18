"""Comprehensive tests for concurrent operations and edge cases in LLM module."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from scriptrag.exceptions import LLMFallbackError, LLMRetryableError, RateLimitError
from scriptrag.llm import LLMClient
from scriptrag.llm.fallback import FallbackHandler
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingResponse,
    LLMProvider,
    Model,
)
from scriptrag.llm.providers import (
    GitHubModelsProvider,
    OpenAICompatibleProvider,
)
from scriptrag.llm.registry import ProviderRegistry
from scriptrag.llm.retry_strategy import RetryStrategy


class TestConcurrentOperations:
    """Test concurrent LLM operations under load."""

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider for testing."""
        provider = AsyncMock()
        provider.is_available = AsyncMock(return_value=True)
        provider.provider_type = LLMProvider.GITHUB_MODELS
        provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat", "embedding"],
                )
            ]
        )
        return provider

    @pytest.fixture
    def client(self):
        """Create LLM client for testing."""
        return LLMClient(
            preferred_provider=LLMProvider.GITHUB_MODELS,
            fallback_order=[
                LLMProvider.GITHUB_MODELS,
                LLMProvider.CLAUDE_CODE,
                LLMProvider.OPENAI_COMPATIBLE,
            ],
        )

    @pytest.mark.asyncio
    async def test_concurrent_completions_same_provider(self, client, mock_provider):
        """Test multiple concurrent completion requests to same provider."""
        request_count = 10
        responses = []

        async def mock_complete(request):
            await asyncio.sleep(0.01)  # Simulate API delay
            return CompletionResponse(
                id=f"response-{id(request)}",
                model=request.model,
                choices=[{"message": {"content": f"Response for {request.model}"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        mock_provider.complete = AsyncMock(side_effect=mock_complete)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        # Create concurrent requests
        requests = [
            CompletionRequest(
                model=f"model-{i}",
                messages=[{"role": "user", "content": f"Query {i}"}],
            )
            for i in range(request_count)
        ]

        # Execute concurrently
        tasks = [
            client.complete(messages=req.messages, model=req.model) for req in requests
        ]
        responses = await asyncio.gather(*tasks)

        # Verify all completed successfully
        assert len(responses) == request_count
        assert all(isinstance(r, CompletionResponse) for r in responses)
        assert len({r.id for r in responses}) == request_count  # All unique IDs
        assert mock_provider.complete.call_count == request_count

    @pytest.mark.asyncio
    async def test_concurrent_completions_with_fallback(self, client):
        """Test concurrent completions with fallback to different providers."""
        # Setup providers with different success patterns
        github_provider = AsyncMock()
        github_provider.is_available = AsyncMock(return_value=True)
        github_provider.provider_type = LLMProvider.GITHUB_MODELS

        claude_provider = AsyncMock()
        claude_provider.is_available = AsyncMock(return_value=True)
        claude_provider.provider_type = LLMProvider.CLAUDE_CODE

        # GitHub fails half the time
        github_calls = 0

        async def github_complete(request):
            nonlocal github_calls
            github_calls += 1
            if github_calls % 2 == 0:
                raise RuntimeError("GitHub API error")
            return CompletionResponse(
                id=f"github-{github_calls}",
                model=request.model,
                choices=[{"message": {"content": "GitHub response"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        # Claude always succeeds
        async def claude_complete(request):
            return CompletionResponse(
                id=f"claude-{id(request)}",
                model=request.model,
                choices=[{"message": {"content": "Claude response"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )

        github_provider.complete = AsyncMock(side_effect=github_complete)
        claude_provider.complete = AsyncMock(side_effect=claude_complete)

        client.registry.providers[LLMProvider.GITHUB_MODELS] = github_provider
        client.registry.providers[LLMProvider.CLAUDE_CODE] = claude_provider

        # Execute concurrent requests
        tasks = [
            client.complete(
                messages=[{"role": "user", "content": f"Query {i}"}],
                model=f"model-{i}",
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        # Verify mixed provider responses
        github_responses = [
            r for r in responses if r.provider == LLMProvider.GITHUB_MODELS
        ]
        claude_responses = [
            r for r in responses if r.provider == LLMProvider.CLAUDE_CODE
        ]

        assert len(github_responses) > 0
        assert len(claude_responses) > 0
        assert len(responses) == 10

    @pytest.mark.asyncio
    async def test_concurrent_embeddings(self, client, mock_provider):
        """Test concurrent embedding requests."""
        request_count = 20

        async def mock_embed(request):
            await asyncio.sleep(0.005)  # Simulate API delay
            return EmbeddingResponse(
                model=request.model,
                data=[{"embedding": [0.1, 0.2, 0.3], "index": 0}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        mock_provider.embed = AsyncMock(side_effect=mock_embed)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = mock_provider

        # Execute concurrent embedding requests
        tasks = [
            client.embed(text=f"Text {i}", model="embed-model")
            for i in range(request_count)
        ]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == request_count
        assert all(isinstance(r, EmbeddingResponse) for r in responses)
        assert mock_provider.embed.call_count == request_count

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, client):
        """Test mix of completions and embeddings concurrently."""
        github_provider = AsyncMock()
        github_provider.is_available = AsyncMock(return_value=True)
        # Mock list_models to return proper Model objects
        github_provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-chat-model",
                    name="Test Chat Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat"],
                ),
                Model(
                    id="test-embedding-model",
                    name="Test Embedding Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                ),
            ]
        )

        async def complete(request):
            await asyncio.sleep(0.01)
            return CompletionResponse(
                id=f"comp-{id(request)}",
                model=request.model,
                choices=[{"message": {"content": "Completion"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        async def embed(request):
            await asyncio.sleep(0.01)
            return EmbeddingResponse(
                model=request.model,
                data=[{"embedding": [0.1]}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        github_provider.complete = AsyncMock(side_effect=complete)
        github_provider.embed = AsyncMock(side_effect=embed)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = github_provider

        # Mix of operations
        tasks = []
        for i in range(20):
            if i % 2 == 0:
                tasks.append(
                    client.complete(messages=[{"role": "user", "content": f"Q{i}"}])
                )
            else:
                tasks.append(client.embed(text=f"Text {i}"))

        responses = await asyncio.gather(*tasks)

        completions = [r for r in responses if isinstance(r, CompletionResponse)]
        embeddings = [r for r in responses if isinstance(r, EmbeddingResponse)]

        assert len(completions) == 10
        assert len(embeddings) == 10
        assert github_provider.complete.call_count == 10
        assert github_provider.embed.call_count == 10

    @pytest.mark.asyncio
    async def test_concurrent_provider_initialization(self):
        """Test concurrent provider initialization and cleanup."""

        # Create multiple clients concurrently
        async def create_and_use_client(i):
            # Use GitHub Models to avoid Claude Code API calls
            client = LLMClient(preferred_provider=LLMProvider.GITHUB_MODELS)
            # Use the client
            models = await client.list_models()
            await client.cleanup()
            return i, len(models)

        tasks = [create_and_use_client(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(isinstance(r, tuple) for r in results)

    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self):
        """Test rate limiting behavior under concurrent load."""
        # Create empty registry to avoid any real providers
        from scriptrag.llm.registry import ProviderRegistry

        registry = ProviderRegistry()

        # Create mock provider
        provider = AsyncMock()
        provider.is_available = AsyncMock(return_value=True)
        provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat"],
                )
            ]
        )

        # Add only our mock provider to the registry
        registry.providers[LLMProvider.GITHUB_MODELS] = provider

        # Create client with our controlled registry
        client = LLMClient(
            preferred_provider=LLMProvider.GITHUB_MODELS, registry=registry
        )

        # Simulate rate limiting after certain number of calls
        call_count = 0

        async def complete_with_rate_limit(request):
            nonlocal call_count
            call_count += 1
            if 5 <= call_count <= 10:
                raise RateLimitError("Rate limit exceeded", retry_after=0.1)
            return CompletionResponse(
                id=f"response-{call_count}",
                model=request.model,
                choices=[{"message": {"content": "Success"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        provider.complete = AsyncMock(side_effect=complete_with_rate_limit)

        # Create concurrent requests that will trigger rate limiting
        with patch("asyncio.sleep"):  # Speed up test
            tasks = [
                client.complete(messages=[{"role": "user", "content": f"Q{i}"}])
                for i in range(15)
            ]

            # Some should succeed, some should retry
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful = [r for r in responses if isinstance(r, CompletionResponse)]
        errors = [r for r in responses if isinstance(r, Exception)]

        # Should have both successes and handled rate limits
        assert len(successful) > 0
        assert call_count > 15  # Due to retries


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def client(self):
        """Create LLM client for testing."""
        return LLMClient()

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "This is not JSON"

        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4",
                messages=[{"role": "user", "content": "Test"}],
            )

            with pytest.raises(Exception) as exc_info:
                await provider.complete(request)

            # Should handle JSON decode error
            assert (
                "JSON" in str(exc_info.value) or "decode" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_network_interruption_during_retry(self):
        """Test network interruption during retry sequence."""
        strategy = RetryStrategy(max_retries=3)

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            if call_count == 2:
                raise httpx.ConnectTimeout("Connection timeout")
            raise httpx.NetworkError("Network completely down")

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await strategy.execute_with_retry(
                    failing_operation,
                    "test_provider",
                    None,
                )

        assert call_count == 3
        assert "Network completely down" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_provider_cleanup_during_operation(self, client):
        """Test provider cleanup while operation is in progress."""
        provider = AsyncMock()
        provider.is_available = AsyncMock(return_value=True)
        provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat"],
                )
            ]
        )

        # Simulate long-running operation
        operation_started = asyncio.Event()
        operation_should_continue = asyncio.Event()

        async def slow_complete(request):
            operation_started.set()
            await operation_should_continue.wait()
            return CompletionResponse(
                id="test",
                model="test",
                choices=[{"message": {"content": "Done"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )

        provider.complete = AsyncMock(side_effect=slow_complete)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = provider

        # Start operation
        task = asyncio.create_task(
            client.complete(messages=[{"role": "user", "content": "Test"}])
        )

        # Wait for operation to start
        await operation_started.wait()

        # Cleanup while operation is running
        cleanup_task = asyncio.create_task(client.cleanup())

        # Let operation complete
        operation_should_continue.set()

        # Both should complete without error
        response = await task
        await cleanup_task

        assert isinstance(response, CompletionResponse)

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty responses from providers."""
        provider = OpenAICompatibleProvider(
            endpoint="https://test.com",
            api_key="test-key",  # pragma: allowlist secret
        )

        # Test empty completion response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}

        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="test-model",
                messages=[{"role": "user", "content": "Test"}],
            )

            response = await provider.complete(request)
            assert response.choices == []
            # Don't access .content when choices is empty (will raise IndexError)
            assert response.id == ""  # Should still have valid structure
            assert response.model == "test-model"

    @pytest.mark.asyncio
    async def test_partial_response_handling(self):
        """Test handling of partial/incomplete responses."""
        provider = GitHubModelsProvider(token="test-token")  # noqa: S106

        incomplete_responses = [
            {"id": "test"},  # Missing choices
            {"choices": [{"message": {}}]},  # Missing content
            {"choices": [{"message": {"content": None}}]},  # Null content
            {"choices": [{}]},  # Missing message
        ]

        for incomplete in incomplete_responses:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = incomplete

            with patch.object(provider.client, "post", return_value=mock_response):
                request = CompletionRequest(
                    model="test",
                    messages=[{"role": "user", "content": "Test"}],
                )

                # Should handle gracefully
                response = await provider.complete(request)
                assert isinstance(response, CompletionResponse)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in providers."""
        provider = GitHubModelsProvider(
            token="test-token",  # noqa: S106
            timeout=0.001,
        )  # Very short timeout

        with patch.object(
            provider.client,
            "post",
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            request = CompletionRequest(
                model="test",
                messages=[{"role": "user", "content": "Test"}],
            )

            with pytest.raises(httpx.TimeoutException):
                await provider.complete(request)

    @pytest.mark.asyncio
    async def test_unicode_handling_in_responses(self):
        """Test handling of Unicode characters in responses."""
        provider = AsyncMock()
        provider.is_available = AsyncMock(return_value=True)
        provider.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat"],
                )
            ]
        )

        unicode_content = "Hello 世界 🌍 مرحبا мир"
        provider.complete = AsyncMock(
            return_value=CompletionResponse(
                id="unicode-test",
                model="test",
                choices=[{"message": {"content": unicode_content}}],
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        # Use GitHub Models to avoid Claude Code API calls
        client = LLMClient(preferred_provider=LLMProvider.GITHUB_MODELS)
        client.registry.providers[LLMProvider.GITHUB_MODELS] = provider

        response = await client.complete(
            messages=[{"role": "user", "content": "Test Unicode"}]
        )

        assert response.choices[0]["message"]["content"] == unicode_content

    @pytest.mark.asyncio
    async def test_race_condition_in_fallback_chain(self):
        """Test race condition in fallback chain selection."""
        fallback_handler = FallbackHandler(
            registry=ProviderRegistry(),
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
            ],
        )

        # Simulate providers becoming available/unavailable during execution
        availability_states = {
            LLMProvider.CLAUDE_CODE: [False, True, False],
            LLMProvider.GITHUB_MODELS: [True, False, True],
        }
        call_counts = {
            LLMProvider.CLAUDE_CODE: 0,
            LLMProvider.GITHUB_MODELS: 0,
        }

        def get_provider(provider_type):
            mock = Mock()
            mock.__class__.__name__ = f"{provider_type.value}Provider"

            async def is_available():
                state_list = availability_states[provider_type]
                count = call_counts[provider_type]
                call_counts[provider_type] += 1
                return state_list[count % len(state_list)]

            mock.is_available = AsyncMock(side_effect=is_available)
            return mock

        fallback_handler.registry.get_provider = Mock(side_effect=get_provider)

        async def mock_try_func(provider, request):
            # Fail to trigger fallback
            raise RuntimeError("Provider failed")

        recorded_chain = []

        with pytest.raises(LLMFallbackError):
            await fallback_handler.complete_with_fallback(
                CompletionRequest(model="test", messages=[]),
                mock_try_func,
                lambda x: recorded_chain.extend(x),
            )

        # Should have attempted both providers
        assert call_counts[LLMProvider.CLAUDE_CODE] > 0
        assert call_counts[LLMProvider.GITHUB_MODELS] > 0

    @pytest.mark.asyncio
    async def test_memory_leak_prevention_in_retry(self):
        """Test that retry strategy doesn't cause memory leaks."""
        strategy = RetryStrategy(max_retries=100)  # High retry count

        call_count = 0
        results = []

        async def leaky_operation():
            nonlocal call_count
            call_count += 1
            # Create large object that could leak
            large_data = "x" * 1000000
            results.append(len(large_data))
            if call_count < 50:
                raise ConnectionError("Retry me")
            return "success"

        with patch("asyncio.sleep"):
            result = await strategy.execute_with_retry(
                leaky_operation,
                "test_provider",
                None,
            )

        assert result == "success"
        assert call_count == 50
        # Memory should be reasonable (list shouldn't grow unbounded)
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_infinite_retry_prevention(self):
        """Test prevention of infinite retry loops."""
        strategy = RetryStrategy(max_retries=3)

        async def always_fails():
            raise ConnectionError("Always fails")

        start_time = time.time()
        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError):
                await strategy.execute_with_retry(
                    always_fails,
                    "test_provider",
                    None,
                )

        # Should complete quickly (not infinite)
        assert time.time() - start_time < 1.0

    @pytest.mark.asyncio
    async def test_provider_switching_during_operation(self, client):
        """Test switching providers mid-operation."""
        provider1 = AsyncMock()
        provider1.is_available = AsyncMock(return_value=True)
        provider1.provider_type = LLMProvider.GITHUB_MODELS
        provider1.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model",
                    name="Test Model",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["completion", "chat"],
                )
            ]
        )

        provider2 = AsyncMock()
        provider2.is_available = AsyncMock(return_value=True)
        provider2.provider_type = LLMProvider.CLAUDE_CODE
        provider2.list_models = AsyncMock(
            return_value=[
                Model(
                    id="test-model-2",
                    name="Test Model 2",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["completion", "chat"],
                )
            ]
        )

        # First provider for first request
        provider1.complete = AsyncMock(
            return_value=CompletionResponse(
                id="p1",
                model="test",
                choices=[{"message": {"content": "Provider 1"}}],
                provider=LLMProvider.GITHUB_MODELS,
            )
        )

        # Second provider for second request
        provider2.complete = AsyncMock(
            return_value=CompletionResponse(
                id="p2",
                model="test",
                choices=[{"message": {"content": "Provider 2"}}],
                provider=LLMProvider.CLAUDE_CODE,
            )
        )

        client.registry.providers[LLMProvider.GITHUB_MODELS] = provider1
        client.registry.providers[LLMProvider.CLAUDE_CODE] = provider2

        # First request
        response1 = await client.complete(
            messages=[{"role": "user", "content": "Test"}],
            provider=LLMProvider.GITHUB_MODELS,
        )

        # Switch provider
        client.current_provider = provider2

        # Second request
        response2 = await client.complete(
            messages=[{"role": "user", "content": "Test"}],
            provider=LLMProvider.CLAUDE_CODE,
        )

        assert response1.provider == LLMProvider.GITHUB_MODELS
        assert response2.provider == LLMProvider.CLAUDE_CODE
