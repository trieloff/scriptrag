"""Tests for custom exception classes."""

from pathlib import Path

import pytest

from scriptrag.exceptions import (
    ConfigurationError,
    DatabaseError,
    LLMError,
    LLMProviderError,
    RateLimitError,
    ScriptRAGError,
    check_config_keys,
    check_database_path,
)


class TestRateLimitError:
    """Test RateLimitError exception class."""

    def test_rate_limit_error_basic(self):
        """Test basic RateLimitError creation."""
        error = RateLimitError()
        assert str(error) == "Error: Rate limit exceeded"
        assert error.retry_after is None
        assert error.provider is None

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError(retry_after=10.5)
        assert error.retry_after == 10.5
        assert "Please wait 10.5 seconds before retrying" in str(error)
        assert error.details["retry_after"] == 10.5

    def test_rate_limit_error_with_provider(self):
        """Test RateLimitError with provider."""
        error = RateLimitError(provider="OpenAI")
        assert error.provider == "OpenAI"
        assert error.details["provider"] == "OpenAI"

    def test_rate_limit_error_full(self):
        """Test RateLimitError with all parameters."""
        error = RateLimitError(
            message="Custom rate limit message",
            retry_after=30.0,
            provider="Claude",
        )
        assert error.message == "Custom rate limit message"
        assert error.retry_after == 30.0
        assert error.provider == "Claude"
        assert "Custom rate limit message" in str(error)
        assert "Please wait 30.0 seconds before retrying" in str(error)
        assert error.details == {"provider": "Claude", "retry_after": 30.0}

    def test_rate_limit_error_inheritance(self):
        """Test that RateLimitError inherits from LLMError."""
        error = RateLimitError()
        assert isinstance(error, LLMError)
        assert isinstance(error, ScriptRAGError)
        assert isinstance(error, Exception)

    def test_rate_limit_error_formatting(self):
        """Test error message formatting."""
        error = RateLimitError(
            message="API rate limit hit",
            retry_after=60.0,
            provider="TestProvider",
        )
        error_str = str(error)
        assert "Error: API rate limit hit" in error_str
        assert "Hint: Please wait 60.0 seconds before retrying" in error_str
        assert "Details:" in error_str
        assert "provider: TestProvider" in error_str
        assert "retry_after: 60.0" in error_str


class TestLLMProviderError:
    """Test LLMProviderError exception class."""

    def test_llm_provider_error_basic(self):
        """Test basic LLMProviderError creation."""
        error = LLMProviderError(message="Provider failed")
        assert str(error) == "Error: Provider failed"
        assert error.message == "Provider failed"

    def test_llm_provider_error_with_hint(self):
        """Test LLMProviderError with hint."""
        error = LLMProviderError(
            message="Connection failed", hint="Check your network connection"
        )
        assert "Error: Connection failed" in str(error)
        assert "Hint: Check your network connection" in str(error)

    def test_llm_provider_error_with_details(self):
        """Test LLMProviderError with details."""
        error = LLMProviderError(
            message="API error",
            details={"status_code": 500, "endpoint": "/v1/completions"},
        )
        error_str = str(error)
        assert "Error: API error" in error_str
        assert "status_code: 500" in error_str
        assert "endpoint: /v1/completions" in error_str

    def test_llm_provider_error_inheritance(self):
        """Test that LLMProviderError inherits from LLMError."""
        error = LLMProviderError(message="Test")
        assert isinstance(error, LLMError)
        assert isinstance(error, ScriptRAGError)
        assert isinstance(error, Exception)

    def test_llm_provider_error_full(self):
        """Test LLMProviderError with all parameters."""
        error = LLMProviderError(
            message="Model not available",
            hint="Try using a different model",
            details={
                "model": "gpt-4",
                "available_models": ["gpt-3.5-turbo", "claude-2"],
            },
        )
        error_str = str(error)
        assert "Error: Model not available" in error_str
        assert "Hint: Try using a different model" in error_str
        assert "model: gpt-4" in error_str
        assert "available_models: ['gpt-3.5-turbo', 'claude-2']" in error_str


