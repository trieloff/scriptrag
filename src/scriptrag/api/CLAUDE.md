# ScriptRAG API Layer

This directory contains the public API surface for ScriptRAG operations. It provides a unified interface used by both the CLI and MCP server.

## Architecture Role

The API layer is the single entry point for all ScriptRAG operations. It enforces validation, access control, and provides a consistent interface regardless of the client (CLI, MCP, or programmatic).

## IMPORTANT: File Organization

**EACH API OPERATION MUST BE IN A SEPARATE FILE**

This ensures:

- Clear separation of concerns
- Easy testing of individual operations
- Manageable file sizes for MCP tools
- Clear import paths

## Directory Structure

```text
api/
├── __init__.py          # Public API exports
├── base.py             # Base API class and shared utilities
├── script/             # Script management operations
│   ├── __init__.py
│   ├── import_script.py
│   ├── list_scripts.py
│   └── get_script.py
├── scene/              # Scene operations
│   ├── __init__.py
│   ├── list_scenes.py
│   ├── get_scene.py
│   └── reprocess_scene.py
├── search/             # Search operations
│   ├── __init__.py
│   ├── search_dialogue.py
│   ├── search_by_character.py
│   └── semantic_search.py
├── character/          # Character management
│   ├── __init__.py
│   ├── list_characters.py
│   ├── get_character.py
│   └── update_bible.py
├── series/             # Series management
│   ├── __init__.py
│   ├── create_series.py
│   └── list_series.py
└── agent/              # Insight agent operations
    ├── __init__.py
    ├── list_agents.py
    └── run_agent.py
```


## Key Patterns

### 1. Input Validation

Use decorators to handle common validation patterns across API operations.

### 2. Error Handling

Convert internal exceptions to appropriate ScriptRAG error types with proper error chaining.

### 3. Dependency Injection

Use optional dependency injection for testability and flexibility.

### 4. Result Types

Use explicit result types from models for type safety and clear interfaces.

## Testing

Each operation should have a corresponding test file:

- `test_import_script.py`
- `test_search_dialogue.py`
- etc.

## Integration Points

The API layer integrates with:

- **Storage Layer**: For data persistence
- **Parser**: For Fountain file processing
- **Extractor**: For content analysis
- **Query Engine**: For search operations
- **Synchronizer**: For Git operations

## Security Considerations

1. **Path Validation**: Always validate file paths are within project
2. **Input Sanitization**: Clean all user inputs
3. **Rate Limiting**: Consider for expensive operations
4. **Audit Logging**: Log all operations with context

## Performance

1. **Lazy Loading**: Don't load data until needed
2. **Caching**: Use storage layer caching
3. **Batch Operations**: Support bulk operations where sensible
4. **Async Support**: Consider async variants for I/O heavy operations
