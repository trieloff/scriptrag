"""Comprehensive tests for LLM providers to achieve 99% coverage."""

import json
import os
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from scriptrag.llm.base_provider import EnhancedBaseLLMProvider
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    LLMProvider,
    Model,
)
from scriptrag.llm.providers.claude_code import ClaudeCodeProvider
from scriptrag.llm.providers.github_models import GitHubModelsProvider
from scriptrag.llm.rate_limiter import GitHubRateLimitParser, RateLimiter, RetryHandler


class MockProvider(EnhancedBaseLLMProvider):
    """Mock provider for testing base class."""

    provider_type = LLMProvider.OPENAI_COMPATIBLE

    async def _validate_availability(self) -> bool:
        return True

    async def list_models(self) -> list[Model]:
        return []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="test", model="test", choices=[], usage={}, provider=self.provider_type
        )

    async def embed(self, request: EmbeddingRequest):
        return {"model": "test", "data": [], "usage": {}}


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        assert limiter._rate_limit_reset_time == 0
        assert limiter._availability_cache is None
        assert limiter._cache_timestamp == 0

    def test_is_rate_limited_no_limit(self):
        """Test rate limiting when no limit is set."""
        limiter = RateLimiter()
        assert not limiter.is_rate_limited()

    def test_is_rate_limited_expired(self):
        """Test rate limiting when limit has expired."""
        limiter = RateLimiter()
        # Set reset time in the past
        limiter._rate_limit_reset_time = time.time() - 10
        assert not limiter.is_rate_limited()

    def test_is_rate_limited_active(self):
        """Test rate limiting when limit is active."""
        limiter = RateLimiter()
        # Set reset time in the future
        limiter._rate_limit_reset_time = time.time() + 10
        assert limiter.is_rate_limited()

    def test_set_rate_limit(self):
        """Test setting rate limit."""
        limiter = RateLimiter()
        wait_seconds = 30

        limiter.set_rate_limit(wait_seconds, "TestProvider")

        # Should be rate limited
        assert limiter.is_rate_limited()
        assert limiter._rate_limit_reset_time > time.time()
        assert limiter._availability_cache is False

    def test_availability_cache_miss(self):
        """Test availability cache when cache is empty."""
        limiter = RateLimiter()
        assert limiter.check_availability_cache() is None

    def test_availability_cache_expired(self):
        """Test availability cache when cache is expired."""
        limiter = RateLimiter()
        limiter._availability_cache = True
        limiter._cache_timestamp = time.time() - 400  # Expired (>300s)

        assert limiter.check_availability_cache() is None

    def test_availability_cache_hit(self):
        """Test availability cache when cache is valid."""
        limiter = RateLimiter()
        limiter._availability_cache = True
        limiter._cache_timestamp = time.time()  # Fresh

        assert limiter.check_availability_cache() is True

    def test_availability_cache_custom_ttl(self):
        """Test availability cache with custom TTL."""
        limiter = RateLimiter()
        limiter._availability_cache = False
        limiter._cache_timestamp = time.time() - 50  # Within 60s

        assert limiter.check_availability_cache(cache_ttl=60) is False

    def test_update_availability_cache(self):
        """Test updating availability cache."""
        limiter = RateLimiter()

        limiter.update_availability_cache(True)
        assert limiter._availability_cache is True
        assert limiter._cache_timestamp > 0


class TestGitHubRateLimitParser:
    """Test GitHub rate limit error parsing."""

    def test_parse_valid_rate_limit_error(self):
        """Test parsing valid rate limit error."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 42911 seconds before retrying.",
                }
            }
        )

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds == 42911

    def test_parse_different_message_format(self):
        """Test parsing with different message format."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": (
                        "Rate limit exceeded. Please wait 123 seconds before retrying."
                    ),
                }
            }
        )

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds == 123

    def test_parse_no_wait_time(self):
        """Test parsing error without wait time."""
        error_text = json.dumps(
            {"error": {"code": "RateLimitReached", "message": "Rate limit exceeded."}}
        )

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds is None

    def test_parse_different_error_code(self):
        """Test parsing with different error code."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "SomeOtherError",
                    "message": "Please wait 123 seconds before retrying.",
                }
            }
        )

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds is None

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        error_text = "This is not valid JSON"

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds is None

    def test_parse_missing_error_field(self):
        """Test parsing JSON without error field."""
        error_text = json.dumps({"message": "Some error"})

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds is None

    def test_parse_invalid_wait_time(self):
        """Test parsing with invalid wait time format."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait abc seconds before retrying.",
                }
            }
        )

        wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(error_text)
        assert wait_seconds is None


