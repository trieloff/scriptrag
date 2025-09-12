"""Scene parsing utilities for extracting and processing Fountain scene content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scriptrag.config import get_logger
from scriptrag.parser import FountainParser, Scene
from scriptrag.utils import ScreenplayUtils

logger = get_logger(__name__)


@dataclass
class ParsedSceneData:
    """Container for parsed scene information."""

    scene_type: str
    location: str | None
    time_of_day: str | None
    heading: str
    content: str
    parsed_scene: Scene | None = None


class SceneParser:
    """Handles parsing and extraction of scene content."""

    def __init__(self) -> None:
        """Initialize the scene parser."""
        self.fountain_parser = FountainParser()
        self.utils = ScreenplayUtils

    def parse_scene_content(self, content: str) -> ParsedSceneData:
        """Parse scene content and extract components.

        Args:
            content: Raw scene content in Fountain format

        Returns:
            ParsedSceneData with extracted components
        """
        # Try to parse with Fountain parser
        parsed_scene = None
        try:
            parsed = self.fountain_parser.parse(content)
            parsed_scene = parsed.scenes[0] if parsed.scenes else None
        except Exception as e:
            logger.debug(f"Fountain parsing failed (will fallback to basic): {e}")

        # Extract heading (first non-empty line)
        lines = content.strip().split("\n")
        heading = lines[0] if lines else ""

        # Parse scene heading components
        scene_type, location, time_of_day = self.utils.parse_scene_heading(heading)

        # If fountain parser succeeded, use its data
        if parsed_scene:
            location = parsed_scene.location or location
            time_of_day = parsed_scene.time_of_day or time_of_day

        return ParsedSceneData(
            scene_type=scene_type,
            location=location,
            time_of_day=time_of_day,
            heading=heading,
            content=content,
            parsed_scene=parsed_scene,
        )

    def extract_scene_metadata(self, scene_data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from scene data.

        Args:
            scene_data: Dictionary containing scene information

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            "has_dialogue": False,
            "has_action": False,
            "character_count": 0,
            "dialogue_count": 0,
            "action_line_count": 0,
        }

        # Check for dialogue
        if dialogue := scene_data.get("dialogue"):
            metadata["has_dialogue"] = True
            metadata["dialogue_count"] = len(dialogue)
            # Count unique characters
            characters = {d.get("character") for d in dialogue if d.get("character")}
            metadata["character_count"] = len(characters)

        # Check for action
        if action := scene_data.get("action"):
            metadata["has_action"] = True
            metadata["action_line_count"] = len(
                [line for line in action if line.strip()]
            )

        return metadata

    def prepare_scene_for_storage(
        self, parsed_data: ParsedSceneData, scene_number: int
    ) -> dict[str, Any]:
        """Prepare parsed scene data for database storage.

        Args:
            parsed_data: Parsed scene data
            scene_number: Scene number for storage

        Returns:
            Dictionary ready for database storage
        """
        # Use parsed scene if available, otherwise construct from components
        if parsed_data.parsed_scene:
            scene = parsed_data.parsed_scene
            return {
                "scene_number": scene_number,
                "heading": scene.heading,
                "content": parsed_data.content,
                "location": scene.location,
                "time_of_day": scene.time_of_day,
                "content_hash": self.utils.compute_scene_hash(parsed_data.content),
            }

        return {
            "scene_number": scene_number,
            "heading": parsed_data.heading,
            "content": parsed_data.content,
            "location": parsed_data.location,
            "time_of_day": parsed_data.time_of_day,
            "content_hash": self.utils.compute_scene_hash(parsed_data.content),
        }

    def split_scene_content(self, content: str) -> tuple[str, str | None, str | None]:
        """Split scene content into heading, action, and dialogue.

        Args:
            content: Raw scene content

        Returns:
            Tuple of (heading, action_text, dialogue_text)
        """
        lines = content.strip().split("\n")
        if not lines:
            return "", None, None

        heading = lines[0]
        remaining_lines = lines[1:] if len(lines) > 1 else []

        if not remaining_lines:
            return heading, None, None

        # Simple heuristic: dialogue lines are uppercase or have parentheticals
        action_lines = []
        dialogue_lines = []

        for line in remaining_lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if it looks like a character name (all caps)
            if (stripped.isupper() and len(stripped.split()) <= 3) or (
                stripped.startswith("(") and stripped.endswith(")")
            ):
                dialogue_lines.append(line)
            else:
                action_lines.append(line)

        action_text = "\n".join(action_lines) if action_lines else None
        dialogue_text = "\n".join(dialogue_lines) if dialogue_lines else None

        return heading, action_text, dialogue_text

    def is_valid_scene_heading(self, heading: str) -> bool:
        """Check if a line is a valid scene heading.

        Args:
            heading: Line to check

        Returns:
            True if valid scene heading
        """
        if not heading:
            return False

        heading_upper = heading.upper().strip()
        valid_prefixes = ["INT.", "EXT.", "I/E.", "INT/EXT.", "INT ", "EXT "]
        return any(heading_upper.startswith(prefix) for prefix in valid_prefixes)

    def normalize_scene_heading(self, heading: str) -> str:
        """Normalize scene heading format.

        Args:
            heading: Raw scene heading

        Returns:
            Normalized heading
        """
        if not heading:
            return ""

        # Ensure proper capitalization of INT/EXT
        heading = heading.strip()
        heading_lower = heading.lower()

        # First normalize spaces around the period for prefixes
        # This handles cases like "int ." or "ext  ."
        heading_lower_normalized = re.sub(
            r"(int|ext|i/e|int/ext)\s*\.", r"\1.", heading_lower
        )

        for prefix in ["int.", "ext.", "i/e.", "int/ext."]:
            if heading_lower_normalized.startswith(prefix):
                # Find where the prefix actually ends in the original heading
                # by looking for the pattern with optional spaces
                pattern = prefix.replace(".", r"\s*\.")
                match = re.match(pattern, heading_lower)
                if match:
                    # Replace the matched prefix with the normalized uppercase version
                    heading = prefix.upper() + heading[match.end() :]
                    break

        # Ensure single space after period
        heading = re.sub(r"\.\s+", ". ", heading)
        return re.sub(r"\s+", " ", heading)
