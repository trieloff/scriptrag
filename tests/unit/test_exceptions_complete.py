"""Complete test coverage for all exception classes and methods."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from scriptrag.exceptions import (
    ConfigurationError,
    DatabaseError,
    GitError,
    LLMError,
    LLMFallbackError,
    LLMProviderError,
    LLMRetryableError,
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


class TestScriptRAGErrorComprehensive:
    """Comprehensive tests for the base ScriptRAGError class."""

    def test_init_message_only(self):
        """Test ScriptRAGError with message only."""
        error = ScriptRAGError("Test message")
        assert error.message == "Test message"
        assert error.hint is None
        assert error.details is None

    def test_init_with_all_params(self):
        """Test ScriptRAGError with all parameters."""
        details = {"key1": "value1", "key2": 42}
        error = ScriptRAGError(
            message="Test error",
            hint="Test hint",
            details=details,
        )
        assert error.message == "Test error"
        assert error.hint == "Test hint"
        assert error.details == details

    def test_format_error_message_only(self):
        """Test format_error with message only."""
        error = ScriptRAGError("Simple error")
        formatted = error.format_error()
        assert formatted == "Error: Simple error"

    def test_format_error_with_hint(self):
        """Test format_error with hint."""
        error = ScriptRAGError("Error message", hint="Helpful hint")
        formatted = error.format_error()
        expected = "Error: Error message\nHint: Helpful hint"
        assert formatted == expected

    def test_format_error_with_details(self):
        """Test format_error with details."""
        details = {"file": "test.py", "line": 10}
        error = ScriptRAGError("Parse error", details=details)
        formatted = error.format_error()
        assert "Error: Parse error" in formatted
        assert "Details:" in formatted
        assert "file: test.py" in formatted
        assert "line: 10" in formatted

    def test_format_error_with_hint_and_details(self):
        """Test format_error with both hint and details."""
        details = {"status": "failed", "code": 500}
        error = ScriptRAGError(
            "Request failed",
            hint="Check network connection",
            details=details,
        )
        formatted = error.format_error()
        assert "Error: Request failed" in formatted
        assert "Hint: Check network connection" in formatted
        assert "Details:" in formatted
        assert "status: failed" in formatted
        assert "code: 500" in formatted

    def test_format_error_empty_details_dict(self):
        """Test format_error with empty details dictionary."""
        error = ScriptRAGError("Test error", details={})
        formatted = error.format_error()
        # Empty details should not add Details section
        assert formatted == "Error: Test error"
        assert "Details:" not in formatted

    def test_str_calls_format_error(self):
        """Test that __str__ calls format_error method."""
        error = ScriptRAGError("Test", hint="Hint")
        str_result = str(error)
        format_result = error.format_error()
        assert str_result == format_result

    def test_inheritance(self):
        """Test ScriptRAGError inheritance."""
        error = ScriptRAGError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, ScriptRAGError)


class TestLLMFallbackErrorComplete:
    """Complete tests for LLMFallbackError class."""

    def test_init_default_values(self):
        """Test LLMFallbackError with default values."""
        error = LLMFallbackError()
        assert error.message == "All LLM providers failed"
        assert error.provider_errors == {}
        assert error.attempted_providers == []
        assert error.fallback_chain == []
        assert error.debug_info is None
        assert error.hint is None

    def test_init_with_message_only(self):
        """Test LLMFallbackError with custom message."""
        error = LLMFallbackError("Custom failure message")
        assert error.message == "Custom failure message"
        assert error.provider_errors == {}
        assert error.attempted_providers == []
        assert error.fallback_chain == []
        assert error.debug_info is None

    def test_init_with_provider_errors(self):
        """Test LLMFallbackError with provider errors."""
        provider_errors = {
            "openai": ValueError("API key invalid"),
            "claude": ConnectionError("Connection timeout"),
        }
        error = LLMFallbackError(provider_errors=provider_errors)
        assert error.provider_errors == provider_errors
        assert "Check provider credentials and availability" in error.hint

    def test_init_with_attempted_providers(self):
        """Test LLMFallbackError with attempted providers."""
        attempted = ["openai", "claude", "github"]
        error = LLMFallbackError(attempted_providers=attempted)
        assert error.attempted_providers == attempted
        assert "Tried 3 providers" in error.hint

    def test_init_with_fallback_chain(self):
        """Test LLMFallbackError with fallback chain."""
        chain = ["primary", "secondary", "tertiary"]
        error = LLMFallbackError(fallback_chain=chain)
        assert error.fallback_chain == chain
        assert error.details["fallback_chain"] == chain

    def test_init_with_debug_info(self):
        """Test LLMFallbackError with debug information."""
        debug_info = {"stack_traces": ["trace1", "trace2"], "timing": "5.2s"}
        error = LLMFallbackError(debug_info=debug_info)
        assert error.debug_info == debug_info
        assert error.details["debug_info"] == debug_info

    def test_init_with_all_parameters(self):
        """Test LLMFallbackError with all parameters."""
        provider_errors = {"openai": ValueError("test error")}
        attempted = ["openai", "claude"]
        chain = ["openai", "claude"]
        debug_info = {"test": "data"}

        error = LLMFallbackError(
            message="Complete failure",
            provider_errors=provider_errors,
            attempted_providers=attempted,
            fallback_chain=chain,
            debug_info=debug_info,
        )

        assert error.message == "Complete failure"
        assert error.provider_errors == provider_errors
        assert error.attempted_providers == attempted
        assert error.fallback_chain == chain
        assert error.debug_info == debug_info

        # Check hint construction
        assert "Tried 2 providers" in error.hint
        assert "Check provider credentials and availability" in error.hint

        # Check details construction
        assert error.details["attempted_providers"] == attempted
        assert error.details["fallback_chain"] == chain
        assert error.details["provider_count"] == 2
        assert "openai" in error.details["provider_errors"]
        assert error.details["debug_info"] == debug_info

    def test_provider_errors_string_conversion(self):
        """Test that provider errors are converted to strings in details."""
        provider_errors = {
            "openai": ValueError("API error"),
            "claude": KeyError("missing key"),
        }
        error = LLMFallbackError(provider_errors=provider_errors)

        # Original errors should be preserved
        assert isinstance(error.provider_errors["openai"], ValueError)
        assert isinstance(error.provider_errors["claude"], KeyError)

        # Details should have string versions
        details_errors = error.details["provider_errors"]
        assert details_errors["openai"] == "API error"
        assert details_errors["claude"] == "'missing key'"

    def test_hint_with_both_providers_and_errors(self):
        """Test hint generation with both attempted providers and errors."""
        provider_errors = {"openai": ValueError("test")}
        attempted = ["openai", "claude"]
        error = LLMFallbackError(
            provider_errors=provider_errors, attempted_providers=attempted
        )

        # Should contain both parts joined with '. '
        assert (
            error.hint
            == "Tried 2 providers. Check provider credentials and availability"
        )

    def test_hint_with_no_providers_or_errors(self):
        """Test hint generation with no providers or errors."""
        error = LLMFallbackError()
        assert error.hint is None

    def test_inheritance(self):
        """Test LLMFallbackError inheritance."""
        error = LLMFallbackError()
        assert isinstance(error, LLMError)
        assert isinstance(error, ScriptRAGError)
        assert isinstance(error, Exception)


class TestLLMRetryableErrorComplete:
    """Complete tests for LLMRetryableError class."""

    def test_init_message_only(self):
        """Test LLMRetryableError with message only."""
        error = LLMRetryableError("Connection failed")
        assert error.message == "Connection failed"
        assert error.provider is None
        assert error.retry_after is None
        assert error.attempt is None
        assert error.max_attempts is None
        assert error.original_error is None
        assert error.hint is None

    def test_init_with_provider(self):
        """Test LLMRetryableError with provider."""
        error = LLMRetryableError("Test error", provider="openai")
        assert error.provider == "openai"
        assert error.details["provider"] == "openai"

    def test_init_with_retry_after(self):
        """Test LLMRetryableError with retry_after."""
        error = LLMRetryableError("Rate limited", retry_after=30.5)
        assert error.retry_after == 30.5
        assert "Retry after 30.5 seconds" in error.hint
        assert error.details["retry_after"] == 30.5

    def test_init_with_attempt_info(self):
        """Test LLMRetryableError with attempt information."""
        error = LLMRetryableError("Failed", attempt=3, max_attempts=5)
        assert error.attempt == 3
        assert error.max_attempts == 5
        assert "Attempt 3/5" in error.hint
        assert error.details["attempt"] == 3
        assert error.details["max_attempts"] == 5

    def test_init_with_original_error(self):
        """Test LLMRetryableError with original error."""
        original = ConnectionError("Network timeout")
        error = LLMRetryableError("Retry needed", original_error=original)
        assert error.original_error is original
        assert "ConnectionError: Network timeout" in error.details["original_error"]

    def test_init_with_all_parameters(self):
        """Test LLMRetryableError with all parameters."""
        original = ValueError("Invalid input")
        error = LLMRetryableError(
            message="Full retry error",
            provider="claude",
            retry_after=60.0,
            attempt=2,
            max_attempts=3,
            original_error=original,
        )

        assert error.message == "Full retry error"
        assert error.provider == "claude"
        assert error.retry_after == 60.0
        assert error.attempt == 2
        assert error.max_attempts == 3
        assert error.original_error is original

        # Check hint construction
        assert error.hint == "Retry after 60.0 seconds. Attempt 2/3"

        # Check details construction
        assert error.details["provider"] == "claude"
        assert error.details["retry_after"] == 60.0
        assert error.details["attempt"] == 2
        assert error.details["max_attempts"] == 3
        assert "ValueError: Invalid input" in error.details["original_error"]

    def test_hint_with_retry_after_only(self):
        """Test hint generation with retry_after only."""
        error = LLMRetryableError("Test", retry_after=15.0)
        assert error.hint == "Retry after 15.0 seconds"

    def test_hint_with_attempt_info_only(self):
        """Test hint generation with attempt info only."""
        error = LLMRetryableError("Test", attempt=1, max_attempts=3)
        assert error.hint == "Attempt 1/3"

    def test_hint_with_both_retry_and_attempt(self):
        """Test hint generation with both retry and attempt info."""
        error = LLMRetryableError("Test", retry_after=10.0, attempt=2, max_attempts=5)
        assert error.hint == "Retry after 10.0 seconds. Attempt 2/5"

    def test_hint_with_no_retry_info(self):
        """Test hint generation with no retry information."""
        error = LLMRetryableError("Test")
        assert error.hint is None

    def test_details_partial_info(self):
        """Test details construction with partial information."""
        error = LLMRetryableError("Test", provider="openai", attempt=1)
        expected_keys = {"provider", "attempt"}
        assert set(error.details.keys()) == expected_keys
        assert "retry_after" not in error.details
        assert "max_attempts" not in error.details
        assert "original_error" not in error.details

    def test_inheritance(self):
        """Test LLMRetryableError inheritance."""
        error = LLMRetryableError("Test")
        assert isinstance(error, LLMError)
        assert isinstance(error, ScriptRAGError)
        assert isinstance(error, Exception)


class TestRateLimitErrorAdditional:
    """Additional tests for RateLimitError to ensure complete coverage."""

    def test_init_with_none_values(self):
        """Test RateLimitError with explicit None values."""
        error = RateLimitError(
            message="Custom message", retry_after=None, provider=None
        )
        assert error.message == "Custom message"
        assert error.retry_after is None
        assert error.provider is None
        assert error.hint is None
        assert error.details == {}  # Empty because both are None

    def test_details_construction_retry_after_only(self):
        """Test details with retry_after but no provider."""
        error = RateLimitError(retry_after=45.0)
        assert error.details == {"retry_after": 45.0}
        assert "provider" not in error.details

    def test_details_construction_provider_only(self):
        """Test details with provider but no retry_after."""
        error = RateLimitError(provider="test_provider")
        assert error.details == {"provider": "test_provider"}
        assert "retry_after" not in error.details


class TestAllExceptionClassesInit:
    """Test initialization of all simple exception classes."""

    @pytest.mark.parametrize(
        "exception_class",
        [
            DatabaseError,
            ConfigurationError,
            ParseError,
            ScriptRAGFileNotFoundError,
            ValidationError,
            LLMError,
            LLMProviderError,
            GitError,
            ScriptRAGIndexError,
            QueryError,
            SearchError,
        ],
    )
    def test_simple_exception_init(self, exception_class):
        """Test that all simple exception classes can be initialized."""
        error = exception_class("Test message")
        assert error.message == "Test message"
        assert isinstance(error, ScriptRAGError)
        assert isinstance(error, Exception)
        assert str(error) == "Error: Test message"

    @pytest.mark.parametrize(
        "exception_class",
        [
            DatabaseError,
            ConfigurationError,
            ParseError,
            ScriptRAGFileNotFoundError,
            ValidationError,
            LLMError,
            LLMProviderError,
            GitError,
            ScriptRAGIndexError,
            QueryError,
            SearchError,
        ],
    )
    def test_simple_exception_with_hint_and_details(self, exception_class):
        """Test simple exceptions with hint and details."""
        details = {"key": "value", "number": 123}
        error = exception_class("Test error", hint="Test hint", details=details)
        assert error.message == "Test error"
        assert error.hint == "Test hint"
        assert error.details == details
        error_str = str(error)
        assert "Error: Test error" in error_str
        assert "Hint: Test hint" in error_str
        assert "Details:" in error_str
        assert "key: value" in error_str
        assert "number: 123" in error_str


class TestCheckDatabasePathComplete:
    """Complete tests for check_database_path function."""

    def test_valid_path_no_exception(self, tmp_path):
        """Test that valid path doesn't raise exception."""
        db_file = tmp_path / "valid.db"
        db_file.touch()
        # Should not raise
        check_database_path(db_file)

    def test_invalid_path_raises_database_error(self):
        """Test that invalid path raises DatabaseError."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("/nonexistent/path/db.sqlite")
        assert "Database not found" in str(exc_info.value)

    def test_none_path_error_message(self):
        """Test error message when path is None."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(None)
        error = exc_info.value
        assert error.details["searched_path"] == "None"
        assert "current_dir" in error.details

    def test_empty_string_path(self):
        """Test with empty string path."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("")
        error = exc_info.value
        assert "searched_path: " in str(error)

    def test_false_path(self):
        """Test with False as path."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(False)
        error = exc_info.value
        assert "searched_path: None" in str(error)

    def test_with_default_paths(self):
        """Test with default paths provided."""
        default_paths = [Path("/default1"), Path("/default2")]
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("/missing", default_paths)
        error = exc_info.value
        assert "default_paths" in error.details
        assert len(error.details["default_paths"]) == 2

    def test_with_empty_default_paths(self):
        """Test with empty default paths list."""
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path("/missing", [])
        error = exc_info.value
        # Empty list is falsy, so default_paths won't be in details
        assert "default_paths" not in error.details

    def test_scriptrag_db_exists_hint(self, tmp_path, monkeypatch):
        """Test hint when scriptrag.db exists in current directory."""
        # Create scriptrag.db in temp directory
        scriptrag_db = tmp_path / "scriptrag.db"
        scriptrag_db.touch()

        # Change to that directory
        monkeypatch.chdir(tmp_path)

        # Try with missing database
        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(tmp_path / "missing.db")

        error = exc_info.value
        assert "Found scriptrag.db in current dir. Use that?" in error.hint

    def test_default_hint_when_no_scriptrag_db(self, tmp_path, monkeypatch):
        """Test default hint when scriptrag.db doesn't exist."""
        # Change to empty directory
        monkeypatch.chdir(tmp_path)

        with pytest.raises(DatabaseError) as exc_info:
            check_database_path(tmp_path / "missing.db")

        error = exc_info.value
        assert "Run 'scriptrag init' to create a new database" in error.hint
        assert "Or set SCRIPTRAG_DATABASE_PATH environment variable" in error.hint


