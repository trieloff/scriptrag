"""Character relationships analyzer for ScriptRAG."""

from __future__ import annotations

import re
from typing import Any

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger

logger = get_logger(__name__)


class CharacterRelationshipsAnalyzer(BaseSceneAnalyzer):
    """Analyzes character relationships within scenes.

    This analyzer uses Bible-extracted character aliases to identify
    character presence, co-presence, and speaking relationships in scenes.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the relationships analyzer.

        Args:
            config: Optional configuration, may contain:
                - bible_characters: Pre-loaded character alias map
        """
        super().__init__(config)
        self.bible_characters: dict[str, Any] | None = (
            config.get("bible_characters") if config else None
        )
        self.alias_to_canonical: dict[str, str] = {}
        self.alias_patterns: dict[str, re.Pattern[str]] = {}
        self._build_alias_index()

    @property
    def name(self) -> str:
        """Unique name for this analyzer."""
        return "relationships"

    @property
    def version(self) -> str:
        """Version of this analyzer."""
        return "1.0.0"

    def _build_alias_index(self) -> None:
        """Build index mapping aliases to canonical names."""
        if not self.bible_characters:
            return

        characters = self.bible_characters.get("characters", [])
        for char_data in characters:
            canonical = char_data.get("canonical", "").upper()
            if not canonical:
                continue

            # Map canonical to itself
            self.alias_to_canonical[canonical] = canonical
            self.alias_patterns[canonical] = self._create_word_boundary_pattern(
                canonical
            )

            # Map each alias to canonical
            for alias in char_data.get("aliases", []):
                alias = alias.upper()
                if alias:
                    self.alias_to_canonical[alias] = canonical
                    self.alias_patterns[alias] = self._create_word_boundary_pattern(
                        alias
                    )

    def _create_word_boundary_pattern(self, text: str) -> re.Pattern[str]:
        """Create a regex pattern for word-boundary matching.

        Args:
            text: The text to match

        Returns:
            Compiled regex pattern
        """
        # Escape special regex characters
        escaped = re.escape(text)
        # Use word boundaries, but handle dots and hyphens
        pattern = rf"\b{escaped}\b"
        return re.compile(pattern, re.IGNORECASE)

    def _normalize_speaker(self, speaker: str) -> str:
        """Normalize speaker name by removing parentheticals.

        Args:
            speaker: Raw speaker name from dialogue

        Returns:
            Normalized speaker name
        """
        # Remove common parentheticals
        normalized = re.sub(
            r"\s*\([^)]*\)\s*", "", speaker
        )  # Remove (CONT'D), (O.S.), etc.
        return normalized.upper().strip()

    def _resolve_to_canonical(self, name: str) -> str | None:
        """Resolve a name/alias to its canonical form.

        Args:
            name: Name or alias to resolve

        Returns:
            Canonical name if found, None otherwise
        """
        name_upper = name.upper()
        return self.alias_to_canonical.get(name_upper)

    def _find_mentions_in_text(self, text: str) -> set[str]:
        """Find character mentions in text using alias patterns.

        Args:
            text: Text to search (heading, action lines, etc.)

        Returns:
            Set of canonical character names mentioned
        """
        mentioned = set()

        for alias, pattern in self.alias_patterns.items():
            if pattern.search(text):
                canonical = self.alias_to_canonical.get(alias)
                if canonical:
                    mentioned.add(canonical)

        return mentioned

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze character relationships in a scene.

        Args:
            scene: Scene data containing dialogue, action, etc.

        Returns:
            Relationship metadata for the scene
        """
        # If no Bible data, return empty
        if not self.bible_characters or not self.alias_to_canonical:
            logger.debug("No Bible character data available for relationships analysis")
            return {}

        # Extract speakers from dialogue
        speaking = set()
        speaking_edges = []

        dialogue_entries = scene.get("dialogue", []) or []
        for entry in dialogue_entries:
            if isinstance(entry, dict):
                speaker = entry.get("character", "")
            else:
                # Handle simple string format
                speaker = str(entry).split(":")[0] if ":" in str(entry) else ""

            if speaker:
                normalized = self._normalize_speaker(speaker)
                canonical = self._resolve_to_canonical(normalized)
                if canonical:
                    speaking.add(canonical)

        # Find mentions in heading and action
        mentioned = set()

        heading = scene.get("heading", "")
        if heading:
            mentioned.update(self._find_mentions_in_text(heading))

        action_lines = scene.get("action", []) or []
        for action in action_lines:
            if isinstance(action, str):
                mentioned.update(self._find_mentions_in_text(action))
            elif isinstance(action, dict):
                action_text = action.get("text", "")
                if action_text:
                    mentioned.update(self._find_mentions_in_text(action_text))

        # Combine speaking and mentioned for present
        present = speaking | mentioned

        # Generate co-presence pairs (unordered, unique)
        co_presence_pairs = []
        present_list = sorted(present)  # Sort for consistent ordering
        for i, char_a in enumerate(present_list):
            for char_b in present_list[i + 1 :]:
                co_presence_pairs.append([char_a, char_b])

        # Generate speaking edges (speaker -> others present)
        for speaker in speaking:
            for other in present:
                if speaker != other:
                    speaking_edges.append([speaker, other])

        # Sort edges for consistency
        speaking_edges.sort()

        # Compute stats
        stats = {
            "present_count": len(present),
            "speaking_count": len(speaking),
        }

        return {
            "present": sorted(present),
            "speaking": sorted(speaking),
            "co_presence_pairs": co_presence_pairs,
            "speaking_edges": speaking_edges,
            "stats": stats,
        }