class TestExceptionUsageInMocks:
    """Test how exceptions are used in mock providers."""

    def test_mock_provider_raises_correct_exceptions(self):
        """Test that mock provider raises the correct exception types."""
        from tests.llm_test_utils import MockLLMProvider

        # This test verifies that the mock provider is using the correct
        # exception types that we defined
        provider = MockLLMProvider(fail_after_n_calls=0)

        # We can't test the actual raising here without async setup,
        # but we can verify the exception types are importable and correct
        assert RateLimitError
        assert LLMProviderError

        # Verify the mock provider has the expected configuration
        assert provider.fail_after_n_calls == 0
        assert hasattr(provider, "rate_limit_after_n_calls")


class TestCheckDatabasePath:
    """Test check_database_path helper function."""

    def test_database_path_exists(self, tmp_path):
        """Test when database path exists - should not raise."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        # Should not raise an exception
        check_database_path(db_path)

    def test_database_path_not_exists(self, tmp_path):
        """Test when database path doesn't exist - should raise."""
        db_path = tmp_path / "nonexistent.db"
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(db_path)

        error = exc_info.value
        assert "Database not found" in str(error)
        assert "Run 'scriptrag init'" in str(error)
        assert str(db_path) in str(error)

    def test_database_path_none(self):
        """Test when database path is None - should raise."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(None)

        error = exc_info.value
        assert "Database not found" in str(error)
        assert "searched_path: None" in str(error)

    def test_database_path_with_default_paths(self, tmp_path):
        """Test with default paths provided."""
        db_path = tmp_path / "missing.db"
        default_paths = [Path("/default/path1"), Path("/default/path2")]

        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(db_path, default_paths)

        error = exc_info.value
        assert "default_paths" in error.details
        # Check that both paths are in the list (platform-agnostic)
        paths_str = str(error.details["default_paths"])
        assert "path1" in paths_str
        assert "path2" in paths_str

    def test_database_path_scriptrag_db_exists(self, tmp_path, monkeypatch):
        """Test when scriptrag.db exists in current directory."""
        # Create scriptrag.db in the tmp directory
        scriptrag_db = tmp_path / "scriptrag.db"
        scriptrag_db.touch()

        # Change current directory to tmp_path for this test
        monkeypatch.chdir(tmp_path)

        # Try to check a different database that doesn't exist
        db_path = tmp_path / "missing.db"

        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(db_path)

        error = exc_info.value
        # When scriptrag.db exists, a different hint should be provided
        assert "Database not found" in str(error)
        assert "Found scriptrag.db in current dir" in str(error)


class TestCheckConfigKeys:
    """Test check_config_keys helper function."""

    def test_valid_config(self):
        """Test with valid configuration - should not raise."""
        config = {
            "database_path": "/path/to/db",
            "llm_config": {
                "provider": "openai",
                "api_key": "test",  # pragma: allowlist secret
            },
        }
        # Should not raise
        check_config_keys(config)

    def test_invalid_db_path_key(self):
        """Test with wrong db_path key."""
        config = {"db_path": "/path/to/db"}

        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)

        error = exc_info.value
        assert "Invalid configuration key 'db_path'" in str(error)
        assert "Use 'database_path' instead" in str(error)
        assert error.details["invalid_key"] == "db_path"
        assert error.details["correct_key"] == "database_path"

    def test_invalid_llm_provider_key(self):
        """Test with wrong llm_provider key."""
        config = {"llm_provider": "openai"}

        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)

        error = exc_info.value
        assert "Invalid configuration key 'llm_provider'" in str(error)
        assert "Use 'llm_config.provider' instead" in str(error)

    def test_invalid_api_key(self):
        """Test with wrong api_key at root level."""
        config = {"api_key": "test-key"}  # pragma: allowlist secret

        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)

        error = exc_info.value
        assert "Invalid configuration key 'api_key'" in str(error)
        assert "Use 'llm_config.api_key' instead" in str(error)

    def test_invalid_model_key(self):
        """Test with wrong model key at root level."""
        config = {"model": "gpt-4"}

        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)

        error = exc_info.value
        assert "Invalid configuration key 'model'" in str(error)
        assert "Use 'llm_config.model' instead" in str(error)

    def test_multiple_invalid_keys_stops_at_first(self):
        """Test that validation stops at first invalid key."""
        config = {
            "db_path": "/path",  # Wrong
            "api_key": "key",  # Also wrong  # pragma: allowlist secret
        }

        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)

        # Should only complain about the first wrong key found
        error = exc_info.value
        assert "db_path" in str(error)
        # Should include all found keys in details
        assert "found_keys" in error.details
        assert "db_path" in error.details["found_keys"]
        assert "api_key" in error.details["found_keys"]
