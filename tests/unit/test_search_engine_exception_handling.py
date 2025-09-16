"""Tests for search engine exception handling bug fix.

This test module specifically tests the fix for the bug where
exception checking used truthiness instead of None comparison.
"""

import asyncio
import sqlite3
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery


class FalsyException(Exception):  # noqa: N818
    """Custom exception that evaluates to False in boolean context."""

    def __bool__(self):
        return False

    def __str__(self):
        return "FalsyException: This exception evaluates to False"


class TestSearchEngineExceptionHandling:
    """Test SearchEngine exception handling with edge cases."""

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
        settings.search_thread_timeout = 1.0  # Short timeout for testing
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

    def test_falsy_exception_handling_with_event_loop(self, mock_settings, mock_db):
        """Test that falsy exceptions are properly caught and re-raised.

        This test specifically addresses the bug where 'if exception:' was used
        instead of 'if exception is not None:', which would fail to detect
        exceptions that evaluate to False.
        """
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Patch search_async to raise a FalsyException
        async def mock_search_async_falsy(q):
            raise FalsyException()

        # We need to simulate being in an async context
        with patch("asyncio.get_running_loop") as mock_get_loop:
            # Simulate a running loop
            mock_get_loop.return_value = Mock(spec_set=asyncio.AbstractEventLoop)

            with patch.object(engine, "search_async", mock_search_async_falsy):
                # The exception should be properly caught and re-raised
                with pytest.raises(FalsyException) as exc_info:
                    engine.search(query)

                assert (
                    str(exc_info.value)
                    == "FalsyException: This exception evaluates to False"
                )

    def test_normal_exception_handling_with_event_loop(self, mock_settings, mock_db):
        """Test that normal exceptions are still properly handled."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Patch search_async to raise a normal exception
        async def mock_search_async_normal(q):
            raise ValueError("Normal exception")

        with patch("asyncio.get_running_loop") as mock_get_loop:
            # Simulate a running loop
            mock_get_loop.return_value = Mock(spec_set=asyncio.AbstractEventLoop)

            with patch.object(engine, "search_async", mock_search_async_normal):
                with pytest.raises(ValueError) as exc_info:
                    engine.search(query)

                assert str(exc_info.value) == "Normal exception"

    def test_exception_with_no_running_loop(self, mock_settings, mock_db):
        """Test exception handling when no event loop is running."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test",
            text_query="test",
            mode=SearchMode.AUTO,
            offset=0,
            limit=10,
        )

        # Patch search_async to raise FalsyException
        async def mock_search_async_falsy(q):
            raise FalsyException()

        # Ensure no event loop is running (default case)
        with patch.object(engine, "search_async", mock_search_async_falsy):
            with pytest.raises(FalsyException) as exc_info:
                engine.search(query)

            assert (
                str(exc_info.value)
                == "FalsyException: This exception evaluates to False"
            )
