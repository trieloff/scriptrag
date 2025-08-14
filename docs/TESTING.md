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

### Platform-Specific Issues Summary

| Platform | Common Issues | Solutions |
|----------|--------------|-----------|
| Windows | Path separators (`\` vs `/`), CRLF line endings, file locking, ANSI in cmd.exe | Use `pathlib.Path`, normalize line endings, handle locks gracefully |
| macOS | Case-insensitive filesystem (default), different temp paths | Use case-sensitive comparisons, respect temp locations |
| Linux | File permissions, case-sensitive filesystem | Set proper permissions, exact case matching |

### 1. ANSI Code Stripping

**Problem**: CLI output contains ANSI escape sequences and Unicode characters that vary across platforms, causing test failures in CI environments.

**Background**: The codebase has over 100 usages of `strip_ansi_codes` across tests, which was a major cross-platform compatibility effort that succeeded but introduced significant boilerplate.

#### Modern Solution: Automatic ANSI Stripping Fixtures (Recommended)

Use the new `cli_fixtures` module that provides automatic ANSI stripping:

```python
# Use the cli_invoke fixture for automatic ANSI stripping
def test_cli_with_fixture(cli_invoke):
    result = cli_invoke("status")
    result.assert_success().assert_contains("Ready")
    # No manual strip_ansi_codes needed!

# Or use the cli_helper for more complex workflows
def test_workflow(cli_helper):
    result = cli_helper.init_database()
    result.assert_success().assert_contains("Database initialized")

    result = cli_helper.analyze_scripts(script_dir=Path("."))
    result.assert_success()
```

#### Legacy Solution: Manual ANSI Stripping

For existing tests or when not using fixtures:

```python
from tests.utils import strip_ansi_codes  # or from tests.cli_fixtures

def test_cli_output(runner):
    result = runner.invoke(app, ["command"])
    output = strip_ansi_codes(result.stdout)
    assert "expected text" in output
```

#### Using Enhanced CLI Test Fixtures

The `tests/cli_fixtures.py` module provides several improvements:

1. **CleanCliRunner**: Automatically returns cleaned results

   ```python
   from tests.cli_fixtures import CleanCliRunner

   runner = CleanCliRunner()
   result = runner.invoke(app, ["status"])  # Returns CleanResult
   assert "Ready" in result.output  # Already stripped!
   ```

2. **CleanResult**: Chainable assertions with automatic ANSI stripping

   ```python
   result.assert_success()
       .assert_contains("Database initialized", "Ready")
       .assert_not_contains("Error", "Failed")
   ```

3. **cli_helper fixture**: Full workflow helper

   ```python
   def test_full_workflow(cli_helper):
       # All methods return CleanResult with stripped output
       cli_helper.init_database().assert_success()
       cli_helper.index_scripts("./scripts").assert_success()

       result = cli_helper.search("query", json=True)
       data = result.parse_json()  # Automatic JSON parsing
       assert len(data["results"]) > 0
   ```

#### Migration Guide

To migrate existing tests to use automatic ANSI stripping:

1. Replace `CliRunner` with `CleanCliRunner` or use `clean_runner` fixture
2. Replace manual `strip_ansi_codes` calls with CleanResult assertions
3. Use `cli_invoke` fixture for simple command invocations
4. Use `cli_helper` fixture for complex workflows

Before:

```python
def test_old_style(runner):
    result = runner.invoke(app, ["init"])
    output = strip_ansi_codes(result.stdout)
    assert result.exit_code == 0
    assert "initialized" in output
```

After:

```python
def test_new_style(cli_invoke):
    result = cli_invoke("init")
    result.assert_success().assert_contains("initialized")
```

### 2. Path Handling

**Problem**: Path separators differ between Windows (`\`) and Unix (`/`).

**Solution**: Use `pathlib.Path` consistently:

```python
from pathlib import Path
import os

# Good - Platform-independent
script_path = tmp_path / "scripts" / "test.fountain"
relative_path = Path("data") / "scripts" / "test.fountain"

# Good - Converting paths for display
display_path = str(script_path)  # Automatically uses correct separator

# Good - Checking path existence across platforms
if script_path.exists() and script_path.is_file():
    content = script_path.read_text()

# Bad - Hard-coded separators
script_path = f"{tmp_path}/scripts/test.fountain"  # Fails on Windows
script_path = tmp_path + "\\scripts\\test.fountain"  # Fails on Unix

# Testing path equality across platforms
def test_path_operations(tmp_path):
    # Good - Use Path.resolve() for canonical comparison
    path1 = Path("./data/../data/file.txt").resolve()
    path2 = (Path.cwd() / "data" / "file.txt").resolve()
    assert path1 == path2

    # Good - Case-insensitive comparison for Windows/macOS
    import platform
    if platform.system() in ("Windows", "Darwin"):
        assert path1.as_posix().lower() == path2.as_posix().lower()
```

#### Windows-Specific Path Issues

```python
# Handle Windows long path limitations (260 chars)
def safe_windows_path(path: Path) -> Path:
    """Ensure path works on Windows with long path support."""
    if platform.system() == "Windows":
        # Use extended-length path prefix for long paths
        str_path = str(path.resolve())
        if len(str_path) > 250 and not str_path.startswith("\\\\?\\"):
            return Path(f"\\\\?\\{str_path}")
    return path

# Handle Windows reserved filenames
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", "COM1", "LPT1"}
def is_valid_filename(name: str) -> bool:
    """Check if filename is valid on all platforms."""
    base_name = Path(name).stem.upper()
    return base_name not in WINDOWS_RESERVED
```

### 3. Line Endings

**Problem**: Git may convert line endings, causing test failures. Windows uses CRLF (`\r\n`), while Unix uses LF (`\n`).

**Solution**: Configure `.gitattributes` and normalize in tests when needed:

```python
# Always normalize line endings when comparing text
def normalize_text(text: str) -> str:
    """Normalize line endings and whitespace for cross-platform comparison."""
    # Convert all line endings to Unix style
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines)

