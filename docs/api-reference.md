# ScriptRAG v2 API Reference

The ScriptRAG v2 API provides a comprehensive Python interface for parsing, indexing, and searching screenplay content.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core API](#core-api)
  - [ScriptRAG Class](#scriptrag-class)
  - [parse_fountain()](#parse_fountain)
  - [index_script()](#index_script)
  - [index_directory()](#index_directory)
  - [search()](#search)
- [Data Models](#data-models)
  - [Script](#script)
  - [Scene](#scene)
  - [SearchResult](#searchresult)
  - [SearchResponse](#searchresponse)
- [Common Patterns](#common-patterns)
  - [Error Handling](#error-handling)
  - [Progress Tracking](#progress-tracking)
  - [Batch Processing](#batch-processing)
- [Configuration](#configuration)
- [Exceptions](#exceptions)
- [See Also](#see-also)

## Installation

```bash
pip install scriptrag
```

Or for development:

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
make setup-dev
source .venv/bin/activate
```

## Quick Start

```python
from scriptrag import ScriptRAG

# Initialize and index a screenplay
rag = ScriptRAG(auto_init_db=True)
script = rag.parse_fountain("screenplay.fountain")
result = rag.index_script("screenplay.fountain")

# Search the indexed content
search_results = rag.search("coffee shop")
for result in search_results.results:
    print(f"Scene {result.scene_number}: {result.scene_heading}")
```

## Core API

### ScriptRAG Class

```python
class ScriptRAG:
    def __init__(
        self,
        settings: ScriptRAGSettings | None = None,
        auto_init_db: bool = True
    ):
        ...
```

Creates a new ScriptRAG instance.

**Parameters:**

- `settings`: Configuration settings (uses defaults if not provided)
- `auto_init_db`: Automatically initialize database if it doesn't exist (default: `True`)

**Examples:**

```python
# Default initialization
rag = ScriptRAG()

# Custom settings
settings = ScriptRAGSettings(database_path="custom.db")
rag = ScriptRAG(settings=settings)
```

### parse_Fountain()

```python
def parse_fountain(self, path: str | Path) -> Script:
    """Parse a Fountain format screenplay file."""
    ...
```

Parses a Fountain format screenplay file.

**Parameters:**

- `path` (str | Path): Path to the Fountain file

**Returns:**

- `Script`: Parsed screenplay object containing scenes, characters, and metadata

**Raises:**

- `FileNotFoundError`: If the specified file doesn't exist
- `ParseError`: If the file cannot be parsed as valid Fountain format

**Example:**

```python
script = rag.parse_fountain("screenplay.fountain")
print(f"Title: {script.title}")
print(f"Scenes: {len(script.scenes)}")

# Access scene details
for scene in script.scenes:
    print(f"Scene {scene.number}: {scene.heading}")
    for dialogue in scene.dialogue_lines:
        print(f"  {dialogue.character}: {dialogue.text}")
```

**See also:** [Script](#script), [Scene](#scene) data models

### index_script()

```python
def index_script(
    self,
    path: str | Path,
    dry_run: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None
) -> dict[str, Any]:
    """Index a parsed screenplay into the database."""
    ...
```

Indexes a Fountain screenplay into the database for searching.

**Parameters:**

- `path` (str | Path): Path to the Fountain file to index
- `dry_run` (bool): If True, preview changes without applying them. Default: `False`.
- `progress_callback` (Callable): Optional callback for progress updates. Signature: `(current: int, total: int, message: str) -> None`

**Returns:**

Dictionary with indexing results:

- `script_id` (int | None): Database ID of the indexed script
- `indexed` (bool): Whether indexing was successful
- `updated` (bool): Whether this was an update to existing script
- `scenes_indexed` (int): Number of scenes indexed
- `characters_indexed` (int): Number of characters indexed
- `dialogues_indexed` (int): Number of dialogues indexed
- `actions_indexed` (int): Number of actions indexed
- `error` (str | None): Error message if indexing failed

**Raises:**

- `FileNotFoundError`: If the specified file doesn't exist
- `DatabaseError`: If database operations fail

**Example:**

```python
# Basic indexing
result = rag.index_script("screenplay.fountain")
if result["indexed"]:
    print(f"Indexed {result['scenes_indexed']} scenes")

# With progress callback
def progress(current, total, message):
    print(f"[{current}/{total}] {message}")

result = rag.index_script("screenplay.fountain", progress_callback=progress)
```

**See also:** [index_directory()](#index_directory) for batch processing, [Progress Tracking](#progress-tracking) for detailed examples

### index_directory()

```python
def index_directory(
    self,
    path: str | Path | None = None,
    recursive: bool = True,
    dry_run: bool = False,
    batch_size: int = 10,
    progress_callback: Callable[[int, int, str], None] | None = None
) -> dict[str, Any]:
    """Index all Fountain files in a directory."""
    ...
```

Indexes all Fountain files in a directory.

**Parameters:**

- `path` (str | Path | None): Directory path to search. Default: current directory.
- `recursive` (bool): Search subdirectories recursively. Default: `True`.
- `dry_run` (bool): Preview changes without applying them. Default: `False`.
- `batch_size` (int): Number of scripts to process per batch. Default: `10`.
- `progress_callback` (Callable): Optional callback for progress updates. Signature: `(current: int, total: int, message: str) -> None`

**Returns:**

Dictionary with indexing statistics:

- `total_scripts_indexed` (int): Number of scripts successfully indexed
- `total_scripts_updated` (int): Number of existing scripts updated
- `total_scenes_indexed` (int): Total scenes across all scripts
- `total_characters_indexed` (int): Total unique characters
- `total_dialogues_indexed` (int): Total dialogue entries
- `total_actions_indexed` (int): Total action entries
- `errors` (list[str]): List of any errors encountered

**Raises:**

- `FileNotFoundError`: If directory doesn't exist
- `ValueError`: If path is not a directory
- `DatabaseError`: If database operations fail

**Example:**

```python
# Index all Fountain files in a directory
result = rag.index_directory("./screenplays")

print(f"Indexed {result['total_scripts_indexed']} scripts")
print(f"Total scenes: {result['total_scenes_indexed']}")

if result['errors']:
    print("Errors encountered:")
    for error in result['errors']:
        print(f"  - {error}")

# Non-recursive indexing
result = rag.index_directory("./screenplays", recursive=False)

# Dry run
preview = rag.index_directory("./screenplays", dry_run=True)

# With progress tracking
def track_progress(current, total, message):
    percent = (current / total * 100) if total > 0 else 0
    print(f"[{percent:.0f}%] {message}")

result = rag.index_directory(
    "./screenplays",
    progress_callback=track_progress
)
```

### search()

```python
def search(
    self,
    query: str,
    mode: SearchMode | str = SearchMode.AUTO,
    limit: int = 10,
    offset: int = 0,
    character: str | None = None,
    location: str | None = None,
    dialogue: str | None = None,
    project: str | None = None,
    include_bible: bool = True,
    only_bible: bool = False,
    filters: dict[str, str] | None = None
) -> SearchResponse:
    """Search for content in the screenplay database."""
    ...
```

Searches indexed screenplay content.

**Parameters:**

- `query` (str): Search query string
- `mode` (SearchMode | str): Search mode - 'strict', 'fuzzy', or 'auto' (default: 'auto')
- `limit` (int): Maximum results to return (default: 10)
- `offset` (int): Results to skip for pagination (default: 0)
- `character` (str | None): Filter by character name
- `location` (str | None): Filter by scene location
- `dialogue` (str | None): Search specifically for dialogue
- `project` (str | None): Filter by project name
- `include_bible` (bool): Include reference content (default: True)
- `only_bible` (bool): Search only reference content (default: False)
- `filters` (dict[str, str] | None): Additional filters as key-value pairs

**Returns:**

`SearchResponse` object containing:

- `results` (list[SearchResult]): List of search results
- `bible_results` (list[BibleSearchResult]): Reference content results
- `total_count` (int): Total matching results
- `query` (SearchQuery): The parsed query used

**Raises:**

- `DatabaseError`: If database is not initialized
- `ValueError`: If invalid search parameters

**Example:**

```python
# Basic search
results = rag.search("coffee shop")
for result in results.results:
    print(f"Scene {result.scene_number}: {result.scene_heading}")

# Search with filters
results = rag.search(
    "important dialogue",
    character="SARAH",
    location="OFFICE"
)

# Search with custom filters
results = rag.search(
    "action sequence",
    filters={"scene_type": "EXT"}
)

# Pagination for large result sets
page1 = rag.search("INT.", limit=10, offset=0)
page2 = rag.search("INT.", limit=10, offset=10)
```

**See also:** [SearchResponse](#searchresponse), [Common Patterns](#common-patterns) for advanced search

## Data Models

### Script

Represents a parsed screenplay with scenes and metadata.

**Attributes:**

- `title`: Screenplay title
- `author`: Author name
- `scenes`: List of Scene objects
- `metadata`: Additional metadata from Fountain file

### Scene

Represents a single scene in a screenplay.

**Attributes:**

- `number`: Scene number
- `heading`: Scene heading (e.g., "INT. COFFEE SHOP - DAY")
- `content`: Full scene text
- `location`: Extracted location
- `time_of_day`: Extracted time (e.g., "DAY", "NIGHT")
- `dialogue_lines`: List of Dialogue objects
- `action_lines`: List of action descriptions

### SearchResult

Represents a single search result.

**Key Attributes:**

- `script_title`: Title of the matching screenplay
- `scene_id`: Unique database ID for the scene
- `scene_number`: Scene number within the script
- `scene_heading`: Full scene heading
- `scene_content`: Scene text content
- `match_type`: Type of match ("text", "dialogue", "action", "vector")
- `relevance_score`: Relevance score (higher is better)
- `matched_text`: The specific text that matched

### SearchResponse

Complete search response containing all results.

**Attributes:**

- `results`: List of SearchResult objects
- `total_count`: Total number of matching results
- `query`: The parsed query used for search


## Common Patterns

### Error Handling

```python
from scriptrag.exceptions import DatabaseError, ParseError

def safe_index(rag, file_path):
    """Safely index a screenplay with error handling."""
    try:
        script = rag.parse_fountain(file_path)
        result = rag.index_script(file_path)
        if result["indexed"]:
            return result["script_id"]
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except ParseError as e:
        print(f"Parse error: {e}")
    except DatabaseError as e:
        print(f"Database error: {e.message}")
    return None
```

### Progress Tracking

```python
from scriptrag import ScriptRAG

# Simple progress callback
def show_progress(current, total, message):
    percent = (current / total * 100) if total > 0 else 0
    bar_length = 40
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r[{bar}] {percent:.1f}% - {message}", end='', flush=True)
    if current >= total:
        print()  # New line when complete

# Use with indexing
result = rag.index_directory(
    "./screenplays",
    progress_callback=show_progress
)
```

### Batch Processing

```python
from pathlib import Path
from scriptrag import ScriptRAG

rag = ScriptRAG()

# Process multiple directories
directories = ["./tv_scripts", "./feature_films", "./shorts"]

for directory in directories:
    path = Path(directory)
    if path.exists():
        print(f"\nProcessing {directory}...")
        result = rag.index_directory(path)
        print(f"  Indexed: {result['scripts_indexed']} scripts")
        print(f"  Scenes: {result['scenes_indexed']} total")
```

### Advanced Search

```python
from scriptrag import ScriptRAG

rag = ScriptRAG()

# Complex search with multiple keywords
def find_theme_scenes(rag, theme_keywords, project=None):
    """Find scenes matching thematic keywords."""
    all_results = []
    seen_ids = set()

    for keyword in theme_keywords:
        results = rag.search(
            keyword,
            project=project,
            mode="fuzzy",
            limit=5
        )
        for result in results.results:
            if result.scene_id not in seen_ids:
                seen_ids.add(result.scene_id)
                all_results.append(result)

    return all_results

# Find romantic scenes
romantic = find_theme_scenes(
    rag,
    ["love", "kiss", "romantic", "heart"],
    project="My Rom-Com"
)
print(f"Found {len(romantic)} romantic scenes")
```

## Exceptions

### DatabaseError

Raised when database operations fail. Contains `message` and `hint` attributes.

### ParseError  

Raised when Fountain parsing fails. Contains error details about the parsing issue.

## Configuration

The ScriptRAG API can be configured through:

1. **Environment Variables**: Set `SCRIPTRAG_*` variables
2. **Configuration Files**: Use `.scriptrag.yaml`, `.scriptrag.toml`, or `.scriptrag.json`
3. **Code**: Pass `ScriptRAGSettings` to the constructor

Example configuration file (`.scriptrag.yaml`):

```yaml
database:
  path: ~/screenplays.db
  timeout: 60.0
  wal_mode: true

search:
  default_limit: 20
  vector_threshold: 3

llm:
  provider: github
  github_token: ${GITHUB_TOKEN}
  model: gpt-4o-mini
```

## See Also

- [User Guide](user-guide.md) - Complete guide for screenwriters
- [CLI Reference](cli-reference.md) - Command-line interface documentation
- [MCP Server Documentation](mcp_server.md) - AI assistant integration
- [Architecture Overview](architecture.md) - System design details
