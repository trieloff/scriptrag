"""Shared test fixtures for ScriptRAG tests."""

import contextlib
import gc
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest

from scriptrag.database import (
    DatabaseConnection,
    GraphDatabase,
    GraphOperations,
    initialize_database,
)
from scriptrag.models import (
    Character,
    Location,
    Scene,
    Script,
)


def _force_close_db_connections(db_path: Path) -> None:
    """Force close any lingering SQLite connections to a database file.

    This is particularly needed on Windows where file handles might not be
    released immediately.
    """
    # Force garbage collection
    gc.collect()

    # Try to connect and close to ensure exclusive access
    with contextlib.suppress(Exception):
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=DELETE")  # Switch from WAL mode
        conn.close()

    # Reduced sleep time for better CI performance
    if hasattr(time, "sleep"):
        time.sleep(0.01)  # Reduced from 0.05s to 0.01s


# Session-scoped database path for shared test database
@pytest.fixture(scope="session")
def session_db_path():
    """Create a session-wide temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize the database schema once for the session
    initialize_database(db_path)

    yield db_path

    # Cleanup with Windows compatibility
    if db_path.exists():
        # Force close any lingering connections
        _force_close_db_connections(db_path)

        # On Windows, SQLite connections might not be fully closed
        # Try multiple times with a small delay
        for attempt in range(5):
            try:
                db_path.unlink()
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.02)  # Reduced from 100ms to 20ms
                    _force_close_db_connections(db_path)
                else:
                    # Last attempt failed, try to at least close WAL files
                    with contextlib.suppress(Exception):
                        wal_path = db_path.with_suffix(".db-wal")
                        shm_path = db_path.with_suffix(".db-shm")
                        if wal_path.exists():
                            wal_path.unlink()
                        if shm_path.exists():
                            shm_path.unlink()
                    import platform

                    if platform.system() == "Windows":
                        import logging

                        logging.warning(
                            f"Could not delete session test database {db_path} on "
                            "Windows - this is expected"
                        )
                    else:
                        raise


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup with Windows compatibility
    if db_path.exists():
        # Force close any lingering connections
        _force_close_db_connections(db_path)

        # On Windows, SQLite connections might not be fully closed
        # Try multiple times with a small delay
        for attempt in range(5):
            try:
                db_path.unlink()
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.02)  # Reduced from 100ms to 20ms
                    _force_close_db_connections(db_path)
                else:
                    # Last attempt failed, try to at least close WAL files
                    with contextlib.suppress(Exception):
                        wal_path = db_path.with_suffix(".db-wal")
                        shm_path = db_path.with_suffix(".db-shm")
                        if wal_path.exists():
                            wal_path.unlink()
                        if shm_path.exists():
                            shm_path.unlink()
                    # Skip cleanup on Windows if file is still locked
                    import platform

                    if platform.system() == "Windows":
                        import logging

                        logging.warning(
                            f"Could not delete test database {db_path} on Windows - "
                            "this is expected"
                        )
                    else:
                        raise


@pytest.fixture
def db_connection(temp_db_path):
    """Create a database connection for testing."""
    # Create the schema first
    initialize_database(temp_db_path)

    # Create connection
    connection = DatabaseConnection(temp_db_path)

    yield connection

    # Ensure connection is properly closed
    with contextlib.suppress(Exception):
        connection.close()

    # Force close any other connections that might have been created
    _force_close_db_connections(temp_db_path)


@pytest.fixture
def graph_db(db_connection):
    """Create a graph database instance for testing."""
    return GraphDatabase(db_connection)


@pytest.fixture
def graph_ops(db_connection):
    """Create graph operations instance for testing."""
    return GraphOperations(db_connection)


@pytest.fixture
def sample_script():
    """Create a sample script for testing."""
    return Script(
        title="Test Screenplay",
        author="Test Author",
        format="screenplay",
        genre="Drama",
        description="A test screenplay for unit testing",
        is_series=False,
    )


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    return Character(
        name="PROTAGONIST",
        description="The main character of our test story",
        aliases=["HERO", "MAIN_CHAR"],
    )


@pytest.fixture
def sample_location():
    """Create a sample location for testing."""
    return Location(
        interior=True,
        name="COFFEE SHOP",
        time="DAY",
        raw_text="INT. COFFEE SHOP - DAY",
    )


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return Scene(
        script_id=uuid4(),
        heading="INT. COFFEE SHOP - DAY",
        description="Our protagonist enters a busy coffee shop",
        script_order=1,
        temporal_order=1,
        estimated_duration_minutes=2.5,
    )


# CI-specific test configuration
def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip integration tests in CI environment."""
    if not os.environ.get("CI"):
        return

    skip_integration = pytest.mark.skip(
        reason="Skipping integration tests in CI due to hanging issues"
    )
    skip_llm = pytest.mark.skip(
        reason="Skipping LLM tests in CI - no LLM endpoint available"
    )

    for item in items:
        # Skip all integration tests in CI
        if "integration" in item.nodeid or "integration" in str(item.fspath):
            item.add_marker(skip_integration)

        # Skip LLM-dependent tests
        if "llm" in item.nodeid.lower() or "embedding" in item.nodeid.lower():
            item.add_marker(skip_llm)

        # Skip e2e tests
        if "e2e" in item.nodeid:
            item.add_marker(skip_integration)

        # Add aggressive timeout to all tests
        if not any(mark.name == "timeout" for mark in item.iter_markers()):
            item.add_marker(pytest.mark.timeout(30))  # 30 second timeout per test
