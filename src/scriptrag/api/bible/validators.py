"""Validation utilities for bible extraction data."""

from __future__ import annotations

from typing import Any

from scriptrag.api.bible.character_bible import BibleCharacter
from scriptrag.api.bible.scene_bible import BibleScene
from scriptrag.api.bible.utils import VALID_SCENE_TYPES
from scriptrag.config import get_logger

logger = get_logger(__name__)


class BibleValidator:
    """Validates and normalizes bible extraction data.

    This class provides validation and normalization functions for
    character and scene data extracted from Bible files, ensuring
    data consistency and quality.
    """

    @staticmethod
    def validate_character(character: BibleCharacter) -> bool:
        """Validate a single BibleCharacter object.

        Checks that the character has required fields and valid data.

        Args:
            character: BibleCharacter object to validate

        Returns:
            True if character is valid, False otherwise
        """
        # Must have a canonical name
        if not character.canonical or not character.canonical.strip():
            return False

        # Canonical name should be uppercase
        if character.canonical != character.canonical.upper():
            logger.warning(
                f"Character canonical name not uppercase: {character.canonical}"
            )

        # Aliases should be a list (even if empty)
        if not isinstance(character.aliases, list):
            return False

        # Tags should be None or a list
        if character.tags is not None and not isinstance(character.tags, list):
            return False

        # Notes should be None or a string
        return character.notes is None or isinstance(character.notes, str)

    @staticmethod
    def normalize_characters(
        characters: list[BibleCharacter],
    ) -> list[BibleCharacter]:
        """Normalize and deduplicate extracted character data.

        Performs comprehensive cleanup of LLM-extracted character data including
        case normalization, deduplication by canonical name, and intelligent
        alias filtering to avoid redundant entries.

        The normalization process:
        1. Converts all names to uppercase for consistency
        2. Removes duplicate canonical names (first occurrence wins)
        3. Filters out redundant aliases (canonical name, first name only)
        4. Maintains alias order while removing duplicates

        Args:
            characters: Raw list of BibleCharacter objects from LLM extraction,
                       potentially containing duplicates and inconsistent casing

        Returns:
            Clean list of BibleCharacter objects with normalized names,
            deduplicated canonicals, and filtered aliases. Characters are
            returned in order of first appearance.
        """
        seen_canonicals = set()
        normalized = []

        for char in characters:
            # Uppercase and strip
            char.canonical = char.canonical.upper().strip()

            # Skip if duplicate canonical
            if char.canonical in seen_canonicals:
                continue
            seen_canonicals.add(char.canonical)

            # Normalize aliases
            normalized_aliases = []
            seen_aliases = {char.canonical}  # Canonical is implicitly an alias

            # Get first name from canonical for comparison
            canonical_parts = char.canonical.split()
            first_name = canonical_parts[0] if canonical_parts else ""

            for alias in char.aliases:
                alias = alias.upper().strip()
                # Skip if:
                # - Empty or already seen
                # - Matches the full canonical name
                # - Is just the first name and canonical has multiple parts
                if not alias or alias in seen_aliases or alias == char.canonical:
                    continue

                # Skip first name only if canonical has multiple parts
                if alias == first_name and len(canonical_parts) > 1:
                    continue

                normalized_aliases.append(alias)
                seen_aliases.add(alias)

            char.aliases = normalized_aliases
            normalized.append(char)

        return normalized

    @staticmethod
    def validate_bible_scene(scene: BibleScene) -> bool:
        """Validate a BibleScene object.

        Checks that the scene has required fields and valid data.

        Args:
            scene: BibleScene object to validate

        Returns:
            True if scene is valid, False otherwise
        """
        # Must have a location
        if not scene.location or not scene.location.strip():
            return False

        # Type should be INT, EXT, or INT/EXT if present
        if scene.type and scene.type.upper() not in VALID_SCENE_TYPES:
            logger.warning(f"Invalid scene type: {scene.type}")

        return True

    @staticmethod
    def validate_scene(scene: dict[str, Any]) -> bool:
        """Validate a scene dictionary.

        Checks that the scene has required fields and valid data.

        Args:
            scene: Scene dictionary to validate

        Returns:
            True if scene is valid, False otherwise
        """
        # Must have a location
        if "location" not in scene or not scene["location"]:
            return False

        # Type should be INT, EXT, or INT/EXT if present
        if scene.get("type") and scene["type"].upper() not in VALID_SCENE_TYPES:
            logger.warning(f"Invalid scene type: {scene['type']}")

        return True

    @staticmethod
    def normalize_scene(scene: dict[str, Any]) -> dict[str, Any]:
        """Normalize a scene dictionary.

        Standardizes scene data for consistency.

        Args:
            scene: Scene dictionary to normalize

        Returns:
            Normalized scene dictionary
        """
        normalized = {}

        # Uppercase location
        if "location" in scene:
            normalized["location"] = scene["location"].upper().strip()

        # Uppercase and standardize type
        if scene.get("type"):
            scene_type = scene["type"].upper().strip()
            # Standardize I/E to INT/EXT
            if scene_type == "I/E":
                scene_type = "INT/EXT"
            normalized["type"] = scene_type

        # Uppercase time if present
        if scene.get("time"):
            normalized["time"] = scene["time"].upper().strip()

        # Keep description as-is
        if "description" in scene:
            normalized["description"] = scene["description"]

        return normalized

    @staticmethod
    def validate_extraction_result(result: dict[str, Any]) -> bool:
        """Validate a complete extraction result.

        Checks the overall structure and version of an extraction result.

        Args:
            result: Extraction result dictionary to validate

        Returns:
            True if result structure is valid, False otherwise
        """
        # Must have version
        if "version" not in result:
            return False

        # Must have extracted_at timestamp
        if "extracted_at" not in result:
            return False

        # Check for expected keys (characters or scenes)
        has_characters = "characters" in result
        has_scenes = "scenes" in result

        if not has_characters and not has_scenes:
            return False

        # Validate character list if present
        if has_characters and not isinstance(result["characters"], list):
            return False

        # Validate scene list if present
        return not has_scenes or isinstance(result["scenes"], list)
