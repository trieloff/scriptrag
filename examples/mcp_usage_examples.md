# ScriptRAG MCP Server Usage Examples

The ScriptRAG MCP server exposes screenplay analysis functionality through the
Model Context Protocol, allowing AI assistants and other MCP-compatible clients
to interact with screenplays.

## Configuration

### Claude Desktop Configuration

Add the following to your Claude Desktop configuration file
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "scriptrag": {
      "command": "python",
      "args": ["-m", "scriptrag.mcp_server"],
      "env": {
        "SCRIPTRAG_DB_PATH": "/path/to/your/screenplay.db"
      }
    }
  }
}
```

### Environment Variables

The MCP server can be configured using environment variables:

- `SCRIPTRAG_MCP_HOST`: Server host (default: localhost)
- `SCRIPTRAG_MCP_PORT`: Server port (default: 8080)
- `SCRIPTRAG_MCP_MAX_RESOURCES`: Maximum resources to expose (default: 1000)
- `SCRIPTRAG_DB_PATH`: Path to SQLite database
- `SCRIPTRAG_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Available Tools

### 1. parse_script

Parse a screenplay file in Fountain format.

```json
{
  "tool": "parse_script",
  "arguments": {
    "path": "/path/to/screenplay.fountain",
    "title": "My Screenplay"  // optional
  }
}
```

### 2. search_scenes

Search for scenes based on various criteria.

```json
{
  "tool": "search_scenes",
  "arguments": {
    "script_id": "script_0",
    "query": "coffee shop",
    "location": "INT. CAFE",
    "characters": ["JOHN", "MARY"],
    "limit": 10
  }
}
```

### 3. get_character_info

Get detailed information about a character.

```json
{
  "tool": "get_character_info",
  "arguments": {
    "script_id": "script_0",
    "character_name": "JOHN"
  }
}
```

### 4. analyze_timeline

Analyze the temporal flow of the script.

```json
{
  "tool": "analyze_timeline",
  "arguments": {
    "script_id": "script_0",
    "include_flashbacks": true
  }
}
```

### 5. update_scene

Update a scene with new information.

```json
{
  "tool": "update_scene",
  "arguments": {
    "script_id": "script_0",
    "scene_id": 5,
    "heading": "INT. OFFICE - NIGHT",
    "action": "The room is dimly lit.",
    "dialogue": [
      {
        "character": "JOHN",
        "text": "We need to talk.",
        "parenthetical": "nervously"
      }
    ]
  }
}
```

### 6. delete_scene

Delete a scene from the script.

```json
{
  "tool": "delete_scene",
  "arguments": {
    "script_id": "script_0",
    "scene_id": 10
  }
}
```

### 7. inject_scene

Insert a new scene at a specific position.

```json
{
  "tool": "inject_scene",
  "arguments": {
    "script_id": "script_0",
    "position": 5,
    "heading": "EXT. PARK - DAY",
    "action": "Birds chirp in the trees.",
    "dialogue": []
  }
}
```

### 8. get_scene_details

Get detailed information about a specific scene.

```json
{
  "tool": "get_scene_details",
  "arguments": {
    "script_id": "script_0",
    "scene_id": 7
  }
}
```

### 9. get_character_relationships

Analyze relationships between characters.

```json
{
  "tool": "get_character_relationships",
  "arguments": {
    "script_id": "script_0",
    "character_name": "JOHN"  // optional, omit for all relationships
  }
}
```

### 10. export_data

Export script data in various formats.

```json
{
  "tool": "export_data",
  "arguments": {
    "script_id": "script_0",
    "format": "json",  // or "csv", "graphml", "fountain"
    "include_metadata": true
  }
}
```

### 11. list_scripts

List all parsed scripts in the database.

```json
{
  "tool": "list_scripts",
  "arguments": {}
}
```

## Available Resources

Resources can be accessed using standard MCP resource URIs:

### Screenplay Resources

- `screenplay://list` - List of all parsed screenplays
- `screenplay://script_0` - Full screenplay structure and metadata
- `scene://script_0/5` - Individual scene information
- `character://script_0/JOHN` - Character details and relationships
- `timeline://script_0` - Script timeline and temporal flow

## Available Prompts

The server provides pre-configured prompts for common analysis tasks:

### 1. analyze_script_structure

Analyze the three-act structure of a screenplay.

```json
{
  "prompt": "analyze_script_structure",
  "arguments": {
    "script_id": "script_0"
  }
}
```

### 2. character_arc_analysis

Analyze a character's arc throughout the screenplay.

```json
{
  "prompt": "character_arc_analysis",
  "arguments": {
    "script_id": "script_0",
    "character_name": "JOHN"
  }
}
```

### 3. scene_improvement_suggestions

Get suggestions for improving a specific scene.

```json
{
  "prompt": "scene_improvement_suggestions",
  "arguments": {
    "script_id": "script_0",
    "scene_number": "5"
  }
}
```

## Example Workflow

Here's a typical workflow for analyzing a screenplay:

1. **Parse the screenplay**:

   ```text
   Use tool: parse_script
   Arguments: {"path": "/path/to/script.fountain"}
   Returns: {"script_id": "script_0", "title": "My Script", ...}
   ```

2. **Search for specific scenes**:

   ```text
   Use tool: search_scenes
   Arguments: {"script_id": "script_0", "query": "confrontation"}
   Returns: List of matching scenes
   ```

3. **Analyze character relationships**:

   ```text
   Use tool: get_character_relationships
   Arguments: {"script_id": "script_0"}
   Returns: Network of character interactions
   ```

4. **Get improvement suggestions**:

   ```text
   Use prompt: scene_improvement_suggestions
   Arguments: {"script_id": "script_0", "scene_number": "10"}
   Returns: AI-generated suggestions
   ```

5. **Export the data**:

   ```text
   Use tool: export_data
   Arguments: {"script_id": "script_0", "format": "json"}
   Returns: Export file path
   ```

## Error Handling

The MCP server returns structured errors for invalid requests:

```json
{
  "error": true,
  "message": "script_id is required"
}
```

Common error scenarios:

- Missing required arguments
- Invalid script or scene IDs
- Unsupported export formats
- File not found errors for screenplay paths

## Performance Considerations

- The server caches parsed scripts in memory for better performance
- Resource listings are generated dynamically based on cached scripts
- Large screenplays may take time to parse initially
- Export operations may be memory-intensive for large scripts

## Security Considerations

- The server only has access to files explicitly provided via tool calls
- Database operations are confined to the configured database path
- No remote network access is performed by default
- Exported files are saved to a temporary directory
