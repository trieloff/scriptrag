"""Tests for the embedding pipeline functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.database import (
    ContentExtractor,
    EmbeddingContent,
    EmbeddingError,
    EmbeddingManager,
    EmbeddingPipeline,
    create_script_embeddings,
    search_screenplay_content,
)
from scriptrag.llm.client import LLMClient, LLMClientError


@pytest.fixture
def mock_connection():
    """Mock database connection."""
    conn = Mock()
    conn.fetch_one = Mock()
    conn.fetch_all = Mock()
    conn.execute = Mock()
    conn.transaction = Mock()
    conn.transaction.return_value.__enter__ = Mock(return_value=conn)
    conn.transaction.return_value.__exit__ = Mock(return_value=None)
    return conn


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock(spec=LLMClient)
    client.generate_embedding = AsyncMock()
    client.generate_embeddings = AsyncMock()
    client.close = AsyncMock()
    client.default_embedding_model = "test-embedding-model"
    return client


@pytest.fixture
def sample_embedding():
    """Sample embedding vector."""
    return [0.1, 0.2, 0.3, 0.4, 0.5]


@pytest.fixture
def sample_content():
    """Sample embedding content."""
    return EmbeddingContent(
        entity_type="scene",
        entity_id="test-scene-id",
        content="INT. COFFEE SHOP - DAY\nCharacters discuss the plan.",
        metadata={"scene_order": 1},
    )


class TestEmbeddingManager:
    """Test the EmbeddingManager class."""

    def test_initialization(self, mock_connection, mock_llm_client):
        """Test embedding manager initialization."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)
        assert manager.connection == mock_connection
        assert manager.llm_client == mock_llm_client

    @pytest.mark.asyncio
    async def test_generate_embedding_success(
        self, mock_connection, mock_llm_client, sample_embedding
    ):
        """Test successful embedding generation."""
        mock_llm_client.generate_embedding.return_value = sample_embedding

        manager = EmbeddingManager(mock_connection, mock_llm_client)
        result = await manager.generate_embedding("test content")

        assert result == sample_embedding
        mock_llm_client.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_content(
        self, mock_connection, mock_llm_client
    ):
        """Test embedding generation with empty content."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        with pytest.raises(
            EmbeddingError, match="Cannot generate embedding for empty content"
        ):
            await manager.generate_embedding("")

    @pytest.mark.asyncio
    async def test_generate_embedding_llm_error(self, mock_connection, mock_llm_client):
        """Test embedding generation with LLM error."""
        mock_llm_client.generate_embedding.side_effect = LLMClientError("LLM failed")

        manager = EmbeddingManager(mock_connection, mock_llm_client)

        with pytest.raises(EmbeddingError, match="Embedding generation failed"):
            await manager.generate_embedding("test content")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(
        self, mock_connection, mock_llm_client, sample_content, sample_embedding
    ):
        """Test batch embedding generation."""
        mock_llm_client.generate_embeddings.return_value = [sample_embedding]

        manager = EmbeddingManager(mock_connection, mock_llm_client)
        contents = [sample_content]

        results = await manager.generate_embeddings(contents)

        assert len(results) == 1
        assert results[0][0] == sample_content
        assert results[0][1] == sample_embedding

    def test_vector_blob_conversion(
        self, mock_connection, mock_llm_client, sample_embedding
    ):
        """Test vector to blob conversion."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        # Convert to blob and back
        blob = manager._vector_to_blob(sample_embedding)
        recovered = manager._blob_to_vector(blob)

        # Should be approximately equal due to float precision
        assert len(recovered) == len(sample_embedding)
        for original, recovered_val in zip(sample_embedding, recovered, strict=True):
            assert abs(original - recovered_val) < 1e-6

    def test_store_embedding(self, mock_connection, mock_llm_client, sample_embedding):
        """Test embedding storage."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        manager.store_embedding("scene", "test-id", "test content", sample_embedding)

        mock_connection.execute.assert_called_once()

    def test_store_embedding_empty(self, mock_connection, mock_llm_client):
        """Test storing empty embedding raises error."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        with pytest.raises(EmbeddingError, match="Cannot store empty embedding"):
            manager.store_embedding("scene", "test-id", "test content", [])

    def test_get_embedding(self, mock_connection, mock_llm_client, sample_embedding):
        """Test embedding retrieval."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)
        blob_data = manager._vector_to_blob(sample_embedding)
        mock_connection.fetch_one.return_value = {
            "vector_blob": blob_data,
            "vector_json": None,
        }

        result = manager.get_embedding("scene", "test-id")

        # Should get back approximately the same vector
        assert len(result) == len(sample_embedding)

    def test_cosine_similarity(self, mock_connection, mock_llm_client):
        """Test cosine similarity calculation."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]

        # Orthogonal vectors should have similarity 0
        assert manager.cosine_similarity(vec1, vec2) == 0.0

        # Identical vectors should have similarity 1
        assert manager.cosine_similarity(vec1, vec3) == 1.0

    def test_cosine_similarity_different_dimensions(
        self, mock_connection, mock_llm_client
    ):
        """Test cosine similarity with different vector dimensions."""
        manager = EmbeddingManager(mock_connection, mock_llm_client)

        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        with pytest.raises(ValueError, match="Vectors must have the same dimension"):
            manager.cosine_similarity(vec1, vec2)


