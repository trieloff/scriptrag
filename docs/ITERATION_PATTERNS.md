# ScriptRAG Development Iteration Patterns

This document captures common patterns where multiple iterations were needed during development, helping future contributors avoid the same pitfalls.

## Executive Summary

Based on analysis of recent PRs and commit history, the ScriptRAG project has several areas that consistently require multiple iterations:

1. **Testing Infrastructure** (30% of fix commits)
2. **LLM Provider Integration** (25% of fix commits)
3. **Type System Compliance** (20% of fix commits)
4. **Cross-platform Compatibility** (15% of fix commits)
5. **Git/LFS Integration** (10% of fix commits)

## Top 10 Iteration Patterns

### 1. ANSI Escape Sequences in Tests

**Problem**: CLI tests pass locally but fail in CI due to ANSI codes.

**Iterations Required**: 3-5 commits typically needed to fix all test cases.

**Solution**:

```python
from scriptrag.tools.utils import strip_ansi_codes

# Always strip ANSI codes before assertions
output = strip_ansi_codes(result.stdout)
assert "expected" in output
```

### 2. LLM Rate Limiting

**Problem**: GitHub Models API rate limits cause test failures.

**Iterations Required**: Multiple attempts to find right retry strategy.

**Solution**:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def call_with_retry():
    pass
```

### 3. Type Annotations for Async Code

**Problem**: MyPy errors with async functions and complex generics.

**Iterations Required**: 2-3 commits to satisfy type checker.

**Solution**:

```python
from typing import TypeVar, Generic

T = TypeVar("T", bound="BaseProvider")

class Client(Generic[T]):
    async def method(self) -> dict[str, Any]:
        pass
```

### 4. Mock File Artifacts

**Problem**: Test mocks creating actual files in filesystem.

**Iterations Required**: Complex Makefile validation added after multiple incidents.

**Solution**:

- Always use `spec` or `spec_set` with mocks
- Clean up in tearDown methods
- Makefile checks for artifacts

### 5. JSON Extraction from LLM Responses

**Problem**: LLMs don't always return clean JSON.

**Iterations Required**: Progressive fallback strategies developed.

**Solution**:

```python
def extract_json(response: str) -> dict:
    # Try direct parse
    # Try markdown code block
    # Try regex extraction
    # Raise if all fail
```

### 6. Cross-platform Path Handling

**Problem**: Windows vs Unix path separators.

**Iterations Required**: Found in multiple test files.

**Solution**:

```python
from pathlib import Path
# Always use Path objects
script_path = Path("tests") / "data" / "script.fountain"
```

### 7. Git LFS Configuration

**Problem**: Embeddings not tracked by LFS automatically.

**Iterations Required**: .gitattributes management refined over time.

**Solution**:

- Automatic .gitattributes updates
- Validation in setup scripts
- Clear documentation

### 8. Database Transaction Deadlocks

**Problem**: Concurrent operations causing locks.

**Iterations Required**: Transaction ordering refined.

**Solution**:

- Consistent operation ordering
- Proper rollback handling
- Connection pooling

### 9. Character Capitalization Consistency

**Problem**: Fountain format has inconsistent capitalization.

**Iterations Required**: Multiple regex refinements.

**Solution**:

- Normalize on import
- Maintain original for display
- Test edge cases

### 10. CI Environment Differences

**Problem**: Different behavior in GitHub Actions.

**Iterations Required**: Environment-specific fixes.

**Solution**:

- CI-specific timeouts
- Environment detection
- Conditional test skipping

## Metrics and Impact

### Commit Pattern Analysis

From recent 100 commits:

- 35% are fixes for previous commits
- 20% mention "fix tests" or "fix CI"
- 15% are linting/type fixes
- 10% are retry/error handling improvements

### File Iteration Frequency

Most frequently modified files (indicating iteration needs):

1. Test files (40+ modifications)
2. LLM providers (30+ modifications)
3. Database operations (25+ modifications)
4. Parser modules (20+ modifications)

## Recommendations for New Contributors

### Before Starting

1. **Run Full Test Suite**: `make test`
2. **Check Type Compliance**: `make type-check`
3. **Run Linting**: `make lint`
4. **Test in CI-like Environment**: Use Docker if possible

### During Development

1. **Use Specialized Agents**: Delegate to ruff-house, type-veronica, etc.
2. **Test Early and Often**: Don't accumulate technical debt
3. **Check CLAUDE.md Files**: 21+ distributed docs with local context
4. **Mock External Services**: Especially LLM calls
5. **Use Path Objects**: Never hardcode path separators

### Common Commands

```bash
# Quick quality check
make check-fast

# Full validation
make check

# Fix formatting
make format

# Run specific test
pytest tests/test_module.py -v

# Enable LLM tests
ENABLE_LLM_TESTS=1 pytest tests/llm/
```

## Success Patterns

### What Works Well

1. **Distributed Documentation**: CLAUDE.md files provide local context
2. **Specialized Agents**: Clear delegation of responsibilities
3. **Comprehensive Makefile**: One-command operations
4. **Pre-commit Hooks**: Catch issues before commit
5. **Structured Logging**: Easy debugging

### Areas for Improvement

1. **File Size Management**: Some modules approaching limits
2. **Test Organization**: Could benefit from more fixtures
3. **Error Messages**: More actionable error descriptions
4. **Documentation**: More examples in docstrings
5. **Performance Profiling**: Identify bottlenecks

## Conclusion

The ScriptRAG codebase is well-engineered but complex. Understanding these iteration patterns can significantly reduce development time and frustration. When in doubt:

1. Check existing CLAUDE.md files
2. Look at recent similar commits
3. Use specialized agents
4. Test thoroughly before committing
5. Ask for help in unclear situations

Remember: Quality over speed. A well-tested, properly typed commit saves hours of debugging later.
