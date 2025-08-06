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



## Key Patterns

### 1. Tool Naming Convention

All tools must be prefixed with `scriptrag_`:

- `scriptrag_import_script`
- `scriptrag_search_dialogue`
- `scriptrag_list_characters`

### 2. Schema Validation

Use JSON Schema for input validation with appropriate field definitions and validation rules.

### 3. Error Handling

Always return proper MCP errors using ToolResult objects with appropriate error flags.

### 4. Content Types

MCP supports multiple content types including text, images, and mixed content formats.

## Server Configuration

The main server file assembles all tools by importing tool modules and registering them with the MCP server instance.

## Testing

Each tool should have comprehensive tests using pytest with async support for tool execution validation.

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
