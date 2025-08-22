"""Scene processing utilities for Fountain parser."""

import json
import re
from typing import Any

from jouvence.document import (
    TYPE_ACTION,
    TYPE_CHARACTER,
    TYPE_DIALOG,
    TYPE_PARENTHETICAL,
)

from scriptrag.config import get_logger
from scriptrag.parser.fountain_models import Dialogue, Scene
from scriptrag.utils import ScreenplayUtils

logger = get_logger(__name__)


class SceneProcessor:
    """Process and extract information from Fountain scenes."""

    # Boneyard metadata pattern
    BONEYARD_PATTERN = re.compile(
        r"/\*\s*SCRIPTRAG-META-START\s*\n(.*?)\nSCRIPTRAG-META-END\s*\*/\n?",
        re.DOTALL,
    )

    def process_jouvence_scene(
        self,
        number: int,
        jouvence_scene: Any,
        full_content: str,
    ) -> Scene:
        """Process a jouvence scene into our Scene object."""
        heading = jouvence_scene.header if jouvence_scene.header else ""

        # Parse scene type and location from heading using ScreenplayUtils
        scene_type, location, time_of_day = ScreenplayUtils.parse_scene_heading(heading)

        # Ensure we have default values if None was returned
        scene_type = scene_type or ""
        location = location or ""
        time_of_day = time_of_day or ""

        # Extract dialogue and action lines
        dialogue_lines = []
        action_lines = []

        # Process scene elements
        i = 0
        elements = jouvence_scene.paragraphs
        while i < len(elements):
            element = elements[i]

            if element.type == TYPE_CHARACTER:
                character = element.text
                parenthetical = None
                dialogue_text = []

                # Look for parenthetical and dialogue
                j = i + 1
                while j < len(elements):
                    next_elem = elements[j]
                    if next_elem.type == TYPE_PARENTHETICAL:
                        parenthetical = next_elem.text
                        j += 1
                    elif next_elem.type == TYPE_DIALOG:
                        dialogue_text.append(next_elem.text)
                        j += 1
                    else:
                        break

                if dialogue_text:
                    dialogue_lines.append(
                        Dialogue(
                            character=character,
                            text=" ".join(dialogue_text),
                            parenthetical=parenthetical,
                        )
                    )
                i = j
            elif element.type == TYPE_ACTION:
                # Post-process action lines to extract missed characters
                # Jouvence misses characters with apostrophes or numbers
                processed_actions = self._extract_missed_characters(
                    element.text, dialogue_lines
                )
                action_lines.extend(processed_actions)
                i += 1
            else:
                i += 1

        # Get original scene text from content
        # This is a simplified approach - in production you might want to
        # track line numbers
        scene_start = full_content.find(heading)
        if scene_start == -1:
            original_text = heading
        else:
            # Find the next scene heading or end of file
            next_scene_pattern = re.compile(
                r"^(INT\.|EXT\.|EST\.|INT\./EXT\.|I/E\.)", re.MULTILINE
            )
            match = next_scene_pattern.search(full_content, scene_start + len(heading))
            scene_end = match.start() if match else len(full_content)
            original_text = full_content[scene_start:scene_end].rstrip()

        # Extract boneyard metadata if present
        boneyard_metadata = None
        boneyard_match = self.BONEYARD_PATTERN.search(original_text)
        if boneyard_match:
            try:
                boneyard_metadata = json.loads(boneyard_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse boneyard JSON: {e}")

        # Build full content (for analysis)
        content_lines_list = [heading]
        content_lines_list.extend(action_lines)
        for dialogue in dialogue_lines:
            content_lines_list.append(dialogue.character)
            if dialogue.parenthetical:
                content_lines_list.append(dialogue.parenthetical)
            content_lines_list.append(dialogue.text)

        # Calculate content hash (excluding boneyard)
        content_hash = ScreenplayUtils.compute_scene_hash(original_text, truncate=True)

        return Scene(
            number=number,
            heading=heading,
            content="\n".join(content_lines_list),
            original_text=original_text,
            content_hash=content_hash,
            type=scene_type,
            location=location.strip(),
            time_of_day=time_of_day.strip(),
            dialogue_lines=dialogue_lines,
            action_lines=action_lines,
            boneyard_metadata=boneyard_metadata,
        )

    def update_scene_boneyard(
        self, content: str, scene_text: str, metadata: dict[str, Any]
    ) -> str:
        """Update or insert boneyard metadata for a scene.

        Args:
            content: Full file content
            scene_text: Original scene text
            metadata: New metadata to add

        Returns:
            Updated content
        """
        scene_start = content.find(scene_text)
        if scene_start == -1:
            logger.warning("Could not find scene in content for boneyard update")
            return content

        # Check if scene already has boneyard
        existing_boneyard = self.BONEYARD_PATTERN.search(scene_text)

        if existing_boneyard:
            # Merge with existing metadata
            try:
                existing_data = json.loads(existing_boneyard.group(1))
                existing_data.update(metadata)
                metadata = existing_data
            except json.JSONDecodeError:
                pass

            # Replace existing boneyard
            boneyard_json = json.dumps(metadata, indent=2)
            new_boneyard = (
                f"/* SCRIPTRAG-META-START\n{boneyard_json}\nSCRIPTRAG-META-END */\n"
            )
            updated_scene = self.BONEYARD_PATTERN.sub(new_boneyard, scene_text)
        else:
            # Add new boneyard at the end of scene
            boneyard_json = json.dumps(metadata, indent=2)
            new_boneyard = (
                f"/* SCRIPTRAG-META-START\n{boneyard_json}\nSCRIPTRAG-META-END */\n"
            )
            updated_scene = scene_text.rstrip() + "\n\n" + new_boneyard

        # Replace scene in content
        return (
            content[:scene_start]
            + updated_scene
            + content[scene_start + len(scene_text) :]
        )

    def _extract_missed_characters(
        self, text: str, existing_dialogue: list[Dialogue]
    ) -> list[str]:
        """Extract character lines that jouvence might have missed.

        Jouvence sometimes misses character names with apostrophes or numbers.
        This method checks for patterns like all-caps lines that could be characters.

        Args:
            text: The action text to check
            existing_dialogue: Already found dialogue to avoid duplicates

        Returns:
            List of action lines (potentially with extracted dialogue moved)
        """
        lines = text.split("\n")
        result = []

        # Track existing character names to avoid duplicates
        existing_chars = {d.character for d in existing_dialogue}

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check if this looks like a character line
            if (
                self._is_character_line(line)
                and line not in existing_chars
                and i + 1 < len(lines)
            ):
                # Look ahead to find potential dialogue after optional parenthetical
                j = i + 1
                parenthetical = None
                dialogue_text = []

                # Check for parenthetical
                if j < len(lines) and lines[j].strip().startswith("("):
                    parenthetical = lines[j].strip()
                    j += 1

                # Collect dialogue lines
                while j < len(lines):
                    potential_dialogue = lines[j].strip()
                    if not potential_dialogue:
                        break
                    # Stop if we hit another character line or action
                    if self._is_character_line(potential_dialogue):
                        break
                    dialogue_text.append(potential_dialogue)
                    j += 1

                # If we found dialogue, create the dialogue entry
                if dialogue_text:
                    existing_dialogue.append(
                        Dialogue(
                            character=line,
                            text=" ".join(dialogue_text),
                            parenthetical=parenthetical,
                        )
                    )
                    i = j  # Skip all processed lines
                    continue

            # Otherwise treat as action
            if line:
                result.append(line)
            i += 1

        return result

    def _is_character_line(self, line: str) -> bool:
        """Check if a line looks like a character name.

        Character lines in Fountain are:
        - All uppercase
        - May contain apostrophes, numbers, periods
        - Often followed by dialogue

        Args:
            line: The line to check

        Returns:
            True if line looks like a character name
        """
        if not line or len(line) > 50:  # Character names shouldn't be too long
            return False

        # Check if it's a scene heading or screenplay directive (not a character)
        line_upper = line.strip().upper()
        if line_upper.startswith(("INT.", "EXT.", "I/E.", "INT/EXT")):
            return False

        # Check for common screenplay transitions and directions
        if line_upper.startswith(
            ("FADE IN:", "FADE OUT", "CUT TO:", "MONTAGE", "INTERCUT")
        ):
            return False

        # Remove valid character name punctuation for checking (including hyphens)
        cleaned = re.sub(r"['\.\(\)0-9\s-]", "", line)

        # Check if remaining text is all uppercase letters
        return cleaned.isupper() and len(cleaned) > 1
