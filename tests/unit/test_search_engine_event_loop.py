"""Tests for search engine event loop handling."""

import asyncio
import sqlite3
from unittest.mock import MagicMock

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery


class TestSearchEngineEventLoop:
    """Test SearchEngine event loop handling."""

    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_timeout = 30.0
        settings.database_cache_size = 2000
        settings.database_temp_store = "MEMORY"
        # Add semantic search settings
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        # Add search thread timeout setting
        settings.search_thread_timeout = 300.0
        return settings

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create a mock database file."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema
        conn.execute("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)

        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                metadata TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id),
                FOREIGN KEY (character_id) REFERENCES characters(id)
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id)
            )
        """)

        # Bible tables
        conn.execute("""
            CREATE TABLE script_bibles (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                title TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)

        conn.execute("""
            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY,
                bible_id INTEGER,
                chunk_number INTEGER,
                heading TEXT,
                level INTEGER,
                content TEXT,
                FOREIGN KEY (bible_id) REFERENCES script_bibles(id)
            )
        """)

        # Insert test data
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (1, "Test Script", "Test Author", '{"season": 1, "episode": 1}'),
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 1, 1, "INT. OFFICE - DAY", "OFFICE", "DAY", "Office scene content"),
        )

        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def search_engine(self, mock_settings, mock_db):
        """Create a SearchEngine instance."""
        mock_settings.database_path = mock_db
        return SearchEngine(mock_settings)

    def test_search_without_existing_event_loop(self, search_engine):
        """Test search method when no event loop is running."""
        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Ensure no event loop is running
        try:
            asyncio.get_running_loop()
            pytest.skip("Event loop is already running")
        except RuntimeError:
            pass  # Good, no loop is running

        # Should work without issues
        response = search_engine.search(query)
        assert response is not None
        assert response.query == query
        assert isinstance(response.results, list)

    @pytest.mark.asyncio
    async def test_search_with_existing_event_loop(self, search_engine):
        """Test search method when an event loop is already running."""
        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # We're in an async test, so an event loop is running
        loop = asyncio.get_running_loop()
        assert loop is not None

        # The search method should handle this case properly
        # by using ThreadPoolExecutor to run async code
        response = search_engine.search(query)
        assert response is not None
        assert response.query == query
        assert isinstance(response.results, list)

    @pytest.mark.asyncio
    async def test_concurrent_searches_with_event_loop(self, search_engine):
        """Test multiple concurrent searches when event loop is running."""
        queries = [
            SearchQuery(
                raw_query=f"test{i}",
                text_query=f"test{i}",
                mode=SearchMode.AUTO,
                offset=0,
                limit=10,
            )
            for i in range(3)
        ]

        # Run multiple searches concurrently in async context
        tasks = []
        loop = asyncio.get_running_loop()

        for query in queries:
            # Each search should work despite being called from async context
            task = loop.run_in_executor(None, search_engine.search, query)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert response is not None
            assert response.query == queries[i]
            assert isinstance(response.results, list)

    def test_search_handles_exception_without_loop(self, mock_settings):
        """Test that exceptions are properly propagated when no loop exists."""
        # Create engine with non-existent database
        nonexistent = mock_settings.database_path / "nonexistent" / "test.db"
        mock_settings.database_path = nonexistent
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Should raise an exception about database not found
        with pytest.raises(DatabaseError) as exc_info:
            engine.search(query)

        # Verify the exception is about the database
        err_msg = str(exc_info.value)
        assert "Database not found" in err_msg or "not found" in err_msg.lower()

    @pytest.mark.asyncio
    async def test_search_handles_exception_with_loop(self, mock_settings):
        """Test that exceptions are properly propagated when loop exists."""
        # Create engine with non-existent database
        nonexistent = mock_settings.database_path / "nonexistent" / "test.db"
        mock_settings.database_path = nonexistent
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # We're in async context
        loop = asyncio.get_running_loop()
        assert loop is not None

        # Should raise an exception about database not found
        with pytest.raises(DatabaseError) as exc_info:
            engine.search(query)

        # Verify the exception is about the database
        err_msg = str(exc_info.value)
        assert "Database not found" in err_msg or "not found" in err_msg.lower()

    @pytest.mark.asyncio
    async def test_search_async_method_directly(self, search_engine):
        """Test calling search_async directly in async context."""
        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Direct async call should work
        response = await search_engine.search_async(query)
        assert response is not None
        assert response.query == query
        assert isinstance(response.results, list)
