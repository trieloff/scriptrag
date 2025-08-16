"""Tests for ScriptRAG initialization."""

import tempfile
from pathlib import Path

import pytest

from scriptrag.main import ScriptRAG


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def scriptrag_instance(temp_db_path):
    """Create a ScriptRAG instance with a temporary database."""
    import gc
    import platform

    from scriptrag.config import ScriptRAGSettings

    settings = ScriptRAGSettings(database_path=temp_db_path)
    instance = ScriptRAG(settings=settings, auto_init_db=True)

    yield instance

    # Ensure proper cleanup on Windows to prevent file locking issues
    if platform.system() == "Windows":
        # Force cleanup of all database-related components
        if hasattr(instance, "db_ops"):
            del instance.db_ops
        if hasattr(instance, "index_command"):
            del instance.index_command
        if hasattr(instance, "search_engine"):
            del instance.search_engine

        # Force garbage collection to close database connections
        del instance
        gc.collect()
        # Small delay to ensure Windows releases file handles
        import time

        time.sleep(0.1)


class TestScriptRAGInit:
    """Test ScriptRAG initialization."""

    def test_init_with_default_settings(self):
        """Test initialization with default settings."""
        scriptrag = ScriptRAG(auto_init_db=False)
        assert scriptrag.settings is not None
        assert scriptrag.parser is not None
        assert scriptrag.db_ops is not None
        assert scriptrag.index_command is not None
        assert scriptrag.search_engine is not None

    def test_init_with_custom_settings(self, temp_db_path):
        """Test initialization with custom settings."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=False)
        assert scriptrag.settings == settings
        # Resolve paths for platform-specific symlinks (macOS /var -> /private/var)
        assert scriptrag.settings.database_path.resolve() == temp_db_path.resolve()

    def test_auto_init_db(self, temp_db_path):
        """Test automatic database initialization."""
        from scriptrag.config import ScriptRAGSettings

        # Ensure the temp database doesn't exist yet
        if temp_db_path.exists():
            temp_db_path.unlink()

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        # Database should be initialized
        assert temp_db_path.exists()
        assert scriptrag.db_ops.check_database_exists()

    def test_no_auto_init_db(self, temp_db_path):
        """Test without automatic database initialization."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=False)

        # Database should not be automatically initialized
        assert not scriptrag.db_ops.check_database_exists()
