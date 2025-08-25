"""Custom exception hierarchy for ScriptRAG with helpful error messages."""

from __future__ import annotations

from typing import Any


class ScriptRAGError(Exception):
    """Base exception with helpful formatting for all ScriptRAG errors.

    Provides structured error messages with hints and details to help users
    understand and fix problems.
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize exception with structured error information.

        Args:
            message: Primary error message describing what went wrong
            hint: Optional hint suggesting how to fix the problem
            details: Optional dictionary with additional debugging information
        """
        self.message = message
        self.hint = hint
        self.details = details
        super().__init__(self.format_error())

    def format_error(self) -> str:
        """Format the error message with hint and details.

        Returns:
            Formatted error string with all available information
        """
        output = f"Error: {self.message}"
        if self.hint:
            output += f"\nHint: {self.hint}"
        if self.details:
            # Format details nicely
            details_str = "\n".join(
                f"  {key}: {value}" for key, value in self.details.items()
            )
            output += f"\nDetails:\n{details_str}"
        return output


class DatabaseError(ScriptRAGError):
    """Database-related errors including connection and query issues."""

    pass


class ConfigurationError(ScriptRAGError):
    """Configuration errors including invalid settings and missing config files."""

    pass


class ParseError(ScriptRAGError):
    """Fountain file parsing errors including format and structure issues."""

    pass


class ScriptRAGFileNotFoundError(ScriptRAGError):
    """File not found errors with helpful path information."""

    pass


class ValidationError(ScriptRAGError):
    """Input validation errors with details about what was expected."""

    pass


class LLMError(ScriptRAGError):
    """LLM provider errors including rate limits and API issues."""

    pass


class RateLimitError(LLMError):
    """Rate limit exceeded error for LLM providers."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        provider: str | None = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            provider: Provider that raised the error
        """
        self.retry_after = retry_after
        self.provider = provider
        hint = None
        if retry_after:
            hint = f"Please wait {retry_after} seconds before retrying"
        details: dict[str, Any] = {}
        if provider:
            details["provider"] = provider
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message=message, hint=hint, details=details)


class LLMProviderError(LLMError):
    """Generic LLM provider error for non-rate-limit failures."""

    pass


