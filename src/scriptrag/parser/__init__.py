"""
Fountain Parser Integration

This module provides integration with the Jouvence fountain parser library
to convert Fountain screenplay files into ScriptRAG data models.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

from jouvence.parser import JouvenceParser, JouvenceParserError
from jouvence.document import JouvenceDocument, JouvenceScene, JouvenceSceneElement

from ..models import (
    Action,
    Character,
    CharacterAppears,
    CharacterSpeaksTo,
    Dialogue,
    ElementType,
    Location,
    Parenthetical,
    Scene,
    SceneAtLocation,
    SceneElement,
    SceneFollows,
    SceneOrderType,
    Script,
    Transition,
)


class FountainParsingError(Exception):
    """Exception raised when fountain parsing fails."""
    pass


class FountainParser:
    """
    Parses Fountain screenplay files and converts them to ScriptRAG data models.

    This parser uses the Jouvence library to handle the low-level fountain
    parsing and then converts the result into ScriptRAG's graph-friendly
    data models.
    """

    # Mapping from Jouvence element types to ScriptRAG ElementType
    JOUVENCE_TYPE_MAP = {
        0: ElementType.ACTION,
        1: ElementType.SCENE_HEADING,
        2: ElementType.CHARACTER,
        3: ElementType.DIALOGUE,
        4: ElementType.PARENTHETICAL,
        5: ElementType.TRANSITION,
        6: ElementType.SHOT,
        7: ElementType.BONEYARD,
        8: ElementType.PAGE_BREAK,
        9: ElementType.SYNOPSIS,
        10: ElementType.SECTION,
    }

    # Regular expressions for parsing scene headings
    SCENE_HEADING_REGEX = re.compile(
        r'^(INT\.|EXT\.)\s+(.+?)(?:\s+-\s+(.+))?$',
        re.IGNORECASE
    )

    # Regular expressions for character name variations
    CHARACTER_CLEANUP_REGEX = re.compile(r'[^A-Z0-9\s]')
    CHARACTER_EXTENSION_REGEX = re.compile(r'\s*\([^)]*\)|\s*(O\.S\.|V\.O\.|CONT\'D)$', re.IGNORECASE)

    def __init__(self):
        """Initialize the fountain parser."""
        self.jouvence_parser = JouvenceParser()
        self._characters_cache: Dict[str, Character] = {}
        self._scene_count = 0

    def parse_file(self, file_path: Union[str, Path]) -> Script:
        """
        Parse a fountain file and return a Script model.

        Args:
            file_path: Path to the fountain file

        Returns:
            Script model with all parsed content

        Raises:
            FountainParsingError: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FountainParsingError(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, UnicodeDecodeError) as e:
            raise FountainParsingError(f"Failed to read file {file_path}: {e}")

        return self.parse_string(content, source_file=str(file_path))

    def parse_string(self, content: str, source_file: Optional[str] = None) -> Script:
        """
        Parse fountain content from a string and return a Script model.

        Args:
            content: Fountain screenplay content
            source_file: Optional source file path for metadata

        Returns:
            Script model with all parsed content

        Raises:
            FountainParsingError: If parsing fails
        """
        try:
            document = self.jouvence_parser.parseString(content)
        except JouvenceParserError as e:
            raise FountainParsingError(f"Fountain parsing error: {e}")
        except Exception as e:
            raise FountainParsingError(f"Unexpected parsing error: {e}")

        return self._convert_document_to_script(document, content, source_file)

    def _convert_document_to_script(
        self,
        document: JouvenceDocument,
        original_content: str,
        source_file: Optional[str] = None
    ) -> Script:
        """Convert a Jouvence document to a ScriptRAG Script model."""

        # Reset parser state
        self._characters_cache.clear()
        self._scene_count = 0

        # Extract title page metadata
        title_values = document.title_values.copy() if document.title_values else {}

        # If title page is empty, try to extract from first scene content
        if not title_values and document.scenes and document.scenes[0].paragraphs:
            first_scene = document.scenes[0]
            if not first_scene.header:  # First scene with no header likely contains title page
                first_paragraph = first_scene.paragraphs[0]
                if first_paragraph.type == 0:  # ACTION type
                    title_values = self._extract_title_from_text(first_paragraph.text)

        # Create the script entity
        script = Script(
            title=self._extract_title(title_values) or 'Untitled Script',
            fountain_source=original_content,
            source_file=source_file,
            title_page=title_values,
            author=title_values.get('Author') or title_values.get('author'),
            description=title_values.get('Description') or title_values.get('description'),
            genre=title_values.get('Genre') or title_values.get('genre'),
            logline=title_values.get('Logline') or title_values.get('logline'),
        )

        # Parse all scenes
        scenes = self._parse_scenes(document.scenes, script.id)
        script.scenes = [scene.id for scene in scenes]

        # Extract all characters
        characters = list(self._characters_cache.values())
        script.characters = [char.id for char in characters]

        return script

    def _extract_title(self, title_values: Dict[str, str]) -> str:
        """Extract script title from title page metadata."""
        title = title_values.get('Title', '').strip()
        if not title:
            # Try alternative title fields (Jouvence uses lowercase keys)
            title = (
                title_values.get('title', '') or
                title_values.get('TITLE', '') or
                ''
            )
        return title.strip() if title else ''

    def _parse_scenes(self, jouvence_scenes: List[JouvenceScene], script_id: UUID) -> List[Scene]:
        """Parse all scenes from the Jouvence document."""
        scenes = []

        for scene_index, jouvence_scene in enumerate(jouvence_scenes):
            # Skip the first "scene" if it has no header (title page content)
            if scene_index == 0 and not jouvence_scene.header:
                continue

            scene = self._parse_single_scene(jouvence_scene, script_id, scene_index)
            if scene:
                scenes.append(scene)

        return scenes

    def _parse_single_scene(
        self,
        jouvence_scene: JouvenceScene,
        script_id: UUID,
        scene_index: int
    ) -> Optional[Scene]:
        """Parse a single scene from Jouvence format."""

        self._scene_count += 1

        # Parse location from scene heading
        location = None
        if jouvence_scene.header:
            location = self._parse_location(jouvence_scene.header)

        # Create the scene
        scene = Scene(
            location=location,
            heading=jouvence_scene.header,
            script_order=self._scene_count,
            script_id=script_id,
        )

        # Parse scene elements
        elements = []
        scene_characters = set()

        for element_index, jouvence_element in enumerate(jouvence_scene.paragraphs):
            element, character_ids = self._parse_scene_element(
                jouvence_element,
                scene.id,
                element_index
            )
            if element:
                elements.append(element)
                scene_characters.update(character_ids)

        scene.elements = elements
        scene.characters = list(scene_characters)

        return scene

    def _parse_location(self, scene_heading: str) -> Optional[Location]:
        """Parse location information from a scene heading."""
        match = self.SCENE_HEADING_REGEX.match(scene_heading.strip())
        if not match:
            return None

        int_ext, location_name, time = match.groups()

        return Location(
            interior=int_ext.upper() == 'INT.',
            name=location_name.strip(),
            time=time.strip() if time else None,
            raw_text=scene_heading,
        )

    def _parse_scene_element(
        self,
        jouvence_element: JouvenceSceneElement,
        scene_id: UUID,
        order: int
    ) -> Tuple[Optional[SceneElement], Set[UUID]]:
        """
        Parse a single scene element from Jouvence format.

        Returns:
            Tuple of (element, set of character IDs referenced)
        """
        element_type = self.JOUVENCE_TYPE_MAP.get(jouvence_element.type)
        if not element_type:
            return None, set()

        text = jouvence_element.text.strip()
        if not text:
            return None, set()

        character_ids = set()

        # Create appropriate element type
        if element_type == ElementType.ACTION:
            # Extract character mentions from action text
            character_ids = self._extract_character_mentions_from_action(text)
            element = Action(
                text=text,
                raw_text=jouvence_element.text,
                scene_id=scene_id,
                order_in_scene=order,
            )

        elif element_type == ElementType.DIALOGUE:
            # For dialogue, we need the previous element to be a character
            element = Dialogue(
                text=text,
                raw_text=jouvence_element.text,
                scene_id=scene_id,
                order_in_scene=order,
                character_id=uuid4(),  # Will be updated by caller
                character_name="UNKNOWN",  # Will be updated by caller
            )

        elif element_type == ElementType.CHARACTER:
            # Character name - this indicates who speaks next
            character = self._get_or_create_character(text)
            character_ids.add(character.id)

            # We don't create a separate element for character names
            # They're handled as metadata for dialogue
            return None, character_ids

        elif element_type == ElementType.PARENTHETICAL:
            element = Parenthetical(
                text=text,
                raw_text=jouvence_element.text,
                scene_id=scene_id,
                order_in_scene=order,
            )

        elif element_type == ElementType.TRANSITION:
            element = Transition(
                text=text,
                raw_text=jouvence_element.text,
                scene_id=scene_id,
                order_in_scene=order,
            )

        else:
            # Handle other element types as actions for now
            element = Action(
                text=text,
                raw_text=jouvence_element.text,
                scene_id=scene_id,
                order_in_scene=order,
            )

        return element, character_ids

    def _get_or_create_character(self, character_text: str) -> Character:
        """Get or create a character from character name text."""
        # Clean up character name
        clean_name = self._clean_character_name(character_text)

        # Check cache
        if clean_name in self._characters_cache:
            character = self._characters_cache[clean_name]
            # Add alias if the original text was different and not already in aliases
            original_text = character_text.strip()
            if original_text.upper() != clean_name and original_text not in character.aliases:
                character.aliases.append(original_text)
            return character

        # Create new character
        character = Character(name=clean_name)

        # Add aliases if the original text was different
        if character_text.strip().upper() != clean_name:
            character.aliases.append(character_text.strip())

        self._characters_cache[clean_name] = character
        return character

    def _clean_character_name(self, character_text: str) -> str:
        """Clean and normalize character name."""
        # Remove extensions like (O.S.), (V.O.), (CONT'D)
        name = self.CHARACTER_EXTENSION_REGEX.sub('', character_text).strip()

        # Remove non-alphanumeric characters except spaces
        name = self.CHARACTER_CLEANUP_REGEX.sub('', name)

        # Normalize whitespace and convert to uppercase
        name = ' '.join(name.split()).upper()

        return name

    def _extract_character_mentions_from_action(self, action_text: str) -> Set[UUID]:
        """Extract character mentions from action text."""
        character_ids = set()

        # Simple heuristic: look for words in ALL CAPS that might be character names
        words = action_text.split()
        for word in words:
            # Skip common action words
            if word.upper() in {'THE', 'AND', 'OR', 'BUT', 'TO', 'OF', 'IN', 'ON', 'AT', 'BY', 'FOR'}:
                continue

            # Check if this looks like a character name (all caps, letters only)
            if word.isupper() and word.isalpha() and len(word) > 1:
                # See if we already have this character
                clean_name = self._clean_character_name(word)
                if clean_name in self._characters_cache:
                    character_ids.add(self._characters_cache[clean_name].id)

        return character_ids

    def _extract_title_from_text(self, text: str) -> Dict[str, str]:
        """Extract title page metadata from text content."""
        title_values = {}

        # Split into lines and look for title page format
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Normalize common title page keys
                if key.lower() in ['title', 'author', 'format', 'description', 'genre', 'logline']:
                    title_values[key.lower()] = value

        return title_values


# Export the main parser class
__all__ = ["FountainParser", "FountainParsingError"]
