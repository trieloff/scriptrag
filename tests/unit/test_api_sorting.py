"""Unit tests for script sorting functionality."""

from pathlib import Path

from scriptrag.api.list import FountainMetadata
from scriptrag.api.sorting import sort_scripts


class TestSortScripts:
    """Test the sort_scripts function."""

    def test_sort_by_season_and_episode(self):
        """Test sorting primarily by season then episode."""
        scripts = [
            FountainMetadata(
                file_path=Path("s2e3.fountain"),
                title="Show",
                season_number=2,
                episode_number=3,
            ),
            FountainMetadata(
                file_path=Path("s1e2.fountain"),
                title="Show",
                season_number=1,
                episode_number=2,
            ),
            FountainMetadata(
                file_path=Path("s2e1.fountain"),
                title="Show",
                season_number=2,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("s1e1.fountain"),
                title="Show",
                season_number=1,
                episode_number=1,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # Should be sorted: S1E1, S1E2, S2E1, S2E3
        assert sorted_scripts[0].season_number == 1
        assert sorted_scripts[0].episode_number == 1
        assert sorted_scripts[1].season_number == 1
        assert sorted_scripts[1].episode_number == 2
        assert sorted_scripts[2].season_number == 2
        assert sorted_scripts[2].episode_number == 1
        assert sorted_scripts[3].season_number == 2
        assert sorted_scripts[3].episode_number == 3

    def test_sort_with_title_as_tiebreaker(self):
        """Test that title is used as tiebreaker for same season/episode."""
        scripts = [
            FountainMetadata(
                file_path=Path("b.fountain"),
                title="Beta Show",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("a.fountain"),
                title="Alpha Show",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("c.fountain"),
                title="Charlie Show",
                season_number=1,
                episode_number=1,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # All have same season/episode, so should be sorted by title
        assert sorted_scripts[0].title == "Alpha Show"
        assert sorted_scripts[1].title == "Beta Show"
        assert sorted_scripts[2].title == "Charlie Show"

    def test_sort_with_none_values_last(self):
        """Test that scripts without season/episode numbers sort last."""
        scripts = [
            FountainMetadata(
                file_path=Path("standalone.fountain"),
                title="Standalone Script",
            ),
            FountainMetadata(
                file_path=Path("s1e1.fountain"),
                title="Series",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("only_episode.fountain"),
                title="Episode Only",
                episode_number=5,
            ),
            FountainMetadata(
                file_path=Path("only_season.fountain"),
                title="Season Only",
                season_number=2,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # Series with both season and episode should come first
        assert sorted_scripts[0].title == "Series"
        # Then season only (season 2, no episode)
        assert sorted_scripts[1].title == "Season Only"
        # Then episode only (no season, episode 5)
        assert sorted_scripts[2].title == "Episode Only"
        # Finally standalone (no season or episode)
        assert sorted_scripts[3].title == "Standalone Script"

    def test_sort_mixed_series_and_standalone(self):
        """Test sorting a mix of series episodes and standalone scripts."""
        scripts = [
            FountainMetadata(
                file_path=Path("movie.fountain"),
                title="Standalone Movie",
            ),
            FountainMetadata(
                file_path=Path("s1e3.fountain"),
                title="TV Show",
                season_number=1,
                episode_number=3,
            ),
            FountainMetadata(
                file_path=Path("s1e1.fountain"),
                title="TV Show",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("another.fountain"),
                title="Another Movie",
            ),
            FountainMetadata(
                file_path=Path("s1e2.fountain"),
                title="TV Show",
                season_number=1,
                episode_number=2,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # Series episodes should come first in order
        assert sorted_scripts[0].episode_number == 1
        assert sorted_scripts[1].episode_number == 2
        assert sorted_scripts[2].episode_number == 3
        # Then standalone scripts sorted by title
        assert sorted_scripts[3].title == "Another Movie"
        assert sorted_scripts[4].title == "Standalone Movie"

    def test_sort_with_missing_titles(self):
        """Test sorting when some scripts have no title."""
        scripts = [
            FountainMetadata(
                file_path=Path("z_file.fountain"),
                season_number=1,
                episode_number=2,
            ),
            FountainMetadata(
                file_path=Path("a_file.fountain"),
                season_number=1,
                episode_number=2,
            ),
            FountainMetadata(
                file_path=Path("m_file.fountain"),
                title="Middle Title",
                season_number=1,
                episode_number=2,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # Same season/episode, so sorted by title (or filename stem if no title)
        assert sorted_scripts[0].file_path.stem == "a_file"
        assert sorted_scripts[1].title == "Middle Title"
        assert sorted_scripts[2].file_path.stem == "z_file"

    def test_sort_case_insensitive(self):
        """Test that sorting by title is case-insensitive."""
        scripts = [
            FountainMetadata(
                file_path=Path("1.fountain"),
                title="ZEBRA",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("2.fountain"),
                title="alpha",
                season_number=1,
                episode_number=1,
            ),
            FountainMetadata(
                file_path=Path("3.fountain"),
                title="Beta",
                season_number=1,
                episode_number=1,
            ),
        ]

        sorted_scripts = sort_scripts(scripts)

        # Should be sorted alphabetically ignoring case
        assert sorted_scripts[0].title == "alpha"
        assert sorted_scripts[1].title == "Beta"
        assert sorted_scripts[2].title == "ZEBRA"

    def test_sort_empty_list(self):
        """Test sorting an empty list."""
        assert sort_scripts([]) == []

    def test_sort_single_item(self):
        """Test sorting a single item list."""
        script = FountainMetadata(
            file_path=Path("test.fountain"),
            title="Test",
        )
        assert sort_scripts([script]) == [script]

    def test_sort_preserves_original_list(self):
        """Test that sorting doesn't modify the original list."""
        scripts = [
            FountainMetadata(
                file_path=Path("b.fountain"),
                title="B",
                season_number=2,
            ),
            FountainMetadata(
                file_path=Path("a.fountain"),
                title="A",
                season_number=1,
            ),
        ]
        original = scripts.copy()

        sorted_scripts = sort_scripts(scripts)

        # Original should be unchanged
        assert scripts == original
        # Sorted should be different
        assert sorted_scripts != scripts
        assert sorted_scripts[0].title == "A"
        assert sorted_scripts[1].title == "B"
