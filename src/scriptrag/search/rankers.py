"""Result ranking and scoring for search results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from scriptrag.search.models import BibleSearchResult, SearchQuery, SearchResult


class SearchRanker(ABC):
    """Base class for search result ranking."""

    @abstractmethod
    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Rank search results.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Ranked results
        """


class RelevanceRanker(SearchRanker):
    """Rank results by relevance score."""

    def rank(
        self,
        results: list[SearchResult],
        query: SearchQuery,  # noqa: ARG002
    ) -> list[SearchResult]:
        """Rank results by relevance score.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Results sorted by relevance score (descending)
        """
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)


class TextMatchRanker(SearchRanker):
    """Rank results by text match quality."""

    def __init__(self) -> None:
        """Initialize text match ranker."""
        self.weights = {
            "exact_match": 1.0,
            "word_match": 0.8,
            "partial_match": 0.5,
            "case_sensitive": 0.1,
        }

    def calculate_text_score(self, text: str, query: str) -> float:
        """Calculate text matching score.

        Args:
            text: Text to search in
            query: Query text

        Returns:
            Score between 0 and 1
        """
        if not text or not query:
            return 0.0

        text_lower = text.lower()
        query_lower = query.lower()

        # Build base score from matching signals
        score = 0.0

        # Exact match
        if query_lower in text_lower:
            score += self.weights["exact_match"]

        # Word-level matching
        query_words = query_lower.split()
        text_words = text_lower.split()
        word_matches = sum(1 for word in query_words if word in text_words)
        if query_words:
            score += self.weights["word_match"] * (word_matches / len(query_words))

        # Partial word matching
        partial_matches = sum(
            1 for word in query_words if any(word in tw for tw in text_words)
        )
        if query_words:
            word_ratio = partial_matches / len(query_words)
            score += self.weights["partial_match"] * word_ratio

        # Reserve headroom for case-sensitive bonus so exact casing can win ties
        case_bonus = self.weights["case_sensitive"]
        score = min(score, 1.0 - case_bonus)

        # Case-sensitive bonus
        if query in text:
            score += case_bonus

        return min(score, 1.0)

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Rank results by text match quality.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Results with updated relevance scores
        """
        query_text = query.dialogue or query.action or query.text_query or ""

        for result in results:
            # Calculate score based on where the match occurred
            content_score = self.calculate_text_score(result.scene_content, query_text)
            heading_score = self.calculate_text_score(result.scene_heading, query_text)
            location_score = 0.0
            if result.scene_location:
                location_score = self.calculate_text_score(
                    result.scene_location, query_text
                )

            # Weight scores by importance
            result.relevance_score = (
                content_score * 0.6 + heading_score * 0.3 + location_score * 0.1
            )

        return sorted(results, key=lambda r: r.relevance_score, reverse=True)


class PositionalRanker(SearchRanker):
    """Rank results by position in script (chronological order)."""

    def rank(
        self,
        results: list[SearchResult],
        query: SearchQuery,  # noqa: ARG002
    ) -> list[SearchResult]:
        """Rank results by position in script.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Results sorted by script ID and scene number
        """
        return sorted(results, key=lambda r: (r.script_id, r.scene_number))


class ProximityRanker(SearchRanker):
    """Rank results by proximity of search terms."""

    def calculate_proximity_score(self, text: str, terms: list[str]) -> float:
        """Calculate proximity score for multiple terms.

        Args:
            text: Text to analyze
            terms: Search terms

        Returns:
            Proximity score (lower is better)
        """
        if not text or len(terms) < 2:
            return 1.0

        text_lower = text.lower()
        positions: dict[str, list[int]] = {}

        # Find positions of each term
        for term in terms:
            term_lower = term.lower()
            positions[term] = []
            idx = 0
            while idx < len(text_lower):
                idx = text_lower.find(term_lower, idx)
                if idx == -1:
                    break
                positions[term].append(idx)
                idx += len(term_lower)

        # If any term is missing, no proximity signal
        if any(not pos_list for pos_list in positions.values()):
            return 0.0

        # Calculate minimum distance between all terms
        min_distance = float("inf")
        for i, term1 in enumerate(terms[:-1]):
            for term2 in terms[i + 1 :]:
                for pos1 in positions[term1]:
                    for pos2 in positions[term2]:
                        distance = abs(pos2 - pos1)
                        min_distance = min(min_distance, distance)

        # Convert to score (inverse of distance, normalized)
        if min_distance == float("inf"):
            return 0.0
        return 1.0 / (1.0 + min_distance / 100.0)

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Rank results by term proximity.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Results ranked by proximity
        """
        # Extract search terms
        terms = []
        if query.text_query:
            terms.extend(query.text_query.split())
        if query.dialogue:
            terms.extend(query.dialogue.split())
        if query.action:
            terms.extend(query.action.split())

        if len(terms) < 2:
            return results

        for result in results:
            proximity_score = self.calculate_proximity_score(
                result.scene_content, terms
            )
            # Combine with existing relevance score
            result.relevance_score = (
                result.relevance_score * 0.7 + proximity_score * 0.3
            )

        return sorted(results, key=lambda r: r.relevance_score, reverse=True)


