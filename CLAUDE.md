# Claude Coding Guidelines for ScriptRAG

This document establishes coding standards, best practices, and development
guidelines for Claude when working on the ScriptRAG project. These guidelines
ensure consistency, maintainability, and alignment with the project's
architecture and philosophy.

## 🎯 Core Principles

### 1. **Quality First**

- Always maintain the existing high code quality standards
- Follow the established testing patterns (839+ lines of comprehensive tests)
- Ensure all code passes the extensive pre-commit hook suite
- Write self-documenting code with clear intention

### 2. **Consistency with Project Architecture**

- Respect the 10-phase development roadmap structure
- Follow the established patterns in database schema and CLI design
- Maintain the GraphRAG pattern throughout all implementations
- Use the project's configuration system consistently

### 3. **Screenplay Domain Expertise**

- Understand that this is a screenwriting tool with specific domain needs
- Respect the Fountain format specifications and screenplay conventions
- Consider temporal, logical, and script ordering in scene management
- Design with screenwriters' workflows in mind

## 📋 Development Process

### **Pre-Development Checklist**

Before writing any code, Claude must:

1. **Check Project Diagnostics** (per AGENTS.md Rule 2)

   ```bash
   make check-fast  # Quick quality checks
   ```

2. **Ensure Clean Working Copy**

   ```bash
   git status  # Should show clean working directory
   ```

3. **Verify Environment Setup**

   ```bash
   make setup-dev  # If needed
   source .venv/bin/activate
   ```

### **Development Workflow**

1. **Plan Implementation** - Create clear, actionable todos using TodoWrite
2. **Write Code** - Follow coding standards below (auto-formatting hooks active)
3. **Test Thoroughly** - Write/update tests for all changes
4. **Quality Check** - Run linting and type checking
5. **Commit Properly** - Follow the movie quote commit convention

### **Auto-Formatting Hooks**

This project includes Claude Code hooks that automatically format code when
files are modified. The hooks are configured in `.claude/config.json` and run
after Write/Edit/MultiEdit operations:

- **Python files**: Automatically formatted with Black and Ruff
- **Markdown files**: Fixed with markdownlint
- **JSON/YAML files**: Formatted and validated
- **All files**: Trailing whitespace removed, proper line endings ensured

**Hook Scripts**:

- `.claude/hooks/auto-format.sh` - Comprehensive formatting for all file types
- `.claude/hooks/format-python.sh` - Fast Python-only formatting

**Configuration Options**:

- `.claude/config.json` - Full auto-formatting (default)
- `.claude/config-python-only.json` - Python-only formatting (faster)

## 🧑‍💻 Coding Standards

### **Python Code Style**

#### **Formatting**

- **Line Length**: 88 characters (Black standard)
- **Quotes**: Double quotes for strings (`"hello"` not `'hello'`)
- **Indentation**: 4 spaces, no tabs
- **Line Endings**: LF only (Unix style)

#### **Type Annotations**

```python
# ✅ GOOD - Complete type annotations
def parse_fountain(self, path: str) -> ScriptModel:
    """Parse fountain file and return script model."""

def search_scenes(
    self,
    query: str,
    filters: dict[str, Any] | None = None
) -> list[Scene]:
    """Search scenes with optional filters."""

# ❌ BAD - Missing or incomplete types
def parse_fountain(self, path):
    pass

def search_scenes(self, query, filters=None):
    pass
```

#### **Documentation Standards**

```python
# ✅ GOOD - Google-style docstrings
def create_scene_graph(
    self,
    scene: Scene,
    script_node_id: str
) -> str:
    """Create scene node and connect to script graph.

    Args:
        scene: Scene object to create node for
        script_node_id: ID of parent script node

    Returns:
        ID of created scene node

    Raises:
        DatabaseError: If node creation fails
        ValidationError: If scene data is invalid
    """
```

#### **Error Handling**

