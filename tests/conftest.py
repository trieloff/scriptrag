"""Shared test fixtures for ScriptRAG tests."""

import contextlib
import gc
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

    # Give Windows time to release file handles
    if hasattr(time, "sleep"):
        time.sleep(0.05)


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
                    time.sleep(0.1)  # Wait 100ms before retrying
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