class TestContentExtractor:
    """Test the ContentExtractor class."""

    def test_initialization(self, mock_connection):
        """Test content extractor initialization."""
        extractor = ContentExtractor(mock_connection)
        assert extractor.connection == mock_connection

    def test_extract_scene_content(self, mock_connection):
        """Test scene content extraction."""
        # Mock scene data
        mock_connection.fetch_one.return_value = {
            "id": "scene-1",
            "heading": "INT. COFFEE SHOP - DAY",
            "description": "A busy coffee shop",
            "script_order": 1,
            "location_id": "loc-1",
        }

        # Mock scene elements
        mock_connection.fetch_all.return_value = [
            {
                "id": "elem-1",
                "text": "JOHN enters the coffee shop.",
                "element_type": "action",
                "character_name": None,
                "order_in_scene": 1,
            },
            {
                "id": "elem-2",
                "text": "Hello, how are you?",
                "element_type": "dialogue",
                "character_name": "JOHN",
                "order_in_scene": 2,
            },
        ]

        extractor = ContentExtractor(mock_connection)
        contents = extractor.extract_scene_content("scene-1")

        assert len(contents) >= 1
        assert contents[0]["entity_type"] == "scene"
        assert contents[0]["entity_id"] == "scene-1"
        assert "COFFEE SHOP" in contents[0]["content"]

    def test_extract_scene_content_not_found(self, mock_connection):
        """Test scene content extraction when scene not found."""
        mock_connection.fetch_one.return_value = None

        extractor = ContentExtractor(mock_connection)
        contents = extractor.extract_scene_content("nonexistent")

        assert contents == []

    def test_extract_character_content(self, mock_connection):
        """Test character content extraction."""
        # Mock character data
        mock_connection.fetch_one.return_value = {
            "id": "char-1",
            "name": "JOHN",
            "description": "The protagonist",
        }

        # Mock character dialogue
        mock_connection.fetch_all.return_value = [
            {
                "text": "Hello there!",
                "scene_id": "scene-1",
                "heading": "INT. COFFEE SHOP - DAY",
            },
            {
                "text": "How are you?",
                "scene_id": "scene-2",
                "heading": "EXT. STREET - NIGHT",
            },
        ]

        extractor = ContentExtractor(mock_connection)
        contents = extractor.extract_character_content("char-1")

        assert len(contents) >= 1
        assert contents[0]["entity_type"] == "character"
        assert contents[0]["entity_id"] == "char-1"
        assert "JOHN" in contents[0]["content"]

    def test_extract_script_content(self, mock_connection):
        """Test script content extraction."""
        # Mock script data
        mock_connection.fetch_one.return_value = {
            "id": "script-1",
            "title": "Test Script",
            "author": "Test Author",
            "genre": "Drama",
            "logline": "A test script",
            "description": "Test description",
            "is_series": False,
        }

        # Mock characters and locations
        mock_connection.fetch_all.side_effect = [
            [{"name": "JOHN"}, {"name": "JANE"}],  # Characters
            [{"name": "COFFEE SHOP", "scene_count": 3}],  # Locations
        ]

        extractor = ContentExtractor(mock_connection)
        contents = extractor.extract_script_content("script-1")

        assert len(contents) == 1
        assert contents[0]["entity_type"] == "script"
        assert contents[0]["entity_id"] == "script-1"
        assert "Test Script" in contents[0]["content"]


