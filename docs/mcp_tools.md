# ScriptRAG MCP Tools Documentation

## Overview

ScriptRAG provides 3 simple MCP tools for screenplay analysis using the existing query system. These tools work with the current ScriptRAG API without requiring additional functionality.

## Available Tools

### 1. scriptrag_query

Execute named SQL queries from the ScriptRAG query library.

**Parameters:**

- `query_name` (required): Name of query from library
- `params`: Query parameters as key-value pairs
- `limit`: Maximum rows to return (default: 50)
- `offset`: Row offset for pagination (default: 0)
- `output_json`: Return JSON formatted output (default: false)

**Returns:**

- `result`: Query results as formatted string
- `query_name`: Name of the executed query
- `row_count`: Estimated number of rows returned

**Examples:**

```python
# Execute a query to get character lines
await scriptrag_query(
    query_name="character-lines",
    params={"character": "WALTER"}
)

# Get scenes with pagination
await scriptrag_query(
    query_name="scenes",
    limit=10,
    offset=20
)

# Get JSON output
await scriptrag_query(
    query_name="characters",
    output_json=True
)
```

### 2. scriptrag_list_queries

List all available queries in the query library.

**Parameters:**
None

**Returns:**

- `queries`: List of available queries with:
  - `name`: Query name
  - `description`: Query description
  - `category`: Query category (if available)
- `total_count`: Total number of available queries

**Example:**

```python
# List all available queries
await scriptrag_list_queries()
```

### 3. scriptrag_status

Get basic system status information.

**Parameters:**
None

**Returns:**

- `database_path`: Path to the SQLite database
- `database_exists`: Whether the database file exists
- `database_size_mb`: Size of database in megabytes
- `available_queries`: Number of queries in the library

**Example:**

```python
# Get system status
await scriptrag_status()
```

## Using with Claude Desktop

1. Configure Claude Desktop to use the ScriptRAG MCP server
2. The 3 tools will appear in the tools menu
3. Use natural language to invoke tools

Example conversation:

```text
User: What queries are available?
Assistant: I'll list all available queries for you.
[Uses scriptrag_list_queries tool]

User: Show me all dialogue for character JESSE
Assistant: I'll execute the character-lines query for JESSE.
[Uses scriptrag_query tool with query_name="character-lines" and params={"character": "JESSE"}]
```

## Query Library

The ScriptRAG query library includes pre-defined queries for common screenplay analysis tasks:

- **Character queries**: Lines, appearances, relationships
- **Scene queries**: List scenes, scene details, scene graph
- **Dialogue queries**: Search dialogue, character interactions
- **Structure queries**: Acts, sequences, story beats

Use `scriptrag_list_queries()` to see all available queries with their descriptions.

## Limitations

These MCP tools are intentionally simple and limited to:

- Executing pre-defined queries only (no custom SQL)
- Read-only operations (no database modifications)
- Working with existing ScriptRAG API functionality

For more advanced operations, use the ScriptRAG CLI directly.
