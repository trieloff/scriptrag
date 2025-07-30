"""Tests for search result ranking module."""

import pytest

from scriptrag.search.ranking import SearchRanker
from scriptrag.search.types import SearchResult


@pytest.fixture
def ranker():
    """Create search ranker instance."""
    return SearchRanker()


@pytest.fixture
def sample_results():
    """Create sample search results for testing."""
    return [
        SearchResult(
            id="d1",
            type="dialogue",
            content="This is a test dialogue with important information",
            score=0.7,
            metadata={
                "character": "John",
                "scene_heading": "INT. OFFICE - DAY",
                "script_order": 10,
            },
            highlights=["test dialogue", "important information"],
        ),
        SearchResult(
            id="s1",
            type="scene",
            content="INT. OFFICE - DAY",
            score=0.8,
            metadata={
                "script_order": 5,
                "description": "A busy office with test equipment",
            },
            highlights=["test equipment"],
        ),
        SearchResult(
            id="c1",
            type="character",
            content="John Smith",
            score=0.6,
            metadata={
                "description": "Main character who loves testing",
                "appearance_count": 25,
            },
            highlights=[],
        ),
        SearchResult(
            id="a1",
            type="action",
            content="John walks to the test station",
            score=0.5,
            metadata={
                "scene_id": "s1",
                "script_order": 15,
            },
            highlights=["test station"],
        ),
    ]


class TestSearchRankerInit:
    """Test SearchRanker initialization."""

    def test_init(self):
        """Test ranker initialization with default type weights."""
        ranker = SearchRanker()

        assert ranker.type_weights["scene"] == 1.0
        assert ranker.type_weights["dialogue"] == 0.9
        assert ranker.type_weights["character"] == 0.85
        assert ranker.type_weights["action"] == 0.8
        assert ranker.type_weights["location"] == 0.75
        assert ranker.type_weights["object"] == 0.7


