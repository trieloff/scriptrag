"""Unit tests for search rankers module achieving high coverage."""

import pytest

from scriptrag.search.models import BibleSearchResult, SearchQuery, SearchResult
from scriptrag.search.rankers import (
    BibleResultRanker,
    CustomScoringFunction,
    HybridRanker,
    PositionalRanker,
    ProximityRanker,
    RelevanceRanker,
    SearchRanker,
    TextMatchRanker,
)


class TestSearchRanker:
    """Test base SearchRanker class."""

    def test_rank_not_implemented(self) -> None:
        """Test that base ranker raises NotImplementedError."""
        base_ranker = SearchRanker()
        with pytest.raises(NotImplementedError):
            base_ranker.rank([], SearchQuery(raw_query="test"))


class TestRelevanceRanker:
    """Test RelevanceRanker functionality."""

    def test_rank_by_relevance_score(self) -> None:
        """Test ranking by relevance score."""
        ranker = RelevanceRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Content 1",
                relevance_score=0.3,
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="EXT. PARK - DAY",
                scene_location="EXT. PARK",
                scene_time="DAY",
                scene_content="Content 2",
                relevance_score=0.8,
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=3,
                scene_number=3,
                scene_heading="INT. HOUSE - NIGHT",
                scene_location="INT. HOUSE",
                scene_time="NIGHT",
                scene_content="Content 3",
                relevance_score=0.5,
            ),
        ]
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(results, query)

        assert ranked[0].relevance_score == 0.8
        assert ranked[1].relevance_score == 0.5
        assert ranked[2].relevance_score == 0.3


class TestTextMatchRanker:
    """Test TextMatchRanker functionality."""

    def test_calculate_text_score_empty_inputs(self) -> None:
        """Test text score calculation with empty inputs."""
        ranker = TextMatchRanker()
        assert ranker.calculate_text_score("", "query") == 0.0
        assert ranker.calculate_text_score("text", "") == 0.0
        assert ranker.calculate_text_score("", "") == 0.0

    def test_calculate_text_score_exact_match(self) -> None:
        """Test exact match scoring."""
        ranker = TextMatchRanker()
        text = "The quick brown fox jumps over the lazy dog"
        query = "brown fox"
        score = ranker.calculate_text_score(text, query)
        assert score > 0
        assert ranker.weights["exact_match"] <= score

    def test_calculate_text_score_word_match(self) -> None:
        """Test word-level matching."""
        ranker = TextMatchRanker()
        text = "The quick brown fox jumps over the lazy dog"
        query = "quick dog"
        score = ranker.calculate_text_score(text, query)
        assert score > 0
        # Both words are present
        assert score >= ranker.weights["word_match"]

    def test_calculate_text_score_partial_match(self) -> None:
        """Test partial word matching."""
        ranker = TextMatchRanker()
        text = "The quickest brown foxes jump"
        query = "quick fox"
        score = ranker.calculate_text_score(text, query)
        assert score > 0

    def test_calculate_text_score_case_sensitive_bonus(self) -> None:
        """Test case-sensitive bonus."""
        ranker = TextMatchRanker()
        text = "The Quick Brown Fox"
        query = "Quick Brown"
        score_exact = ranker.calculate_text_score(text, query)

        # Compare with non-matching case
        score_lower = ranker.calculate_text_score(text, "quick brown")
        assert score_exact > score_lower

    def test_calculate_text_score_max_cap(self) -> None:
        """Test that score is capped at 1.0."""
        ranker = TextMatchRanker()
        text = "test test test"
        query = "test"
        score = ranker.calculate_text_score(text, query)
        assert score <= 1.0

    def test_rank_with_text_query(self) -> None:
        """Test ranking with text query."""
        ranker = TextMatchRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. COFFEE SHOP - DAY",
                scene_location="COFFEE SHOP",
                scene_time="DAY",
                scene_content="Walter orders coffee and sits down",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="EXT. PARK - DAY",
                scene_location="PARK",
                scene_time="DAY",
                scene_content="Sarah walks through the park",
            ),
        ]
        query = SearchQuery(raw_query="test", text_query="coffee")
        ranked = ranker.rank(results, query)

        assert ranked[0].scene_id == 1  # Coffee scene should rank first

    def test_rank_with_dialogue_query(self) -> None:
        """Test ranking with dialogue query."""
        ranker = TextMatchRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="OFFICE",
                scene_time="DAY",
                scene_content="Hello world",
            ),
        ]
        query = SearchQuery(raw_query="test", dialogue="Hello")
        ranked = ranker.rank(results, query)

        assert ranked[0].relevance_score > 0

    def test_rank_with_action_query(self) -> None:
        """Test ranking with action query."""
        ranker = TextMatchRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="OFFICE",
                scene_time="DAY",
                scene_content="John walks to the door",
            ),
        ]
        query = SearchQuery(raw_query="test", action="walks")
        ranked = ranker.rank(results, query)

        assert ranked[0].relevance_score > 0

    def test_rank_location_scoring(self) -> None:
        """Test location-based scoring."""
        ranker = TextMatchRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="OFFICE BUILDING",
                scene_time="DAY",
                scene_content="Work scene",
            ),
        ]
        query = SearchQuery(raw_query="test", text_query="office")
        ranked = ranker.rank(results, query)

        # Should match on location
        assert ranked[0].relevance_score > 0