```python
# ✅ GOOD - Specific exception handling with logging
try:
    script = self.fountain_parser.parse(path)
except FountainParseError as e:
    self.logger.error("Failed to parse fountain file", path=path, error=str(e))
    raise ScriptRAGError(f"Parse failed for {path}: {e}") from e

# ❌ BAD - Broad exception catching
try:
    script = self.fountain_parser.parse(path)
except Exception:
    pass
```

#### **Database Operations**

```python
# ✅ GOOD - Use connection context managers and proper transaction handling
async def create_character(self, character: Character) -> str:
    """Create character in database."""
    async with self.db.transaction() as conn:
        char_id = await conn.execute(
            "INSERT INTO characters (id, name, description) VALUES (?, ?, ?)",
            (character.id, character.name, character.description)
        )
        await self._create_character_node(char_id, conn)
        return char_id

# ❌ BAD - Direct database access without proper transaction handling
def create_character(self, character):
    conn = sqlite3.connect(self.db_path)
    conn.execute("INSERT INTO characters ...")
    conn.close()
```

### **Configuration Management**

```python
# ✅ GOOD - Use the settings system consistently
from scriptrag.config import get_settings, get_logger

class MyComponent:
    def __init__(self, config: ScriptRAGSettings | None = None):
        self.config = config or get_settings()
        self.logger = get_logger(__name__)

# ❌ BAD - Hard-coded configuration
class MyComponent:
    def __init__(self):
        self.db_path = "./screenplay.db"  # Hard-coded
```

### **Testing Patterns**

#### **Test Structure**

```python
# ✅ GOOD - Follow existing test patterns
class TestSceneOperations:
    """Test scene-related operations."""

    def test_create_scene_with_valid_data(self, db_connection, sample_scene):
        """Test creating scene with valid data."""
        # Arrange
        graph_ops = GraphOperations(db_connection)

        # Act
        scene_id = graph_ops.create_scene_node(sample_scene, "script-123")

        # Assert
        assert scene_id is not None
        scene_node = graph_ops.graph.get_node(scene_id)
        assert scene_node.node_type == "scene"
        assert scene_node.properties["script_order"] == sample_scene.script_order

    def test_create_scene_with_invalid_data(self, db_connection):
        """Test creating scene with invalid data raises appropriate error."""
        graph_ops = GraphOperations(db_connection)

        with pytest.raises(ValidationError, match="Invalid scene data"):
            graph_ops.create_scene_node(None, "script-123")
```

#### **Fixture Usage**

```python
# ✅ GOOD - Reuse existing fixtures, create new ones following patterns
@pytest.fixture
def sample_dialogue_element():
    """Create sample dialogue element for testing."""
    return SceneElement(
        element_type="dialogue",
        text="Hello, world!",
        character_name="PROTAGONIST",
        order_in_scene=1
    )
```

## 🗃️ Project-Specific Conventions

### **Module Organization**

```text
src/scriptrag/
├── __init__.py          # Main API exports
├── cli.py              # Command-line interface
├── mcp_server.py       # MCP server implementation
├── config/             # Configuration management
├── database/           # Database layer (schema, operations, graph)
├── models/             # Data models and types
├── parser/             # Fountain format parsing
└── llm/               # LLM integration (future)
```

### **Import Organization**

```python
# ✅ GOOD - Follow import ordering
"""Module docstring."""

# Standard library imports
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Third-party imports
import networkx as nx
import typer
from pydantic import BaseModel, Field
from rich.console import Console

# Local imports
from scriptrag.config import get_logger, get_settings
from scriptrag.database import GraphDatabase
from scriptrag.models import Scene, Character, Script

# Module-level constants
DEFAULT_TIMEOUT = 30
```

### **Database Schema Adherence**

- Always use the established schema in `database/schema.py`
- Respect foreign key relationships and constraints
- Use proper JSON fields for flexible metadata storage
- Follow the graph database patterns (nodes/edges tables)

### **CLI Command Patterns**