def test_file_content(tmp_path):
    # Write with explicit line ending
    content = "Line 1\nLine 2\nLine 3"
    file_path = tmp_path / "test.txt"
    file_path.write_text(content, encoding='utf-8', newline='\n')  # Force LF

    # Read and normalize for comparison
    read_content = file_path.read_text(encoding='utf-8')
    assert normalize_text(read_content) == normalize_text(content)

# Handle binary vs text mode
def test_binary_files(tmp_path):
    # Binary mode preserves exact bytes (no line ending conversion)
    file_path = tmp_path / "data.bin"
    data = b"Binary\r\nData"
    file_path.write_bytes(data)
    assert file_path.read_bytes() == data  # Exact match
```

#### Git Configuration

Add to `.gitattributes`:

```text
# Force LF for Python and Fountain files
*.py text eol=lf
*.fountain text eol=lf
*.md text eol=lf

# Mark binary files
*.db binary
*.sqlite binary
```

### 4. SQLite Vector Extension Support

**Problem**: SQLite vector extension availability and behavior varies across platforms.

**Solution**: Test for extension availability and handle gracefully:

```python
import sqlite3
import platform

def test_sqlite_vector_support(tmp_path):
    """Test SQLite vector extension support across platforms."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    # Check if vector extension is available
    try:
        conn.enable_load_extension(True)
        # Platform-specific extension paths
        if platform.system() == "Windows":
            extensions = ["vec0.dll", "sqlite-vec.dll"]
        elif platform.system() == "Darwin":
            extensions = ["vec0.dylib", "libvec0.dylib"]
        else:  # Linux
            extensions = ["vec0.so", "libvec0.so"]

        loaded = False
        for ext in extensions:
            try:
                conn.load_extension(ext)
                loaded = True
                break
            except sqlite3.OperationalError:
                continue

        if not loaded:
            pytest.skip("SQLite vector extension not available on this platform")

        # Test vector operations
        conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(a float[3])")
        conn.execute("INSERT INTO test_vec VALUES (?)", ([1.0, 2.0, 3.0],))

    except (AttributeError, sqlite3.OperationalError) as e:
        pytest.skip(f"Vector extension not supported: {e}")
    finally:
        conn.close()
```

### 5. File Locking Behavior

**Problem**: File locking behavior differs significantly between Windows and Unix systems.

**Solution**: Handle platform-specific locking patterns:

```python
import fcntl  # Unix only
import msvcrt  # Windows only
import platform
import time

def test_file_locking(tmp_path):
    """Test file locking behavior across platforms."""
    file_path = tmp_path / "locked_file.txt"
    file_path.write_text("test content")

    if platform.system() == "Windows":
        # Windows exclusive locking
        import msvcrt
        with open(file_path, 'r+b') as f:
            try:
                # Lock file for exclusive access
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                # File is locked, other processes can't write

                # Attempt to open in another "process" (simulation)
                try:
                    with open(file_path, 'w') as f2:
                        f2.write("should fail")
                    assert False, "Should not be able to write to locked file"
                except (IOError, OSError):
                    pass  # Expected on Windows

            finally:
                # Unlock
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

    else:  # Unix/Linux/macOS
        # Unix advisory locking
        import fcntl
        with open(file_path, 'r+b') as f:
            try:
                # Acquire exclusive lock (non-blocking)
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # On Unix, other processes can still open the file
                # but should respect the advisory lock
                with open(file_path, 'r') as f2:
                    content = f2.read()  # Reading is typically allowed
                    assert content == "test content"

            finally:
                # Release lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# Database locking specific to SQLite
def test_sqlite_locking(tmp_path):
    """Test SQLite database locking across platforms."""
    db_path = tmp_path / "test.db"

    # SQLite handles locking internally, but behavior varies
    conn1 = sqlite3.connect(str(db_path), timeout=1.0)
    conn2 = sqlite3.connect(str(db_path), timeout=1.0)

    try:
        # Create table
        conn1.execute("CREATE TABLE test (id INTEGER)")
        conn1.commit()

        # Start transaction on conn1
        conn1.execute("BEGIN EXCLUSIVE")
        conn1.execute("INSERT INTO test VALUES (1)")

        # Try to write from conn2 (should timeout)
        try:
            conn2.execute("INSERT INTO test VALUES (2)")
            if platform.system() == "Windows":
                # Windows might handle this differently
                pytest.skip("Windows SQLite locking behaves differently")
        except sqlite3.OperationalError as e:
            assert "locked" in str(e).lower()

    finally:
        conn1.close()
        conn2.close()
```

### 6. Platform Detection and Conditional Testing

**Solution**: Use platform detection for OS-specific test logic:

```python
import platform
import sys

def get_platform_info():
    """Get detailed platform information for test adaptation."""
    return {
        "system": platform.system(),  # 'Windows', 'Linux', 'Darwin'
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),  # 'x86_64', 'arm64', etc.
        "python_version": sys.version,
        "is_windows": platform.system() == "Windows",
        "is_macos": platform.system() == "Darwin",
        "is_linux": platform.system() == "Linux",
        "is_ci": bool(os.getenv("CI") or os.getenv("GITHUB_ACTIONS")),
    }

@pytest.fixture
def platform_info():
    """Fixture providing platform information."""
    return get_platform_info()

def test_platform_specific_behavior(platform_info):
    """Example of platform-specific test."""
    if platform_info["is_windows"]:
        # Windows-specific test
        assert os.pathsep == ";"
        assert os.linesep == "\r\n"
    else:
        # Unix-like systems
        assert os.pathsep == ":"
        assert os.linesep == "\n"

    # Skip tests on specific platforms
    if platform_info["is_macos"] and platform_info["machine"] == "arm64":
        pytest.skip("Test not compatible with Apple Silicon")

# Conditional test marking
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix only test")
def test_unix_specific():
    """Test that only runs on Unix-like systems."""
    import pwd
    assert pwd.getpwuid(os.getuid()).pw_name

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only test")
def test_windows_specific():
    """Test that only runs on Windows."""
    import winreg
    # Windows registry operations
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

| Issue | Platform | Solution |
|-------|----------|----------|
| ANSI codes in CI output | All | Use `strip_ansi_codes()` or `CleanCliRunner` |
| Path separator issues | Windows | Use `pathlib.Path` instead of string concatenation |
| Fixture contamination | All | Copy fixtures to tmp_path before modification |
| Database already exists | All | Ensure proper test isolation with tmp_path |
| LLM rate limits | All | Mark with `@pytest.mark.requires_llm` and handle gracefully |
| Mock file artifacts | All | Use `spec_set` parameter in mocks |
| Slow tests | All | Use canary pattern, run integration tests separately |
| CRLF line endings | Windows | Configure `.gitattributes`, normalize in tests |
| File locking errors | Windows | Handle `PermissionError`, use context managers |
| Case sensitivity | macOS | Use case-insensitive comparisons where needed |
| Temp directory paths | Windows | Use `tmp_path` fixture, avoid hardcoded `/tmp` |
| Unicode in paths | Windows | Use `utf-8` encoding explicitly |
| SQLite DLL loading | Windows | Check multiple extension paths |
| Long path names (>260) | Windows | Use extended path syntax `\\?\` |

### Platform-Specific Test Failures

#### Windows-Specific Issues

```python
# Issue: PermissionError when deleting files
def test_file_operations_windows(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("content")

    # Close all handles before deletion
    import gc
    gc.collect()  # Force garbage collection

    # Retry deletion with timeout
    import time
    for attempt in range(3):
        try:
            file_path.unlink()
            break
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1)

# Issue: Command line argument escaping
def test_cli_args_windows():
    # Windows needs special escaping for quotes
    import shlex
    import platform

    if platform.system() == "Windows":
        # Windows escaping
        arg = '"quoted value"'
        escaped = arg.replace('"', '""')
    else:
        # Unix escaping
        arg = "'quoted value'"
        escaped = shlex.quote(arg)
```

#### macOS-Specific Issues

```python
# Issue: Case-insensitive filesystem
def test_case_sensitivity_macos(tmp_path):
    file1 = tmp_path / "Test.txt"
    file2 = tmp_path / "test.txt"

    file1.write_text("content1")

    # Check if filesystem is case-sensitive
    try:
        file2.write_text("content2")
        # Case-sensitive filesystem
        assert file1.read_text() == "content1"
        assert file2.read_text() == "content2"
    except:
        # Case-insensitive filesystem (default macOS)
        assert file1.read_text() == file2.read_text()

# Issue: Different temp directory location
def test_temp_directory_macos():
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    # macOS might use /var/folders/... instead of /tmp
    assert temp_dir.exists()
```

#### Linux-Specific Issues

```python
# Issue: File permissions
def test_file_permissions_linux(tmp_path):
    import stat
    file_path = tmp_path / "test.sh"
    file_path.write_text("#!/bin/bash\necho test")

    # Set executable permission
    file_path.chmod(file_path.stat().st_mode | stat.S_IEXEC)

    # Verify permission was set
    assert file_path.stat().st_mode & stat.S_IEXEC
```

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

### Platform-Specific CI/CD Setup

For comprehensive cross-platform testing, configure your CI/CD matrix:

```yaml
# GitHub Actions example
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ["3.11", "3.12", "3.13"]
    exclude:
      # Skip certain combinations if needed
      - os: macos-latest
        python-version: "3.11"
```

### Environment Variables for Cross-Platform Testing

```bash
# Windows
set SCRIPTRAG_TEST_PLATFORM=windows
set SCRIPTRAG_TEST_SKIP_SLOW=1

# Unix/Linux/macOS
export SCRIPTRAG_TEST_PLATFORM=unix
export SCRIPTRAG_TEST_SKIP_SLOW=1
```

---

*Last updated: 2025-08-14*
