# Claude Coding Guidelines for ScriptRAG v2

This document establishes essential coding standards and development guidelines
for Claude when working on the ScriptRAG project - a Git-native screenplay
analysis system. With specialized sub-agents and distributed CLAUDE.md files
across 17 modules, this focuses on immediate code creation rules while
delegating specialized work to appropriate experts.

**Codebase Scale**: 20+ Python modules, 86+ tests, 2230+ lines of test code

## 🎯 Core Principles

### 1. **Quality First**

- Always maintain the existing high code quality standards
- Follow the established testing patterns (2230+ lines of comprehensive tests)
- Ensure all code passes the extensive pre-commit hook suite
- Write self-documenting code with clear intention
- Be aware of common iteration points from recent development

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
- Handle boneyard metadata sections for Git integration
- Maintain character capitalization consistency

## 🤖 Sub-Agent Delegation

**Delegate specialized work to expert sub-agents:**

- **Code Quality Issues** → Use `ruff-house` for Python linting problems
- **Type Checking** → Use `type-veronica` for type annotation issues  
- **Test Failures** → Use `test-holmes` or `test-mycroft` for pytest debugging
- **Documentation** → Use `docstring-rogers` for comprehensive docstrings
- **Commit Messages** → Use `commit-quentin` for movie quote commit messages
- **Project Updates** → Use `project-lumbergh` for README/roadmap maintenance
- **Screenplay Domain** → Use `screenplay-sorkin` for Fountain format expertise
- **CI/CD Analysis** → Use `ci-mulder` for build failure investigation

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

- **Python files**: Automatically formatted with Ruff
- **Markdown files**: Fixed with markdownlint
- **JSON/YAML files**: Formatted and validated
- **All files**: Trailing whitespace removed, proper line endings ensured

**Hook Scripts**:

- `.claude/hooks/auto-format.sh` - Comprehensive formatting for all file types
- `.claude/hooks/format-python.sh` - Fast Python-only formatting

## 🧑‍💻 Essential Coding Standards

### **Python Code Style (Immediate Rules)**

- **Line Length**: 88 characters (Ruff standard)
- **Quotes**: Double quotes for strings (`"hello"` not `'hello'`)
- **Indentation**: 4 spaces, no tabs
- **Line Endings**: LF only (Unix style)

### **File Size Limits (MCP Compatibility)**

To ensure MCP tools can effectively read and process our code, Python files must adhere to these size limits:

- **Regular Python files**:
  - Soft limit: 1000 lines (warning - consider refactoring)
  - Hard limit: 1500 lines (error - must refactor)
- **Test files**:
  - Hard limit: 2000 lines (error - must split)

**Why these limits?**

- MCP tools have token limitations when reading files
- Smaller files are easier to understand and maintain
- Encourages modular design and single responsibility principle

**When to refactor large files:**

1. Split by functionality or responsibility
2. Extract common utilities to separate modules
3. Use composition and delegation patterns
4. Create sub-modules for complex features

**Current file size guidelines:**

- **Regular modules**: Max 600 lines (largest current: `database_operations.py` at 536 lines)
- **API modules**: Max 600 lines (current: `index.py` at 518 lines)
- **LLM providers**: Max 600 lines (complex error handling and rate limiting)
- **Parser modules**: Max 500 lines (Fountain parser at 441 lines)
- **Test files**: Max 500 lines per test module for maintainability

### **Type Annotations (Required)**

```python
# ✅ GOOD - Complete type annotations with proper async typing
async def parse_fountain(self, path: str) -> ScriptModel:
    """Parse fountain file and return script model."""

# ✅ GOOD - Complex generic types for LLM providers
T = TypeVar("T", bound="BaseLLMProvider")
class LLMClient(Generic[T]):
    providers: dict[str, T]

# ❌ BAD - Missing types (delegate to type-veronica)
def parse_fountain(self, path):
    pass
```

**Common Type Issues (from recent iterations):**
- LLM provider hierarchies require careful generic typing
- Async operations need explicit return type annotations
- Mock types in tests can cause mypy false positives

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

# ✅ GOOD - LLM rate limiting with exponential backoff
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_llm_with_retry(self, prompt: str) -> str:
    try:
        return await self.llm_client.complete(prompt)
    except RateLimitError as e:
        self.logger.warning("Rate limit hit", wait_time=e.retry_after)
        raise
