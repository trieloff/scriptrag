"""Unit tests for semantic search service."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.api.semantic_search import SceneSearchResult, SemanticSearchService
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def settings():
    """Create test settings."""
    return ScriptRAGSettings()


@pytest.fixture
def mock_db_ops():
    """Create mock database operations."""
    db_ops = MagicMock(spec=DatabaseOperations)
    db_ops.transaction = MagicMock()
    return db_ops


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.default_model = "test-model"
    service.generate_embedding = AsyncMock()
    service.encode_embedding_for_db = Mock()
    service.decode_embedding_from_db = Mock()
    service.cosine_similarity = Mock()
    service.generate_scene_embedding = AsyncMock()
    service.save_embedding_to_lfs = Mock()
    return service


@pytest.fixture
def semantic_search(settings, mock_db_ops, mock_embedding_service):
    """Create semantic search service with mocks."""
    return SemanticSearchService(
        settings=settings,
        db_ops=mock_db_ops,
        embedding_service=mock_embedding_service,
    )


class TestSemanticSearchService:
    """Test SemanticSearchService class."""

    def test_init(self, settings):
        """Test semantic search service initialization."""
        service = SemanticSearchService(settings)
        assert service.settings == settings
        assert service.db_ops is not None
        assert service.embedding_service is not None

    @pytest.mark.asyncio
    async def test_search_similar_scenes(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test searching for similar scenes."""
        # Setup mocks
        query_embedding = [0.1, 0.2, 0.3]
        query_bytes = b"query_bytes"
        mock_embedding_service.generate_embedding.return_value = query_embedding
        mock_embedding_service.encode_embedding_for_db.return_value = query_bytes

        # Mock database results
        mock_scenes = [
            {
                "id": 1,
                "script_id": 10,
                "heading": "INT. ROOM - DAY",
                "location": "ROOM",
                "content": "Scene 1 content",
                "_embedding": b"scene1_bytes",
                "metadata": None,
            },
            {
                "id": 2,
                "script_id": 10,
                "heading": "EXT. STREET - NIGHT",
                "location": "STREET",
                "content": "Scene 2 content",
                "_embedding": b"scene2_bytes",
                "metadata": None,
            },
        ]

        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_db_ops.search_similar_scenes.return_value = mock_scenes

        # Mock embedding decoding and similarity
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            [0.1, 0.2, 0.3],  # scene 1 embedding
            [0.2, 0.3, 0.4],  # scene 2 embedding
        ]
        mock_embedding_service.cosine_similarity.side_effect = [
            0.9,  # scene 1 similarity
            0.6,  # scene 2 similarity
        ]

        # Execute search
        results = await semantic_search.search_similar_scenes(
            query="test query",
            script_id=10,
            top_k=5,
            threshold=0.5,
        )

        # Verify results
        assert len(results) == 2
        assert results[0].scene_id == 1
        assert results[0].similarity_score == 0.9
        assert results[1].scene_id == 2
        assert results[1].similarity_score == 0.6

        # Verify calls
        mock_embedding_service.generate_embedding.assert_called_once_with(
            "test query", "test-model"
        )
        mock_db_ops.search_similar_scenes.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_scenes_with_threshold(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test searching with similarity threshold."""
        # Setup mocks
        query_embedding = [0.1, 0.2, 0.3]
        mock_embedding_service.generate_embedding.return_value = query_embedding
        mock_embedding_service.encode_embedding_for_db.return_value = b"query"

        # Mock database results
        mock_scenes = [
            {
                "id": 1,
                "script_id": 10,
                "heading": "INT. ROOM - DAY",
                "location": "ROOM",
                "content": "Scene 1",
                "_embedding": b"scene1",
                "metadata": None,
            },
            {
                "id": 2,
                "script_id": 10,
                "heading": "EXT. STREET - NIGHT",
                "location": "STREET",
                "content": "Scene 2",
                "_embedding": b"scene2",
                "metadata": None,
            },
        ]

        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_db_ops.search_similar_scenes.return_value = mock_scenes

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
        results = await semantic_search.search_similar_scenes(
            query="test", threshold=0.5
        )

        # Only one result should meet threshold
        assert len(results) == 1
        assert results[0].scene_id == 1
        assert results[0].similarity_score == 0.8

    @pytest.mark.asyncio
    async def test_find_related_scenes(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test finding related scenes."""
        source_embedding_bytes = b"source_embedding"
        source_embedding = [0.1, 0.2, 0.3]

        # Mock database operations
        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_db_ops.get_embedding.return_value = source_embedding_bytes
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            source_embedding,  # Source scene
            [0.15, 0.25, 0.35],  # Related scene 1
            [0.8, 0.1, 0.1],  # Unrelated scene
        ]

        # Mock search results
        mock_scenes = [
            {
                "id": 1,  # Source scene (should be skipped)
                "script_id": 10,
                "heading": "INT. ROOM - DAY",
                "location": "ROOM",
                "content": "Source scene",
                "_embedding": b"scene1",
                "metadata": None,
            },
            {
                "id": 2,
                "script_id": 10,
                "heading": "INT. ROOM - NIGHT",
                "location": "ROOM",
                "content": "Related scene",
                "_embedding": b"scene2",
                "metadata": None,
            },
            {
                "id": 3,
                "script_id": 10,
                "heading": "EXT. PARK - DAY",
                "location": "PARK",
                "content": "Unrelated scene",
                "_embedding": b"scene3",
                "metadata": None,
            },
        ]
        mock_db_ops.search_similar_scenes.return_value = mock_scenes

        # Mock similarity scores
        mock_embedding_service.cosine_similarity.side_effect = [
            0.95,  # Very similar
            0.2,  # Not similar
        ]

        # Execute search
        results = await semantic_search.find_related_scenes(
            scene_id=1, script_id=10, threshold=0.5
        )

        # Should return only the related scene (not source, not unrelated)
        assert len(results) == 1
        assert results[0].scene_id == 2
        assert results[0].similarity_score == 0.95

    @pytest.mark.asyncio
    async def test_find_related_scenes_no_embedding(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test finding related scenes when source has no embedding."""
        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn
        mock_db_ops.get_embedding.return_value = None  # No embedding

        results = await semantic_search.find_related_scenes(scene_id=1)

        assert results == []

    @pytest.mark.asyncio
    async def test_generate_missing_embeddings(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test generating embeddings for scenes without them."""
        # Mock scenes without embeddings
        mock_scenes = [
            {"id": 1, "heading": "INT. ROOM - DAY", "content": "Scene 1"},
            {"id": 2, "heading": "EXT. PARK - DAY", "content": "Scene 2"},
        ]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_scenes
        mock_conn.execute.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn

        # Mock embedding generation
        mock_embedding_service.generate_scene_embedding.side_effect = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
        mock_embedding_service.save_embedding_to_lfs.return_value = "path/to/embedding"
        mock_embedding_service.encode_embedding_for_db.return_value = b"encoded"

        # Execute generation
        processed, generated = await semantic_search.generate_missing_embeddings(
            script_id=10
        )

        assert processed == 2
        assert generated == 2
        assert mock_embedding_service.generate_scene_embedding.call_count == 2
        assert mock_db_ops.upsert_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_missing_embeddings_with_error(
        self, semantic_search, mock_db_ops, mock_embedding_service
    ):
        """Test generating embeddings with some failures."""
        # Mock scenes
        mock_scenes = [
            {"id": 1, "heading": "INT. ROOM - DAY", "content": "Scene 1"},
            {"id": 2, "heading": "EXT. PARK - DAY", "content": "Scene 2"},
        ]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_scenes
        mock_conn.execute.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__.return_value = mock_conn

        # First succeeds, second fails
        mock_embedding_service.generate_scene_embedding.side_effect = [
            [0.1, 0.2, 0.3],
            Exception("API error"),
        ]
        mock_embedding_service.save_embedding_to_lfs.return_value = "path"
        mock_embedding_service.encode_embedding_for_db.return_value = b"encoded"

        # Execute generation
        processed, generated = await semantic_search.generate_missing_embeddings()

        assert processed == 2
        assert generated == 1  # Only one succeeded
        assert mock_db_ops.upsert_embedding.call_count == 1

    def test_scene_search_result(self):
        """Test SceneSearchResult dataclass."""
        result = SceneSearchResult(
            scene_id=1,
            script_id=10,
            heading="INT. ROOM - DAY",
            location="ROOM",
            content="Scene content",
            similarity_score=0.95,
            metadata={"key": "value"},
        )

        assert result.scene_id == 1
        assert result.script_id == 10
        assert result.heading == "INT. ROOM - DAY"
        assert result.location == "ROOM"
        assert result.content == "Scene content"
        assert result.similarity_score == 0.95
        assert result.metadata == {"key": "value"}
