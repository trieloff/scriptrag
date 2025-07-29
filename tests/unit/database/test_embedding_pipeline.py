#!/usr/bin/env python3
"""
Unit tests for embedding pipeline with batch processing and similarity search.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.database.embeddings import (
    EmbeddingContent,
    EmbeddingError,
    EmbeddingManager,
)
from scriptrag.llm.client import LLMClientError


class TestEmbeddingManager:
    """Test EmbeddingManager class."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock()
        client.default_embedding_model = "test-embed-model"
        client.generate_embedding = AsyncMock()
        client.generate_embeddings = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.llm.batch_size = 5
        settings.llm.embedding_dimensions = 384
        return settings

    @pytest.fixture
    def embedding_manager(self, db_connection, mock_llm_client, mock_settings):
        """Create embedding manager with mocked dependencies."""
        with patch(
            "scriptrag.database.embeddings.get_settings", return_value=mock_settings
        ):
            return EmbeddingManager(
                connection=db_connection,
                llm_client=mock_llm_client,
                embedding_model="test-model",
            )

    @pytest.mark.asyncio
    async def test_generate_embedding_single(self, embedding_manager, mock_llm_client):
        """Test generating a single embedding."""
        test_content = "This is a test scene description"
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        mock_llm_client.generate_embedding.return_value = test_embedding

        result = await embedding_manager.generate_embedding(test_content)

        assert result == test_embedding
        mock_llm_client.generate_embedding.assert_called_once_with(
            test_content, model="test-model"
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_content(self, embedding_manager):
        """Test error handling for empty content."""
        with pytest.raises(EmbeddingError, match="empty content"):
            await embedding_manager.generate_embedding("")

        with pytest.raises(EmbeddingError, match="empty content"):
            await embedding_manager.generate_embedding("   ")

    @pytest.mark.asyncio
    async def test_generate_embedding_error_handling(
        self, embedding_manager, mock_llm_client
    ):
        """Test error handling when LLM client fails."""
        mock_llm_client.generate_embedding.side_effect = LLMClientError("API error")

        with pytest.raises(EmbeddingError, match="Embedding generation failed"):
            await embedding_manager.generate_embedding("test content")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, embedding_manager, mock_llm_client):
        """Test batch embedding generation."""
        contents = [
            EmbeddingContent(
                entity_type="scene",
                entity_id="scene1",
                content="Scene 1 content",
                metadata={"order": 1},
            ),
            EmbeddingContent(
                entity_type="scene",
                entity_id="scene2",
                content="Scene 2 content",
                metadata={"order": 2},
            ),
            EmbeddingContent(
                entity_type="character",
                entity_id="char1",
                content="Character description",
                metadata={"name": "ALICE"},
            ),
        ]

        mock_embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]

        mock_llm_client.generate_embeddings.return_value = mock_embeddings

        results = await embedding_manager.generate_embeddings(contents)

        assert len(results) == 3
        for i, (content, embedding) in enumerate(results):
            assert content == contents[i]
            assert embedding == mock_embeddings[i]

        # Should be called once with all texts
        mock_llm_client.generate_embeddings.assert_called_once()
        call_args = mock_llm_client.generate_embeddings.call_args[0][0]
        assert call_args == [
            "Scene 1 content",
            "Scene 2 content",
            "Character description",
        ]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_processing(
        self, embedding_manager, mock_llm_client
    ):
        """Test batch processing with configured batch size."""
        # Create more contents than batch size (5)
        contents = []
        for i in range(12):
            contents.append(
                EmbeddingContent(
                    entity_type="scene",
                    entity_id=f"scene{i}",
                    content=f"Scene {i} content",
                    metadata={},
                )
            )

        # Mock embeddings for each batch
        mock_llm_client.generate_embeddings.side_effect = [
            [[0.1, 0.2, 0.3]] * 5,  # First batch (5 items)
            [[0.4, 0.5, 0.6]] * 5,  # Second batch (5 items)
            [[0.7, 0.8, 0.9]] * 2,  # Third batch (2 items)
        ]

        results = await embedding_manager.generate_embeddings(contents)

        assert len(results) == 12
        # Should be called 3 times (batches of 5, 5, 2)
        assert mock_llm_client.generate_embeddings.call_count == 3

        # Verify batch sizes
        calls = mock_llm_client.generate_embeddings.call_args_list
        assert len(calls[0][0][0]) == 5  # First batch
        assert len(calls[1][0][0]) == 5  # Second batch
        assert len(calls[2][0][0]) == 2  # Third batch

    @pytest.mark.asyncio
    async def test_generate_embeddings_custom_batch_size(
        self, embedding_manager, mock_llm_client
    ):
        """Test batch processing with custom batch size."""
        contents = [
            EmbeddingContent(
                entity_type="scene",
                entity_id=f"scene{i}",
                content=f"Content {i}",
                metadata={},
            )
            for i in range(7)
        ]

        mock_llm_client.generate_embeddings.side_effect = [
            [[0.1, 0.2]] * 3,  # First batch
            [[0.3, 0.4]] * 3,  # Second batch
            [[0.5, 0.6]] * 1,  # Third batch
        ]

        results = await embedding_manager.generate_embeddings(contents, batch_size=3)

        assert len(results) == 7
        assert mock_llm_client.generate_embeddings.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_embeddings_empty_list(self, embedding_manager):
        """Test handling empty content list."""
        results = await embedding_manager.generate_embeddings([])
        assert results == []

    @pytest.mark.asyncio
    async def test_generate_embeddings_error_handling(
        self, embedding_manager, mock_llm_client
    ):
        """Test error handling in batch generation."""
        contents = [
            EmbeddingContent(
                entity_type="scene", entity_id="scene1", content="Content", metadata={}
            )
        ]

        mock_llm_client.generate_embeddings.side_effect = LLMClientError(
            "Batch API error"
        )

        with pytest.raises(EmbeddingError, match="Batch embedding generation failed"):
            await embedding_manager.generate_embeddings(contents)

    def test_vector_blob_conversion(self, embedding_manager):
        """Test conversion between vector and blob formats."""
        test_vectors = [
            [0.1, 0.2, 0.3, 0.4],
            [-0.5, 0.0, 0.5, 1.0],
            [1e-6, 1e6, -1e-6, -1e6],
        ]

        for vector in test_vectors:
            blob = embedding_manager._vector_to_blob(vector)
            assert isinstance(blob, bytes)
            assert len(blob) == len(vector) * 4  # 4 bytes per float

            # Convert back
            recovered = embedding_manager._blob_to_vector(blob)
            assert len(recovered) == len(vector)
            for original, recovered_val in zip(vector, recovered, strict=False):
                assert abs(original - recovered_val) < 1e-6

    def test_parse_vector_json(self, embedding_manager):
        """Test parsing vector JSON data."""
        # Valid JSON
        valid_json = "[0.1, 0.2, 0.3, 0.4]"
        result = embedding_manager._parse_vector_json(valid_json)
        assert result == [0.1, 0.2, 0.3, 0.4]

        # Invalid JSON
        invalid_json = "not json"
        result = embedding_manager._parse_vector_json(invalid_json)
        assert result is None

        # JSON but not a list
        not_list = '{"key": "value"}'
        result = embedding_manager._parse_vector_json(not_list)
        assert result is None

        # List with non-numeric values
        mixed_list = '[0.1, "string", 0.3]'
        result = embedding_manager._parse_vector_json(mixed_list)
        assert result is None

        # List with integers (should convert to float)
        int_list = "[1, 2, 3, 4]"
        result = embedding_manager._parse_vector_json(int_list)
        assert result == [1.0, 2.0, 3.0, 4.0]

    def test_validate_embedding_dimension(self, embedding_manager):
        """Test embedding dimension validation."""
        # First embedding sets the dimension
        embedding1 = [0.1, 0.2, 0.3, 0.4]
        embedding_manager._validate_embedding_dimension(embedding1)  # Should pass

        # Store an embedding to establish dimension
        embedding_manager.store_embedding(
            "test_type", "test_id", "test content", embedding1
        )

        # Same dimension should pass
        embedding2 = [0.5, 0.6, 0.7, 0.8]
        embedding_manager._validate_embedding_dimension(embedding2)  # Should pass

        # Different dimension should fail
        embedding3 = [0.1, 0.2, 0.3]  # Wrong dimension
        with pytest.raises(EmbeddingError, match="dimension mismatch"):
            embedding_manager._validate_embedding_dimension(embedding3, expected_dim=4)

        # Empty embedding should fail
        with pytest.raises(EmbeddingError, match="empty embedding"):
            embedding_manager._validate_embedding_dimension([])

    def test_store_embedding(self, embedding_manager, db_connection):
        """Test storing a single embedding."""
        entity_type = "scene"
        entity_id = str(uuid4())
        content = "Test scene content"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        model = "test-model"

        embedding_manager.store_embedding(
            entity_type, entity_id, content, embedding, model
        )

        # Verify stored in database
        row = db_connection.fetch_one(
            "SELECT * FROM embeddings WHERE entity_id = ?", (entity_id,)
        )

        assert row is not None
        assert row["entity_type"] == entity_type
        assert row["entity_id"] == entity_id
        assert row["content"] == content
        assert row["embedding_model"] == model
        assert row["dimension"] == 5

        # Verify blob format
        recovered = embedding_manager._blob_to_vector(row["vector_blob"])
        assert len(recovered) == len(embedding)
        for orig, recov in zip(embedding, recovered, strict=False):
            assert abs(orig - recov) < 1e-6

    def test_store_embedding_empty_vector(self, embedding_manager):
        """Test error when storing empty embedding."""
        with pytest.raises(EmbeddingError, match="empty embedding"):
            embedding_manager.store_embedding(
                "type",
                "id",
                "content",
                [],  # Empty embedding
                "model",
            )

    def test_store_embedding_update_existing(self, embedding_manager):
        """Test updating existing embedding."""
        entity_type = "character"
        entity_id = "char1"

        # Store initial embedding
        embedding_manager.store_embedding(
            entity_type, entity_id, "Initial content", [0.1, 0.2, 0.3], "model1"
        )

        # Update with new embedding
        embedding_manager.store_embedding(
            entity_type, entity_id, "Updated content", [0.4, 0.5, 0.6], "model1"
        )

        # Verify updated
        row = embedding_manager.connection.fetch_one(
            "SELECT * FROM embeddings WHERE entity_id = ? AND embedding_model = ?",
            (entity_id, "model1"),
        )

        assert row["content"] == "Updated content"
        recovered = embedding_manager._blob_to_vector(row["vector_blob"])
        assert recovered[0] == pytest.approx(0.4, abs=1e-6)

    @pytest.mark.asyncio
    async def test_store_embeddings_batch(self, embedding_manager):
        """Test storing multiple embeddings."""
        embeddings = [
            (
                EmbeddingContent(
                    entity_type="scene",
                    entity_id=f"scene{i}",
                    content=f"Scene {i} content",
                    metadata={},
                ),
                [0.1 * i, 0.2 * i, 0.3 * i],
            )
            for i in range(5)
        ]

        count = await embedding_manager.store_embeddings(
            embeddings, model="batch-model"
        )

        assert count == 5

        # Verify all stored
        for i in range(5):
            row = embedding_manager.connection.fetch_one(
                "SELECT * FROM embeddings WHERE entity_id = ?", (f"scene{i}",)
            )
            assert row is not None
            assert row["embedding_model"] == "batch-model"

    @pytest.mark.asyncio
    async def test_store_embeddings_skip_invalid(self, embedding_manager):
        """Test that invalid embeddings are skipped."""
        # First store one embedding to establish dimension
        embedding_manager.store_embedding(
            "scene", "scene0", "content", [0.1, 0.2, 0.3], "test-model"
        )

        embeddings = [
            (
                EmbeddingContent(
                    entity_type="scene",
                    entity_id="scene1",
                    content="Valid",
                    metadata={},
                ),
                [0.1, 0.2, 0.3],  # Valid dimension
            ),
            (
                EmbeddingContent(
                    entity_type="scene",
                    entity_id="scene2",
                    content="Invalid",
                    metadata={},
                ),
                [],  # Empty embedding
            ),
            (
                EmbeddingContent(
                    entity_type="scene",
                    entity_id="scene3",
                    content="Wrong dim",
                    metadata={},
                ),
                [0.1, 0.2],  # Wrong dimension
            ),
            (
                EmbeddingContent(
                    entity_type="scene",
                    entity_id="scene4",
                    content="Valid 2",
                    metadata={},
                ),
                [0.4, 0.5, 0.6],  # Valid dimension
            ),
        ]

        count = await embedding_manager.store_embeddings(embeddings)

        # Only 2 valid embeddings should be stored
        assert count == 2

    def test_get_embedding(self, embedding_manager):
        """Test retrieving an embedding."""
        entity_type = "location"
        entity_id = "loc1"
        embedding = [0.1, 0.2, 0.3, 0.4]

        # Store embedding
        embedding_manager.store_embedding(
            entity_type, entity_id, "Location description", embedding, "test-model"
        )

        # Retrieve it
        retrieved = embedding_manager.get_embedding(
            entity_type, entity_id, "test-model"
        )

        assert retrieved is not None
        assert len(retrieved) == len(embedding)
        for orig, ret in zip(embedding, retrieved, strict=False):
            assert abs(orig - ret) < 1e-6

    def test_get_embedding_not_found(self, embedding_manager):
        """Test retrieving non-existent embedding."""
        result = embedding_manager.get_embedding(
            "nonexistent_type", "nonexistent_id", "test-model"
        )
        assert result is None

    def test_get_embedding_fallback_to_json(self, embedding_manager, db_connection):
        """Test fallback to JSON format when blob is missing."""
        entity_id = "test_id"
        embedding = [0.1, 0.2, 0.3]

        # Manually insert with only JSON format
        with db_connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO embeddings
                (
                    entity_type, entity_id, content, embedding_model,
                    vector_json, dimension
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("test", entity_id, "content", "model", json.dumps(embedding), 3),
            )

        # Should retrieve from JSON
        retrieved = embedding_manager.get_embedding("test", entity_id, "model")
        assert retrieved == embedding

    def test_delete_embedding(self, embedding_manager):
        """Test deleting an embedding."""
        entity_type = "scene"
        entity_id = "scene_to_delete"

        # Store embedding
        embedding_manager.store_embedding(
            entity_type, entity_id, "Content", [0.1, 0.2, 0.3], "test-model"
        )

        # Delete it
        success = embedding_manager.delete_embedding(
            entity_type, entity_id, "test-model"
        )
        assert success is True

        # Verify it's gone
        retrieved = embedding_manager.get_embedding(
            entity_type, entity_id, "test-model"
        )
        assert retrieved is None

        # Delete non-existent should return False
        success = embedding_manager.delete_embedding(
            "nonexistent", "nonexistent", "test-model"
        )
        assert success is False

    def test_cosine_similarity(self, embedding_manager):
        """Test cosine similarity calculation."""
        # Identical vectors
        vec1 = [1.0, 0.0, 0.0]
        similarity = embedding_manager.cosine_similarity(vec1, vec1)
        assert similarity == pytest.approx(1.0)

        # Orthogonal vectors
        vec2 = [0.0, 1.0, 0.0]
        similarity = embedding_manager.cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

        # Opposite vectors
        vec3 = [-1.0, 0.0, 0.0]
        similarity = embedding_manager.cosine_similarity(vec1, vec3)
        assert similarity == pytest.approx(-1.0)

        # Arbitrary vectors
        vec4 = [0.6, 0.8, 0.0]
        vec5 = [0.8, 0.6, 0.0]
        similarity = embedding_manager.cosine_similarity(vec4, vec5)
        assert similarity == pytest.approx(0.96, abs=0.01)

        # Different dimensions should raise error
        with pytest.raises(ValueError, match="same dimension"):
            embedding_manager.cosine_similarity([1, 2], [1, 2, 3])

        # Zero vectors
        zero_vec = [0.0, 0.0, 0.0]
        similarity = embedding_manager.cosine_similarity(zero_vec, vec1)
        assert similarity == 0.0

    def test_find_similar(self, embedding_manager):
        """Test finding similar embeddings."""
        # Store test embeddings
        embeddings_data = [
            ("scene", "scene1", "Action scene", [1.0, 0.0, 0.0]),
            ("scene", "scene2", "Similar action", [0.9, 0.1, 0.0]),
            ("scene", "scene3", "Different scene", [0.0, 1.0, 0.0]),
            ("character", "char1", "Character desc", [0.8, 0.2, 0.0]),
        ]

        for entity_type, entity_id, content, embedding in embeddings_data:
            embedding_manager.store_embedding(
                entity_type, entity_id, content, embedding, "test-model"
            )

        # Find similar to first scene
        query_embedding = [1.0, 0.0, 0.0]
        results = embedding_manager.find_similar(
            query_embedding, model="test-model", limit=3, min_similarity=0.5
        )

        assert len(results) >= 2
        # Results should be sorted by similarity
        assert results[0]["entity_id"] == "scene1"
        assert results[0]["similarity"] == pytest.approx(1.0)
        assert results[1]["entity_id"] == "scene2"
        assert results[1]["similarity"] > 0.9

        # Test with entity type filter
        scene_results = embedding_manager.find_similar(
            query_embedding, entity_type="scene", model="test-model", limit=10
        )

        # Should not include character
        entity_ids = [r["entity_id"] for r in scene_results]
        assert "char1" not in entity_ids

        # Test with high similarity threshold
        high_threshold_results = embedding_manager.find_similar(
            query_embedding, model="test-model", min_similarity=0.95
        )

        # Should only include very similar items
        assert len(high_threshold_results) <= 2

    def test_find_similar_dimension_mismatch(self, embedding_manager):
        """Test handling dimension mismatch in similarity search."""
        # Store embeddings with dimension 3
        embedding_manager.store_embedding(
            "scene", "scene1", "Content", [0.1, 0.2, 0.3], "model"
        )

        # Search with different dimension should skip mismatched embeddings
        query = [0.1, 0.2, 0.3, 0.4]  # Dimension 4
        results = embedding_manager.find_similar(query, model="model")

        assert len(results) == 0  # No matches due to dimension mismatch

    @pytest.mark.asyncio
    async def test_semantic_search(self, embedding_manager, mock_llm_client):
        """Test semantic search functionality."""
        # Store some embeddings first
        test_embeddings = [
            ("scene", "scene1", "Coffee shop conversation", [0.8, 0.2, 0.0]),
            ("scene", "scene2", "Restaurant dialogue", [0.7, 0.3, 0.0]),
            ("scene", "scene3", "Car chase action", [0.0, 0.0, 1.0]),
        ]

        for entity_type, entity_id, content, embedding in test_embeddings:
            embedding_manager.store_embedding(
                entity_type, entity_id, content, embedding, "test-model"
            )

        # Mock query embedding
        query = "dialogue in a cafe"
        query_embedding = [0.75, 0.25, 0.0]
        mock_llm_client.generate_embedding.return_value = query_embedding

        results = await embedding_manager.semantic_search(
            query, entity_type="scene", model="test-model", limit=2, min_similarity=0.5
        )

        assert len(results) >= 1
        assert results[0]["entity_id"] in ["scene1", "scene2"]
        assert results[0]["similarity"] > 0.9

        # Verify query was embedded
        mock_llm_client.generate_embedding.assert_called_once_with(
            query, model="test-model"
        )

    @pytest.mark.asyncio
    async def test_semantic_search_empty_query(self, embedding_manager):
        """Test semantic search with empty query."""
        results = await embedding_manager.semantic_search("")
        assert results == []

        results = await embedding_manager.semantic_search("   ")
        assert results == []

    @pytest.mark.asyncio
    async def test_semantic_search_error_handling(
        self, embedding_manager, mock_llm_client
    ):
        """Test error handling in semantic search."""
        mock_llm_client.generate_embedding.side_effect = Exception("Embedding error")

        with pytest.raises(EmbeddingError, match="Semantic search failed"):
            await embedding_manager.semantic_search("test query")

    def test_get_embeddings_stats(self, embedding_manager):
        """Test getting embedding statistics."""
        # Store various embeddings
        test_data = [
            ("scene", "s1", [0.1, 0.2, 0.3]),
            ("scene", "s2", [0.1, 0.2, 0.3]),
            ("character", "c1", [0.1, 0.2, 0.3]),
            ("location", "l1", [0.1, 0.2, 0.3]),
        ]

        for entity_type, entity_id, embedding in test_data:
            embedding_manager.store_embedding(
                entity_type,
                entity_id,
                f"{entity_type} content",
                embedding,
                "test-model",
            )

        stats = embedding_manager.get_embeddings_stats("test-model")

        assert stats["model"] == "test-model"
        assert stats["total_embeddings"] == 4
        assert stats["dimension"] == 3
        assert stats["entity_counts"]["scene"] == 2
        assert stats["entity_counts"]["character"] == 1
        assert stats["entity_counts"]["location"] == 1

    def test_get_embeddings_stats_empty(self, embedding_manager):
        """Test stats for model with no embeddings."""
        stats = embedding_manager.get_embeddings_stats("nonexistent-model")

        assert stats["model"] == "nonexistent-model"
        assert stats["total_embeddings"] == 0
        assert stats["dimension"] is None
        assert stats["entity_counts"] == {}

    @pytest.mark.asyncio
    async def test_refresh_embeddings(self, embedding_manager, mock_llm_client):
        """Test refreshing embeddings."""
        # Store initial embeddings
        initial_embeddings = [
            ("scene", "s1", "Scene 1", [0.1, 0.2, 0.3]),
            ("scene", "s2", "Scene 2", [0.4, 0.5, 0.6]),
            ("character", "c1", "Character", [0.7, 0.8, 0.9]),
        ]

        for entity_type, entity_id, content, embedding in initial_embeddings:
            embedding_manager.store_embedding(
                entity_type, entity_id, content, embedding, "old-model"
            )

        # Mock new embeddings
        new_embeddings = {
            "Scene 1": [0.11, 0.21, 0.31],
            "Scene 2": [0.41, 0.51, 0.61],
            "Character": [0.71, 0.81, 0.91],
        }

        def mock_generate(content, model):  # noqa: ARG001
            return new_embeddings.get(content, [0.0, 0.0, 0.0])

        mock_llm_client.generate_embedding.side_effect = mock_generate

        # Refresh all scene embeddings
        count = await embedding_manager.refresh_embeddings(
            entity_type="scene", model="new-model", force=True
        )

        assert count == 2

        # Verify embeddings were updated
        updated = embedding_manager.get_embedding("scene", "s1", "new-model")
        assert updated == pytest.approx([0.11, 0.21, 0.31], abs=1e-6)

    @pytest.mark.asyncio
    async def test_refresh_embeddings_specific_entities(
        self, embedding_manager, mock_llm_client
    ):
        """Test refreshing specific entity embeddings."""
        # Store embeddings
        for i in range(5):
            embedding_manager.store_embedding(
                "scene", f"s{i}", f"Scene {i}", [0.1 * i, 0.2 * i, 0.3 * i], "model"
            )

        mock_llm_client.generate_embedding.return_value = [1.0, 1.0, 1.0]

        # Refresh only specific entities
        count = await embedding_manager.refresh_embeddings(
            entity_ids=["s1", "s3"], model="model", force=True
        )

        assert count == 2
        assert mock_llm_client.generate_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_embeddings_no_force(self, embedding_manager):
        """Test refresh without force only updates old embeddings."""
        # This test would require mocking time or database dates
        # For now, just verify the parameter is handled
        count = await embedding_manager.refresh_embeddings(
            entity_type="scene", force=False
        )
        # Without old embeddings, nothing to refresh
        assert count == 0

    @pytest.mark.asyncio
    async def test_close_manager(self, embedding_manager, mock_llm_client):
        """Test closing the embedding manager."""
        await embedding_manager.close()
        mock_llm_client.close.assert_called_once()

    def test_store_embedding_transaction_rollback(
        self, embedding_manager, db_connection
    ):
        """Test that embedding storage is transactional."""
        entity_id = "test_transaction"

        try:
            with db_connection.transaction():
                embedding_manager.store_embedding(
                    "scene", entity_id, "Content", [0.1, 0.2, 0.3], "model"
                )
                # Force error
                raise ValueError("Rollback test")
        except ValueError:
            pass

        # Embedding should not be stored due to rollback
        result = embedding_manager.get_embedding("scene", entity_id, "model")
        assert result is None