```python
# ✅ GOOD - Follow established CLI patterns
@script_app.command("analyze")
def script_analyze(
    script_path: Annotated[
        Path,
        typer.Argument(help="Path to screenplay file", exists=True)
    ],
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (json, yaml, text)")
    ] = "text",
) -> None:
    """Analyze screenplay structure and characters."""
    try:
        settings = get_settings()
        console.print(f"[blue]Analyzing screenplay:[/blue] {script_path}")

        # Implementation here

        console.print("[green]✓[/green] Analysis complete")

    except Exception as e:
        console.print(f"[red]Error analyzing screenplay:[/red] {e}")
        raise typer.Exit(1) from e
```

## 🔧 Quality Assurance

### **Required Tools Integration**

#### **Pre-commit Hooks**

All code must pass the comprehensive pre-commit hook suite:

- **Black**: Code formatting (88 char lines)
- **Ruff**: Linting and import sorting
- **MyPy**: Type checking
- **Bandit**: Security scanning
- **Codespell**: Spell checking
- **Detect-secrets**: Secret detection

#### **Testing Requirements**

```bash
# Run before committing
make test           # Full test suite with coverage
make lint          # All linting checks
make type-check    # Type checking
make security      # Security scans
```

#### **Code Coverage**

- Maintain >80% code coverage for new code
- Write both unit and integration tests
- Test error conditions and edge cases

### **Performance Considerations**

#### **Database Queries**

```python
# ✅ GOOD - Efficient queries with proper indexing
def get_character_scenes(self, character_id: str) -> list[Scene]:
    """Get scenes where character appears (uses index)."""
    return self.db.fetch_all(
        """
        SELECT s.* FROM scenes s
        JOIN scene_elements se ON s.id = se.scene_id
        WHERE se.character_id = ?
        ORDER BY s.script_order
        """,
        (character_id,)
    )

# ❌ BAD - Inefficient queries
def get_character_scenes(self, character_id: str) -> list[Scene]:
    """Inefficient - loads all scenes then filters."""
    all_scenes = self.db.fetch_all("SELECT * FROM scenes")
    return [s for s in all_scenes if character_id in s.character_ids]
```

#### **Memory Management**

```python
# ✅ GOOD - Process large datasets in chunks
async def embed_all_scenes(self, batch_size: int = 100) -> None:
    """Embed scenes in batches to manage memory."""
    for scenes_batch in self.get_scenes_in_batches(batch_size):
        embeddings = await self.llm_client.embed_batch(scenes_batch)
        await self.store_embeddings(embeddings)

# ❌ BAD - Load everything into memory
async def embed_all_scenes(self) -> None:
    all_scenes = self.get_all_scenes()  # Could be thousands
    embeddings = await self.llm_client.embed_batch(all_scenes)
```

## 🎬 Screenplay Domain Guidelines

### **Fountain Format Handling**

```python
# ✅ GOOD - Respect fountain format conventions
def parse_scene_heading(self, heading: str) -> SceneLocation:
    """Parse scene heading following fountain spec."""
    # INT./EXT. LOCATION - TIME format
    match = re.match(r'^(INT|EXT)\.\s+(.+?)\s+-\s+(.+)$', heading.strip())
    if not match:
        raise FountainFormatError(f"Invalid scene heading: {heading}")

    return SceneLocation(
        interior=(match.group(1) == "INT"),
        name=match.group(2).strip(),
        time_of_day=match.group(3).strip(),
        raw_text=heading
    )
```

### **Scene Ordering Systems**

```python
# ✅ GOOD - Support all three ordering systems
class SceneOrderType(Enum):
    """Types of scene ordering."""
    SCRIPT = "script"      # Order as written in script
    TEMPORAL = "temporal"  # Chronological order in story
    LOGICAL = "logical"    # Logical/causal dependencies

def get_scenes_ordered(
    self,
    script_id: str,
    order_type: SceneOrderType
) -> list[Scene]:
    """Get scenes in specified order."""
    order_column = f"{order_type.value}_order"
    return self.db.fetch_all(
        f"SELECT * FROM scenes WHERE script_id = ? ORDER BY {order_column}",
        (script_id,)
    )
```

