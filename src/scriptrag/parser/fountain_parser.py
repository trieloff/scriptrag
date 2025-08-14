"""Fountain screenplay format parser using jouvence library."""

import json
import re
from dataclasses import dataclass, field
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
from scriptrag.utils.screenplay import ScreenplayUtils

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
    boneyard_metadata: dict[str, Any] | None = None
    has_new_metadata: bool = False

    def update_boneyard(self, metadata: dict[str, Any]) -> None:
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
    metadata: dict[str, Any] = field(default_factory=dict)


class FountainParser:
    """Parse Fountain screenplay format using jouvence."""

    # Boneyard metadata pattern
    BONEYARD_PATTERN = re.compile(
        r"/\*\s*SCRIPTRAG-META-START\s*\n(.*?)\nSCRIPTRAG-META-END\s*\*/\n?",
        re.DOTALL,
    )

    def parse(self, content: str) -> Script:
        """Parse Fountain content into structured format.

        Args:
            content: Raw Fountain text

        Returns:
            Parsed Script object with scenes
        """
        # Apply the same jouvence boneyard bug workaround as in parse_file()
        # See parse_file() for detailed explanation of this workaround
        boneyard_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)
        cleaned_content = boneyard_pattern.sub("", content)

        # Parse using jouvence
        # Note: jouvence 0.4.2 has a bug where parse() with file objects
        # references an undefined variable 'fp'. Use parseString() instead.
        parser = JouvenceParser()
        doc = parser.parseString(cleaned_content)

        # Extract title and author from metadata
        title = doc.title_values.get("title") if doc.title_values else None

        # Check various author field variations
        author = None
        if doc.title_values:
            # Check all common variations of author fields
            author_fields = ["author", "authors", "writer", "writers", "written by"]
            for field in author_fields:
                if field in doc.title_values:
                    author = doc.title_values[field]
                    break

        # Extract additional metadata
        metadata = {}
        if doc.title_values:
            # Extract episode number
            if "episode" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["episode"] = int(doc.title_values["episode"])
                except (ValueError, TypeError):  # pragma: no cover
                    metadata["episode"] = doc.title_values["episode"]

            # Extract season number
            if "season" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["season"] = int(doc.title_values["season"])
                except (ValueError, TypeError):  # pragma: no cover
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
        # Get the full content for scene processing
        content = file_path.read_text(encoding="utf-8")

        # WORKAROUND for jouvence v0.4.2 infinite loop bug:
        #
        # ISSUE: The jouvence parser (v0.4.2) has a bug where it enters an infinite
        # loop when parsing certain boneyard comments. Specifically, when the parser
        # encounters boneyard comments like our SCRIPTRAG-META blocks, it gets stuck
        # in the RE_BONEYARD_END pattern matching at parser.py:540 in peekline().
        # This causes tests to hang indefinitely until they timeout.
        #
        # ROOT CAUSE: The jouvence parser's state machine for boneyard parsing has
        # a logic error that prevents it from properly detecting the end of certain
        # boneyard comment patterns, causing it to loop forever.
        #
        # WORKAROUND: We temporarily strip ALL boneyard comments (/* ... */) from
        # the content before passing it to jouvence for parsing. This prevents the
        # infinite loop from occurring. We preserve our SCRIPTRAG-META blocks by:
        # 1. First saving their locations and content
        # 2. Removing all boneyard comments for parsing
        # 3. Re-inserting our metadata after parsing completes
        #
        # This workaround can be removed once jouvence fixes the boneyard parsing bug.
        # The metadata remains intact in the original files - we only strip it during
        # the parsing phase to avoid triggering the jouvence bug.

        boneyard_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)
        scriptrag_metadata_blocks = []
        cleaned_content = content

        # First, save our ScriptRAG metadata blocks
        for match in self.BONEYARD_PATTERN.finditer(content):
            scriptrag_metadata_blocks.append(
                (match.start(), match.end(), match.group(0))
            )

        # Then remove ALL boneyard comments to avoid the jouvence bug
        cleaned_content = boneyard_pattern.sub("", cleaned_content)

        # Parse using jouvence with parseString to avoid file path issues
        logger.debug(f"Parsing fountain file: {file_path}")
        parser = JouvenceParser()
        try:
            doc = parser.parseString(cleaned_content)
        except Exception as e:
            logger.error(f"Jouvence parser failed: {e}")
            raise

        # Extract title and author from metadata
        title = doc.title_values.get("title") if doc.title_values else None

        # Check various author field variations
        author = None
        if doc.title_values:
            # Check all common variations of author fields
            author_fields = ["author", "authors", "writer", "writers", "written by"]
            for field in author_fields:
                if field in doc.title_values:
                    author = doc.title_values[field]
                    break

        # Extract additional metadata
        metadata = {}
        if doc.title_values:
            # Extract episode number
            if "episode" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["episode"] = int(doc.title_values["episode"])
                except (ValueError, TypeError):  # pragma: no cover
                    metadata["episode"] = doc.title_values["episode"]

            # Extract season number
            if "season" in doc.title_values:
                try:
                    # Try to parse as int, but keep as string if it fails
                    metadata["season"] = int(doc.title_values["season"])
                except (ValueError, TypeError):  # pragma: no cover
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
        self,
        file_path: Path,
        script: Script,
        updated_scenes: list[Scene],
        dry_run: bool = False,
    ) -> None:
        """Write the script back to file with updated boneyard metadata.

        Args:
            file_path: Path to write to
            script: The script object
            updated_scenes: List of scenes with new metadata
            dry_run: If True, don't actually write (safety parameter)
        """
        # Safety check: never write in dry_run mode
        if dry_run:
            return

        content = file_path.read_text(encoding="utf-8")

        # Safety check: don't write if no scenes have new metadata
        # But still ensure newline at end of file
        if not any(getattr(s, "has_new_metadata", False) for s in updated_scenes):
            # Just ensure newline at end if needed
            if content and not content.endswith("\n"):
                content += "\n"
                file_path.write_text(content, encoding="utf-8")
            return

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

        # Write back with proper end-of-file newline
        if content and not content.endswith("\n"):
            content += "\n"
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

    def _update_scene_boneyard(
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
