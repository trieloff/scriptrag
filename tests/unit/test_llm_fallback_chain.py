"""Comprehensive tests for LLM fallback chain behavior."""

from unittest.mock import AsyncMock, Mock

import pytest

from scriptrag.exceptions import LLMFallbackError
from scriptrag.llm.fallback import FallbackHandler
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
)
from scriptrag.llm.registry import ProviderRegistry


class TestFallbackChain:
    """Test fallback chain behavior and error aggregation."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry with providers."""
        registry = Mock(spec=ProviderRegistry)
        registry.providers = {}
        return registry

    @pytest.fixture
    def fallback_handler(self, mock_registry):
        """Create fallback handler with mock registry."""
        return FallbackHandler(
            registry=mock_registry,
            preferred_provider=LLMProvider.CLAUDE_CODE,
            fallback_order=[
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
                LLMProvider.OPENAI_COMPATIBLE,
            ],
            debug_mode=True,
        )

    @pytest.fixture
    def completion_request(self):
        """Create sample completion request."""
        return CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
        )

    @pytest.fixture
    def embedding_request(self):
        """Create sample embedding request."""
        return EmbeddingRequest(
            model="embedding-model",
            input="Test text",
            dimensions=512,
        )

    @pytest.mark.asyncio
    async def test_fallback_chain_success_on_preferred(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test successful completion with preferred provider."""
        # Setup preferred provider
        mock_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_provider.is_available = AsyncMock(return_value=True)
        expected_response = CompletionResponse(
            id="test-id",
            model="test-model",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.CLAUDE_CODE,
        )

        async def mock_try_func(provider, request):
            return expected_response

        mock_registry.get_provider.return_value = mock_provider

        # Track fallback chain
        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        result = await fallback_handler.complete_with_fallback(
            completion_request,
            mock_try_func,
            record_chain,
        )

        # Verify
        assert result == expected_response
        # The chain should contain: preferred + fallback order (without duplicates)
        assert recorded_chain == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]
        mock_provider.is_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_chain_preferred_fails_fallback_succeeds(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test fallback to secondary provider when preferred fails."""
        # Setup providers
        preferred_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        preferred_provider.is_available = AsyncMock(return_value=True)
        preferred_provider.__class__.__name__ = "ClaudeCodeProvider"

        fallback_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        fallback_provider.is_available = AsyncMock(return_value=True)
        fallback_provider.__class__.__name__ = "GitHubModelsProvider"

        expected_response = CompletionResponse(
            id="fallback-id",
            model="fallback-model",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Fallback response"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.GITHUB_MODELS,
        )

        # Mock registry to return different providers
        def get_provider(provider_type):
            if provider_type == LLMProvider.CLAUDE_CODE:
                return preferred_provider
            if provider_type == LLMProvider.GITHUB_MODELS:
                return fallback_provider
            return None

        mock_registry.get_provider.side_effect = get_provider

        # Mock try function to fail for preferred, succeed for fallback
        async def mock_try_func(provider, request):
            if provider == preferred_provider:
                raise RuntimeError("Preferred provider failed")
            return expected_response

        # Track fallback chain
        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        result = await fallback_handler.complete_with_fallback(
            completion_request,
            mock_try_func,
            record_chain,
        )

        # Verify
        assert result == expected_response
        assert preferred_provider.is_available.called
        assert fallback_provider.is_available.called

    @pytest.mark.asyncio
    async def test_fallback_chain_all_providers_fail_with_error_aggregation(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test error aggregation when all providers fail."""
        # Setup providers that all fail
        providers = {
            LLMProvider.CLAUDE_CODE: (
                "ClaudeCodeProvider",
                RuntimeError("Claude error"),
            ),
            LLMProvider.GITHUB_MODELS: (
                "GitHubModelsProvider",
                ValueError("GitHub error"),
            ),
            LLMProvider.OPENAI_COMPATIBLE: (
                "OpenAIProvider",
                ConnectionError("OpenAI connection failed"),
            ),
        }

        def get_provider(provider_type):
            if provider_type in providers:
                mock = AsyncMock(
                    spec=["complete", "cleanup", "embed", "list_models", "is_available"]
                )
                mock.is_available = AsyncMock(return_value=True)
                mock.__class__.__name__ = providers[provider_type][0]
                return mock
            return None

        mock_registry.get_provider.side_effect = get_provider

        # Mock try function to fail with specific errors
        async def mock_try_func(provider, request):
            for _ptype, (pname, error) in providers.items():
                if provider.__class__.__name__ == pname:
                    raise error
            raise RuntimeError("Unknown provider")

        # Track fallback chain
        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and verify error aggregation
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        assert "All LLM providers failed" in str(error)
        assert len(error.provider_errors) == 3
        assert "claude_code" in error.provider_errors
        assert "github_models" in error.provider_errors
        assert "openai_compatible" in error.provider_errors
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
        # Debug info should be included when debug_mode=True
        assert error.debug_info is not None

    @pytest.mark.asyncio
    async def test_fallback_chain_provider_not_available(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test fallback when provider is not available."""
        # Setup providers with availability issues
        unavailable_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        unavailable_provider.is_available = AsyncMock(return_value=False)
        unavailable_provider.__class__.__name__ = "ClaudeCodeProvider"

        available_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        available_provider.is_available = AsyncMock(return_value=True)
        available_provider.__class__.__name__ = "GitHubModelsProvider"

        def get_provider(provider_type):
            if provider_type == LLMProvider.CLAUDE_CODE:
                return unavailable_provider
            if provider_type == LLMProvider.GITHUB_MODELS:
                return available_provider
            return None

        mock_registry.get_provider.side_effect = get_provider

        expected_response = CompletionResponse(
            id="github-id",
            model="github-model",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "GitHub response"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.GITHUB_MODELS,
        )

        async def mock_try_func(provider, request):
            if provider == available_provider:
                return expected_response
            raise RuntimeError("Should not be called")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        result = await fallback_handler.complete_with_fallback(
            completion_request,
            mock_try_func,
            record_chain,
        )

        # Verify
        assert result == expected_response
        assert unavailable_provider.is_available.called
        assert available_provider.is_available.called

    @pytest.mark.asyncio
    async def test_fallback_chain_provider_not_in_registry(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test fallback when provider is not in registry."""
        # Only return provider for GitHub Models
        available_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        available_provider.is_available = AsyncMock(return_value=True)
        available_provider.__class__.__name__ = "GitHubModelsProvider"

        def get_provider(provider_type):
            if provider_type == LLMProvider.GITHUB_MODELS:
                return available_provider
            return None  # Others not in registry

        mock_registry.get_provider.side_effect = get_provider

        expected_response = CompletionResponse(
            id="github-id",
            model="github-model",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "GitHub response"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.GITHUB_MODELS,
        )

        async def mock_try_func(provider, request):
            return expected_response

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        result = await fallback_handler.complete_with_fallback(
            completion_request,
            mock_try_func,
            record_chain,
        )

        # Verify
        assert result == expected_response
        assert available_provider.is_available.called

    @pytest.mark.asyncio
    async def test_embedding_fallback_chain_success(
        self, fallback_handler, mock_registry, embedding_request
    ):
        """Test embedding fallback chain with success."""
        # Setup provider
        mock_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_provider.is_available = AsyncMock(return_value=True)
        expected_response = EmbeddingResponse(
            model="embedding-model",
            data=[{"embedding": [0.1, 0.2, 0.3]}],
            provider=LLMProvider.CLAUDE_CODE,
        )

        async def mock_try_func(provider, request):
            return expected_response

        mock_registry.get_provider.return_value = mock_provider

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        result = await fallback_handler.embed_with_fallback(
            embedding_request,
            mock_try_func,
            record_chain,
        )

        # Verify
        assert result == expected_response
        assert recorded_chain == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]

    @pytest.mark.asyncio
    async def test_embedding_fallback_all_fail(
        self, fallback_handler, mock_registry, embedding_request
    ):
        """Test embedding fallback when all providers fail."""
        # Setup providers that all fail
        mock_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.__class__.__name__ = "TestProvider"

        mock_registry.get_provider.return_value = mock_provider

        async def mock_try_func(provider, request):
            raise RuntimeError("Embedding failed")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and verify
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.embed_with_fallback(
                embedding_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        assert "All LLM providers failed for embedding" in str(error)

    @pytest.mark.asyncio
    async def test_fallback_chain_order_customization(self, mock_registry):
        """Test custom fallback chain order."""
        custom_order = [
            LLMProvider.GITHUB_MODELS,
            LLMProvider.OPENAI_COMPATIBLE,
            LLMProvider.CLAUDE_CODE,
        ]

        handler = FallbackHandler(
            registry=mock_registry,
            preferred_provider=LLMProvider.GITHUB_MODELS,
            fallback_order=custom_order,
            debug_mode=False,
        )

        # Setup providers
        attempts = []

        def get_provider(provider_type):
            mock = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            mock.is_available = AsyncMock(return_value=True)
            mock.__class__.__name__ = f"{provider_type.value}Provider"
            return mock

        mock_registry.get_provider.side_effect = get_provider

        async def mock_try_func(provider, request):
            attempts.append(provider.__class__.__name__)
            if len(attempts) == 3:  # Succeed on third attempt
                return CompletionResponse(
                    id="test",
                    model="test",
                    choices=[
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Success"},
                            "finish_reason": "stop",
                        }
                    ],
                    provider=LLMProvider.OPENAI_COMPATIBLE,
                )
            raise RuntimeError(f"Attempt {len(attempts)} failed")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        request = CompletionRequest(model="test", messages=[])
        result = await handler.complete_with_fallback(
            request,
            mock_try_func,
            record_chain,
        )

        # Verify order
        assert attempts == [
            "github_modelsProvider",  # Preferred first
            "openai_compatibleProvider",  # Second in fallback order
            "claude_codeProvider",  # Third in fallback order
        ]

    @pytest.mark.asyncio
    async def test_fallback_debug_mode_includes_stack_traces(
        self, mock_registry, completion_request
    ):
        """Test debug mode includes stack traces in error info."""
        handler = FallbackHandler(
            registry=mock_registry,
            preferred_provider=LLMProvider.CLAUDE_CODE,
            debug_mode=True,
        )

        mock_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.__class__.__name__ = "TestProvider"

        mock_registry.get_provider.return_value = mock_provider

        async def mock_try_func(provider, request):
            raise ValueError("Test error with traceback")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        with pytest.raises(LLMFallbackError) as exc_info:
            await handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        # Verify debug info included
        error = exc_info.value
        assert error.debug_info is not None
        assert "claude_code_error" in error.debug_info
        assert "stack_trace" in error.debug_info["claude_code_error"]
        assert "timestamp" in error.debug_info["claude_code_error"]

    @pytest.mark.asyncio
    async def test_fallback_no_debug_mode_excludes_details(
        self, mock_registry, completion_request
    ):
        """Test non-debug mode excludes detailed error info."""
        handler = FallbackHandler(
            registry=mock_registry,
            preferred_provider=LLMProvider.CLAUDE_CODE,
            debug_mode=False,  # Debug mode off
        )

        mock_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.__class__.__name__ = "TestProvider"

        mock_registry.get_provider.return_value = mock_provider

        async def mock_try_func(provider, request):
            raise ValueError("Test error")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute
        with pytest.raises(LLMFallbackError) as exc_info:
            await handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        # Verify debug info excluded
        error = exc_info.value
        assert error.debug_info is None
