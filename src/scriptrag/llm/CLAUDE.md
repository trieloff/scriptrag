# LLM Integration Guidelines

## Overview

The LLM integration layer provides a multi-provider abstraction for language model interactions. This module has required significant iteration due to rate limiting, error handling, and provider-specific quirks.

## Common Iteration Points (Learn from Past Development)

### 1. Rate Limiting Issues

**Problem**: GitHub Models API has aggressive rate limiting that caused frequent failures.

**Solution Pattern**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def call_with_retry(self, prompt: str) -> dict:
    """Call LLM with exponential backoff."""
    try:
        return await self._make_request(prompt)
    except RateLimitError as e:
        self.logger.warning(f"Rate limit hit, retry after {e.retry_after}s")
        raise
```

### 2. JSON Extraction Failures

**Problem**: LLMs don't always return valid JSON despite instructions.

**Solution Pattern**:
```python
def extract_json(self, response: str) -> dict:
    """Extract JSON from LLM response with multiple fallback strategies."""
    # Try direct parsing
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown
    json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON-like structure
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from response: {response[:200]}")
```

### 3. Model Discovery Limitations

**Problem**: Dynamic model discovery often fails or returns incomplete lists.

**Solution**: Use static model lists with fallback:
```python
KNOWN_MODELS = {
    "gpt-4": {"context": 8192, "provider": "openai"},
    "claude-3-opus": {"context": 200000, "provider": "anthropic"},
    "llama-3-70b": {"context": 8192, "provider": "meta"},
}

def get_available_models(self) -> list[str]:
    """Get available models with static fallback."""
    try:
        # Try dynamic discovery
        models = self._discover_models()
        if models:
            return models
    except Exception as e:
        self.logger.warning(f"Model discovery failed: {e}")

    # Fall back to known models
    return list(KNOWN_MODELS.keys())
```

### 4. Timeout Handling

**Problem**: Long-running LLM calls timeout in CI environments.

**Solution**:
```python
DEFAULT_TIMEOUT = 30  # seconds
CI_TIMEOUT = 60  # longer timeout for CI

async def complete(self, prompt: str, timeout: int = None) -> str:
    """Complete with appropriate timeout."""
    if timeout is None:
        timeout = CI_TIMEOUT if os.getenv("CI") else DEFAULT_TIMEOUT

    try:
        async with asyncio.timeout(timeout):
            return await self._complete_impl(prompt)
    except asyncio.TimeoutError:
        self.logger.error(f"LLM call timed out after {timeout}s")
        raise
```

## Type Annotation Patterns

The LLM module uses complex generics and async types:

```python
from typing import TypeVar, Generic, Protocol

T = TypeVar("T", bound="BaseLLMProvider")

class LLMProvider(Protocol):
    """Protocol for LLM providers."""
    async def complete(self, prompt: str) -> str: ...
    async def complete_json(self, prompt: str) -> dict: ...

class LLMClient(Generic[T]):
    """Generic client supporting multiple providers."""
    providers: dict[str, T]

    async def complete(
        self,
        prompt: str,
        provider: str | None = None
    ) -> str:
        """Complete using specified or default provider."""
        ...
```

## Testing Guidelines

### Unit Tests
Always mock LLM calls in unit tests:
```python
@patch("scriptrag.llm.client.LLMClient.complete")
def test_scene_analysis(mock_complete):
    mock_complete.return_value = '{"scene_type": "action"}'
    # Test logic here
```

### Integration Tests
- Disabled by default in CI (set `ENABLE_LLM_TESTS=1` to enable)
- Use smallest/fastest models for testing
- Implement proper retry logic
- Cache responses when possible

## Provider-Specific Notes

### GitHub Models (`github_models.py`)
- **Rate Limits**: 15 requests per minute for free tier
- **Authentication**: Requires `GITHUB_TOKEN` environment variable
- **Model List**: Static list, discovery often incomplete
- **Error Codes**: 429 for rate limit, 401 for auth issues

### Claude Code (`claude_code.py`)
- **Context Window**: Very large (200k tokens)
- **JSON Mode**: Supports structured output
- **Timeout**: Longer timeouts needed for complex tasks
- **Error Handling**: Detailed error messages in responses

### OpenAI Compatible (`openai.py`)
- **Standard API**: Works with many providers
- **Streaming**: Supports streaming responses
- **Function Calling**: Structured output via functions
- **Cost Tracking**: Token usage in responses

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `RateLimitError` | Too many requests | Implement exponential backoff |
| `JSONDecodeError` | Invalid JSON response | Use extraction fallbacks |
| `TimeoutError` | Slow model response | Increase timeout, use faster model |
| `AuthenticationError` | Invalid API key | Check environment variables |
| `ModelNotFoundError` | Unknown model | Use static model list |

## Best Practices

1. **Always implement retry logic** for production use
2. **Mock LLM calls** in unit tests
3. **Use structured prompts** for consistent JSON output
4. **Log all errors** with context for debugging
5. **Implement fallbacks** for model selection
6. **Cache responses** when appropriate
7. **Monitor token usage** to control costs
8. **Use appropriate timeouts** for different environments

## Files Requiring Special Attention

- `client.py` (490 lines) - Complex multi-provider abstraction
- `providers/claude_code.py` (506 lines) - Sophisticated error handling
- `providers/github_models.py` (438 lines) - Rate limiting complexity

These files are at the upper limit of recommended size and may benefit from refactoring into smaller, more focused modules.
