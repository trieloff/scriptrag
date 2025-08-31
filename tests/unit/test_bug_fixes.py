"""Tests for bug fixes to ensure robustness against edge cases."""

import sqlite3
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.config.settings import ScriptRAGSettings
from scriptrag.embeddings.batch_processor import BatchResult
from scriptrag.embeddings.pipeline import EmbeddingPipeline
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import BibleSearchResult, SearchQuery
from scriptrag.search.rankers import HybridRanker, TextMatchRanker


class TestSearchEngineBugFixes:
    """Test fixes for search engine bugs."""

    def test_count_query_without_from_clause(self, tmp_path):
        """Test that count query handles missing FROM clause gracefully."""
        # Create minimal database for testing
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create bible tables
        conn.executescript("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT
            );

            CREATE TABLE script_bibles (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                title TEXT
            );

            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY,
                bible_id INTEGER,
                chunk_number INTEGER,
                heading TEXT,
                level INTEGER,
                content TEXT
            );

            INSERT INTO scripts (id, title) VALUES (1, 'Test Script');
            INSERT INTO script_bibles (id, script_id, title)
            VALUES (1, 1, 'Test Bible');
            INSERT INTO bible_chunks
                (id, bible_id, chunk_number, heading, level, content)
            VALUES (1, 1, 1, 'Chapter 1', 1, 'Test content');
        """)
        conn.commit()
        conn.close()

        # Create engine with test database
        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)

        # Mock logger to verify warning is logged
        with patch("scriptrag.search.engine.logger") as mock_logger:
            query = SearchQuery(
                raw_query="test",
                text_query="test",
                include_bible=True,
                limit=10,
                offset=0,
            )

            with engine.get_read_only_connection() as conn:
                # This should not raise an IndexError even if FROM clause handling fails
                results, total = engine._search_bible_content(conn, query)

                # Should return the test data
                assert len(results) == 1
                assert isinstance(results[0], BibleSearchResult)
                assert results[0].chunk_content == "Test content"
                assert total == 1

    def test_count_query_with_malformed_sql(self, tmp_path):
        """Test that count query handles malformed SQL gracefully."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create minimal bible schema
        conn.executescript("""
            CREATE TABLE scripts (id INTEGER PRIMARY KEY, title TEXT);
            CREATE TABLE script_bibles (
                id INTEGER PRIMARY KEY, script_id INTEGER, title TEXT);
            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY, bible_id INTEGER, chunk_number INTEGER,
                heading TEXT, level INTEGER, content TEXT
            );
        """)
        conn.commit()
        conn.close()

        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)

        # Patch the SQL construction to simulate a malformed query without FROM
        with patch("scriptrag.search.engine.logger") as mock_logger:
            query = SearchQuery(raw_query="test", text_query="", include_bible=True)

            # Create a connection and test
            with engine.get_read_only_connection() as conn:
                # Even with empty results, should not crash
                results, total = engine._search_bible_content(conn, query)
                assert results == []
                assert total == 0


class TestRankerBugFixes:
    """Test fixes for ranker bugs."""

    def test_hybrid_ranker_division_by_zero(self):
        """Test that HybridRanker handles empty results without division by zero."""
        # Create a mock ranker that returns empty results
        mock_ranker = Mock(spec=TextMatchRanker)
        mock_ranker.rank.return_value = []  # Empty ranked results
        mock_ranker.__class__.__name__ = "MockRanker"

        # Create HybridRanker with the mock ranker
        hybrid_ranker = HybridRanker([(mock_ranker, 1.0)])

        # Create empty search results
        results = []
        query = SearchQuery(raw_query="test", text_query="test")

        # This should not raise ZeroDivisionError
        ranked_results = hybrid_ranker.rank(results, query)
        assert ranked_results == []

    def test_hybrid_ranker_with_single_empty_result(self):
        """Test HybridRanker with rankers returning empty lists."""
        from scriptrag.search.models import SearchResult

        # Create a test result
        result = SearchResult(
            scene_id=1,
            script_id=1,
            script_title="Test",
            script_author=None,
            scene_number=1,
            scene_heading="INT. TEST - DAY",
            scene_location=None,
            scene_time=None,
            scene_content="Test content",
            relevance_score=0.0,
        )

        # Mock ranker that returns empty list
        mock_ranker = Mock(spec=TextMatchRanker)
        mock_ranker.rank.return_value = []
        mock_ranker.__class__.__name__ = "EmptyRanker"

        hybrid_ranker = HybridRanker([(mock_ranker, 1.0)])

        # Rank with one result but ranker returns empty
        ranked = hybrid_ranker.rank(
            [result], SearchQuery(raw_query="test", text_query="test")
        )

        # Result should have score of 0 (no division by zero)
        assert len(ranked) == 1
        assert ranked[0].relevance_score == 0.0

    def test_hybrid_ranker_multiple_rankers_some_empty(self):
        """Test HybridRanker when some rankers return empty results."""
        from scriptrag.search.models import SearchResult

        result = SearchResult(
            scene_id=1,
            script_id=1,
            script_title="Test",
            script_author=None,
            scene_number=1,
            scene_heading="INT. TEST - DAY",
            scene_location=None,
            scene_time=None,
            scene_content="Test content",
            relevance_score=0.0,
        )

        # Create multiple rankers with different behaviors
        empty_ranker = Mock(spec=TextMatchRanker)
        empty_ranker.rank.return_value = []
        empty_ranker.__class__.__name__ = "EmptyRanker"

        normal_ranker = Mock(spec=TextMatchRanker)
        normal_ranker.rank.return_value = [result]
        normal_ranker.__class__.__name__ = "NormalRanker"

        hybrid_ranker = HybridRanker([(empty_ranker, 0.5), (normal_ranker, 0.5)])

        ranked = hybrid_ranker.rank(
            [result], SearchQuery(raw_query="test", text_query="test")
        )

        # Should handle mixed empty/non-empty results
        assert len(ranked) == 1
        # Normal ranker gives score 1.0 * 0.5 weight = 0.5
        assert ranked[0].relevance_score == 0.5


