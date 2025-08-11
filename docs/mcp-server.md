# ScriptRAG MCP Server

The ScriptRAG MCP (Model Context Protocol) server exposes screenplay analysis functionality through standardized tools and resources that can be used by AI assistants like Claude.

## Installation

The MCP server is installed automatically with ScriptRAG:

```bash
pip install scriptrag
```

## Running the Server

Start the MCP server:

```bash
scriptrag-mcp
```

The server runs on stdio transport by default for integration with Claude Desktop and other MCP clients.

## Available Tools

### Script Management

#### `scriptrag_import_script`

Import a Fountain screenplay file into the database.

**Parameters:**

- `file_path` (string, required): Path to the Fountain file
- `force` (boolean): Force re-import if script exists

**Example:**

```json
{
  "file_path": "/path/to/screenplay.fountain",
  "force": false
}
```

#### `scriptrag_list_scripts`

List all imported scripts with metadata.

**Parameters:**

- `limit` (integer): Maximum scripts to return (1-100, default: 10)
- `offset` (integer): Pagination offset (default: 0)

#### `scriptrag_get_script`

Get detailed information about a specific script.

**Parameters:**

- `script_id` (integer): Script database ID
- `title` (string): Script title
- `file_path` (string): Original file path

### Scene Operations

#### `scriptrag_list_scenes`

List scenes with filtering options.

**Parameters:**

- `script_id` (integer): Filter by script
- `character` (string): Filter by character presence
- `location` (string): Filter by scene location
- `limit` (integer): Maximum results (1-100, default: 20)
- `offset` (integer): Pagination offset

#### `scriptrag_get_scene`

Get detailed scene content and metadata.

**Parameters:**

- `scene_id` (integer, required): Scene database ID
- `include_dialogue` (boolean): Include dialogue breakdown (default: true)
- `include_analysis` (boolean): Include analysis results (default: false)

### Search Operations

#### `scriptrag_search_dialogue`

Search for dialogue content across scripts.

**Parameters:**

- `query` (string, required): Dialogue text to search
- `character` (string): Filter by character
- `script_id` (integer): Filter by script
- `fuzzy` (boolean): Enable fuzzy matching
- `limit` (integer): Maximum results (1-50, default: 10)

#### `scriptrag_search_character`

Search for character appearances and mentions.

**Parameters:**

- `character_name` (string, required): Character name
- `include_mentions` (boolean): Include action line mentions
- `script_id` (integer): Filter by script
- `limit` (integer): Maximum results (1-100, default: 20)

#### `scriptrag_semantic_search`

Semantic search using vector embeddings.

**Parameters:**

- `query` (string, required): Search query
- `include_bible` (boolean): Include bible content
- `only_bible` (boolean): Search only bible content
- `threshold` (float): Similarity threshold (0.0-1.0, default: 0.7)
- `limit` (integer): Maximum results (1-50, default: 10)

### Character Operations

#### `scriptrag_list_characters`

List all characters with statistics.

**Parameters:**

- `script_id` (integer): Filter by script
- `min_lines` (integer): Minimum dialogue lines
- `sort_by` (string): Sort by name/lines/scenes/appearances
- `limit` (integer): Maximum results (1-200, default: 50)

#### `scriptrag_get_character`

Get detailed character information and analysis.

**Parameters:**

- `character_name` (string, required): Character name
- `script_id` (integer): Filter by script
- `include_relationships` (boolean): Include relationships
- `include_arc_analysis` (boolean): Include character arc analysis

### Analysis Operations

#### `scriptrag_list_agents`

List available analysis agents.

**Parameters:**

- `category` (string): Filter by category
- `builtin_only` (boolean): Show only built-in agents

#### `scriptrag_run_agent`

Run an analysis agent on content.

**Parameters:**

- `agent_name` (string, required): Agent name
- `scene_id` (integer): Scene to analyze
- `script_id` (integer): Script to analyze
- `custom_content` (string): Custom content to analyze
- `save_results` (boolean): Save results to database

## Available Resources

Resources provide direct access to content through URI patterns:

### Script Resources

- `scriptrag://scripts/{script_id}` - Full script content in Fountain format
- `scriptrag://scripts/{script_id}/metadata` - Script metadata as JSON

### Scene Resources

- `scriptrag://scenes/{scene_id}` - Individual scene content
- `scriptrag://scenes/{scene_id}/analysis` - Scene analysis data

### Character Resources

- `scriptrag://characters/{character_name}` - Character information across all scripts
- `scriptrag://characters/{character_name}/script/{script_id}` - Character in specific script
- `scriptrag://characters/{character_name}/dialogue` - All dialogue for character

## Integration with Claude Desktop

To use ScriptRAG with Claude Desktop, add the following to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "scriptrag": {
      "command": "scriptrag-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

## Example Usage

### Import and Analyze a Script

1. Import a screenplay:

```text
Use scriptrag_import_script to import "/path/to/screenplay.fountain"
```

1. List scenes:

```text
Use scriptrag_list_scenes with script_id from the import
```

1. Search for dialogue:

```text
Use scriptrag_search_dialogue to find "specific dialogue"
```

1. Get character information:

```text
Use scriptrag_get_character for "CHARACTER_NAME"
```

### Semantic Search Example

```text
Use scriptrag_semantic_search with query "themes of redemption"
```

This will search across all script content and bible entries for semantically similar content.

## Error Handling

All tools return a consistent error format:

```json
{
  "success": false,
  "message": "Error description",
  "error": "Detailed error information"
}
```

## Performance Considerations

- Tools implement pagination for large result sets
- Content is truncated if it exceeds size limits
- Async operations are used throughout for better performance
- Database connections are pooled and reused

## Security

- File paths are validated before access
- Input sanitization is applied to all parameters
- Resource URIs are validated before access
- No direct SQL execution from user input

## Troubleshooting

### Server Won't Start

- Ensure ScriptRAG is properly installed
- Check that the database is initialized: `scriptrag init`
- Verify Python version is 3.11 or higher

### Tools Not Working

- Check that scripts are imported first
- Ensure database contains data
- Review server logs for detailed error messages

### Performance Issues

- Use pagination for large result sets
- Adjust similarity threshold for semantic search
- Consider indexing large script collections in batches

## Development

To extend the MCP server with new tools:

1. Create a new tool file in `src/scriptrag/mcp/tools/`
2. Implement the tool function with proper decorators
3. Add the tool to the imports in `tools/__init__.py`
4. Update this documentation

Each tool should:

- Use the `@mcp.tool()` decorator
- Accept and validate input parameters
- Return structured output using Pydantic models
- Handle errors gracefully
- Include proper logging

