"""Configuration package for ScriptRAG.

This package provides centralized configuration management and logging setup.
"""

from .logging import (
    LOGGING_CONFIGS,
    TemporaryLogLevel,
    configure_logging,
    get_logger,
    setup_logging_for_environment,
)
from .settings import (
    DatabaseSettings,
    LLMSettings,
    LoggingSettings,
    MCPSettings,
    PathSettings,
    PerformanceSettings,
    ScriptRAGSettings,
    create_default_config,
    get_settings,
    load_settings,
    reset_settings,
)

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    "setup_logging_for_environment",
    "TemporaryLogLevel",
    "LOGGING_CONFIGS",
    # Settings
    "ScriptRAGSettings",
    "DatabaseSettings",
    "LLMSettings",
    "LoggingSettings",
    "MCPSettings",
    "PerformanceSettings",
    "PathSettings",
    "get_settings",
    "load_settings",
    "reset_settings",
    "create_default_config",
]
