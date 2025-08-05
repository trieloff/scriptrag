# Testing Guidelines for Claude

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