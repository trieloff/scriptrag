"""Pytest configuration and fixtures."""

import os
from pathlib import Path

import pytest

from scriptrag.config import ScriptRAGSettings, set_settings

# Import CLI fixtures to make them available globally
from tests.cli_fixtures import clean_runner, cli_helper, cli_invoke  # noqa: F401

# Import LLM test fixtures to make them available globally
from tests.llm_test_utils import (  # noqa: F401
    mock_completion_response,
    mock_embedding_response,
    mock_llm_client,
    mock_llm_provider,
    mock_llm_provider_with_delay,
    mock_llm_provider_with_failures,
    mock_llm_provider_with_rate_limit,
    patch_llm_client,
)

# Import mock file detection plugin if available
try:
    from tests.conftest_mock_detection import (
        _mock_file_detector,  # noqa: F401
    )
    from tests.conftest_mock_detection import (
        pytest_addoption as mock_detection_addoption,
    )
    from tests.conftest_mock_detection import (
        pytest_configure as mock_detection_configure,
    )
    from tests.conftest_mock_detection import (
        pytest_sessionstart as mock_detection_sessionstart,
    )
    from tests.conftest_mock_detection import (
        pytest_terminal_summary as mock_detection_terminal_summary,
    )

    MOCK_DETECTION_AVAILABLE = True
except ImportError:
    MOCK_DETECTION_AVAILABLE = False


def pytest_addoption(parser):
    """Add command-line options for pytest."""
    if MOCK_DETECTION_AVAILABLE:
        mock_detection_addoption(parser)


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
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (may need extended timeout)",
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test",
    )
    config.addinivalue_line(
        "markers",
        "timeout(seconds): override timeout for specific test",
    )

    # Configure mock detection if available
    if MOCK_DETECTION_AVAILABLE:
        mock_detection_configure(config)


def pytest_sessionstart(session):
    """Called at the start of the test session."""
    if MOCK_DETECTION_AVAILABLE:
        mock_detection_sessionstart(session)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print summary at the end of test session."""
    if MOCK_DETECTION_AVAILABLE:
        mock_detection_terminal_summary(terminalreporter, exitstatus, config)


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


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """Ensure singletons are cleaned up between tests to prevent contamination."""
    yield

    # Clean up connection manager after each test to prevent cross-test contamination
    try:
        from scriptrag.database.connection_manager import close_connection_manager

        close_connection_manager()
    except Exception:
        # Ignore cleanup errors - they shouldn't fail tests
        pass

    # Clean up settings cache after each test
    try:
        import scriptrag.config.settings as settings_module

        settings_module._settings = None
    except Exception:
        # Ignore cleanup errors - they shouldn't fail tests
        pass


@pytest.fixture(autouse=True)
def isolated_test_environment(request, tmp_path, monkeypatch):
    """Ensure unit tests run with isolated database and settings.

    This fixture runs automatically for unit tests to prevent:
    1. Database creation at repo root
    2. Fixture file contamination
    3. Cross-test interference

    Integration tests are excluded to allow testing of real application behavior.
    """
    # Only apply isolation to unit tests, not integration tests
    test_path = str(request.fspath)
    # Use os.sep for cross-platform compatibility
    if f"{os.sep}integration{os.sep}" in test_path or "/integration/" in test_path:
        # Skip isolation for integration tests - they should test real behavior
        yield
        return

    # Set isolated database path for unit tests
    db_path = tmp_path / "test_scriptrag.db"
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

    # Create isolated settings
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    yield

    # Settings cleanup happens automatically


@pytest.fixture(autouse=True)
def verify_fixtures_clean():
    """Verify that fixture files are clean before and after each test."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "fountain" / "test_data"

    if not fixtures_dir.exists():
        yield
        return

    # Files that are expected to have metadata
    expected_with_metadata = {
        "coffee_shop_with_metadata.fountain",
        "script_with_metadata.fountain",
        "props_test_script.fountain",
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
