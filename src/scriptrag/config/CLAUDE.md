# Configuration Management

This directory contains the configuration system for ScriptRAG, supporting hierarchical configuration with environment variables, config files, and defaults.

## Architecture Role

The configuration system provides:

- Centralized settings management
- Environment-specific overrides
- Validation and type safety
- Dynamic reloading capabilities

## Configuration Hierarchy

Settings are loaded in this order (later overrides earlier):

1. Default values (in code)
2. System config (`/etc/scriptrag/config.yaml`)
3. User config (`~/.scriptrag/config.yaml`)
4. Project config (`.scriptrag/config.yaml`)
5. Environment variables (`SCRIPTRAG_*`)
6. Command-line arguments

## Implementation

```python
from pydantic import BaseSettings, Field, validator
from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml
import os

class LLMConfig(BaseSettings):
    """LLM-related configuration."""
    provider: str = Field("auto", description="LLM provider (auto, openai, claude_sdk)")
    model: str = Field("gpt-4-turbo-preview", description="Model to use")
    api_key: Optional[str] = Field(None, description="API key")
    base_url: Optional[str] = Field(None, description="API base URL")
    temperature: float = Field(0.3, ge=0, le=2)
    max_retries: int = Field(3, ge=0)
    timeout: int = Field(30, ge=1)

    class Config:
        env_prefix = "SCRIPTRAG_LLM_"

class StorageConfig(BaseSettings):
    """Storage-related configuration."""
    database_path: Path = Field(".scriptrag/cache.db", description="SQLite database path")
    embeddings_dir: str = Field("embeddings", description="Embeddings directory")
    enable_lfs: bool = Field(True, description="Use Git LFS for embeddings")
    cache_size_mb: int = Field(100, ge=10)

    class Config:
        env_prefix = "SCRIPTRAG_STORAGE_"

class ScriptRAGConfig(BaseSettings):
    """Main configuration class."""
    # Sub-configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    # General settings
    debug: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")
    parallel_processing: bool = Field(True, description="Enable parallel processing")
    auto_process: bool = Field(True, description="Auto-process on commit")

    # Paths
    agents_dir: Path = Field("insight-agents", description="Custom agents directory")
    scripts_dir: Path = Field("scripts", description="Screenplay scripts directory")

    class Config:
        env_prefix = "SCRIPTRAG_"
        env_nested_delimiter = "__"  # SCRIPTRAG_LLM__MODEL
```

## Configuration Loading

```python
class ConfigManager:
    """Manage configuration loading and access."""

    def __init__(self):
        self._config: Optional[ScriptRAGConfig] = None
        self._config_files: List[Path] = []

    def load(self) -> ScriptRAGConfig:
        """Load configuration from all sources."""
        # Find config files
        config_files = self._find_config_files()

        # Load YAML configs
        config_data = {}
        for config_file in config_files:
            if config_file.exists():
                with open(config_file) as f:
                    data = yaml.safe_load(f) or {}
                    config_data = self._deep_merge(config_data, data)

        # Create config with environment overrides
        self._config = ScriptRAGConfig(**config_data)
        return self._config

    def _find_config_files(self) -> List[Path]:
        """Find all config files in hierarchy."""
        files = [
            Path("/etc/scriptrag/config.yaml"),
            Path.home() / ".scriptrag" / "config.yaml",
            Path.cwd() / ".scriptrag" / "config.yaml"
        ]
        return [f for f in files if f.exists()]

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
```

## Configuration File Format

```yaml
# .scriptrag/config.yaml example
debug: false
log_level: INFO

llm:
  provider: openai
  model: gpt-4-turbo-preview
  temperature: 0.3
  max_retries: 3

storage:
  database_path: .scriptrag/cache.db
  enable_lfs: true
  cache_size_mb: 200

agents_dir: ./insight-agents
scripts_dir: ./scripts

# Project-specific settings
project:
  series_id: breaking-bad
  auto_tag_characters: true

# Git hooks
hooks:
  pre_commit:
    enabled: true
    process_staged_only: true
  post_checkout:
    enabled: true
    full_reindex: false
```

## Environment Variables

All settings can be overridden with environment variables:

```bash
# Simple values
export SCRIPTRAG_DEBUG=true
export SCRIPTRAG_LOG_LEVEL=DEBUG

# Nested values use double underscore
export SCRIPTRAG_LLM__PROVIDER=claude_sdk
export SCRIPTRAG_LLM__MODEL=claude-3-opus
export SCRIPTRAG_STORAGE__DATABASE_PATH=/tmp/scriptrag.db
```

## Dynamic Configuration

```python
# Global config access
_config_manager = ConfigManager()
_config: Optional[ScriptRAGConfig] = None

def get_config() -> ScriptRAGConfig:
    """Get current configuration."""
    global _config
    if _config is None:
        _config = _config_manager.load()
    return _config

def reload_config() -> ScriptRAGConfig:
    """Reload configuration from disk."""
    global _config
    _config = _config_manager.load()
    return _config

def get_setting(path: str, default: Any = None) -> Any:
    """Get setting by dot-notation path."""
    config = get_config()

    # Navigate path
    value = config
    for part in path.split('.'):
        if hasattr(value, part):
            value = getattr(value, part)
        else:
            return default

    return value
```

## Validation

```python
class ConfigValidator:
    """Validate configuration values."""

    @staticmethod
    def validate_paths(config: ScriptRAGConfig) -> List[str]:
        """Validate all path settings."""
        errors = []

        # Check agents directory
        if not config.agents_dir.exists():
            errors.append(f"Agents directory not found: {config.agents_dir}")

        # Check database parent directory
        if not config.storage.database_path.parent.exists():
            errors.append(
                f"Database directory not found: {config.storage.database_path.parent}"
            )

        return errors

    @staticmethod  
    def validate_llm(config: ScriptRAGConfig) -> List[str]:
        """Validate LLM configuration."""
        errors = []

        if config.llm.provider == "openai" and not config.llm.api_key:
            if not os.environ.get("OPENAI_API_KEY"):
                errors.append("OpenAI API key not configured")

        return errors
```

## Usage in Components

```python
# In any component
from ..config import get_config, get_setting

class SomeComponent:
    def __init__(self):
        config = get_config()
        self.llm_model = config.llm.model
        self.debug = config.debug

        # Or use path notation
        self.retries = get_setting("llm.max_retries", default=3)
```

## Testing Configuration

```python
import pytest
from ..config import ScriptRAGConfig, ConfigManager

def test_config_loading(tmp_path):
    """Test configuration loading."""
    # Create test config
    config_file = tmp_path / ".scriptrag" / "config.yaml"
    config_file.parent.mkdir()
    config_file.write_text("""
    debug: true
    llm:
      provider: openai
      model: gpt-3.5-turbo
    """)

    # Load config
    os.chdir(tmp_path)
    config = ConfigManager().load()

    assert config.debug is True
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-3.5-turbo"
```
