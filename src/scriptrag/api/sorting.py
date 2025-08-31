"""Script sorting utilities for ScriptRAG."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriptrag.api.list import FountainMetadata


def sort_scripts(scripts: list[FountainMetadata]) -> list[FountainMetadata]:
    """Sort scripts by season, episode, then title.

    Scripts are sorted with the following priority:
    1. Season number (ascending, None values last)
    2. Episode number (ascending, None values last)
    3. Title (alphabetical, as tie-breaker)

    This ensures that episodes in a series are displayed in proper viewing order,
    regardless of their titles.

    Args:
        scripts: List of FountainMetadata objects to sort

    Returns:
        Sorted list of FountainMetadata objects
    """

    def sort_key(script: FountainMetadata) -> tuple:
        """Generate sort key for a script.

        Returns a tuple that ensures proper ordering:
        - Season/episode numbers use 999999 for None to sort them last
        - Title uses empty string for None
        """
        season = script.season_number if script.season_number is not None else 999999
        episode = script.episode_number if script.episode_number is not None else 999999
        title = script.title or script.file_path.stem or ""

        return (season, episode, title.lower())

    return sorted(scripts, key=sort_key)
