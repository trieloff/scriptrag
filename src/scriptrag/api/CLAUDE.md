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

## Implementation Pattern

Each operation file should follow this pattern:

```python
"""Operation: import_script - Import a Fountain screenplay into ScriptRAG."""

from pathlib import Path
from typing import Optional

from ..base import BaseAPI, api_operation
from ...models import Script, ScriptID
from ...parser import FountainParser
from ...storage import StorageManager


class ImportScriptAPI(BaseAPI):
    """Import script operation."""

    @api_operation
    def execute(
        self,
        fountain_path: Path,
        series_id: Optional[str] = None
    ) -> ScriptID:
        """Import a Fountain screenplay.

        Args:
            fountain_path: Path to the fountain file
            series_id: Optional series to associate with

        Returns:
            ScriptID of the imported script

        Raises:
            FileNotFoundError: If fountain file doesn't exist
            ParsingError: If fountain file is invalid
            StorageError: If storage operation fails
        """
        # Implementation here
        pass
```

## Key Patterns

### 1. Input Validation

```python
@api_operation  # Decorator handles common validation
def execute(self, path: Path) -> Result:
    # Path validation handled by decorator
    # Business logic here
```

### 2. Error Handling

```python
from ...exceptions import ScriptRAGError, ParsingError

try:
    result = self.parser.parse(path)
except FountainParseError as e:
    raise ParsingError(f"Failed to parse {path}: {e}") from e
```

### 3. Dependency Injection

```python
class SearchAPI(BaseAPI):
    def __init__(self, storage: Optional[StorageManager] = None):
        super().__init__()
        self.storage = storage or StorageManager()
```

### 4. Result Types

Use explicit result types from models:

```python
from ...models import (
    ScriptID,
    Scene,
    SearchResult,
    Character
)
```

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