```

**Common Error Patterns:**
- **LLM APIs**: Rate limiting, timeouts, JSON parsing failures
- **Fountain Parsing**: Malformed metadata, character extraction
- **Git Operations**: LFS issues, boneyard processing errors

## 🗃️ Project Structure

### **Module Organization**

```text
src/scriptrag/
├── __init__.py          # Main API exports
├── api/                # Core API layer
│   ├── database_operations.py  # Complex SQL/graph operations (536 lines)
│   └── index.py        # Core indexing functionality (518 lines)
├── config/             # Configuration management
├── database/           # Database layer (schema, operations, graph)
├── llm/                # LLM integration layer
│   ├── client.py       # Multi-provider abstraction (490 lines)
│   └── providers/      # Provider implementations
│       ├── claude_code.py      # Claude integration (506 lines)
│       └── github_models.py    # GitHub Models API (438 lines)
├── models/             # Data models and types
├── parser/             # Fountain format parsing
│   └── fountain_parser.py      # Main parser (441 lines)
└── tools/              # Utility functions and helpers
```

**Distributed Documentation**: 17 CLAUDE.md files across modules for local context

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
make lint          # All linting checks (delegate fixes to ruff-house)
make type-check    # Type checking (delegate fixes to type-veronica)
make security      # Security scans
make check-fast    # Quick quality checks (recommended first step)
```

### **Code Coverage Requirements**

- Maintain >80% code coverage for new code
- Write both unit and integration tests
- Test error conditions and edge cases
- Current test suite: 86+ tests, 2230+ lines of test code

### **Testing Gotchas (from recent iterations)**

```python
# ✅ GOOD - Strip ANSI codes in CLI tests
from scriptrag.tools.utils import strip_ansi_codes

def test_cli_output():
    result = runner.invoke(app, ["status"])
    output = strip_ansi_codes(result.output)
    assert "Ready" in output  # Will work in CI

# ❌ BAD - ANSI codes break CI tests
def test_cli_output():
    result = runner.invoke(app, ["status"])
    assert "Ready" in result.output  # Fails in CI due to ANSI codes
```

**Key Testing Issues:**
- **ANSI Escape Sequences**: Always use `strip_ansi_codes()` for CLI output
- **Mock File Artifacts**: Makefile validates no mock objects in filesystem
- **LLM Rate Limits**: Tests disabled by default in CI (use `ENABLE_LLM_TESTS=1`)
- **Cross-platform**: Windows/macOS path handling differences

## 🚀 Essential Development Commands

```bash
# Setup and maintenance
make setup-dev          # Complete dev environment setup
make update             # Update all dependencies

# Code quality (run before commits)
make format             # Format code with ruff
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
- **Module CLAUDE.md files**: 17 distributed documentation files
- **Test Utilities**: `src/scriptrag/tools/utils.py` (ANSI stripping)

### **Common Development Patterns**

1. **LLM Provider Integration**
   - Always implement rate limiting and retry logic
   - Handle JSON extraction failures gracefully
   - Use static model lists (dynamic discovery often unreliable)

2. **Git Integration**
   - Automatic .gitattributes for LFS management
   - Boneyard metadata injection/extraction for Fountain files
   - Content hashing for change detection

3. **Database Operations**
   - Complex graph queries for character relationships
   - Scene embedding with Git LFS storage
   - Multi-step pipelines with transaction management

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
6. **Learn from iterations** - Check recent PRs for common pitfall patterns

**Areas Requiring Extra Care (based on recent development):**
- LLM provider rate limiting and error handling
- ANSI escape sequences in test output
- Type annotations for async operations and generics
- Mock file artifacts in test environments
- Cross-platform compatibility (Windows/macOS/Linux)

## 📊 Common Iteration Patterns

Based on analysis of recent PRs and commits, these areas consistently require multiple iterations:

### Top 5 Areas Requiring Iteration
1. **Testing Infrastructure** (30% of fix commits) - ANSI codes, mock artifacts
2. **LLM Provider Integration** (25% of fix commits) - Rate limiting, JSON extraction
3. **Type System Compliance** (20% of fix commits) - Async annotations, generics
4. **Cross-platform Compatibility** (15% of fix commits) - Path handling, line endings
5. **Git/LFS Integration** (10% of fix commits) - .gitattributes, embedding storage

### Commit Pattern Metrics
From recent development:
- 35% of commits are fixes for previous commits
- 20% mention "fix tests" or "fix CI"
- 15% are linting/type fixes
- 10% are retry/error handling improvements

### Quick Solutions to Common Problems

| Problem | Quick Solution | Delegate To |
|---------|----------------|-------------|
| ANSI codes in tests | Use `strip_ansi_codes()` | - |
| LLM rate limits | Implement exponential backoff | - |
| Type errors with async | Explicit return annotations | `type-veronica` |
| Mock file artifacts | Use `spec_set` in mocks | - |
| Cross-platform paths | Use `pathlib.Path` | - |
| JSON extraction fails | Multiple fallback strategies | - |
| CI test failures | Check environment differences | `ci-mulder` |

**When in doubt, delegate to the appropriate sub-agent rather than guessing.**

Remember: *"In every job that must be done, there is an element of fun."* -
Mary Poppins, Mary Poppins (1964)

---

*This document focuses on immediate coding needs. Detailed guidelines are
handled by specialized sub-agents - use them liberally!*
