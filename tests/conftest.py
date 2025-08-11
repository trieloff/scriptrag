"""Pytest configuration and fixtures."""

import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "requires_llm: mark test as requiring LLM providers (may be skipped)",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test",
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


# Note: protect_fixture_files fixture was removed as it was interfering with
# temporary test files. The verify_fixtures_clean fixture provides sufficient
# protection by detecting any contamination of the actual fixture files.


@pytest.fixture(autouse=True)
def verify_fixtures_clean():
    """Verify that fixture files are clean before and after each test."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "fountain" / "test_data"

    if not fixtures_dir.exists():
        yield
        return

    # Files that are expected to have metadata
    # Some fixture scripts intentionally include boneyard metadata blocks to
    # validate parsing and update behavior. Only consider metadata in files
    # outside this allowlist as contamination introduced by tests.
    expected_with_metadata = {
        "coffee_shop_with_metadata.fountain",
        "script_with_metadata.fountain",
        "props_test_script.fountain",
        # The following fixtures ship with metadata by design
        "props_context_multi_scene.fountain",
        "nested_script.fountain",
        "coffee_shop.fountain",
        "parser_test.fountain",
        "simple_script.fountain",
    }

    def check_fixtures():
        """Check that fixture files don't have unexpected metadata."""
        contaminated_files = []
        for fountain_file in fixtures_dir.glob("*.fountain"):
            if fountain_file.name in expected_with_metadata:
                continue

            try:
                content = fountain_file.read_text(encoding="utf-8")
                if "SCRIPTRAG-META-START" in content:
                    contaminated_files.append(fountain_file.name)
            except (OSError, PermissionError):
                # Can't read file, skip
                pass

        if contaminated_files:
            files_list = ", ".join(contaminated_files)
            pytest.fail(
                f"Fixture files are contaminated with metadata: {files_list}. "
                f"Tests should NEVER modify fixture files directly! "
                f"Always copy fixture files to a temp directory before modifying them."
            )

    # Check before test
    check_fixtures()

    yield

    # Check after test
    check_fixtures()
