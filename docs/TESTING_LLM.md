# LLM Testing Guide

This document explains how to run and configure tests that depend on LLM (Large Language Model) providers in ScriptRAG.

## Overview

ScriptRAG includes tests that interact with LLM providers for screenplay analysis. These tests are handled differently in CI and local environments due to:

- Rate limiting concerns
- API costs
- Network reliability
- Execution time

## Test Categories

### 1. Unit Tests (No LLM Required)

- **Marker**: `@pytest.mark.unit`
- **Timeout**: 10 seconds
- **Description**: Fast tests that mock all LLM interactions
- **Always run**: Yes

### 2. Integration Tests (Mock LLM by Default)

- **Marker**: `@pytest.mark.integration`
- **Timeout**: 30 seconds
- **Description**: Test full workflows with mocked LLM providers
- **Always run**: Yes

### 3. LLM Tests (Real Providers)

- **Marker**: `@pytest.mark.requires_llm`
- **Timeout**: 60-120 seconds
- **Description**: Tests that use actual LLM providers
- **Run conditionally**: Only when explicitly enabled

## Running Tests Locally

### Quick Test (No LLM)

```bash
# Run all tests except those requiring real LLMs
make test

# Run only unit tests
pytest -m unit

# Run integration tests with mocked LLMs
pytest -m integration
```

### Full Test Suite (Including LLM Tests)

⚠️ **SECURITY WARNING**: Never use real API keys in test environments!

- Use test/dummy API keys for local testing
- Store production credentials securely (e.g., using a secrets manager)
- Never commit credentials to version control
- Consider using tools like `direnv` or `dotenv` for local development

```bash
# Enable LLM tests locally
export SCRIPTRAG_TEST_LLMS=1

# Configure your LLM providers with TEST credentials only
# NEVER use production API keys here!
export GITHUB_TOKEN="test-token-only"  # pragma: allowlist secret
export SCRIPTRAG_LLM_API_KEY="test-key-only"  # pragma: allowlist secret
export SCRIPTRAG_LLM_ENDPOINT="https://api.openai.com/v1"

# For production/real API testing, use secure credential management:
# - Environment-specific config files (not in git)
# - CI/CD secret management
# - Cloud provider secret managers (AWS Secrets Manager, Azure Key Vault, etc.)

# Run all tests including LLM tests
pytest

# Run only LLM tests
pytest -m requires_llm
```

### Test with Specific Timeout

```bash
# Override default timeout for all tests
pytest --timeout=120

# Run specific test with custom timeout
pytest tests/integration/test_full_workflow.py::TestFullWorkflow::test_workflow_with_real_llm --timeout=180
```

## Running Tests in CI

### Default CI Behavior

- LLM tests are **automatically skipped** in CI environments
- This prevents rate limiting and reduces CI time
- Mock providers are used for integration tests

### Enabling LLM Tests in CI

```yaml
# GitHub Actions example
env:
  SCRIPTRAG_TEST_LLMS: 1
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  SCRIPTRAG_LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
```

### CI Environment Detection

The test suite automatically detects CI environments by checking:

- `CI` environment variable
- `GITHUB_ACTIONS` environment variable

## Test Timeout Configuration

### Per-Test Type Timeouts

Timeout values can be configured via environment variables for different CI/test environments:

```bash
# Custom timeout configuration (optional)
export SCRIPTRAG_TEST_TIMEOUT_UNIT=10        # Default: 10 seconds
export SCRIPTRAG_TEST_TIMEOUT_INTEGRATION=30  # Default: 30 seconds
export SCRIPTRAG_TEST_TIMEOUT_LLM=60         # Default: 60 seconds
export SCRIPTRAG_TEST_TIMEOUT_LLM_LONG=120   # Default: 120 seconds
```

```python
from tests.llm_test_utils import (
    TIMEOUT_UNIT,        # Configurable via SCRIPTRAG_TEST_TIMEOUT_UNIT
    TIMEOUT_INTEGRATION, # Configurable via SCRIPTRAG_TEST_TIMEOUT_INTEGRATION
    TIMEOUT_LLM,        # Configurable via SCRIPTRAG_TEST_TIMEOUT_LLM
    TIMEOUT_LLM_LONG,   # Configurable via SCRIPTRAG_TEST_TIMEOUT_LLM_LONG
)

@pytest.mark.timeout(TIMEOUT_LLM)
def test_with_llm():
    # Test with configurable timeout (default: 60 seconds)
    pass
```

### Global Timeout

Set in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = [
    "--timeout=300",  # 5-minute global timeout
    "--timeout-method=thread",  # Thread-based timeout
]
```

## Mock LLM Providers

### Using Mock Providers in Tests

```python
from tests.llm_test_utils import MockLLMProvider, mock_llm_client

@pytest.mark.integration
async def test_with_mock_llm(mock_llm_client):
    # Use the pre-configured mock client
    response = await mock_llm_client.complete(request)
    assert response.choices[0]["text"] == "Mock response"
