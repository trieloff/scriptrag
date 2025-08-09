# ScriptRAG API Layer

This directory contains the public API surface for ScriptRAG operations. It provides a unified interface used by both the CLI and MCP server.

**Current Scale**: Contains complex modules including `database_operations.py` (536 lines) and `index.py` (518 lines) that handle sophisticated SQL and graph operations.

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

## Common Iteration Points (Lessons from Development)

### Database Operations Complexity

The `database_operations.py` module has grown to 536 lines due to:
- Complex SQL query construction with dynamic filters
- Graph operations using NetworkX for character relationships
- Transaction management for consistency
- Batch processing optimizations

**Best Practice**: Consider splitting into focused modules:
- Query builder module
- Graph operations module
- Transaction manager module

### Indexing Challenges

The `index.py` module (518 lines) handles:
- Scene content indexing
- Embedding generation and storage
- Git LFS integration for large vectors
- Incremental index updates

**Common Issues**:
- Memory usage with large scripts
- LFS tracking configuration
- Concurrent indexing conflicts

### SQL Query Patterns

```python
# GOOD - Parameterized queries prevent injection
def query_scenes(filters: dict) -> tuple[str, list]:
    query = "SELECT * FROM scenes WHERE 1=1"
    params = []

    if filters.get("act"):
        query += " AND act = ?"
        params.append(filters["act"])

    return query, params

# BAD - String concatenation vulnerable to injection
def query_scenes(filters: dict) -> str:
    query = f"SELECT * FROM scenes WHERE act = {filters['act']}"
    return query
```

### Graph Operations

```python
# Complex character relationship graphs require careful management
import networkx as nx

class CharacterGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_interaction(self, char_a: str, char_b: str, scene: str):
        # Weight increases with more interactions
        if self.graph.has_edge(char_a, char_b):
            self.graph[char_a][char_b]["weight"] += 1
            self.graph[char_a][char_b]["scenes"].append(scene)
        else:
            self.graph.add_edge(char_a, char_b, weight=1, scenes=[scene])
```

### Transaction Management

```python
from contextlib import contextmanager

@contextmanager
def atomic_operation(conn):
    """Ensure all-or-nothing operations."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### Embedding Storage with Git LFS

```python
# Automatically configure Git LFS for embeddings
def setup_lfs_tracking(embedding_dir: Path):
    gitattributes = embedding_dir.parent / ".gitattributes"
    pattern = f"{embedding_dir.name}/*.npy filter=lfs diff=lfs merge=lfs -text"

    if not gitattributes.exists() or pattern not in gitattributes.read_text():
        with open(gitattributes, "a") as f:
            f.write(f"\n{pattern}\n")
```

## Refactoring Recommendations

Based on current file sizes and complexity:

1. **Split `database_operations.py`**:
   - `query_builder.py` - SQL query construction
   - `graph_ops.py` - NetworkX operations
   - `db_utils.py` - Connection and transaction management

2. **Split `index.py`**:
   - `content_indexer.py` - Text indexing
   - `embedding_manager.py` - Vector storage
   - `index_utils.py` - Common utilities

3. **Extract Common Patterns**:
   - Create `api/patterns.py` for reusable patterns
   - Move validation decorators to `api/validators.py`
   - Extract error handling to `api/errors.py`
