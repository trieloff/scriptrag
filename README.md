# ScriptRAG: A Graph-Based Screenwriting Assistant

[![97% Vibe_Coded](https://img.shields.io/badge/97%25-Vibe_Coded-ff69b4?style=for-the-badge&logo=claude&logoColor=white)](https://github.com/trieloff/vibe-coded-badge-action)

ScriptRAG is a novel screenwriting tool that combines Fountain parsing, graph databases, and local LLMs
to create an intelligent screenplay assistant using the GraphRAG (Graph + Retrieval-Augmented
Generation) pattern.

## ✨ Features

- **📝 Fountain Format Support**: Parse and analyze industry-standard screenplay files
- **🔍 Intelligent Search**: Search by character, dialogue, scene descriptions, or semantic similarity
- **📊 Script Analysis**: Automatic extraction of characters, scenes, dialogue, and metadata
- **📺 TV Series Support**: Handle multi-episode series with season/episode organization
- **🤖 AI Integration**: MCP server for integration with Claude Desktop and other AI assistants
- **⚡ Real-time Monitoring**: Watch directories for changes and auto-index new scripts
- **🎭 Scene Management**: Read, add, update, and delete scenes with automatic renumbering
- **📈 Analytics**: Character statistics, dialogue analysis, and scene queries

## 📚 Documentation

### For Users

- **[Installation Guide](docs/installation.md)** - Get ScriptRAG up and running
- **[User Guide](docs/user-guide.md)** - Complete guide for screenwriters
- **[Usage Examples](docs/usage.md)** - Common workflows and examples
- **[Bulk Import Guide](docs/bulk_import_guide.md)** - Import multiple screenplays
- **[MCP Usage Examples](examples/mcp_usage_examples.md)** - Using with AI assistants

### For Developers

- **[Developer Guide](docs/developer-guide.md)** - Contributing to ScriptRAG
- **[Testing Best Practices](docs/TESTING.md)** - Comprehensive testing guidelines for cross-platform reliability
- **[Architecture Overview](docs/architecture.md)** - System design and patterns
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[MCP Server Documentation](docs/mcp_server.md)** - Model Context Protocol integration
- **[AI Agent Guidelines](AGENTS.md)** - Guidelines for AI contributors
- **[Claude Coding Guidelines](CLAUDE.md)** - Coding standards and workflows

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- uv package manager (will be installed if not present)
- SQLite 3.38+ (for vector support)
- Optional: LLM provider for advanced analysis features
  - LMStudio running at <http://localhost:1234>
  - Or GitHub Models API token
  - Or OpenAI-compatible endpoint

### Installation

```bash
# Clone the repository
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up development environment
make setup-dev

# Initialize the database
make db-init

# Activate the virtual environment
source .venv/bin/activate
```

### Try Without Installing

You can use ScriptRAG directly without cloning the repository using `uvx`:

```bash
# Run ScriptRAG directly from GitHub
uvx --from git+https://github.com/trieloff/scriptrag scriptrag --help

# Initialize database (first time only)
uvx --from git+https://github.com/trieloff/scriptrag scriptrag init

# Index a screenplay
uvx --from git+https://github.com/trieloff/scriptrag scriptrag index screenplay.fountain

# Complete pull workflow (analyze + index)
uvx --from git+https://github.com/trieloff/scriptrag scriptrag pull screenplay.fountain

# Search for scenes
uvx --from git+https://github.com/trieloff/scriptrag scriptrag search "coffee shop"
```

This approach is ideal for:

- Quick testing without commitment
- Using ScriptRAG in CI/CD pipelines  
- Running from other project directories
- Temporary environments

For regular use, a full installation is recommended for better performance.

### Basic Usage

```bash
# Initialize the database (first time only)
uv run scriptrag init

# Quick start - Pull screenplay files into database (analyze + index)
# This is the recommended workflow for importing screenplays
uv run scriptrag pull path/to/screenplay.fountain

# List available Fountain files
uv run scriptrag list

# Search for scenes
uv run scriptrag search "coffee shop"

# Search with character filter
uv run scriptrag search --character SARAH "important dialogue"

# Read specific scenes
uv run scriptrag scene read --project "Script Title" --scene 1

# Watch for changes and auto-import
uv run scriptrag watch path/to/screenplays/

# Start the MCP server for AI integration
uv run scriptrag mcp
```

#### Configuration

Create a `scriptrag.yaml` configuration file:

```yaml
database_path: /path/to/your/scriptrag.db
log_level: INFO
```

Then use it with commands that support configuration:

```bash
uv run scriptrag pull --config scriptrag.yaml path/to/screenplay.fountain
```

Or use environment variables:

```bash
export SCRIPTRAG_DATABASE_PATH=/path/to/your/scriptrag.db
uv run scriptrag scene read --project "My Script" --scene 1
```

See the [Configuration Guide](docs/configuration.md) for complete documentation on configuration options, naming conventions, and precedence rules.

See the [User Guide](docs/user-guide.md) for complete documentation.

### Complete Workflow Example

Here's a full example of importing and working with a screenplay:

```bash
# 1. Create a Fountain screenplay file
cat > my_script.fountain << 'EOF'
Title: My Amazing Script
Author: Your Name

INT. COFFEE SHOP - DAY

JANE (30s) sits alone at a corner table, laptop open.

JANE
(to herself)
This is where the magic happens.

A WAITER approaches.

WAITER
Your usual?

JANE
(smiling)
You know it.

EOF

# 2. Initialize database and import the screenplay
uv run scriptrag init
uv run scriptrag pull my_script.fountain

# 3. Read specific scenes
uv run scriptrag scene read --project "My Amazing Script" --scene 1

# 4. View available queries
uv run scriptrag query list

# 5. List all scenes
uv run scriptrag query simple_scene_list

# 6. Scene management (requires session tokens)
# Read a scene and get a session token
uv run scriptrag scene read --project "My Amazing Script" --scene 1
# Use the token to update the scene (within 10 minutes)
# uv run scriptrag scene update --token <session-token> "Updated scene content"
```

### Command Reference

| Command | Description | Working Status |
|---------|-------------|----------------|
| `init` | Initialize database | ✅ Working |
| `list` | List Fountain files | ✅ Working |
| `analyze` | Add metadata to scripts | ✅ Working |
| `index` | Import scripts to database | ✅ Working |
| `pull` | Complete import workflow | ✅ Working |
| `scene read` | Read scenes from database | ✅ Working |
| `scene add/update/delete` | Manage scenes | ✅ Working |
| `watch` | Auto-import on changes | ✅ Working |
| `mcp` | Start MCP server | ✅ Working |
| `search` | Search scripts | ✅ Working |
| `query` | Run SQL queries | ✅ Working |

## 🧪 Development & Testing

### Quick Validation

Use the canary test target for rapid validation before pushing changes:

```bash
# Run canary tests (< 30 seconds) - mimics CI's quick validation
make test-canary

# Run fast checks + canary tests (recommended before push)
make check-canary
```

The canary tests:

- Skip integration, slow, and LLM tests
- Fail fast on first error
- Limit to 10 failures maximum
- Timeout tests after 15 seconds
- Complete in under 30 seconds

### Complete Testing

```bash
# Run full test suite with coverage
make test

# Run specific test types
make test-unit         # Unit tests only
make test-integration  # Integration tests
make test-llm         # LLM tests (requires SCRIPTRAG_TEST_LLMS=1)

# Quick tests without coverage
make test-fast

# Run all quality checks (lint, type-check, security, tests)
make check
```

See [Testing Best Practices](docs/TESTING.md) for comprehensive testing guidelines.

## Tech Stack

- **Language**: Python with uv package manager
- **Database**: SQLite as a graph database
- **LLM**: Local LLMs via LMStudio (OpenAI-compatible API)
- **Parser**: Fountain screenplay format parser
- **Pattern**: GraphRAG (Graph + Retrieval-Augmented Generation)
- **Interface**: MCP (Model Context Protocol) server

## Building and Packaging

### Package Distribution

ScriptRAG is distributed as a Python wheel and source distribution. The packages are optimized for size by excluding development files:

#### Building Packages

```bash
# Install build dependencies
make setup-dev

# Build wheel and source distribution
uv run python -m build

# Verify package contents
unzip -l dist/*.whl  # Check wheel contents
tar -tzf dist/*.tar.gz  # Check source distribution
```

#### What's Included

The distribution packages include:

- All runtime Python code (`src/scriptrag/`)
- SQL schema files for database initialization
- README and LICENSE files
- Required metadata and configuration

The following are excluded to reduce package size:

- Development documentation (CLAUDE.md files, architecture docs)
- Test files and fixtures
- Development tools and scripts
- Examples and notebooks
- CI/CD configuration

## Contributing

Contributions are welcome! Please see our [Developer Guide](docs/developer-guide.md) and [AI Agent Guidelines](AGENTS.md) for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- [Fountain Format](https://fountain.io/)
- [GraphRAG with SQLite Example](https://deepwiki.com/stephenc222/example-graphrag-with-sqlite/1-overview)
- [LMStudio](https://lmstudio.ai/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
