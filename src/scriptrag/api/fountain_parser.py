"""Simplified Fountain parser for API usage.

This module provides a simplified Fountain parser that extracts screenplay content
directly using the Jouvence library and converts it to API-friendly models.
Unlike the full domain parser, this parser focuses on extracting scene content
and character information for REST API responses.

Key features:
- Extracts scene headings from Fountain scene headers
- Concatenates scene elements (action, dialogue, parentheticals) into scene content
- Extracts character names from CHARACTER elements that precede dialogue
- Handles graceful fallback for parsing errors
- Returns simple ScriptModel and SceneModel objects for API serialization
"""

from typing import Any

from jouvence.parser import JouvenceParser

from scriptrag.api.models import SceneModel, ScriptModel


class FountainParser:
    """Simplified Fountain parser that returns API models."""

    def __init__(self) -> None:
        """Initialize parser."""
        pass

    def parse_string(
        self, content: str, title: str | None = None, author: str | None = None
    ) -> ScriptModel:
        """Parse Fountain content and return API script model.

        Args:
            content: Fountain format content
            title: Optional title override
            author: Optional author override

        Returns:
            ScriptModel for API usage
        """
        try:
            # Parse using jouvence directly for simpler API usage
            jouvence_parser = JouvenceParser()
            document = jouvence_parser.parseString(content)

            # Extract title page metadata
            title_values = document.title_values or {}
            script_title = (
                title or self._extract_title(title_values) or "Untitled Script"
            )
            script_author = (
                author or title_values.get("Author") or title_values.get("author")
            )

            # Parse scenes
            scenes = []
            all_characters: set[str] = set()

            scene_number = 0
            for jouvence_scene in document.scenes:
                # Skip the first "scene" if it has no header (title page content)
                if not jouvence_scene.header:
                    continue

                scene_number += 1
                scene_model = self._parse_scene_for_api(jouvence_scene, scene_number)
                scenes.append(scene_model)
                all_characters.update(scene_model.characters)

            return ScriptModel(
                title=script_title,
                author=script_author,
                scenes=scenes,
                characters=all_characters,
                metadata=title_values,
            )

        except Exception as e:
            # Fallback: return minimal script with error info
            return ScriptModel(
                title=title or "Parse Error",
                author=author,
                scenes=[],
                characters=set(),
                metadata={"parse_error": str(e)},
            )

    def _parse_scene_for_api(
        self, jouvence_scene: Any, scene_number: int
    ) -> SceneModel:
        """Parse a single scene for API usage.

        Args:
            jouvence_scene: Jouvence scene object
            scene_number: Scene number in script

        Returns:
            SceneModel for API
        """
        heading = jouvence_scene.header or f"Scene {scene_number}"

        # Extract content and characters from scene elements
        content_parts = []
        characters = []
        current_character = None

        for element in jouvence_scene.paragraphs:
            element_text = element.text.strip()
            if not element_text:
                continue

            # Map Jouvence element types
            # 0: ACTION, 1: SCENE_HEADING, 2: CHARACTER, 3: DIALOGUE,
            # 4: PARENTHETICAL, 5: TRANSITION
            element_type = element.type

            if element_type == 0:  # ACTION
                content_parts.append(element_text)

            elif element_type == 2:  # CHARACTER
                current_character = self._clean_character_name(element_text)
                if current_character and current_character not in characters:
                    characters.append(current_character)

            elif element_type == 3:  # DIALOGUE
                content_parts.append(element_text)

            elif element_type == 4:  # PARENTHETICAL
                content_parts.append(f"({element_text})")

            elif element_type == 5:  # TRANSITION
                content_parts.append(element_text)

            else:  # Other types (including scene headings)
                content_parts.append(element_text)

        # Join content with newlines
        scene_content = "\n".join(content_parts) if content_parts else ""

        return SceneModel(
            scene_number=scene_number,
            heading=heading,
            content=scene_content,
            characters=characters,
        )

    def _extract_title(self, title_values: dict[str, str]) -> str:
        """Extract script title from title page metadata."""
        title = title_values.get("Title", "").strip()
        if not title:
            # Try alternative title fields
            title = title_values.get("title", "") or title_values.get("TITLE", "") or ""
        return title.strip() if title else ""

    def _clean_character_name(self, character_text: str) -> str:
        """Clean and normalize character name."""
        import re

        # Remove extensions like (O.S.), (V.O.), (CONT'D)
        name = re.sub(
            r"\s*\([^)]*\)|\s*(O\.S\.|V\.O\.|CONT'D)$",
            "",
            character_text,
            flags=re.IGNORECASE,
        ).strip()

        # Remove non-alphanumeric characters except spaces
        name = re.sub(r"[^A-Z0-9\s]", "", name)

        # Normalize whitespace and convert to uppercase
        return " ".join(name.split()).upper()