class TestPositionalRanker:
    """Test PositionalRanker functionality."""

    def test_rank_by_position(self) -> None:
        """Test ranking by script position."""
        ranker = PositionalRanker()
        results = [
            SearchResult(
                script_id=2,
                script_title="Test 2",
                script_author="Author",
                scene_id=3,
                scene_number=3,
                scene_heading="Scene 3",
                scene_location="LOC3",
                scene_time="DAY",
                scene_content="Content 3",
            ),
            SearchResult(
                script_id=1,
                script_title="Test 1",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene 1",
                scene_location="LOC1",
                scene_time="DAY",
                scene_content="Content 1",
            ),
            SearchResult(
                script_id=1,
                script_title="Test 1",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="Scene 2",
                scene_location="LOC2",
                scene_time="DAY",
                scene_content="Content 2",
            ),
        ]
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(results, query)

        # Should be sorted by script_id then scene_number
        assert ranked[0].script_id == 1
        assert ranked[0].scene_number == 1
        assert ranked[1].script_id == 1
        assert ranked[1].scene_number == 2
        assert ranked[2].script_id == 2
        assert ranked[2].scene_number == 3


class TestProximityRanker:
    """Test ProximityRanker functionality."""

    def test_calculate_proximity_score_empty(self) -> None:
        """Test proximity score with empty inputs."""
        ranker = ProximityRanker()
        assert ranker.calculate_proximity_score("", ["term1", "term2"]) == 1.0
        assert ranker.calculate_proximity_score("text", []) == 1.0
        assert ranker.calculate_proximity_score("text", ["single"]) == 1.0

    def test_calculate_proximity_score_missing_terms(self) -> None:
        """Test proximity score when terms are missing."""
        ranker = ProximityRanker()
        text = "The quick brown fox"
        terms = ["quick", "elephant"]  # elephant not in text
        score = ranker.calculate_proximity_score(text, terms)
        assert score == float("inf")

    def test_calculate_proximity_score_adjacent_terms(self) -> None:
        """Test proximity score for adjacent terms."""
        ranker = ProximityRanker()
        text = "The quick brown fox jumps"
        terms = ["quick", "brown"]
        score = ranker.calculate_proximity_score(text, terms)
        assert score > 0
        assert score < 1.0  # Should be high score for adjacent terms

    def test_calculate_proximity_score_distant_terms(self) -> None:
        """Test proximity score for distant terms."""
        ranker = ProximityRanker()
        text = "The quick fox is very very very very very brown"
        terms = ["quick", "brown"]
        score_distant = ranker.calculate_proximity_score(text, terms)

        text2 = "The quick brown fox"
        score_close = ranker.calculate_proximity_score(text2, terms)

        assert score_close > score_distant

    def test_calculate_proximity_score_multiple_occurrences(self) -> None:
        """Test proximity with multiple term occurrences."""
        ranker = ProximityRanker()
        text = "quick brown quick brown"
        terms = ["quick", "brown"]
        score = ranker.calculate_proximity_score(text, terms)
        assert score > 0

    def test_rank_single_term(self) -> None:
        """Test ranking with single term (no proximity)."""
        ranker = ProximityRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
                relevance_score=0.5,
            ),
        ]
        query = SearchQuery(raw_query="test", text_query="single")
        ranked = ranker.rank(results, query)

        # Should return unchanged with single term
        assert ranked == results

    def test_rank_with_dialogue_and_action(self) -> None:
        """Test ranking with dialogue and action terms."""
        ranker = ProximityRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Hello there, John walks quickly",
                relevance_score=0.5,
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="Scene",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Hello... Long pause... John... More text... walks",
                relevance_score=0.5,
            ),
        ]
        query = SearchQuery(raw_query="test", dialogue="Hello", action="walks")
        ranked = ranker.rank(results, query)

        # First result should rank higher (terms closer)
        assert ranked[0].scene_id == 1

    def test_rank_preserves_zero_score(self) -> None:
        """Test that infinity proximity returns 0 score."""
        ranker = ProximityRanker()
        text = "only has one term"
        terms = ["one", "missing"]
        score = ranker.calculate_proximity_score(text, terms)
        assert score == 0.0