class TestCheckConfigKeysComplete:
    """Complete tests for check_config_keys function."""

    def test_valid_config_no_exception(self):
        """Test that valid config doesn't raise exception."""
        valid_config = {
            "database_path": "/path/to/db",
            "llm_api_key": "key",  # pragma: allowlist secret
            "llm_model": "gpt-4",
            "other_valid_key": "value",
        }
        # Should not raise
        check_config_keys(valid_config)

    def test_empty_config_no_exception(self):
        """Test that empty config doesn't raise exception."""
        # Should not raise
        check_config_keys({})

    def test_db_path_wrong_key(self):
        """Test detection of wrong db_path key."""
        config = {"db_path": "/path"}
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)
        error = exc_info.value
        assert "Invalid configuration key 'db_path'" in error.message
        assert "Use 'database_path' instead" in error.hint
        assert error.details["invalid_key"] == "db_path"
        assert error.details["correct_key"] == "database_path"
        assert "db_path" in error.details["found_keys"]

    def test_api_key_wrong_key(self):
        """Test detection of wrong api_key key."""
        config = {"api_key": "secret"}  # pragma: allowlist secret
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)
        error = exc_info.value
        assert "Invalid configuration key 'api_key'" in error.message
        assert "Use 'llm_api_key' instead" in error.hint
        assert error.details["invalid_key"] == "api_key"
        assert error.details["correct_key"] == "llm_api_key"

    def test_model_wrong_key(self):
        """Test detection of wrong model key."""
        config = {"model": "gpt-4"}
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)
        error = exc_info.value
        assert "Invalid configuration key 'model'" in error.message
        assert "Use 'llm_model' instead" in error.hint
        assert error.details["invalid_key"] == "model"
        assert error.details["correct_key"] == "llm_model"

    def test_multiple_wrong_keys_stops_at_first(self):
        """Test that function stops at first wrong key found."""
        config = {
            "db_path": "/path",
            "api_key": "key",  # pragma: allowlist secret
            "model": "gpt-4",
        }
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)
        error = exc_info.value
        # Should only report the first error found (dict iteration order)
        # but all keys should be in found_keys
        assert len(error.details["found_keys"]) == 3
        assert "db_path" in error.details["found_keys"]
        assert "api_key" in error.details["found_keys"]
        assert "model" in error.details["found_keys"]

    def test_mixed_valid_invalid_keys(self):
        """Test config with mix of valid and invalid keys."""
        config = {
            "database_path": "/valid/path",  # Valid
            "db_path": "/invalid/path",  # Invalid
            "llm_model": "gpt-4",  # Valid
        }
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_keys(config)
        error = exc_info.value
        # Should catch the invalid key
        assert "db_path" in str(error)
        # All keys should be listed in found_keys
        assert len(error.details["found_keys"]) == 3


