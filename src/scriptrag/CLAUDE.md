# ScriptRAG Core Module

This is the root module for ScriptRAG v2, implementing a Git-native screenplay analysis system using GraphRAG patterns.

## Architecture Role

The scriptrag module serves as the main package that orchestrates all components in the system. It follows the [architecture](../../ARCHITECTURE.md) defined for the project.

## Key Components

- `api/`: Public API surface (used by CLI and MCP)
  - `analyze.py`: Scene analysis with insight agents and embeddings
  - `index.py`: Script indexing with character extraction
  - `database_operations.py`: Core database operations
- `cli/`: Command-line interface implementation
- `mcp/`: Model Context Protocol server
- `parser/`: Fountain file parsing
- `analyzers/`: Content analyzers including embedding generation
- `query/`: Query engine for search
- `search/`: Search engine with vector similarity
- `storage/`: Storage layer implementations
- `agents/`: Insight agents for extensible extraction
- `config/`: Configuration management
- `models/`: Data models and types
- `llm/`: LLM client and provider implementations
- `utils/`: Shared utilities

## Development Guidelines

1. **Type Everything**: Full type annotations required
2. **Test Coverage**: Maintain >80% coverage
3. **Modular Design**: Each component has a single responsibility
4. **Error Handling**: Use specific exception types
5. **Logging**: Use structured logging throughout

## Import Structure

```python
# Public API imports
from scriptrag import ScriptRAG
from scriptrag.models import Scene, Script, Character

# Internal imports use relative paths
from .parser import FountainParser
from .storage.database import DatabaseStorage
```

## Configuration

The system uses a hierarchical configuration system:

1. Environment variables (`scriptrag_*`)
2. User config file (`~/.scriptrag/config.yaml`)
3. Project config file (`.scriptrag/config.yaml`)
4. Default values

## Error Handling

All exceptions inherit from `ScriptRAGError` base class:

- `ParsingError`: Fountain parsing failures
- `ExtractionError`: LLM extraction issues
- `StorageError`: Database/file system problems
- `ConfigurationError`: Invalid configuration

## Logging

Use structured logging with the project logger:

```python
from scriptrag.config import get_logger
logger = get_logger(__name__)
```
