# Installation

## Requirements

- Python 3.11 or higher
- SQLite 3.38 or higher (for vector support)
- uv package manager

## Why uv?

ScriptRAG uses [uv](https://github.com/astral-sh/uv) as its package manager for several key benefits:

- **Automatic Virtual Environment Management**: uv handles virtual environment creation and activation automatically
- **Faster Dependency Resolution**: Significantly faster than pip for installing and resolving dependencies
- **Reproducible Builds**: Ensures consistent dependency versions across all environments
- **Simplified Commands**: No need to manually activate virtual environments before running commands

## Install uv

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install from Source

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
uv sync
```

## Development Installation

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
uv sync --dev
```

## Verify Installation

```bash
uv run scriptrag --version
```

## Configuration

ScriptRAG can be configured through multiple sources including environment variables, configuration files, and CLI arguments. See the [Configuration Guide](configuration.md) for detailed information on:

- Configuration file formats (YAML, TOML, JSON)
- Environment variable naming conventions
- CLI argument formats
- Precedence order of configuration sources
