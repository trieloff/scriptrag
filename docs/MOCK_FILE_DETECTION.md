# Mock File Detection Guide

## Problem

Tests using Python's `MagicMock` can inadvertently create file system artifacts when mock objects are used as file paths or converted to strings that become filenames. These artifacts have names like:

- `<MagicMock name='...' id='...'>`
- Files containing `Mock` and `name=` in the path
- Files with `id='...'` patterns

## Enhanced Detection System

This project now includes an enhanced detection system to trace which specific tests create mock file artifacts.

## Quick Commands

```bash
# Detect any existing mock files
make detect-mock-files

# Run tests with tracking to identify problematic tests
make test-trace-mocks

# Clean up any mock files
make clean-mock-files
```

## Detailed Usage

### 1. Basic Detection

Check for mock files in the current project:

```bash
python tests/detect_mock_files.py
```

With cleanup:

```bash
python tests/detect_mock_files.py --clean
```

### 2. Test-Level Tracking

Run tests with per-test tracking to identify which specific tests create mock files:

```bash
pytest --track-mock-files
```

To fail tests that create mock files:

```bash
pytest --track-mock-files --fail-on-mock-files
```

### 3. Environment Variables

Enable tracking via environment variable:

```bash
PYTEST_TRACK_MOCK_FILES=1 pytest
```

### 4. Marking Tests

If a test legitimately needs to create files with mock-like names, mark it:

```python
@pytest.mark.allow_mock_files
def test_that_creates_mock_files():
    # Test code here
    pass
```

## How It Works

The detection system:

1. **Takes a baseline snapshot** before tests run
2. **Monitors the filesystem** after each test
3. **Reports new mock files** created by each test
4. **Provides detailed analysis** of the mock file patterns

## Common Causes

Mock files are typically created when:

1. **Using MagicMock without spec**:

   ```python
   # ❌ BAD - Can create filesystem artifacts
   mock_path = MagicMock()
   Path(mock_path).write_text("data")

   # ✅ GOOD - Use spec_set to prevent misuse
   mock_path = MagicMock(spec_set=Path)
   ```

2. **Converting mocks to strings for file operations**:

   ```python
   # ❌ BAD - Mock's string representation becomes filename
   mock = MagicMock()
   with open(mock, 'w') as f:
       f.write("data")

   # ✅ GOOD - Use proper string values
   filename = "test.txt"
   with open(filename, 'w') as f:
       f.write("data")
   ```

3. **Missing spec in patch decorators**:

   ```python
   # ❌ BAD - No spec constraint
   @patch('module.function')
   def test_something(mock_func):
       pass

   # ✅ GOOD - Use autospec for safety
   @patch('module.function', autospec=True)
   def test_something(mock_func):
       pass
   ```

## Integration with CI

The Makefile includes validation that runs before and after tests:

```bash
# Before tests
make test  # Automatically checks for pre-existing mock files

# After tests  
make test  # Automatically validates no new mock files were created
```

## Detection Patterns

The system detects files matching these patterns:

- `*Mock*name=*` - Files with Mock and name= in path
- `<Mock*` - Files starting with <Mock
- `*<Mock*` - Files containing <Mock
- `*id='*'*` - Files with id='...' pattern
- `*MagicMock*` - Files containing MagicMock
- `*spec=*` - Files with spec= in name
- `*\bid=0x[0-9a-f]+\b*` - Files with hex id pattern

## Troubleshooting

### Finding the Culprit Test

1. Run with tracking enabled:

   ```bash
   make test-trace-mocks
   ```

2. Look for output like:

   ```text
   ⚠️  Test 'tests/test_example.py::test_function' created 2 mock file(s)
        - <MagicMock name='path' id='140234567890'>
        - <MagicMock name='file' id='140234567891'>
   ```

3. Fix the identified test by:
   - Adding `spec_set=True` to mocks
   - Using proper string values instead of mock objects
   - Properly configuring patch decorators

### Cleaning Up

If mock files accumulate:

```bash
# Clean mock files only
make clean-mock-files

# Or clean everything
make clean-all
```

## Best Practices

1. **Always use spec or spec_set** when creating mocks
2. **Never use mock objects directly as file paths**
3. **Use autospec=True in patch decorators**
4. **Run `make test-trace-mocks` locally before pushing**
5. **Fix tests immediately when they create mock files**

## Example Fix

Before (creates mock files):

```python
def test_file_operation():
    mock_path = MagicMock()
    # This creates a file named "<MagicMock id='...'>"
    Path(mock_path).write_text("content")
```

After (fixed):

```python
def test_file_operation(tmp_path):
    test_file = tmp_path / "test.txt"
    # This creates a proper temporary file
    test_file.write_text("content")
```

## CI Integration

### GitHub Actions

```yaml
name: Test with Mock Detection

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest

      - name: Run tests with mock detection
        run: |
          python tests/ci_mock_detection.py \
            --github-annotations \
            --junit mock-report.xml \
            --fail-on-baseline

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: mock-detection-report
          path: mock-report.xml
```

### GitLab CI

```yaml
test-with-mock-detection:
  script:
    - pip install -e .
    - python tests/ci_mock_detection.py --junit mock-report.xml
  artifacts:
    when: always
    reports:
      junit: mock-report.xml
```

### CircleCI

```yaml
version: 2.1
jobs:
  test:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: pip install -e . pytest
      - run:
          name: Run tests with mock detection
          command: |
            python tests/ci_mock_detection.py \
              --junit $CIRCLE_TEST_REPORTS/mock-detection.xml
      - store_test_results:
          path: $CIRCLE_TEST_REPORTS
```
