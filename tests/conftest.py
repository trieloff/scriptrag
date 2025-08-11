"""Pytest configuration and fixtures."""

import os

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "requires_llm: mark test as requiring LLM providers (may be skipped)",
    )


def pytest_collection_modifyitems(config, items):
    """Modify collected test items to add skip markers for LLM tests in CI."""
    # If running in CI with known rate limit issues, skip LLM tests by default
    # unless explicitly enabled via SCRIPTRAG_TEST_LLMS environment variable
    if (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")) and not os.getenv(
        "SCRIPTRAG_TEST_LLMS"
    ):
        skip_llm = pytest.mark.skip(
            reason=(
                "Skipping LLM tests in CI due to rate limits - "
                "set SCRIPTRAG_TEST_LLMS=1 to enable"
            )
        )
        for item in items:
            if "requires_llm" in item.keywords:
                item.add_marker(skip_llm)
