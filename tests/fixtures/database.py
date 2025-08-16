"""Optimized database fixtures for testing."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from scriptrag.config import ScriptRAGSettings, set_settings
from scriptrag.database.operations import DatabaseOperations


@pytest.fixture(scope="session")
def in_memory_engine() -> Engine:
    """Create an in-memory SQLite engine for testing.

    This is much faster than file-based SQLite for tests.
    Scope is 'session' to reuse across tests where possible.
    """
    # Use in-memory database with shared cache for better performance
    return create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,  # Allow multi-threaded access
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
    """
    connection = in_memory_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Marker for tests that require a real database file
requires_db_file = pytest.mark.requires_db_file

# Marker for tests that can use in-memory database
memory_db_ok = pytest.mark.memory_db_ok
