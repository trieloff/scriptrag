"""Unit tests for search filters module achieving high coverage."""

import pytest

from scriptrag.search.filters import (
    BibleContentFilter,
    CharacterFilter,
    DuplicateFilter,
    LocationFilter,
    SearchFilter,
    SearchFilterChain,
    SeasonEpisodeFilter,
    TimeOfDayFilter,
)
from scriptrag.search.models import BibleSearchResult, SearchQuery, SearchResult


class TestSearchFilter:
    """Test base SearchFilter class."""

    def test_filter_not_implemented(self) -> None:
        """Test that base filter raises NotImplementedError."""
        base_filter = SearchFilter()
        with pytest.raises(NotImplementedError):
            base_filter.filter([], SearchQuery(raw_query="test"))


class TestSearchFilterChain:
    """Test SearchFilterChain functionality."""

    def test_empty_chain(self) -> None:
        """Test filter chain with no filters."""
        chain = SearchFilterChain()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        assert chain.apply(results, query) == results

    def test_add_filter(self) -> None:
        """Test adding filter to chain."""
        chain = SearchFilterChain()
        filter_obj = DuplicateFilter()
        result = chain.add_filter(filter_obj)
        assert result is chain  # Should return self for chaining
        assert len(chain.filters) == 1

    def test_chain_multiple_filters(self) -> None:
        """Test chaining multiple filters."""
        chain = SearchFilterChain()
        chain.add_filter(CharacterFilter(["JOHN"])).add_filter(DuplicateFilter())
        assert len(chain.filters) == 2


class TestCharacterFilter:
    """Test CharacterFilter functionality."""

    def test_filter_no_characters(self) -> None:
        """Test filter when no characters specified."""
        filter_obj = CharacterFilter()
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
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        assert filter_obj.filter(results, query) == results

    def test_filter_with_character_in_content(self) -> None:
        """Test filter with character name in content."""
        filter_obj = CharacterFilter(["JOHN"])
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
                scene_content="JOHN enters the room",
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
                scene_content="MARY walks alone",
            ),
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1
        assert filtered[0].scene_id == 1

    def test_filter_case_insensitive(self) -> None:
        """Test case insensitive character matching."""
        filter_obj = CharacterFilter(["john"])
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
                scene_content="JOHN speaks loudly",
            )
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1

    def test_filter_from_query_characters(self) -> None:
        """Test using characters from query."""
        filter_obj = CharacterFilter()
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
                scene_content="PETER enters",
            )
        ]
        query = SearchQuery(raw_query="test", characters=["PETER"])
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1


class TestLocationFilter:
    """Test LocationFilter functionality."""

    def test_filter_no_locations(self) -> None:
        """Test filter when no locations specified."""
        filter_obj = LocationFilter()
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
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        assert filter_obj.filter(results, query) == results

    def test_filter_with_location(self) -> None:
        """Test filter with location."""
        filter_obj = LocationFilter(["OFFICE"])
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
                scene_content="Test content",
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
                scene_content="Test content",
            ),
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1
        assert filtered[0].scene_id == 1

    def test_filter_null_location(self) -> None:
        """Test filter with null location in results."""
        filter_obj = LocationFilter(["OFFICE"])
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location=None,
                scene_time="DAY",
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 0

    def test_filter_from_query_locations(self) -> None:
        """Test using locations from query."""
        filter_obj = LocationFilter()
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
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test", locations=["OFFICE"])
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1


class TestTimeOfDayFilter:
    """Test TimeOfDayFilter functionality."""

    def test_filter_no_times(self) -> None:
        """Test filter when no times specified."""
        filter_obj = TimeOfDayFilter()
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
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        assert filter_obj.filter(results, query) == results

    def test_filter_with_time(self) -> None:
        """Test filter with time of day."""
        filter_obj = TimeOfDayFilter(["DAY"])
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
                scene_content="Test content",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="EXT. PARK - NIGHT",
                scene_location="EXT. PARK",
                scene_time="NIGHT",
                scene_content="Test content",
            ),
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1
        assert filtered[0].scene_time == "DAY"

    def test_filter_null_time(self) -> None:
        """Test filter with null time in results."""
        filter_obj = TimeOfDayFilter(["DAY"])
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE",
                scene_location="INT. OFFICE",
                scene_time=None,
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 0

    def test_filter_case_insensitive(self) -> None:
        """Test case insensitive time matching."""
        filter_obj = TimeOfDayFilter(["day"])
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
                scene_content="Test content",
            )
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1


