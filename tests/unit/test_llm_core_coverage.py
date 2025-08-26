"""Comprehensive unit tests for LLM core modules to achieve 99% code coverage."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.llm.base_provider import EnhancedBaseLLMProvider
from scriptrag.llm.model_registry import ModelRegistry
from scriptrag.llm.models import LLMProvider
from scriptrag.llm.providers import (
    ClaudeCodeProvider,
    GitHubModelsProvider,
    OpenAICompatibleProvider,
)
from scriptrag.llm.rate_limiter import RateLimiter, RetryHandler
from scriptrag.llm.registry import ProviderRegistry


class TestModelRegistry:
    """Test ModelRegistry functionality."""

    def test_github_models_static_list(self):
        """Test GitHub Models static model list."""
        models = ModelRegistry.GITHUB_MODELS

        assert len(models) >= 2

        # Check for expected models
        model_ids = [model.id for model in models]
        assert "gpt-4o" in model_ids
        assert "gpt-4o-mini" in model_ids

        # Verify model properties
        gpt4o = next(m for m in models if m.id == "gpt-4o")
        assert gpt4o.name == "GPT-4o"
        assert gpt4o.provider == LLMProvider.GITHUB_MODELS
        assert "completion" in gpt4o.capabilities
        assert "chat" in gpt4o.capabilities
        assert gpt4o.context_window == 128000
        assert gpt4o.max_output_tokens == 16384

    def test_claude_code_models_static_list(self):
        """Test Claude Code static model list."""
        models = ModelRegistry.CLAUDE_CODE_MODELS

        assert len(models) >= 8  # Should have multiple Claude models

        # Check for expected models
        model_ids = [model.id for model in models]
        assert "claude-3-opus-20240229" in model_ids
        assert "claude-3-sonnet-20240229" in model_ids
        assert "claude-3-haiku-20240307" in model_ids
        assert "claude-3-5-sonnet-20241022" in model_ids
        assert "claude-3-5-haiku-20241022" in model_ids

        # Check aliases
        assert "sonnet" in model_ids
        assert "opus" in model_ids
        assert "haiku" in model_ids

        # Verify model properties
        opus = next(m for m in models if m.id == "claude-3-opus-20240229")
        assert opus.name == "Claude 3 Opus"
        assert opus.provider == LLMProvider.CLAUDE_CODE
        assert "completion" in opus.capabilities
        assert "chat" in opus.capabilities
        assert opus.context_window == 200000
        assert opus.max_output_tokens == 4096

        # Check 3.5 models have higher token limits
        sonnet_35 = next(m for m in models if m.id == "claude-3-5-sonnet-20241022")
        assert sonnet_35.max_output_tokens == 8192

    def test_github_model_id_map(self):
        """Test GitHub model ID mapping."""
        id_map = ModelRegistry.GITHUB_MODEL_ID_MAP

        assert len(id_map) >= 7

        # Check for expected mappings
        assert (
            "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1" in id_map
        )
        assert (
            id_map["azureml://registries/azure-openai/models/gpt-4o-mini/versions/1"]
            == "gpt-4o-mini"
        )

        assert "azureml://registries/azure-openai/models/gpt-4o/versions/2" in id_map
        assert (
            id_map["azureml://registries/azure-openai/models/gpt-4o/versions/2"]
            == "gpt-4o"
        )

        # Check Llama models
        llama_key = (
            "azureml://registries/azureml-meta/models/Meta-Llama-3-70B-Instruct/"
            "versions/6"
        )
        assert llama_key in id_map
        assert id_map[llama_key] == "Meta-Llama-3-70B-Instruct"

    def test_get_static_models_github(self):
        """Test get_static_models for GitHub Models."""
        models = ModelRegistry.get_static_models(LLMProvider.GITHUB_MODELS)
        assert models == ModelRegistry.GITHUB_MODELS

    def test_get_static_models_claude_code(self):
        """Test get_static_models for Claude Code."""
        models = ModelRegistry.get_static_models(LLMProvider.CLAUDE_CODE)
        assert models == ModelRegistry.CLAUDE_CODE_MODELS

    def test_get_static_models_unknown_provider(self):
        """Test get_static_models for unknown provider."""
        models = ModelRegistry.get_static_models(LLMProvider.OPENAI_COMPATIBLE)
        assert models == []

    def test_model_registry_is_class_var(self):
        """Test that model lists are ClassVar (immutable at class level)."""
        # These should be accessible from the class without instantiation
        assert hasattr(ModelRegistry, "GITHUB_MODELS")
        assert hasattr(ModelRegistry, "CLAUDE_CODE_MODELS")
        assert hasattr(ModelRegistry, "GITHUB_MODEL_ID_MAP")

        # Should not be able to create instance attributes with same name
        registry = ModelRegistry()

        # Original class attributes should still be accessible
        assert registry.GITHUB_MODELS == ModelRegistry.GITHUB_MODELS
        assert registry.CLAUDE_CODE_MODELS == ModelRegistry.CLAUDE_CODE_MODELS


class TestProviderRegistry:
    """Test ProviderRegistry functionality."""

    def test_initialization(self):
        """Test ProviderRegistry initialization."""
        registry = ProviderRegistry()

        assert registry.providers == {}
        assert registry._custom_providers == {}

    def test_register_provider_class(self):
        """Test registering custom provider class."""
        registry = ProviderRegistry()

        class CustomProvider(EnhancedBaseLLMProvider):
            provider_type = LLMProvider.OPENAI_COMPATIBLE

            async def _validate_availability(self) -> bool:
                return True

            async def complete(self, request):
                return Mock(spec=object)

            async def embed(self, request):
                return Mock(spec=object)

            async def list_models(self):
                return []

        registry.register_provider_class(LLMProvider.OPENAI_COMPATIBLE, CustomProvider)

        assert LLMProvider.OPENAI_COMPATIBLE in registry._custom_providers
        assert (
            registry._custom_providers[LLMProvider.OPENAI_COMPATIBLE] == CustomProvider
        )

    def test_create_provider_custom(self):
        """Test creating custom registered provider."""
        registry = ProviderRegistry()

        class CustomProvider(EnhancedBaseLLMProvider):
            provider_type = LLMProvider.OPENAI_COMPATIBLE

            def __init__(self, custom_param=None, **kwargs):
                super().__init__(**kwargs)
                self.custom_param = custom_param

            async def _validate_availability(self) -> bool:
                return True

            async def complete(self, request):
                return Mock(spec=object)

            async def embed(self, request):
                return Mock(spec=object)

            async def list_models(self):
                return []

        registry.register_provider_class(LLMProvider.OPENAI_COMPATIBLE, CustomProvider)

        provider = registry.create_provider(
            LLMProvider.OPENAI_COMPATIBLE, custom_param="test"
        )

        assert isinstance(provider, CustomProvider)
        assert provider.custom_param == "test"

    def test_create_provider_claude_code(self):
        """Test creating Claude Code provider."""
        registry = ProviderRegistry()

        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = registry.create_provider(LLMProvider.CLAUDE_CODE)
            assert isinstance(provider, ClaudeCodeProvider)

    def test_create_provider_github_models(self):
        """Test creating GitHub Models provider."""
        registry = ProviderRegistry()

        provider = registry.create_provider(
            LLMProvider.GITHUB_MODELS,
            token="test-token",  # noqa: S106
            timeout=30.0,
        )

        assert isinstance(provider, GitHubModelsProvider)
        assert provider.token == "test-token"  # noqa: S105
        assert provider.timeout == 30.0

    def test_create_provider_openai_compatible(self):
        """Test creating OpenAI-compatible provider."""
        registry = ProviderRegistry()

        provider = registry.create_provider(
            LLMProvider.OPENAI_COMPATIBLE,
            endpoint="https://api.example.com",
            api_key="test-key",  # pragma: allowlist secret
            timeout=60.0,
        )

        assert isinstance(provider, OpenAICompatibleProvider)

    def test_create_provider_unknown(self):
        """Test creating unknown provider type."""
        registry = ProviderRegistry()

        # Test by creating a mock that mimics an unknown enum value
        # Since all known values are handled, we simulate an unknown one
        mock_unknown = Mock(spec=LLMProvider)
        mock_unknown.value = "unknown_provider"

        with pytest.raises(ValueError, match="Unknown provider type"):
            registry.create_provider(mock_unknown)

    def test_initialize_default_providers(self):
        """Test initializing default providers."""
        registry = ProviderRegistry()

        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            providers = registry.initialize_default_providers(
                github_token="gh-token",  # pragma: allowlist secret  # noqa: S106
                openai_endpoint="https://api.example.com",
                openai_api_key="openai-key",  # pragma: allowlist secret
                timeout=45.0,
            )

        assert len(providers) == 3
        assert LLMProvider.CLAUDE_CODE in providers
        assert LLMProvider.GITHUB_MODELS in providers
        assert LLMProvider.OPENAI_COMPATIBLE in providers

        # Check GitHub Models provider configuration
        gh_provider = providers[LLMProvider.GITHUB_MODELS]
        # Cast to GitHubModelsProvider to access token and timeout attributes
        assert isinstance(gh_provider, GitHubModelsProvider)
        assert gh_provider.token == "gh-token"  # noqa: S105
        assert gh_provider.timeout == 45.0

        # Check that registry stores the providers
        assert registry.providers == providers

    def test_get_provider(self):
        """Test getting provider by type."""
        registry = ProviderRegistry()

        # Initially no providers
        assert registry.get_provider(LLMProvider.CLAUDE_CODE) is None

        # Add a provider
        mock_provider = Mock(spec=object)
        registry.providers[LLMProvider.CLAUDE_CODE] = mock_provider

        assert registry.get_provider(LLMProvider.CLAUDE_CODE) == mock_provider

    def test_set_provider(self):
        """Test setting a provider instance."""
        registry = ProviderRegistry()

        mock_provider = Mock(spec=object)
        registry.set_provider(LLMProvider.CLAUDE_CODE, mock_provider)

        assert registry.providers[LLMProvider.CLAUDE_CODE] == mock_provider

    def test_remove_provider(self):
        """Test removing a provider."""
        registry = ProviderRegistry()

        # Add a provider
        mock_provider = Mock(spec=object)
        registry.providers[LLMProvider.CLAUDE_CODE] = mock_provider

        # Remove it
        registry.remove_provider(LLMProvider.CLAUDE_CODE)

        assert LLMProvider.CLAUDE_CODE not in registry.providers

        # Removing non-existent provider should not error
        registry.remove_provider(LLMProvider.GITHUB_MODELS)

    def test_list_providers(self):
        """Test listing provider types."""
        registry = ProviderRegistry()

        # Initially empty
        assert registry.list_providers() == []

        # Add providers
        registry.providers[LLMProvider.CLAUDE_CODE] = Mock(spec=object)
        registry.providers[LLMProvider.GITHUB_MODELS] = Mock(spec=object)

        provider_types = registry.list_providers()
        assert len(provider_types) == 2
        assert LLMProvider.CLAUDE_CODE in provider_types
        assert LLMProvider.GITHUB_MODELS in provider_types

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup of provider resources."""
        registry = ProviderRegistry()

        # Create mock providers with clients
        mock_provider1 = Mock(spec=["client", "provider_type"])
        mock_provider1.client = AsyncMock()
        mock_provider1.client.aclose = AsyncMock()
        mock_provider1.provider_type = LLMProvider.CLAUDE_CODE

        mock_provider2 = Mock(spec=["client", "provider_type"])
        mock_provider2.client = None  # No client to clean up
        mock_provider2.provider_type = LLMProvider.GITHUB_MODELS

        mock_provider3 = Mock(spec=object)
        # No client attribute
        if hasattr(mock_provider3, "client"):
            delattr(mock_provider3, "client")
        mock_provider3.provider_type = LLMProvider.OPENAI_COMPATIBLE

        registry.providers = {
            LLMProvider.CLAUDE_CODE: mock_provider1,
            LLMProvider.GITHUB_MODELS: mock_provider2,
            LLMProvider.OPENAI_COMPATIBLE: mock_provider3,
        }

        await registry.cleanup()

        # Only provider1 should have had its client closed
        mock_provider1.client.aclose.assert_called_once()

        # Others should not have been affected
        assert mock_provider2.client is None

    def test_initialize_default_providers_minimal(self):
        """Test initializing default providers with minimal parameters."""
        registry = ProviderRegistry()

        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            providers = registry.initialize_default_providers()

        assert len(providers) == 3

        # Check that providers were created with timeout
        gh_provider = providers[LLMProvider.GITHUB_MODELS]
        # Cast to GitHubModelsProvider to access timeout attribute
        assert isinstance(gh_provider, GitHubModelsProvider)
        # Token may be set from environment, so we just check it exists
        assert hasattr(gh_provider, "token")
        assert gh_provider.timeout == 30.0  # Default timeout


