"""Tests for ScriptRAG search functionality."""

import tempfile
from pathlib import Path

import pytest

from scriptrag.exceptions import DatabaseError
from scriptrag.main import ScriptRAG
from scriptrag.search.models import SearchMode


@pytest.fixture
def sample_fountain_content():
    """Sample Fountain screenplay content."""
    return """Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - DAY

The coffee shop is bustling with morning customers.

ALICE
(nervously)
I need to tell you something important.

BOB
What is it?

ALICE
I've been offered a job in London.

EXT. PARK - DAY

Alice and Bob walk through the park.

BOB
(shocked)
London? That's so far away!

ALICE
I know, but it's an amazing opportunity.

FADE OUT.
"""


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


@pytest.fixture
def indexed_scriptrag(scriptrag_instance, sample_fountain_content):
    """Create a ScriptRAG instance with indexed content."""
    # Create and index a script
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".fountain", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(sample_fountain_content)
        file_path = Path(tmp.name)

    try:
        scriptrag_instance.index_script(file_path)
    finally:
        if file_path.exists():
            file_path.unlink()

    return scriptrag_instance


class TestSearch:
    """Test search functionality."""

    def test_search_without_database(self, temp_db_path):
        """Test error when searching without initialized database."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=False)

        with pytest.raises(DatabaseError) as exc_info:
            scriptrag.search("test query")

        assert "Database not initialized" in str(exc_info.value)

    def test_search_basic(self, indexed_scriptrag):
        """Test basic search functionality."""
        results = indexed_scriptrag.search("coffee")

        assert results is not None
        assert results.query == "coffee"
        assert results.total_results > 0
        assert len(results.results) > 0

    def test_search_with_mode(self, indexed_scriptrag):
        """Test search with different modes."""
        # Scene search
        results = indexed_scriptrag.search("park", mode=SearchMode.SCENE)
        assert results.total_results > 0

        # Character search
        results = indexed_scriptrag.search("Alice", mode=SearchMode.CHARACTER)
        assert results.total_results > 0

        # Dialogue search
        results = indexed_scriptrag.search("London", mode=SearchMode.DIALOGUE)
        assert results.total_results > 0

    def test_search_with_filters(self, indexed_scriptrag):
        """Test search with filters."""
        results = indexed_scriptrag.search("coffee", filters={"scene_type": "INT"})

        assert results.total_results > 0

    def test_search_with_limit(self, indexed_scriptrag):
        """Test search with result limit."""
        results = indexed_scriptrag.search("test", limit=1)

        assert len(results.results) <= 1

    def test_search_with_offset(self, indexed_scriptrag):
        """Test search with offset for pagination."""
        # Get first page
        results1 = indexed_scriptrag.search("test", limit=1, offset=0)

        # Get second page
        results2 = indexed_scriptrag.search("test", limit=1, offset=1)

        # Results should be different if there are multiple matches
        if results1.total_results > 1:
            assert results1.results != results2.results

    def test_search_empty_query(self, indexed_scriptrag):
        """Test search with empty query."""
        results = indexed_scriptrag.search("")

        # Should return all results or handle gracefully
        assert results is not None

    def test_search_no_results(self, indexed_scriptrag):
        """Test search with query that has no matches."""
        results = indexed_scriptrag.search("nonexistentterm123456")

        assert results.total_results == 0
        assert len(results.results) == 0

    def test_search_special_characters(self, indexed_scriptrag):
        """Test search with special characters in query."""
        # Test with quotes, parentheses, etc.
        results = indexed_scriptrag.search('"coffee shop"')
        assert results is not None

        results = indexed_scriptrag.search("(nervously)")
        assert results is not None
