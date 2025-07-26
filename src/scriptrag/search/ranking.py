"""Search result ranking and filtering.

This module provides functionality for ranking and filtering search results
based on relevance, recency, and other factors.
"""

from typing import Any

from scriptrag.config import get_logger

from .types import SearchResult, SearchResults

logger = get_logger(__name__)


class SearchRanker:
    """Ranks and filters search results for optimal relevance."""

    def __init__(self) -> None:
        """Initialize search ranker."""
        self.type_weights = {
            "scene": 1.0,
            "dialogue": 0.9,
            "character": 0.85,
            "action": 0.8,
            "location": 0.75,
            "object": 0.7,
        }

    def rank_results(
        self,
        results: SearchResults,
        query: str,
        boost_recent: bool = True,
    ) -> SearchResults:
        """Rank search results by relevance.

        Args:
            results: Raw search results
            query: Original search query
            boost_recent: Whether to boost recent results

        Returns:
            Ranked search results
        """
        if not results:
            return []

        # Calculate composite scores
        scored_results: list[Any] = []
        for result in results:
            composite_score = self._calculate_composite_score(
                result, query, boost_recent
            )
            # Create a copy with updated score
            ranked_result = dict(result)
            ranked_result["score"] = composite_score
            scored_results.append(ranked_result)

        # Sort by composite score
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # Remove duplicates while preserving order
        seen_ids = set()
        unique_results: SearchResults = []
        for result in scored_results:
            result_key = f"{result['type']}:{result['id']}"
            if result_key not in seen_ids:
                seen_ids.add(result_key)
                unique_results.append(result)

        return unique_results

    def filter_results(
        self,
        results: SearchResults,
        min_score: float = 0.0,
        max_results: int | None = None,
        deduplicate: bool = True,
    ) -> SearchResults:
        """Filter search results based on criteria.

        Args:
            results: Search results to filter
            min_score: Minimum score threshold
            max_results: Maximum number of results
            deduplicate: Remove duplicate results

        Returns:
            Filtered search results
        """
        filtered = []

        # Apply score filter
        for result in results:
            if result["score"] >= min_score:
                filtered.append(result)

        # Remove duplicates if requested
        if deduplicate:
            filtered = self._deduplicate_results(filtered)

        # Apply result limit
        if max_results is not None:
            filtered = filtered[:max_results]

        return filtered

    def group_results_by_type(self, results: SearchResults) -> dict[str, SearchResults]:
        """Group search results by type.

        Args:
            results: Search results to group

        Returns:
            Dictionary mapping types to results
        """
        grouped: dict[str, SearchResults] = {}
        for result in results:
            result_type = result["type"]
            if result_type not in grouped:
                grouped[result_type] = []
            grouped[result_type].append(result)

        return grouped

    def merge_results(
        self,
        *result_sets: SearchResults,
        query: str | None = None,
    ) -> SearchResults:
        """Merge multiple result sets.

        Args:
            result_sets: Multiple result sets to merge
            query: Query for re-ranking (optional)

        Returns:
            Merged and ranked results
        """
        all_results = []
        for result_set in result_sets:
            all_results.extend(result_set)

        # Re-rank if query provided
        if query:
            return self.rank_results(all_results, query)

        # Otherwise just sort by existing scores
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return self._deduplicate_results(all_results)

    def _calculate_composite_score(
        self,
        result: SearchResult,
        query: str,
        boost_recent: bool = True,
    ) -> float:
        """Calculate composite relevance score.

        Args:
            result: Search result
            query: Original query
            boost_recent: Whether to boost recent results

        Returns:
            Composite score
        """
        # Start with base score
        base_score = result["score"]

        # Apply type weight
        type_weight = self.type_weights.get(result["type"], 0.5)
        weighted_score = base_score * type_weight

        # Boost for query term density
        density_boost = self._calculate_density_boost(query, result["content"])
        weighted_score *= 1.0 + density_boost

        # Boost for exact matches
        if self._has_exact_match(query, result["content"]):
            weighted_score *= 1.2

        # Boost for metadata matches
        metadata_boost = self._calculate_metadata_boost(query, result["metadata"])
        weighted_score *= 1.0 + metadata_boost

        # Recency boost (if applicable)
        if boost_recent and "script_order" in result["metadata"]:
            # Assuming lower script_order means earlier in script
            # This is a simple linear decay - could be improved
            order = result["metadata"]["script_order"]
            recency_factor = 1.0 / (1.0 + order / 1000.0)
            weighted_score *= 0.9 + (0.1 * recency_factor)

        # Ensure score stays in [0, 1] range
        return min(1.0, weighted_score)

    def _calculate_density_boost(self, query: str, content: str) -> float:
        """Calculate boost based on query term density.

        Args:
            query: Search query
            content: Content to analyze

        Returns:
            Density boost factor (0.0 to 0.5)
        """
        if not query or not content:
            return 0.0

        query_words = query.lower().split()
        content_lower = content.lower()
        content_words = len(content_lower.split())

        if content_words == 0:
            return 0.0

        # Count occurrences of each query word
        total_occurrences = 0
        for word in query_words:
            total_occurrences += content_lower.count(word)

        # Calculate density
        density = total_occurrences / content_words

        # Convert to boost (cap at 0.5)
        return min(0.5, density * 5.0)

    def _has_exact_match(self, query: str, content: str) -> bool:
        """Check if content contains exact query match.

        Args:
            query: Search query
            content: Content to check

        Returns:
            True if exact match found
        """
        if not query or not content:
            return False

        return query.lower() in content.lower()

    def _calculate_metadata_boost(self, query: str, metadata: dict[str, Any]) -> float:
        """Calculate boost based on metadata matches.

        Args:
            query: Search query
            metadata: Result metadata

        Returns:
            Metadata boost factor (0.0 to 0.3)
        """
        if not query or not metadata:
            return 0.0

        boost = 0.0
        query_lower = query.lower()

        # Check character name match
        if "character" in metadata:
            char_name = str(metadata["character"]).lower()
            if query_lower in char_name:
                boost += 0.15

        # Check scene heading match
        if "scene_heading" in metadata:
            heading = str(metadata["scene_heading"]).lower()
            if query_lower in heading:
                boost += 0.1

        # Check description match
        if "description" in metadata:
            desc = str(metadata["description"]).lower()
            if query_lower in desc:
                boost += 0.05

        return boost

    def _deduplicate_results(self, results: SearchResults) -> SearchResults:
        """Remove duplicate results.

        Args:
            results: Results to deduplicate

        Returns:
            Deduplicated results
        """
        seen = set()
        unique = []

        for result in results:
            # Create unique key
            key = f"{result['type']}:{result['id']}"

            if key not in seen:
                seen.add(key)
                unique.append(result)

        return unique
