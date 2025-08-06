# ScriptRAG CLI Implementation

This directory contains the command-line interface implementation using Typer. Each command group and subcommand should be in separate files for maintainability.

## Architecture Role

The CLI is one of the two main user interfaces (along with MCP). It translates command-line arguments into API calls and formats the results for terminal output.

## IMPORTANT: File Organization

**EACH COMMAND GROUP MUST BE IN A SEPARATE FILE**

Structure:

```text
cli/
├── __init__.py          # CLI app initialization
├── main.py             # Entry point and app assembly
├── script.py           # Script commands (import, list, show)
├── scene.py            # Scene commands (list, show, reprocess)
├── search.py           # Search commands (dialogue, character, semantic)
├── character.py        # Character commands (list, show, update-bible)
├── series.py           # Series commands (create, list)
├── agent.py            # Agent commands (list, run)
├── config.py           # Config commands (show, set, get)
├── utils.py            # Shared CLI utilities (formatting, output)
└── styles.py           # Rich styles and themes
```


## Key Patterns

### 1. Error Handling

Use decorators to catch and format API errors with appropriate exit codes.

### 2. Output Formatting

Use Rich for beautiful terminal output including tables, progress bars, and styled text.

### 3. Input Validation

Typer provides built-in validation for paths, ensuring files exist and are accessible.

### 4. Interactive Features

Use interactive prompts and confirmations for complex user inputs.

## Command Structure

The CLI provides hierarchical commands organized by functionality: script management, scene operations, search commands, character management, and agent execution.

## Configuration

The CLI respects configuration from:

1. Environment variables (scriptrag_*)
2. Config file (~/.scriptrag/config.YAML)
3. Command-line options (highest precedence)

## Testing

Each command group should have tests:

- `test_script_commands.py`
- `test_search_commands.py`
- etc.

Use Typer's testing utilities with CliRunner for automated command testing.

## Rich Integration

We use Rich for all output:

- Tables for structured data
- Progress bars for long operations  
- Syntax highlighting for code/scripts
- Tree views for hierarchical data
- Panels for important information

## Performance Tips

1. **Streaming Output**: For large results, stream instead of loading all
2. **Pagination**: Add `--page` option for long lists
3. **Caching**: Cache API client between commands in same session
4. **Async**: Consider async for I/O bound operations
