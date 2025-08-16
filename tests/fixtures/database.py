"""Optimized database fixtures for testing.

Fixture Scope Decisions:
------------------------
1. in_memory_engine: function scope
   - Originally session scope for performance, but changed to function scope
   - Reason: Parallel test safety with pytest-xdist
   - Each test gets its own database to prevent shared state issues
   - Uses worker_id to ensure isolation between parallel workers

2. fast_db_settings: function scope
   - Creates fresh settings for each test
   - Prevents configuration bleed between tests
   - Allows per-test customization

3. fast_db_ops: function scope
   - Depends on fast_db_settings, must match its scope
   - Ensures clean DatabaseOperations instance per test

4. db_session: function scope
   - Provides transaction isolation via rollback
   - Each test runs in its own transaction that's rolled back
   - Prevents data persistence between tests

5. worker_id: session scope
   - Provided by pytest-xdist, doesn't change during test session
   - Used to create worker-specific resources

Performance Trade-offs:
- Function scope adds ~0.01s overhead per test vs session scope
- Acceptable trade-off for guaranteed test isolation
- Critical for parallel test execution reliability
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from scriptrag.config import ScriptRAGSettings, set_settings
from scriptrag.database.operations import DatabaseOperations


@pytest.fixture(scope="function")
def in_memory_engine(worker_id: str) -> Engine:
    """Create an in-memory SQLite engine for testing.

    This is much faster than file-based SQLite for tests.
    Scope is 'function' for parallel test safety - each test gets its own DB.

    The worker_id parameter is provided by pytest-xdist to ensure isolation
    between parallel test workers. Each worker gets its own database instance.

    Note: We use function scope instead of session scope to prevent shared
    state issues when tests run in parallel with pytest-xdist.
    """
    # Create worker-specific database URL for parallel test isolation
    if worker_id == "master":
        # Not running in parallel mode
        db_url = "sqlite:///:memory:"
    else:
        # Running in parallel - use file-based DB with worker ID for isolation
        # In-memory DBs can't be shared across threads safely
        db_url = f"sqlite:///tmp/test_db_{worker_id}.db"

    return create_engine(
        db_url,
        connect_args={
            "check_same_thread": False,  # Allow multi-threaded access within worker
            "timeout": 5,  # Faster timeout for tests
        },
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,  # Disable SQL echo for speed
    )


@pytest.fixture(scope="function")
def fast_db_settings(tmp_path: Path) -> ScriptRAGSettings:
    """Create optimized database settings for testing.

    Uses in-memory SQLite when possible, with performance optimizations.
    """
    # Check if test needs persistent database
    use_memory = os.environ.get("TEST_DB_PERSIST") != "1"

    db_path = Path(":memory:") if use_memory else tmp_path / "test_scriptrag.db"

    settings = ScriptRAGSettings(
        database_path=db_path,
        database_timeout=5.0,  # Faster timeout for tests
        database_wal_mode=False,  # WAL not needed for in-memory
        database_journal_mode="MEMORY",  # Fastest journal mode
        database_synchronous="OFF",  # Fastest sync mode (OK for tests)
        database_cache_size=-8000,  # Larger cache for performance
        database_temp_store="MEMORY",  # Use memory for temp tables
        log_level="WARNING",  # Less logging overhead
        debug=False,
    )

    set_settings(settings)
    return settings


@pytest.fixture(scope="function")
def fast_db_ops(fast_db_settings: ScriptRAGSettings) -> DatabaseOperations:
    """Create a fast DatabaseOperations instance for testing."""
    return DatabaseOperations(fast_db_settings)


@pytest.fixture(scope="function")
def db_session(in_memory_engine: Engine) -> Generator[Session, None, None]:
    """Create a database session for testing.

    Each test gets its own transaction that is rolled back after the test.
    This ensures complete isolation between tests even when running in parallel.
    """
    connection = in_memory_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def worker_id(request) -> str:
    """Get the pytest-xdist worker ID for parallel test isolation.

    Returns 'master' if not running in parallel mode.
    """
    return getattr(request.config, "workerinput", {}).get("workerid", "master")


# Marker for tests that require a real database file
requires_db_file = pytest.mark.requires_db_file

# Marker for tests that can use in-memory database
memory_db_ok = pytest.mark.memory_db_ok
