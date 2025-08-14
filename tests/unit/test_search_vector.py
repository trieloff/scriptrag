"""Tests for vector search functionality."""

import sqlite3
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.models import SearchQuery, SearchResult
from scriptrag.search.vector import VectorSearchEngine


class TestVectorSearchEngine:
    """Test VectorSearchEngine class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.llm_embedding_model = "text-embedding-ada-002"
        settings.llm_embedding_dimensions = 1536
        settings.search_vector_similarity_threshold = 0.3
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        return settings

    @pytest.fixture
    def vector_engine(self, mock_settings):
        """Create a VectorSearchEngine instance."""
        return VectorSearchEngine(mock_settings)

    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding vector."""
        np.random.seed(42)
        return np.random.randn(1536).astype(np.float32)

    @pytest.fixture
    def mock_llm_client(self, sample_embedding):
        """Create a mock LLM client."""
        client = AsyncMock()

        # Mock embedding response
        embedding_response = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = sample_embedding.tolist()
        embedding_response.data = [embedding_data]

        client.embed = AsyncMock(return_value=embedding_response)
        return client

    @pytest.mark.asyncio
    async def test_initialize(self, vector_engine):
        """Test initialization of vector search engine."""
        with patch("scriptrag.search.vector.get_default_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await vector_engine.initialize()

            assert vector_engine.llm_client == mock_client
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup(self, vector_engine):
        """Test cleanup of resources."""
        vector_engine.llm_client = MagicMock()
        vector_engine._query_embeddings_cache = {"test": np.array([1, 2, 3])}

        await vector_engine.cleanup()

        assert vector_engine.llm_client is None
        assert len(vector_engine._query_embeddings_cache) == 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_settings):
        """Test async context manager for resource management."""
        with patch("scriptrag.search.vector.get_default_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            async with VectorSearchEngine(mock_settings) as engine:
                assert engine.llm_client == mock_client
                mock_get_client.assert_called_once()

            # After exiting context, client should be cleaned up
            assert engine.llm_client is None

    @pytest.mark.asyncio
    async def test_generate_query_embedding(
        self, vector_engine, mock_llm_client, sample_embedding
    ):
        """Test generating embeddings for a query."""
        vector_engine.llm_client = mock_llm_client
        query_text = "Find scenes with dramatic tension"

        result = await vector_engine.generate_query_embedding(query_text)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert np.array_equal(result, sample_embedding)

        # Check caching
        assert query_text in vector_engine._query_embeddings_cache
        cached_result = await vector_engine.generate_query_embedding(query_text)
        assert np.array_equal(cached_result, result)

        # Should only call embed once due to caching
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_query_embedding_error(self, vector_engine):
        """Test error handling in embedding generation."""
        vector_engine.llm_client = AsyncMock()
        vector_engine.llm_client.embed = AsyncMock(side_effect=Exception("API error"))

        with pytest.raises(RuntimeError, match="Failed to generate query embedding"):
            await vector_engine.generate_query_embedding("test query")

    def test_cosine_similarity(self, vector_engine):
        """Test cosine similarity calculation."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([0, 1, 0])
        vec3 = np.array([1, 0, 0])
        vec4 = np.array([0.5, 0.5, 0])

        # Orthogonal vectors
        assert vector_engine.cosine_similarity(vec1, vec2) == 0.0

        # Identical vectors
        assert vector_engine.cosine_similarity(vec1, vec3) == 1.0

        # Partially similar vectors
        similarity = vector_engine.cosine_similarity(vec1, vec4)
        assert 0.7 < similarity < 0.8  # Should be around 0.707

        # Zero vector
        zero_vec = np.array([0, 0, 0])
        assert vector_engine.cosine_similarity(vec1, zero_vec) == 0.0

    def test_decode_embedding_blob(self, vector_engine):
        """Test decoding binary embedding data."""
        # Create a sample embedding
        original = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        # Convert to binary blob
        blob = struct.pack(f"{len(original)}f", *original)

        # Decode and verify
        decoded = vector_engine.decode_embedding_blob(blob)
        assert np.allclose(decoded, original)
        assert decoded.dtype == np.float32

    @pytest.mark.asyncio
    async def test_search_similar_scenes(self, vector_engine, tmp_path):
        """Test searching for similar scenes."""
        # Create test database with embeddings
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Create schema
        conn.execute("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT,
                version INTEGER DEFAULT 1,
                is_current BOOLEAN DEFAULT TRUE
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
            "INSERT INTO scripts (id, title, author) "
            "VALUES (1, 'Test Script', 'Author')"
        )
        conn.execute("""
            INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (1, 1, 1, 'INT. OFFICE - DAY', 'OFFICE', 'DAY', 'A tense meeting.')
        """)

        # Create and store embedding
        embedding = np.array([0.5, 0.5, 0.0], dtype=np.float32)
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        conn.execute(
            """
            INSERT INTO embeddings (entity_type, entity_id, embedding_model, embedding)
            VALUES ('scene', 1, 'test-model', ?)
        """,
            (blob,),
        )
        conn.commit()

        # Search for similar scenes
        query = SearchQuery(raw_query="test", text_query="test")
        query_embedding = np.array([0.6, 0.4, 0.0], dtype=np.float32)

        results = await vector_engine.search_similar_scenes(
            conn=conn,
            query=query,
            query_embedding=query_embedding,
            limit=10,
            threshold=0.5,
        )

        assert len(results) == 1
        result, score = results[0]
        assert isinstance(result, SearchResult)
        assert result.scene_id == 1
        assert result.match_type == "vector"
        assert 0.9 < score < 1.0  # Should have high similarity

        conn.close()

    @pytest.mark.asyncio
    async def test_enhance_results_with_vector_search(
        self, vector_engine, mock_llm_client, tmp_path
    ):
        """Test enhancing SQL results with vector search."""
        # Setup mock LLM client
        vector_engine.llm_client = mock_llm_client

        # Create test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Create minimal schema
        conn.execute(
            """CREATE TABLE scripts (
                id INTEGER PRIMARY KEY, title TEXT, author TEXT, metadata TEXT,
                version INTEGER DEFAULT 1, is_current BOOLEAN DEFAULT TRUE
            )"""
        )
        conn.execute(
            """CREATE TABLE scenes (
                id INTEGER PRIMARY KEY, script_id INTEGER, scene_number INTEGER,
                heading TEXT, location TEXT, time_of_day TEXT, content TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY, entity_type TEXT, entity_id INTEGER,
                embedding_model TEXT, embedding BLOB
            )"""
        )

        # Create existing SQL results
        existing_results = [
            SearchResult(
                script_id=1,
                script_title="Script 1",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="OFFICE",
                scene_time="DAY",
                scene_content="Content 1",
            )
        ]

        # Create query with text
        query = SearchQuery(
            raw_query="dramatic tension", text_query="dramatic tension", limit=10
        )

        # Mock search_similar_scenes to return additional results
        vector_result = SearchResult(
            script_id=2,
            script_title="Script 2",
            script_author="Author",
            scene_id=2,
            scene_number=2,
            scene_heading="EXT. STREET - NIGHT",
            scene_location="STREET",
            scene_time="NIGHT",
            scene_content="Content 2",
            match_type="vector",
            relevance_score=0.85,
        )

        with patch.object(
            vector_engine, "search_similar_scenes", return_value=[(vector_result, 0.85)]
        ):
            enhanced_results = await vector_engine.enhance_results_with_vector_search(
                conn=conn, query=query, existing_results=existing_results, limit=5
            )

        assert len(enhanced_results) == 2
        assert enhanced_results[0] == existing_results[0]
        assert enhanced_results[1].scene_id == 2
        assert enhanced_results[1].match_type == "vector"

        conn.close()

    @pytest.mark.asyncio
    async def test_enhance_results_no_text_query(self, vector_engine):
        """Test that enhancement returns original results when no text query."""
        existing_results = [MagicMock(spec=SearchResult)]
        query = SearchQuery(raw_query="", text_query=None)

        conn = MagicMock()
        results = await vector_engine.enhance_results_with_vector_search(
            conn=conn, query=query, existing_results=existing_results, limit=5
        )

        assert results == existing_results

    @pytest.mark.asyncio
    async def test_enhance_results_error_handling(self, vector_engine):
        """Test error handling in result enhancement."""
        existing_results = [MagicMock(spec=SearchResult)]
        query = SearchQuery(raw_query="test", text_query="test")

        # Mock generate_query_embedding to raise error
        with patch.object(
            vector_engine,
            "generate_query_embedding",
            side_effect=Exception("Embedding error"),
        ):
            conn = MagicMock()
            results = await vector_engine.enhance_results_with_vector_search(
                conn=conn, query=query, existing_results=existing_results, limit=5
            )

            # Should return original results on error
            assert results == existing_results