class TestSeasonEpisodeFilter:
    """Test SeasonEpisodeFilter functionality."""

    def test_filter_no_season_episode(self) -> None:
        """Test filter when no season/episode specified."""
        filter_obj = SeasonEpisodeFilter()
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
                scene_content="Test content",
                season=1,
                episode=1,
            )
        ]
        query = SearchQuery(raw_query="test")
        assert filter_obj.filter(results, query) == results

    def test_filter_single_episode(self) -> None:
        """Test filter with single episode."""
        filter_obj = SeasonEpisodeFilter(season_start=1, episode_start=2)
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
                scene_content="Test content",
                season=1,
                episode=1,
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Test content",
                season=1,
                episode=2,
            ),
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1
        assert filtered[0].episode == 2

    def test_filter_episode_range(self) -> None:
        """Test filter with episode range."""
        filter_obj = SeasonEpisodeFilter(
            season_start=1, season_end=1, episode_start=2, episode_end=4
        )
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=i,
                scene_number=i,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Test content",
                season=1,
                episode=i,
            )
            for i in range(1, 6)
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 3
        assert all(2 <= r.episode <= 4 for r in filtered)

    def test_filter_null_values(self) -> None:
        """Test filter with null season/episode in results."""
        filter_obj = SeasonEpisodeFilter(season_start=1, episode_start=1)
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
                scene_content="Test content",
                season=None,
                episode=None,
            )
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 0

    def test_filter_from_query(self) -> None:
        """Test using season/episode from query."""
        filter_obj = SeasonEpisodeFilter()
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
                scene_content="Test content",
                season=2,
                episode=3,
            )
        ]
        query = SearchQuery(
            raw_query="test",
            season_start=2,
            season_end=2,
            episode_start=3,
            episode_end=3,
        )
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 1


class TestDuplicateFilter:
    """Test DuplicateFilter functionality."""

    def test_filter_no_duplicates(self) -> None:
        """Test filter with no duplicates."""
        filter_obj = DuplicateFilter()
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=i,
                scene_number=i,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Test content",
            )
            for i in range(1, 4)
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 3

    def test_filter_with_duplicates(self) -> None:
        """Test filter with duplicate scene IDs."""
        filter_obj = DuplicateFilter()
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
                scene_content="Test content",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. OFFICE - DAY",
                scene_location="INT. OFFICE",
                scene_time="DAY",
                scene_content="Different match",
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
                scene_content="Test content",
            ),
        ]
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)
        assert len(filtered) == 2
        assert filtered[0].scene_id == 1
        assert filtered[1].scene_id == 2


class TestBibleContentFilter:
    """Test BibleContentFilter static methods."""

    def test_filter_by_heading(self) -> None:
        """Test filtering by heading pattern."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Character Notes",
                chunk_level=1,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=2,
                chunk_heading="Plot Summary",
                chunk_level=1,
                chunk_content="Content",
            ),
        ]
        filtered = BibleContentFilter.filter_by_heading(results, "Character")
        assert len(filtered) == 1
        assert filtered[0].chunk_heading == "Character Notes"

    def test_filter_by_heading_empty_pattern(self) -> None:
        """Test filtering with empty heading pattern."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Chapter 1",
                chunk_level=1,
                chunk_content="Content",
            )
        ]
        filtered = BibleContentFilter.filter_by_heading(results, "")
        assert filtered == results

    def test_filter_by_heading_case_insensitive(self) -> None:
        """Test case insensitive heading filtering."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="character notes",
                chunk_level=1,
                chunk_content="Content",
            )
        ]
        filtered = BibleContentFilter.filter_by_heading(results, "CHARACTER")
        assert len(filtered) == 1

    def test_filter_by_heading_null_heading(self) -> None:
        """Test filtering with null heading in result."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading=None,
                chunk_level=1,
                chunk_content="Content",
            )
        ]
        filtered = BibleContentFilter.filter_by_heading(results, "Character")
        assert len(filtered) == 0

    def test_filter_by_level(self) -> None:
        """Test filtering by heading level."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Level 1",
                chunk_level=1,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=2,
                chunk_heading="Level 2",
                chunk_level=2,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=3,
                chunk_heading="Level 3",
                chunk_level=3,
                chunk_content="Content",
            ),
        ]
        filtered = BibleContentFilter.filter_by_level(results, 2)
        assert len(filtered) == 2
        assert all(r.chunk_level <= 2 for r in filtered)

    def test_deduplicate(self) -> None:
        """Test deduplication of bible results."""
        results = [
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Chapter 1",
                chunk_level=1,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=1,
                chunk_heading="Chapter 1",
                chunk_level=1,
                chunk_content="Content",
            ),
            BibleSearchResult(
                script_id=1,
                script_title="Test",
                bible_id=1,
                bible_title="Bible",
                chunk_id=2,
                chunk_heading="Chapter 2",
                chunk_level=1,
                chunk_content="Content",
            ),
        ]
        deduped = BibleContentFilter.deduplicate(results)
        assert len(deduped) == 2
        assert deduped[0].chunk_id == 1
        assert deduped[1].chunk_id == 2
