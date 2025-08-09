# Testing Guidelines for Claude - ScriptRAG Test Suite

**Current Scale**: 86+ tests, 2230+ lines of test code covering all major components

## ANSI Escape Codes in CI Environment

### The Issue
When running tests in GitHub Actions CI environment, CLI output contains ANSI escape codes that can cause string matching assertions to fail. These escape codes are used for colors, formatting, and terminal control sequences.

### The Problem
Tests that work perfectly in local development may fail in CI because:
- The CI environment has different terminal capabilities
- ANSI codes like `\x1b[1m` (bold), `\x1b[0m` (reset), etc. are embedded in output
- Simple string assertions like `assert "--force" in result.stdout` fail when the actual output contains escape sequences

### The Solution
**Always use the `strip_ansi_codes()` utility function when testing CLI output:**

```python
from tests.utils import strip_ansi_codes

def test_cli_command(self):
    result = runner.invoke(app, ["command", "--help"])

    # ❌ BAD - Will fail in CI due to ANSI codes
    assert "--force" in result.stdout

    # ✅ GOOD - Strips ANSI codes before matching
    clean_output = strip_ansi_codes(result.stdout)
    assert "--force" in clean_output
```

### The Utility
The `strip_ansi_codes()` function is available in `tests/utils.py`:
- Removes all ANSI escape sequences using regex pattern `\x1b\[[0-9;]*m`
- Returns clean text suitable for string matching
- Shared across all test files to avoid duplication

### When to Use
Use `strip_ansi_codes()` whenever you:
- Test CLI help output
- Check for specific options or commands in output
- Verify any formatted text from typer/click commands
- Compare CLI output strings

### Example Pattern
```python
def test_analyze_help(self):
    """Test analyze command help."""
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0

    # Strip ANSI escape codes for reliable string matching
    clean_output = strip_ansi_codes(result.stdout)
    assert "Analyze Fountain files" in clean_output
    assert "--force" in clean_output
    assert "--dry-run" in clean_output
    assert "--analyzer" in clean_output
```

### Remember
- Local tests may pass without stripping, but CI will fail
- Always strip ANSI codes when checking CLI output content
- The utility is already imported in most integration test files
- This is not a bug - it's a difference in terminal environments

## Mock File Artifacts Prevention

### The Issue
Python's mock objects can create unexpected file-like artifacts in the filesystem when not properly configured, polluting the codebase.

### The Solution
The Makefile includes sophisticated validation to detect and prevent mock artifacts:

```makefile
# Check for mock object artifacts (sophisticated validation)
find . -type f -name "<*>" -o -name "*MagicMock*" | grep -v .git
```

### Best Practices
- Always use proper mock configuration with `spec` or `spec_set`
- Clean up mocks in tearDown methods
- Use context managers for file mocks

## LLM Provider Testing

### Rate Limiting Issues
LLM tests are **disabled by default in CI** due to rate limiting:

```python
# Tests require ENABLE_LLM_TESTS=1 environment variable
@pytest.mark.skipif(
    not os.getenv("ENABLE_LLM_TESTS"),
    reason="LLM tests disabled by default (set ENABLE_LLM_TESTS=1)"
)
def test_llm_provider():
    pass
```

### Common LLM Test Patterns

```python
# ✅ GOOD - Mock LLM responses for unit tests
def test_scene_analysis():
    with patch("scriptrag.llm.client.LLMClient.complete") as mock:
        mock.return_value = {"scene_type": "action"}
        result = analyzer.analyze_scene(scene)
        assert result.scene_type == "action"

# ✅ GOOD - Test rate limiting handling
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def test_with_retry():
    # Test exponential backoff for rate limits
    pass
```

## Cross-Platform Compatibility

### Path Handling
```python
# ✅ GOOD - Use pathlib for cross-platform paths
from pathlib import Path
script_path = Path("tests/data/script.fountain")

# ❌ BAD - Hardcoded path separators
script_path = "tests/data/script.fountain"  # Fails on Windows
```

### Line Endings
```python
# ✅ GOOD - Handle both Unix and Windows line endings
output = result.stdout.replace("\r\n", "\n")
assert expected in output
```

## Test Organization Best Practices

### File Size Limits
- Keep test files under 500 lines for maintainability
- Split large test suites by functionality
- Use test fixtures for shared setup

### Test Naming
```python
# ✅ GOOD - Descriptive test names
def test_fountain_parser_handles_malformed_metadata():
    pass

def test_llm_provider_retries_on_rate_limit():
    pass

# ❌ BAD - Vague test names
def test_parser():
    pass
```

### Common Test Fixtures

```python
@pytest.fixture
def sample_fountain_script():
    """Provide a standard test script."""
    return Path("tests/data/casablanca.fountain")

@pytest.fixture
def mock_llm_client():
    """Mock LLM client with preset responses."""
    with patch("scriptrag.llm.client.LLMClient") as mock:
        mock.complete.return_value = {"result": "test"}
        yield mock
```

## Areas Requiring Extra Testing Care

Based on recent development iterations:

1. **ANSI Escape Sequences**: Always strip from CLI output
2. **Mock Configuration**: Prevent filesystem artifacts  
3. **LLM Rate Limiting**: Mock in unit tests, careful integration testing
4. **Type Checking**: Mock types can confuse mypy
5. **Async Operations**: Use pytest-asyncio properly
6. **Git Operations**: Mock Git commands to avoid repository state changes
7. **Database Transactions**: Proper rollback in test teardown
8. **Fountain Parsing**: Test malformed scripts and edge cases
9. **Cross-platform Paths**: Use pathlib consistently
10. **Character Encoding**: UTF-8 handling for international scripts
