# ScriptRAG MCP Server

The ScriptRAG MCP (Model Context Protocol) server exposes screenplay analysis
functionality to AI assistants and other MCP-compatible clients.

## Overview

The MCP server provides a standardized interface for:

- Parsing screenplays in Fountain format
- Searching scenes based on various criteria
- Analyzing character relationships and timelines
- Managing screenplay structure
- Exporting data in multiple formats

## Running the Server

```bash
# Using uv to run the MCP server
uv run scriptrag-mcp

# With custom configuration
uv run scriptrag-mcp --config-file config.yaml

# With environment variables
SCRIPTRAG_MCP_HOST=0.0.0.0 SCRIPTRAG_MCP_PORT=9000 uv run scriptrag-mcp
```

## Configuration

The server can be configured through:

1. Configuration files (YAML/JSON)
2. Environment variables
3. Command-line arguments

### Example Configuration

```yaml
mcp:
  host: localhost
  port: 8080
  max_resources: 1000
  enable_all_tools: true
  # Or specify specific tools:
  # enabled_tools:
  #   - parse_script
  #   - search_scenes
```

## Available Tools

### Script Management

- `parse_script` - Parse a Fountain format screenplay
- `list_scripts` - List all parsed scripts

### Scene Operations

- `search_scenes` - Search scenes by query, location, or characters
- `get_scene_details` - Get detailed information about a scene
- `update_scene` - Update scene content
- `delete_scene` - Remove a scene
- `inject_scene` - Insert a new scene at a specific position

### Analysis Tools

- `get_character_info` - Character statistics and information
- `get_character_relationships` - Analyze character interactions
- `analyze_timeline` - Temporal flow analysis
- `export_data` - Export in JSON, CSV, GraphML, or Fountain format

## Available Resources

Resources provide read-only access to screenplay data:

- `screenplay://list` - List of all screenplays
- `screenplay://{script_id}` - Full screenplay structure
- `scene://{script_id}/{scene_id}` - Individual scene details
- `character://{script_id}/{character_name}` - Character information
- `timeline://{script_id}` - Timeline analysis

## Available Prompts

Pre-configured prompts for common analysis tasks:

- `analyze_script_structure` - Three-act structure analysis
- `character_arc_analysis` - Character development tracking
- `scene_improvement_suggestions` - Scene optimization recommendations

## Integration with Claude

To use with Claude Desktop, add to your configuration:

```json
{
  "mcpServers": {
    "scriptrag": {
      "command": "uv",
      "args": ["run", "scriptrag-mcp"],
      "env": {
        "SCRIPTRAG_DB_PATH": "/path/to/screenplay.db"
      }
    }
  }
}
```

## Development Status

The MCP server is fully implemented with:

- ✅ Complete tool implementations (11 tools)
- ✅ Resource management system
- ✅ Prompt templates
- ✅ Type-safe request/response handling
- ✅ Comprehensive test coverage
- ✅ Error handling and logging

Note: Some features like scene manipulation and timeline analysis will be fully
functional once the underlying database operations are implemented in earlier
project phases.
