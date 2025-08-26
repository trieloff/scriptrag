"""Test error handling in semantic result processing."""

from typing import Any
from unittest.mock import Mock

from scriptrag.api.semantic_result_processing import (
    build_bible_results,
    build_scene_results,
)


class TestSemanticResultErrorHandling:
    """Test error handling in semantic result processing functions."""

    def test_build_scene_results_skips_corrupted_embeddings(self) -> None:
        """Test that scenes with corrupted embeddings are skipped."""
        # Mock embedding service
        mock_embedding_service = Mock(spec=object)

        # First call raises ValueError (corrupted), second succeeds
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            ValueError("Corrupted embedding"),
            [0.1, 0.2, 0.3],  # Valid embedding for second scene
        ]
        mock_embedding_service.cosine_similarity.return_value = 0.8

        # Mock builder
        def builder(**kwargs: Any) -> dict[str, Any]:
            return {"similarity_score": kwargs["similarity_score"], **kwargs}

        # Test data with two scenes
        candidates = [
            {
                "id": 1,
                "script_id": 100,
                "heading": "Scene 1",
                "location": "INT. HOUSE",
                "content": "Content 1",
                "_embedding": b"corrupted_data",
                "metadata": {},
            },
            {
                "id": 2,
                "script_id": 100,
                "heading": "Scene 2",
                "location": "EXT. STREET",
                "content": "Content 2",
                "_embedding": b"valid_data",
                "metadata": {},
            },
        ]

        query_embedding = [0.4, 0.5, 0.6]

        # Build results
        results = build_scene_results(
            candidates,
            query_embedding=query_embedding,
            embedding_service=mock_embedding_service,
            threshold=0.5,
            builder=builder,
        )

        # Should only have one result (the valid one)
        assert len(results) == 1
        assert results[0]["scene_id"] == 2
        assert results[0]["heading"] == "Scene 2"

    def test_build_scene_results_handles_missing_embedding_key(self) -> None:
        """Test that scenes missing embedding key are skipped."""
        mock_embedding_service = Mock(spec=object)
        mock_embedding_service.decode_embedding_from_db.side_effect = KeyError(
            "_embedding"
        )

        def builder(**kwargs: Any) -> dict[str, Any]:
            return {"similarity_score": kwargs["similarity_score"], **kwargs}

        # Scene missing _embedding key will be handled
        candidates = [
            {
                "id": 1,
                "script_id": 100,
                "heading": "Scene 1",
                "content": "Content 1",
                "_embedding": b"data",  # Will raise KeyError in mock
            }
        ]

        results = build_scene_results(
            candidates,
            query_embedding=[0.1, 0.2],
            embedding_service=mock_embedding_service,
            threshold=0.5,
            builder=builder,
        )

        # Should have no results
        assert len(results) == 0

    def test_build_bible_results_skips_corrupted_embeddings(self) -> None:
        """Test that bible chunks with corrupted embeddings are skipped."""
        mock_embedding_service = Mock(spec=object)

        # First call raises ValueError, second and third succeed
        mock_embedding_service.decode_embedding_from_db.side_effect = [
            ValueError("Corrupted embedding"),
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
        mock_embedding_service.cosine_similarity.side_effect = [0.9, 0.6]

        def builder(**kwargs: Any) -> dict[str, Any]:
            return {"similarity_score": kwargs["similarity_score"], **kwargs}

        chunks = [
            {
                "id": 1,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "Bible 1",
                "heading": "Chapter 1",
                "content": "Content 1",
                "embedding": b"corrupted",
                "level": 1,
                "metadata": {},
            },
            {
                "id": 2,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "Bible 1",
                "heading": "Chapter 2",
                "content": "Content 2",
                "embedding": b"valid1",
                "level": 1,
                "metadata": {},
            },
            {
                "id": 3,
                "bible_id": 10,
                "script_id": 100,
                "bible_title": "Bible 1",
                "heading": "Chapter 3",
                "content": "Content 3",
                "embedding": b"valid2",
                "level": 1,
                "metadata": {},
            },
        ]

        results = build_bible_results(
            chunks,
            query_embedding=[0.7, 0.8, 0.9],
            embedding_service=mock_embedding_service,
            threshold=0.5,
            builder=builder,
        )

        # Should have two results (the valid ones)
        assert len(results) == 2
        # Results should be sorted by similarity score (descending)
        assert results[0]["chunk_id"] == 2  # similarity 0.9
        assert results[1]["chunk_id"] == 3  # similarity 0.6

    def test_build_scene_results_with_skip_id(self) -> None:
        """Test that skip_id parameter works correctly even with errors."""
        mock_embedding_service = Mock(spec=object)

        # Only called once (scene 2 is skipped)
        mock_embedding_service.decode_embedding_from_db.return_value = [0.1, 0.2, 0.3]
        mock_embedding_service.cosine_similarity.return_value = 0.8

        def builder(**kwargs: Any) -> dict[str, Any]:
            return {"similarity_score": kwargs["similarity_score"], **kwargs}

        candidates = [
            {
                "id": 1,
                "script_id": 100,
                "heading": "Scene 1",
                "content": "Content 1",
                "_embedding": b"data1",
            },
            {
                "id": 2,  # This will be skipped
                "script_id": 100,
                "heading": "Scene 2",
                "content": "Content 2",
                "_embedding": b"data2",
            },
        ]

        results = build_scene_results(
            candidates,
            query_embedding=[0.4, 0.5, 0.6],
            embedding_service=mock_embedding_service,
            threshold=0.5,
            builder=builder,
            skip_id=2,  # Skip scene with id=2
        )

        # Should only have scene 1
        assert len(results) == 1
        assert results[0]["scene_id"] == 1

    def test_build_results_all_corrupted(self) -> None:
        """Test that empty list is returned when all embeddings are corrupted."""
        mock_embedding_service = Mock(spec=object)
        mock_embedding_service.decode_embedding_from_db.side_effect = ValueError(
            "All corrupted"
        )

        def builder(**kwargs: Any) -> dict[str, Any]:
            return kwargs

        candidates = [
            {
                "id": i,
                "script_id": 100,
                "heading": f"Scene {i}",
                "content": f"Content {i}",
                "_embedding": b"bad",
            }
            for i in range(5)
        ]

        results = build_scene_results(
            candidates,
            query_embedding=[0.1, 0.2],
            embedding_service=mock_embedding_service,
            threshold=0.5,
            builder=builder,
        )

        assert results == []
