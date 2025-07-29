# ScriptRAG

ScriptRAG is a semantic graph for screenplay analysis and querying using GraphRAG
(Graph Retrieval-Augmented Generation).

## Overview

ScriptRAG builds a knowledge graph from screenplay data, enabling advanced analysis
and querying capabilities for screenwriters, script analysts, and production teams.

## Features

- **Fountain Format Support**: Parse and analyze industry-standard Fountain screenplays
- **GraphRAG Architecture**: Combine graph databases with retrieval-augmented generation
- **Semantic Analysis**: Extract character relationships, plot structures, and thematic elements
- **Advanced Querying**: Natural language queries over screenplay data
- **Production Ready**: Comprehensive testing, logging, and configuration management

## Quick Start

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install ScriptRAG
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
uv sync

# Initialize a new project
uv run scriptrag init my-project

# Parse a screenplay
uv run scriptrag parse screenplay.fountain

# Query the graph
uv run scriptrag query "What are the main character relationships?"
```

## Documentation

- [Installation Guide](installation.md)
- [Usage Examples](usage.md)
- [API Reference](API.md)
- [Development Setup](development.md)

## License

MIT License - see LICENSE file for details.
EOF < /dev/null
