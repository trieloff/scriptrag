"""Search filtering logic for different content types."""

from abc import ABC, abstractmethod

from scriptrag.search.models import (
    BibleSearchResult,
    SearchQuery,
    SearchResult,
)


class SearchFilterChain:
    """Chain of filters for search results."""

    def __init__(self) -> None:
        """Initialize the filter chain."""
        self.filters: list[SearchFilter] = []

    def add_filter(self, filter_instance: "SearchFilter") -> "SearchFilterChain":
        """Add a filter to the chain.

        Args:
            filter_instance: Filter to add

        Returns:
            Self for chaining
        """
        self.filters.append(filter_instance)
        return self

    def apply(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Apply all filters in the chain.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """
        filtered = results
        for filter_instance in self.filters:
            filtered = filter_instance.filter(filtered, query)
        return filtered


class SearchFilter(ABC):
    """Base class for search filters."""

    @abstractmethod
    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Filter search results.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """


class CharacterFilter(SearchFilter):
    """Filter results by character presence."""

    def __init__(self, characters: list[str] | None = None):
        """Initialize character filter.

        Args:
            characters: List of character names to filter by
        """
        self.characters = characters or []

    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Filter results to only include scenes with specified characters.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """
        if not self.characters and not query.characters:
            return results

        characters_to_check = self.characters or query.characters
        # In a real implementation, we'd check scene content for character presence
        # For now, return all results if character name appears in content
        filtered = []
        for result in results:
            for char in characters_to_check:
                if char.upper() in result.scene_content.upper():
                    filtered.append(result)
                    break
        return filtered


class LocationFilter(SearchFilter):
    """Filter results by location."""

    def __init__(self, locations: list[str] | None = None):
        """Initialize location filter.

        Args:
            locations: List of locations to filter by
        """
        self.locations = locations or []

    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Filter results by location.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """
        if not self.locations and not query.locations:
            return results

        locations_to_check = self.locations or query.locations
        filtered = []
        for result in results:
            if not result.scene_location:
                continue
            for location in locations_to_check:
                if location.upper() in result.scene_location.upper():
                    filtered.append(result)
                    break
        return filtered


class TimeOfDayFilter(SearchFilter):
    """Filter results by time of day."""

    def __init__(self, times: list[str] | None = None):
        """Initialize time filter.

        Args:
            times: List of times (DAY, NIGHT, etc.) to filter by
        """
        self.times = times or []

    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,  # noqa: ARG002
    ) -> list[SearchResult]:
        """Filter results by time of day.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """
        if not self.times:
            return results

        filtered = []
        for result in results:
            if not result.scene_time:
                continue
            for time in self.times:
                if time.upper() in result.scene_time.upper():
                    filtered.append(result)
                    break
        return filtered


class SeasonEpisodeFilter(SearchFilter):
    """Filter results by season and episode."""

    def __init__(
        self,
        season_start: int | None = None,
        season_end: int | None = None,
        episode_start: int | None = None,
        episode_end: int | None = None,
    ):
        """Initialize season/episode filter.

        Args:
            season_start: Starting season number
            season_end: Ending season number (for range)
            episode_start: Starting episode number
            episode_end: Ending episode number (for range)
        """
        self.season_start = season_start
        self.season_end = season_end
        self.episode_start = episode_start
        self.episode_end = episode_end

    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Filter results by season/episode.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results
        """
        # Use query parameters if not specified in constructor
        season_start = self.season_start or query.season_start
        season_end = self.season_end or query.season_end
        episode_start = self.episode_start or query.episode_start
        episode_end = self.episode_end or query.episode_end

        if season_start is None:
            return results

        filtered = []
        for result in results:
            if result.season is None or result.episode is None:
                continue

            # Check if result is within range
            if season_end is not None:
                # Range query
                if (
                    season_start <= result.season <= season_end
                    and episode_start is not None
                    and episode_end is not None
                    and episode_start <= result.episode <= episode_end
                ):
                    filtered.append(result)
            else:
                # Single episode query
                if (
                    result.season == season_start
                    and episode_start is not None
                    and result.episode == episode_start
                ):
                    filtered.append(result)

        return filtered


class DuplicateFilter(SearchFilter):
    """Remove duplicate results based on scene ID."""

    def filter(
        self,
        results: list[SearchResult],
        query: SearchQuery,  # noqa: ARG002
    ) -> list[SearchResult]:
        """Remove duplicate results.

        Args:
            results: Results to filter
            query: Search query for context

        Returns:
            Filtered results with duplicates removed
        """
        seen_ids = set()
        filtered = []
        for result in results:
            if result.scene_id not in seen_ids:
                seen_ids.add(result.scene_id)
                filtered.append(result)
        return filtered


class BibleContentFilter:
    """Filter for bible content results."""

    @staticmethod
    def filter_by_heading(
        results: list[BibleSearchResult],
        heading_pattern: str,
    ) -> list[BibleSearchResult]:
        """Filter bible results by heading pattern.

        Args:
            results: Bible results to filter
            heading_pattern: Pattern to match in headings

        Returns:
            Filtered bible results
        """
        if not heading_pattern:
            return results

        filtered = []
        for result in results:
            heading = result.chunk_heading
            if heading and heading_pattern.upper() in heading.upper():
                filtered.append(result)
        return filtered

    @staticmethod
    def filter_by_level(
        results: list[BibleSearchResult],
        max_level: int,
    ) -> list[BibleSearchResult]:
        """Filter bible results by heading level.

        Args:
            results: Bible results to filter
            max_level: Maximum heading level to include

        Returns:
            Filtered bible results
        """
        return [r for r in results if r.chunk_level <= max_level]

    @staticmethod
    def deduplicate(results: list[BibleSearchResult]) -> list[BibleSearchResult]:
        """Remove duplicate bible results.

        Args:
            results: Bible results to deduplicate

        Returns:
            Deduplicated results
        """
        seen_ids = set()
        filtered = []
        for result in results:
            if result.chunk_id not in seen_ids:
                seen_ids.add(result.chunk_id)
                filtered.append(result)
        return filtered
