"""Screenplay-specific utility functions."""

from __future__ import annotations

import hashlib
import re
from typing import Any


class ScreenplayUtils:
    """Utility functions for screenplay processing."""

    # Boneyard metadata pattern (same as in fountain_parser.py)
    BONEYARD_PATTERN = re.compile(
        r"/\*\s*SCRIPTRAG-META-START\s*\n(.*?)\nSCRIPTRAG-META-END\s*\*/\n?",
        re.DOTALL,
    )

    @staticmethod
    def extract_location(heading: str) -> str | None:
        """Extract location from scene heading.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Extracted location or None
        """
        if not heading:
            return None

        # Remove scene type prefixes
        heading_upper = heading.upper()
        rest = heading

        if heading_upper.startswith("INT./EXT."):
            rest = heading[9:].strip()
        elif (
            heading_upper.startswith("INT.")
            or heading_upper.startswith("EXT.")
            or heading_upper.startswith("I/E.")
            or heading_upper.startswith("I/E ")
            or heading_upper.startswith("INT ")
            or heading_upper.startswith("EXT ")
        ):
            rest = heading[4:].strip()

        # Extract location (everything before " - " if present)
        if " - " in rest:
            location, _ = rest.rsplit(" - ", 1)
            location = location.strip()
            # If location is empty or just whitespace, return None
            return location if location else None

        # Handle case where rest starts with "- " (time only, no location)
        if rest.strip().startswith("- "):
            return None

        # If no " - " separator, the rest is the location
        rest = rest.strip()
        return rest if rest else None

    @staticmethod
    def extract_time(heading: str) -> str | None:
        """Extract time of day from scene heading.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Extracted time or None
        """
        if not heading:
            return None

        heading_upper = heading.upper()
        last_part = heading_upper.rsplit(" - ", 1)[-1]
        if re.search(r"\bMIDNIGHT\b", last_part):
            return "NIGHT"
        time_indicators = [
            "DAY",
            "NIGHT",
            "MORNING",
            "AFTERNOON",
            "EVENING",
            "DAWN",
            "DUSK",
            "CONTINUOUS",
            "LATER",
            "MOMENTS LATER",
            "SUNSET",
            "SUNRISE",
            "NOON",
        ]

        for indicator in time_indicators:
            if re.search(rf"\b{re.escape(indicator)}\b", last_part):
                return indicator

        return None

    @staticmethod
    def parse_scene_heading(heading: str) -> tuple[str, str | None, str | None]:
        """Parse a scene heading into its components.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Tuple of (scene_type, location, time_of_day)
        """
        if not heading:
            return "", None, None

        scene_type = ""
        heading_upper = heading.upper()

        # Determine scene type (check more specific patterns first)
        if (
            heading_upper.startswith("INT./EXT.")
            or heading_upper.startswith("I/E.")
            or heading_upper.startswith("I/E ")
        ):
            scene_type = "INT/EXT"
        elif heading_upper.startswith("INT.") or heading_upper.startswith("INT "):
            scene_type = "INT"
        elif heading_upper.startswith("EXT.") or heading_upper.startswith("EXT "):
            scene_type = "EXT"

        location = ScreenplayUtils.extract_location(heading)
        time_of_day = ScreenplayUtils.extract_time(heading)

        return scene_type, location, time_of_day

    @staticmethod
    def compute_scene_hash(scene_text: str, truncate: bool = True) -> str:
        """Compute a stable hash for scene content.

        This creates a consistent hash based on the actual scene text,
        excluding any boneyard metadata.

        Args:
            scene_text: Raw scene text (may include boneyard)
            truncate: If True, truncate hash to 16 characters (default: True)

        Returns:
            Hex digest of the scene content hash (SHA256)
        """
        # Remove boneyard content before hashing
        content_for_hash = re.sub(
            ScreenplayUtils.BONEYARD_PATTERN, "", scene_text
        ).strip()
        hash_digest = hashlib.sha256(content_for_hash.encode("utf-8")).hexdigest()
        return hash_digest[:16] if truncate else hash_digest

    @staticmethod
    def strip_boneyard(scene_text: str) -> str:
        """Remove boneyard metadata from scene text.

        Args:
            scene_text: Raw scene text that may contain boneyard

        Returns:
            Scene text with boneyard removed
        """
        return re.sub(ScreenplayUtils.BONEYARD_PATTERN, "", scene_text).strip()

    @staticmethod
    def format_scene_for_prompt(scene: dict[str, Any]) -> str:
        """Format scene content for LLM prompts.

        This creates a human-readable format suitable for LLM analysis.

        Args:
            scene: Scene data dictionary

        Returns:
            Formatted scene content as a string
        """
        parts = []

        if heading := scene.get("heading"):
            parts.append(f"SCENE HEADING: {heading}")

        if action := scene.get("action"):
            parts.append("ACTION:")
            for line in action:
                if line.strip():
                    parts.append(line)

        # Only process if dialogue is a list
        if (dialogue := scene.get("dialogue")) and isinstance(dialogue, list):
            parts.append("DIALOGUE:")
            for entry in dialogue:
                # Handle both dict and string formats
                if isinstance(entry, dict):
                    character = entry.get("character", "")
                    text = entry.get("text", "")
                    if character and text:
                        parts.append(f"{character}: {text}")
                elif isinstance(entry, str):
                    # String format like "CHARACTER: text"
                    if entry.strip():
                        parts.append(entry)

        # Fallback to raw content if no structured data
        if not parts and (content := scene.get("content")):
            parts.append(content)

        return "\n".join(parts)

    @staticmethod
    def format_scene_for_embedding(scene: dict[str, Any]) -> str:
        """Format scene content for embedding generation.

        This creates a compact format optimized for embedding models.
        If original_text is provided, uses that (with boneyard removed).
        Otherwise falls back to structured data.

        Args:
            scene: Scene data dictionary

        Returns:
            Formatted text suitable for embedding generation
        """
        # Prefer original text without boneyard for most accurate representation
        if original_text := scene.get("original_text"):
            return ScreenplayUtils.strip_boneyard(original_text)

        # Fallback to structured data if no original text
        parts = []

        # Add heading
        if heading := scene.get("heading"):
            parts.append(f"Scene: {heading}")

        # Add action (compressed to single line)
        if action := scene.get("action"):
            action_text = " ".join(line.strip() for line in action if line.strip())
            if action_text:
                parts.append(f"Action: {action_text}")

        # Add dialogue (only process if dialogue is a list)
        if (dialogue := scene.get("dialogue")) and isinstance(dialogue, list):
            for entry in dialogue:
                # Handle both dict and string formats
                if isinstance(entry, dict):
                    character = entry.get("character", "")
                    text = entry.get("text", "")
                    if character and text:
                        parts.append(f"{character}: {text}")
                elif isinstance(entry, str):
                    # String format like "CHARACTER: text"
                    if entry.strip():
                        parts.append(entry)

        # Fallback to content field
        if not parts and (content := scene.get("content")):
            parts.append(content)

        return "\n".join(parts)
