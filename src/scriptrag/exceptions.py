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


class GitError(ScriptRAGError):
    """Git-related errors including LFS and repository issues."""

    pass


class ScriptRAGIndexError(ScriptRAGError):
    """Indexing errors including embedding and storage issues."""

    pass


class QueryError(ScriptRAGError):
    """Query execution errors including SQL and parameter issues."""

    pass


class SearchError(ScriptRAGError):
    """Search errors including query parsing and execution issues."""

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
        "llm_provider": "llm_config.provider",
        "api_key": "llm_config.api_key",  # pragma: allowlist secret
        "model": "llm_config.model",
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