class TestCLIErrorHandlerIntegration:
    """Test CLI error handler integration with exceptions."""

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_scriptrag_error_basic(self, mock_logger, mock_console):
        """Test handling of basic ScriptRAG error."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = ScriptRAGError("Test error message")

        with pytest.raises(typer.Exit):
            handle_cli_error(error)

        # Check console output
        mock_console.print.assert_called_once_with("[red]✗ Test error message[/red]")

        # Check logging
        mock_logger.error.assert_called_once()
        log_call_args = mock_logger.error.call_args
        assert log_call_args[0][0] == "ScriptRAG error occurred"
        assert log_call_args[1]["error_type"] == "ScriptRAGError"
        assert log_call_args[1]["message"] == "Test error message"

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_scriptrag_error_with_hint(self, mock_logger, mock_console):
        """Test handling of ScriptRAG error with hint."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = ScriptRAGError("Error message", hint="Helpful hint")

        with pytest.raises(typer.Exit):
            handle_cli_error(error)

        # Check console calls
        expected_calls = [
            ("[red]✗ Error message[/red]",),
            ("[yellow]→ Helpful hint[/yellow]",),
        ]
        actual_calls = [call[0] for call in mock_console.print.call_args_list]
        assert actual_calls == expected_calls

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_scriptrag_error_with_details_verbose(
        self, mock_logger, mock_console
    ):
        """Test handling of ScriptRAG error with details in verbose mode."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        details = {"file": "test.py", "line": 42}
        error = ScriptRAGError("Parse error", details=details)

        with pytest.raises(typer.Exit):
            handle_cli_error(error, verbose=True)

        # Check that details are printed in verbose mode
        calls = mock_console.print.call_args_list
        call_args = [call[0][0] for call in calls]

        assert "[red]✗ Parse error[/red]" in call_args
        assert "\n[dim]Details:[/dim]" in call_args
        assert "  [dim]file:[/dim] test.py" in call_args
        assert "  [dim]line:[/dim] 42" in call_args

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_scriptrag_error_with_details_not_verbose(
        self, mock_logger, mock_console
    ):
        """Test handling of ScriptRAG error with details in non-verbose mode."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        details = {"file": "test.py", "line": 42}
        error = ScriptRAGError("Parse error", details=details)

        with pytest.raises(typer.Exit):
            handle_cli_error(error, verbose=False)

        # Check that details are NOT printed in non-verbose mode
        calls = mock_console.print.call_args_list
        call_args = [call[0][0] for call in calls]

        assert "[red]✗ Parse error[/red]" in call_args
        # Details should not be printed
        assert not any("Details:" in call for call in call_args)
        assert not any("file:" in call for call in call_args)

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_file_not_found_error(self, mock_logger, mock_console):
        """Test handling of FileNotFoundError."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = FileNotFoundError("No such file or directory: 'test.txt'")
        error.filename = "test.txt"

        with pytest.raises(typer.Exit):
            handle_cli_error(error)

        # Check console output
        calls = mock_console.print.call_args_list
        call_args = [call[0][0] for call in calls]
        assert any("File not found:" in call for call in call_args)
        assert any("Check that the file path is correct" in call for call in call_args)

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_keyboard_interrupt(self, mock_logger, mock_console):
        """Test handling of KeyboardInterrupt."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = KeyboardInterrupt()

        with pytest.raises(typer.Exit):
            handle_cli_error(error)

        # Check console output
        mock_console.print.assert_called_with(
            "\n[yellow]Operation cancelled by user[/yellow]"
        )

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_generic_error_not_verbose(self, mock_logger, mock_console):
        """Test handling of generic error in non-verbose mode."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = RuntimeError("Something went wrong")

        with pytest.raises(typer.Exit):
            handle_cli_error(error, verbose=False)

        calls = mock_console.print.call_args_list
        call_args = [call[0][0] for call in calls]

        assert any(
            "Unexpected error: Something went wrong" in call for call in call_args
        )
        assert any(
            "Run with --verbose for full error details" in call for call in call_args
        )

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    @patch("scriptrag.cli.utils.error_handler.traceback")
    def test_handle_generic_error_verbose(
        self, mock_traceback, mock_logger, mock_console
    ):
        """Test handling of generic error in verbose mode."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        mock_traceback.format_exc.return_value = "Mock traceback\nline 2\nline 3"
        error = RuntimeError("Something went wrong")

        with pytest.raises(typer.Exit):
            handle_cli_error(error, verbose=True)

        calls = mock_console.print.call_args_list
        call_args = [call[0][0] for call in calls]

        assert any(
            "Unexpected error: Something went wrong" in call for call in call_args
        )
        assert any("Full traceback:" in call for call in call_args)
        assert any("Mock traceback\nline 2\nline 3" in call for call in call_args)

    @patch("scriptrag.cli.utils.error_handler.console")
    @patch("scriptrag.cli.utils.error_handler.logger")
    def test_handle_cli_error_custom_exit_code(self, mock_logger, mock_console):
        """Test handling error with custom exit code."""
        from scriptrag.cli.utils.error_handler import handle_cli_error

        error = ScriptRAGError("Test error")

        with pytest.raises(typer.Exit) as exc_info:
            handle_cli_error(error, exit_code=42)

        # Check that the custom exit code is used
        assert exc_info.value.exit_code == 42


