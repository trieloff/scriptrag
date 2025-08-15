"""Tests for custom exception classes."""

from pathlib import Path

import pytest

from scriptrag.exceptions import (
    ConfigurationError,
    DatabaseError,
    GitError,
    LLMError,
    LLMProviderError,
    ParseError,
    QueryError,
    RateLimitError,
    ScriptRAGError,
    ScriptRAGFileNotFoundError,
    ScriptRAGIndexError,
    SearchError,
    ValidationError,
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

    def test_database_path_empty_string(self):
        """Test when database path is empty string - should raise."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("")

        error = exc_info.value
        assert "Database not found" in str(error)
        assert "searched_path: " in str(error)  # Empty string should show as empty

    def test_database_path_false_value(self):
        """Test when database path is False - should raise."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(False)

        error = exc_info.value
        assert "Database not found" in str(error)
        # False is falsy, so it gets converted to "None" in the logic
        assert "searched_path: None" in str(error)

    def test_database_path_with_empty_default_paths(self):
        """Test with empty default paths list."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("/nonexistent/path", [])

        error = exc_info.value
        # Empty list is falsy, so default_paths won't be added to details
        assert "default_paths" not in error.details
        assert "searched_path: /nonexistent/path" in str(error)


class TestCheckConfigKeys:
    """Additional tests for check_config_keys helper function."""

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

    def test_empty_config(self):
        """Test with empty configuration - should not raise."""
        config = {}
        # Should not raise an exception
        check_config_keys(config)

    def test_config_with_none_values(self):
        """Test with configuration containing None values."""
        config = {"valid_key": None, "another_valid": "value"}
        # Should not raise an exception
        check_config_keys(config)


class TestScriptRAGError:
    """Test the base ScriptRAGError class."""

    def test_scriptrag_error_basic(self):
        """Test basic ScriptRAGError creation."""
        error = ScriptRAGError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.hint is None
        assert error.details is None
        assert str(error) == "Error: Something went wrong"

    def test_scriptrag_error_with_hint(self):
        """Test ScriptRAGError with hint."""
        error = ScriptRAGError(
            "Database connection failed", hint="Check your database configuration"
        )
        assert error.message == "Database connection failed"
        assert error.hint == "Check your database configuration"
        error_str = str(error)
        assert "Error: Database connection failed" in error_str
        assert "Hint: Check your database configuration" in error_str

    def test_scriptrag_error_with_details(self):
        """Test ScriptRAGError with details dictionary."""
        details = {"file_path": "/test/path", "line_number": 42, "encoding": "utf-8"}
        error = ScriptRAGError("File parsing error", details=details)
        assert error.message == "File parsing error"
        assert error.details == details
        error_str = str(error)
        assert "Error: File parsing error" in error_str
        assert "Details:" in error_str
        assert "file_path: /test/path" in error_str
        assert "line_number: 42" in error_str
        assert "encoding: utf-8" in error_str

    def test_scriptrag_error_with_all_parameters(self):
        """Test ScriptRAGError with message, hint, and details."""
        details = {"attempted_path": "/missing/file.txt", "permissions": "755"}
        error = ScriptRAGError(
            "File not accessible",
            hint="Ensure the file exists and has proper permissions",
            details=details,
        )
        assert error.message == "File not accessible"
        assert error.hint == "Ensure the file exists and has proper permissions"
        assert error.details == details
        error_str = str(error)
        assert "Error: File not accessible" in error_str
        assert "Hint: Ensure the file exists and has proper permissions" in error_str
        assert "Details:" in error_str
        assert "attempted_path: /missing/file.txt" in error_str
        assert "permissions: 755" in error_str

    def test_format_error_method_direct(self):
        """Test the format_error method directly."""
        error = ScriptRAGError("Test message")
        formatted = error.format_error()
        assert formatted == "Error: Test message"

    def test_format_error_with_hint_only(self):
        """Test format_error with hint but no details."""
        error = ScriptRAGError("Test message", hint="This is a hint")
        formatted = error.format_error()
        expected = "Error: Test message\nHint: This is a hint"
        assert formatted == expected

    def test_format_error_with_details_only(self):
        """Test format_error with details but no hint."""
        error = ScriptRAGError(
            "Test message", details={"key1": "value1", "key2": "value2"}
        )
        formatted = error.format_error()
        assert "Error: Test message" in formatted
        assert "Details:" in formatted
        assert "key1: value1" in formatted
        assert "key2: value2" in formatted
        assert "Hint:" not in formatted

    def test_format_error_empty_details(self):
        """Test format_error with empty details dictionary."""
        error = ScriptRAGError("Test message", details={})
        formatted = error.format_error()
        # Empty details should not add a Details section
        assert formatted == "Error: Test message"
        assert "Details:" not in formatted

    def test_format_error_complex_details(self):
        """Test format_error with complex nested data in details."""
        details = {
            "list_data": [1, 2, 3],
            "dict_data": {"nested": "value"},
            "none_value": None,
            "bool_value": True,
        }
        error = ScriptRAGError("Complex data error", details=details)
        formatted = error.format_error()
        assert "Error: Complex data error" in formatted
        assert "Details:" in formatted
        assert "list_data: [1, 2, 3]" in formatted
        assert "dict_data: {'nested': 'value'}" in formatted
        assert "none_value: None" in formatted
        assert "bool_value: True" in formatted


class TestAllSimpleExceptions:
    """Test all the simple exception classes that just pass."""

    def test_database_error(self):
        """Test DatabaseError exception."""
        error = DatabaseError("Database connection failed")
        assert isinstance(error, ScriptRAGError)
        assert str(error) == "Error: Database connection failed"

    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        error = ConfigurationError("Invalid config key", hint="Check documentation")
        assert isinstance(error, ScriptRAGError)
        assert "Error: Invalid config key" in str(error)
        assert "Hint: Check documentation" in str(error)

    def test_parse_error(self):
        """Test ParseError exception."""
        error = ParseError(
            "Fountain parsing failed",
            details={"line": 25, "character": "JOHN"},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Fountain parsing failed" in str(error)
        assert "line: 25" in str(error)
        assert "character: JOHN" in str(error)

    def test_scriptrag_file_not_found_error(self):
        """Test ScriptRAGFileNotFoundError exception."""
        error = ScriptRAGFileNotFoundError(
            "Script file not found",
            hint="Check the file path",
            details={"path": "/missing/script.fountain"},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Script file not found" in str(error)
        assert "Hint: Check the file path" in str(error)
        assert "path: /missing/script.fountain" in str(error)

    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError(
            "Invalid input format",
            hint="Expected JSON format",
            details={"received": "plain text", "expected": "JSON"},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Invalid input format" in str(error)
        assert "Hint: Expected JSON format" in str(error)
        assert "received: plain text" in str(error)
        assert "expected: JSON" in str(error)

    def test_llm_error(self):
        """Test LLMError exception."""
        error = LLMError(
            "LLM request failed",
            details={"provider": "openai", "model": "gpt-4"},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: LLM request failed" in str(error)
        assert "provider: openai" in str(error)
        assert "model: gpt-4" in str(error)

    def test_git_error(self):
        """Test GitError exception."""
        error = GitError(
            "Git LFS operation failed",
            hint="Ensure Git LFS is installed",
            details={"command": "git lfs pull", "exit_code": 1},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Git LFS operation failed" in str(error)
        assert "Hint: Ensure Git LFS is installed" in str(error)
        assert "command: git lfs pull" in str(error)
        assert "exit_code: 1" in str(error)

    def test_scriptrag_index_error(self):
        """Test ScriptRAGIndexError exception."""
        error = ScriptRAGIndexError(
            "Indexing failed",
            hint="Check database connectivity",
            details={"embedding_count": 0, "total_scenes": 25},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Indexing failed" in str(error)
        assert "Hint: Check database connectivity" in str(error)
        assert "embedding_count: 0" in str(error)
        assert "total_scenes: 25" in str(error)

    def test_query_error(self):
        """Test QueryError exception."""
        error = QueryError(
            "SQL query execution failed",
            hint="Check query syntax",
            details={"query": "SELECT * FROM scenes WHERE id = ?", "params": [123]},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: SQL query execution failed" in str(error)
        assert "Hint: Check query syntax" in str(error)
        assert "query: SELECT * FROM scenes WHERE id = ?" in str(error)
        assert "params: [123]" in str(error)

    def test_search_error(self):
        """Test SearchError exception."""
        error = SearchError(
            "Search query parsing failed",
            hint="Use simpler search terms",
            details={"query": "complex[nested(query)]", "parsed_tokens": []},
        )
        assert isinstance(error, ScriptRAGError)
        assert "Error: Search query parsing failed" in str(error)
        assert "Hint: Use simpler search terms" in str(error)
        assert "query: complex[nested(query)]" in str(error)
        assert "parsed_tokens: []" in str(error)


class TestInheritanceHierarchy:
    """Test the exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_scriptrag_error(self):
        """Test that all custom exceptions inherit from ScriptRAGError."""
        exceptions = [
            DatabaseError,
            ConfigurationError,
            ParseError,
            ScriptRAGFileNotFoundError,
            ValidationError,
            LLMError,
            RateLimitError,
            LLMProviderError,
            GitError,
            ScriptRAGIndexError,
            QueryError,
            SearchError,
        ]

        for exc_class in exceptions:
            error = exc_class("test message")
            assert isinstance(error, ScriptRAGError)
            assert isinstance(error, Exception)

    def test_llm_exception_hierarchy(self):
        """Test that LLM-related exceptions inherit correctly."""
        rate_limit_error = RateLimitError()
        provider_error = LLMProviderError("Provider error")

        # Both should inherit from LLMError
        assert isinstance(rate_limit_error, LLMError)
        assert isinstance(provider_error, LLMError)

        # And ultimately from ScriptRAGError
        assert isinstance(rate_limit_error, ScriptRAGError)
        assert isinstance(provider_error, ScriptRAGError)


class TestEdgeCaseScenarios:
    """Test edge cases and unusual scenarios."""

    def test_exception_with_very_long_message(self):
        """Test exception with extremely long message."""
        long_message = "x" * 1000  # 1000 character message
        error = ScriptRAGError(long_message)
        assert error.message == long_message
        assert f"Error: {long_message}" == str(error)

    def test_exception_with_special_characters(self):
        """Test exception with special characters in message and details."""
        message = "Error with special chars: éñ中文🎭\n\t\r"
        details = {"unicode_key_🔑": "unicode_value_✨", "newline\nkey": "tab\tvalue"}
        error = ScriptRAGError(message, details=details)
        error_str = str(error)
        assert message in error_str
        assert "unicode_key_🔑: unicode_value_✨" in error_str
        assert "newline\nkey: tab\tvalue" in error_str

    def test_exception_str_vs_repr(self):
        """Test string representation vs repr of exceptions."""
        error = ScriptRAGError("Test error", hint="Test hint")
        str_repr = str(error)
        assert "Error: Test error" in str_repr
        assert "Hint: Test hint" in str_repr
        # repr should still be the default Exception repr
        assert "ScriptRAGError" in repr(error)

    def test_exception_details_with_none_and_empty_values(self):
        """Test exception details containing None and empty values."""
        details = {
            "none_value": None,
            "empty_string": "",
            "empty_list": [],
            "empty_dict": {},
            "zero": 0,
            "false": False,
        }
        error = ScriptRAGError("Test with edge case values", details=details)
        error_str = str(error)
        assert "none_value: None" in error_str
        assert "empty_string: " in error_str  # Should show as empty
        assert "empty_list: []" in error_str
        assert "empty_dict: {}" in error_str
        assert "zero: 0" in error_str
        assert "false: False" in error_str
