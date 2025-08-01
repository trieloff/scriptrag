# ScriptRAG MCP Server Implementation

This directory contains the Model Context Protocol (MCP) server implementation. Each tool should be in a separate file for clarity and maintainability.

## Architecture Role

The MCP server is one of the two main user interfaces (along with CLI). It exposes ScriptRAG functionality as MCP tools and resources that can be used by AI assistants like Claude.

## IMPORTANT: File Organization

**EACH MCP TOOL MUST BE IN A SEPARATE FILE**

Structure:

```text
mcp/
├── __init__.py              # MCP server initialization
├── server.py               # Main server setup and registration
├── tools/                  # MCP tool implementations
│   ├── __init__.py
│   ├── import_script.py
│   ├── list_scripts.py
│   ├── get_script.py
│   ├── list_scenes.py
│   ├── get_scene.py
│   ├── reprocess_scene.py
│   ├── search_dialogue.py
│   ├── search_character.py
│   ├── semantic_search.py
│   ├── list_characters.py
│   ├── get_character.py
│   ├── update_bible.py
│   ├── create_series.py
│   ├── list_series.py
│   ├── list_agents.py
│   └── run_agent.py
├── resources/              # MCP resource implementations
│   ├── __init__.py
│   ├── series.py          # Series information resources
│   ├── character.py       # Character bible resources
│   └── script.py          # Script content resources
└── utils.py               # Shared MCP utilities
```

## Implementation Pattern

Each tool file should follow this pattern:

```python
"""MCP tool: import_script - Import a Fountain screenplay into ScriptRAG."""

from pathlib import Path
from typing import Dict, Any, Optional

from mcp.types import Tool, ToolResult
from ..api import ScriptRAGAPI
from ..exceptions import ScriptRAGError


def create_tool() -> Tool:
    """Create the import_script tool definition."""
    return Tool(
        name="scriptrag_import_script",
        description="Import a Fountain screenplay into ScriptRAG",
        inputSchema={
            "type": "object",
            "properties": {
                "fountain_path": {
                    "type": "string",
                    "description": "Path to the Fountain file to import"
                },
                "series_id": {
                    "type": "string",
                    "description": "Optional series ID to associate with",
                    "default": None
                }
            },
            "required": ["fountain_path"]
        }
    )


async def execute(arguments: Dict[str, Any]) -> ToolResult:
    """Execute the import_script tool.

    Args:
        arguments: Tool arguments from MCP client

    Returns:
        ToolResult with success/error information
    """
    try:
        fountain_path = Path(arguments["fountain_path"])
        series_id = arguments.get("series_id")

        # Validate path
        if not fountain_path.exists():
            return ToolResult(
                isError=True,
                content=[{
                    "type": "text",
                    "text": f"File not found: {fountain_path}"
                }]
            )

        # Execute API operation
        api = ScriptRAGAPI()
        script_id = api.import_script(fountain_path, series_id=series_id)

        return ToolResult(
            content=[{
                "type": "text",
                "text": f"Successfully imported script: {script_id}"
            }]
        )

    except ScriptRAGError as e:
        return ToolResult(
            isError=True,
            content=[{
                "type": "text",
                "text": f"ScriptRAG error: {str(e)}"
            }]
        )
    except Exception as e:
        return ToolResult(
            isError=True,
            content=[{
                "type": "text",
                "text": f"Unexpected error: {str(e)}"
            }]
        )
```

## Resource Implementation Pattern

```python
"""MCP resource: Character bible resource provider."""

from typing import List
from urllib.parse import urlparse

from mcp.types import Resource
from ..api import ScriptRAGAPI


def list_resources() -> List[Resource]:
    """List available character bible resources."""
    api = ScriptRAGAPI()
    resources = []

    for series in api.list_series():
        for character in api.list_characters(series.id):
            if character.bible_path:
                resources.append(Resource(
                    uri=f"scriptrag://character/{character.id}",
                    name=f"{character.name} - Character Bible",
                    description=f"Character bible for {character.name} in {series.title}",
                    mimeType="text/markdown"
                ))

    return resources


async def read_resource(uri: str) -> str:
    """Read a character bible resource."""
    parsed = urlparse(uri)
    if parsed.scheme != "scriptrag" or parsed.netloc != "character":
        raise ValueError(f"Invalid resource URI: {uri}")

    character_id = parsed.path.lstrip("/")
    api = ScriptRAGAPI()
    character = api.get_character(character_id)

    if not character.bible_path:
        raise ValueError(f"No bible found for character: {character_id}")

    return character.bible_content
```

## Key Patterns

### 1. Tool Naming Convention

All tools must be prefixed with `scriptrag_`:

- `scriptrag_import_script`
- `scriptrag_search_dialogue`
- `scriptrag_list_characters`

### 2. Schema Validation

Use JSON Schema for input validation:

```python
"inputSchema": {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query",
            "minLength": 1,
            "maxLength": 500
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results",
            "minimum": 1,
            "maximum": 100,
            "default": 10
        }
    },
    "required": ["query"]
}
```

### 3. Error Handling

Always return proper MCP errors:

```python
# Don't raise exceptions, return error results
return ToolResult(
    isError=True,
    content=[{
        "type": "text",
        "text": f"Error: {str(e)}"
    }]
)
```

### 4. Content Types

MCP supports multiple content types:

```python
# Text content
content=[{"type": "text", "text": "Result text"}]

# Image content (for diagrams)
content=[{"type": "image", "data": base64_data, "mimeType": "image/png"}]

# Mixed content
content=[
    {"type": "text", "text": "Found scene:"},
    {"type": "text", "text": scene_content}
]
```

## Server Configuration

The main server file assembles all tools:

```python
from mcp import Server
from .tools import (
    import_script,
    search_dialogue,
    # ... all other tools
)
from .resources import (
    character_resources,
    script_resources,
    # ... all other resources  
)

def create_server() -> Server:
    server = Server("scriptrag", "1.0.0")

    # Register all tools
    for tool_module in [import_script, search_dialogue, ...]:
        server.add_tool(
            tool_module.create_tool(),
            tool_module.execute
        )

    # Register resources
    server.add_resources(character_resources.list_resources)

    return server
```

## Testing

Each tool should have comprehensive tests:

```python
import pytest
from ..tools.import_script import create_tool, execute

@pytest.mark.asyncio
async def test_import_script_success():
    result = await execute({
        "fountain_path": "test.fountain"
    })
    assert not result.isError
    assert "Successfully imported" in result.content[0]["text"]
```

## Performance Considerations

1. **Async Operations**: All tool executions should be async
2. **Streaming**: For large results, consider streaming responses
3. **Caching**: Cache API client instances
4. **Timeout Handling**: Implement reasonable timeouts

## Security

1. **Path Validation**: Always validate file paths are safe
2. **Input Sanitization**: Clean all inputs before processing
3. **Resource Access**: Validate resource URIs before access
4. **Rate Limiting**: Consider implementing rate limits

## Integration with Claude

The MCP server integrates with Claude Code through:

1. Tool discovery via `mcp list-tools`
2. Tool execution via `mcp call-tool`
3. Resource access via `mcp read-resource`

Claude will automatically discover and use these tools when appropriate.
