"""TV Series Pattern Detection Module.

This module provides functionality to detect and extract TV series metadata
from fountain file names and directory structures.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import ClassVar


@dataclass
class SeriesInfo:
    """Information extracted from a TV series script filename."""

    series_name: str
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    is_series: bool = False
    is_special: bool = False
    multi_part: str | None = None  # For multi-part episodes (e.g., "Part 1")


class SeriesPatternDetector:
    """Detects TV series patterns in filenames and extracts metadata."""

    # Common TV series filename patterns
    PATTERNS: ClassVar[list[tuple[str, Pattern[str]]]] = [
        # ShowName_S01E01_EpisodeTitle.fountain
        (
            "underscore_format",
            re.compile(
                r"^(?P<series>.+?)_S(?P<season>\d+)E(?P<episode>\d+)"
                r"(?:_(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # ShowName - 1x01 - Episode Title.fountain
        (
            "x_format",
            re.compile(
                r"^(?P<series>.+?)\s*-\s*(?P<season>\d+)x(?P<episode>\d+)"
                r"(?:\s*-\s*(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # ShowName.101.EpisodeTitle.fountain or ShowName.10001.EpisodeTitle.fountain
        (
            "dotted_format",
            re.compile(
                r"^(?P<series>.+?)\.(?P<season>\d{1,2})(?P<episode>\d{2,3})"
                r"(?:\.(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # Season 1/Episode 01 - Title.fountain
        (
            "directory_format",
            re.compile(
                r"Episode\s*(?P<episode>\d+)(?:\s*-\s*(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # ShowName - Episode 101 - Title.fountain
        (
            "episode_number_format",
            re.compile(
                r"^(?P<series>.+?)\s*-\s*Episode\s*(?P<season>\d)(?P<episode>\d{2})"
                r"(?:\s*-\s*(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # ShowName S01E01.fountain (no title)
        (
            "simple_format",
            re.compile(
                r"^(?P<series>.+?)\s+S(?P<season>\d+)E(?P<episode>\d+)\.fountain$",
                re.IGNORECASE,
            ),
        ),
        # ShowName - Special - Title.fountain
        (
            "special_format",
            re.compile(
                r"^(?P<series>.+?)\s*-\s*Special(?:\s*-\s*(?P<title>.+?))?\.fountain$",
                re.IGNORECASE,
            ),
        ),
    ]

    # Multi-part episode patterns
    MULTIPART_PATTERNS: ClassVar[list[Pattern[str]]] = [
        re.compile(r"Part\s*(\d+|[IVX]+)", re.IGNORECASE),
        re.compile(r"Pt\s*\.?\s*(\d+|[IVX]+)", re.IGNORECASE),
        re.compile(r"\((\d+|[IVX]+)\s*of\s*\d+\)", re.IGNORECASE),
    ]

    def __init__(self, custom_pattern: str | None = None) -> None:
        """Initialize the detector with optional custom pattern.

        Args:
            custom_pattern: Custom regex pattern for series detection
        """
        self.custom_pattern = None
        if custom_pattern:
            try:
                self.custom_pattern = re.compile(custom_pattern, re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid custom pattern: {e}") from e

    def detect(self, file_path: str | Path) -> SeriesInfo:
        """Detect series information from a file path.

        Args:
            file_path: Path to the fountain file

        Returns:
            SeriesInfo with extracted metadata
        """
        file_path = Path(file_path)
        filename = file_path.name

        # Try custom pattern first
        if self.custom_pattern:
            match = self.custom_pattern.match(filename)
            if match:
                return self._extract_from_match(match, filename, file_path)

        # Try built-in patterns
        for pattern_name, pattern in self.PATTERNS:
            match = pattern.match(filename)
            if match:
                info = self._extract_from_match(match, filename, file_path)

                # For directory format, try to get series name from parent
                if pattern_name == "directory_format" and not info.series_name:
                    extracted_name = self._extract_series_from_path(file_path)
                    if extracted_name:
                        info.series_name = extracted_name

                return info

        # No pattern matched - check if it might still be a series based on path
        series_name = self._extract_series_from_path(file_path)
        if series_name:
            # Extract title from filename
            title = filename.replace(".fountain", "").strip()
            return SeriesInfo(
                series_name=series_name,
                episode_title=title,
                is_series=True,
            )

        # Not a series
        return SeriesInfo(
            series_name=filename.replace(".fountain", "").strip(),
            is_series=False,
        )

    def _extract_from_match(
        self, match: re.Match[str], filename: str, file_path: Path
    ) -> SeriesInfo:
        """Extract series info from a regex match."""
        groups = match.groupdict()

        # Extract basic info
        series_name = groups.get("series", "").strip()
        season_str = groups.get("season", "")
        episode_str = groups.get("episode", "")
        title = (groups.get("title") or "").strip()

        # Convert to integers
        season_number = int(season_str) if season_str else None
        episode_number = int(episode_str) if episode_str else None

        # Check for special episode
        is_special = "special" in filename.lower()

        # Check for multi-part episode
        multi_part = None
        if title:
            for pattern in self.MULTIPART_PATTERNS:
                part_match = pattern.search(title)
                if part_match:
                    multi_part = part_match.group(0)
                    break

        # If no series name from pattern, try to extract from path
        if not series_name:
            series_name = self._extract_series_from_path(file_path)

        return SeriesInfo(
            series_name=series_name or "Unknown Series",
            season_number=season_number,
            episode_number=episode_number,
            episode_title=title or None,
            is_series=bool(season_number or episode_number or is_special),
            is_special=is_special,
            multi_part=multi_part,
        )

    def _extract_series_from_path(self, file_path: Path) -> str | None:
        """Extract series name from directory structure."""
        # Look for common patterns in parent directories
        for parent in file_path.parents:
            parent_name = parent.name

            # Skip common directory names and temp directories
            if (
                parent_name.lower() in {"scripts", "screenplays", "fountain", ".", ".."}
                or parent_name.startswith(("tmp", "temp"))
                or len(parent_name) > 20
            ):  # Skip very long directory names (likely temp dirs)
                continue

            # Check if parent looks like a season directory
            if re.match(r"Season\s*\d+", parent_name, re.IGNORECASE):
                # Go up one more level for series name
                grandparent = parent.parent
                if grandparent and grandparent.name not in {".", ".."}:
                    return grandparent.name
            else:
                # This might be the series name
                return parent_name

        return None

    def detect_bulk(self, file_paths: list[Path]) -> dict[Path, SeriesInfo]:
        """Detect series information for multiple files.

        Args:
            file_paths: List of fountain file paths

        Returns:
            Dictionary mapping file paths to their SeriesInfo
        """
        results = {}
        for file_path in file_paths:
            results[file_path] = self.detect(file_path)
        return results

    def group_by_series(
        self, series_infos: dict[Path, SeriesInfo]
    ) -> dict[str, list[tuple[Path, SeriesInfo]]]:
        """Group files by series name.

        Args:
            series_infos: Dictionary of file paths to SeriesInfo

        Returns:
            Dictionary mapping series names to lists of (path, info) tuples
        """
        grouped: dict[str, list[tuple[Path, SeriesInfo]]] = {}
        for path, info in series_infos.items():
            series_name = info.series_name
            if series_name not in grouped:
                grouped[series_name] = []
            grouped[series_name].append((path, info))

        # Sort episodes within each series
        for series_name in grouped:
            grouped[series_name].sort(
                key=lambda x: (
                    x[1].season_number or 0,
                    x[1].episode_number or 0,
                    x[0].name,
                )
            )

        return grouped
