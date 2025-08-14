"""Pytest configuration for utils tests."""

import platform

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip certain tests on Windows due to async/mock hanging issues."""
    if platform.system() == "Windows":
        skip_windows = pytest.mark.skip(
            reason="Skipped on Windows due to async/mock hanging issues"
        )
        for item in items:
            # Skip all async tests in test_llm_client.py on Windows
            if "test_llm_client.py" in str(item.fspath) and "async" in item.name:
                item.add_marker(skip_windows)