class TestRateLimiterCoverage:
    """Additional tests for RateLimiter coverage."""

    def test_is_rate_limited_edge_cases(self):
        """Test is_rate_limited edge cases."""
        rate_limiter = RateLimiter()

        # Test with reset time exactly at current time
        current_time = time.time()
        rate_limiter._rate_limit_reset_time = current_time

        # Should still be considered rate limited at exactly the reset time
        result = rate_limiter.is_rate_limited()
        # This might be True or False depending on timing, but should not error
        assert isinstance(result, bool)

    def test_set_rate_limit_zero_seconds(self):
        """Test set_rate_limit with zero seconds."""
        rate_limiter = RateLimiter()

        rate_limiter.set_rate_limit(0, "TestAPI")

        # Should immediately not be rate limited
        assert rate_limiter.is_rate_limited() is False
        assert rate_limiter._availability_cache is False

    def test_check_availability_cache_exact_ttl(self):
        """Test check_availability_cache at exact TTL boundary."""
        rate_limiter = RateLimiter()

        # Set cache exactly at TTL boundary
        current_time = time.time()
        rate_limiter._availability_cache = True
        rate_limiter._cache_timestamp = current_time - 300  # Exactly 300 seconds ago

        # Should be expired (>= TTL)
        result = rate_limiter.check_availability_cache(cache_ttl=300)
        assert result is None

    def test_update_availability_cache_false(self):
        """Test update_availability_cache with False value."""
        rate_limiter = RateLimiter()

        rate_limiter.update_availability_cache(False)

        assert rate_limiter._availability_cache is False
        assert rate_limiter._cache_timestamp > 0


