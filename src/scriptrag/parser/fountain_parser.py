"""Fountain screenplay format parser."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

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
    """Parse Fountain screenplay format."""

    # Scene heading pattern
    SCENE_PATTERN = re.compile(
        r"^(INT\.|EXT\.|EST\.|INT\./EXT\.|I/E\.)\s*(.+?)(?:\s*-\s*(.+))?$",
        re.IGNORECASE | re.MULTILINE,
    )

    # Character name pattern (all caps, possibly with extension)
    CHARACTER_PATTERN = re.compile(r"^([A-Z][A-Z\s]+)(?:\s*\(.+\))?$")

    # Parenthetical pattern
    PARENTHETICAL_PATTERN = re.compile(r"^\(.+\)$")

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
        # Extract title page metadata
        title, author, title_end = self._parse_title_page(content)

        # Find all scenes
        scenes = []
        scene_matches = list(self.SCENE_PATTERN.finditer(content[title_end:]))

        for i, match in enumerate(scene_matches):
            scene_start = match.start() + title_end
            scene_end = (
                scene_matches[i + 1].start() + title_end
                if i + 1 < len(scene_matches)
                else len(content)
            )

            scene_text = content[scene_start:scene_end]
            scene = self._parse_scene(i + 1, scene_text, match)
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

    def _parse_title_page(self, content: str) -> tuple[str | None, str | None, int]:
        """Parse title page metadata.

        Returns:
            Tuple of (title, author, end_position)
        """
        title = None
        author = None

        # Title page ends at first blank line
        title_page_end = content.find("\n\n")
        if title_page_end == -1:
            return None, None, 0

        title_page = content[:title_page_end]

        # Simple pattern matching for title and author
        for line in title_page.split("\n"):
            if line.startswith("Title:"):
                title = line[6:].strip()
            elif line.startswith("Author:"):
                author = line[7:].strip()

        return title, author, title_page_end

    def _parse_scene(self, number: int, scene_text: str, match: re.Match) -> Scene:
        """Parse individual scene."""
        # Extract scene heading components
        scene_type = match.group(1).rstrip(".").upper()
        location = match.group(2).strip() if match.group(2) else ""
        time_of_day = match.group(3).strip() if match.group(3) else ""
        heading = match.group(0)

        # Extract boneyard metadata if present
        boneyard_match = self.BONEYARD_PATTERN.search(scene_text)
        boneyard_metadata = None
        if boneyard_match:
            try:
                boneyard_metadata = json.loads(boneyard_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse boneyard JSON: {e}")

        # Parse dialogue and action
        dialogue_lines = []
        action_lines = []

        lines = scene_text.split("\n")[1:]  # Skip heading
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and boneyard
            if not line or line.startswith("/*"):
                i += 1
                continue

            # Check for character name
            if self.CHARACTER_PATTERN.match(line):
                character = line
                i += 1

                # Check for parenthetical
                parenthetical = None
                if i < len(lines) and self.PARENTHETICAL_PATTERN.match(
                    lines[i].strip()
                ):
                    parenthetical = lines[i].strip()
                    i += 1

                # Collect dialogue lines
                dialogue_text = []
                while i < len(lines) and lines[i].strip() and not self.CHARACTER_PATTERN.match(lines[i].strip()):
                    dialogue_text.append(lines[i].strip())
                    i += 1

                if dialogue_text:
                    dialogue_lines.append(
                        Dialogue(
                            character=character,
                            text=" ".join(dialogue_text),
                            parenthetical=parenthetical,
                        )
                    )
            else:
                # It's an action line
                if line:
                    action_lines.append(line)
                i += 1

        # Calculate content hash (excluding boneyard)
        content_for_hash = re.sub(
            self.BONEYARD_PATTERN, "", scene_text
        ).strip()
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]

        # Build full content (for analysis)
        content_lines = [heading]
        content_lines.extend(action_lines)
        for dialogue in dialogue_lines:
            content_lines.append(dialogue.character)
            if dialogue.parenthetical:
                content_lines.append(dialogue.parenthetical)
            content_lines.append(dialogue.text)

        return Scene(
            number=number,
            heading=heading,
            content="\n".join(content_lines),
            original_text=scene_text,
            content_hash=content_hash,
            type=scene_type,
            location=location,
            time_of_day=time_of_day,
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