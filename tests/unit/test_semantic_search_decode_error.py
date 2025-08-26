"""Test error handling for embedding decode errors in semantic search."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scriptrag.api.semantic_search import SemanticSearchService
from scriptrag.config import ScriptRAGSettings


class TestSemanticSearchDecodeError:
    """Test handling of embedding decode errors in semantic search."""

    @pytest.fixture
    def semantic_search_service(self, tmp_path: Path) -> SemanticSearchService:
        """Create a semantic search service for testing."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        return SemanticSearchService(settings)

    @pytest.mark.asyncio
    @patch("scriptrag.api.semantic_search.logger")
    async def test_find_related_scenes_handles_decode_error(
        self,
        mock_logger: Mock,
        semantic_search_service: SemanticSearchService,
    ) -> None:
        """Test that find_related_scenes handles decode errors gracefully."""
        # Mock the database operations
        with patch.object(semantic_search_service, "db_ops") as mock_db_ops:
            mock_conn = Mock(spec=object)
            mock_db_ops.transaction.return_value.__enter__ = Mock(
                return_value=mock_conn
            )
            mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

            # Mock getting source embedding that will fail to decode
            mock_db_ops.get_embedding.return_value = b"corrupted_data"

            # Mock embedding service to raise ValueError on decode
            with patch.object(
                semantic_search_service, "embedding_service"
            ) as mock_embedding_service:
                mock_embedding_service.decode_embedding_from_db.side_effect = (
                    ValueError(
                        "Embedding data too short: expected at least 4 bytes, got 3"
                    )
                )

                # Call the method
                results = await semantic_search_service.find_related_scenes(
                    scene_id=123,
                    threshold=0.7,
                    top_k=10,
                )

                # Should return empty list
                assert results == []

                # Should log a warning
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert "Failed to decode source scene embedding" in call_args[0][0]
                assert call_args[1]["scene_id"] == 123
                assert "Embedding data too short" in call_args[1]["error"]

    @pytest.mark.asyncio
    @patch("scriptrag.api.semantic_search.logger")
    async def test_find_related_scenes_with_valid_then_corrupted(
        self,
        mock_logger: Mock,
        semantic_search_service: SemanticSearchService,
    ) -> None:
        """Test handling when source is valid but candidate embeddings are corrupted."""
        with patch.object(semantic_search_service, "db_ops") as mock_db_ops:
            mock_conn = Mock(spec=object)
            mock_db_ops.transaction.return_value.__enter__ = Mock(
                return_value=mock_conn
            )
            mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

            # Mock getting valid source embedding
            valid_embedding_bytes = (
                b"\x03\x00\x00\x00" + b"\x00\x00\x80\x3f" * 3
            )  # [1.0, 1.0, 1.0]
            mock_db_ops.get_embedding.return_value = valid_embedding_bytes

            # Mock embedding service
            with patch.object(
                semantic_search_service, "embedding_service"
            ) as mock_embedding_service:
                # First decode (source) succeeds
                mock_embedding_service.decode_embedding_from_db.side_effect = [
                    [1.0, 1.0, 1.0],  # Source decodes successfully
                    ValueError("Corrupted candidate"),  # First candidate fails
                    [0.9, 0.9, 0.9],  # Second candidate succeeds
                ]
                mock_embedding_service.default_model = "test-model"

                mock_embedding_service.cosine_similarity.return_value = 0.95

                # Mock search results with two candidates
                mock_db_ops.search_similar_scenes.return_value = [
                    {
                        "id": 1,
                        "script_id": 100,
                        "heading": "Corrupted Scene",
                        "content": "This will fail",
                        "_embedding": b"bad_data",
                    },
                    {
                        "id": 2,
                        "script_id": 100,
                        "heading": "Valid Scene",
                        "content": "This will work",
                        "_embedding": b"good_data",
                    },
                ]

                # Call the method
                results = await semantic_search_service.find_related_scenes(
                    scene_id=123,
                    threshold=0.7,
                    top_k=10,
                )

                # Should have one result (the valid one)
                assert len(results) == 1
                assert results[0].scene_id == 2
                assert results[0].heading == "Valid Scene"
                assert results[0].similarity_score == 0.95

    @pytest.mark.asyncio
    async def test_integration_with_real_embedding_service(
        self,
        semantic_search_service: SemanticSearchService,
    ) -> None:
        """Test integration with real embedding service decode validation."""
        # Create a truly corrupted embedding
        corrupted_bytes = b"\xff\xff"  # Too short to be valid

        with patch.object(semantic_search_service.db_ops, "transaction") as mock_trans:
            mock_conn = Mock(spec=object)
            mock_trans.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = Mock(return_value=None)

            with patch.object(
                semantic_search_service.db_ops, "get_embedding"
            ) as mock_get_embedding:
                mock_get_embedding.return_value = corrupted_bytes

                # This should not raise an exception but return empty results
                results = await semantic_search_service.find_related_scenes(
                    scene_id=456,
                    threshold=0.5,
                )

                assert results == []
