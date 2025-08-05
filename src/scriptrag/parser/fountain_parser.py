"""Fountain screenplay format parser using jouvence library."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from jouvence.document import (
    TYPE_ACTION,
    TYPE_CHARACTER,
    TYPE_DIALOG,
    TYPE_PARENTHETICAL,
)
from jouvence.parser import JouvenceParser

from scriptrag.config import get_logger

logger = get_logger(__name__)


@dataclass
class Dialogue:
    """Represents a dialogue entry."""

    character: str
    text: str
    parenthetical: str | None = None


@dataclass
class Scene:
    """Represents a scene in a screenplay."""

    number: int
    heading: str
    content: str
    original_text: str
    content_hash: str
    type: str = "INT"  # INT or EXT
    location: str = ""
    time_of_day: str = ""
    dialogue_lines: list[Dialogue] = field(default_factory=list)
    action_lines: list[str] = field(default_factory=list)
    boneyard_metadata: dict | None = None
    has_new_metadata: bool = False

    def update_boneyard(self, metadata: dict) -> None:
        """Update the boneyard metadata for this scene."""
        if self.boneyard_metadata is None:
            self.boneyard_metadata = {}
        self.boneyard_metadata.update(metadata)
        self.has_new_metadata = True


@dataclass
class Script:
    """Represents a parsed screenplay."""

    title: str | None
    author: str | None
    scenes: list[Scene]
    metadata: dict = field(default_factory=dict)


class FountainParser:
    """Parse Fountain screenplay format using jouvence."""

    # Boneyard metadata pattern
    BONEYARD_PATTERN = re.compile(
        r"/\*\s*SCRIPTRAG-META-START\s*\n(.*?)\nSCRIPTRAG-META-END\s*\*/",
        re.DOTALL,
    )

    def parse(self, content: str) -> Script:
        """Parse Fountain content into structured format.

        Args:
            content: Raw Fountain text

        Returns:
            Parsed Script object with scenes
        """
        # Parse using jouvence
        parser = JouvenceParser()
        # Create a StringIO object from the content string
        doc = parser.parse(StringIO(content))

        # Extract title and author from metadata
        title = doc.title_values.get("title") if doc.title_values else None
        author = doc.title_values.get("author") if doc.title_values else None

        # Extract additional metadata
        metadata = {}
        if doc.title_values:
            # Extract episode number
            if "episode" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["episode"] = int(doc.title_values["episode"])
                except (ValueError, TypeError):
                    metadata["episode"] = doc.title_values["episode"]

            # Extract season number
            if "season" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["season"] = int(doc.title_values["season"])
                except (ValueError, TypeError):
                    metadata["season"] = doc.title_values["season"]

        # Process scenes
        scenes = []
        scene_number = 0
        for jouvence_scene in doc.scenes:
            # Skip scenes without headers (like FADE IN sections)
            if jouvence_scene.header:
                scene_number += 1
                scene = self._process_jouvence_scene(
                    scene_number, jouvence_scene, content
                )
                scenes.append(scene)

        return Script(title=title, author=author, scenes=scenes, metadata=metadata)

    def parse_file(self, file_path: Path) -> Script:
        """Parse a Fountain file.

        Args:
            file_path: Path to the Fountain file

        Returns:
            Parsed Script object
        """
        # Parse using jouvence directly with file path
        parser = JouvenceParser()
        doc = parser.parse(str(file_path))

        # Get the full content for scene processing
        content = file_path.read_text(encoding="utf-8")

        # Extract title and author from metadata
        title = doc.title_values.get("title") if doc.title_values else None
        author = doc.title_values.get("author") if doc.title_values else None

        # Extract additional metadata
        metadata = {}
        if doc.title_values:
            # Extract episode number
            if "episode" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["episode"] = int(doc.title_values["episode"])
                except (ValueError, TypeError):
                    metadata["episode"] = doc.title_values["episode"]

            # Extract season number
            if "season" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["season"] = int(doc.title_values["season"])
                except (ValueError, TypeError):
                    metadata["season"] = doc.title_values["season"]

        # Process scenes
        scenes = []
        scene_number = 0
        for jouvence_scene in doc.scenes:
            # Skip scenes without headers (like FADE IN sections)
            if jouvence_scene.header:
                scene_number += 1
                scene = self._process_jouvence_scene(
                    scene_number, jouvence_scene, content
                )
                scenes.append(scene)

        script = Script(title=title, author=author, scenes=scenes, metadata=metadata)

        # Add file metadata
        script.metadata["source_file"] = str(file_path)

        return script

    def write_with_updated_scenes(
        self, file_path: Path, script: Script, updated_scenes: list[Scene]
    ) -> None:
        """Write the script back to file with updated boneyard metadata.

        Args:
            file_path: Path to write to
            script: The script object
            updated_scenes: List of scenes with new metadata
        """
        content = file_path.read_text(encoding="utf-8")

        # Create a map of scenes by content hash for quick lookup
        updated_by_hash = {s.content_hash: s for s in updated_scenes}

        # Process each scene
        for scene in script.scenes:
            if scene.content_hash in updated_by_hash:
                updated_scene = updated_by_hash[scene.content_hash]
                if updated_scene.has_new_metadata and updated_scene.boneyard_metadata:
                    content = self._update_scene_boneyard(
                        content,
                        scene.original_text,
                        updated_scene.boneyard_metadata,
                    )

        # Write back
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Updated {len(updated_scenes)} scenes in {file_path}")

    def _process_jouvence_scene(
        self,
        number: int,
        jouvence_scene: Any,
        full_content: str,
    ) -> Scene:
        """Process a jouvence scene into our Scene object."""
        heading = jouvence_scene.header if jouvence_scene.header else ""

        # Parse scene type and location from heading
        scene_type = "INT"
        location = ""
        time_of_day = ""

        heading_upper = heading.upper()
        if heading_upper.startswith("INT."):
            scene_type = "INT"
            rest = heading[4:].strip()
        elif heading_upper.startswith("EXT."):
            scene_type = "EXT"
            rest = heading[4:].strip()
        elif heading_upper.startswith("INT./EXT.") or heading_upper.startswith("I/E."):
            scene_type = "INT/EXT"
            if heading_upper.startswith("INT./EXT."):
                rest = heading[9:].strip()
            else:
                rest = heading[4:].strip()
        else:
            rest = heading

        # Split location and time of day
        if " - " in rest:
            location, time_of_day = rest.rsplit(" - ", 1)
        else:
            location = rest

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
                action_lines.append(element.text)
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
        content_for_hash = re.sub(self.BONEYARD_PATTERN, "", original_text).strip()
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]

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

    def _update_scene_boneyard(
        self, content: str, scene_text: str, metadata: dict
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
                f"/* SCRIPTRAG-META-START\n{boneyard_json}\nSCRIPTRAG-META-END */"
            )
            new_scene_text = self.BONEYARD_PATTERN.sub(new_boneyard, scene_text)
        else:
            # Insert new boneyard at end of scene
            boneyard_json = json.dumps(metadata, indent=2)
            new_boneyard = (
                f"\n\n/* SCRIPTRAG-META-START\n{boneyard_json}\nSCRIPTRAG-META-END */"
            )
            new_scene_text = scene_text.rstrip() + new_boneyard

        # Replace in content
        return (
            content[:scene_start]
            + new_scene_text
            + content[scene_start + len(scene_text) :]
        )