class TestRetryHandlerCoverage:
    """Additional tests for RetryHandler coverage."""

    def test_should_retry_boundary_conditions(self):
        """Test should_retry at boundary conditions."""
        handler = RetryHandler(max_retries=3)

        # Test exactly at the limit
        assert handler.should_retry(2) is False  # attempt 2 with max 3
        assert handler.should_retry(1) is True  # attempt 1 with max 3

        # Test with max_retries = 1 (minimal retries)
        handler_minimal = RetryHandler(max_retries=1)
        assert handler_minimal.should_retry(0) is False  # No retries allowed
        assert handler_minimal.should_retry(1) is False  # Beyond limit

    def test_should_retry_with_different_error_types(self):
        """Test should_retry with various error types."""
        handler = RetryHandler(max_retries=3)

        # Test with different exception types
        errors = [
            ValueError("Value error"),
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            RuntimeError("Runtime error"),
        ]

        for error in errors:
            # Should handle different error types consistently
            assert handler.should_retry(0, error) is True
            assert handler.should_retry(2, error) is False

    def test_log_retry_with_empty_reason(self):
        """Test log_retry with empty reason string."""
        handler = RetryHandler()

        # Should handle empty reason gracefully
        handler.log_retry(1, "")
        # None needs to be converted to empty string before calling log_retry
        handler.log_retry(1, "")

    def test_log_retry_various_attempts(self):
        """Test log_retry with different attempt numbers."""
        handler = RetryHandler(max_retries=5)

        # Test logging at various attempt numbers
        for attempt in range(5):
            handler.log_retry(attempt, f"Retry attempt {attempt}")

        # Should handle attempts beyond max_retries
        handler.log_retry(10, "Beyond max retries")

    def test_retry_handler_max_retries_validation(self):
        """Test RetryHandler with various max_retries values."""
        # Test with very small max_retries
        handler_zero = RetryHandler(max_retries=0)
        assert handler_zero.max_retries == 0
        assert handler_zero.should_retry(0) is False

        # Test with large max_retries
        handler_large = RetryHandler(max_retries=100)
        assert handler_large.max_retries == 100
        assert handler_large.should_retry(50) is True
        assert handler_large.should_retry(99) is False


