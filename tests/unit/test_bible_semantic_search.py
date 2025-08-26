"""Unit tests for bible content semantic search."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.api.semantic_search import BibleSearchResult, SemanticSearchService
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def settings():
    """Create test settings."""
    return ScriptRAGSettings()


@pytest.fixture
def mock_db_ops():
    """Create mock database operations."""
    db_ops = MagicMock(spec=DatabaseOperations)
    db_ops.transaction = MagicMock(spec=object)
    return db_ops


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.default_model = "test-model"
    service.generate_embedding = AsyncMock(spec=object)
    service.encode_embedding_for_db = Mock(spec=object)
    service.decode_embedding_from_db = Mock(spec=object)
    service.cosine_similarity = Mock(spec=object)
    service.save_embedding_to_lfs = Mock(spec=object)
    return service


@pytest.fixture
def semantic_search(settings, mock_db_ops, mock_embedding_service):
    """Create semantic search service with mocks."""
    return SemanticSearchService(
        settings=settings,
        db_ops=mock_db_ops,
        embedding_service=mock_embedding_service,
    )


class TestBibleSemanticSearch:
    """Test bible content semantic search functionality."""

    @pytest.mark.asyncio
    async def test_search_similar_bible_content(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test searching for similar bible content."""
        # Setup mocks
        query_embedding = [0.1, 0.2, 0.3]
        mock_embedding_service.generate_embedding.return_value = query_embedding

        # Mock database results
        mock_chunks = [
            {
                "id": 1,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "Character Bible",
                "heading": "Main Character",
                "content": "Character backstory...",
                "level": 2,
                "embedding": b"chunk1_bytes",
                "metadata": None,
            },
            {
                "id": 2,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "Character Bible",
                "heading": "Supporting Cast",
                "content": "Supporting character details...",
                "level": 2,
                "embedding": b"chunk2_bytes",
                "metadata": None,
            },
        ]

        mock_conn = MagicMock(spec=object)
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = mock_chunks

        # Mock embedding decoding and similarity
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            [0.1, 0.2, 0.3],  # chunk 1 embedding
            [0.2, 0.3, 0.4],  # chunk 2 embedding
        ]
        mock_embedding_service.cosine_similarity.side_effect = [
            0.95,  # chunk 1 similarity
            0.65,  # chunk 2 similarity
        ]

        # Execute search
        results = await semantic_search.search_similar_bible_content(
            query="character backstory",
            script_id=100,
            top_k=5,
            threshold=0.5,
        )

        # Verify results
        assert len(results) == 2
        assert isinstance(results[0], BibleSearchResult)
        assert results[0].chunk_id == 1
        assert results[0].bible_title == "Character Bible"
        assert results[0].heading == "Main Character"
        assert results[0].similarity_score == 0.95
        assert results[1].chunk_id == 2
        assert results[1].similarity_score == 0.65

        # Verify calls
        mock_embedding_service.generate_embedding.assert_called_once_with(
            "character backstory", "test-model"
        )

    @pytest.mark.asyncio
    async def test_search_bible_content_with_threshold(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test bible search with similarity threshold filtering."""
        # Setup mocks
        query_embedding = [0.1, 0.2, 0.3]
        mock_embedding_service.generate_embedding.return_value = query_embedding

        # Mock database results
        mock_chunks = [
            {
                "id": 1,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "World Bible",
                "heading": "Magic System",
                "content": "Magic rules...",
                "level": 1,
                "embedding": b"chunk1",
                "metadata": None,
            },
            {
                "id": 2,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "World Bible",
                "heading": "Geography",
                "content": "World map...",
                "level": 1,
                "embedding": b"chunk2",
                "metadata": None,
            },
        ]

        mock_conn = MagicMock(spec=object)
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = mock_chunks

        # Mock similarity scores - one below threshold
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            [0.1, 0.2, 0.3],
            [0.2, 0.3, 0.4],
        ]
        mock_embedding_service.cosine_similarity.side_effect = [
            0.8,  # Above threshold
            0.3,  # Below threshold
        ]

        # Execute search with threshold 0.5
        results = await semantic_search.search_similar_bible_content(
            query="magic system", threshold=0.5
        )

        # Only one result should meet threshold
        assert len(results) == 1
        assert results[0].chunk_id == 1
        assert results[0].heading == "Magic System"
        assert results[0].similarity_score == 0.8

    @pytest.mark.asyncio
    async def test_generate_bible_embeddings(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test generating embeddings for bible chunks."""
        # Mock chunks without embeddings
        mock_chunks = [
            {"id": 1, "heading": "Chapter 1", "content": "Chapter 1 content"},
            {"id": 2, "heading": "Chapter 2", "content": "Chapter 2 content"},
        ]

        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = mock_chunks
        mock_conn.execute.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn

        # Mock embedding generation
        mock_embedding_service.generate_embedding.side_effect = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
        mock_embedding_service.save_embedding_to_lfs.return_value = "path/to/embedding"
        mock_embedding_service.encode_embedding_for_db.return_value = b"encoded"

        # Execute generation
        processed, generated = await semantic_search.generate_bible_embeddings(
            script_id=100
        )

        assert processed == 2
        assert generated == 2
        assert mock_embedding_service.generate_embedding.call_count == 2
        assert mock_db_ops.upsert_embedding.call_count == 2

        # Verify the embeddings were saved with correct entity type
        first_call = mock_db_ops.upsert_embedding.call_args_list[0]
        assert first_call.kwargs["entity_type"] == "bible_chunk"
        assert first_call.kwargs["entity_id"] == 1

    @pytest.mark.asyncio
    async def test_generate_bible_embeddings_with_error(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test bible embedding generation with failures."""
        # Mock chunks
        mock_chunks = [
            {"id": 1, "heading": "Chapter 1", "content": "Chapter 1 content"},
            {"id": 2, "heading": None, "content": "Chapter 2 content"},
        ]

        mock_conn = MagicMock(spec=object)
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = mock_chunks
        mock_conn.execute.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn

        # First succeeds, second fails
        mock_embedding_service.generate_embedding.side_effect = [
            [0.1, 0.2, 0.3],
            Exception("API error"),
        ]
        mock_embedding_service.save_embedding_to_lfs.return_value = "path"
        mock_embedding_service.encode_embedding_for_db.return_value = b"encoded"

        # Execute generation
        processed, generated = await semantic_search.generate_bible_embeddings()

        assert processed == 2
        assert generated == 1  # Only one succeeded
        assert mock_db_ops.upsert_embedding.call_count == 1

    def test_bible_search_result_dataclass(self):
        """Test BibleSearchResult dataclass."""
        result = BibleSearchResult(
            chunk_id=1,
            bible_id=10,
            script_id=100,
            bible_title="Character Bible",
            heading="Main Character",
            content="Character backstory and details",
            similarity_score=0.92,
            level=2,
            metadata={"word_count": 150},
        )

        assert result.chunk_id == 1
        assert result.bible_id == 10
        assert result.script_id == 100
        assert result.bible_title == "Character Bible"
        assert result.heading == "Main Character"
        assert result.content == "Character backstory and details"
        assert result.similarity_score == 0.92
        assert result.level == 2
        assert result.metadata == {"word_count": 150}
