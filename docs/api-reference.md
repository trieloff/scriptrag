# ScriptRAG v2 API Reference

The ScriptRAG v2 API provides a comprehensive Python interface for parsing, indexing, and searching screenplay content. This document covers the main `ScriptRAG` class and its methods.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [ScriptRAG Class](#scriptrag-class)
  - [Initialization](#initialization)
  - [parse_fountain()](#parse_fountain)
  - [index_script()](#index_script)
  - [index_directory()](#index_directory)
  - [search()](#search)
- [Data Models](#data-models)
- [Exceptions](#exceptions)
- [Examples](#examples)

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

# Initialize ScriptRAG with automatic database setup
rag = ScriptRAG(auto_init_db=True)

# Parse a Fountain screenplay
script = rag.parse_fountain("path/to/screenplay.fountain")
print(f"Parsed '{script.title}' with {len(script.scenes)} scenes")

# Index the screenplay into the database
result = rag.index_script("path/to/screenplay.fountain")
print(f"Indexed {result['scenes_indexed']} scenes")

# Search the indexed content
search_results = rag.search("coffee shop", limit=5)
for result in search_results.results:
    print(f"Scene {result.scene_number}: {result.scene_heading}")
```

## ScriptRAG Class

### Initialization

```python
ScriptRAG(
    settings: ScriptRAGSettings | None = None,
    auto_init_db: bool = True
)
```

Creates a new ScriptRAG instance.

**Parameters:**

- `settings` (ScriptRAGSettings, optional): Configuration settings. Uses defaults if not provided.
- `auto_init_db` (bool): Automatically initialize database if it doesn't exist. Default: `True`.

**Example:**

```python
from scriptrag import ScriptRAG
from scriptrag.config import ScriptRAGSettings

# Using default settings
rag = ScriptRAG()

# Using custom settings
settings = ScriptRAGSettings(
    database_path="/custom/path/scriptrag.db",
    database_timeout=60.0
)
rag = ScriptRAG(settings=settings)

# Skip auto database initialization
rag = ScriptRAG(auto_init_db=False)
```

### parse_Fountain()

```python
parse_fountain(path: str | Path) -> Script
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
# Parse a screenplay
script = rag.parse_fountain("screenplay.fountain")

# Access parsed data
print(f"Title: {script.title}")
print(f"Author: {script.author}")
print(f"Number of scenes: {len(script.scenes)}")

# Iterate through scenes
for scene in script.scenes:
    print(f"Scene {scene.number}: {scene.heading}")
    print(f"  Location: {scene.location}")
    print(f"  Time: {scene.time_of_day}")

    # Access dialogue
    for dialogue in scene.dialogue_lines:
        print(f"  {dialogue.character}: {dialogue.text}")
```

### index_script()

```python
index_script(
    path: str | Path,
    dry_run: bool = False
) -> dict[str, Any]
```

Indexes a Fountain screenplay into the database for searching.

**Parameters:**

- `path` (str | Path): Path to the Fountain file to index
- `dry_run` (bool): If True, preview changes without applying them. Default: `False`.

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
# Index a screenplay
result = rag.index_script("screenplay.fountain")

if result["indexed"]:
    print(f"Successfully indexed script ID: {result['script_id']}")
    print(f"Scenes: {result['scenes_indexed']}")
    print(f"Characters: {result['characters_indexed']}")
    print(f"Dialogues: {result['dialogues_indexed']}")
else:
    print(f"Indexing failed: {result['error']}")

# Dry run to preview
preview = rag.index_script("screenplay.fountain", dry_run=True)
print(f"Would index {preview['scenes_indexed']} scenes")
```

### index_directory()

```python
index_directory(
    path: str | Path | None = None,
    recursive: bool = True,
    dry_run: bool = False,
    batch_size: int = 10
) -> dict[str, Any]
```

Indexes all Fountain files in a directory.

**Parameters:**

- `path` (str | Path | None): Directory path to search. Default: current directory.
- `recursive` (bool): Search subdirectories recursively. Default: `True`.
- `dry_run` (bool): Preview changes without applying them. Default: `False`.
- `batch_size` (int): Number of scripts to process per batch. Default: `10`.

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
```

### search()

```python
search(
    query: str,
    mode: SearchMode | str = SearchMode.AUTO,
    limit: int = 10,
    offset: int = 0,
    character: str | None = None,
    location: str | None = None,
    dialogue: str | None = None,
    project: str | None = None,
    include_bible: bool = True,
    only_bible: bool = False
) -> SearchResponse
```

Searches indexed screenplay content.

**Parameters:**

- `query` (str): Search query string
- `mode` (SearchMode | str): Search mode - 'strict', 'fuzzy', or 'auto'. Default: 'auto'.
- `limit` (int): Maximum results to return. Default: `10`.
- `offset` (int): Results to skip for pagination. Default: `0`.
- `character` (str | None): Filter by character name
- `location` (str | None): Filter by scene location
- `dialogue` (str | None): Search specifically for dialogue
- `project` (str | None): Filter by project name
- `include_bible` (bool): Include reference content. Default: `True`.
- `only_bible` (bool): Search only reference content. Default: `False`.

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
    print(f"  {result.scene_content[:100]}...")

# Search with filters
results = rag.search(
    "important dialogue",
    character="SARAH",
    location="OFFICE",
    limit=5
)

# Fuzzy search for similar content
results = rag.search(
    "romantic conversation",
    mode="fuzzy",
    limit=10
)

# Pagination
page1 = rag.search("INT.", limit=10, offset=0)
page2 = rag.search("INT.", limit=10, offset=10)

# Search only in specific project
results = rag.search(
    "conflict",
    project="My Screenplay",
    mode="strict"
)
```

## Data Models

### Script

Represents a parsed screenplay:

```python
@dataclass
class Script:
    title: str | None
    author: str | None
    scenes: list[Scene]
    metadata: dict[str, Any]
```

### Scene

Represents a scene in a screenplay:

```python
@dataclass
class Scene:
    number: int
    heading: str
    content: str
    original_text: str
    content_hash: str
    type: str  # "INT" or "EXT"
    location: str
    time_of_day: str
    dialogue_lines: list[Dialogue]
    action_lines: list[str]
    boneyard_metadata: dict[str, Any] | None
```

### Dialogue

Represents a dialogue entry:

```python
@dataclass
class Dialogue:
    character: str
    text: str
    parenthetical: str | None
```

### SearchResult

Individual search result:

```python
@dataclass
class SearchResult:
    script_id: int
    script_title: str
    script_author: str | None
    scene_id: int
    scene_number: int
    scene_heading: str
    scene_location: str | None
    scene_time: str | None
    scene_content: str
    season: int | None
    episode: int | None
    match_type: str  # "text", "dialogue", "action", "vector"
    relevance_score: float
    matched_text: str | None
    character_name: str | None
```

### SearchResponse

Complete search response:

```python
@dataclass
class SearchResponse:
    query: SearchQuery
    results: list[SearchResult]
    bible_results: list[BibleSearchResult]
    total_count: int
    bible_total_count: int
```

## Exceptions

### DatabaseError

Raised when database operations fail:

```python
from scriptrag.exceptions import DatabaseError

try:
    rag.search("query")
except DatabaseError as e:
    print(f"Database error: {e.message}")
    print(f"Hint: {e.hint}")
```

### ParseError

Raised when Fountain parsing fails:

```python
from scriptrag.exceptions import ParseError

try:
    script = rag.parse_fountain("invalid.fountain")
except ParseError as e:
    print(f"Parse error: {e}")
```

## Examples

### Complete Workflow

```python
from scriptrag import ScriptRAG
from scriptrag.config import ScriptRAGSettings
from pathlib import Path

# 1. Initialize with custom settings
settings = ScriptRAGSettings(
    database_path=Path.home() / "screenplays.db",
    database_timeout=60.0,
    llm_provider="github",
    github_token="your-token"
)
rag = ScriptRAG(settings=settings)

# 2. Index a directory of screenplays
result = rag.index_directory(
    Path.home() / "Documents/Screenplays",
    recursive=True,
    batch_size=5
)
print(f"Indexed {result['total_scripts_indexed']} screenplays")

# 3. Search for specific content
# Find all coffee shop scenes
coffee_scenes = rag.search("coffee shop", limit=20)

# Find dialogue by a specific character
sarah_dialogue = rag.search(
    "love",
    character="SARAH",
    mode="fuzzy"
)

# Find action sequences
action_scenes = rag.search(
    "fight OR chase OR explosion",
    mode="strict"
)

# 4. Analyze results
for result in coffee_scenes.results:
    print(f"\nScript: {result.script_title}")
    print(f"Scene {result.scene_number}: {result.scene_heading}")
    if result.matched_text:
        print(f"Matched: ...{result.matched_text}...")
```

### Batch Processing

```python
from pathlib import Path

# Process multiple directories
directories = [
    Path("./tv_scripts"),
    Path("./feature_films"),
    Path("./short_films")
]

for directory in directories:
    if directory.exists():
        print(f"\nProcessing {directory}...")
        result = rag.index_directory(directory)
        print(f"  Indexed: {result['total_scripts_indexed']}")
        print(f"  Scenes: {result['total_scenes_indexed']}")
```

### Error Handling

```python
from scriptrag.exceptions import DatabaseError, ParseError

def safe_index(rag, file_path):
    """Safely index a screenplay with error handling."""
    try:
        # First try to parse
        script = rag.parse_fountain(file_path)
        print(f"Parsed: {script.title}")

        # Then index
        result = rag.index_script(file_path)
        if result["indexed"]:
            print(f"Indexed successfully: {result['script_id']}")
        else:
            print(f"Indexing failed: {result['error']}")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except ParseError as e:
        print(f"Parse error in {file_path}: {e}")
    except DatabaseError as e:
        print(f"Database error: {e.message}")
        print(f"Hint: {e.hint}")
    except Exception as e:
        print(f"Unexpected error: {e}")

# Use the safe function
safe_index(rag, "screenplay.fountain")
```

### Custom Search Queries

```python
# Complex search with multiple filters
def find_romantic_scenes(rag, project_name):
    """Find romantic scenes in a specific project."""

    keywords = [
        "love", "kiss", "romantic", "heart",
        "embrace", "passion", "romance"
    ]

    all_results = []
    for keyword in keywords:
        results = rag.search(
            keyword,
            project=project_name,
            mode="fuzzy",
            limit=5
        )
        all_results.extend(results.results)

    # Deduplicate by scene_id
    seen = set()
    unique_results = []
    for result in all_results:
        if result.scene_id not in seen:
            seen.add(result.scene_id)
            unique_results.append(result)

    return unique_results

# Use the custom search
romantic = find_romantic_scenes(rag, "My Rom-Com")
print(f"Found {len(romantic)} romantic scenes")
```

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
