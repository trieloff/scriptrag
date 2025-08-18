# SQLite VSS Extension Required on macOS - Remove Graceful Degradation

## Problem Statement

ScriptRAG v2 requires SQLite with loadable extension support to use `sqlite-vec` for vector similarity search (VSS). However, macOS ships with SQLite compiled **without** `enable_load_extension` support for security reasons, causing the application to fail.

Currently (as of PR #[current-branch]), we've implemented graceful degradation that allows the code to run without VSS support, but this creates a false sense of functionality - the vector search features simply don't work on macOS with the default SQLite.

## Current State

### What Was Fixed

- PR #[current-branch] (`terragon/implement-scene-embedding-search`) fixed test failures by:
  - Adding `hasattr(conn, "enable_load_extension")` checks in `src/scriptrag/storage/vss_service.py`
  - Allowing tests to pass by mocking SQLite_vec functionality
  - Gracefully degrading when extension loading isn't available

### Why This Isn't Sufficient

1. **Silent Failure**: Users on macOS get no vector search functionality but the app appears to work
2. **Inconsistent Behavior**: Different functionality on macOS vs Linux/Windows
3. **Debugging Confusion**: Users may spend time debugging "broken" search without realizing VSS isn't available
4. **CI/CD Issues**: macOS CI tests pass but don't test actual VSS functionality

## Proposed Solution

Replace graceful degradation with **early, explicit failure** and proper dependency installation:

1. **Fail Fast**: Check SQLite capabilities at startup and fail with clear instructions
2. **Documentation**: Explicitly document SQLite extension requirements
3. **CI/CD**: Install proper SQLite with extension support in GitHub Actions
4. **User Guidance**: Provide platform-specific installation instructions

## Implementation Tasks

### 1. Remove Graceful Degradation ❌

**File**: `src/scriptrag/storage/vss_service.py`

Remove the graceful handling added in lines 85-94:

```python
# REMOVE THIS:
if hasattr(conn, "enable_load_extension"):
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (AttributeError, sqlite3.OperationalError) as e:
        logger.debug(f"SQLite extension loading not available: {e}")
        # Continue without VSS support - tests will mock this functionality

# REPLACE WITH:
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)
```

### 2. Add Startup Dependency Check ✅

**New File**: `src/scriptrag/utils/dependency_check.py`

```python
"""Dependency validation for ScriptRAG."""

import sqlite3
import sys
import platform
from pathlib import Path

from scriptrag.exceptions import DependencyError


def check_sqlite_vss_support() -> None:
    """Check if SQLite has vector similarity search support.

    Raises:
        DependencyError: If SQLite doesn't support required extensions
    """
    try:
        conn = sqlite3.connect(":memory:")

        # Check for extension loading capability
        if not hasattr(conn, "enable_load_extension"):
            system = platform.system()
            if system == "Darwin":  # macOS
                raise DependencyError(
                    message="SQLite on macOS doesn't support extensions",
                    hint=(
                        "macOS ships with SQLite compiled without extension support.\n"
                        "To fix this, install SQLite with extension support:\n\n"
                        "Using Homebrew:\n"
                        "  brew install sqlite3\n"
                        "  brew install python@3.11\n\n"
                        "Or using MacPorts:\n"
                        "  sudo port install sqlite3 +loadext\n"
                        "  sudo port install python311\n\n"
                        "Then reinstall ScriptRAG in a fresh virtual environment:\n"
                        "  python3.11 -m venv .venv\n"
                        "  source .venv/bin/activate\n"
                        "  pip install -e .\n\n"
                        "For more details, see: https://github.com/yourusername/scriptrag/wiki/macOS-Setup"
                    ),
                    details={
                        "system": system,
                        "sqlite_version": sqlite3.sqlite_version,
                        "python_version": sys.version,
                    }
                )
            else:
                raise DependencyError(
                    message=f"SQLite on {system} doesn't support extensions",
                    hint="Your SQLite installation doesn't support loadable extensions. "
                         "Please install SQLite with extension support enabled.",
                    details={
                        "system": system,
                        "sqlite_version": sqlite3.sqlite_version,
                    }
                )

        # Try to actually load the extension
        try:
            conn.enable_load_extension(True)
            import sqlite_vec
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception as e:
            raise DependencyError(
                message="Failed to load sqlite-vec extension",
                hint="sqlite-vec extension could not be loaded. "
                     "Ensure sqlite-vec is installed: pip install sqlite-vec",
                details={"error": str(e)}
            ) from e

    finally:
        if conn:
            conn.close()


def check_all_dependencies() -> None:
    """Check all required dependencies for ScriptRAG.

    Raises:
        DependencyError: If any required dependency is missing or incompatible
    """
    check_sqlite_vss_support()
    # Add other dependency checks here as needed
```

### 3. Add Startup Check to CLI ✅

**File**: `src/scriptrag/cli/main.py`

Add dependency check at startup:

```python
import typer
from scriptrag.utils.dependency_check import check_all_dependencies
from scriptrag.exceptions import DependencyError

app = typer.Typer()

@app.callback()
def main_callback(ctx: typer.Context):
    """ScriptRAG - Git-native screenplay analysis."""
    # Skip dependency check for help commands
    if ctx.invoked_subcommand in ["--help", None]:
        return

    try:
        check_all_dependencies()
    except DependencyError as e:
        typer.secho(f"❌ Dependency Error: {e.message}", fg=typer.colors.RED, err=True)
        if e.hint:
            typer.secho(f"\n{e.hint}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)
```

### 4. Update Documentation ✅

**File**: `README.md`

Add explicit SQLite requirements:

```markdown
## System Requirements

- Python 3.11+
- uv package manager (will be installed if not present)
- **SQLite 3.38+ with loadable extension support** ⚠️
  - **macOS**: Requires Homebrew/MacPorts SQLite (see [macOS Setup](#macos-setup))
  - **Linux**: Usually supported by default
  - **Windows**: Supported by default Python installation

### macOS Setup

macOS users **must** install SQLite with extension support:

#### Option 1: Using Homebrew (Recommended)
```bash
# Install SQLite with extensions
brew install sqlite3

# Install Python linked to Homebrew SQLite
brew install python@3.11

# Create virtual environment with Homebrew Python
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
source .venv/bin/activate

# Install ScriptRAG
pip install -e .
```

#### Option 2: Using MacPorts

```bash
sudo port install sqlite3 +loadext
sudo port install python311
```

#### Verification

```bash
# Test SQLite extension support
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); print('✅ SQLite extensions supported')"
```

### 5. Update GitHub Actions Workflow ✅

**File**: `.github/workflows/ci.yml`

Add SQLite installation steps to the test-matrix job (after line 244, before Python setup):

```yaml
  test-matrix:
    name: Test Python ${{ matrix.python-version }} on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    # ... existing configuration ...

    steps:
      - uses: actions/checkout@v4

      # ADD THIS BLOCK: macOS SQLite with extension support
      - name: Install SQLite with extensions (macOS)
        if: runner.os == 'macOS'
        run: |
          brew update
          brew install sqlite3
          # Export for Python to find the right SQLite
          echo "LDFLAGS=-L$(brew --prefix sqlite3)/lib" >> $GITHUB_ENV
          echo "CPPFLAGS=-I$(brew --prefix sqlite3)/include" >> $GITHUB_ENV
          echo "PKG_CONFIG_PATH=$(brew --prefix sqlite3)/lib/pkgconfig" >> $GITHUB_ENV

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      # ADD THIS BLOCK: Rebuild sqlite3 module on macOS
      - name: Rebuild Python sqlite3 (macOS)
        if: runner.os == 'macOS'
        run: |
          pip install --no-binary :all: --force-reinstall pysqlite3-binary

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        # ... rest of existing workflow ...

      # ADD THIS BLOCK: Before running tests
      - name: Verify SQLite extension support
        run: |
          python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); print('SQLite extensions supported')"
        shell: bash