class TestRetryHandler:
    """Test retry handler functionality."""

    def test_init_default(self):
        """Test retry handler with default max retries."""
        handler = RetryHandler()
        assert handler.max_retries == 3

    def test_init_custom_max_retries(self):
        """Test retry handler with custom max retries."""
        handler = RetryHandler(max_retries=5)
        assert handler.max_retries == 5

    def test_should_retry_first_attempt(self):
        """Test should retry on first attempt."""
        handler = RetryHandler(max_retries=3)
        assert handler.should_retry(0) is True

    def test_should_retry_middle_attempt(self):
        """Test should retry on middle attempt."""
        handler = RetryHandler(max_retries=3)
        assert handler.should_retry(1) is True

    def test_should_retry_last_attempt(self):
        """Test should not retry on last attempt."""
        handler = RetryHandler(max_retries=3)
        assert handler.should_retry(2) is False

    def test_should_retry_beyond_max(self):
        """Test should not retry beyond max attempts."""
        handler = RetryHandler(max_retries=3)
        assert handler.should_retry(3) is False
        assert handler.should_retry(10) is False

    def test_should_retry_with_error(self):
        """Test should retry with error information."""
        handler = RetryHandler(max_retries=3)
        error = ValueError("Test error")
        assert handler.should_retry(0, error) is True

    def test_log_retry(self):
        """Test log retry method."""
        handler = RetryHandler(max_retries=3)
        # This should not raise an exception
        handler.log_retry(0, "Test reason")
        handler.log_retry(1)  # No reason


