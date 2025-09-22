"""ScriptRAG configuration settings."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from scriptrag.exceptions import ConfigurationError, check_config_keys


class ScriptRAGSettings(BaseSettings):
    """ScriptRAG configuration settings.

    Settings are loaded with the following precedence (highest to lowest):
    1. CLI arguments (when provided via command flags)
       Example: scriptrag index --db-path /custom/path.db

    2. Config file values (YAML, TOML, or JSON)
       Example: scriptrag --config myconfig.yaml
       Multiple files: Later files override earlier ones

    3. Environment variables (prefixed with SCRIPTRAG_)
       Example: export SCRIPTRAG_DATABASE_PATH=/data/scripts.db

    4. .env file (in current directory or specified path)
       Example: SCRIPTRAG_LOG_LEVEL=DEBUG in .env file

    5. Default values (defined in field declarations below)

    Use 'scriptrag config validate' to see the effective configuration
    after all sources are merged.
    """

    model_config = SettingsConfigDict(
        env_prefix="SCRIPTRAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database settings
    database_path: Path = Field(
        default_factory=lambda: Path.cwd() / "scriptrag.db",
        description="Path to the SQLite database file",
    )
    database_timeout: float = Field(
        default=30.0,
        description="SQLite connection timeout in seconds",
        ge=0.1,
    )
    database_foreign_keys: bool = Field(
        default=True,
        description="Enable foreign key constraints",
    )
    database_journal_mode: str = Field(
        default="WAL",
        description="SQLite journal mode (DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF)",
        pattern="^(DELETE|TRUNCATE|PERSIST|MEMORY|WAL|OFF)$",
    )
    database_synchronous: str = Field(
        default="NORMAL",
        description="SQLite synchronous mode (OFF, NORMAL, FULL, EXTRA)",
        pattern="^(OFF|NORMAL|FULL|EXTRA)$",
    )
    database_cache_size: int = Field(
        default=-2000,
        description="SQLite cache size (negative = KB, positive = pages)",
    )
    database_temp_store: str = Field(
        default="MEMORY",
        description="SQLite temp store location (DEFAULT, FILE, MEMORY)",
        pattern="^(DEFAULT|FILE|MEMORY)$",
    )

    # Application settings
    app_name: str = Field(
        default="scriptrag",
        description="Application name",
    )
    metadata_scan_size: int = Field(
        default=10240,
        description=(
            "Number of bytes to read from end of file when scanning for metadata "
            "(0 = read entire file)"
        ),
        ge=0,
    )
    skip_boneyard_filter: bool = Field(
        default=False,
        description=(
            "Skip boneyard metadata filtering during indexing "
            "(useful for testing with scripts that don't have metadata)"
        ),
    )

    # Debug settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # Logging settings
    log_level: str = Field(
        default="WARNING",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        pattern="^(?i)(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )
    log_format: str = Field(
        default="console",
        description="Log output format (console, json, structured)",
        pattern="^(?i)(console|json|structured)$",
    )
    log_file: Path | None = Field(
        default=None,
        description="Optional log file path",
    )
    log_file_rotation: str = Field(
        default="1 day",
        description="Log file rotation interval",
    )
    log_file_retention: str = Field(
        default="7 days",
        description="Log file retention period",
    )

    # Search settings
    search_vector_threshold: int = Field(
        default=10,
        description="Word count threshold for automatic vector search",
        ge=1,
    )
    search_vector_similarity_threshold: float = Field(
        default=0.3,
        description="Minimum similarity score for vector search results",
        ge=0.0,
        le=1.0,
    )
    search_vector_result_limit_factor: float = Field(
        default=0.5,
        description="Factor of query limit to use for vector results",
        ge=0.1,
        le=1.0,
    )
    search_vector_min_results: int = Field(
        default=5,
        description="Minimum number of vector results to fetch",
        ge=1,
    )
    search_thread_timeout: float = Field(
        default=300.0,
        description="Timeout in seconds for search thread execution",
        ge=1.0,
    )

    # LLM settings
    llm_provider: str | None = Field(
        default=None,
        description="Preferred LLM provider: claude_code, github_models, openai",
    )
    llm_endpoint: str | None = Field(
        default=None,
        description="OpenAI-compatible API endpoint URL",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="API key for OpenAI-compatible endpoint",
    )
    llm_model: str | None = Field(
        default=None,
        description=(
            "Default model to use for completions. "
            "Use 'default', 'auto', 'none', or empty string for automatic selection."
        ),
    )
    llm_embedding_model: str | None = Field(
        default=None,
        description=(
            "Default model to use for embeddings. "
            "Use 'default', 'auto', 'none', or empty string for automatic selection."
        ),
    )
    llm_embedding_dimensions: int | None = Field(
        default=None,
        description="Dimensions for embedding vectors (e.g., 1536)",
    )
    llm_temperature: float = Field(
        default=0.7,
        description="Default temperature for completions",
        ge=0.0,
        le=2.0,
    )
    llm_max_tokens: int | None = Field(
        default=None,
        description="Default max tokens for completions",
    )
    llm_force_static_models: bool = Field(
        default=False,
        description="Force use of static model lists instead of dynamic discovery",
    )
    llm_model_cache_ttl: int = Field(
        default=3600,
        description="TTL in seconds for cached model lists (0 to disable caching)",
        ge=0,
    )

    # Bible-specific settings
    bible_embeddings_path: str = Field(
        default="embeddings/bible",
        description="Path for storing bible chunk embeddings in Git LFS",
    )
    bible_max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum size for bible files in bytes",
        gt=0,
    )
    bible_llm_context_limit: int = Field(
        default=2000,
        description=(
            "Maximum character limit for LLM context when extracting bible aliases"
        ),
        gt=0,
    )

    @field_validator("database_path", "log_file", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path | None:
        """Expand environment variables and resolve path.

        Accepts:
        - None (for optional fields)
        - str: Path as string, supports env vars and ~ expansion
        - Path: pathlib.Path object
        - Numbers: Converted to string (e.g., 123 -> "123")

        Rejects:
        - dict, list, set: Not valid path representations
        - Complex objects without proper string conversion
        """
        if v is None:
            return None
        if isinstance(v, str):
            # Expand environment variables like $HOME
            expanded = os.path.expandvars(v)
            # Expand user home directory ~
            path = Path(expanded).expanduser()
            return path.resolve()
        if isinstance(v, Path):
            return v.resolve()

        # Explicitly reject collection types that shouldn't be paths
        if isinstance(v, (dict, list, set, tuple)):  # noqa: UP038
            raise ValueError(
                f"Path fields cannot accept {type(v).__name__} types. "
                f"Expected str or Path, got: {v!r}"
            )

        # For other types (numbers, bools, etc.), try string conversion
        try:
            # Convert to string and then to Path for numeric types, etc.
            str_value = str(v)
            return Path(str_value).resolve()
        except (TypeError, ValueError, OSError) as e:
            # Provide a clear error message for unsupported types
            raise ValueError(
                f"Path fields must be string, Path, or convertible to string. "
                f"Got {type(v).__name__}: {v!r}"
            ) from e

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: Any) -> str:
        """Normalize log level to uppercase for case-insensitive handling."""
        if isinstance(v, str):
            return v.upper()
        # Only accept string values, reject other types
        raise ValueError(f"log_level must be a string, got {type(v).__name__}")

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, v: Any) -> str:
        """Normalize log format to lowercase for case-insensitive handling."""
        if isinstance(v, str):
            return v.lower()
        # Only accept string values, reject other types
        raise ValueError(f"log_format must be a string, got {type(v).__name__}")

    @classmethod
    def from_env(cls) -> ScriptRAGSettings:
        """Create settings from environment variables."""
        return cls()

    @field_validator("llm_model", "llm_embedding_model", mode="before")
    @classmethod
    def normalize_llm_models(cls, v: Any) -> Any:
        """Normalize sentinel values for LLM model fields.

        Treat common placeholders like "default", "auto", empty strings,
        and "none" (any casing/whitespace) as unset (None) so that the
        application can auto-select appropriate models at runtime.
        """
        if v is None:
            return None
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"", "default", "auto", "none"}:
                # Log normalization at debug level for troubleshooting
                # Note: We can't use get_logger here since it's a class method
                # executed during model validation before the instance exists
                if os.getenv("SCRIPTRAG_DEBUG", "").lower() == "true":
                    import sys

                    # Use stderr directly since we're in a validator
                    sys.stderr.write(
                        f"DEBUG: Normalizing LLM model sentinel value '{v}' to None\n"
                    )
                    sys.stderr.flush()
                return None
        return v

    @classmethod
    def from_file(cls, config_path: Path | str) -> ScriptRAGSettings:
        """Load settings from a configuration file.

        Args:
            config_path: Path to configuration file (YAML, TOML, or JSON).

        Returns:
            Settings loaded from the file.

        Raises:
            ValueError: If file format is not supported.
            FileNotFoundError: If config file doesn't exist.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        suffix = config_path.suffix.lower()

        if suffix in {".yml", ".yaml"}:
            with config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        elif suffix == ".toml":
            with config_path.open("rb") as f:
                data = tomllib.load(f)
        elif suffix == ".json":
            with config_path.open(encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ConfigurationError(
                message=f"Unsupported configuration file format: {suffix}",
                hint="Use one of the supported formats: .yml, .yaml, .toml, or .json",
                details={
                    "file": str(config_path),
                    "detected_format": suffix,
                    "supported_formats": [".yml", ".yaml", ".toml", ".json"],
                },
            )

        # Check for common configuration mistakes
        check_config_keys(data)

        return cls(**data)

    @classmethod
    def from_multiple_sources(
        cls,
        config_files: list[Path | str] | None = None,
        env_file: Path | str | None = None,
        cli_args: dict[str, Any] | None = None,
    ) -> ScriptRAGSettings:
        """Load settings with proper precedence from multiple sources.

        Precedence (highest to lowest):
        1. CLI arguments
        2. Config files (last file wins)
        3. Environment variables
        4. .env file
        5. Default values

        Args:
            config_files: List of config files to load (later files override earlier).
            env_file: Path to .env file (default: .env in current directory).
            cli_args: Dictionary of CLI arguments.

        Returns:
            Merged settings from all sources.
        """
        # Start with defaults
        data = {}

        # Load from config files (each file can override previous)
        if config_files:
            for config_file in config_files:
                try:
                    file_settings = cls.from_file(config_file)
                    # Convert to dict and merge
                    file_data = file_settings.model_dump()
                    data.update(file_data)
                except FileNotFoundError:
                    # Import get_logger locally to avoid circular dependency
                    # during module initialization, but still emit proper log messages
                    try:
                        # Try to get a logger and emit proper warning
                        from scriptrag.config.logging import get_logger as _get_logger

                        logger = _get_logger("scriptrag.config.settings")
                        logger.warning(
                            "Configuration file not found, using defaults",
                            config_file=str(config_file),
                        )
                    except ImportError:
                        # Fallback to warnings if logging is not available
                        import warnings

                        warnings.warn(
                            f"Config file not found: {config_file}, using defaults",
                            UserWarning,
                            stacklevel=2,
                        )
                    # Config file doesn't exist - use defaults
                    pass

        # Create settings with env vars and .env file
        # This will apply env vars on top of config file values
        # Use typing.cast to tell mypy that _env_file is a valid parameter
        from typing import Any, cast

        if env_file:
            # pydantic-settings v2 supports _env_file parameter
            settings = cast(
                "ScriptRAGSettings", cast(Any, cls)(_env_file=env_file, **data)
            )
        else:
            settings = cls(**data)

        # Apply CLI args last (highest precedence)
        if cli_args:
            # Filter out None values from CLI args
            cli_data = {k: v for k, v in cli_args.items() if v is not None}
            if cli_data:
                # Update settings with CLI args
                updated_data = settings.model_dump()
                updated_data.update(cli_data)
                settings = cls(**updated_data)

        return settings


# Global settings instance
_settings: ScriptRAGSettings | None = None
# Cache for config file paths that exist
_config_paths_cache: list[Path | str] | None = None


def _get_config_paths() -> list[Path | str]:
    """Get list of config file paths to check.

    Returns paths in priority order (later files override earlier).
    Caches the list of existing config files to avoid repeated filesystem checks.
    """
    global _config_paths_cache

    if _config_paths_cache is not None:
        return _config_paths_cache

    # Define all potential config paths in priority order
    # Based on documented hierarchy in src/scriptrag/config/CLAUDE.md
    potential_paths = [
        # System config
        Path("/etc/scriptrag/config.yaml"),
        Path("/etc/scriptrag/config.json"),
        Path("/etc/scriptrag/config.toml"),
        # User config in home directory
        Path.home() / ".scriptrag" / "config.yaml",
        Path.home() / ".scriptrag" / "config.json",
        Path.home() / ".scriptrag" / "config.toml",
        # User config in .config directory (XDG standard)
        Path.home() / ".config" / "scriptrag" / "config.yaml",
        Path.home() / ".config" / "scriptrag" / "config.json",
        Path.home() / ".config" / "scriptrag" / "config.toml",
        # Project config in current directory
        Path.cwd() / ".scriptrag" / "config.yaml",
        Path.cwd() / ".scriptrag" / "config.json",
        Path.cwd() / ".scriptrag" / "config.toml",
        # Alternative project config names
        Path.cwd() / "scriptrag.yaml",
        Path.cwd() / "scriptrag.json",
        Path.cwd() / "scriptrag.toml",
    ]

    # Filter to only existing files to avoid unnecessary warnings
    existing_paths: list[Path | str] = []
    for path in potential_paths:
        try:
            if path.exists() and path.is_file():
                existing_paths.append(path)
        except (OSError, PermissionError):
            # Skip paths we can't access
            continue

    # Cache the result
    _config_paths_cache = existing_paths
    return existing_paths


def get_settings() -> ScriptRAGSettings:
    """Get the global settings instance.

    Loads configuration from multiple sources with proper precedence:
    1. Environment variables (highest priority)
    2. Config files (in order: system, user, project)
    3. Default values (lowest priority)

    Returns:
        Global ScriptRAGSettings instance.
    """
    global _settings
    if _settings is None:
        config_paths = _get_config_paths()

        if config_paths:
            # Load from existing config files
            _settings = ScriptRAGSettings.from_multiple_sources(
                config_files=config_paths
            )
        else:
            # No config files found, load from environment only
            _settings = ScriptRAGSettings.from_env()
    return _settings


def set_settings(settings: ScriptRAGSettings) -> None:
    """Set the global settings instance.

    Args:
        settings: Settings instance to use globally.
    """
    global _settings
    _settings = settings


def clear_settings_cache() -> None:
    """Clear the global settings cache.

    This forces get_settings() to re-read from environment variables
    and configuration files on the next call. Useful for testing
    when environment variables are changed via monkeypatch.
    """
    global _settings, _config_paths_cache
    _settings = None
    _config_paths_cache = None


def reset_settings() -> None:
    """Reset the global settings instance.

    Forces recreation of settings on next call to get_settings(),
    useful for tests that modify environment variables.
    """
    # Alias to clear_settings_cache for backwards compatibility
    clear_settings_cache()


def get_settings_for_cli(
    config_file: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ScriptRAGSettings:
    """Get settings for CLI commands with consistent precedence.

    This is the standard way for CLI commands to load settings. It ensures
    consistent behavior across all commands with proper precedence:
    1. CLI arguments (highest priority)
    2. Specified config file OR standard config locations
    3. Environment variables
    4. Default values (lowest priority)

    Args:
        config_file: Optional specific config file to load. If not provided,
                    uses standard config locations.
        cli_overrides: Dictionary of CLI argument overrides (e.g., db_path).
                      Only non-None values are applied.

    Returns:
        ScriptRAGSettings instance with all sources merged.

    Raises:
        FileNotFoundError: If config_file is specified but doesn't exist.

    Example:
        # In a CLI command
        settings = get_settings_for_cli(
            config_file=config,  # From --config option
            cli_overrides={"database_path": db_path} if db_path else None
        )
    """
    if config_file:
        # User specified a config file explicitly
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        # Use the specified file with CLI overrides
        settings = ScriptRAGSettings.from_multiple_sources(
            config_files=[config_file],
            cli_args=cli_overrides,
        )
    else:
        # No config file specified, use standard locations
        # get_settings() already handles all standard paths efficiently
        settings = get_settings()

        # Apply CLI overrides if any
        if cli_overrides:
            # Filter out None values
            filtered_overrides = {
                k: v for k, v in cli_overrides.items() if v is not None
            }
            if filtered_overrides:
                # Create new instance with overrides
                data = settings.model_dump()
                data.update(filtered_overrides)
                settings = ScriptRAGSettings(**data)

    return settings
