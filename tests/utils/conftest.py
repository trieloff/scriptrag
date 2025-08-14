"""Pytest configuration for utils tests."""

import os
import platform

import pytest


def pytest_ignore_collect(collection_path, path, config):
    """Skip entire test files on Windows CI to avoid hanging issues."""
    # Skip test_llm_client.py entirely on Windows CI
    return (
        platform.system() == "Windows"
        and os.getenv("CI")
        and "test_llm_client.py" in str(collection_path)
    )


def pytest_collection_modifyitems(config, items):
    """Skip certain tests on Windows due to async/mock hanging issues."""
    if platform.system() == "Windows":
        skip_windows = pytest.mark.skip(
            reason="Skipped on Windows due to async/mock hanging issues"
        )
        for item in items:
            # Skip all async tests in test_llm_client.py on Windows
            if "test_llm_client.py" in str(item.fspath):
                item.add_marker(skip_windows)
