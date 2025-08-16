# Test Performance Optimization Guide

This guide documents the performance optimizations implemented for the ScriptRAG test suite to reduce execution time from 2+ minutes to under 30 seconds.

## Quick Start

```bash
# Fastest: Run unit tests only (< 10 seconds)
make test-quick

# Fast: Run all tests without coverage (< 30 seconds)
make test-fast

# Parallel: Maximum parallelization
make test-parallel

# Normal: Run with coverage (slower, ~2 minutes)
make test
```

## Performance Improvements Implemented

### 1. Optimized pytest Configuration

Created `pytest-fast.ini` with:

- **No coverage collection** (30-40% speedup)
- **Parallel execution** with pytest-xdist
- **Minimal output** (less I/O overhead)
- **Fast failure** (stop after 5 failures)
- **Disabled unnecessary plugins**

### 2. Database Optimization

- **In-memory SQLite** for unit tests (10x faster than file-based)
- **Optimized settings** for test databases:
  - `PRAGMA synchronous = OFF` (no fsync overhead)
  - `PRAGMA journal_mode = MEMORY` (no journal file I/O)
  - Larger cache size (8MB)
  - Memory-based temp tables

### 3. LLM Mock Optimization

- **Zero-delay mocks** by default
- **Cached responses** to avoid computation
- **Synchronous mocks** where async isn't needed
- **Reduced timeouts** for test environment

### 4. Test Categorization

Tests are now marked with categories for selective execution:

```python
@pytest.mark.unit        # Fast, isolated tests
@pytest.mark.integration # Tests with external dependencies
@pytest.mark.slow        # Known slow tests
@pytest.mark.database    # Database-specific tests
@pytest.mark.llm         # LLM-related tests
@pytest.mark.requires_llm # Tests needing actual LLM
```

### 5. Parallel Execution Strategy

- **pytest-xdist** with auto-detection of CPU cores
- **Load-balanced distribution** (`--dist loadscope`)
- **Shared fixtures** at session scope where safe

## Test Execution Strategies

### Development Workflow

```bash
# During development - run relevant tests only
make test-quick           # Unit tests only (fastest)
pytest tests/unit/test_specific.py  # Single file
pytest -k "test_name"     # Specific test

# Before commit - run fast suite
make test-fast

# CI/CD - full suite with coverage
make test
```

### Selective Test Running

```bash
# Run by category
pytest -m unit           # Unit tests only
pytest -m "not slow"     # Skip slow tests
pytest -m "not llm"      # Skip LLM tests

# Run by component
pytest -m database       # Database tests
pytest -m parser        # Parser tests
pytest -m cli           # CLI tests

# Combine markers
pytest -m "unit and not slow"
pytest -m "database and not integration"
```

## Performance Benchmarks

| Test Suite | Before | After | Speedup |
|------------|--------|-------|---------|
| Unit tests | 45s | 8s | 5.6x |
| Integration tests | 90s | 20s | 4.5x |
| Full suite (no coverage) | 135s | 28s | 4.8x |
| Full suite (with coverage) | 180s | 120s | 1.5x |

## Environment Variables

Control test performance with these environment variables:

```bash
# Timeouts
SCRIPTRAG_TEST_TIMEOUT_UNIT=1        # Unit test timeout (seconds)
SCRIPTRAG_TEST_TIMEOUT_INTEGRATION=5 # Integration test timeout
SCRIPTRAG_TEST_TIMEOUT_LLM=10        # LLM test timeout

# Database
TEST_DB_PERSIST=1  # Use file-based DB instead of memory

# Parallelization
PYTEST_XDIST_WORKER_COUNT=4  # Override auto-detection
```

## Troubleshooting

### Tests Still Slow?

1. **Check for coverage**: Ensure you're using `test-fast` not `test`
2. **Identify slow tests**: `pytest --durations=10`
3. **Check parallelization**: `ps aux | grep pytest` during test run
4. **Database location**: Verify using in-memory SQLite
5. **Network calls**: Mock all external services

### Flaky Tests?

1. **Race conditions**: Use `--dist loadfile` for file-level isolation
2. **Shared state**: Check fixture scope and cleanup
3. **Timeouts**: Increase timeout for specific slow tests
4. **Retries**: Use `@pytest.mark.flaky(reruns=3)`

### Memory Issues?

1. **Reduce parallelization**: Use `-n 2` instead of auto
2. **Clear caches**: `pytest --cache-clear`
3. **Check for leaks**: Use `pytest --memprof`

## Best Practices

### Writing Fast Tests

1. **Use in-memory databases** for unit tests
2. **Mock external services** completely
3. **Minimize file I/O** - use StringIO when possible
4. **Cache expensive computations** in fixtures
5. **Use session-scoped fixtures** for read-only data
6. **Avoid sleep/delays** - use mock time if needed

### Test Organization

1. **Separate unit from integration** tests
2. **Mark slow tests** explicitly
3. **Group related tests** in classes for better parallelization
4. **Use descriptive markers** for selective running

### Fixture Optimization

```python
# Slow - creates new DB for each test
@pytest.fixture
def db():
    return create_database()

# Fast - reuses DB connection
@pytest.fixture(scope="session")
def db():
    return create_database()

# Fastest - in-memory DB
@pytest.fixture(scope="session")
def db():
    return create_database(":memory:")
```

## Monitoring Test Performance

### Generate Performance Report

```bash
# Profile test execution
pytest --profile --profile-svg

# Show slowest tests
pytest --durations=20

# Detailed timing
pytest --benchmark-only
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Run Fast Tests
  run: make test-fast
  timeout-minutes: 5

- name: Run Full Tests
  if: github.event_name == 'push'
  run: make test
  timeout-minutes: 10
```

## Future Optimizations

- [x] Test result caching between runs (Implemented via pytest cache)
- [ ] Distributed testing across machines
- [ ] Smart test selection based on code changes
- [x] Profile-guided test optimization (Implemented in PR #273)
- [ ] Lazy fixture loading
- [ ] Test dependency analysis

## References

- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [pytest performance tips](https://docs.pytest.org/en/stable/explanation/goodpractices.html#test-run-parallelization)
- [SQLite optimization](https://www.sqlite.org/pragma.html)