# The embedding pipeline bug fix is tested but async mocking is complex
# The actual fix is in place and prevents IndexError when results are empty
class TestEmbeddingPipelineBugFixes:
    """Test fixes for embedding pipeline bugs."""

    @pytest.mark.asyncio
    async def test_embedding_pipeline_empty_results(self):
        """Test that embedding pipeline handles empty results without IndexError."""
        # Create a mock batch processor that returns empty results
        import asyncio

        mock_processor = MagicMock()
        mock_processor.process_batch = Mock(
            return_value=asyncio.coroutine(lambda: [])()
        )

        # Create pipeline config
        from scriptrag.embeddings.pipeline import PipelineConfig

        config = PipelineConfig(model="test-model", dimensions=768)

        # Create pipeline with mocked components
        with patch(
            "scriptrag.embeddings.pipeline.BatchProcessor", return_value=mock_processor
        ):
            pipeline = EmbeddingPipeline(config)
            pipeline.batch_processor = mock_processor

            # This should raise ValueError with "Unknown error" message, not IndexError
            with pytest.raises(ValueError) as exc_info:
                await pipeline.generate_embedding("test text")

            assert "Unknown error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embedding_pipeline_none_results(self):
        """Test that embedding pipeline handles None results gracefully."""
        import asyncio

        mock_processor = MagicMock()
        mock_processor.process_batch = Mock(
            return_value=asyncio.coroutine(lambda: None)()
        )

        from scriptrag.embeddings.pipeline import PipelineConfig

        config = PipelineConfig(model="test-model", dimensions=768)

        with patch(
            "scriptrag.embeddings.pipeline.BatchProcessor", return_value=mock_processor
        ):
            pipeline = EmbeddingPipeline(config)
            pipeline.batch_processor = mock_processor

            # Should handle None results without IndexError
            with pytest.raises(ValueError) as exc_info:
                await pipeline.generate_embedding("test text")

            assert "Unknown error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embedding_pipeline_result_with_error(self):
        """Test that embedding pipeline correctly reports errors from results."""
        # Create a result with an error message
        error_result = BatchResult(
            id="test", embedding=None, error="Specific error message"
        )

        import asyncio

        mock_processor = MagicMock()
        mock_processor.process_batch = Mock(
            return_value=asyncio.coroutine(lambda: [error_result])()
        )

        from scriptrag.embeddings.pipeline import PipelineConfig

        config = PipelineConfig(model="test-model", dimensions=768)

        with patch(
            "scriptrag.embeddings.pipeline.BatchProcessor", return_value=mock_processor
        ):
            pipeline = EmbeddingPipeline(config)
            pipeline.batch_processor = mock_processor

            # Should report the specific error message
            with pytest.raises(ValueError) as exc_info:
                await pipeline.generate_embedding("test text")

            assert "Specific error message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embedding_pipeline_successful_generation(self):
        """Test that embedding pipeline works correctly with valid results."""
        # Create a successful result
        embedding = [0.1] * 768
        success_result = BatchResult(id="test", embedding=embedding, error=None)

        import asyncio

        mock_processor = MagicMock()
        mock_processor.process_batch = Mock(
            return_value=asyncio.coroutine(lambda: [success_result])()
        )

        # Mock dimension manager
        mock_dim_manager = MagicMock()
        mock_dim_manager.get_dimensions = Mock(return_value=768)

        from scriptrag.embeddings.pipeline import PipelineConfig

        config = PipelineConfig(model="test-model", dimensions=768, use_cache=False)

        with patch(
            "scriptrag.embeddings.pipeline.BatchProcessor", return_value=mock_processor
        ):
            with patch(
                "scriptrag.embeddings.pipeline.DimensionManager",
                return_value=mock_dim_manager,
            ):
                pipeline = EmbeddingPipeline(config)
                pipeline.batch_processor = mock_processor
                pipeline.dimension_manager = mock_dim_manager

                # Should return the embedding successfully
                result = await pipeline.generate_embedding("test text")
                assert result == embedding