class TestEnhancedBaseLLMProvider:
    """Test enhanced base LLM provider."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        provider = MockProvider()
        assert provider.token is None
        assert provider.timeout == 30.0
        assert provider.base_url is None
        assert provider.client is None
        assert provider._models_cache is None
        assert isinstance(provider.rate_limiter, RateLimiter)

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        provider = MockProvider(
            token="test-token",  # noqa: S106
            timeout=60.0,
            base_url="https://example.com",
        )
        assert provider.token == "test-token"  # noqa: S105  # noqa: S105
        assert provider.timeout == 60.0
        assert provider.base_url == "https://example.com"

    def test_init_http_client(self):
        """Test HTTP client initialization."""
        provider = MockProvider(timeout=45.0)
        provider._init_http_client()

        assert provider.client is not None
        assert isinstance(provider.client, httpx.AsyncClient)
        # Verify timeout is set correctly (httpx uses Timeout objects)
        assert provider.timeout == 45.0

    def test_init_http_client_already_initialized(self):
        """Test HTTP client initialization when already initialized."""
        provider = MockProvider()
        mock_client = AsyncMock()
        provider.client = mock_client

        provider._init_http_client()
        # Should not change existing client
        assert provider.client is mock_client

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        provider = MockProvider()

        async with provider as p:
            assert p is provider
            assert provider.client is not None

        # Client should be closed
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_is_available_no_token(self):
        """Test availability check without token."""
        provider = MockProvider()
        assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_rate_limited(self):
        """Test availability check when rate limited."""
        provider = MockProvider(token="test-token")  # noqa: S106
        provider.rate_limiter.set_rate_limit(30, "Test")

        assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_cached_true(self):
        """Test availability check with cached positive result."""
        provider = MockProvider(token="test-token")  # noqa: S106
        provider.rate_limiter.update_availability_cache(True)

        assert await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_cached_false(self):
        """Test availability check with cached negative result."""
        provider = MockProvider(token="test-token")  # noqa: S106
        provider.rate_limiter.update_availability_cache(False)

        assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_no_cache(self):
        """Test availability check without cache."""
        provider = MockProvider(token="test-token")  # noqa: S106
        # Should return True for mock provider
        assert await provider.is_available()

    def test_get_auth_headers_no_token(self):
        """Test auth headers without token."""
        provider = MockProvider()
        headers = provider._get_auth_headers()
        assert headers == {}

    def test_get_auth_headers_with_token(self):
        """Test auth headers with token."""
        provider = MockProvider(token="test-token")  # noqa: S106
        headers = provider._get_auth_headers()
        expected = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
        }
        assert headers == expected

    def test_handle_rate_limit_no_wait_time(self):
        """Test rate limit handling without wait time."""
        provider = MockProvider()
        # Should not set rate limit
        provider._handle_rate_limit(429, "Rate limited")
        assert not provider.rate_limiter.is_rate_limited()

    def test_handle_rate_limit_with_wait_time(self):
        """Test rate limit handling with wait time."""
        provider = MockProvider()
        provider._handle_rate_limit(429, "Rate limited", wait_seconds=30)
        assert provider.rate_limiter.is_rate_limited()

    def test_handle_rate_limit_non_429(self):
        """Test rate limit handling with non-429 status."""
        provider = MockProvider()
        provider._handle_rate_limit(500, "Server error", wait_seconds=30)
        assert not provider.rate_limiter.is_rate_limited()

    @pytest.mark.asyncio
    async def test_make_request_no_client(self):
        """Test make request initializes client."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106

        with patch.object(provider, "_init_http_client") as mock_init:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_client.get.return_value = mock_response

            def init_side_effect():
                provider.client = mock_client

            mock_init.side_effect = init_side_effect

            response = await provider._make_request("GET", "/test")

            mock_init.assert_called_once()
            mock_client.get.assert_called_once()
            assert response is mock_response

    @pytest.mark.asyncio
    async def test_make_request_no_base_url(self):
        """Test make request without base URL."""
        provider = MockProvider(token="test")  # noqa: S106
        provider.client = AsyncMock()

        with pytest.raises(ValueError, match="Base URL not configured"):
            await provider._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_get(self):
        """Test GET request."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        response = await provider._make_request("GET", "/test")

        mock_client.get.assert_called_once_with(
            "https://example.com/test",
            headers={
                "Authorization": "Bearer test",
                "Content-Type": "application/json",
            },
        )
        assert response is mock_response

    @pytest.mark.asyncio
    async def test_make_request_post(self):
        """Test POST request with JSON data."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        json_data = {"key": "value"}
        response = await provider._make_request("POST", "/test", json_data=json_data)

        mock_client.post.assert_called_once_with(
            "https://example.com/test",
            headers={
                "Authorization": "Bearer test",
                "Content-Type": "application/json",
            },
            json=json_data,
        )
        assert response is mock_response

    @pytest.mark.asyncio
    async def test_make_request_custom_headers(self):
        """Test request with custom headers."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        custom_headers = {"X-Custom": "value"}
        response = await provider._make_request("GET", "/test", headers=custom_headers)

        expected_headers = {
            "Authorization": "Bearer test",
            "Content-Type": "application/json",
            "X-Custom": "value",
        }
        mock_client.get.assert_called_once_with(
            "https://example.com/test", headers=expected_headers
        )

    @pytest.mark.asyncio
    async def test_make_request_unsupported_method(self):
        """Test request with unsupported method."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106
        provider.client = AsyncMock()

        with pytest.raises(ValueError, match="Unsupported HTTP method: PUT"):
            await provider._make_request("PUT", "/test")

    @pytest.mark.asyncio
    async def test_make_request_http_error(self):
        """Test request with HTTP error."""
        provider = MockProvider(base_url="https://example.com", token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        provider.client = mock_client

        with pytest.raises(httpx.ConnectError):
            await provider._make_request("GET", "/test")

    @patch("scriptrag.llm.base_provider.get_settings")
    def test_init_model_discovery(self, mock_get_settings):
        """Test model discovery initialization."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.llm_model_cache_ttl = 3600
        mock_settings.llm_force_static_models = False
        mock_get_settings.return_value = mock_settings

        # Mock discovery class
        mock_discovery_class = Mock()
        mock_instance = Mock()
        mock_discovery_class.return_value = mock_instance

        provider = MockProvider()
        static_models = [{"id": "test", "name": "Test"}]

        result = provider._init_model_discovery(
            mock_discovery_class, static_models, extra_arg="value"
        )

        # Verify discovery class called correctly
        mock_discovery_class.assert_called_once_with(
            provider_name="openai_compatible",
            static_models=static_models,
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
            extra_arg="value",
        )
        assert result is mock_instance

    @patch("scriptrag.llm.base_provider.get_settings")
    def test_init_model_discovery_no_cache(self, mock_get_settings):
        """Test model discovery initialization without cache."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.llm_model_cache_ttl = 0
        mock_settings.llm_force_static_models = True
        mock_get_settings.return_value = mock_settings

        # Mock discovery class
        mock_discovery_class = Mock()
        mock_instance = Mock()
        mock_discovery_class.return_value = mock_instance

        provider = MockProvider()
        static_models = []

        result = provider._init_model_discovery(mock_discovery_class, static_models)

        # Verify cache disabled
        mock_discovery_class.assert_called_once_with(
            provider_name="openai_compatible",
            static_models=static_models,
            cache_ttl=None,
            use_cache=False,
            force_static=True,
        )


class TestClaudeCodeProvider:
    """Test Claude Code provider."""

    def test_init(self):
        """Test Claude Code provider initialization."""
        with patch("scriptrag.config.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                llm_model_cache_ttl=3600, llm_force_static_models=False
            )

            provider = ClaudeCodeProvider()

            assert provider.provider_type == LLMProvider.CLAUDE_CODE
            assert hasattr(provider, "sdk_available")
            assert hasattr(provider, "model_discovery")
            assert hasattr(provider, "schema_handler")
            assert hasattr(provider, "retry_handler")

    def test_init_with_mock_settings(self):
        """Test initialization with mock settings (testing scenario)."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            # Create mock with Mock class name
            mock_cache_ttl = Mock()
            mock_cache_ttl.__class__.__name__ = "Mock"

            mock_settings = Mock()
            mock_settings.llm_model_cache_ttl = mock_cache_ttl
            mock_settings.llm_force_static_models = False
            mock_get_settings.return_value = mock_settings

            provider = ClaudeCodeProvider()

            # Should use fallback values when mocked
            assert provider.model_discovery.cache.ttl == 3600

    def test_init_import_error(self):
        """Test initialization when settings import fails."""
        with patch("scriptrag.config.get_settings", side_effect=ImportError):
            # Mock SDK to focus on settings import error
            with patch.dict("sys.modules", {"claude_code_sdk": Mock()}):
                with patch("shutil.which", return_value="/usr/bin/claude"):
                    provider = ClaudeCodeProvider()

                    # Should use fallback values
                    assert provider.model_discovery.cache.ttl == 3600
                    assert (
                        provider.model_discovery.cache is not None
                    )  # use_cache=True means cache exists

    def test_check_sdk_available(self):
        """Test SDK availability check when available."""
        with patch("scriptrag.config.get_settings"):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                # Mock the import by patching at the module level where it's used
                with patch.dict("sys.modules", {"claude_code_sdk": Mock()}):
                    provider = ClaudeCodeProvider()
                    assert provider.sdk_available is True

    def test_check_sdk_no_executable(self):
        """Test SDK check when executable not in PATH."""
        with patch("scriptrag.config.get_settings"):
            with patch("shutil.which", return_value=None):
                with patch.dict("sys.modules", {"claude_code_sdk": Mock()}):
                    provider = ClaudeCodeProvider()
                    assert provider.sdk_available is False

    def test_check_sdk_import_error(self):
        """Test SDK check when SDK not installed."""
        with patch("scriptrag.config.get_settings"):
            # Create a mapping that excludes claude_code_sdk to trigger ImportError
            with patch.dict(
                "sys.modules", {"claude_code_sdk": None}
            ):  # None triggers ImportError
                with patch("shutil.which", return_value="/usr/bin/claude"):
                    provider = ClaudeCodeProvider()
                    assert provider.sdk_available is False

    @pytest.mark.asyncio
    async def test_is_available_disabled_by_env(self):
        """Test availability when disabled by environment variable."""
        with patch("scriptrag.config.get_settings"):
            with patch.dict(os.environ, {"SCRIPTRAG_IGNORE_CLAUDE": "1"}):
                provider = ClaudeCodeProvider()
                assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_sdk_not_available(self):
        """Test availability when SDK not available."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = False
            assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_sdk_check_success(self):
        """Test availability when SDK check succeeds."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                mock_sdk.ClaudeCodeOptions = Mock()

                provider = ClaudeCodeProvider()
                provider.sdk_available = True

                assert await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_sdk_import_error(self):
        """Test availability when SDK import fails."""
        with patch("scriptrag.config.get_settings"):
            with patch(
                "scriptrag.llm.providers.claude_code.claude_code_sdk",
                side_effect=ImportError,
            ):
                provider = ClaudeCodeProvider()
                provider.sdk_available = True

                assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_attribute_error(self):
        """Test availability when SDK has attribute error."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                del mock_sdk.ClaudeCodeOptions  # Remove attribute

                provider = ClaudeCodeProvider()
                provider.sdk_available = True

                assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_module_not_found(self):
        """Test availability when module not found."""
        with patch("scriptrag.config.get_settings"):
            with patch(
                "scriptrag.llm.providers.claude_code.claude_code_sdk",
                side_effect=ModuleNotFoundError("No module"),
            ):
                provider = ClaudeCodeProvider()
                provider.sdk_available = True

                assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_general_exception(self):
        """Test availability when unexpected error occurs."""
        with patch("scriptrag.config.get_settings"):
            with patch(
                "scriptrag.llm.providers.claude_code.claude_code_sdk",
                side_effect=RuntimeError("Unexpected"),
            ):
                provider = ClaudeCodeProvider()
                provider.sdk_available = True

                assert not await provider.is_available()

    @pytest.mark.asyncio
    async def test_is_available_environment_markers(self):
        """Test availability using environment markers."""
        with patch("scriptrag.config.get_settings"):
            with patch(
                "scriptrag.llm.providers.claude_code.claude_code_sdk",
                side_effect=ImportError,
            ):
                with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session"}):
                    provider = ClaudeCodeProvider()
                    provider.sdk_available = True

                    assert await provider.is_available()

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test model listing."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()
            mock_discovery = AsyncMock()
            mock_models = [{"id": "claude-3", "name": "Claude 3"}]
            mock_discovery.discover_models.return_value = mock_models
            provider.model_discovery = mock_discovery

            models = await provider.list_models()
            assert models == mock_models

    @pytest.mark.asyncio
    async def test_complete_sdk_not_available(self):
        """Test completion when SDK not available."""
        with patch("scriptrag.config.get_settings"):
            with patch(
                "scriptrag.llm.providers.claude_code.claude_code_sdk",
                side_effect=ImportError("SDK not found"),
            ):
                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3", messages=[{"role": "user", "content": "test"}]
                )

                with pytest.raises(
                    RuntimeError,
                    match="Claude Code environment detected but SDK not available",
                ):
                    await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Test successful completion."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                # Mock SDK components
                mock_options = Mock()
                mock_sdk.ClaudeCodeOptions.return_value = mock_options

                # Mock message and query
                mock_message = Mock()
                mock_message.__class__.__name__ = "AssistantMessage"
                mock_text_block = Mock()
                mock_text_block.text = "Test response"
                mock_message.content = [mock_text_block]

                async def mock_query(*args, **kwargs):
                    yield mock_message

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3",
                    messages=[{"role": "user", "content": "test"}],
                    system="System message",
                )

                response = await provider.complete(request)

                assert response.model == "claude-3"
                assert len(response.choices) == 1
                assert response.choices[0]["message"]["content"] == "Test response"

    @pytest.mark.asyncio
    async def test_complete_with_json_format(self):
        """Test completion with JSON response format."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                # Mock SDK components
                mock_options = Mock()
                mock_sdk.ClaudeCodeOptions.return_value = mock_options

                # Mock message with JSON response
                mock_message = Mock()
                mock_message.__class__.__name__ = "AssistantMessage"
                mock_text_block = Mock()
                mock_text_block.text = '{"result": "success"}'
                mock_message.content = [mock_text_block]

                async def mock_query(*args, **kwargs):
                    yield mock_message

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3",
                    messages=[{"role": "user", "content": "test"}],
                    response_format={"type": "json_object"},
                )

                response = await provider.complete(request)

                assert (
                    response.choices[0]["message"]["content"] == '{"result": "success"}'
                )

    @pytest.mark.asyncio
    async def test_complete_json_validation_retry(self):
        """Test completion with JSON validation retry."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                # Mock SDK components
                mock_options = Mock()
                mock_sdk.ClaudeCodeOptions.return_value = mock_options

                # Mock messages - first invalid, then valid JSON
                mock_message1 = Mock()
                mock_message1.__class__.__name__ = "AssistantMessage"
                mock_text_block1 = Mock()
                mock_text_block1.text = "invalid json"
                mock_message1.content = [mock_text_block1]

                mock_message2 = Mock()
                mock_message2.__class__.__name__ = "AssistantMessage"
                mock_text_block2 = Mock()
                mock_text_block2.text = '{"result": "success"}'
                mock_message2.content = [mock_text_block2]

                call_count = 0

                async def mock_query(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        yield mock_message1
                    else:
                        yield mock_message2

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3",
                    messages=[{"role": "user", "content": "test"}],
                    response_format={"type": "json_object"},
                )

                response = await provider.complete(request)

                # Should succeed after retry
                assert (
                    response.choices[0]["message"]["content"] == '{"result": "success"}'
                )
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_complete_timeout_error(self):
        """Test completion with timeout error."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                mock_sdk.ClaudeCodeOptions.return_value = Mock()

                async def mock_query(*args, **kwargs):
                    raise TimeoutError("Request timed out")

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3", messages=[{"role": "user", "content": "test"}]
                )

                with pytest.raises(TimeoutError):
                    await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_attribute_error(self):
        """Test completion with attribute error."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                mock_sdk.ClaudeCodeOptions.return_value = Mock()

                # Mock message without expected attributes
                mock_message = Mock()
                mock_message.__class__.__name__ = "AssistantMessage"
                # Missing content attribute

                async def mock_query(*args, **kwargs):
                    yield mock_message

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()
                request = CompletionRequest(
                    model="claude-3", messages=[{"role": "user", "content": "test"}]
                )

                with pytest.raises(
                    RuntimeError, match="Invalid SDK response structure"
                ):
                    await provider.complete(request)

    @pytest.mark.asyncio
    async def test_execute_query_timeout_retry(self):
        """Test query execution with timeout and retry."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                mock_options = Mock()

                call_count = 0

                async def mock_query(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise TimeoutError("Timeout on first call")
                    # Second call succeeds
                    mock_message = Mock()
                    mock_message.__class__.__name__ = "AssistantMessage"
                    mock_text_block = Mock()
                    mock_text_block.text = "Success after retry"
                    mock_message.content = [mock_text_block]
                    yield mock_message

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()

                # Mock retry handler to allow retry
                provider.retry_handler.should_retry = Mock(return_value=True)

                result = await provider._execute_query(
                    "test prompt", mock_options, 0, 3
                )

                assert "Success after retry" in result

    @pytest.mark.asyncio
    async def test_execute_query_result_message_fallback(self):
        """Test query execution with ResultMessage fallback."""
        with patch("scriptrag.config.get_settings"):
            with patch("claude_code_sdk") as mock_sdk:
                mock_options = Mock()

                # Mock ResultMessage (no AssistantMessage)
                mock_message = Mock()
                mock_message.__class__.__name__ = "ResultMessage"
                mock_message.result = "Result from ResultMessage"

                async def mock_query(*args, **kwargs):
                    yield mock_message

                mock_sdk.query = mock_query

                provider = ClaudeCodeProvider()

                result = await provider._execute_query(
                    "test prompt", mock_options, 0, 1
                )

                assert result == "Result from ResultMessage"

    @pytest.mark.asyncio
    async def test_validate_json_response_with_markdown(self):
        """Test JSON validation with markdown code blocks."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            response_text = '```json\n{"key": "value"}\n```'
            response_format = {"type": "json_object"}

            result = await provider._validate_json_response(
                response_text, response_format, 0
            )

            assert result["valid"] is True
            assert result["json_text"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_validate_json_response_with_generic_markdown(self):
        """Test JSON validation with generic markdown code blocks."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            response_text = '```\n{"key": "value"}\n```'
            response_format = {"type": "json_object"}

            result = await provider._validate_json_response(
                response_text, response_format, 0
            )

            assert result["valid"] is True
            assert result["json_text"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_validate_json_response_schema_validation(self):
        """Test JSON validation with schema requirements."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            # Mock schema handler
            provider.schema_handler.extract_schema_info = Mock(
                return_value={
                    "schema": {
                        "properties": {"required_field": {"type": "string"}},
                        "required": ["required_field"],
                    }
                }
            )

            response_text = '{"wrong_field": "value"}'
            response_format = {"type": "json_object", "schema": {}}

            result = await provider._validate_json_response(
                response_text, response_format, 0
            )

            assert result["valid"] is False
            assert "Missing required field" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_json_response_invalid_json(self):
        """Test JSON validation with invalid JSON."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            response_text = "This is not JSON"
            response_format = {"type": "json_object"}

            result = await provider._validate_json_response(
                response_text, response_format, 0
            )

            assert result["valid"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_embed_not_implemented(self):
        """Test embedding method raises NotImplementedError."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()
            request = EmbeddingRequest(model="test", input=["test"])

            with pytest.raises(
                NotImplementedError, match="Claude Code SDK doesn't support embeddings"
            ):
                await provider.embed(request)

    def test_messages_to_prompt(self):
        """Test message to prompt conversion."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "How are you?"},
            ]

            prompt = provider._messages_to_prompt(messages)

            expected = (
                "System: You are helpful\n\nUser: Hello\n\nAssistant: Hi there"
                "\n\nUser: How are you?"
            )
            assert prompt == expected

    def test_messages_to_prompt_missing_fields(self):
        """Test message to prompt conversion with missing fields."""
        with patch("scriptrag.config.get_settings"):
            provider = ClaudeCodeProvider()

            messages = [
                {"role": "user"},  # Missing content
                {"content": "No role"},  # Missing role
                {},  # Empty message
            ]

            prompt = provider._messages_to_prompt(messages)

            expected = "User: \n\nUser: No role\n\nUser: "
            assert prompt == expected


class TestGitHubModelsProvider:
    """Test GitHub Models provider."""

    def test_init_with_token(self):
        """Test initialization with explicit token."""
        provider = GitHubModelsProvider(token="test-token", timeout=60.0)  # noqa: S106

        assert provider.token == "test-token"  # noqa: S105
        assert provider.timeout == 60.0
        assert provider.base_url == "https://models.inference.ai.azure.com"
        assert provider.provider_type == LLMProvider.GITHUB_MODELS

    def test_init_from_env(self):
        """Test initialization with token from environment."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            provider = GitHubModelsProvider()
            assert provider.token == "env-token"  # noqa: S105

    def test_init_no_token(self):
        """Test initialization without token."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubModelsProvider()
            assert provider.token is None

    @pytest.mark.asyncio
    async def test_validate_availability_no_client(self):
        """Test availability validation without HTTP client."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        provider.client = None

        with patch.object(provider, "_init_http_client") as mock_init:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            def init_side_effect():
                provider.client = mock_client

            mock_init.side_effect = init_side_effect

            result = await provider._validate_availability()

            mock_init.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_availability_success(self):
        """Test successful availability validation."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = await provider._validate_availability()

        mock_client.get.assert_called_once_with(
            "https://models.inference.ai.azure.com/models",
            headers={
                "Authorization": "Bearer test",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_availability_http_error(self):
        """Test availability validation with HTTP error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        provider.client = mock_client

        result = await provider._validate_availability()

        assert result is False
        # Should update cache
        assert provider.rate_limiter._availability_cache is False

    @pytest.mark.asyncio
    async def test_validate_availability_timeout(self):
        """Test availability validation with timeout."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        provider.client = mock_client

        result = await provider._validate_availability()

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_availability_http_status_error(self):
        """Test availability validation with HTTP status error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=Mock()
        )
        provider.client = mock_client

        result = await provider._validate_availability()

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_availability_general_exception(self):
        """Test availability validation with general exception."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.get.side_effect = ValueError("Unexpected error")
        provider.client = mock_client

        result = await provider._validate_availability()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available(self):
        """Test general availability check."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106

        with patch.object(
            provider, "_validate_availability", return_value=True
        ) as mock_validate:
            result = await provider.is_available()

            mock_validate.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test model listing."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_discovery = AsyncMock()
        mock_models = [{"id": "gpt-4", "name": "GPT-4"}]
        mock_discovery.discover_models.return_value = mock_models
        provider.model_discovery = mock_discovery

        models = await provider.list_models()
        assert models == mock_models

    @pytest.mark.asyncio
    async def test_complete_no_token(self):
        """Test completion without token."""
        provider = GitHubModelsProvider()
        request = CompletionRequest(model="gpt-4", messages=[])

        with pytest.raises(ValueError, match="GitHub token not configured"):
            await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Test successful completion."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = CompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=100,
            system="You are helpful",
        )

        response = await provider.complete(request)

        # Verify request payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["model"] == "gpt-4"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 100
        assert len(payload["messages"]) == 2  # system + user message
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

        # Verify response
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4"
        assert len(response.choices) == 1
        assert response.choices[0]["message"]["content"] == "Hello!"
        assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_complete_with_response_format(self):
        """Test completion with response format."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        }
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = CompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
            response_format={"type": "json_object", "schema": {"type": "object"}},
        )

        await provider.complete(request)

        # Verify response_format was included
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert "response_format" in payload
        assert payload["response_format"]["type"] == "json_object"

    @pytest.mark.asyncio
    async def test_complete_http_error(self):
        """Test completion with HTTP error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        provider.client = mock_client

        request = CompletionRequest(model="gpt-4", messages=[])

        with pytest.raises(httpx.ConnectError):
            await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_api_error(self):
        """Test completion with API error response."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = CompletionRequest(model="gpt-4", messages=[])

        with pytest.raises(ValueError, match="GitHub Models API error"):
            await provider.complete(request)

    @pytest.mark.asyncio
    async def test_complete_rate_limit_error(self):
        """Test completion with rate limit error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 60 seconds before retrying.",
                }
            }
        )
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = CompletionRequest(model="gpt-4", messages=[])

        with pytest.raises(ValueError):
            await provider.complete(request)

        # Verify rate limit was set
        assert provider.rate_limiter.is_rate_limited()

    @pytest.mark.asyncio
    async def test_complete_json_decode_error(self):
        """Test completion with JSON decode error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = CompletionRequest(model="gpt-4", messages=[])

        with pytest.raises(ValueError, match="Invalid API response"):
            await provider.complete(request)

    def test_parse_completion_response_success(self):
        """Test successful response parsing."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106

        data = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        response = provider._parse_completion_response(data, "gpt-4")

        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4"
        assert len(response.choices) == 1
        assert response.usage["total_tokens"] == 15

    def test_parse_completion_response_validation_error(self):
        """Test response parsing with validation error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106

        # Malformed data that will cause validation error
        data = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant"},  # Missing content
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10},
        }

        response = provider._parse_completion_response(data, "gpt-4")

        # Should create sanitized response
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4"
        assert len(response.choices) == 1
        assert response.choices[0]["message"]["content"] == ""

    def test_parse_completion_response_no_choices(self):
        """Test response parsing with no valid choices."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106

        data = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": ["invalid_choice"],  # Not dict
            "usage": {},
        }

        response = provider._parse_completion_response(data, "gpt-4")

        # Should create default choice
        assert len(response.choices) == 1
        assert response.choices[0]["message"]["content"] == ""
        assert response.choices[0]["message"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_embed_no_token(self):
        """Test embedding without token."""
        provider = GitHubModelsProvider()
        request = EmbeddingRequest(model="text-embedding", input=["test"])

        with pytest.raises(ValueError, match="GitHub token not configured"):
            await provider.embed(request)

    @pytest.mark.asyncio
    async def test_embed_success(self):
        """Test successful embedding."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-ada-002",
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = EmbeddingRequest(
            model="text-embedding-ada-002", input=["test text"], dimensions=1536
        )

        response = await provider.embed(request)

        # Verify request payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["model"] == "text-embedding-ada-002"
        assert payload["input"] == ["test text"]
        assert payload["dimensions"] == 1536

        # Verify response
        assert response["model"] == "text-embedding-ada-002"
        assert len(response["data"]) == 1

    @pytest.mark.asyncio
    async def test_embed_api_error(self):
        """Test embedding with API error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = EmbeddingRequest(model="test", input=["test"])

        with pytest.raises(ValueError, match="GitHub Models API error"):
            await provider.embed(request)

    @pytest.mark.asyncio
    async def test_embed_http_error(self):
        """Test embedding with HTTP error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        provider.client = mock_client

        request = EmbeddingRequest(model="test", input=["test"])

        with pytest.raises(httpx.ConnectError):
            await provider.embed(request)

    @pytest.mark.asyncio
    async def test_embed_json_error(self):
        """Test embedding with JSON decode error."""
        provider = GitHubModelsProvider(token="test")  # noqa: S106
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_client.post.return_value = mock_response
        provider.client = mock_client

        request = EmbeddingRequest(model="test", input=["test"])

        with pytest.raises(ValueError, match="Invalid embedding response"):
            await provider.embed(request)
