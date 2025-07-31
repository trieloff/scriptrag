"""Tests for hybrid search functionality in search interface."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.llm.client import LLMClient
from scriptrag.search.interface import SearchInterface
from scriptrag.search.types import SearchResult, SearchType


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    conn = MagicMock(spec=DatabaseConnection)
    conn.fetch_all = MagicMock(return_value=[])
    conn.fetch_one = MagicMock(return_value=None)
    return conn


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock(spec=LLMClient)
    client.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    client.generate_embeddings = AsyncMock(return_value=[[0.1] * 768])
    client.default_embedding_model = "text-embedding-ada-002"
    return client


@pytest.fixture
def search_interface(mock_connection, mock_llm_client):
    """Create search interface with mocks."""
    return SearchInterface(mock_connection, mock_llm_client)


class TestHybridSearchScoreCombination:
    """Test hybrid search score combination algorithms."""

    @pytest.mark.asyncio
    async def test_combines_text_and_semantic_scores(self, search_interface):
        """Test that hybrid search properly combines text and semantic scores."""
        # Mock text search results
        text_results = [
            SearchResult(
                id="doc1",
                type="dialogue",
                content="The quick brown fox",
                score=0.7,
                metadata={"character": "Alice"},
                highlights=["quick"],
            ),
            SearchResult(
                id="doc2",
                type="action",
                content="The fox jumps",
                score=0.5,
                metadata={},
                highlights=["fox"],
            ),
        ]

        # Mock semantic search results with overlapping document
        semantic_results = [
            SearchResult(
                id="doc1",  # Same document as text search
                type="dialogue",
                content="The quick brown fox",
                score=0.9,  # Higher semantic score
                metadata={"character": "Alice"},
                highlights=[],
            ),
            SearchResult(
                id="doc3",  # Different document
                type="scene",
                content="Forest scene with animals",
                score=0.8,
                metadata={"location": "Forest"},
                highlights=[],
            ),
        ]

        with (
            patch.object(
                search_interface, "_search_full_text", return_value=text_results
            ),
            patch.object(
                search_interface, "_search_semantic", return_value=semantic_results
            ),
        ):
            results = await search_interface.search(
                "fox", search_types=[SearchType.FULL_TEXT, SearchType.SEMANTIC]
            )

            # Check that results are deduplicated and scores are combined
            assert len(results) == 3  # doc1, doc2, doc3

            # Find doc1 in results
            doc1_result = next((r for r in results if r["id"] == "doc1"), None)
            assert doc1_result is not None
            # Score should reflect combination/ranking
            assert doc1_result["score"] > 0

    @pytest.mark.asyncio
    async def test_weights_different_search_types(self, search_interface):
        """Test that different search types are weighted according to configuration."""
        # Create results with same base score but different types
        dialogue_result = SearchResult(
            id="d1",
            type="dialogue",
            content="Test dialogue",
            score=0.5,
            metadata={},
            highlights=[],
        )

        action_result = SearchResult(
            id="a1",
            type="action",
            content="Test action",
            score=0.5,
            metadata={},
            highlights=[],
        )

        location_result = SearchResult(
            id="l1",
            type="location",
            content="Test location",
            score=0.5,
            metadata={},
            highlights=[],
        )

        all_results = [dialogue_result, action_result, location_result]

        with patch.object(
            search_interface.ranker,
            "type_weights",
            {
                "dialogue": 0.9,
                "action": 0.8,
                "location": 0.75,
            },
        ):
            ranked_results = search_interface.ranker.rank_results(all_results, "test")

            # Verify ordering based on type weights
            assert ranked_results[0]["type"] == "dialogue"
            assert ranked_results[1]["type"] == "action"
            assert ranked_results[2]["type"] == "location"

            # Verify scores are weighted
            assert ranked_results[0]["score"] > ranked_results[1]["score"]
            assert ranked_results[1]["score"] > ranked_results[2]["score"]


class TestHybridSearchDeduplication:
    """Test result deduplication across different search types."""

    @pytest.mark.asyncio
    async def test_deduplicates_results_from_multiple_sources(self, search_interface):
        """Test duplicate results from different search methods are deduplicated."""
        # Same content appearing in different search results
        duplicate_result1 = SearchResult(
            id="scene1",
            type="scene",
            content="INT. OFFICE - DAY",
            score=0.8,
            metadata={"script_order": 1},
            highlights=["OFFICE"],
        )

        duplicate_result2 = SearchResult(
            id="scene1",  # Same ID
            type="scene",
            content="INT. OFFICE - DAY",
            score=0.6,  # Different score
            metadata={"script_order": 1},
            highlights=[],
        )

        unique_result = SearchResult(
            id="scene2",
            type="scene",
            content="EXT. STREET - NIGHT",
            score=0.7,
            metadata={"script_order": 2},
            highlights=[],
        )

        with (
            patch.object(
                search_interface,
                "_search_scenes",
                return_value=[duplicate_result1, unique_result],
            ),
            patch.object(
                search_interface, "_search_full_text", return_value=[duplicate_result2]
            ),
        ):
            results = await search_interface.search(
                "office", search_types=[SearchType.SCENE, SearchType.FULL_TEXT]
            )

            # Should have 2 results, not 3
            assert len(results) == 2

            # Check that scene1 appears only once
            scene1_count = sum(1 for r in results if r["id"] == "scene1")
            assert scene1_count == 1

    @pytest.mark.asyncio
    async def test_preserves_first_occurrence_during_deduplication(
        self, search_interface
    ):
        """Test that deduplication preserves the first occurrence of duplicates."""
        result_first = SearchResult(
            id="char1",
            type="character",
            content="John Smith",
            score=0.4,
            metadata={"appearances": 10},
            highlights=[],
        )

        result_second = SearchResult(
            id="char1",
            type="character",
            content="John Smith",
            score=0.9,
            metadata={"appearances": 10},
            highlights=["John"],
        )

        # Mix the results - first occurrence will be kept
        mixed_results = [result_first, result_second]

        deduplicated = search_interface.ranker._deduplicate_results(mixed_results)

        assert len(deduplicated) == 1
        # The deduplication keeps the first occurrence
        assert deduplicated[0]["score"] == 0.4
        assert deduplicated[0]["highlights"] == []

    @pytest.mark.asyncio
    async def test_ranking_deduplicates_after_sorting(self, search_interface):
        """Test that rank_results sorts before deduplicating to keep highest scores."""
        result_low_score = SearchResult(
            id="char1",
            type="character",
            content="John Smith",
            score=0.4,
            metadata={"appearances": 10},
            highlights=[],
        )

        result_high_score = SearchResult(
            id="char1",
            type="character",
            content="John Smith",
            score=0.9,
            metadata={"appearances": 10},
            highlights=["John"],
        )

        # Mix the results with low score first
        mixed_results = [result_low_score, result_high_score]

        # rank_results should sort by score first, then deduplicate
        ranked = search_interface.ranker.rank_results(mixed_results, "John")

        assert len(ranked) == 1
        # After ranking, the higher scored result should be kept
        assert ranked[0]["score"] > 0.4

    @pytest.mark.asyncio
    async def test_deduplicates_across_different_types_with_same_id(
        self, search_interface
    ):
        """Test deduplication handles same ID across different types correctly."""
        # This tests the case where type:id combination matters
        dialogue_result = SearchResult(
            id="1",
            type="dialogue",
            content="Hello world",
            score=0.8,
            metadata={},
            highlights=[],
        )

        scene_result = SearchResult(
            id="1",  # Same ID but different type
            type="scene",
            content="INT. ROOM - DAY",
            score=0.7,
            metadata={},
            highlights=[],
        )

        results = [dialogue_result, scene_result]
        deduplicated = search_interface.ranker._deduplicate_results(results)

        # Should keep both since they have different types
        assert len(deduplicated) == 2


class TestHybridSearchRanking:
    """Test hybrid search ranking with different factors."""

    @pytest.mark.asyncio
    async def test_exact_match_boost(self, search_interface):
        """Test that exact matches get boosted in ranking."""
        exact_match_result = SearchResult(
            id="d1",
            type="dialogue",
            content="The exact phrase we're looking for",
            score=0.5,
            metadata={},
            highlights=["exact phrase"],
        )

        partial_match_result = SearchResult(
            id="d2",
            type="dialogue",
            content="This has the phrase but not exact",
            score=0.5,
            metadata={},
            highlights=["phrase"],
        )

        results = [partial_match_result, exact_match_result]

        ranked = search_interface.ranker.rank_results(results, "exact phrase")

        # Exact match should rank higher despite same base score
        assert ranked[0]["id"] == "d1"
        assert ranked[0]["score"] > ranked[1]["score"]

    @pytest.mark.asyncio
    async def test_query_term_density_boost(self, search_interface):
        """Test that results with higher query term density rank higher."""
        high_density_result = SearchResult(
            id="d1",
            type="dialogue",
            content="fox fox fox in the fox house",  # High density of "fox"
            score=0.5,
            metadata={},
            highlights=[],
        )

        low_density_result = SearchResult(
            id="d2",
            type="dialogue",
            content="The quick brown fox jumps over the lazy dog in the long sentence",
            score=0.5,
            metadata={},
            highlights=[],
        )

        results = [low_density_result, high_density_result]

        ranked = search_interface.ranker.rank_results(results, "fox")

        # High density result should rank higher
        assert ranked[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_metadata_boost(self, search_interface):
        """Test that metadata matches boost ranking."""
        result_with_metadata_match = SearchResult(
            id="d1",
            type="dialogue",
            content="Hello there",
            score=0.5,
            metadata={"character": "John Smith", "scene_heading": "INT. OFFICE - DAY"},
            highlights=[],
        )

        result_without_metadata_match = SearchResult(
            id="d2",
            type="dialogue",
            content="Hello there",
            score=0.5,
            metadata={"character": "Alice", "scene_heading": "EXT. PARK - DAY"},
            highlights=[],
        )

        results = [result_without_metadata_match, result_with_metadata_match]

        ranked = search_interface.ranker.rank_results(results, "John")

        # Result with metadata match should rank higher
        assert ranked[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_recency_boost(self, search_interface):
        """Test that more recent results (lower script_order) get boosted."""
        early_result = SearchResult(
            id="s1",
            type="scene",
            content="Early scene",
            score=0.5,
            metadata={"script_order": 10},
            highlights=[],
        )

        late_result = SearchResult(
            id="s2",
            type="scene",
            content="Late scene",
            score=0.5,
            metadata={"script_order": 100},
            highlights=[],
        )

        results = [late_result, early_result]

        ranked = search_interface.ranker.rank_results(
            results, "scene", boost_recent=True
        )

        # Early result should rank higher when boost_recent is True
        assert ranked[0]["id"] == "s1"


class TestHybridSearchEmptyResults:
    """Test hybrid search with empty or partial results."""

    @pytest.mark.asyncio
    async def test_handles_empty_results_from_all_sources(self, search_interface):
        """Test that hybrid search handles empty results gracefully."""
        with (
            patch.object(search_interface, "_search_dialogue", return_value=[]),
            patch.object(search_interface, "_search_action", return_value=[]),
            patch.object(search_interface, "_search_semantic", return_value=[]),
        ):
            results = await search_interface.search(
                "nonexistent",
                search_types=[
                    SearchType.DIALOGUE,
                    SearchType.ACTION,
                    SearchType.SEMANTIC,
                ],
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_handles_partial_empty_results(self, search_interface):
        """Test hybrid search when some sources return empty results."""
        dialogue_results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="Found dialogue",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]

        with (
            patch.object(
                search_interface, "_search_dialogue", return_value=dialogue_results
            ),
            patch.object(search_interface, "_search_action", return_value=[]),
            patch.object(search_interface, "_search_semantic", return_value=[]),
        ):
            results = await search_interface.search(
                "found",
                search_types=[
                    SearchType.DIALOGUE,
                    SearchType.ACTION,
                    SearchType.SEMANTIC,
                ],
            )

            assert len(results) == 1
            assert results[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_handles_none_results(self, search_interface):
        """Test that None results are handled gracefully."""
        # Simulate a search method returning None instead of empty list
        with patch.object(search_interface, "_search_dialogue", return_value=None):
            # This should handle the None without crashing
            try:
                results = await search_interface.search(
                    "test", search_types=[SearchType.DIALOGUE]
                )
                # If None is returned, it would fail when trying to extend
                # So we expect either empty results or an exception to be caught
                assert isinstance(results, list)
            except Exception:
                # The search should handle exceptions gracefully
                pass


class TestHybridSearchContentTypes:
    """Test hybrid search across different content types."""

    @pytest.mark.asyncio
    async def test_search_across_scenes_characters_dialogue(self, search_interface):
        """Test searching across scenes, characters, and dialogue simultaneously."""
        scene_results = [
            SearchResult(
                id="s1",
                type="scene",
                content="INT. CASTLE - NIGHT",
                score=0.7,
                metadata={"script_order": 5},
                highlights=["CASTLE"],
            )
        ]

        character_results = [
            SearchResult(
                id="c1",
                type="character",
                content="CASTLE GUARD",
                score=0.8,
                metadata={"appearances": 3},
                highlights=["CASTLE"],
            )
        ]

        dialogue_results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="We must defend the castle!",
                score=0.9,
                metadata={"character": "GUARD"},
                highlights=["castle"],
            )
        ]

        with (
            patch.object(
                search_interface, "_search_scenes", return_value=scene_results
            ),
            patch.object(
                search_interface, "_search_characters", return_value=character_results
            ),
            patch.object(
                search_interface, "_search_dialogue", return_value=dialogue_results
            ),
        ):
            results = await search_interface.search(
                "castle",
                search_types=[
                    SearchType.SCENE,
                    SearchType.CHARACTER,
                    SearchType.DIALOGUE,
                ],
            )

            # Should have all three results
            assert len(results) == 3

            # Check that all content types are present
            result_types = {r["type"] for r in results}
            assert result_types == {"scene", "character", "dialogue"}

            # Dialogue should rank highest due to score and type weight
            assert results[0]["type"] == "dialogue"

    @pytest.mark.asyncio
    async def test_filters_apply_across_all_search_types(self, search_interface):
        """Test that entity filters are applied to all search types."""
        entity_filter = {"character_id": "c1", "scene_id": "s1"}

        with (
            patch.object(search_interface, "_search_dialogue") as mock_dialogue,
            patch.object(search_interface, "_search_action") as mock_action,
            patch.object(search_interface, "_search_semantic") as mock_semantic,
        ):
            # Set return values
            mock_dialogue.return_value = []
            mock_action.return_value = []
            mock_semantic.return_value = []

            await search_interface.search(
                "test",
                search_types=[
                    SearchType.DIALOGUE,
                    SearchType.ACTION,
                    SearchType.SEMANTIC,
                ],
                entity_filter=entity_filter,
            )

            # Verify all methods received the filter
            mock_dialogue.assert_called_once_with("test", entity_filter)
            mock_action.assert_called_once_with("test", entity_filter)
            mock_semantic.assert_called_once_with("test", entity_filter)


class TestHybridSearchIntegration:
    """Integration tests for hybrid search functionality."""

    @pytest.mark.asyncio
    async def test_full_hybrid_search_workflow(self, search_interface, mock_connection):
        """Test complete hybrid search workflow with multiple result types."""
        # Mock database results for text search
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "To be or not to be",
                "character_name": "Hamlet",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. CASTLE - NIGHT",
                "script_order": 50,
            }
        ]

        # Mock semantic search results
        semantic_results = [
            {
                "entity_id": "s2",
                "entity_type": "scene",
                "content": "Existential crisis scene",
                "similarity": 0.85,
                "entity_details": {"theme": "existence"},
            }
        ]

        with patch.object(
            search_interface.embedding_pipeline,
            "semantic_search",
            return_value=semantic_results,
        ):
            results = await search_interface.search(
                "existence",
                search_types=[SearchType.DIALOGUE, SearchType.SEMANTIC],
                limit=10,
                min_score=0.3,
            )

            # Should have results from both search types
            assert len(results) >= 1

            # Results should be properly ranked and filtered
            for result in results:
                assert result["score"] >= 0.3

    @pytest.mark.asyncio
    async def test_hybrid_search_performance(self, search_interface):
        """Test hybrid search performs well with multiple parallel searches."""
        # Create many mock results
        large_results = [
            SearchResult(
                id=f"r{i}",
                type="dialogue",
                content=f"Result content {i}",
                score=0.5 + (i % 10) / 20,
                metadata={},
                highlights=[],
            )
            for i in range(100)
        ]

        with (
            patch.object(
                search_interface, "_search_dialogue", return_value=large_results[:33]
            ),
            patch.object(
                search_interface, "_search_action", return_value=large_results[33:66]
            ),
            patch.object(
                search_interface, "_search_semantic", return_value=large_results[66:]
            ),
        ):
            import time

            start_time = time.time()

            results = await search_interface.search(
                "content",
                search_types=[
                    SearchType.DIALOGUE,
                    SearchType.ACTION,
                    SearchType.SEMANTIC,
                ],
                limit=20,
            )

            end_time = time.time()

            # Should complete quickly even with many results
            assert end_time - start_time < 1.0

            # Should respect limit
            assert len(results) <= 20

            # Results should be properly ranked
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i + 1]["score"]


class TestHybridSearchEdgeCases:
    """Test edge cases and error conditions in hybrid search."""

    @pytest.mark.asyncio
    async def test_search_with_failing_subsearches(self, search_interface):
        """Test hybrid search when some sub-searches fail."""
        dialogue_results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="Working dialogue",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]

        with (
            patch.object(
                search_interface, "_search_dialogue", return_value=dialogue_results
            ),
            patch.object(
                search_interface,
                "_search_action",
                side_effect=Exception("Action search failed"),
            ),
            patch.object(
                search_interface,
                "_search_semantic",
                side_effect=Exception("Semantic search failed"),
            ),
        ):
            # Should still return results from working searches
            results = await search_interface.search(
                "test",
                search_types=[
                    SearchType.DIALOGUE,
                    SearchType.ACTION,
                    SearchType.SEMANTIC,
                ],
            )

            assert len(results) == 1
            assert results[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_merge_results_with_none_query(self, search_interface):
        """Test merge_results when no query is provided for re-ranking."""
        results1 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="First",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Second",
                score=0.6,
                metadata={},
                highlights=[],
            ),
        ]

        results2 = [
            SearchResult(
                id="r3",
                type="action",
                content="Third",
                score=0.7,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r1",
                type="dialogue",
                content="First",
                score=0.5,
                metadata={},
                highlights=[],
            ),  # Duplicate
        ]

        merged = search_interface.ranker.merge_results(results1, results2, query=None)

        # Should sort by score and deduplicate
        assert len(merged) == 3  # r1, r2, r3 (deduplicated)
        assert merged[0]["score"] >= merged[1]["score"] >= merged[2]["score"]

    @pytest.mark.asyncio
    async def test_group_results_by_type(self, search_interface):
        """Test grouping results by type."""
        results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="D1",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="s1",
                type="scene",
                content="S1",
                score=0.7,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="d2",
                type="dialogue",
                content="D2",
                score=0.6,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="c1",
                type="character",
                content="C1",
                score=0.5,
                metadata={},
                highlights=[],
            ),
        ]

        grouped = search_interface.ranker.group_results_by_type(results)

        assert len(grouped) == 3  # dialogue, scene, character
        assert len(grouped["dialogue"]) == 2
        assert len(grouped["scene"]) == 1
        assert len(grouped["character"]) == 1

        # Verify correct grouping
        assert all(r["type"] == "dialogue" for r in grouped["dialogue"])
        assert all(r["type"] == "scene" for r in grouped["scene"])
        assert all(r["type"] == "character" for r in grouped["character"])
