"""Output formatting for bible extraction results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from scriptrag.api.bible.character_bible import BibleCharacter
from scriptrag.api.bible.scene_bible import BibleScene
from scriptrag.config import get_logger

logger = get_logger(__name__)


class BibleFormatter:
    """Formats bible extraction results for various output formats.

    This class handles the conversion of extracted bible data into
    standardized output formats suitable for database storage,
    API responses, and user presentation.
    """

    @staticmethod
    def format_character_result(
        characters: list[BibleCharacter], extracted_at: datetime | None = None
    ) -> dict[str, Any]:
        """Format character extraction results.

        Converts a list of BibleCharacter objects into a standardized
        dictionary format suitable for database storage and API responses.

        Args:
            characters: List of extracted BibleCharacter objects
            extracted_at: Optional extraction timestamp, defaults to current time

        Returns:
            Dictionary containing formatted character data with schema:
            {
                "version": 1,
                "extracted_at": "ISO timestamp",
                "characters": [...]
            }
        """
        if extracted_at is None:
            extracted_at = datetime.now()

        return {
            "version": 1,
            "extracted_at": extracted_at.isoformat(),
            "characters": [
                BibleFormatter._format_character(char) for char in characters
            ],
        }

    @staticmethod
    def _format_character(character: BibleCharacter) -> dict[str, Any]:
        """Format a single character for output.

        Args:
            character: BibleCharacter object to format

        Returns:
            Dictionary with character data
        """
        return {
            "canonical": character.canonical,
            "aliases": character.aliases,
            "tags": character.tags,
            "notes": character.notes,
        }

    @staticmethod
    def format_scene_result(
        scenes: list[BibleScene] | list[dict[str, Any]],
        extracted_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Format scene extraction results.

        Converts extracted scene data into a standardized dictionary format.
        Accepts either BibleScene objects or dictionaries for flexibility.

        Args:
            scenes: List of BibleScene objects or scene dictionaries
            extracted_at: Optional extraction timestamp, defaults to current time

        Returns:
            Dictionary containing formatted scene data with schema:
            {
                "version": 1,
                "extracted_at": "ISO timestamp",
                "scenes": [...]
            }
        """
        if extracted_at is None:
            extracted_at = datetime.now()

        formatted_scenes = []
        for scene in scenes:
            if isinstance(scene, BibleScene):
                formatted_scenes.append(BibleFormatter._format_scene(scene))
            else:
                formatted_scenes.append(scene)

        return {
            "version": 1,
            "extracted_at": extracted_at.isoformat(),
            "scenes": formatted_scenes,
        }

    @staticmethod
    def _format_scene(scene: BibleScene) -> dict[str, Any]:
        """Format a single scene for output.

        Args:
            scene: BibleScene object to format

        Returns:
            Dictionary with scene data
        """
        return {
            "location": scene.location,
            "type": scene.type,
            "time": scene.time,
            "description": scene.description,
        }

    @staticmethod
    def create_empty_result(
        result_type: str = "characters", extracted_at: datetime | None = None
    ) -> dict[str, Any]:
        """Create standardized empty result for failed extractions.

        Provides consistent structure when extraction fails due to
        missing Bible files, LLM errors, or other issues.

        Args:
            result_type: Type of result ("characters" or "scenes")
            extracted_at: Optional extraction timestamp, defaults to current time

        Returns:
            Dictionary with version 1 schema containing empty data list
            and timestamp.
        """
        if extracted_at is None:
            extracted_at = datetime.now()

        return {
            "version": 1,
            "extracted_at": extracted_at.isoformat(),
            result_type: [],
        }

    @staticmethod
    def merge_results(
        character_result: dict[str, Any] | None = None,
        scene_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge character and scene results into a combined format.

        Args:
            character_result: Optional character extraction result
            scene_result: Optional scene extraction result

        Returns:
            Combined dictionary with both character and scene data
        """
        merged = {
            "version": 1,
            "extracted_at": datetime.now().isoformat(),
        }

        if character_result:
            merged["characters"] = character_result.get("characters", [])

        if scene_result:
            merged["scenes"] = scene_result.get("scenes", [])

        return merged
