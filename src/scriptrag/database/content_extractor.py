"""Content extraction for embedding generation.

This module provides functions to extract meaningful text content from
screenplay elements for embedding generation. It handles various types
of screenplay content including scenes, characters, dialogue, and actions.
"""

from scriptrag.config import get_logger
from scriptrag.models import ElementType

from .connection import DatabaseConnection
from .embeddings import EmbeddingContent

logger = get_logger(__name__)


class ContentExtractor:
    """Extracts text content from screenplay elements for embedding generation."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize content extractor.

        Args:
            connection: Database connection instance
        """
        self.connection = connection

    def extract_scene_content(self, scene_id: str) -> list[EmbeddingContent]:
        """Extract content from a scene for embedding.

        Args:
            scene_id: Scene ID to extract content from

        Returns:
            List of content items ready for embedding
        """
        contents: list[EmbeddingContent] = []

        try:
            # Get scene details
            scene_row = self.connection.fetch_one(
                "SELECT * FROM scenes WHERE id = ?", (scene_id,)
            )

            if not scene_row:
                logger.warning("Scene not found", scene_id=scene_id)
                return contents

            # Extract scene heading and description
            scene_text_parts = []
            if scene_row["heading"]:
                scene_text_parts.append(f"SCENE: {scene_row['heading']}")
            if scene_row["description"]:
                scene_text_parts.append(f"DESCRIPTION: {scene_row['description']}")

            # Get all scene elements
            elements_rows = self.connection.fetch_all(
                """
                SELECT * FROM scene_elements
                WHERE scene_id = ?
                ORDER BY order_in_scene
                """,
                (scene_id,),
            )

            # Organize elements by type
            actions = []
            dialogues = []
            all_text = []

            for element in elements_rows:
                element_text = element["text"]
                element_type = element["element_type"]

                if element_type == ElementType.ACTION.value:
                    actions.append(element_text)
                elif element_type == ElementType.DIALOGUE.value:
                    character_name = (
                        element["character_name"]
                        if element["character_name"]
                        else "UNKNOWN"
                    )
                    dialogues.append(f"{character_name}: {element_text}")

                all_text.append(element_text)

            # Create scene overview embedding
            if scene_text_parts or all_text:
                full_scene_text = "\n".join(scene_text_parts + all_text)
                contents.append(
                    EmbeddingContent(
                        entity_type="scene",
                        entity_id=scene_id,
                        content=full_scene_text,
                        metadata={
                            "scene_order": (
                                scene_row["script_order"]  # noqa: SIM401
                                if "script_order" in scene_row
                                else None
                            ),
                            "location_id": (
                                scene_row["location_id"]  # noqa: SIM401
                                if "location_id" in scene_row
                                else None
                            ),
                            "element_count": len(elements_rows),
                        },
                    )
                )

            # Create action summary embedding
            if actions:
                action_text = "\n".join(actions)
                contents.append(
                    EmbeddingContent(
                        entity_type="scene_action",
                        entity_id=scene_id,
                        content=action_text,
                        metadata={
                            "scene_id": scene_id,
                            "action_count": len(actions),
                        },
                    )
                )

            # Create dialogue summary embedding
            if dialogues:
                dialogue_text = "\n".join(dialogues)
                contents.append(
                    EmbeddingContent(
                        entity_type="scene_dialogue",
                        entity_id=scene_id,
                        content=dialogue_text,
                        metadata={
                            "scene_id": scene_id,
                            "dialogue_count": len(dialogues),
                        },
                    )
                )

            logger.debug(
                "Extracted scene content",
                scene_id=scene_id,
                content_items=len(contents),
            )

        except Exception as e:
            logger.error(
                "Failed to extract scene content",
                scene_id=scene_id,
                error=str(e),
            )

        return contents

    def extract_character_content(self, character_id: str) -> list[EmbeddingContent]:
        """Extract content from a character for embedding.

        Args:
            character_id: Character ID to extract content from

        Returns:
            List of content items ready for embedding
        """
        contents: list[EmbeddingContent] = []

        try:
            # Get character details
            char_row = self.connection.fetch_one(
                "SELECT * FROM characters WHERE id = ?", (character_id,)
            )

            if not char_row:
                logger.warning("Character not found", character_id=character_id)
                return contents

            # Create character description embedding
            char_parts = [f"CHARACTER: {char_row['name']}"]
            if char_row["description"]:
                char_parts.append(f"DESCRIPTION: {char_row['description']}")

            # Get character's dialogue from all scenes
            dialogue_rows = self.connection.fetch_all(
                """
                SELECT se.text, se.scene_id, s.heading
                FROM scene_elements se
                JOIN scenes s ON se.scene_id = s.id
                WHERE se.character_id = ? AND se.element_type = 'dialogue'
                ORDER BY s.script_order, se.order_in_scene
                """,
                (character_id,),
            )

            # Collect all dialogue
            all_dialogue = []
            scene_contexts = []

            for dialogue_row in dialogue_rows:
                all_dialogue.append(dialogue_row["text"])
                if dialogue_row["heading"]:
                    scene_contexts.append(
                        f"In {dialogue_row['heading']}: {dialogue_row['text']}"
                    )

            # Create character profile embedding
            if char_parts:
                char_text = "\n".join(char_parts)
                if all_dialogue:
                    # Include sample dialogue in character description
                    sample_dialogue = all_dialogue[:5]  # First 5 lines
                    char_text += "\n\nSAMPLE DIALOGUE:\n" + "\n".join(sample_dialogue)

                contents.append(
                    EmbeddingContent(
                        entity_type="character",
                        entity_id=character_id,
                        content=char_text,
                        metadata={
                            "name": char_row["name"],
                            "dialogue_count": len(all_dialogue),
                            "scene_count": len(
                                {row["scene_id"] for row in dialogue_rows}
                            ),
                        },
                    )
                )

            # Create character dialogue embedding (if substantial)
            if len(all_dialogue) >= 3:
                dialogue_text = f"CHARACTER {char_row['name']} DIALOGUE:\n" + "\n".join(
                    all_dialogue
                )
                contents.append(
                    EmbeddingContent(
                        entity_type="character_dialogue",
                        entity_id=character_id,
                        content=dialogue_text,
                        metadata={
                            "character_id": character_id,
                            "name": char_row["name"],
                            "line_count": len(all_dialogue),
                        },
                    )
                )

            logger.debug(
                "Extracted character content",
                character_id=character_id,
                content_items=len(contents),
            )

        except Exception as e:
            logger.error(
                "Failed to extract character content",
                character_id=character_id,
                error=str(e),
            )

        return contents

    def extract_location_content(self, location_id: str) -> list[EmbeddingContent]:
        """Extract content from a location for embedding.

        Args:
            location_id: Location ID to extract content from

        Returns:
            List of content items ready for embedding
        """
        contents: list[EmbeddingContent] = []

        try:
            # Get location details
            loc_row = self.connection.fetch_one(
                "SELECT * FROM locations WHERE id = ?", (location_id,)
            )

            if not loc_row:
                logger.warning("Location not found", location_id=location_id)
                return contents

            # Get scenes at this location
            scene_rows = self.connection.fetch_all(
                """
                SELECT id, heading, description, script_order
                FROM scenes
                WHERE location_id = ?
                ORDER BY script_order
                """,
                (location_id,),
            )

            # Create location description
            loc_parts = [f"LOCATION: {loc_row['raw_text']}"]
            if loc_row["name"]:
                int_ext = "INTERIOR" if loc_row["interior"] else "EXTERIOR"
                time_desc = (
                    f" - {loc_row['time_of_day']}" if loc_row["time_of_day"] else ""
                )
                loc_parts.append(f"TYPE: {int_ext} {loc_row['name']}{time_desc}")

            # Add context from scenes at this location
            if scene_rows:
                scene_contexts = []
                for scene in scene_rows[:10]:  # Limit to prevent overly long text
                    if scene["description"]:
                        scene_contexts.append(
                            f"Scene {scene['script_order']}: {scene['description']}"
                        )

                if scene_contexts:
                    loc_parts.append("SCENE CONTEXTS:\n" + "\n".join(scene_contexts))

            if loc_parts:
                location_text = "\n".join(loc_parts)
                contents.append(
                    EmbeddingContent(
                        entity_type="location",
                        entity_id=location_id,
                        content=location_text,
                        metadata={
                            "name": loc_row["name"],
                            "interior": loc_row["interior"],
                            "time_of_day": loc_row["time_of_day"],
                            "scene_count": len(scene_rows),
                        },
                    )
                )

            logger.debug(
                "Extracted location content",
                location_id=location_id,
                content_items=len(contents),
            )

        except Exception as e:
            logger.error(
                "Failed to extract location content",
                location_id=location_id,
                error=str(e),
            )

        return contents

    def extract_script_content(self, script_id: str) -> list[EmbeddingContent]:
        """Extract summary content from a script for embedding.

        Args:
            script_id: Script ID to extract content from

        Returns:
            List of content items ready for embedding
        """
        contents: list[EmbeddingContent] = []

        try:
            # Get script details
            script_row = self.connection.fetch_one(
                "SELECT * FROM scripts WHERE id = ?", (script_id,)
            )

            if not script_row:
                logger.warning("Script not found", script_id=script_id)
                return contents

            # Create script overview
            script_parts = [f"SCRIPT: {script_row['title']}"]
            if script_row["author"]:
                script_parts.append(f"AUTHOR: {script_row['author']}")
            if script_row["genre"]:
                script_parts.append(f"GENRE: {script_row['genre']}")
            if script_row["logline"]:
                script_parts.append(f"LOGLINE: {script_row['logline']}")
            if script_row["description"]:
                script_parts.append(f"DESCRIPTION: {script_row['description']}")

            # Get character summary
            char_rows = self.connection.fetch_all(
                "SELECT name FROM characters WHERE script_id = ? ORDER BY name",
                (script_id,),
            )

            if char_rows:
                char_names = [row["name"] for row in char_rows]
                script_parts.append(f"CHARACTERS: {', '.join(char_names)}")

            # Get location summary
            loc_rows = self.connection.fetch_all(
                """
                SELECT name, COUNT(*) as scene_count
                FROM locations l
                JOIN scenes s ON l.id = s.location_id
                WHERE l.script_id = ?
                GROUP BY l.id, l.name
                ORDER BY scene_count DESC
                LIMIT 10
                """,
                (script_id,),
            )

            if loc_rows:
                location_info = [
                    f"{row['name']} ({row['scene_count']} scenes)" for row in loc_rows
                ]
                script_parts.append(f"MAIN LOCATIONS: {', '.join(location_info)}")

            if script_parts:
                script_text = "\n".join(script_parts)
                contents.append(
                    EmbeddingContent(
                        entity_type="script",
                        entity_id=script_id,
                        content=script_text,
                        metadata={
                            "title": script_row["title"],
                            "author": script_row["author"],
                            "genre": script_row["genre"],
                            "is_series": script_row["is_series"],
                            "character_count": len(char_rows),
                            "location_count": len(loc_rows),
                        },
                    )
                )

            logger.debug(
                "Extracted script content",
                script_id=script_id,
                content_items=len(contents),
            )

        except Exception as e:
            logger.error(
                "Failed to extract script content",
                script_id=script_id,
                error=str(e),
            )

        return contents

    def extract_all_script_elements(self, script_id: str) -> list[EmbeddingContent]:
        """Extract content from all elements of a script for embedding.

        Args:
            script_id: Script ID to extract all content from

        Returns:
            List of all content items ready for embedding
        """
        all_contents = []

        try:
            # Extract script overview
            all_contents.extend(self.extract_script_content(script_id))

            # Extract all characters
            char_rows = self.connection.fetch_all(
                "SELECT id FROM characters WHERE script_id = ?", (script_id,)
            )

            for char_row in char_rows:
                all_contents.extend(self.extract_character_content(char_row["id"]))

            # Extract all locations
            loc_rows = self.connection.fetch_all(
                "SELECT id FROM locations WHERE script_id = ?", (script_id,)
            )

            for loc_row in loc_rows:
                all_contents.extend(self.extract_location_content(loc_row["id"]))

            # Extract all scenes
            scene_rows = self.connection.fetch_all(
                "SELECT id FROM scenes WHERE script_id = ? ORDER BY script_order",
                (script_id,),
            )

            for scene_row in scene_rows:
                all_contents.extend(self.extract_scene_content(scene_row["id"]))

            logger.info(
                "Extracted all script content",
                script_id=script_id,
                total_content_items=len(all_contents),
                character_count=len(char_rows),
                location_count=len(loc_rows),
                scene_count=len(scene_rows),
            )

        except Exception as e:
            logger.error(
                "Failed to extract all script content",
                script_id=script_id,
                error=str(e),
            )

        return all_contents