### **Character Relationship Modeling**

```python
# ✅ GOOD - Model complex character relationships
def create_character_interaction(
    self,
    char1_id: str,
    char2_id: str,
    scene_id: str,
    interaction_type: str = "dialogue",
    metadata: dict[str, Any] | None = None
) -> str:
    """Create character interaction edge in graph."""
    properties = {
        "interaction_type": interaction_type,
        "scene_id": scene_id,
        **(metadata or {})
    }

    return self.graph.add_edge(
        from_node_id=char1_id,
        to_node_id=char2_id,
        edge_type="INTERACTS_WITH",
        properties=properties
    )
```

## 💬 Commit Message Guidelines

Following AGENTS.md, all commits must include semantic commit format with
movie quotes:

```text
feat(parser): add support for dual dialogue parsing

Implemented parsing for dual dialogue sections in Fountain format,
allowing characters to speak simultaneously in split-screen scenarios.

"Roads? Where we're going, we don't need roads." - Doc Brown, Back to the Future (1985)
```

### **Commit Types for ScriptRAG Context**

- `feat(parser)`: New Fountain parsing features
- `feat(database)`: New database/graph functionality  
- `feat(cli)`: New CLI commands or options
- `feat(mcp)`: MCP server features
- `fix(schema)`: Database schema fixes
- `fix(query)`: Query optimization fixes
- `refactor(graph)`: Graph operations improvements
- `test(scene)`: Scene-related test additions
- `docs(api)`: API documentation updates

## 🚀 Development Commands

### **Essential Make Commands**

```bash
# Setup and maintenance
make setup-dev          # Complete dev environment setup
make update             # Update all dependencies

# Code quality (run before commits)
make format             # Format code with black/ruff
make lint              # Run all linters
make type-check        # Type checking with mypy
make check             # Run all quality checks
make pre-commit        # Run pre-commit on all files

# Testing
make test              # Full test suite with coverage
make test-fast         # Quick tests without coverage
make test-parallel     # Parallel test execution

# Project-specific
make parse-fountain FILE=script.fountain  # Parse fountain file
make db-init           # Initialize database
make run               # Run CLI application
make run-mcp          # Run MCP server

# Claude Code Hooks (manual testing)
.claude/hooks/auto-format.sh              # Test comprehensive auto-formatting
.claude/hooks/format-python.sh FILE.py    # Test Python-only formatting
```

## 📚 Learning Resources

### **Key Documentation to Reference**

- **README.md**: Full project roadmap and architecture
- **AGENTS.md**: Commit message guidelines and project rules
- **Database Schema**: `src/scriptrag/database/schema.py`
- **Configuration**: `src/scriptrag/config/settings.py`
- **Test Patterns**: `tests/test_database.py` (839+ lines of examples)

### **Domain Knowledge**

- **Fountain Format**: <https://fountain.io/>
- **GraphRAG Pattern**: Graph + Retrieval-Augmented Generation
- **Screenplay Structure**: Acts, scenes, characters, dialogue, action
- **LMStudio Integration**: OpenAI-compatible local LLM serving

## 🎭 Final Notes

This is a sophisticated screenwriting tool that combines traditional software
engineering with domain-specific screenplay knowledge. When working on
ScriptRAG:

1. **Respect the craft** - Screenwriting has specific conventions and workflows
2. **Think in graphs** - Characters, scenes, and relationships form complex networks
3. **Plan for scale** - Professional scripts can have hundreds of scenes
   and characters
4. **Maintain quality** - This project has high standards - keep them high
5. **Follow the roadmap** - We're in Phase 3 of 10, respect the planned
   architecture

Remember: *"In every job that must be done, there is an element of fun."* -
Mary Poppins, Mary Poppins (1964)

---

*This document is living and should be updated as the project evolves.
Always check for the latest version before starting significant work.*
