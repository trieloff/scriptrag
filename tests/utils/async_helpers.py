"""Async test utilities for ScriptRAG testing."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


@asynccontextmanager
async def async_mock_api(api_class: type, **method_returns: Any):
    """Context manager for mocking async APIs.

    Args:
        api_class: The API class to mock
        **method_returns: Method names and their return values

    Example:
        async with async_mock_api(
            SceneManagementAPI,
            read_scene=ReadSceneResultFactory.success(),
            update_scene=UpdateSceneResultFactory.success(),
        ) as mock_api:
            # Use mock_api in test
            result = await mock_api.read_scene(...)
    """
    mock_instance = MagicMock(spec=api_class)

    for method_name, return_value in method_returns.items():
        setattr(mock_instance, method_name, AsyncMock(return_value=return_value))

    with patch.object(api_class, "__new__", return_value=mock_instance):
        yield mock_instance


def async_return(value: Any) -> AsyncMock:
    """Create an AsyncMock that returns a specific value.

    Args:
        value: The value to return

    Returns:
        AsyncMock configured to return the value
    """
    return AsyncMock(return_value=value)


def async_raise(exception: Exception) -> AsyncMock:
    """Create an AsyncMock that raises an exception.

    Args:
        exception: The exception to raise

    Returns:
        AsyncMock configured to raise the exception
    """
    return AsyncMock(side_effect=exception)


class AsyncIteratorMock:
    """Mock for async iterators."""

    def __init__(self, items: list):
        """Initialize with items to iterate over."""
        self.items = items
        self.index = 0

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self):
        """Get next item or raise StopAsyncIteration."""
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


def run_async(coro):
    """Run an async coroutine in a test.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine

    Example:
        result = run_async(my_async_function())
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If loop is already running (e.g., in Jupyter), create a new task
        task = asyncio.create_task(coro)
        return asyncio.run(asyncio.gather(task))[0]
    # Normal case - run the coroutine
    return loop.run_until_complete(coro)


class AsyncContextManagerMock:
    """Mock for async context managers."""

    def __init__(self, enter_value=None, exit_value=None):
        """Initialize with values for __aenter__ and __aexit__."""
        self.enter_value = enter_value
        self.exit_value = exit_value

    async def __aenter__(self):
        """Enter the context."""
        return self.enter_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        return self.exit_value
