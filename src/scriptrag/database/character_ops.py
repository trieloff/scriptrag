"""Character-related operations for screenplay management.

This module handles character creation, connections, and analysis.
"""

import json
import re
from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import Character

from .connection import DatabaseConnection
from .graph import GraphDatabase, GraphNode

# Constants
MAX_CHARACTER_NAME_WORDS = 3  # Maximum words in character names

logger = get_logger(__name__)


class CharacterOperations:
    """Operations for managing characters and their relationships."""

    def __init__(self, connection: DatabaseConnection, graph: GraphDatabase) -> None:
        """Initialize character operations.

        Args:
            connection: Database connection instance
            graph: Graph database instance
        """
        self.connection = connection
        self.graph = graph

    def create_character_node(self, character: Character, script_node_id: str) -> str:
        """Create a character node in the graph.

        Args:
            character: Character model instance
            script_node_id: Parent script node ID

        Returns:
            Character node ID
        """
        # Get script entity ID from the node
        script_id = None
        try:
            script_node = self.graph.get_node(script_node_id)
            if script_node:
                script_id = (
                    script_node.properties.get("entity_id") or script_node.entity_id
                )
            else:
                logger.warning(f"Script node not found: {script_node_id}")
        except Exception as e:
            logger.warning(f"Failed to get script node: {e}")

        # Only insert into characters table if we have a valid script_id
        if script_id:
            try:
                with self.connection.transaction() as conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO characters (
                            id, script_id, name, description, aliases_json,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            str(character.id),
                            script_id,
                            character.name,
                            character.description,
                            json.dumps(character.aliases)
                            if character.aliases
                            else None,
                        ),
                    )
            except Exception as e:
                logger.warning(f"Failed to insert character into database: {e}")

        # Create character node
        character_node_id = self.graph.add_node(
            node_type="character",
            entity_id=str(character.id),
            label=character.name,
            properties={
                "description": character.description,
                "aliases": character.aliases,
            },
        )

        # Connect to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=character_node_id,
            edge_type="HAS_CHARACTER",
            properties={},
        )

        logger.info(f"Created character node: {character_node_id} for {character.name}")
        return character_node_id

    def connect_character_to_scene(
        self,
        character_node_id: str,
        scene_node_id: str,
        dialogue_count: int = 0,
    ) -> str | None:
        """Connect a character to a scene they appear in.

        Args:
            character_node_id: Character node ID
            scene_node_id: Scene node ID
            dialogue_count: Number of dialogue blocks for this character

        Returns:
            Edge ID if created
        """
        edge_id = self.graph.add_edge(
            from_node_id=character_node_id,
            to_node_id=scene_node_id,
            edge_type="appears_in",
            properties={"dialogue_count": dialogue_count},
        )

        logger.debug(
            f"Connected character {character_node_id} to scene {scene_node_id}"
        )
        return edge_id

    def connect_character_interaction(
        self,
        character1_id: str,
        character2_id: str,
        scene_node_id: str,
        interaction_type: str = "dialogue",
    ) -> str | None:
        """Create interaction edge between two characters.

        Args:
            character1_id: First character node ID
            character2_id: Second character node ID
            scene_node_id: Scene where interaction occurs
            interaction_type: Type of interaction

        Returns:
            Edge ID if created
        """
        edge_id = self.graph.add_edge(
            from_node_id=character1_id,
            to_node_id=character2_id,
            edge_type="interacts_with",
            properties={
                "scene_id": scene_node_id,
                "interaction_type": interaction_type,
            },
        )

        logger.debug(
            f"Created {interaction_type} interaction: "
            f"{character1_id} <-> {character2_id}"
        )
        return edge_id

    def get_character_scenes(self, character_node_id: str) -> list[GraphNode]:
        """Get all scenes a character appears in.

        Args:
            character_node_id: Character node ID

        Returns:
            List of scene nodes
        """
        scenes = self.graph.get_neighbors(
            character_node_id, direction="out", edge_type="appears_in"
        )
        logger.debug(f"Found {len(scenes)} scenes for character {character_node_id}")
        return scenes

    def get_character_interactions(
        self, character_node_id: str, interaction_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all character interactions for a given character.

        Args:
            character_node_id: Character node ID
            interaction_type: Optional filter by interaction type

        Returns:
            List of interaction data
        """
        # Get both incoming and outgoing interactions
        outgoing = self.graph.find_edges(
            from_node_id=character_node_id, edge_type="interacts_with"
        )
        incoming = self.graph.find_edges(
            to_node_id=character_node_id, edge_type="interacts_with"
        )

        interactions = []
        for edge in outgoing + incoming:
            if (
                interaction_type
                and edge.properties.get("interaction_type") != interaction_type
            ):
                continue

            # Get the other character
            other_char_id = (
                edge.to_node_id
                if edge.from_node_id == character_node_id
                else edge.from_node_id
            )
            other_char = self.graph.get_node(other_char_id)

            if other_char:
                interactions.append(
                    {
                        "character_id": other_char.id,
                        "character_name": other_char.label,
                        "scene_id": edge.properties.get("scene_id"),
                        "interaction_type": edge.properties.get("interaction_type"),
                    }
                )

        return interactions

    def analyze_character_centrality(
        self, script_node_id: str
    ) -> dict[str, dict[str, Any]]:
        """Analyze character importance based on graph centrality.

        Args:
            script_node_id: Script node ID

        Returns:
            Dictionary of character centrality metrics
        """
        # Get all characters in the script
        characters = self.graph.get_neighbors(
            script_node_id, direction="out", edge_type="HAS_CHARACTER"
        )

        centrality = {}
        for char in characters:
            # Count scenes appeared in
            scenes = self.get_character_scenes(char.id)

            # Count interactions
            interactions = self.get_character_interactions(char.id)

            # Calculate simple centrality metrics
            centrality[char.id] = {
                "name": char.label,
                "scene_count": len(scenes),
                "interaction_count": len(interactions),
                "unique_interactions": len({i["character_id"] for i in interactions}),
                # Simple centrality score
                "centrality_score": len(scenes) + len(interactions) * 0.5,
            }

        # Sort by centrality score
        return dict(
            sorted(
                centrality.items(),
                key=lambda x: x[1]["centrality_score"] or 0.0,
                reverse=True,
            )
        )

    def extract_characters_from_content(self, content: str) -> list[str]:
        """Extract character names from scene content.

        Args:
            content: Scene content text

        Returns:
            List of character names found
        """
        characters = []

        # Pattern for character names in dialogue (uppercase before colon)
        dialogue_pattern = r"^([A-Z][A-Z\s\'\-\.]+)(?:\s*\([^\)]+\))?\s*:"
        matches = re.findall(dialogue_pattern, content, re.MULTILINE)

        for match in matches:
            # Clean up the character name
            char_name = match.strip()

            # Remove parentheticals like (CONT'D) or (V.O.)
            char_name = re.sub(r"\s*\([^\)]+\)\s*$", "", char_name)

            # Validate character name
            if self._is_valid_character_name(char_name):
                characters.append(char_name)

        # Also look for character names in action lines (less reliable)
        # This pattern looks for capitalized names in action descriptions
        action_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
        action_matches = re.findall(action_pattern, content)

        for match in action_matches:
            if (
                self._is_valid_character_name(match)
                and match not in characters
                and content.count(match) >= 2
            ):
                characters.append(match)

        return list(
            dict.fromkeys(characters)
        )  # Remove duplicates while preserving order

    def _is_valid_character_name(self, name: str) -> bool:
        """Validate if a string is likely a character name.

        Args:
            name: Potential character name

        Returns:
            True if valid character name
        """
        # Skip common non-character words
        skip_words = {
            "INT",
            "EXT",
            "FADE",
            "CUT",
            "DISSOLVE",
            "THE",
            "END",
            "CONTINUED",
            "CONT'D",
            "V.O.",
            "O.S.",
            "LATER",
            "MOMENTS",
            "CONTINUOUS",
            "SAME",
            "BACK",
            "CLOSE",
            "ANGLE",
            "POV",
            "INSERT",
            "SERIES",
            "FLASHBACK",
            "TITLE",
            "SUPER",
            "CARD",
        }

        if name.upper() in skip_words:
            return False

        # Check word count
        word_count = len(name.split())
        if word_count > MAX_CHARACTER_NAME_WORDS:
            return False

        # Must be mostly alphabetic
        if not re.match(r"^[A-Za-z\s\'\-\.]+$", name):
            return False

        # Must have at least one letter
        return any(c.isalpha() for c in name)

    def update_character_appearances(
        self, scene_node_id: str, character_names: list[str], script_node_id: str
    ) -> None:
        """Update character appearances based on scene analysis.

        Args:
            scene_node_id: Scene node ID
            character_names: List of character names found in scene
            script_node_id: Script node ID for creating new characters
        """
        # Get all existing characters in the script
        existing_chars = self.graph.get_neighbors(
            script_node_id, direction="outgoing", edge_type="HAS_CHARACTER"
        )

        char_name_to_id = {
            (char.label or "").upper(): char.id for char in existing_chars if char.label
        }

        for char_name in character_names:
            char_name_upper = char_name.upper()

            # Find or create character node
            if char_name_upper in char_name_to_id:
                char_node_id = char_name_to_id[char_name_upper]
            else:
                # Create new character
                character = Character(
                    name=char_name,
                    description="Character appearing in scenes",
                )
                char_node_id = self.create_character_node(character, script_node_id)
                char_name_to_id[char_name_upper] = char_node_id

            # Connect character to scene
            existing_edges = self.graph.find_edges(
                from_node_id=char_node_id,
                to_node_id=scene_node_id,
                edge_type="appears_in",
            )

            if not existing_edges:
                self.connect_character_to_scene(char_node_id, scene_node_id)