class TestComplexErrorScenarios:
    """Test complex error scenarios and edge cases."""

    def test_nested_exception_chaining(self):
        """Test exception chaining behavior."""
        original_error = ValueError("Original problem")
        try:
            raise original_error
        except ValueError as e:
            wrapped_error = DatabaseError(
                "Database connection failed",
                hint="Check network connectivity",
                details={"original_error": str(e)},
            )
            wrapped_error.__cause__ = e

        assert wrapped_error.__cause__ is original_error
        assert "Database connection failed" in str(wrapped_error)
        assert "original_error: Original problem" in str(wrapped_error)

    def test_error_with_complex_details(self):
        """Test error with complex nested data structures."""
        complex_details = {
            "nested_dict": {"level1": {"level2": "deep_value"}},
            "list_data": [1, 2, {"nested": "in_list"}],
            "tuple_data": ("a", "b", "c"),
            "none_value": None,
            "boolean_true": True,
            "boolean_false": False,
        }
        error = ScriptRAGError("Complex error", details=complex_details)
        error_str = str(error)

        # All complex data should be converted to string representation
        assert "nested_dict: {'level1': {'level2': 'deep_value'}}" in error_str
        assert "list_data: [1, 2, {'nested': 'in_list'}]" in error_str
        assert "tuple_data: ('a', 'b', 'c')" in error_str
        assert "none_value: None" in error_str
        assert "boolean_true: True" in error_str
        assert "boolean_false: False" in error_str

    def test_error_message_with_newlines_and_special_chars(self):
        """Test error messages containing newlines and special characters."""
        message = "Multi-line\nerror\tmessage\nwith special chars: éñ🎭"
        hint = "Multi-line\nhint with\ttabs"
        details = {"multi_line_key\nwith\ttab": "multi_line\nvalue"}

        error = ScriptRAGError(message, hint=hint, details=details)
        error_str = str(error)

        assert message in error_str
        assert hint in error_str
        assert "multi_line_key\nwith\ttab: multi_line\nvalue" in error_str

    def test_error_inheritance_chain(self):
        """Test the complete inheritance chain for all exceptions."""
        test_cases = [
            (RateLimitError, [LLMError, ScriptRAGError, Exception]),
            (LLMFallbackError, [LLMError, ScriptRAGError, Exception]),
            (DatabaseError, [ScriptRAGError, Exception]),
            (ConfigurationError, [ScriptRAGError, Exception]),
        ]

        for exception_class, expected_bases in test_cases:
            error = exception_class("test")
            for base_class in expected_bases:
                assert isinstance(error, base_class)

    def test_exception_attribute_access(self):
        """Test direct attribute access on exception instances."""
        error = ScriptRAGError(
            "Test message", hint="Test hint", details={"key": "value"}
        )

        # Direct attribute access should work
        assert error.message == "Test message"
        assert error.hint == "Test hint"
        assert error.details["key"] == "value"

        # Modifying attributes should work
        error.message = "Modified message"
        error.hint = "Modified hint"
        error.details["new_key"] = "new_value"

        assert error.message == "Modified message"
        assert error.hint == "Modified hint"
        assert error.details["new_key"] == "new_value"

        # Format should reflect changes
        formatted = error.format_error()
        assert "Modified message" in formatted
        assert "Modified hint" in formatted
        assert "new_key: new_value" in formatted
