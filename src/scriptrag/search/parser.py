"""Query parser for search functionality."""

from __future__ import annotations

import re

from scriptrag.search.models import SearchMode, SearchQuery


class QueryParser:
    """Parse search queries and detect components."""

    # Patterns for detecting query components
    DIALOGUE_PATTERN = re.compile(r'"([^"]+)"')
    PARENTHETICAL_PATTERN = re.compile(r"\(([^)]+)\)")
    ALL_CAPS_PATTERN = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]+)*\b")
    EPISODE_RANGE_PATTERN = re.compile(r"s(\d+)e(\d+)(?:-s(\d+)e(\d+))?", re.IGNORECASE)

    def parse(
        self,
        query: str,
        character: str | None = None,
        dialogue: str | None = None,
        parenthetical: str | None = None,
        project: str | None = None,
        range_str: str | None = None,
        mode: SearchMode = SearchMode.AUTO,
        limit: int = 5,
        offset: int = 0,
        include_bible: bool = True,
        only_bible: bool = False,
    ) -> SearchQuery:
        """Parse a search query into components.

        Args:
            query: Raw query string
            character: Explicit character filter
            dialogue: Explicit dialogue filter
            parenthetical: Explicit parenthetical filter
            project: Project name filter
            range_str: Episode range (e.g., "s1e2-s1e5")
            mode: Search mode (strict/fuzzy/auto)
            limit: Result limit
            offset: Result offset
            include_bible: Include bible content in search
            only_bible: Search only bible content

        Returns:
            Parsed SearchQuery object
        """
        parsed = SearchQuery(
            raw_query=query,
            mode=mode,
            limit=limit,
            offset=offset,
            project=project,
            include_bible=include_bible,
            only_bible=only_bible,
        )

        # Parse episode range if provided
        if range_str:
            self._parse_range(range_str, parsed)

        # Use explicit parameters if provided
        if character:
            parsed.characters = [character.upper()]
        if dialogue:
            parsed.dialogue = dialogue
        if parenthetical:
            parsed.parenthetical = parenthetical

        # Auto-detect components from query if not explicitly provided
        if not (character or dialogue or parenthetical):
            self._auto_detect_components(query, parsed)

        return parsed

    def _auto_detect_components(self, query: str, parsed: SearchQuery) -> None:
        """Auto-detect query components from the raw query.

        Args:
            query: Raw query string
            parsed: SearchQuery object to populate
        """
        remaining_query = query

        # Extract dialogue (quoted text)
        dialogue_matches = self.DIALOGUE_PATTERN.findall(remaining_query)
        if dialogue_matches:
            # Use the first quoted string as dialogue
            parsed.dialogue = dialogue_matches[0]
            # Remove from remaining query
            remaining_query = self.DIALOGUE_PATTERN.sub("", remaining_query)

        # Extract parentheticals
        parenthetical_matches = self.PARENTHETICAL_PATTERN.findall(remaining_query)
        if parenthetical_matches:
            # Use the first parenthetical
            parsed.parenthetical = parenthetical_matches[0]
            # Remove from remaining query
            remaining_query = self.PARENTHETICAL_PATTERN.sub("", remaining_query)

        # Extract ALL CAPS words (characters/locations)
        caps_matches = self.ALL_CAPS_PATTERN.findall(remaining_query)
        for match in caps_matches:
            # Common screenplay locations
            location_keywords = {
                "INT",
                "EXT",
                "INT/EXT",
                "DAY",
                "NIGHT",
                "MORNING",
                "AFTERNOON",
                "EVENING",
                "CONTINUOUS",
                "LATER",
            }

            # Skip location keywords
            if match not in location_keywords:
                # Check if it looks like a location (multiple words)
                if " " in match:
                    parsed.locations.append(match)
                else:
                    # Single word in caps - likely a character
                    parsed.characters.append(match)

            # Remove from remaining query
            remaining_query = remaining_query.replace(match, "")

        # Whatever remains is general text/action query
        remaining_query = remaining_query.strip()
        if remaining_query:
            # Clean up extra spaces
            remaining_query = " ".join(remaining_query.split())
            if remaining_query:
                parsed.text_query = remaining_query

    def _parse_range(self, range_str: str, parsed: SearchQuery) -> None:
        """Parse episode range string.

        Args:
            range_str: Range string (e.g., "s1e2-s1e5")
            parsed: SearchQuery object to populate
        """
        match = self.EPISODE_RANGE_PATTERN.match(range_str)
        if match:
            parsed.season_start = int(match.group(1))
            parsed.episode_start = int(match.group(2))

            # Check for end range
            if match.group(3) and match.group(4):
                parsed.season_end = int(match.group(3))
                parsed.episode_end = int(match.group(4))
            else:
                # Single episode
                parsed.season_end = parsed.season_start
                parsed.episode_end = parsed.episode_start
