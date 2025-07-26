# Claude Coding Guidelines for ScriptRAG

This document establishes essential coding standards and development guidelines
for Claude when working on the ScriptRAG project. With specialized sub-agents
now available, this focuses on immediate code creation rules while delegating
specialized work to appropriate experts.

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

## 🤖 Sub-Agent Delegation

**Delegate specialized work to expert sub-agents:**

- **Code Quality Issues** → Use `ruff-fixer` for Python linting problems
- **Type Checking** → Use `mypy-fixer` for type annotation issues  
- **Test Failures** → Use `test-fixer` for pytest debugging and fixes
- **Documentation** → Use `docstring-writer` for comprehensive docstrings
- **Commit Messages** → Use `commit-crafter` for movie quote commit messages
- **Project Updates** → Use `project-updater` for README/roadmap maintenance
- **Screenplay Domain** → Use `screenplay-expert` for Fountain format expertise

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
3. **Delegate Specialized Tasks** - Use appropriate sub-agents for quality/domain work
4. **Test Thoroughly** - Write/update tests (delegate test fixes to `test-fixer`)
5. **Quality Check** - Run linting and type checking (delegate fixes to specialists)
6. **Commit Properly** - Delegate to `commit-crafter` for proper commit messages

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

## 🧑‍💻 Essential Coding Standards

### **Python Code Style (Immediate Rules)**

- **Line Length**: 88 characters (Black standard)
- **Quotes**: Double quotes for strings (`"hello"` not `'hello'`)
- **Indentation**: 4 spaces, no tabs
- **Line Endings**: LF only (Unix style)

### **Type Annotations (Required)**

```python
# ✅ GOOD - Complete type annotations
def parse_fountain(self, path: str) -> ScriptModel:
    """Parse fountain file and return script model."""

# ❌ BAD - Missing types (delegate to mypy-fixer)
def parse_fountain(self, path):
    pass
```

### **Configuration Management**

```python
# ✅ GOOD - Use the settings system consistently
from scriptrag.config import get_settings, get_logger

class MyComponent:
    def __init__(self, config: ScriptRAGSettings | None = None):
        self.config = config or get_settings()
        self.logger = get_logger(__name__)
```

### **Error Handling**

```python
# ✅ GOOD - Specific exception handling with logging
try:
    script = self.fountain_parser.parse(path)
except FountainParseError as e:
    self.logger.error("Failed to parse fountain file", path=path, error=str(e))
    raise ScriptRAGError(f"Parse failed for {path}: {e}") from e
```

## 🗃️ Project Structure

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
"""Module docstring."""

# Standard library imports
import json
from pathlib import Path
from typing import Any

# Third-party imports
import typer
from pydantic import BaseModel

# Local imports
from scriptrag.config import get_settings
from scriptrag.models import Scene

# Module-level constants
DEFAULT_TIMEOUT = 30
```

## 🔧 Quality Assurance

### **Required Commands (Run Before Commits)**

```bash
make test           # Full test suite with coverage
make lint          # All linting checks (delegate fixes to ruff-fixer)
make type-check    # Type checking (delegate fixes to mypy-fixer)
make security      # Security scans
```

### **Code Coverage Requirements**

- Maintain >80% code coverage for new code
- Write both unit and integration tests
- Test error conditions and edge cases

## 🚀 Essential Development Commands

```bash
# Setup and maintenance
make setup-dev          # Complete dev environment setup
make update             # Update all dependencies

# Code quality (run before commits)
make format             # Format code with black/ruff
make lint              # Run all linters
make type-check        # Type checking with mypy
make check             # Run all quality checks

# Testing
make test              # Full test suite with coverage
make test-fast         # Quick tests without coverage

# Project-specific
make db-init           # Initialize database
make run               # Run CLI application
make run-mcp          # Run MCP server
```

## 📚 Quick Reference

### **Key Files to Check**

- **README.md**: Project roadmap and architecture
- **AGENTS.md**: Commit message guidelines and project rules
- **Database Schema**: `src/scriptrag/database/schema.py`
- **Configuration**: `src/scriptrag/config/settings.py`

### **Domain Knowledge Resources**

- **Fountain Format**: <https://fountain.io/>
- **GraphRAG Pattern**: Graph + Retrieval-Augmented Generation
- **Screenplay Structure**: Acts, scenes, characters, dialogue, action

## 🎭 Remember

This is a sophisticated screenwriting tool combining software engineering with
screenplay domain knowledge. When working on ScriptRAG:

1. **Respect the craft** - Screenwriting has specific conventions
2. **Think in graphs** - Characters, scenes, and relationships form networks
3. **Plan for scale** - Professional scripts have hundreds of scenes
4. **Maintain quality** - High standards throughout
5. **Use sub-agents** - Delegate specialized work to experts

**When in doubt, delegate to the appropriate sub-agent rather than guessing.**

Remember: *"In every job that must be done, there is an element of fun."* -
Mary Poppins, Mary Poppins (1964)

---

*This document focuses on immediate coding needs. Detailed guidelines are
handled by specialized sub-agents - use them liberally!*
