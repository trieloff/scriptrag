# Enhanced MagicMock File Detection System - Summary

## Overview

I've implemented an enhanced detection system to trace MagicMock file contamination down to individual test cases. This solves the problem where the test matrix fails due to mock files being created in the filesystem.

## Components Created

### 1. **Core Detection Module** (`tests/detect_mock_files.py`)

- **MockFileDetector**: Scans for mock file artifacts using comprehensive patterns
- **TestMockFileTracker**: Tracks mock files created during test execution
- Detects patterns like:
  - `<MagicMock name='...' id='...'>`
  - Files with `Mock` and `name=` in path
  - Files with `id='...'` patterns
  - Hex ID patterns (`id=0x...`)

### 2. **Pytest Plugin** (`tests/conftest_mock_detection.py`)

- Integrates with pytest to track each test individually
- Takes baseline snapshot before tests
- Monitors after each test for new mock files
- Reports which specific test created which files
- Can optionally fail tests that create mock files

### 3. **Integration with Existing Tests** (updated `tests/conftest.py`)

- Seamlessly integrates the detection plugin
- Backward compatible - only activates when requested
- Works alongside existing test infrastructure

### 4. **Convenience Scripts**

- `tests/run_with_mock_detection.sh`: Runs tests with tracking enabled
- Makefile targets:
  - `make detect-mock-files`: Check for existing mock files
  - `make test-trace-mocks`: Run tests with per-test tracking
  - `make clean-mock-files`: Clean up mock artifacts

### 5. **Documentation**

- `docs/MOCK_FILE_DETECTION.md`: Comprehensive usage guide
- `tests/test_mock_detection_demo.py`: Working examples

## How It Works

### Detection Process

1. **Baseline Phase**: Before tests start, scan for any pre-existing mock files
2. **Test Monitoring**: After each test, check for new files
3. **Pattern Analysis**: Identify files matching mock patterns
4. **Attribution**: Link each mock file to the specific test that created it
5. **Reporting**: Provide detailed report showing test→file mappings

### Usage Examples

```bash
# Basic detection
python tests/detect_mock_files.py

# Run specific test with tracking
pytest tests/test_scene_management.py --track-mock-files

# Run all tests and identify problematic ones
make test-trace-mocks

# Clean up any mock files
make clean-mock-files
```

### Test Output Example

When a test creates mock files, you'll see:

```text
⚠️  Test 'tests/test_example.py::test_bad_function' created 2 mock file(s)
     - <MagicMock name='path' id='140234567890'>
     - test_MockFile_name='config'.txt
```

## Benefits

1. **Precise Attribution**: Know exactly which test creates mock files
2. **Early Detection**: Catch issues during development, not in CI
3. **Easy Cleanup**: Automated tools to remove mock artifacts
4. **Prevention Guidance**: Clear documentation on how to fix issues
5. **CI Integration**: Can be added to CI pipeline to prevent regression

## Common Fixes

When tests are identified as creating mock files:

### Fix 1: Use spec_set

```python
# Before (creates artifacts)
mock = MagicMock()

# After (safe)
mock = MagicMock(spec_set=SomeClass)
```

### Fix 2: Use tmp_path fixture

```python
# Before (creates artifacts)
mock_path = MagicMock()
Path(mock_path).write_text("data")

# After (safe)
def test_something(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("data")
```

### Fix 3: Proper patch configuration

```python
# Before (unsafe)
@patch('module.function')

# After (safe)
@patch('module.function', autospec=True)
```

## Integration with CI

The system can be integrated into CI pipelines:

```yaml
# GitHub Actions example
- name: Run tests with mock detection
  run: |
    make test-trace-mocks
    # Or use environment variable
    PYTEST_TRACK_MOCK_FILES=1 pytest
```

## Next Steps

1. **Run Initial Scan**: Use `make test-trace-mocks` to identify all problematic tests
2. **Fix Identified Tests**: Update tests using the patterns above
3. **Add to CI**: Enable `--fail-on-mock-files` in CI to prevent regression
4. **Monitor**: Use periodic checks to ensure no new issues

## Technical Details

### Pattern Matching

The detector uses regex patterns to identify mock files:

```python
MOCK_PATTERNS = [
    re.compile(r".*Mock.*name=.*"),      # Mock with name parameter
    re.compile(r"<Mock.*"),              # Starting with <Mock
    re.compile(r".*<Mock.*"),            # Containing <Mock
    re.compile(r".*id='.*'.*"),         # ID pattern
    re.compile(r".*MagicMock.*"),       # Containing MagicMock
    re.compile(r".*\bid=0x[0-9a-f]+\b.*"), # Hex ID pattern
]
```

### Excluded Directories

The system automatically excludes:

- `.git`, `__pycache__`, `.pytest_cache`
- Virtual environments (`.venv`, `venv`)
- Cache directories (`.mypy_cache`, `.ruff_cache`)
- Coverage and test output directories

## Conclusion

This enhanced detection system provides the tools needed to:

1. Identify which specific tests create mock file artifacts
2. Understand why the contamination happens
3. Fix the problematic tests
4. Prevent future occurrences

The system is non-invasive, backward compatible, and provides clear actionable information to resolve the test matrix failures.