class LLMFallbackError(LLMError):
    """Error raised when all LLM providers fail with detailed fallback information."""

    def __init__(
        self,
        message: str = "All LLM providers failed",
        provider_errors: dict[str, Exception] | None = None,
        attempted_providers: list[str] | None = None,
        fallback_chain: list[str] | None = None,
        debug_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize fallback error with detailed provider failure information.

        Args:
            message: Primary error message
            provider_errors: Dictionary mapping provider names to their specific errors
            attempted_providers: List of providers that were attempted
            fallback_chain: The order in which providers were tried
            debug_info: Additional debugging information (stack traces, etc.)
        """
        self.provider_errors = provider_errors or {}
        self.attempted_providers = attempted_providers or []
        self.fallback_chain = fallback_chain or []
        self.debug_info = debug_info

        # Create structured hint
        hint_parts = []
        if self.attempted_providers:
            hint_parts.append(f"Tried {len(self.attempted_providers)} providers")
        if self.provider_errors:
            hint_parts.append("Check provider credentials and availability")

        hint = ". ".join(hint_parts) if hint_parts else None

        # Create detailed error information
        details: dict[str, Any] = {
            "attempted_providers": self.attempted_providers,
            "fallback_chain": self.fallback_chain,
            "provider_count": len(self.attempted_providers),
        }

        # Add individual provider errors
        if self.provider_errors:
            details["provider_errors"] = {
                provider: str(error) for provider, error in self.provider_errors.items()
            }

        # Add debug info if available
        if self.debug_info:
            details["debug_info"] = self.debug_info

        super().__init__(message=message, hint=hint, details=details)


class LLMRetryableError(LLMError):
    """Error for transient failures that can be retried with backoff."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
        attempt: int | None = None,
        max_attempts: int | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize retryable error.

        Args:
            message: Error message
            provider: Provider that failed
            retry_after: Suggested retry delay in seconds
            attempt: Current attempt number
            max_attempts: Maximum number of attempts
            original_error: The original exception that caused this error
        """
        self.provider = provider
        self.retry_after = retry_after
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.original_error = original_error

        hint_parts = []
        if retry_after:
            hint_parts.append(f"Retry after {retry_after} seconds")
        if attempt and max_attempts:
            hint_parts.append(f"Attempt {attempt}/{max_attempts}")

        hint = ". ".join(hint_parts) if hint_parts else None

        details: dict[str, Any] = {}
        if provider:
            details["provider"] = provider
        if retry_after:
            details["retry_after"] = retry_after
        if attempt:
            details["attempt"] = attempt
        if max_attempts:
            details["max_attempts"] = max_attempts
        if original_error:
            details["original_error"] = (
                f"{type(original_error).__name__}: {original_error}"
            )

        super().__init__(message=message, hint=hint, details=details)


class GitError(ScriptRAGError):
    """Git-related errors including LFS and repository issues."""

    pass


class ScriptRAGIndexError(ScriptRAGError):
    """Indexing errors including embedding and storage issues."""

    pass


class EmbeddingError(ScriptRAGError):
    """Embedding generation errors."""

    pass


class EmbeddingResponseError(EmbeddingError):
    """Error when embedding response is invalid or missing."""

    pass


class QueryError(ScriptRAGError):
    """Query execution errors including SQL and parameter issues."""

    pass


class SearchError(ScriptRAGError):
    """Search errors including query parsing and execution issues."""

    pass


class EmbeddingError(ScriptRAGError):
    """Errors related to embedding generation and storage."""

    pass


class EmbeddingLoadError(EmbeddingError):
    """Error loading saved embeddings from disk."""

    pass


class EmbeddingGenerationError(EmbeddingError):
    """Error generating embeddings with the LLM."""

    pass


class AnalyzerError(ScriptRAGError):
    """Base error for scene analyzer failures."""

    pass


class AnalyzerInitializationError(AnalyzerError):
    """Error initializing an analyzer."""

    pass


class AnalyzerExecutionError(AnalyzerError):
    """Error during analyzer execution on a scene."""

    pass


class FileSystemError(ScriptRAGError):
    """File system operation errors."""

    pass


def check_database_path(db_path: Any, default_paths: list[Any] | None = None) -> None:
    """Check for common database path issues and provide helpful errors.

    Args:
        db_path: Path to check for database
        default_paths: List of default paths that were searched

    Raises:
        DatabaseError: With helpful hints about database initialization
    """
    from pathlib import Path

    if not db_path or not Path(db_path).exists():
        # Check for common locations
        hints = []
        if Path("scriptrag.db").exists():
            hints.append("Found scriptrag.db in current dir. Use that?")

        if not hints:
            hints.append("Run 'scriptrag init' to create a new database")
            hints.append("Or set SCRIPTRAG_DATABASE_PATH environment variable")

        details: dict[str, Any] = {
            "searched_path": str(db_path) if db_path else "None",
            "current_dir": str(Path.cwd()),
        }

        if default_paths:
            details["default_paths"] = [str(p) for p in default_paths]

        raise DatabaseError(
            message=f"Database not found at {db_path}",
            hint=" ".join(hints),
            details=details,
        )


def check_config_keys(config: dict[str, Any]) -> None:
    """Check for common configuration mistakes.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ConfigurationError: With hints about correct configuration keys
    """
    # Common mistakes in config keys
    wrong_keys = {
        "db_path": "database_path",
        "api_key": "llm_api_key",  # pragma: allowlist secret
        "model": "llm_model",
    }

    for wrong, correct in wrong_keys.items():
        if wrong in config:
            raise ConfigurationError(
                message=f"Invalid configuration key '{wrong}'",
                hint=f"Use '{correct}' instead of '{wrong}'",
                details={
                    "found_keys": list(config.keys()),
                    "invalid_key": wrong,
                    "correct_key": correct,
                },
            )