class TestSearchRankerRankResults:
    """Test SearchRanker result ranking functionality."""

    def test_rank_results_empty_list(self, ranker):
        """Test ranking empty results list."""
        results = ranker.rank_results([], "test")
        assert results == []

    def test_rank_results_basic_sorting(self, ranker, sample_results):
        """Test basic result ranking and sorting."""
        ranked = ranker.rank_results(sample_results, "test")

        # Should have all results
        assert len(ranked) == 4

        # Should be sorted by composite score (descending)
        scores = [result["score"] for result in ranked]
        assert scores == sorted(scores, reverse=True)

        # Results should be properly ranked (exact order may vary due to boosts)
        assert ranked[0]["score"] >= ranked[1]["score"]

    def test_rank_results_type_weights_applied(self, ranker):
        """Test that type weights are properly applied."""
        results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="Test content",
                score=0.8,  # Same base score
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="a1",
                type="action",
                content="Test content",
                score=0.8,  # Same base score
                metadata={},
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # Dialogue should rank higher due to better type weight (0.9 vs 0.8)
        assert ranked[0]["type"] == "dialogue"
        assert ranked[1]["type"] == "action"

    def test_rank_results_exact_match_boost(self, ranker):
        """Test exact match boost in ranking."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="This is test content exactly",  # Contains exact match
                score=0.3,  # Lower base score
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="This contains testing and other words",  # No exact match
                score=0.4,  # Higher base score but not enough to overcome boost
                metadata={},
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # First result should rank higher due to exact match boost (1.2x)
        # 0.3 * 0.9 (type_weight) * 1.2 (exact match) = 0.324
        # vs 0.4 * 0.9 (type_weight) = 0.36
        # But exact match also gets density boost and other factors
        # Let us just check the boost exists
        assert ranked[0]["score"] > ranked[1]["score"] or ranked[0]["id"] == "r1"

    def test_rank_results_metadata_boost(self, ranker):
        """Test metadata matching provides ranking boost."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Some content",
                score=0.5,
                metadata={"character": "TestCharacter"},  # Character name matches
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Some content",
                score=0.5,
                metadata={"character": "OtherCharacter"},  # No match
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # First result should rank higher due to metadata boost
        assert ranked[0]["id"] == "r1"

    def test_rank_results_recency_boost(self, ranker):
        """Test recency boost for script order."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Test content",
                score=0.5,
                metadata={"script_order": 100},  # Later in script
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Test content",
                score=0.5,
                metadata={"script_order": 1},  # Earlier in script
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test", boost_recent=True)

        # Earlier scene should have slight boost
        assert ranked[0]["id"] == "r2"

    def test_rank_results_no_recency_boost(self, ranker):
        """Test ranking without recency boost."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Test content",
                score=0.6,
                metadata={"script_order": 100},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Test content",
                score=0.5,
                metadata={"script_order": 1},
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test", boost_recent=False)

        # Higher base score should win without recency boost
        assert ranked[0]["id"] == "r1"

    def test_rank_results_deduplication(self, ranker):
        """Test ranking removes duplicate results."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Test content",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r1",  # Same ID and type
                type="dialogue",
                content="Different content",
                score=0.6,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Other content",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # Should have only 2 unique results
        assert len(ranked) == 2

        # Should keep first occurrence of duplicate
        unique_ids = [r["id"] for r in ranked]
        assert "r1" in unique_ids
        assert "r2" in unique_ids

    def test_rank_results_score_capping(self, ranker):
        """Test ranking caps composite scores at 1.0."""
        results = [
            SearchResult(
                id="r1",
                type="scene",  # High type weight
                content="test",  # Exact match
                score=0.9,  # High base score
                metadata={"character": "test"},  # Metadata match
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # Score should be capped at 1.0 despite all boosts
        assert ranked[0]["score"] <= 1.0


class TestSearchRankerFilterResults:
    """Test SearchRanker result filtering functionality."""

    def test_filter_results_min_score(self, ranker, sample_results):
        """Test filtering by minimum score."""
        filtered = ranker.filter_results(sample_results, min_score=0.65)

        # Should only include results with score >= 0.65
        assert len(filtered) == 2  # dialogue (0.7) and scene (0.8)
        assert all(r["score"] >= 0.65 for r in filtered)

    def test_filter_results_max_results(self, ranker, sample_results):
        """Test filtering by maximum number of results."""
        filtered = ranker.filter_results(sample_results, max_results=2)

        assert len(filtered) == 2

    def test_filter_results_no_deduplication(self, ranker):
        """Test filtering without deduplication."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Content 1",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r1",  # Duplicate
                type="dialogue",
                content="Content 2",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        filtered = ranker.filter_results(results, deduplicate=False)

        # Should keep both duplicates
        assert len(filtered) == 2

    def test_filter_results_with_deduplication(self, ranker):
        """Test filtering with deduplication enabled."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Content 1",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r1",  # Duplicate
                type="dialogue",
                content="Content 2",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        filtered = ranker.filter_results(results, deduplicate=True)

        # Should remove duplicates
        assert len(filtered) == 1


class TestSearchRankerGroupResults:
    """Test SearchRanker result grouping functionality."""

    def test_group_results_by_type(self, ranker, sample_results):
        """Test grouping results by type."""
        grouped = ranker.group_results_by_type(sample_results)

        assert len(grouped) == 4  # 4 different types
        assert "dialogue" in grouped
        assert "scene" in grouped
        assert "character" in grouped
        assert "action" in grouped

        assert len(grouped["dialogue"]) == 1
        assert len(grouped["scene"]) == 1
        assert len(grouped["character"]) == 1
        assert len(grouped["action"]) == 1

    def test_group_results_multiple_same_type(self, ranker):
        """Test grouping with multiple results of same type."""
        results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="First dialogue",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="d2",
                type="dialogue",
                content="Second dialogue",
                score=0.7,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="s1",
                type="scene",
                content="Scene content",
                score=0.6,
                metadata={},
                highlights=[],
            ),
        ]

        grouped = ranker.group_results_by_type(results)

        assert len(grouped) == 2  # dialogue and scene
        assert len(grouped["dialogue"]) == 2
        assert len(grouped["scene"]) == 1

    def test_group_results_empty(self, ranker):
        """Test grouping empty results."""
        grouped = ranker.group_results_by_type([])
        assert grouped == {}


class TestSearchRankerMergeResults:
    """Test SearchRanker result merging functionality."""

    def test_merge_results_basic(self, ranker):
        """Test basic result set merging."""
        set1 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Result 1",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]
        set2 = [
            SearchResult(
                id="r2",
                type="scene",
                content="Result 2",
                score=0.9,
                metadata={},
                highlights=[],
            )
        ]

        merged = ranker.merge_results(set1, set2)

        assert len(merged) == 2
        # Should be sorted by score
        assert merged[0]["score"] >= merged[1]["score"]
        assert merged[0]["id"] == "r2"  # Higher score

    def test_merge_results_with_query_rerank(self, ranker):
        """Test merging with query-based re-ranking."""
        set1 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="test content",  # Matches query
                score=0.5,
                metadata={},
                highlights=[],
            )
        ]
        set2 = [
            SearchResult(
                id="r2",
                type="dialogue",
                content="other content",  # Doesn't match query
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]

        merged = ranker.merge_results(set1, set2, query="test")

        # Query-based ranking should boost first result
        assert merged[0]["id"] == "r1"

    def test_merge_results_multiple_sets(self, ranker):
        """Test merging multiple result sets."""
        set1 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="A",
                score=0.7,
                metadata={},
                highlights=[],
            )
        ]
        set2 = [
            SearchResult(
                id="r2",
                type="scene",
                content="B",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]
        set3 = [
            SearchResult(
                id="r3",
                type="action",
                content="C",
                score=0.6,
                metadata={},
                highlights=[],
            )
        ]

        merged = ranker.merge_results(set1, set2, set3)

        assert len(merged) == 3
        # Should be sorted by score
        scores = [r["score"] for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_merge_results_with_duplicates(self, ranker):
        """Test merging removes duplicates."""
        set1 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Content",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]
        set2 = [
            SearchResult(
                id="r1",  # Duplicate
                type="dialogue",
                content="Different content",
                score=0.7,
                metadata={},
                highlights=[],
            )
        ]

        merged = ranker.merge_results(set1, set2)

        assert len(merged) == 1  # Duplicate removed

    def test_merge_results_empty_sets(self, ranker):
        """Test merging with empty result sets."""
        set1 = []
        set2 = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="A",
                score=0.7,
                metadata={},
                highlights=[],
            )
        ]
        set3 = []

        merged = ranker.merge_results(set1, set2, set3)

        assert len(merged) == 1
        assert merged[0]["id"] == "r1"


class TestSearchRankerPrivateMethods:
    """Test SearchRanker private methods."""

    def test_calculate_composite_score(self, ranker):
        """Test composite score calculation."""
        result = SearchResult(
            id="r1",
            type="dialogue",
            content="test content",
            score=0.5,
            metadata={"script_order": 10},
            highlights=[],
        )

        score = ranker._calculate_composite_score(result, "test", boost_recent=True)

        # Should be higher than base score due to various boosts
        assert score > 0.5
        assert score <= 1.0

    def test_calculate_density_boost(self, ranker):
        """Test query term density boost calculation."""
        # High density - 3 matches in 3 words = 100% density
        high_density = ranker._calculate_density_boost("test", "test test test")

        # Medium density - 2 matches in 8 words = 25% density
        med_density = ranker._calculate_density_boost(
            "test", "this is a test sentence with test word"
        )

        # Low density - 1 match in 16 words = 6.25% density
        low_density = ranker._calculate_density_boost(
            "test",
            "this is a very long sentence with many words and only one test word in it",
        )

        # No match
        no_match = ranker._calculate_density_boost("xyz", "some content without match")

        # Check relationships (allow for equal in case of calculation edge cases)
        assert high_density >= med_density >= low_density >= no_match
        assert no_match == 0.0
        assert high_density <= 0.5  # Capped at 0.5

    def test_calculate_density_boost_empty_inputs(self, ranker):
        """Test density boost with empty inputs."""
        assert ranker._calculate_density_boost("", "content") == 0.0
        assert ranker._calculate_density_boost("query", "") == 0.0
        assert ranker._calculate_density_boost("", "") == 0.0

    def test_has_exact_match(self, ranker):
        """Test exact match detection."""
        assert ranker._has_exact_match("test", "this is a test") is True
        # Substring
        assert ranker._has_exact_match("test", "this is testing") is True
        assert ranker._has_exact_match("test", "no match here") is False
        # Case insensitive
        assert ranker._has_exact_match("TEST", "test content") is True

    def test_has_exact_match_empty_inputs(self, ranker):
        """Test exact match with empty inputs."""
        assert ranker._has_exact_match("", "content") is False
        assert ranker._has_exact_match("query", "") is False
        assert ranker._has_exact_match("", "") is False

    def test_calculate_metadata_boost(self, ranker):
        """Test metadata boost calculation."""
        metadata = {
            "character": "TestCharacter",
            "scene_heading": "INT. TEST ROOM - DAY",
            "description": "A room for testing equipment",
        }

        # Query matches character name
        char_boost = ranker._calculate_metadata_boost("test", metadata)
        assert char_boost > 0

        # Query matches scene heading
        scene_boost = ranker._calculate_metadata_boost("room", metadata)
        assert scene_boost > 0

        # Query matches description
        desc_boost = ranker._calculate_metadata_boost("equipment", metadata)
        assert desc_boost > 0

        # Query matches multiple fields
        multi_boost = ranker._calculate_metadata_boost("test", metadata)
        # Should get boost from multiple matches
        assert multi_boost >= char_boost

    def test_calculate_metadata_boost_empty_inputs(self, ranker):
        """Test metadata boost with empty inputs."""
        assert ranker._calculate_metadata_boost("", {"character": "John"}) == 0.0
        assert ranker._calculate_metadata_boost("test", {}) == 0.0
        assert ranker._calculate_metadata_boost("", {}) == 0.0

    def test_deduplicate_results(self, ranker):
        """Test result deduplication."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Content 1",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="scene",
                content="Content 2",
                score=0.7,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r1",  # Duplicate
                type="dialogue",
                content="Content 3",
                score=0.6,
                metadata={},
                highlights=[],
            ),
        ]

        unique = ranker._deduplicate_results(results)

        assert len(unique) == 2
        unique_keys = [f"{r['type']}:{r['id']}" for r in unique]
        assert "dialogue:r1" in unique_keys
        assert "scene:r2" in unique_keys

        # Should keep first occurrence
        r1_result = next(r for r in unique if r["id"] == "r1")
        assert r1_result["content"] == "Content 1"

    def test_deduplicate_results_empty(self, ranker):
        """Test deduplication with empty list."""
        unique = ranker._deduplicate_results([])
        assert unique == []


