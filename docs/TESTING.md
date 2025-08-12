# ScriptRAG Testing Best Practices

This guide documents testing best practices for the ScriptRAG project to ensure reliable, cross-platform test execution.

## Table of Contents

- [Test Organization](#test-organization)
- [Cross-Platform Compatibility](#cross-platform-compatibility)
- [CLI Testing](#cli-testing)
- [Test Isolation](#test-isolation)
- [Database Testing](#database-testing)
- [LLM Provider Testing](#llm-provider-testing)
- [Common Patterns](#common-patterns)
- [Debugging Tips](#debugging-tips)

## Test Organization

### Directory Structure

```text
tests/
├── unit/           # Fast, isolated unit tests
├── integration/    # End-to-end integration tests
├── fixtures/       # Test data files (NEVER modify directly!)
├── agents/         # Agent-specific tests
├── llm/           # LLM provider tests
└── utils.py       # Common test utilities
```

### Test Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>`
- Test methods: `test_<specific_behavior>`

Example:

```python
# tests/unit/test_cli_commands_init.py
class TestInitCommand:
    def test_database_creation_succeeds(self):
        ...

    def test_handles_existing_database_error(self):
        ...
```

## Cross-Platform Compatibility

### 1. ANSI Code Stripping

**Problem**: CLI output contains ANSI escape sequences and Unicode characters that vary across platforms.

**Solution**: Always strip ANSI codes when testing CLI output:

```python
from scriptrag.tools.utils import strip_ansi_codes

def test_cli_output(runner):
    result = runner.invoke(app, ["command"])
    output = strip_ansi_codes(result.stdout)
    assert "expected text" in output
```

### 2. Path Handling

**Problem**: Path separators differ between Windows (`\`) and Unix (`/`).

**Solution**: Use `pathlib.Path` consistently:

```python
from pathlib import Path

# Good
script_path = tmp_path / "scripts" / "test.fountain"

# Bad
script_path = f"{tmp_path}/scripts/test.fountain"
```

### 3. Line Endings

**Problem**: Git may convert line endings, causing test failures.

**Solution**: Configure `.gitattributes` and normalize in tests when needed:

```python
content = file_path.read_text()
# Normalize line endings if needed
content = content.replace('\r\n', '\n')
```

## CLI Testing

### Using CLITestHelper

The project provides a `CLITestHelper` class for common CLI testing patterns:

```python
from tests.utils import CLITestHelper

def test_workflow(tmp_path):
    helper = CLITestHelper(tmp_path)

    # Initialize database
    exit_code, output = helper.init_database()
    assert exit_code == 0
    assert "Database initialized" in output

    # Analyze scripts
    exit_code, output = helper.analyze_scripts(
        script_dir=tmp_path,
        analyzer="props_inventory",
        force=True
    )
    assert exit_code == 0

    # Index scripts
    exit_code, output = helper.index_scripts(tmp_path)
    assert exit_code == 0
```

### Testing Error Conditions

Always test both success and failure paths:

```python
def test_init_handles_existing_database(tmp_path):
    db_path = tmp_path / "test.db"
    db_path.touch()  # Create existing file

    runner = CliRunner()
    result = runner.invoke(app, ["init", "--db-path", str(db_path)])

    assert result.exit_code == 1
    output = strip_ansi_codes(result.stdout)
    assert "already exists" in output.lower()
```

## Test Isolation

### Automatic Isolation

The `conftest.py` provides automatic test isolation for unit tests:

```python
@pytest.fixture(autouse=True)
def isolated_test_environment(request, tmp_path, monkeypatch):
    """Automatically isolates unit tests."""
    # Only for unit tests, not integration tests
    if "/integration/" in str(request.fspath):
        yield
        return

    # Create isolated database
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))
    ...
```

### Fixture File Protection

**CRITICAL**: Never modify fixture files directly!

```python
# Bad - modifies fixture directly
def test_bad(fixtures_dir):
    script = fixtures_dir / "test.fountain"
    script.write_text("new content")  # DON'T DO THIS!

# Good - copy to temp directory first
def test_good(tmp_path, fixtures_dir):
    source = fixtures_dir / "test.fountain"
    script = tmp_path / "test.fountain"
    shutil.copy2(source, script)
    script.write_text("new content")  # Safe to modify copy
```

## Database Testing

### Creating Test Databases

```python
from tests.utils import verify_database_structure

def test_database_operations(tmp_path):
    db_path = tmp_path / "test.db"

    # Initialize database
    init_command = DatabaseInitializer(db_path)
    init_command.initialize_database()

    # Verify structure
    structure = verify_database_structure(db_path)
    assert "scripts" in structure
    assert "scenes" in structure
```

### Asserting Database Content

```python
from tests.utils import assert_scene_in_database, count_database_records

def test_indexing(tmp_path):
    # ... perform indexing ...

    # Check specific scene exists
    scene = assert_scene_in_database(
        db_path=tmp_path / "test.db",
        scene_heading="INT. COFFEE SHOP - DAY",
        script_title="Test Script"
    )
    assert scene["scene_number"] == 1

    # Check record counts
    count = count_database_records(tmp_path / "test.db", "scenes")
    assert count == 3
```

## LLM Provider Testing

### Marking LLM Tests

Tests requiring external LLM providers should be marked:

```python
@pytest.mark.requires_llm
def test_llm_analysis():
    # Test will be skipped in CI unless SCRIPTRAG_TEST_LLMS=1
    ...
```

### Handling Rate Limits

LLM tests should gracefully handle rate limiting:

```python
def test_with_llm(monkeypatch):
    result = runner.invoke(app, ["analyze", "--analyzer", "props_inventory"])

    if result.exit_code != 0:
        output = strip_ansi_codes(result.stdout)
        if "Rate limit" in output or "All LLM providers failed" in output:
            pytest.skip("LLM provider rate limited")

    assert result.exit_code == 0
```

## Common Patterns

### Creating Test Screenplays

```python
from tests.utils import create_test_screenplay

def test_with_screenplay(tmp_path):
    # Use default content
    script = create_test_screenplay(tmp_path)

    # Or provide custom content
    script = create_test_screenplay(
        tmp_path,
        filename="custom.fountain",
        content="""Title: Custom Script

INT. LOCATION - DAY

Action here."""
    )
```

### Testing JSON Output

```python
def test_json_output(helper):
    exit_code, output, data = helper.search("query", json=True)

    assert exit_code == 0
    assert data is not None
    assert "results" in data
    assert len(data["results"]) > 0
```

### Monkeypatching Environment

```python
def test_with_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SCRIPTRAG_LOG_LEVEL", "DEBUG")

    # Environment is automatically restored after test
```

## Debugging Tips

### 1. Verbose Test Output

```bash
# Run with verbose output
make test PYTEST_ARGS="-vv"

# Show print statements
make test PYTEST_ARGS="-s"

# Run specific test
make test PYTEST_ARGS="tests/unit/test_cli.py::TestInit::test_create"
```

### 2. Debugging CI Failures

Check for platform-specific issues:

```python
import platform

def test_platform_specific():
    if platform.system() == "Windows":
        # Windows-specific test logic
        ...
    else:
        # Unix-specific test logic
        ...
```

### 3. Inspecting Test Artifacts

```python
def test_with_artifacts(tmp_path):
    # Keep artifacts for debugging
    db_path = tmp_path / "test.db"

    # ... perform operations ...

    # Print path for manual inspection
    print(f"Database at: {db_path}")

    # Or dump database content
    conn = sqlite3.connect(str(db_path))
    for row in conn.execute("SELECT * FROM scripts"):
        print(row)
```

### 4. Test Timeouts

For slow tests, use pytest-timeout:

```python
@pytest.mark.timeout(30)  # 30 second timeout
def test_slow_operation():
    ...
```

## Running Tests

### Quick Commands

```bash
# Run all tests with coverage
make test

# Run unit tests only (fast)
make test PYTEST_ARGS="-m 'not integration'"

# Run integration tests only
make test PYTEST_ARGS="-m integration"

# Run with specific Python version
uv run --python 3.13 pytest

# Run in parallel (if configured)
make test PYTEST_ARGS="-n auto"
```

### CI/CD Considerations

The CI pipeline runs tests in this order:

1. **Canary tests** (Ubuntu, Python 3.12) - Fast, fail-early
2. **Test matrix** (Ubuntu/macOS/Windows × Python 3.12/3.13)
3. **Integration tests** (Ubuntu only, with LLM providers if available)

### Test Coverage

Maintain >80% code coverage:

```bash
# Generate coverage report
make test
coverage report

# Generate HTML report
coverage html
open htmlcov/index.html
```

## Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| ANSI codes in CI output | Use `strip_ansi_codes()` on all CLI output |
| Path separator issues | Use `pathlib.Path` instead of string concatenation |
| Fixture contamination | Copy fixtures to tmp_path before modification |
| Database already exists | Ensure proper test isolation with tmp_path |
| LLM rate limits | Mark with `@pytest.mark.requires_llm` and handle gracefully |
| Mock file artifacts | Use `spec_set` parameter in mocks |
| Slow tests | Use canary pattern, run integration tests separately |

## Best Practices Summary

1. **Always strip ANSI codes** from CLI output before assertions
2. **Never modify fixture files** - always copy to tmp_path first
3. **Use pathlib.Path** for all path operations
4. **Test both success and failure** conditions
5. **Mark LLM tests** with `@pytest.mark.requires_llm`
6. **Handle rate limits gracefully** with pytest.skip()
7. **Use test utilities** from `tests/utils.py` for common patterns
8. **Maintain test isolation** - each test should be independent
9. **Keep tests fast** - mock external dependencies in unit tests
10. **Document complex test logic** with clear comments

## Contributing

When adding new tests:

1. Follow the naming conventions
2. Add appropriate markers (`@pytest.mark.integration`, `@pytest.mark.requires_llm`)
3. Use the test utilities for common operations
4. Ensure tests pass on all platforms (Ubuntu, macOS, Windows)
5. Maintain or improve code coverage
6. Update this guide if you discover new patterns or issues

---

*Last updated: 2025-08-12*
