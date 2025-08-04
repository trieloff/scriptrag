"""ScriptRAG configuration settings."""

import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScriptRAGSettings(BaseSettings):
    """ScriptRAG configuration settings.

    Settings are loaded with the following precedence (highest to lowest):
    1. CLI arguments (when provided)
    2. Config file values
    3. Environment variables
    4. Default values
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

    # Application settings
    app_name: str = Field(
        default="scriptrag",
        description="Application name",
    )

    # Debug settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    @field_validator("database_path", mode="before")
    @classmethod
    def expand_database_path(cls, v: Any) -> Path:
        """Expand environment variables and resolve path."""
        if isinstance(v, str):
            # Expand environment variables like $HOME
            expanded = os.path.expandvars(v)
            # Expand user home directory ~
            path = Path(expanded).expanduser()
            return path.resolve()
        if isinstance(v, Path):
            return v.resolve()
        # Default case - convert to Path
        return Path(v)  # pragma: no cover
        # This line is a defensive fallback for unexpected types.
        # In practice, Pydantic ensures v is always str or Path.

    @classmethod
    def from_env(cls) -> "ScriptRAGSettings":
        """Create settings from environment variables."""
        return cls()


# Global settings instance
_settings: ScriptRAGSettings | None = None


def get_settings() -> ScriptRAGSettings:
    """Get the global settings instance.

    Returns:
        Global ScriptRAGSettings instance.
    """
    global _settings
    if _settings is None:
        _settings = ScriptRAGSettings.from_env()
    return _settings


def set_settings(settings: ScriptRAGSettings) -> None:
    """Set the global settings instance.

    Args:
        settings: Settings instance to use globally.
    """
    global _settings
    _settings = settings