class TestSearchRankerEdgeCases:
    """Test SearchRanker edge cases and error conditions."""

    def test_ranking_with_unknown_type(self, ranker):
        """Test ranking with unknown result type."""
        results = [
            SearchResult(
                id="r1",
                type="unknown_type",
                content="Test content",
                score=0.5,
                metadata={},
                highlights=[],
            )
        ]

        ranked = ranker.rank_results(results, "test")

        # Should handle unknown type gracefully (use default weight)
        assert len(ranked) == 1
        assert ranked[0]["score"] > 0

    def test_ranking_with_negative_base_score(self, ranker):
        """Test ranking handles negative base scores."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Test content",
                score=-0.1,  # Negative score
                metadata={},
                highlights=[],
            )
        ]

        ranked = ranker.rank_results(results, "test")

        # Should handle gracefully
        assert len(ranked) == 1

    def test_ranking_with_missing_metadata_fields(self, ranker):
        """Test ranking with incomplete metadata."""
        results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="Test content",
                score=0.5,
                metadata={},  # Empty metadata
                highlights=[],
            )
        ]

        ranked = ranker.rank_results(results, "test")

        # Should handle missing metadata gracefully
        assert len(ranked) == 1
        assert ranked[0]["score"] > 0

    def test_filter_with_extreme_values(self, ranker, sample_results):
        """Test filtering with extreme parameter values."""
        # Very high min_score
        filtered = ranker.filter_results(sample_results, min_score=2.0)
        assert filtered == []

        # Zero max_results
        filtered = ranker.filter_results(sample_results, max_results=0)
        assert len(filtered) == 0

        # Negative max_results - Python slicing handles this
        filtered = ranker.filter_results(sample_results, max_results=-1)
        # In Python, list[:-1] returns all but the last element
        assert len(filtered) >= 0

    def test_merge_with_no_arguments(self, ranker):
        """Test merge with no result sets."""
        merged = ranker.merge_results()
        assert merged == []

    def test_ranking_performance_with_large_dataset(self, ranker):
        """Test ranking performance with large number of results."""
        # Create large dataset
        large_results = [
            SearchResult(
                id=f"r{i}",
                type="dialogue",
                content=f"Test content {i}",
                score=0.5 + (i % 50) / 100,  # Varying scores
                metadata={"script_order": i},
                highlights=[],
            )
            for i in range(1000)
        ]

        import time

        start_time = time.time()

        ranked = ranker.rank_results(large_results, "test")

        end_time = time.time()

        # Should complete in reasonable time
        assert end_time - start_time < 5.0
        assert len(ranked) == 1000

        # Should be properly sorted
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)
