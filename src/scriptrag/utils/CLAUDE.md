# Utilities

This directory contains shared utilities and helper functions used across ScriptRAG components.

## Purpose

The utils module provides:

- Common functionality shared between components
- Helper functions that don't belong to specific domains
- Development and debugging tools
- Performance utilities

## Logging Utilities

```python
# utils/logging.py
import structlog
from typing import Any, Dict
import sys

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger for a module."""
    return structlog.get_logger(name)

def configure_logging(debug: bool = False) -> None:
    """Configure structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

## Text Processing

```python
# utils/text.py
import re
from typing import List, Tuple

def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    # Convert multiple spaces to single
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    return text.strip()

def extract_parentheticals(text: str) -> List[Tuple[str, str]]:
    """Extract parenthetical expressions from text."""
    pattern = r'(\w+)\s*\(([^)]+)\)'
    return re.findall(pattern, text)

def remove_parentheticals(text: str) -> str:
    """Remove parenthetical expressions from text."""
    return re.sub(r'\([^)]+\)', '', text).strip()

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
```

## File System Utilities

```python
# utils/filesystem.py
from pathlib import Path
from typing import List, Optional
import hashlib

def find_files(
    root: Path,
    pattern: str,
    recursive: bool = True
) -> List[Path]:
    """Find files matching pattern."""
    if recursive:
        return list(root.rglob(pattern))
    return list(root.glob(pattern))

def safe_path_join(base: Path, *parts: str) -> Path:
    """Safely join path parts preventing directory traversal."""
    base = base.resolve()
    path = base.joinpath(*parts).resolve()

    # Ensure the final path is within base
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal detected: {path}")

    return path

def calculate_file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of file contents."""
    hasher = hashlib.new(algorithm)

    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()

def atomic_write(path: Path, content: str) -> None:
    """Write file atomically to prevent corruption."""
    tmp_path = path.with_suffix(path.suffix + '.tmp')

    try:
        tmp_path.write_text(content, encoding='utf-8')
        tmp_path.replace(path)
    except:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
```

## Performance Utilities

```python
# utils/performance.py
import time
from contextlib import contextmanager
from typing import Iterator, Dict, Any
import psutil
import functools

@contextmanager
def timer(name: str) -> Iterator[Dict[str, Any]]:
    """Time a code block."""
    result = {"name": name, "duration": 0}
    start = time.perf_counter()

    try:
        yield result
    finally:
        result["duration"] = time.perf_counter() - start

def memory_usage() -> Dict[str, float]:
    """Get current memory usage."""
    process = psutil.Process()
    info = process.memory_info()

    return {
        "rss_mb": info.rss / 1024 / 1024,
        "vms_mb": info.vms / 1024 / 1024,
        "percent": process.memory_percent()
    }

def memoize(maxsize: int = 128):
    """Memoization decorator with size limit."""
    def decorator(func):
        @functools.lru_cache(maxsize=maxsize)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.cache_info = wrapper.cache_info
        wrapper.cache_clear = wrapper.cache_clear
        return wrapper

    return decorator
```

## Validation Utilities

```python
# utils/validation.py
from typing import Any, Dict, List
import jsonschema

def validate_json_schema(
    data: Any,
    schema: Dict[str, Any]
) -> List[str]:
    """Validate data against JSON schema."""
    errors = []
    validator = jsonschema.Draft7Validator(schema)

    for error in validator.iter_errors(data):
        error_path = ".".join(str(p) for p in error.path)
        errors.append(f"{error_path}: {error.message}")

    return errors

def validate_fountain_syntax(text: str) -> List[str]:
    """Basic validation of Fountain syntax."""
    errors = []
    lines = text.split('\n')

    for i, line in enumerate(lines, 1):
        # Check for common issues
        if line.startswith('INT.') or line.startswith('EXT.'):
            if not line.isupper():
                errors.append(f"Line {i}: Scene headings should be uppercase")

        # Check for tabs (should use spaces)
        if '\t' in line:
            errors.append(f"Line {i}: Contains tabs (use spaces instead)")

    return errors
```

## CLI Utilities

```python
# utils/cli.py
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Any, Iterator
from contextlib import contextmanager

console = Console()

@contextmanager
def progress_context(description: str) -> Iterator[Any]:
    """Show progress spinner for long operations."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(description)
        yield progress
        progress.remove_task(task)

def format_error(error: Exception) -> str:
    """Format exception for CLI display."""
    return f"[red]✗[/red] {type(error).__name__}: {str(error)}"

def format_success(message: str) -> str:
    """Format success message for CLI display."""
    return f"[green]✓[/green] {message}"

def confirm(prompt: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    suffix = " [Y/n]" if default else " [y/N]"
    response = console.input(prompt + suffix + " ").lower().strip()

    if not response:
        return default

    return response[0] == 'y'
```

## Development Utilities

```python
# utils/debug.py
import pdb
import sys
from typing import Any

def debug_on_exception():
    """Drop into debugger on unhandled exception."""
    def excepthook(type, value, traceback):
        if hasattr(sys, 'ps1') or not sys.stderr.isatty():
            # Interactive mode or no terminal
            sys.__excepthook__(type, value, traceback)
        else:
            import traceback as tb
            import pdb
            tb.print_exception(type, value, traceback)
            pdb.post_mortem(traceback)

    sys.excepthook = excepthook

def pretty_print(obj: Any, indent: int = 2) -> str:
    """Pretty print any object."""
    import json

    # Try JSON serialization first
    try:
        return json.dumps(obj, indent=indent, default=str)
    except:
        # Fallback to repr
        import pprint
        return pprint.pformat(obj, indent=indent)
```

## Testing Utilities

```python
# utils/testing.py
from pathlib import Path
import tempfile
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def temp_git_repo() -> Iterator[Path]:
    """Create a temporary git repository for testing."""
    import git

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        repo = git.Repo.init(path)

        # Initial commit
        (path / "README.md").write_text("Test repo")
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")

        yield path

def create_test_fountain(
    scenes: int = 5,
    characters: List[str] = None
) -> str:
    """Generate test Fountain content."""
    if characters is None:
        characters = ["ALICE", "BOB", "CHARLIE"]

    content = ["Title: Test Script", ""]

    for i in range(1, scenes + 1):
        content.extend([
            f"INT. LOCATION {i} - DAY",
            "",
            f"This is scene {i}.",
            "",
            characters[i % len(characters)],
            f"Dialogue for scene {i}.",
            ""
        ])

    return "\n".join(content)
```

## Import All Utilities

```python
# utils/__init__.py
from .logging import get_logger, configure_logging
from .text import normalize_whitespace, truncate_text
from .filesystem import find_files, safe_path_join
from .performance import timer, memoize
from .validation import validate_json_schema
from .cli import console, progress_context
from .debug import debug_on_exception
from .testing import temp_git_repo, create_test_fountain

__all__ = [
    "get_logger",
    "configure_logging",
    "normalize_whitespace",
    "truncate_text",
    "find_files",
    "safe_path_join",
    "timer",
    "memoize",
    "validate_json_schema",
    "console",
    "progress_context",
    "debug_on_exception",
    "temp_git_repo",
    "create_test_fountain",
]
```
