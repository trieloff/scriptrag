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

## Implementation Pattern

Each command file should follow this pattern:

```python
"""Script-related CLI commands."""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..api import ScriptRAGAPI
from ..models import Script
from .utils import handle_errors, format_script

app = typer.Typer(help="Script management commands")
console = Console()


@app.command()
@handle_errors
def import_script(
    path: Path = typer.Argument(
        ...,
        help="Path to Fountain file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True
    ),
    series: str = typer.Option(
        None,
        "--series", "-s",
        help="Series ID to associate with"
    )
):
    """Import a Fountain screenplay into ScriptRAG."""
    api = ScriptRAGAPI()

    with console.status(f"Importing {path.name}..."):
        script_id = api.import_script(path, series_id=series)

    console.print(f"✅ Imported script: {script_id}", style="success")


@app.command()
@handle_errors
def list_scripts(
    series: str = typer.Option(None, "--series", "-s", help="Filter by series"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results")
):
    """List all scripts in the database."""
    api = ScriptRAGAPI()
    scripts = api.list_scripts(series_id=series)

    table = Table(title="Scripts")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Series", style="green")
    table.add_column("Episodes/Scenes", justify="right")

    for script in scripts[:limit]:
        table.add_row(
            script.id,
            script.title,
            script.series_id or "-",
            str(len(script.scenes))
        )

    console.print(table)
```

## Key Patterns

### 1. Error Handling

Use the `@handle_errors` decorator to catch and format API errors:

```python
from functools import wraps
from ..exceptions import ScriptRAGError

def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ScriptRAGError as e:
            console.print(f"❌ Error: {e}", style="error")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"❌ Unexpected error: {e}", style="error")
            if console.is_debug:
                console.print_exception()
            raise typer.Exit(2)
    return wrapper
```

### 2. Output Formatting

Use Rich for beautiful terminal output:

```python
# Tables for lists
table = Table(title="Search Results", show_lines=True)

# Progress bars for long operations
with Progress() as progress:
    task = progress.add_task("Processing...", total=100)

# Styled output
console.print("[bold green]Success![/bold green]")
console.print(Panel("Scene content here", title="Scene 42"))
```

### 3. Input Validation

Typer provides built-in validation:

```python
path: Path = typer.Argument(
    ...,
    exists=True,  # Must exist
    file_okay=True,  # Can be a file
    dir_okay=False,  # Cannot be a directory
    readable=True,  # Must be readable
    resolve_path=True  # Resolve to absolute
)
```

### 4. Interactive Features

For complex inputs:

```python
if not series_id:
    series_id = typer.prompt("Enter series ID")

if typer.confirm("Are you sure?"):
    # Proceed with operation
```

## Command Structure

```bash
scriptrag script import path/to/script.fountain
scriptrag script list --series breaking-bad
scriptrag script show s01e01

scriptrag scene list s01e01
scriptrag scene show <content-hash>
scriptrag scene reprocess <content-hash>

scriptrag search dialogue "I am the one who knocks"
scriptrag search character WALTER --limit 20
scriptrag search semantic "tense confrontation"

scriptrag character list breaking-bad
scriptrag character show breaking-bad:WALTER
scriptrag character update-bible breaking-bad:WALTER docs/walter.md

scriptrag agent list
scriptrag agent run emotional_beats <content-hash>
```

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

Use Typer's testing utilities:

```python
from typer.testing import CliRunner
runner = CliRunner()
result = runner.invoke(app, ["import", "test.fountain"])
```

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