class HybridRanker(SearchRanker):
    """Combine multiple ranking strategies."""

    def __init__(self, rankers: list[tuple[SearchRanker, float]] | None = None):
        """Initialize hybrid ranker.

        Args:
            rankers: List of (ranker, weight) tuples
        """
        if rankers is None:
            # Default ranker configuration
            rankers = [
                (TextMatchRanker(), 0.4),
                (RelevanceRanker(), 0.3),
                (ProximityRanker(), 0.2),
                (PositionalRanker(), 0.1),
            ]
        self.rankers = rankers

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Rank results using hybrid approach.

        Args:
            results: Results to rank
            query: Search query for context

        Returns:
            Results with combined ranking
        """
        if not results:
            return results

        # Store scores from each ranker
        scores: dict[int, dict[str, float]] = {}
        for result in results:
            scores[result.scene_id] = {}

        # Apply each ranker and collect scores
        for ranker, weight in self.rankers:
            ranked = ranker.rank(list(results), query)
            # Assign scores based on position
            max_score = len(ranked)
            for i, result in enumerate(ranked):
                # Avoid division by zero if ranked is empty
                score = (max_score - i) / max_score if max_score > 0 else 0
                ranker_name = ranker.__class__.__name__
                scores[result.scene_id][ranker_name] = score * weight

        # Calculate combined scores
        for result in results:
            combined_score = sum(scores[result.scene_id].values())
            result.relevance_score = combined_score

        return sorted(results, key=lambda r: r.relevance_score, reverse=True)


class BibleResultRanker:
    """Ranker for bible search results."""

    @staticmethod
    def rank_by_hierarchy(results: list[BibleSearchResult]) -> list[BibleSearchResult]:
        """Rank bible results by hierarchical structure.

        Args:
            results: Bible results to rank

        Returns:
            Results sorted by bible ID, then chunk level, then position
        """
        return sorted(results, key=lambda r: (r.bible_id, r.chunk_level, r.chunk_id))

    @staticmethod
    def rank_by_relevance(
        results: list[BibleSearchResult], query_text: str
    ) -> list[BibleSearchResult]:
        """Rank bible results by text relevance.

        Args:
            results: Bible results to rank
            query_text: Query text for matching

        Returns:
            Results sorted by relevance
        """
        ranker = TextMatchRanker()

        for result in results:
            # Calculate scores for heading and content
            heading_score = 0.0
            if result.chunk_heading:
                heading_score = ranker.calculate_text_score(
                    result.chunk_heading, query_text
                )

            content_score = ranker.calculate_text_score(
                result.chunk_content, query_text
            )

            # Weight heading matches higher for bible content
            result.relevance_score = heading_score * 0.4 + content_score * 0.6

        return sorted(results, key=lambda r: r.relevance_score, reverse=True)


class CustomScoringFunction:
    """Allow custom scoring functions for specialized ranking."""

    def __init__(self, scoring_fn: Callable[[SearchResult, SearchQuery], float]):
        """Initialize with custom scoring function.

        Args:
            scoring_fn: Function that takes (result, query) and returns score
        """
        self.scoring_fn = scoring_fn

    def apply(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Apply custom scoring function.

        Args:
            results: Results to score
            query: Search query for context

        Returns:
            Results with updated scores
        """
        for result in results:
            result.relevance_score = self.scoring_fn(result, query)
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)