```

Also update the test-canary job (around line 163) with the same SQLite setup for consistency.

### 6. Update Exception Handling ✅

**File**: `src/scriptrag/exceptions.py`

Add DependencyError if not already present:

```python
class DependencyError(ScriptRAGError):
    """Raised when a required system dependency is missing or incompatible."""

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        details: dict[str, Any] | None = None
    ):
        super().__init__(message=message, hint=hint, details=details)
```

### 7. Update Tests ✅

**File**: `tests/unit/test_vss_service.py`

Remove the mocking workaround in fixture since we now require real SQLite extension support:

```python
@pytest.fixture
def vss_service(mock_settings, tmp_path):
    """Create VSS service with in-memory database."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    # For unit tests, we still mock sqlite_vec to avoid actual extension loading
    with patch("scriptrag.storage.vss_service.sqlite_vec.load"):
        service = VSSService(mock_settings, db_path)
        # ... rest of fixture
```

Add new test for dependency checking:

```python
# tests/unit/test_dependency_check.py
import pytest
from unittest.mock import patch, MagicMock
from scriptrag.utils.dependency_check import check_sqlite_vss_support
from scriptrag.exceptions import DependencyError


def test_sqlite_vss_check_fails_without_extension_support():
    """Test that check fails when SQLite lacks extension support."""
    mock_conn = MagicMock()
    # Simulate macOS default SQLite (no enable_load_extension)
    del mock_conn.enable_load_extension

    with patch("sqlite3.connect", return_value=mock_conn):
        with patch("platform.system", return_value="Darwin"):
            with pytest.raises(DependencyError) as exc_info:
                check_sqlite_vss_support()

            assert "macOS ships with SQLite" in exc_info.value.hint
            assert "brew install sqlite3" in exc_info.value.hint
```

## Testing Requirements

### Local Testing

1. Test on macOS with default SQLite (should fail with clear error)
2. Test on macOS with Homebrew SQLite (should work)
3. Test on Linux (should work by default)
4. Test on Windows (should work by default)

### CI Testing

1. Verify GitHub Actions successfully installs SQLite with extensions on macOS
2. Verify all tests pass on all platforms
3. Verify dependency check provides helpful error messages

## Migration Path for Users

For users who have already installed ScriptRAG on macOS:

1. **Uninstall current environment**:

   ```bash
   deactivate
   rm -rf .venv
   ```

2. **Install proper SQLite**:

   ```bash
   brew install sqlite3 python@3.11
   ```

3. **Reinstall ScriptRAG**:

   ```bash
   /opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

## References

- Current PR with graceful degradation: `terragon/implement-scene-embedding-search` (commit: 04b9f04)
- Current CI workflow: `.github/workflows/ci.yml` (runs on macOS-latest without SQLite extension setup)
- SQLite extension loading issue: <https://github.com/python/cpython/issues/55023>
- SQLite-vec documentation: <https://github.com/asg017/sqlite-vec>
- Original test failure: `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'`
- Files modified in temporary fix:
  - `src/scriptrag/storage/vss_service.py` (lines 85-94)
  - `tests/unit/test_vss_service.py` (fixture modification)

## Success Criteria

- [ ] ScriptRAG fails immediately on macOS without proper SQLite, with helpful error message
- [ ] Documentation clearly states SQLite extension requirement
- [ ] macOS users have clear installation instructions
- [ ] GitHub Actions tests pass on macOS with proper SQLite installed
- [ ] No silent failures or degraded functionality

## Estimated Effort

- **Priority**: High (blocks macOS users)
- **Complexity**: Medium
- **Estimated Time**: 4-6 hours
- **Story Points**: 8

## Labels

- `bug`
- `dependencies`
- `macos`
- `documentation`
- `ci/cd`