class TestHybridRanker:
    """Test HybridRanker functionality."""

    def test_default_rankers(self) -> None:
        """Test hybrid ranker with default configuration."""
        ranker = HybridRanker()
        assert len(ranker.rankers) == 4

    def test_custom_rankers(self) -> None:
        """Test hybrid ranker with custom configuration."""
        custom_rankers = [
            (RelevanceRanker(), 0.7),
            (TextMatchRanker(), 0.3),
        ]
        ranker = HybridRanker(custom_rankers)
        assert len(ranker.rankers) == 2

    def test_rank_empty_results(self) -> None:
        """Test ranking empty results."""
        ranker = HybridRanker()
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank([], query)
        assert ranked == []

    def test_rank_combined_scoring(self) -> None:
        """Test combined scoring from multiple rankers."""
        ranker = HybridRanker(
            [
                (RelevanceRanker(), 0.5),
                (PositionalRanker(), 0.5),
            ]
        )
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="Scene 2",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
                relevance_score=0.9,  # High relevance
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene 1",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
                relevance_score=0.1,  # Low relevance but first position
            ),
        ]
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(results, query)

        # Combined score should balance relevance and position
        assert all(r.relevance_score > 0 for r in ranked)

    def test_rank_single_result(self) -> None:
        """Test ranking single result."""
        ranker = HybridRanker()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
                relevance_score=0.5,
            ),
        ]
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(results, query)

        assert len(ranked) == 1
        assert ranked[0].relevance_score > 0


class TestBibleResultRanker:
    """Test BibleResultRanker functionality."""

    def test_rank_by_hierarchy(self) -> None:
        """Test ranking bible results by hierarchy."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=2,
                bible_title="Bible 2",
                chunk_id=1,
                chunk_heading="Chapter",
                chunk_level=1,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible 1",
                chunk_id=3,
                chunk_heading="Chapter",
                chunk_level=2,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible 1",
                chunk_id=2,
                chunk_heading="Chapter",
                chunk_level=1,
                chunk_content="Content",
            ),
        ]

        ranked = BibleResultRanker.rank_by_hierarchy(results)

        # Should be sorted by bible_id, chunk_level, chunk_id
        assert ranked[0].bible_id == 1
        assert ranked[0].chunk_level == 1
        assert ranked[0].chunk_id == 2
        assert ranked[1].bible_id == 1
        assert ranked[1].chunk_level == 2
        assert ranked[2].bible_id == 2

    def test_rank_by_relevance(self) -> None:
        """Test ranking bible results by text relevance."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Introduction",
                chunk_level=1,
                chunk_content="This is about something else",
                relevance_score=0.0,
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=2,
                chunk_heading="Character Development",
                chunk_level=1,
                chunk_content="The character grows throughout the story",
                relevance_score=0.0,
            ),
        ]

        ranked = BibleResultRanker.rank_by_relevance(results, "character")

        # Second result should rank higher (matches in both heading and content)
        assert ranked[0].chunk_id == 2
        assert ranked[0].relevance_score > ranked[1].relevance_score

    def test_rank_by_relevance_null_heading(self) -> None:
        """Test ranking with null heading."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading=None,
                chunk_level=1,
                chunk_content="Character information",
                relevance_score=0.0,
            ),
        ]

        ranked = BibleResultRanker.rank_by_relevance(results, "character")

        # Should still calculate content score
        assert ranked[0].relevance_score > 0


class TestCustomScoringFunction:
    """Test CustomScoringFunction functionality."""

    def test_custom_scoring(self) -> None:
        """Test custom scoring function."""

        def custom_score(result: SearchResult, query: SearchQuery) -> float:
            # Score based on scene number
            return 1.0 / result.scene_number if result.scene_number > 0 else 0.0

        scorer = CustomScoringFunction(custom_score)
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=3,
                scene_number=3,
                scene_heading="Scene 3",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene 1",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="Scene 2",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
            ),
        ]
        query = SearchQuery(raw_query="test")

        ranked = scorer.apply(results, query)

        # Should be sorted by custom score (1/scene_number)
        assert ranked[0].scene_number == 1  # Score = 1.0
        assert ranked[1].scene_number == 2  # Score = 0.5
        assert ranked[2].scene_number == 3  # Score = 0.33

    def test_custom_scoring_with_query_context(self) -> None:
        """Test custom scoring that uses query context."""

        def query_aware_score(result: SearchResult, query: SearchQuery) -> float:
            # Boost score if query contains "important"
            base_score = 0.5
            if query.text_query and "important" in query.text_query:
                base_score += 0.5
            return base_score

        scorer = CustomScoringFunction(query_aware_score)
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="Scene",
                scene_location="LOC",
                scene_time="DAY",
                scene_content="Content",
            ),
        ]

        query_normal = SearchQuery(raw_query="test", text_query="normal")
        ranked_normal = scorer.apply(results, query_normal)
        assert ranked_normal[0].relevance_score == 0.5

        query_important = SearchQuery(raw_query="test", text_query="important")
        ranked_important = scorer.apply(results, query_important)
        assert ranked_important[0].relevance_score == 1.0
