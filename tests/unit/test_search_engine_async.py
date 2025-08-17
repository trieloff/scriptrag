"""Tests for async search engine functionality."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery, SearchResponse


class TestSearchEngineAsync:
    """Test async SearchEngine methods."""

    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_timeout = 30.0
        settings.database_cache_size = 2000
        settings.database_temp_store = "MEMORY"
        settings.search_vector_threshold = 10
        settings.llm_embedding_model = "text-embedding-ada-002"
        settings.llm_embedding_dimensions = 1536
        settings.search_vector_similarity_threshold = 0.3
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        return settings

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create a mock database with test data."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create schema
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
                content TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY,
                entity_type TEXT,
                entity_id INTEGER,
                embedding_model TEXT,
                embedding BLOB
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
            (1, 1, 1, "INT. OFFICE - DAY", "OFFICE", "DAY", "A tense conversation."),
        )

        conn.commit()
        conn.close()
        return db_path

    @pytest.mark.asyncio
    async def test_async_search(self, mock_settings, mock_db):
        """Test async search method."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="tense", text_query="tense")
        response = await engine.search_async(query)

        assert isinstance(response, SearchResponse)
        assert response.total_count >= 0
        assert "sql" in response.search_methods

    @pytest.mark.asyncio
    async def test_async_search_with_vector(self, mock_settings, mock_db):
        """Test async search with vector search enabled."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        # Create a query that triggers vector search
        query = SearchQuery(
            raw_query="find scenes with emotional depth and character development",
            text_query="find scenes with emotional depth and character development",
            mode=SearchMode.FUZZY,
        )

        # Mock vector engine
        with patch.object(
            engine.vector_engine, "enhance_results_with_vector_search"
        ) as mock_enhance:
            mock_enhance.return_value = []

            response = await engine.search_async(query)

            assert isinstance(response, SearchResponse)
            assert "sql" in response.search_methods
            assert "semantic" in response.search_methods
            mock_enhance.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_search_vector_error_handling(self, mock_settings, mock_db):
        """Test that vector search errors are handled gracefully."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="test query with many words to trigger vector search",
            text_query="test query with many words to trigger vector search",
            mode=SearchMode.FUZZY,
        )

        # Mock vector engine to raise error
        with patch.object(
            engine.vector_engine, "enhance_results_with_vector_search"
        ) as mock_enhance:
            mock_enhance.side_effect = Exception("Vector search failed")

            response = await engine.search_async(query)

            # Should still return results from SQL search
            assert isinstance(response, SearchResponse)
            assert "sql" in response.search_methods
            assert "semantic" in response.search_methods

    def test_search_sync_wrapper(self, mock_settings, mock_db):
        """Test synchronous wrapper for search."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", text_query="test")

        # The sync wrapper should work
        response = engine.search(query)

        assert isinstance(response, SearchResponse)
        assert response.total_count >= 0
        assert "sql" in response.search_methods

    @pytest.mark.asyncio
    async def test_vector_search_integration(self, mock_settings, mock_db):
        """Test full vector search integration."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        # Mock the LLM client for embeddings
        mock_llm_client = AsyncMock()
        embedding_response = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.1] * 1536  # Mock embedding
        embedding_response.data = [embedding_data]
        mock_llm_client.embed = AsyncMock(return_value=embedding_response)

        with patch.object(engine.vector_engine, "llm_client", mock_llm_client):
            query = SearchQuery(
                raw_query="Find dramatic scenes with conflict",
                text_query="Find dramatic scenes with conflict",
                mode=SearchMode.FUZZY,
            )

            response = await engine.search_async(query)

            assert isinstance(response, SearchResponse)
            assert "semantic" in response.search_methods

    @pytest.mark.asyncio
    async def test_search_performance(self, mock_settings, mock_db):
        """Test that execution time is tracked correctly."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", text_query="test")
        response = await engine.search_async(query)

        assert response.execution_time_ms is not None
        assert response.execution_time_ms >= 0  # Allow 0 for very fast operations
        assert response.execution_time_ms < 5000  # Should be reasonably fast
