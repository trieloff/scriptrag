# CLI Refactoring Guide

This guide explains how to refactor large Python files in ScriptRAG to comply with the file size limits established for MCP tool compatibility.

**Note**: This guide provides examples and patterns for refactoring. The actual refactoring of large files should be done as separate, focused PRs to ensure proper testing and review.

## File Size Limits

- **Regular Python files**: 1000 lines (soft), 1500 lines (hard)
- **Test files**: 2000 lines (hard)

## Current Violations

The following files exceed our limits and need refactoring:

1. `src/scriptrag/cli.py` (3313 lines)
2. `src/scriptrag/mcp_server.py` (3346 lines)
3. `src/scriptrag/mentors/character_arc.py` (2538 lines)
4. `src/scriptrag/database/operations.py` (1967 lines)
5. `src/scriptrag/database/migrations.py` (1896 lines)

## Refactoring Strategy: CLI Example

The CLI module (`cli.py`) is already well-organized into command groups, making it an ideal candidate for demonstrating the refactoring pattern.

### Current Structure

```python
# cli.py (3313 lines)
app = typer.Typer(...)

# Configuration commands (lines 161-315)
config_app = typer.Typer(...)
app.add_typer(config_app)

# Script commands (lines 318-633)
script_app = typer.Typer(...)
app.add_typer(script_app)

# Scene commands (lines 1230-1753)
scene_app = typer.Typer(...)
app.add_typer(scene_app)

# ... and so on
```

### Refactored Structure

```text
src/scriptrag/cli/
├── __init__.py          # Exports main app
├── main.py             # Main app and common utilities (~150 lines)
├── config.py           # Config commands (~150 lines)
├── script.py           # Script commands (~300 lines)
├── scene.py            # Scene commands (~500 lines)
├── search.py           # Search commands (~300 lines)
├── dev.py              # Dev commands (~150 lines)
├── bible.py            # Bible commands (~600 lines)
├── server.py           # Server commands (~100 lines)
└── mentor.py           # Mentor commands (~400 lines)
```

### Refactoring Steps

1. **Create Package Structure**

   ```bash
   mkdir -p src/scriptrag/cli
   ```

2. **Extract Command Groups**
   Each command group becomes its own module:

   ```python
   # cli/config.py
   from pathlib import Path
   import typer
   from ..config import get_logger, get_settings

   config_app = typer.Typer(name="config", help="Configuration management")

   @config_app.command("init")
   def config_init(...):
       """Initialize configuration."""
       ...
   ```

3. **Create Main Entry Point**

   ```python
   # cli/main.py
   import typer
   from .config import config_app
   from .script import script_app
   # ... other imports

   app = typer.Typer(name="scriptrag", help="ScriptRAG CLI")

   # Register all command groups
   app.add_typer(config_app)
   app.add_typer(script_app)
   # ... etc
   ```

4. **Update Package Init**

   ```python
   # cli/__init__.py
   from .main import app
   __all__ = ["app"]
   ```

5. **Update Imports**
   In the main `cli.py` file:

   ```python
   from .cli import app  # Now imports from package
   ```

## Refactoring Other Large Files

### MCP Server (`mcp_server.py`)

The MCP server can be split by tool categories:

```text
src/scriptrag/mcp/
├── __init__.py
├── server.py           # Main server setup (~300 lines)
├── tools/
│   ├── __init__.py
│   ├── script.py       # Script-related tools
│   ├── scene.py        # Scene-related tools
│   ├── search.py       # Search tools
│   ├── graph.py        # Graph operations
│   └── bible.py        # Script bible tools
└── handlers.py         # Request/response handlers
```

### Character Arc Mentor (`character_arc.py`)

Split by analysis phases:

```text
src/scriptrag/mentors/character_arc/
├── __init__.py
├── base.py             # Base character arc analyzer
├── setup.py            # Character setup analysis
├── transformation.py   # Character transformation tracking
├── relationships.py    # Character relationship analysis
└── patterns.py         # Arc pattern detection
```

### Database Operations (`operations.py`)

Split by operation type:

```text
src/scriptrag/database/operations/
├── __init__.py
├── base.py             # Base operations
├── script.py           # Script CRUD operations
├── scene.py            # Scene operations
├── character.py        # Character operations
└── relationship.py     # Relationship operations
```

## Benefits of Refactoring

1. **MCP Compatibility**: Files stay within token limits
2. **Better Organization**: Related functionality grouped together
3. **Easier Maintenance**: Smaller files are easier to understand and modify
4. **Improved Testing**: Can test modules in isolation
5. **Faster Development**: Easier to find and modify specific functionality

## Testing After Refactoring

Always run the full test suite after refactoring:

```bash
make test
make lint
make type-check
```

Ensure that:

- All imports are updated correctly
- No functionality is lost
- All tests pass
- Type checking succeeds
- Linting passes

## Gradual Refactoring Approach

You don't need to refactor everything at once. Start with:

1. Files that exceed the hard limit (1500 lines)
2. Files that are frequently modified
3. Files with clear logical divisions

The pre-commit hooks will prevent new files from exceeding limits, so focus on addressing existing violations gradually.
