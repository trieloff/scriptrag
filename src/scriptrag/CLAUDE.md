# ScriptRAG Core Module

This is the root module for ScriptRAG v2, implementing a Git-native screenplay analysis system using GraphRAG patterns.

## Architecture Role

The scriptrag module serves as the main package that orchestrates all components in the system. It follows the architecture defined in `/root/repo/ARCHITECTURE.md`.

## Key Components

- **API/**: Public API surface (used by CLI and MCP)
- **cli/**: Command-line interface implementation
- **MCP/**: Model Context Protocol server
- **parser/**: Fountain file parsing (Actor in FMC)
- **extractor/**: Content extraction with LLM (Actor in FMC)
- **embeddings/**: Vector embedding generation (Actor in FMC)
- **synchronizer/**: Git operations and hooks (Actor in FMC)
- **indexer/**: Database indexing (Actor in FMC)
- **query/**: Query engine for search (Actor in FMC)
- **storage/**: Storage layer implementations (Places in FMC)
- **agents/**: Insight agents for extensible extraction
- **config/**: Configuration management
- **models/**: Data models and types
- **utils/**: Shared utilities

## Development Guidelines

1. **Follow FMC Patterns**: Actors perform actions, Places store data
2. **Use Channels**: Actors communicate through channels, not directly
3. **Respect Read/Write**: Actor → Place = write, Place → Actor = read
4. **Type Everything**: Full type annotations required
5. **Test Coverage**: Maintain >80% coverage

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

1. Environment variables (scriptrag_*)
2. User config file (~/.scriptrag/config.YAML)
3. Project config file (.scriptrag/config.YAML)
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
