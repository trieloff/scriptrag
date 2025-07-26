"""Configuration management for ScriptRAG.

This module provides centralized configuration management using Pydantic Settings
with support for environment variables, YAML config files, and validation.
"""

from pathlib import Path

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    # SQLite database path
    path: Path = Field(
        default=Path("./data/screenplay.db"), description="Path to SQLite database file"
    )

    # Connection settings
    pool_size: int = Field(
        default=10, description="Maximum number of database connections in the pool"
    )

    pool_timeout: int = Field(
        default=30, description="Timeout in seconds for getting connection from pool"
    )

    # Performance settings
    enable_wal_mode: bool = Field(
        default=True,
        description="Enable WAL (Write-Ahead Logging) mode for better concurrency",
    )

    synchronous_mode: str = Field(
        default="NORMAL", description="SQLite synchronous mode (OFF, NORMAL, FULL)"
    )

    cache_size: int = Field(
        default=10000, description="SQLite cache size in pages (negative for KB)"
    )

    @field_validator("path")
    def ensure_parent_directory(cls, v: Path) -> Path:
        """Ensure the database directory exists."""
        v.parent.mkdir(parents=True, exist_ok=True)
        return v

    model_config = {
        "env_prefix": "SCRIPTRAG_DB_",
        "extra": "ignore",
    }


class LLMSettings(BaseSettings):
    """LLM client configuration settings."""

    # API endpoint
    endpoint: str = Field(
        default="http://localhost:1234/v1",
        description="LLM API endpoint URL (LMStudio compatible)",
    )

    # Authentication
    api_key: str | None = Field(
        default=None, description="API key for authentication (if required)"
    )

    # Model settings
    default_model: str = Field(
        default="default", description="Default model name to use"
    )

    embedding_model: str = Field(
        default="default", description="Model name for embeddings generation"
    )

    # Request settings
    timeout: int = Field(default=120, description="Request timeout in seconds")

    max_retries: int = Field(default=3, description="Maximum number of retry attempts")

    retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )

    # Generation parameters
    max_tokens: int = Field(
        default=2048, description="Maximum tokens for text generation"
    )

    temperature: float = Field(
        default=0.7, description="Temperature for text generation (0.0-2.0)"
    )

    top_p: float = Field(default=0.9, description="Top-p sampling parameter (0.0-1.0)")

    # Embedding settings
    embedding_dimensions: int = Field(
        default=1536, description="Expected embedding vector dimensions"
    )

    batch_size: int = Field(
        default=32, description="Batch size for embedding generation"
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within valid range (0.0-2.0)."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v: float) -> float:
        """Validate top-p is within valid range (0.0-1.0)."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Top-p must be between 0.0 and 1.0")
        return v

    model_config = {
        "env_prefix": "SCRIPTRAG_LLM_",
        "extra": "ignore",
    }


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    format: str = Field(
        default="structured", description="Log format (structured, json, plain)"
    )

    file_path: Path | None = Field(
        default=None, description="Path to log file (None for console only)"
    )

    max_file_size: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum log file size in bytes",  # 10MB
    )

    backup_count: int = Field(
        default=5, description="Number of backup log files to keep"
    )

    json_logs: bool = Field(
        default=False, description="Whether to output logs in JSON format"
    )

    # Third-party library log levels
    sqlalchemy_level: str = Field(
        default="WARNING", description="Log level for SQLAlchemy"
    )

    httpx_level: str = Field(default="WARNING", description="Log level for HTTPX")

    @field_validator("level", "sqlalchemy_level", "httpx_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    model_config = {
        "env_prefix": "SCRIPTRAG_LOG_",
        "extra": "ignore",
    }


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) server settings."""

    # Server settings
    host: str = Field(default="localhost", description="MCP server host")

    port: int = Field(default=8080, description="MCP server port")

    # Resource settings
    max_resources: int = Field(
        default=1000, description="Maximum number of resources to expose"
    )

    resource_cache_ttl: int = Field(
        default=300, description="Resource cache TTL in seconds"
    )

    # Tool settings
    enable_all_tools: bool = Field(
        default=True, description="Whether to enable all available MCP tools"
    )

    enabled_tools: list[str] = Field(
        default_factory=lambda: [
            "parse_script",
            "search_scenes",
            "get_character_info",
            "analyze_timeline",
            "update_scene",
            "delete_scene",
            "inject_scene",
        ],
        description="List of enabled MCP tools",
    )

    model_config = {
        "env_prefix": "SCRIPTRAG_MCP_",
        "extra": "ignore",
    }


class PerformanceSettings(BaseSettings):
    """Performance and optimization settings."""

    # Graph processing
    max_graph_nodes: int = Field(
        default=100000, description="Maximum number of nodes in the graph"
    )

    max_traversal_depth: int = Field(
        default=10, description="Maximum depth for graph traversals"
    )

    # Caching
    enable_query_cache: bool = Field(
        default=True, description="Enable query result caching"
    )

    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")

    max_cache_size: int = Field(
        default=1000, description="Maximum number of cached items"
    )

    # Embedding processing
    embedding_batch_size: int = Field(
        default=100, description="Batch size for embedding operations"
    )

    max_concurrent_embeddings: int = Field(
        default=5, description="Maximum concurrent embedding requests"
    )

    # Memory management
    max_memory_usage: int = Field(
        default=2 * 1024 * 1024 * 1024,  # 2GB
        description="Maximum memory usage in bytes",
    )

    model_config = {
        "env_prefix": "SCRIPTRAG_PERF_",
        "extra": "ignore",
    }


class PathSettings(BaseSettings):
    """File path and directory settings."""

    # Base directories
    data_dir: Path = Field(
        default=Path("./data"), description="Base directory for data files"
    )

    cache_dir: Path = Field(
        default=Path("./cache"), description="Directory for cache files"
    )

    logs_dir: Path = Field(
        default=Path("./logs"), description="Directory for log files"
    )

    temp_dir: Path = Field(
        default=Path("./temp"), description="Directory for temporary files"
    )

    # Script directories
    scripts_dir: Path = Field(
        default=Path("./scripts"), description="Directory containing screenplay files"
    )

    exports_dir: Path = Field(
        default=Path("./exports"), description="Directory for exported files"
    )

    @field_validator(
        "data_dir", "cache_dir", "logs_dir", "temp_dir", "scripts_dir", "exports_dir"
    )
    def ensure_directory_exists(cls, v: Path) -> Path:
        """Ensure directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    model_config = {
        "env_prefix": "SCRIPTRAG_PATH_",
        "extra": "ignore",
    }


class APISettings(BaseSettings):
    """API server configuration settings."""

    # CORS settings
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # Auth settings (placeholder for future implementation)
    enable_auth: bool = Field(default=False, description="Enable authentication")

    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT tokens",
    )

    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )

    model_config = {
        "env_prefix": "SCRIPTRAG_API_",
        "extra": "ignore",
    }


class ScriptRAGSettings(BaseSettings):
    """Main ScriptRAG configuration settings."""

    # Environment
    environment: str = Field(
        default="development",
        description="Application environment (development, testing, production)",
    )

    debug: bool = Field(default=True, description="Enable debug mode")

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    api: APISettings = Field(default_factory=APISettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the supported environments."""
        valid_envs = ["development", "testing", "production"]
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "ScriptRAGSettings":
        """Load settings from YAML file.

        Args:
            file_path: Path to YAML configuration file

        Returns:
            ScriptRAGSettings instance
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with file_path.open(encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    def to_yaml(self, file_path: str | Path) -> None:
        """Save settings to YAML file.

        Args:
            file_path: Path to save YAML configuration file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(),
                f,
                default_flow_style=False,
                sort_keys=True,
                indent=2,
            )

    def get_log_file_path(self) -> Path | None:
        """Get the full path to the log file."""
        if self.logging.file_path:
            if self.logging.file_path.is_absolute():
                return self.logging.file_path
            return self.paths.logs_dir / self.logging.file_path
        return None

    def get_database_path(self) -> Path:
        """Get the full path to the database file."""
        if self.database.path.is_absolute():
            return self.database.path
        return self.paths.data_dir / self.database.path.name

    @property
    def llm_endpoint(self) -> str:
        """Get the LLM endpoint URL."""
        return self.llm.endpoint

    @property
    def llm_api_key(self) -> str | None:
        """Get the LLM API key."""
        return self.llm.api_key

    @property
    def database_url(self) -> str:
        """Get the database URL."""
        return f"sqlite+aiosqlite:///{self.get_database_path()}"

    @property
    def cors_origins(self) -> list[str]:
        """Get CORS origins."""
        return self.api.cors_origins


