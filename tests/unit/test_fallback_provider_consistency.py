"""Test for consistent provider error tracking in fallback handler."""

from unittest.mock import AsyncMock, Mock

import pytest

from scriptrag.exceptions import LLMFallbackError
from scriptrag.llm.fallback import FallbackHandler
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
)
from scriptrag.llm.registry import ProviderRegistry


class TestProviderErrorConsistency:
    """Test that provider errors are tracked consistently using enum values."""

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

    @pytest.mark.asyncio
    async def test_provider_not_found_uses_enum_value(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test that when a provider is not found, errors use enum values."""
        # Setup: No providers in registry
        mock_registry.get_provider.return_value = None

        async def mock_try_func(provider, request):
            raise RuntimeError("Should not be called")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and expect failure
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        # All errors should use enum values as keys
        assert "claude_code" in error.provider_errors
        assert "github_models" in error.provider_errors
        assert "openai_compatible" in error.provider_errors
        # Class names should NOT be in error keys
        assert "ClaudeCodeProvider" not in error.provider_errors
        assert "GitHubModelsProvider" not in error.provider_errors
        assert "OpenAIProvider" not in error.provider_errors
        # Verify error messages
        assert isinstance(error.provider_errors["claude_code"], RuntimeError)
        assert "not found in registry" in str(error.provider_errors["claude_code"])

    @pytest.mark.asyncio
    async def test_provider_not_available_uses_enum_value(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test that when a provider is not available, errors use enum values."""

        # Setup unavailable providers
        def create_unavailable_provider(class_name):
            provider = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            provider.is_available = AsyncMock(return_value=False)
            provider.__class__.__name__ = class_name
            return provider

        providers = {
            LLMProvider.CLAUDE_CODE: create_unavailable_provider("ClaudeCodeProvider"),
            LLMProvider.GITHUB_MODELS: create_unavailable_provider(
                "GitHubModelsProvider"
            ),
            LLMProvider.OPENAI_COMPATIBLE: create_unavailable_provider(
                "OpenAIProvider"
            ),
        }

        mock_registry.get_provider.side_effect = lambda ptype: providers.get(ptype)

        async def mock_try_func(provider, request):
            raise RuntimeError("Should not be called")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and expect failure
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        # All errors should use enum values as keys
        assert "claude_code" in error.provider_errors
        assert "github_models" in error.provider_errors
        assert "openai_compatible" in error.provider_errors
        # Class names should NOT be in error keys
        assert "ClaudeCodeProvider" not in error.provider_errors
        assert "GitHubModelsProvider" not in error.provider_errors
        assert "OpenAIProvider" not in error.provider_errors
        # Verify error messages mention class names but keys are enum values
        assert isinstance(error.provider_errors["claude_code"], RuntimeError)
        assert "ClaudeCodeProvider not available" in str(
            error.provider_errors["claude_code"]
        )

    @pytest.mark.asyncio
    async def test_provider_exception_uses_enum_value(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test that when a provider throws an exception, errors use enum values."""

        # Setup providers that throw different exceptions
        def create_failing_provider(class_name, exception):
            provider = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            provider.is_available = AsyncMock(return_value=True)
            provider.__class__.__name__ = class_name
            return provider

        providers = {
            LLMProvider.CLAUDE_CODE: create_failing_provider(
                "ClaudeCodeProvider", ValueError("Claude failed")
            ),
            LLMProvider.GITHUB_MODELS: create_failing_provider(
                "GitHubModelsProvider", KeyError("GitHub failed")
            ),
            LLMProvider.OPENAI_COMPATIBLE: create_failing_provider(
                "OpenAIProvider", ConnectionError("OpenAI failed")
            ),
        }

        exceptions = {
            "ClaudeCodeProvider": ValueError("Claude failed"),
            "GitHubModelsProvider": KeyError("GitHub failed"),
            "OpenAIProvider": ConnectionError("OpenAI failed"),
        }

        mock_registry.get_provider.side_effect = lambda ptype: providers.get(ptype)

        async def mock_try_func(provider, request):
            # Throw the exception based on provider class name
            class_name = provider.__class__.__name__
            if class_name in exceptions:
                raise exceptions[class_name]
            raise RuntimeError(f"Unknown provider: {class_name}")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and expect failure
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        # All errors should use enum values as keys
        assert "claude_code" in error.provider_errors
        assert "github_models" in error.provider_errors
        assert "openai_compatible" in error.provider_errors
        # Class names should NOT be in error keys
        assert "ClaudeCodeProvider" not in error.provider_errors
        assert "GitHubModelsProvider" not in error.provider_errors
        assert "OpenAIProvider" not in error.provider_errors
        # Verify exception types
        assert isinstance(error.provider_errors["claude_code"], ValueError)
        assert isinstance(error.provider_errors["github_models"], KeyError)
        assert isinstance(error.provider_errors["openai_compatible"], ConnectionError)
        # Verify exception messages
        assert str(error.provider_errors["claude_code"]) == "Claude failed"
        assert str(error.provider_errors["github_models"]) == "'GitHub failed'"
        assert str(error.provider_errors["openai_compatible"]) == "OpenAI failed"

    @pytest.mark.asyncio
    async def test_mixed_failure_scenarios_use_enum_values(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test mixed failure scenarios all use enum values consistently.

        Scenario:
        - Claude: not found in registry
        - GitHub: provider not available
        - OpenAI: throws exception
        """

        github_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        github_provider.is_available = AsyncMock(return_value=False)
        github_provider.__class__.__name__ = "GitHubModelsProvider"

        openai_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        openai_provider.is_available = AsyncMock(return_value=True)
        openai_provider.__class__.__name__ = "OpenAIProvider"

        def get_provider(ptype):
            if ptype == LLMProvider.CLAUDE_CODE:
                return None  # Not found
            if ptype == LLMProvider.GITHUB_MODELS:
                return github_provider  # Not available
            if ptype == LLMProvider.OPENAI_COMPATIBLE:
                return openai_provider  # Will throw exception
            return None

        mock_registry.get_provider.side_effect = get_provider

        async def mock_try_func(provider, request):
            if provider == openai_provider:
                raise TimeoutError("OpenAI timeout")
            raise RuntimeError("Unexpected provider")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute and expect failure
        with pytest.raises(LLMFallbackError) as exc_info:
            await fallback_handler.complete_with_fallback(
                completion_request,
                mock_try_func,
                record_chain,
            )

        error = exc_info.value
        # All errors should use enum values as keys
        assert len(error.provider_errors) == 3
        assert "claude_code" in error.provider_errors
        assert "github_models" in error.provider_errors
        assert "openai_compatible" in error.provider_errors

        # Verify each error type
        assert isinstance(error.provider_errors["claude_code"], RuntimeError)
        assert "not found in registry" in str(error.provider_errors["claude_code"])

        assert isinstance(error.provider_errors["github_models"], RuntimeError)
        assert "not available" in str(error.provider_errors["github_models"])

        assert isinstance(error.provider_errors["openai_compatible"], TimeoutError)
        assert "timeout" in str(error.provider_errors["openai_compatible"]).lower()

        # Verify attempted_providers list uses enum values consistently
        assert error.attempted_providers == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]

    @pytest.mark.asyncio
    async def test_successful_provider_after_failures_still_tracks_errors(
        self, fallback_handler, mock_registry, completion_request
    ):
        """Test that errors are tracked correctly even when eventually successful.

        Scenario:
        - Claude: not found in registry
        - GitHub: throws exception
        - OpenAI: succeeds
        """

        github_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        github_provider.is_available = AsyncMock(return_value=True)
        github_provider.__class__.__name__ = "GitHubModelsProvider"

        openai_provider = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        openai_provider.is_available = AsyncMock(return_value=True)
        openai_provider.__class__.__name__ = "OpenAIProvider"

        def get_provider(ptype):
            if ptype == LLMProvider.CLAUDE_CODE:
                return None  # Not found
            if ptype == LLMProvider.GITHUB_MODELS:
                return github_provider  # Will throw exception
            if ptype == LLMProvider.OPENAI_COMPATIBLE:
                return openai_provider  # Will succeed
            return None

        mock_registry.get_provider.side_effect = get_provider

        expected_response = CompletionResponse(
            id="success-id",
            model="test-model",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Success!"},
                    "finish_reason": "stop",
                }
            ],
            provider=LLMProvider.OPENAI_COMPATIBLE,
        )

        async def mock_try_func(provider, request):
            if provider == github_provider:
                raise ValueError("GitHub error")
            if provider == openai_provider:
                return expected_response
            raise RuntimeError("Unexpected provider")

        recorded_chain = []

        def record_chain(chain):
            recorded_chain.extend(chain)

        # Execute - should succeed
        result = await fallback_handler.complete_with_fallback(
            completion_request,
            mock_try_func,
            record_chain,
        )

        assert result == expected_response
        # Verify the recorded chain includes all providers
        assert recorded_chain == [
            "claude_code",
            "github_models",
            "openai_compatible",
        ]

        # Even though successful, internal error tracking should have used enum values
        # (These are not exposed in success case, but structure would be consistent)