class TestEmbeddingPipeline:
    """Test the EmbeddingPipeline class."""

    def test_initialization(self, mock_connection, mock_llm_client):
        """Test pipeline initialization."""
        pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
        assert pipeline.connection == mock_connection
        assert pipeline.llm_client == mock_llm_client

    @pytest.mark.asyncio
    async def test_process_script_success(
        self, mock_connection, mock_llm_client, sample_embedding
    ):
        """Test successful script processing."""
        # Mock the content extractor to return some content
        with patch.object(
            ContentExtractor, "extract_all_script_elements"
        ) as mock_extract:
            mock_extract.return_value = [
                EmbeddingContent(
                    entity_type="scene",
                    entity_id="scene-1",
                    content="Test scene content",
                    metadata={},
                )
            ]

            # Mock embedding generation
            mock_llm_client.generate_embeddings.return_value = [sample_embedding]

            # Mock storage
            with patch.object(EmbeddingManager, "store_embeddings") as mock_store:
                mock_store.return_value = 1

                with patch.object(
                    EmbeddingManager, "get_embeddings_stats"
                ) as mock_stats:
                    mock_stats.return_value = {"total_embeddings": 1}

                    pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
                    result = await pipeline.process_script("script-1")

                    assert result["status"] == "success"
                    assert result["embeddings_stored"] == 1

    @pytest.mark.asyncio
    async def test_process_script_no_content(self, mock_connection, mock_llm_client):
        """Test script processing with no content."""
        with patch.object(
            ContentExtractor, "extract_all_script_elements"
        ) as mock_extract:
            mock_extract.return_value = []

            pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
            result = await pipeline.process_script("script-1")

            assert result["status"] == "no_content"
            assert result["embeddings_stored"] == 0

    @pytest.mark.asyncio
    async def test_semantic_search(
        self, mock_connection, mock_llm_client, sample_embedding
    ):
        """Test semantic search functionality."""
        # Mock embedding generation for query
        mock_llm_client.generate_embedding.return_value = sample_embedding

        # Mock search results
        with patch.object(EmbeddingManager, "semantic_search") as mock_search:
            mock_search.return_value = [
                {
                    "entity_type": "scene",
                    "entity_id": "scene-1",
                    "content": "Test content",
                    "similarity": 0.8,
                    "metadata": {},
                }
            ]

            # Mock scene details lookup
            mock_connection.fetch_one.return_value = {
                "heading": "INT. TEST - DAY",
                "script_order": 1,
            }

            pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
            results = await pipeline.semantic_search("test query")

            assert len(results) == 1
            assert results[0]["entity_type"] == "scene"
            assert "entity_details" in results[0]

    @pytest.mark.asyncio
    async def test_get_similar_scenes(
        self, mock_connection, mock_llm_client, sample_embedding
    ):
        """Test finding similar scenes."""
        # Mock getting reference scene embedding
        with patch.object(EmbeddingManager, "get_embedding") as mock_get:
            mock_get.return_value = sample_embedding

            # Mock similarity search
            with patch.object(EmbeddingManager, "find_similar") as mock_find:
                mock_find.return_value = [
                    {
                        "entity_type": "scene",
                        "entity_id": "scene-2",  # Different from reference
                        "content": "Similar scene",
                        "similarity": 0.7,
                        "metadata": {},
                    }
                ]

                # Mock scene details
                mock_connection.fetch_one.return_value = {
                    "heading": "INT. SIMILAR - DAY",
                    "script_order": 2,
                    "description": "A similar scene",
                }

                pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
                results = await pipeline.get_similar_scenes("scene-1")

                assert len(results) == 1
                assert results[0]["entity_id"] == "scene-2"
                assert "entity_details" in results[0]

    @pytest.mark.asyncio
    async def test_close(self, mock_connection, mock_llm_client):
        """Test pipeline cleanup."""
        pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)
        await pipeline.close()

        # Should close the embedding manager
        mock_llm_client.close.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_create_script_embeddings(self, mock_connection):
        """Test create_script_embeddings convenience function."""
        patch_path = "scriptrag.database.embedding_pipeline.EmbeddingPipeline"
        with patch(patch_path) as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.process_script.return_value = {"status": "success"}
            mock_pipeline_class.return_value = mock_pipeline

            result = await create_script_embeddings("script-1", mock_connection)

            assert result["status"] == "success"
            mock_pipeline.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_screenplay_content(self, mock_connection):
        """Test search_screenplay_content convenience function."""
        patch_path = "scriptrag.database.embedding_pipeline.EmbeddingPipeline"
        with patch(patch_path) as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.semantic_search.return_value = [{"entity_type": "scene"}]
            mock_pipeline_class.return_value = mock_pipeline

            results = await search_screenplay_content("test query", mock_connection)

            assert len(results) == 1
            mock_pipeline.close.assert_called_once()


class TestErrorHandling:
    """Test error handling in embedding pipeline."""

    @pytest.mark.asyncio
    async def test_embedding_manager_storage_error(
        self, mock_connection, mock_llm_client
    ):
        """Test error handling in embedding storage."""
        mock_connection.execute.side_effect = Exception("Database error")

        manager = EmbeddingManager(mock_connection, mock_llm_client)

        with pytest.raises(EmbeddingError, match="Failed to store embedding"):
            manager.store_embedding("scene", "test-id", "content", [0.1, 0.2])

    @pytest.mark.asyncio
    async def test_pipeline_extraction_error(self, mock_connection, mock_llm_client):
        """Test error handling in content extraction."""
        with patch.object(
            ContentExtractor, "extract_all_script_elements"
        ) as mock_extract:
            mock_extract.side_effect = Exception("Extraction failed")

            pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)

            with pytest.raises(EmbeddingError, match="Script processing failed"):
                await pipeline.process_script("script-1")

    @pytest.mark.asyncio
    async def test_semantic_search_error(self, mock_connection, mock_llm_client):
        """Test error handling in semantic search."""
        mock_llm_client.generate_embedding.side_effect = LLMClientError("LLM failed")

        pipeline = EmbeddingPipeline(mock_connection, mock_llm_client)

        with pytest.raises(EmbeddingError, match="Semantic search failed"):
            await pipeline.semantic_search("test query")