class TestEnhancedBaseLLMProviderCoverage:
    """Additional coverage tests for EnhancedBaseLLMProvider."""

    @pytest.mark.asyncio
    async def test_aexit_cleanup_scenarios(self):
        """Test __aexit__ cleanup in various scenarios."""

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

        # Test cleanup when client is None
        provider.client = None
        await provider.__aexit__(None, None, None)
        assert provider.client is None

        # Test cleanup when client exists
        mock_client = AsyncMock(spec=object)
        provider.client = mock_client

        await provider.__aexit__(None, None, None)

        mock_client.aclose.assert_called_once()
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_is_available_with_exception_in_cache_check(self):
        """Test is_available when cache check raises exception."""

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

        provider = TestProvider(token="test")  # noqa: S106

        # Mock rate_limiter methods to raise exceptions
        with patch.object(
            provider.rate_limiter,
            "check_availability_cache",
            side_effect=Exception("Cache error"),
        ):
            # The exception should be raised, not handled gracefully
            with pytest.raises(Exception, match="Cache error"):
                await provider.is_available()

    def test_handle_rate_limit_non_429_status(self):
        """Test _handle_rate_limit with non-429 status codes."""

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

        # Test with 500 status (should not set rate limit)
        provider._handle_rate_limit(500, "Server error", 60)
        assert not provider.rate_limiter.is_rate_limited()

        # Test with 429 status but no wait_seconds
        provider._handle_rate_limit(429, "Rate limited", None)
        assert not provider.rate_limiter.is_rate_limited()

        # Test with 429 status and zero wait_seconds
        provider._handle_rate_limit(429, "Rate limited", 0)
        assert not provider.rate_limiter.is_rate_limited()

    @pytest.mark.asyncio
    async def test_make_request_with_custom_headers(self):
        """Test _make_request with custom headers that override auth headers."""

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

        provider = TestProvider(
            token="test-token",  # noqa: S106
            base_url="https://api.example.com",
        )

        mock_response = Mock(spec=object)
        mock_client = AsyncMock(spec=object)
        mock_client.post.return_value = mock_response

        provider.client = mock_client

        # Custom headers that override default ones
        custom_headers = {
            "Authorization": "Bearer custom-token",
            "Custom-Header": "custom-value",
        }

        response = await provider._make_request("POST", "/test", headers=custom_headers)

        assert response == mock_response

        # Verify custom headers were used
        call_args = mock_client.post.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer custom-token"  # Overridden
        assert headers["Custom-Header"] == "custom-value"
        assert headers["Content-Type"] == "application/json"  # From auth headers

    def test_init_model_discovery_none_cache_ttl(self):
        """Test _init_model_discovery with None cache TTL from settings."""

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

        mock_discovery_class = Mock(spec=object)

        with patch("scriptrag.llm.base_provider.get_settings") as mock_get_settings:
            mock_settings = Mock(
                spec=["llm_model_cache_ttl", "llm_force_static_models"]
            )
            mock_settings.llm_model_cache_ttl = -1  # Negative value
            mock_settings.llm_force_static_models = True
            mock_get_settings.return_value = mock_settings

            provider = TestProvider()

            provider._init_model_discovery(mock_discovery_class, [])

            # Verify cache_ttl is None for negative values
            call_kwargs = mock_discovery_class.call_args[1]
            assert call_kwargs["cache_ttl"] is None
            assert call_kwargs["use_cache"] is False
            assert call_kwargs["force_static"] is True
