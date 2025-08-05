"""Fountain screenplay format parser using jouvence library."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import jouvence
from jouvence.parser import FountainElement

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
        fountain_doc = jouvence.Fountain(content)
        
        # Extract title and author from metadata
        title = fountain_doc.title_page.get("Title") if fountain_doc.title_page else None
        author = fountain_doc.title_page.get("Author") if fountain_doc.title_page else None
        
        # Find all scene headings and process scenes
        scenes = []
        scene_number = 0
        current_scene_elements = []
        current_scene_heading = None
        current_scene_start_pos = 0
        
        for i, element in enumerate(fountain_doc.elements):
            if element.element_type == "Scene Heading":
                # Process previous scene if exists
                if current_scene_heading is not None:
                    scene = self._process_scene_elements(
                        scene_number,
                        current_scene_heading,
                        current_scene_elements,
                        content,
                        current_scene_start_pos,
                        element.original_line,
                    )
                    scenes.append(scene)
                
                # Start new scene
                scene_number += 1
                current_scene_heading = element
                current_scene_elements = []
                current_scene_start_pos = element.original_line
            else:
                # Add element to current scene
                current_scene_elements.append(element)
        
        # Don't forget the last scene
        if current_scene_heading is not None:
            scene = self._process_scene_elements(
                scene_number,
                current_scene_heading,
                current_scene_elements,
                content,
                current_scene_start_pos,
                len(content.splitlines()),
            )
            scenes.append(scene)
        
        return Script(title=title, author=author, scenes=scenes)

    def parse_file(self, file_path: Path) -> Script:
        """Parse a Fountain file.

        Args:
            file_path: Path to the Fountain file

        Returns:
            Parsed Script object
        """
        content = file_path.read_text(encoding="utf-8")
        script = self.parse(content)

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

    def _process_scene_elements(
        self,
        number: int,
        heading_element: FountainElement,
        elements: list[FountainElement],
        full_content: str,
        scene_start_line: int,
        scene_end_line: int,
    ) -> Scene:
        """Process scene elements into a Scene object."""
        heading = heading_element.element_text
        
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
            rest = heading[9:].strip() if heading_upper.startswith("INT./EXT.") else heading[4:].strip()
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
        
        i = 0
        while i < len(elements):
            element = elements[i]
            
            if element.element_type == "Character":
                character = element.element_text
                parenthetical = None
                dialogue_text = []
                
                # Look for parenthetical and dialogue
                j = i + 1
                while j < len(elements):
                    next_elem = elements[j]
                    if next_elem.element_type == "Parenthetical":
                        parenthetical = next_elem.element_text
                        j += 1
                    elif next_elem.element_type == "Dialogue":
                        dialogue_text.append(next_elem.element_text)
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
            elif element.element_type == "Action":
                action_lines.append(element.element_text)
                i += 1
            else:
                i += 1
        
        # Get original scene text from content
        content_lines = full_content.splitlines()
        scene_lines = content_lines[scene_start_line:scene_end_line]
        original_text = "\n".join(scene_lines)
        
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
            new_boneyard = f"/* SCRIPTRAG-META-START\n{json.dumps(metadata, indent=2)}\nSCRIPTRAG-META-END */"
            new_scene_text = self.BONEYARD_PATTERN.sub(new_boneyard, scene_text)
        else:
            # Insert new boneyard at end of scene
            new_boneyard = f"\n\n/* SCRIPTRAG-META-START\n{json.dumps(metadata, indent=2)}\nSCRIPTRAG-META-END */"
            new_scene_text = scene_text.rstrip() + new_boneyard

        # Replace in content
        content = content[:scene_start] + new_scene_text + content[scene_start + len(scene_text):]

        return content