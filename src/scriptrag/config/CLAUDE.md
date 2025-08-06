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



## Configuration File Format

Configuration files use YAML format with hierarchical settings for LLM providers, storage options, processing preferences, and project-specific configurations.

## Environment Variables

All settings can be overridden with environment variables using the SCRIPTRAG_ prefix, with nested values using double underscores.




## Testing Configuration

Configuration loading and validation should be thoroughly tested with various file hierarchies and environment variable overrides.
