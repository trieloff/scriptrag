"""Fountain screenplay format parser using jouvence library."""

import re
from pathlib import Path
from typing import Any

from jouvence.parser import JouvenceParser

from scriptrag.config import get_logger
from scriptrag.exceptions import ParseError
from scriptrag.parser.fountain_models import Scene, Script
from scriptrag.parser.fountain_processor import SceneProcessor

logger = get_logger(__name__)


class FountainParser:
    """Parse Fountain screenplay format using jouvence."""

    def __init__(self) -> None:
        """Initialize the fountain parser."""
        self.processor = SceneProcessor()
        # Keep BONEYARD_PATTERN for parse_file compatibility
        self.BONEYARD_PATTERN = self.processor.BONEYARD_PATTERN

    def _apply_jouvence_workaround(self, content: str) -> str:
        """Apply workaround for jouvence v0.4.2 infinite loop bug.

        ISSUE: The jouvence parser (v0.4.2) has a bug where it enters an infinite
        loop when parsing certain boneyard comments. Specifically, when the parser
        encounters boneyard comments like our SCRIPTRAG-META blocks, it gets stuck
        in the RE_BONEYARD_END pattern matching at parser.py:540 in peekline().
        This causes tests to hang indefinitely until they timeout.

        ROOT CAUSE: The jouvence parser's state machine for boneyard parsing has
        a logic error that prevents it from properly detecting the end of certain
        boneyard comment patterns, causing it to loop forever.

        WORKAROUND: We temporarily strip ALL boneyard comments (/* ... */) from
        the content before passing it to jouvence for parsing. This prevents the
        infinite loop from occurring.

        This workaround can be removed once jouvence fixes the boneyard parsing bug.

        Args:
            content: Raw Fountain text

        Returns:
            Content with boneyard comments removed
        """
        boneyard_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)
        return boneyard_pattern.sub("", content)

    def _extract_doc_metadata(
        self, doc: Any
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        """Extract metadata from parsed jouvence document.

        Args:
            doc: Parsed jouvence document

        Returns:
            Tuple of (title, author, metadata_dict)
        """
        # Extract title
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
        metadata: dict[str, Any] = {}
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

            # Extract series title (for TV scripts)
            if "series" in doc.title_values:
                metadata["series_title"] = doc.title_values["series"]
            elif "series_title" in doc.title_values:
                metadata["series_title"] = doc.title_values["series_title"]
            elif "show" in doc.title_values:
                metadata["series_title"] = doc.title_values["show"]

            # Extract project title (for grouping multiple drafts)
            if "project" in doc.title_values:
                metadata["project_title"] = doc.title_values["project"]
            elif "project_title" in doc.title_values:
                metadata["project_title"] = doc.title_values["project_title"]

        return title, author, metadata

    def _process_scenes(self, doc: Any, content: str) -> list[Scene]:
        """Process scenes from parsed jouvence document.

        Args:
            doc: Parsed jouvence document
            content: Original content for scene text extraction

        Returns:
            List of processed Scene objects
        """
        scenes = []
        scene_number = 0
        for jouvence_scene in doc.scenes:
            # Skip scenes without headers (like FADE IN sections)
            if jouvence_scene.header:
                scene_number += 1
                scene = self.processor.process_jouvence_scene(
                    scene_number, jouvence_scene, content
                )
                scenes.append(scene)
        return scenes

    def parse(self, content: str) -> Script:
        """Parse Fountain content into structured format.

        Args:
            content: Raw Fountain text

        Returns:
            Parsed Script object with scenes
        """
        # Apply jouvence workaround to avoid infinite loop bug
        cleaned_content = self._apply_jouvence_workaround(content)

        # Parse using jouvence
        # Note: jouvence 0.4.2 has a bug where parse() with file objects
        # references an undefined variable 'fp'. Use parseString() instead.
        parser = JouvenceParser()
        doc = parser.parseString(cleaned_content)

        # Extract metadata using helper method
        title, author, metadata = self._extract_doc_metadata(doc)

        # Process scenes using helper method
        scenes = self._process_scenes(doc, content)

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

        # Apply jouvence workaround to avoid infinite loop bug
        cleaned_content = self._apply_jouvence_workaround(content)

        # Parse using jouvence with parseString to avoid file path issues
        logger.debug(f"Parsing fountain file: {file_path}")
        parser = JouvenceParser()
        try:
            doc = parser.parseString(cleaned_content)
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error(f"Jouvence parser failed: {e}")
            raise ParseError(
                message=f"Failed to parse Fountain file: {file_path}",
                hint="Check Fountain syntax and format.",
                details={
                    "file": str(file_path),
                    "parser_error": str(e),
                    "issues": "Unclosed notes, invalid headings, bad title",
                },
            ) from e

        # Extract metadata using helper method
        title, author, metadata = self._extract_doc_metadata(doc)

        # Process scenes using helper method
        scenes = self._process_scenes(doc, content)

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
                    content = self.processor.update_scene_boneyard(
                        content,
                        scene.original_text,
                        updated_scene.boneyard_metadata,
                    )

        # Write back with proper end-of-file newline
        if content and not content.endswith("\n"):
            content += "\n"
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Updated {len(updated_scenes)} scenes in {file_path}")
