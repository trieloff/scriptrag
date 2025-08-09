# ScriptRAG: A Graph-Based Screenwriting Assistant

[![94% Vibe_Coded](https://img.shields.io/badge/94%25-Vibe_Coded-ff69b4?style=for-the-badge&logo=claude&logoColor=white)](https://github.com/trieloff/vibe-coded-badge-action)

ScriptRAG is a novel screenwriting tool that combines Fountain parsing, graph databases, and local LLMs
to create an intelligent screenplay assistant using the GraphRAG (Graph + Retrieval-Augmented
Generation) pattern.

## 📚 Documentation

### For Users

- **[Installation Guide](docs/installation.md)** - Get ScriptRAG up and running
- **[User Guide](docs/user-guide.md)** - Complete guide for screenwriters
- **[Usage Examples](docs/usage.md)** - Common workflows and examples
- **[Bulk Import Guide](docs/bulk_import_guide.md)** - Import multiple screenplays
- **[MCP Usage Examples](examples/mcp_usage_examples.md)** - Using with AI assistants

### For Developers

- **[Developer Guide](docs/developer-guide.md)** - Contributing to ScriptRAG
- **[Architecture Overview](docs/architecture.md)** - System design and patterns
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[MCP Server Documentation](docs/mcp_server.md)** - Model Context Protocol integration
- **[AI Agent Guidelines](AGENTS.md)** - Guidelines for AI contributors
- **[Claude Coding Guidelines](CLAUDE.md)** - Coding standards and workflows

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- uv package manager
- SQLite 3.38+ (for vector support)
- LMStudio running at <http://localhost:1234>

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

### Basic Usage

```bash
# Parse a screenplay
scriptrag script import path/to/screenplay.fountain

# Search for scenes
scriptrag scene search "coffee shop"

# Start the MCP server
scriptrag mcp start
```

See the [User Guide](docs/user-guide.md) for complete documentation.

## Tech Stack

- **Language**: Python with uv package manager
- **Database**: SQLite as a graph database
- **LLM**: Local LLMs via LMStudio (OpenAI-compatible API)
- **Parser**: Fountain screenplay format parser
- **Pattern**: GraphRAG (Graph + Retrieval-Augmented Generation)
- **Interface**: MCP (Model Context Protocol) server

## Contributing

Contributions are welcome! Please see our [Developer Guide](docs/developer-guide.md) and [AI Agent Guidelines](AGENTS.md) for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- [Fountain Format](https://fountain.io/)
- [GraphRAG with SQLite Example](https://deepwiki.com/stephenc222/example-graphrag-with-sqlite/1-overview)
- [LMStudio](https://lmstudio.ai/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
