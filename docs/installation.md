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

## Running Without Installation

ScriptRAG can be run directly without cloning the repository using `uvx`, a tool that comes with `uv` for running Python applications in isolated environments.

### What is uvx?

`uvx` is a command-line tool that:

- Creates temporary, isolated Python environments
- Installs packages and their dependencies on-the-fly
- Runs Python applications without permanent installation
- Caches packages for faster subsequent runs

### When to Use uvx

Use `uvx` when you want to:

- **Quick testing**: Try ScriptRAG without committing to a full installation
- **CI/CD pipelines**: Run ScriptRAG in automated workflows without setup overhead
- **Cross-project usage**: Use ScriptRAG from any directory without switching environments
- **Temporary environments**: Run ScriptRAG in Docker containers or ephemeral systems
- **One-off commands**: Execute single ScriptRAG commands without maintaining a local installation

### Command Syntax

The full syntax for running ScriptRAG with uvx is:

```bash
uvx --from git+https://github.com/trieloff/scriptrag scriptrag [COMMAND] [OPTIONS]
```

### Common Examples

```bash
# Display help and available commands
uvx --from git+https://github.com/trieloff/scriptrag scriptrag --help

# Initialize a new ScriptRAG database
uvx --from git+https://github.com/trieloff/scriptrag scriptrag init

# Index a single screenplay
uvx --from git+https://github.com/trieloff/scriptrag scriptrag index screenplay.fountain

# Complete pull workflow (analyze + index) - recommended
uvx --from git+https://github.com/trieloff/scriptrag scriptrag pull screenplay.fountain

# Search across indexed screenplays
uvx --from git+https://github.com/trieloff/scriptrag scriptrag search "coffee shop"

# Search with character filter
uvx --from git+https://github.com/trieloff/scriptrag scriptrag search --character JANE "morning routine"

# List available scripts
uvx --from git+https://github.com/trieloff/scriptrag scriptrag list

# Read specific scenes
uvx --from git+https://github.com/trieloff/scriptrag scriptrag scene read --project "My Script" --scene 1

# Watch directory for changes (long-running)
uvx --from git+https://github.com/trieloff/scriptrag scriptrag watch /path/to/screenplays/
```

### Using with Configuration Files

You can use configuration files with uvx:

```bash
# Using a configuration file
uvx --from git+https://github.com/trieloff/scriptrag scriptrag pull --config scriptrag.yaml screenplay.fountain

# Using environment variables
export SCRIPTRAG_DATABASE_PATH=/path/to/scriptrag.db
uvx --from git+https://github.com/trieloff/scriptrag scriptrag list
```

### Performance Considerations

- **First run**: Initial execution will be slower as uvx downloads and caches ScriptRAG and its dependencies
- **Subsequent runs**: Cached packages make later runs much faster (though still slower than local installation)
- **Network dependency**: Requires internet connection for first run and periodic cache updates
- **Disk usage**: uvx maintains a cache directory (typically in `~/.cache/uv`)

### Known Issues

- **Verbose logging**: The current version may show more detailed logs than necessary when run via uvx. This is a known issue that will be addressed in a future update.

### uvx vs. Full Installation

| Aspect | uvx | Full Installation |
|--------|-----|-------------------|
| **Setup time** | None (immediate) | 2-5 minutes |
| **First run speed** | Slower (downloads packages) | Fast |
| **Subsequent runs** | Moderate (cached) | Fast |
| **Disk usage** | Minimal (shared cache) | ~200MB per installation |
| **Update process** | Automatic (always latest) | Manual (`git pull && uv sync`) |
| **Development** | Not suitable | Full capabilities |
| **Best for** | Quick tests, CI/CD, one-off usage | Regular use, development |

### Recommendation

- **Use uvx for**: Quick testing, CI/CD pipelines, occasional use, trying ScriptRAG before committing
- **Use full installation for**: Regular use, development, performance-critical workflows, offline usage

## Configuration

ScriptRAG can be configured through multiple sources including environment variables, configuration files, and CLI arguments. See the [Configuration Guide](configuration.md) for detailed information on:

- Configuration file formats (YAML, TOML, JSON)
- Environment variable naming conventions
- CLI argument formats
- Precedence order of configuration sources
