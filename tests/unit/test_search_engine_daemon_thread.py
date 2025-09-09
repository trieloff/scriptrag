"""Tests for search engine daemon thread bug fix.

This test module specifically tests the fix for the bug where
the search thread was not marked as daemon, causing resource leaks
and potentially hanging the program on exit.
"""

import asyncio
import sqlite3
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery, SearchResponse


class TestSearchEngineDaemonThread:
    """Test SearchEngine daemon thread handling."""

    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_timeout = 30.0
        settings.database_cache_size = 2000
        settings.database_temp_store = "MEMORY"
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        settings.search_thread_timeout = 0.1  # Very short timeout for testing
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
                action TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT,
                aliases TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY,
                content TEXT,
                chunk_type TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX idx_scenes_script_id ON scenes(script_id)
        """)
        conn.execute("""
            CREATE INDEX idx_scenes_scene_number ON scenes(scene_number)
        """)
        conn.commit()
        conn.close()
        return db_path

    def test_daemon_thread_property(self, mock_settings, mock_db):
        """Test that the thread is created as daemon.

        This ensures the thread won't prevent program exit on timeout.
        """
        mock_settings.database_path = mock_db
        mock_settings.search_thread_timeout = 5.0  # Normal timeout
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Track the thread that gets created
        created_thread = None
        original_thread_class = threading.Thread

        class TrackedThread(threading.Thread):
            def __init__(self, *args, **kwargs):
                nonlocal created_thread
                super().__init__(*args, **kwargs)
                created_thread = self

        # Create a normal async function that completes quickly
        async def normal_search_async(q):
            return SearchResponse(query=q, results=[], total_count=0)

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_get_loop.return_value = Mock()  # Simulate a running loop

            with patch("threading.Thread", TrackedThread):
                with patch.object(engine, "search_async", normal_search_async):
                    result = engine.search(query)

                    # Verify result
                    assert isinstance(result, SearchResponse)

                    # Verify the thread was created as a daemon thread
                    assert created_thread is not None
                    assert created_thread.daemon is True

    def test_thread_cleanup_on_success(self, mock_settings, mock_db):
        """Test that the thread completes and cleans up properly on success."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Create a fast async function that completes quickly
        async def fast_search_async(q):
            return SearchResponse(query=q, results=[], total_count=0)

        # Track thread lifecycle
        thread_states = {
            "created": False,
            "started": False,
            "joined": False,
            "is_daemon": False,
        }

        original_thread_init = threading.Thread.__init__
        original_thread_start = threading.Thread.start
        original_thread_join = threading.Thread.join

        def track_thread_init(self, *args, **kwargs):
            result = original_thread_init(self, *args, **kwargs)
            thread_states["created"] = True
            thread_states["is_daemon"] = self.daemon
            return result

        def track_thread_start(self):
            thread_states["started"] = True
            return original_thread_start(self)

        def track_thread_join(self, timeout=None):
            result = original_thread_join(self, timeout)
            thread_states["joined"] = True
            return result

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_get_loop.return_value = Mock()  # Simulate a running loop

            with patch.object(threading.Thread, "__init__", track_thread_init):
                with patch.object(threading.Thread, "start", track_thread_start):
                    with patch.object(threading.Thread, "join", track_thread_join):
                        with patch.object(engine, "search_async", fast_search_async):
                            result = engine.search(query)

                            # Verify result
                            assert isinstance(result, SearchResponse)
                            assert result.total_count == 0

                            # Verify thread lifecycle
                            assert thread_states["created"] is True
                            assert thread_states["started"] is True
                            assert thread_states["joined"] is True
                            assert thread_states["is_daemon"] is True

    def test_thread_exception_propagation(self, mock_settings, mock_db):
        """Test that exceptions from the thread are properly propagated."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Create an async function that raises an exception
        async def failing_search_async(q):
            raise ValueError("Test exception from async search")

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_get_loop.return_value = Mock()  # Simulate a running loop

            with patch.object(engine, "search_async", failing_search_async):
                # Exception should be propagated
                exc_msg = "Test exception from async search"
                with pytest.raises(ValueError, match=exc_msg):
                    engine.search(query)

    def test_no_daemon_thread_without_event_loop(self, mock_settings, mock_db):
        """Test that no thread is created when there's no running event loop."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Create a normal async function
        async def normal_search_async(q):
            return SearchResponse(query=q, results=[], total_count=0)

        # Track if a thread is created
        thread_created = False
        original_thread_init = threading.Thread.__init__

        def track_thread_init(self, *args, **kwargs):
            nonlocal thread_created
            thread_created = True
            return original_thread_init(self, *args, **kwargs)

        # Don't simulate a running loop (asyncio.get_running_loop will raise)
        err = RuntimeError("No running loop")
        with patch("asyncio.get_running_loop", side_effect=err):
            with patch.object(threading.Thread, "__init__", track_thread_init):
                with patch.object(engine, "search_async", normal_search_async):
                    result = engine.search(query)

                    # Verify result
                    assert isinstance(result, SearchResponse)

                    # Verify no thread was created (direct event loop used)
                    assert thread_created is False

    def test_concurrent_searches_with_daemon_threads(self, mock_settings, mock_db):
        """Test that multiple concurrent searches use daemon threads correctly."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

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

        # Track all created threads
        created_threads = []
        original_thread_init = threading.Thread.__init__

        def track_thread_init(self, *args, **kwargs):
            result = original_thread_init(self, *args, **kwargs)
            created_threads.append(self)
            return result

        async def normal_search_async(q):
            await asyncio.sleep(0.01)  # Small delay
            return SearchResponse(query=q, results=[], total_count=0)

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_get_loop.return_value = Mock()  # Simulate a running loop

            with patch.object(threading.Thread, "__init__", track_thread_init):
                with patch.object(engine, "search_async", normal_search_async):
                    # Run multiple searches
                    for query in queries:
                        result = engine.search(query)
                        assert isinstance(result, SearchResponse)

                    # Verify all threads were daemon threads
                    assert len(created_threads) == 3
                    for thread in created_threads:
                        assert thread.daemon is True