```

### Configuring Mock Behavior

```python
from tests.llm_test_utils import MockLLMProvider

# Create provider with simulated delays
provider = MockLLMProvider(
    response_delay=0.5,  # 500ms delay
    fail_after_n_calls=3,  # Fail after 3 calls
    rate_limit_after_n_calls=5  # Rate limit after 5 calls
)
```

### Using Test Fixtures

```python
from tests.llm_fixtures import (
    get_scene_analysis_response,
    get_character_analysis_response,
    create_llm_completion_response
)

# Get pre-defined responses
scene_analysis = get_scene_analysis_response("coffee_shop")
character_analysis = get_character_analysis_response("SARAH")

# Create JSON response for mocking
mock_response = create_llm_completion_response("scene", "coffee_shop")
```

## Retry Logic for Flaky Tests

### Automatic Retry Decorator

```python
from tests.llm_test_utils import retry_flaky_test

@retry_flaky_test(max_attempts=3, wait_min=1, wait_max=10)
def test_that_might_be_flaky():
    # Test will retry up to 3 times with exponential backoff
    pass
```

### When to Use Retries

- Network-dependent tests
- Tests with race conditions
- Tests affected by rate limiting
- Tests with timing dependencies

## Debugging Test Timeouts

### 1. Check Test Markers

```bash
# List all test markers
pytest --markers

# Run tests with verbose output
pytest -vv tests/integration/test_llm_timeout_handling.py
```

### 2. Increase Timeout for Debugging

```bash
# Disable timeout completely for debugging
pytest --timeout=0 tests/failing_test.py

# Use very long timeout
pytest --timeout=600 tests/slow_test.py
```

### 3. Check Mock Configuration

```python
# Ensure mocks are properly configured
with patch("scriptrag.utils.get_default_llm_client") as mock_client:
    mock_client.return_value = create_mock_llm_client_sync()
    # Your test code
```

## Best Practices

### 1. Always Mock in Unit Tests

- Unit tests should never make real LLM calls
- Use `MockLLMProvider` or patch LLM clients
- Keep unit tests fast (<1 second each)

### 2. Use Appropriate Timeouts

- Unit tests: 10 seconds max
- Integration tests: 30 seconds max
- LLM tests: 60-120 seconds
- Use `@pytest.mark.timeout()` for specific needs

### 3. Handle Rate Limiting

- Use retry decorators for flaky tests
- Mock LLM providers in CI
- Implement exponential backoff
- Cache responses when possible

### 4. Test Categories

- Mark tests appropriately: `unit`, `integration`, `requires_llm`
- Skip expensive tests in CI by default
- Document special requirements

### 5. Mock Responses

- Use consistent fixtures from `llm_fixtures.py`
- Create realistic mock responses
- Test error conditions with mock errors
- Simulate delays and failures

## Troubleshooting

### Problem: Tests timeout in CI but pass locally

**Solution**: Check if LLM tests are accidentally enabled in CI. Ensure `SCRIPTRAG_TEST_LLMS` is not set.

### Problem: Rate limit errors

**Solution**:

1. Use mock providers in tests
2. Add retry logic with exponential backoff
3. Reduce parallel test execution

### Problem: Inconsistent test failures

**Solution**:

1. Add `@retry_flaky_test` decorator
2. Increase timeout values
3. Check for race conditions
4. Use proper async/await patterns

### Problem: Mock not being used

**Solution**:

1. Verify patch location is correct
2. Check import order
3. Ensure async mocks for async functions
4. Use `AsyncMock` for coroutines

## Example Test File

```python
"""Example test file with proper LLM handling."""

import pytest
from unittest.mock import patch

from tests.llm_test_utils import (
    TIMEOUT_INTEGRATION,
    mock_llm_client,
    retry_flaky_test,
)
from tests.llm_fixtures import create_llm_completion_response


class TestScreenplayAnalysis:

    @pytest.mark.unit
    @pytest.mark.timeout(10)
    def test_parse_scene_no_llm(self):
        """Unit test without LLM dependency."""
        # Test scene parsing logic without LLM
        pass

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    async def test_analyze_with_mock(self, mock_llm_client):
        """Integration test with mocked LLM."""
        # Use mock client for fast, reliable testing
        response = await mock_llm_client.complete(request)
        assert response is not None

    @pytest.mark.requires_llm
    @pytest.mark.timeout(60)
    @retry_flaky_test(max_attempts=2)
    async def test_analyze_with_real_llm(self):
        """Test with real LLM (skipped in CI by default)."""
        # This test only runs when SCRIPTRAG_TEST_LLMS=1
        from scriptrag.utils import get_default_llm_client
        client = await get_default_llm_client()
        # Perform real LLM operations
        pass
```

## Related Documentation

- [TESTING.md](TESTING.md) - General testing guidelines
- [README.md](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
