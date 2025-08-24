# ScriptRAG Configuration Guide

This guide provides comprehensive documentation for configuring ScriptRAG, including naming conventions, configuration sources, and precedence rules.

## Table of Contents

1. [Configuration Sources](#configuration-sources)
2. [Precedence Order](#precedence-order)
3. [Naming Conventions](#naming-conventions)
4. [Configuration Options](#configuration-options)
5. [Environment Variables](#environment-variables)
6. [Configuration Files](#configuration-files)
7. [CLI Arguments](#cli-arguments)
8. [Examples](#examples)

## Configuration Sources

ScriptRAG supports multiple configuration sources to provide flexibility in different deployment scenarios:

1. **Default Values** - Built-in defaults in the code
2. **.env Files** - Environment variable files
3. **Environment Variables** - System environment variables
4. **Configuration Files** - YAML, TOML, or JSON files
5. **CLI Arguments** - Command-line parameters

## Precedence Order

Configuration values are loaded with the following precedence (highest to lowest):

1. **CLI Arguments** - Command-line parameters (e.g., `--db-path`)
2. **Configuration Files** - YAML/TOML/JSON files (later files override earlier)
3. **Environment Variables** - System environment variables
4. **.env File** - Environment variable file in current directory
5. **Default Values** - Built-in defaults

This means CLI arguments always win, followed by config files, then environment variables, and finally defaults.

## Naming Conventions

ScriptRAG follows consistent naming conventions across different configuration sources:

### Key Naming Rules

| Source | Format | Example |
|--------|--------|---------|
| **Python/Internal** | snake_case | `database_path` |
| **Environment Variables** | UPPER_SNAKE_CASE with prefix | `SCRIPTRAG_DATABASE_PATH` |
| **Config Files (YAML/TOML/JSON)** | snake_case | `database_path` |
| **CLI Arguments** | kebab-case | `--db-path` or `--database-path` |

### Important Notes

- **Python Settings**: Always use `snake_case` (e.g., `database_path`, `log_level`)
- **Environment Variables**: Always prefix with `SCRIPTRAG_` and use `UPPER_SNAKE_CASE`
- **Config Files**: Use `snake_case` to match Python settings
- **CLI Arguments**: Use hyphens (`-`) not underscores (`_`)

## Configuration Options

### Database Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `database_path` | Path | `./scriptrag.db` | Path to SQLite database file |
| `database_timeout` | float | `30.0` | Connection timeout in seconds |
| `database_wal_mode` | bool | `true` | Enable Write-Ahead Logging |
| `database_foreign_keys` | bool | `true` | Enable foreign key constraints |
| `database_journal_mode` | str | `WAL` | SQLite journal mode |
| `database_synchronous` | str | `NORMAL` | SQLite synchronous mode |
| `database_cache_size` | int | `-2000` | SQLite cache size (KB) |
| `database_temp_store` | str | `MEMORY` | SQLite temp store location |

### Application Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `app_name` | str | `scriptrag` | Application name |
| `metadata_scan_size` | int | `10240` | Bytes to scan for metadata |
| `debug` | bool | `false` | Enable debug mode |

### Logging Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `log_level` | str | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `log_format` | str | `console` | Output format - see below for details |
| `log_file` | Path | `null` | Optional log file path |
| `log_file_rotation` | str | `1 day` | Log rotation interval |
| `log_file_retention` | str | `7 days` | Log retention period |

#### Log Format Options

ScriptRAG supports three logging formats to suit different environments:

- **`console`** (default) - Human-readable output with colors, ideal for development
  - Colored output when connected to a terminal
  - Clear, easy-to-read format for debugging
  - Best for local development and interactive use

- **`json`** - Machine-readable JSON format, ideal for production
  - Each log entry as a JSON object
  - Perfect for log aggregation systems (ELK, Splunk, etc.)
  - Includes structured metadata for filtering and searching

- **`structured`** - Key-value pairs format, good for production debugging
  - Readable yet parseable format
  - Balance between human and machine readability
  - Useful when you need both visibility and structure

### Search Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `search_vector_threshold` | int | `10` | Word count for auto vector search |
| `search_vector_similarity_threshold` | float | `0.3` | Min similarity score |
| `search_vector_result_limit_factor` | float | `0.5` | Factor for vector results |
| `search_vector_min_results` | int | `5` | Min number of vector results |

### LLM Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `llm_provider` | str | `null` | LLM provider (claude_code/github_models/openai_compatible) |
| `llm_endpoint` | str | `null` | OpenAI-compatible API endpoint |
| `llm_api_key` | str | `null` | API key for endpoint |
| `llm_model` | str | `null` | Default completion model |
| `llm_embedding_model` | str | `null` | Default embedding model |
| `llm_embedding_dimensions` | int | `null` | Embedding vector dimensions |
| `llm_temperature` | float | `0.7` | Generation temperature |
| `llm_max_tokens` | int | `null` | Max tokens for completions |
| `llm_force_static_models` | bool | `false` | Use static model lists |
| `llm_model_cache_ttl` | int | `3600` | Model list cache TTL (seconds) |

### Bible Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `bible_embeddings_path` | str | `embeddings/bible` | Path for bible embeddings |
| `bible_max_file_size` | int | `10485760` | Max bible file size (bytes) |

## Environment Variables

All settings can be configured via environment variables by prefixing with `SCRIPTRAG_` and converting to uppercase:

```bash
# Database settings
export SCRIPTRAG_DATABASE_PATH=/path/to/database.db
export SCRIPTRAG_DATABASE_TIMEOUT=60.0
export SCRIPTRAG_DATABASE_WAL_MODE=true

# Logging settings
export SCRIPTRAG_LOG_LEVEL=DEBUG
export SCRIPTRAG_LOG_FORMAT=json
export SCRIPTRAG_LOG_FILE=/var/log/scriptrag.log

# LLM settings
export SCRIPTRAG_LLM_PROVIDER=github_models
export SCRIPTRAG_LLM_API_KEY=your-api-key
export SCRIPTRAG_LLM_ENDPOINT=https://api.example.com/v1
```

### Path Expansion

Environment variables in paths are automatically expanded:

```bash
export SCRIPTRAG_DATABASE_PATH=$HOME/data/scriptrag.db
export SCRIPTRAG_LOG_FILE=~/logs/scriptrag.log
```

## Configuration Files

ScriptRAG supports three configuration file formats. Example files are provided in the `examples/` directory:

- `examples/scriptrag.yaml.example` - YAML configuration example
- `examples/scriptrag.toml.example` - TOML configuration example
- `examples/.env.example` - Environment variables example

Copy and customize these examples for your needs:

### YAML Configuration (`scriptrag.yaml`)

```yaml
# Database configuration
database_path: /path/to/scriptrag.db
database_timeout: 60.0
database_wal_mode: true

# Logging configuration
log_level: INFO
log_format: console
log_file: /var/log/scriptrag.log

# LLM configuration
llm_provider: github_models
llm_api_key: your-api-key-here  # pragma: allowlist secret
llm_model: gpt-4
llm_temperature: 0.7

# Search configuration
search_vector_threshold: 10
search_vector_similarity_threshold: 0.3
```

### TOML Configuration (`scriptrag.toml`)

```toml
# Database configuration
database_path = "/path/to/scriptrag.db"
database_timeout = 60.0
database_wal_mode = true

# Logging configuration
log_level = "INFO"
log_format = "console"
log_file = "/var/log/scriptrag.log"

# LLM configuration
llm_provider = "github_models"
llm_api_key = "your-api-key-here"  # pragma: allowlist secret
llm_model = "gpt-4"
llm_temperature = 0.7
```

### JSON Configuration (`scriptrag.json`)

```json
{
  "database_path": "/path/to/scriptrag.db",
  "database_timeout": 60.0,
  "database_wal_mode": true,
  "log_level": "INFO",
  "log_format": "console",
  "log_file": "/var/log/scriptrag.log",
  "llm_provider": "github_models",
  "llm_api_key": "your-api-key-here",  // pragma: allowlist secret
  "llm_model": "gpt-4",
  "llm_temperature": 0.7
}
```

## CLI Arguments

CLI arguments use kebab-case and typically have short aliases:

```bash
# Database path
uv run scriptrag init --db-path /path/to/database.db
uv run scriptrag init -d /path/to/database.db

# Configuration file
uv run scriptrag pull --config scriptrag.yaml
uv run scriptrag pull -c scriptrag.yaml

# Force option
uv run scriptrag init --force
uv run scriptrag init -f
```

### Common CLI Options

| Long Option | Short | Description |
|-------------|-------|-------------|
| `--db-path` | `-d` | Database file path |
| `--config` | `-c` | Configuration file path |
| `--force` | `-f` | Force operation |
| `--verbose` | `-v` | Verbose output |
| `--dry-run` | `-n` | Preview without changes |

## Examples

### Example 1: Using Configuration File with CLI Override

```bash
# Create config file
cat > scriptrag.yaml << EOF
database_path: /default/path/scriptrag.db
log_level: INFO
EOF

# Override database path via CLI
uv run scriptrag init --config scriptrag.yaml --db-path /custom/path/db.db
# Result: Uses /custom/path/db.db (CLI wins)
```

### Example 2: Environment Variables with Config File

```bash
# Set environment variable
export SCRIPTRAG_LOG_LEVEL=DEBUG

# Create config file with different value
cat > scriptrag.yaml << EOF
log_level: INFO
EOF

# Use config file
uv run scriptrag pull --config scriptrag.yaml
# Result: Uses INFO (config file wins over env var)
```

### Example 3: Complete Configuration Setup

```bash
# 1. Create .env file for local development
cat > .env << EOF
SCRIPTRAG_DATABASE_PATH=./dev.db
SCRIPTRAG_LOG_LEVEL=DEBUG
EOF

# 2. Create production config
cat > prod.yaml << EOF
database_path: /var/lib/scriptrag/prod.db
log_level: WARNING
log_file: /var/log/scriptrag.log
llm_provider: github_models
llm_api_key: ${GITHUB_TOKEN}
EOF

# 3. Run with production config
uv run scriptrag pull --config prod.yaml /path/to/scripts
```

### Example 4: Multiple Configuration Files

```bash
# Base configuration
cat > base.yaml << EOF
database_timeout: 30.0
log_format: console
EOF

# Override for production
cat > prod.yaml << EOF
database_path: /prod/scriptrag.db
log_level: WARNING
EOF

# Load both (prod.yaml overrides base.yaml)
uv run scriptrag pull --config base.yaml --config prod.yaml
```

### Example 5: Logging Configuration

```bash
# Development setup with console logging
export SCRIPTRAG_LOG_FORMAT=console
export SCRIPTRAG_LOG_LEVEL=DEBUG
uv run scriptrag pull screenplay.fountain

# Production setup with JSON logging to file
cat > prod-config.yaml << EOF
log_format: json
log_level: INFO
log_file: /var/log/scriptrag/app.log
EOF
uv run scriptrag pull --config prod-config.yaml screenplay.fountain

# Docker container with structured logging
docker run -e SCRIPTRAG_LOG_FORMAT=structured \
           -e SCRIPTRAG_LOG_LEVEL=INFO \
           scriptrag:latest

# Quick debugging with verbose output
SCRIPTRAG_LOG_LEVEL=DEBUG SCRIPTRAG_LOG_FORMAT=console uv run scriptrag search "dialogue"
```

## Troubleshooting

### Common Issues

1. **Configuration not loading**: Check file format and syntax
2. **Environment variables ignored**: Ensure `SCRIPTRAG_` prefix
3. **CLI arguments not working**: Use hyphens, not underscores
4. **Path not found**: Use absolute paths or ensure relative paths are correct

### Debugging Configuration

To see which configuration is being used:

```bash
# Enable debug logging
export SCRIPTRAG_LOG_LEVEL=DEBUG

# Run command with verbose output
uv run scriptrag init --verbose
```

### Configuration Validation

ScriptRAG validates configuration on load and provides helpful error messages:

- Invalid value types
- Out-of-range values
- Missing required settings
- Unsupported file formats

## Best Practices

1. **Development**: Use `.env` files for local settings
2. **Production**: Use YAML/TOML config files with environment variable substitution
3. **Docker**: Use environment variables for container configuration
4. **CI/CD**: Use config files checked into version control
5. **Secrets**: Use environment variables for sensitive data (API keys)

## Migration Guide

If you're upgrading from an older version:

1. **Old format**: `db_path` → **New format**: `database_path`
2. **Old format**: `SCRIPTRAG_DB_PATH` → **New format**: `SCRIPTRAG_DATABASE_PATH`
3. **Old format**: Mixed naming → **New format**: Consistent snake_case

## See Also

- [Installation Guide](installation.md) - Initial setup and requirements
- [User Guide](user-guide.md) - Complete usage documentation
- [API Reference](api-reference.md) - Programmatic configuration
