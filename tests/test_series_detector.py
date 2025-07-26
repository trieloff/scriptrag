"""Tests for TV series pattern detection module."""

from pathlib import Path

import pytest

from scriptrag.parser.series_detector import SeriesPatternDetector


class TestSeriesPatternDetector:
    """Test cases for SeriesPatternDetector."""

    def test_underscore_format(self) -> None:
        """Test detection of ShowName_S01E01_EpisodeTitle.fountain format."""
        detector = SeriesPatternDetector()

        # Basic format
        info = detector.detect("BreakingBad_S01E01_Pilot.fountain")
        assert info.series_name == "BreakingBad"
        assert info.season_number == 1
        assert info.episode_number == 1
        assert info.episode_title == "Pilot"
        assert info.is_series is True

        # Without episode title
        info = detector.detect("BreakingBad_S02E03.fountain")
        assert info.series_name == "BreakingBad"
        assert info.season_number == 2
        assert info.episode_number == 3
        assert info.episode_title is None

        # With spaces in series name
        info = detector.detect("Breaking Bad_S01E01_Pilot.fountain")
        assert info.series_name == "Breaking Bad"

    def test_x_format(self) -> None:
        """Test detection of ShowName - 1x01 - Episode Title.fountain format."""
        detector = SeriesPatternDetector()

        info = detector.detect("The Wire - 3x05 - Straight and True.fountain")
        assert info.series_name == "The Wire"
        assert info.season_number == 3
        assert info.episode_number == 5
        assert info.episode_title == "Straight and True"
        assert info.is_series is True

    def test_dotted_format(self) -> None:
        """Test detection of ShowName.101.EpisodeTitle.fountain format."""
        detector = SeriesPatternDetector()

        info = detector.detect(
            "Friends.201.The One with Ross's New Girlfriend.fountain"
        )
        assert info.series_name == "Friends"
        assert info.season_number == 2
        assert info.episode_number == 1
        assert info.episode_title == "The One with Ross's New Girlfriend"
        assert info.is_series is True

    def test_directory_format(self) -> None:
        """Test detection from directory structure."""
        detector = SeriesPatternDetector()

        # Create a mock path structure
        file_path = Path("/shows/Breaking Bad/Season 1/Episode 01 - Pilot.fountain")
        info = detector.detect(file_path)

        # Should extract episode info from filename
        assert info.episode_number == 1
        assert info.episode_title == "Pilot"
        assert info.is_series is True

        # Series name should be extracted from path
        assert info.series_name == "Breaking Bad"

    def test_special_episodes(self) -> None:
        """Test detection of special episodes."""
        detector = SeriesPatternDetector()

        info = detector.detect("The Office - Special - Christmas Party.fountain")
        assert info.series_name == "The Office"
        assert info.episode_title == "Christmas Party"
        assert info.is_special is True
        assert info.is_series is True

    def test_multi_part_episodes(self) -> None:
        """Test detection of multi-part episodes."""
        detector = SeriesPatternDetector()

        # Part format
        info = detector.detect("Lost_S01E01_Pilot Part 1.fountain")
        assert info.multi_part == "Part 1"

        # Roman numerals
        info = detector.detect("Lost_S01E02_Pilot Part II.fountain")
        assert info.multi_part == "Part II"

        # X of Y format
        info = detector.detect("Lost_S06E17_The End (1 of 2).fountain")
        assert info.multi_part == "(1 of 2)"

    def test_custom_pattern(self) -> None:
        """Test custom regex pattern."""
        # Custom pattern for "ShowName Episode S01E01.fountain"
        custom_pattern = (
            r"^(?P<series>.+?)\s+Episode\s+S(?P<season>\d+)E(?P<episode>\d+)\.fountain$"
        )
        detector = SeriesPatternDetector(custom_pattern)

        info = detector.detect("The Sopranos Episode S01E01.fountain")
        assert info.series_name == "The Sopranos"
        assert info.season_number == 1
        assert info.episode_number == 1

    def test_invalid_custom_pattern(self) -> None:
        """Test invalid custom pattern raises error."""
        with pytest.raises(ValueError, match="Invalid custom pattern"):
            SeriesPatternDetector("[invalid regex")

    def test_non_series_files(self) -> None:
        """Test files that are not part of a series."""
        detector = SeriesPatternDetector()

        info = detector.detect("MyAwesomeMovie.fountain")
        assert info.series_name == "MyAwesomeMovie"
        assert info.is_series is False
        assert info.season_number is None
        assert info.episode_number is None

    def test_detect_bulk(self) -> None:
        """Test bulk detection of multiple files."""
        detector = SeriesPatternDetector()

        files = [
            Path("BreakingBad_S01E01_Pilot.fountain"),
            Path("BreakingBad_S01E02_CatsInTheBag.fountain"),
            Path("BreakingBad_S01E03_AndTheBagIsInTheRiver.fountain"),
        ]

        results = detector.detect_bulk(files)

        assert len(results) == 3
        for _file_path, info in results.items():
            assert info.series_name == "BreakingBad"
            assert info.season_number == 1
            assert info.is_series is True

    def test_group_by_series(self) -> None:
        """Test grouping files by series."""
        detector = SeriesPatternDetector()

        files = [
            Path("BreakingBad_S01E01.fountain"),
            Path("BreakingBad_S01E02.fountain"),
            Path("TheWire_S01E01.fountain"),
            Path("TheWire_S01E02.fountain"),
            Path("StandaloneScript.fountain"),
        ]

        series_infos = detector.detect_bulk(files)
        grouped = detector.group_by_series(series_infos)

        assert len(grouped) == 3
        assert "BreakingBad" in grouped
        assert "TheWire" in grouped
        assert "StandaloneScript" in grouped

        # Check sorting within series
        bb_episodes = grouped["BreakingBad"]
        assert len(bb_episodes) == 2
        assert bb_episodes[0][1].episode_number == 1
        assert bb_episodes[1][1].episode_number == 2

    def test_edge_cases(self) -> None:
        """Test edge cases and unusual formats."""
        detector = SeriesPatternDetector()

        # Double digit seasons
        info = detector.detect("Show_S10E20_Title.fountain")
        assert info.season_number == 10
        assert info.episode_number == 20

        # Triple digit episodes
        info = detector.detect("LongShow.10001.Title.fountain")
        assert info.season_number == 10
        assert info.episode_number == 1

        # No extension (should not match)
        info = detector.detect("Show_S01E01_Title")
        assert info.is_series is False

    def test_case_insensitivity(self) -> None:
        """Test that patterns are case insensitive."""
        detector = SeriesPatternDetector()

        # Lowercase
        info = detector.detect("show_s01e01_title.fountain")
        assert info.season_number == 1
        assert info.episode_number == 1

        # Mixed case
        info = detector.detect("Show - 1X01 - Title.fountain")
        assert info.season_number == 1
        assert info.episode_number == 1