# Global settings instance
_settings: ScriptRAGSettings | None = None


def get_settings() -> ScriptRAGSettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = ScriptRAGSettings()
    return _settings


def load_settings(config_file: str | Path | None = None) -> ScriptRAGSettings:
    """Load settings from file or environment.

    Args:
        config_file: Optional path to configuration file

    Returns:
        ScriptRAGSettings instance
    """
    global _settings

    if config_file:
        _settings = ScriptRAGSettings.from_yaml(config_file)
    else:
        _settings = ScriptRAGSettings()

    return _settings


def reset_settings() -> None:
    """Reset the global settings instance."""
    global _settings
    _settings = None


# Configuration file templates
DEFAULT_CONFIG_TEMPLATE = """
# ScriptRAG Configuration File
# This file contains default settings for ScriptRAG

environment: development
debug: true

database:
  path: ./data/screenplay.db
  pool_size: 10
  enable_wal_mode: true
  synchronous_mode: NORMAL

llm:
  endpoint: http://localhost:1234/v1
  timeout: 120
  max_tokens: 2048
  temperature: 0.7
  top_p: 0.9

logging:
  level: INFO
  format: structured
  json_logs: false

mcp:
  host: localhost
  port: 8080
  enable_all_tools: true

performance:
  max_graph_nodes: 100000
  enable_query_cache: true
  cache_ttl: 3600

paths:
  data_dir: ./data
  cache_dir: ./cache
  logs_dir: ./logs
  scripts_dir: ./scripts
"""


def create_default_config(file_path: str | Path) -> None:
    """Create a default configuration file.

    Args:
        file_path: Path where to create the configuration file
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as f:
        f.write(DEFAULT_CONFIG_TEMPLATE.strip())
