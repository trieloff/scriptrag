"""Graph operations for screenplay-specific functionality.

This module provides high-level operations for managing screenplay data
in the graph database, including entity management, relationship creation,
and screenplay-specific queries.
"""

from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import (
    Character,
    Episode,
    Location,
    Scene,
    SceneDependency,
    SceneOrderType,
    Script,
    Season,
)

from .character_ops import CharacterOperations
from .connection import DatabaseConnection
from .continuity_ops import ContinuityOperations
from .embedding_ops import EmbeddingOperations
from .graph import GraphDatabase, GraphNode
from .location_ops import LocationOperations
from .scene_ops import SceneOperations
from .scene_ordering import SceneOrderingOperations
from .script_ops import ScriptOperations
from .vectors import VectorOperations

logger = get_logger(__name__)


class GraphOperations:
    """High-level operations for screenplay graph database.

    This class acts as a facade for the various specialized operation modules,
    providing a unified interface for graph database operations.
    """

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize graph operations.

        Args:
            connection: Database connection instance
        """
        self.connection = connection
        self.graph = GraphDatabase(connection)
        self.vectors = VectorOperations(connection)
        self.ordering = SceneOrderingOperations(connection)

        # Initialize specialized operation modules
        self._script_ops = ScriptOperations(connection, self.graph)
        self._character_ops = CharacterOperations(connection, self.graph)
        self._location_ops = LocationOperations(connection, self.graph)
        self._scene_ops = SceneOperations(connection, self.graph)
        self._embedding_ops = EmbeddingOperations(connection, self.vectors)
        self._continuity_ops = ContinuityOperations(connection, self.graph)

    # Script-level operations (delegate to ScriptOperations)
    def create_script_graph(self, script: Script) -> str:
        """Create graph representation of a script."""
        return self._script_ops.create_script_graph(script)

    def add_season_to_script(self, season: Season, script_node_id: str) -> str:
        """Add a season to a series script."""
        return self._script_ops.add_season_to_script(season, script_node_id)

    def add_episode_to_season(
        self,
        episode: Episode,
        season_node_id: str,
        script_node_id: str | None = None,
    ) -> str:
        """Add an episode to a season."""
        return self._script_ops.add_episode_to_season(
            episode, season_node_id, script_node_id
        )

    def ensure_script_order(self, script_id: str) -> bool:
        """Ensure scenes in a script have proper ordering."""
        return self._script_ops.ensure_script_order(script_id)

    # Character operations (delegate to CharacterOperations)
    def create_character_node(self, character: Character, script_node_id: str) -> str:
        """Create a character node in the graph."""
        return self._character_ops.create_character_node(character, script_node_id)

    def connect_character_to_scene(
        self,
        character_node_id: str,
        scene_node_id: str,
        dialogue_count: int = 0,
    ) -> str | None:
        """Connect a character to a scene they appear in."""
        return self._character_ops.connect_character_to_scene(
            character_node_id, scene_node_id, dialogue_count
        )

    def connect_character_interaction(
        self,
        character1_id: str,
        character2_id: str,
        scene_node_id: str,
        interaction_type: str = "dialogue",
    ) -> str | None:
        """Create interaction edge between two characters."""
        return self._character_ops.connect_character_interaction(
            character1_id, character2_id, scene_node_id, interaction_type
        )

    def get_character_scenes(self, character_node_id: str) -> list[GraphNode]:
        """Get all scenes a character appears in."""
        return self._character_ops.get_character_scenes(character_node_id)

    def get_character_interactions(
        self, character_node_id: str, interaction_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all character interactions for a given character."""
        return self._character_ops.get_character_interactions(
            character_node_id, interaction_type
        )

    def analyze_character_centrality(
        self, script_node_id: str
    ) -> dict[str, dict[str, Any]]:
        """Analyze character importance based on graph centrality."""
        return self._character_ops.analyze_character_centrality(script_node_id)

    def _extract_characters_from_content(self, content: str) -> list[str]:
        """Extract character names from scene content."""
        return self._character_ops.extract_characters_from_content(content)

    def _update_character_appearances(
        self, scene_node_id: str, character_names: list[str], script_node_id: str
    ) -> None:
        """Update character appearances based on scene analysis."""
        self._character_ops.update_character_appearances(
            scene_node_id, character_names, script_node_id
        )

    # Location operations (delegate to LocationOperations)
    def create_location_node(self, location: Location, script_node_id: str) -> str:
        """Create a location node in the graph."""
        return self._location_ops.create_location_node(location, script_node_id)

    def connect_scene_to_location(
        self, scene_node_id: str, location_node_id: str, time_of_day: str | None = None
    ) -> str | None:
        """Connect a scene to its location."""
        return self._location_ops.connect_scene_to_location(
            scene_node_id, location_node_id, time_of_day
        )

    def get_location_scenes(self, location_node_id: str) -> list[GraphNode]:
        """Get all scenes that take place in a location."""
        return self._location_ops.get_location_scenes(location_node_id)

    def _update_scene_location_with_propagation(
        self,
        scene_node_id: str,
        new_location: str,
        script_node_id: str,
        update_characters: bool = True,
    ) -> dict[str, Any]:
        """Update a scene's location with optional character propagation."""
        return self._location_ops.update_scene_location_with_propagation(
            scene_node_id, new_location, script_node_id, update_characters
        )

    # Scene operations (delegate to SceneOperations)
    def create_scene_node(
        self,
        scene: Scene,
        script_node_id: str,
        location_node_id: str | None = None,
        episode_node_id: str | None = None,
    ) -> str:
        """Create a scene node in the graph."""
        return self._scene_ops.create_scene_node(
            scene, script_node_id, location_node_id, episode_node_id
        )

    def create_scene_sequence(
        self, scene_ids: list[str], sequence_type: str = "follows"
    ) -> list[str]:
        """Create sequential relationships between scenes."""
        return self._scene_ops.create_scene_sequence(scene_ids, sequence_type)

    def update_scene_order(
        self, script_node_id: str, scene_positions: dict[str, int]
    ) -> bool:
        """Update the order of scenes in a script."""
        return self._scene_ops.update_scene_order(script_node_id, scene_positions)

    def get_script_scenes(
        self, script_node_id: str, order_type: SceneOrderType = SceneOrderType.SCRIPT
    ) -> list[GraphNode]:
        """Get all scenes for a script in specified order."""
        return self._scene_ops.get_script_scenes(script_node_id, order_type)

    def _get_ordered_scenes(
        self, scenes: list[GraphNode], order_property: str
    ) -> list[GraphNode]:
        """Order scenes by a specific property."""
        return self._scene_ops._get_ordered_scenes(scenes, order_property)

    def get_scene_character_network(self, scene_node_id: str) -> dict[str, list[str]]:
        """Get the character interaction network for a scene."""
        return self._scene_ops.get_scene_character_network(scene_node_id)

    def reorder_scenes(
        self,
        script_node_id: str,
        order_type: SceneOrderType,
        custom_order: list[str] | None = None,
    ) -> bool:
        """Reorder scenes based on specified criteria."""
        return self._scene_ops.reorder_scenes(script_node_id, order_type, custom_order)

    def delete_scene_with_references(self, scene_node_id: str) -> bool:
        """Delete a scene and clean up all references."""
        return self._scene_ops.delete_scene_with_references(scene_node_id)

    def inject_scene_at_position(
        self,
        new_scene: Scene,
        script_node_id: str,
        position: int,
        location_node_id: str | None = None,
    ) -> str | None:
        """Inject a new scene at a specific position."""
        return self._scene_ops.inject_scene_at_position(
            new_scene, script_node_id, position, location_node_id
        )

    def update_scene_metadata(
        self,
        scene_node_id: str,
        metadata: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update scene metadata."""
        return self._scene_ops.update_scene_metadata(scene_node_id, metadata, merge)

    def get_scene_dependencies(self, scene_node_id: str) -> list[SceneDependency]:
        """Get dependencies for a specific scene."""
        return self._scene_ops.get_scene_dependencies(scene_node_id)

    # Embedding operations (delegate to EmbeddingOperations)
    def store_scene_embedding(
        self,
        scene_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for a scene."""
        return self._embedding_ops.store_scene_embedding(
            scene_id, embedding, content, model_name
        )

    def store_character_embedding(
        self,
        character_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for a character."""
        return self._embedding_ops.store_character_embedding(
            character_id, embedding, content, model_name
        )

    def store_dialogue_embedding(
        self,
        dialogue_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for dialogue."""
        return self._embedding_ops.store_dialogue_embedding(
            dialogue_id, embedding, content, model_name
        )

    def find_similar_scenes(
        self,
        scene_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
        exclude_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find scenes similar to a given embedding."""
        return self._embedding_ops.find_similar_scenes(
            scene_embedding, limit, threshold, exclude_ids
        )

    def find_similar_characters(
        self,
        character_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
        exclude_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find characters similar to a given embedding."""
        return self._embedding_ops.find_similar_characters(
            character_embedding, limit, threshold, exclude_ids
        )

    def semantic_search_scenes(
        self,
        query_embedding: list[float],
        script_id: str | None = None,
        limit: int = 20,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for scenes using semantic similarity."""
        return self._embedding_ops.semantic_search_scenes(
            query_embedding, script_id, limit, threshold
        )

    def semantic_search_dialogue(
        self,
        query_embedding: list[float],
        character_id: str | None = None,
        limit: int = 20,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for dialogue using semantic similarity."""
        return self._embedding_ops.semantic_search_dialogue(
            query_embedding, character_id, limit, threshold
        )

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about stored embeddings."""
        return self._embedding_ops.get_embedding_stats()

    def delete_entity_embeddings(self, entity_type: str, entity_id: str) -> int:
        """Delete all embeddings for a specific entity."""
        return self._embedding_ops.delete_entity_embeddings(entity_type, entity_id)

    def batch_store_embeddings(
        self,
        embeddings: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> dict[str, int]:
        """Store multiple embeddings in batches."""
        return self._embedding_ops.batch_store_embeddings(embeddings, batch_size)

    # Continuity operations (delegate to ContinuityOperations)
    def infer_temporal_order(self, script_id: str) -> dict[str, int]:
        """Infer temporal order of scenes based on time of day."""
        return self._continuity_ops.infer_temporal_order(script_id)

    def analyze_scene_dependencies(self, script_id: str) -> list[SceneDependency]:
        """Analyze dependencies between scenes."""
        return self._continuity_ops.analyze_scene_dependencies(script_id)

    def calculate_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order of scenes based on dependencies."""
        return self._continuity_ops.calculate_logical_order(script_id)

    def validate_scene_ordering(self, script_id: str) -> dict[str, Any]:
        """Validate the current scene ordering for consistency."""
        return self._continuity_ops.validate_scene_ordering(script_id)

    def validate_story_continuity(self, script_node_id: str) -> dict[str, Any]:
        """Validate story continuity across all scenes."""
        return self._continuity_ops.validate_story_continuity(script_node_id)

    def _is_temporal_regression(self, current_time: str, next_time: str) -> bool:
        """Check if there's a temporal regression between times."""
        return self._continuity_ops._is_temporal_regression(current_time, next_time)

    # Direct graph operations (for backwards compatibility)
    def add_node(
        self,
        node_type: str,
        entity_id: str,
        label: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Add a node to the graph."""
        return self.graph.add_node(node_type, entity_id, label, properties)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        return self.graph.get_node(node_id)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str | None:
        """Add an edge between two nodes."""
        return self.graph.add_edge(
            from_node_id=source_id,
            to_node_id=target_id,
            edge_type=edge_type,
            properties=properties,
        )

    # Scene ordering operations (delegate to existing SceneOrderingOperations)
    def _remove_scene_dependencies(self, scene_node_id: str) -> None:
        """Remove scene from dependency tracking."""
        # Get all dependency edges
        dep_edges = self.graph.find_edges(
            from_node_id=scene_node_id, edge_type="depends_on"
        )
        dep_edges.extend(
            self.graph.find_edges(to_node_id=scene_node_id, edge_type="depends_on")
        )

        # Remove all dependency edges
        for edge in dep_edges:
            self.graph.delete_edge(edge.id)

    def _reindex_scenes_after_deletion(
        self, script_node_id: str, deleted_position: int
    ) -> None:
        """Reindex scene positions after deletion."""
        # Get remaining scenes
        scenes = self.get_script_scenes(script_node_id)

        # Update positions for scenes after the deleted one
        for scene in scenes:
            current_pos = scene.properties.get("scene_order", 0)
            if current_pos > deleted_position:
                scene.properties["scene_order"] = current_pos - 1
                self.graph.update_node(scene.id, properties=scene.properties)

    def _shift_scenes_for_injection(self, script_node_id: str, position: int) -> None:
        """Shift scene positions to make room for injection."""
        # Get existing scenes
        scenes = self.get_script_scenes(script_node_id)

        # Shift scenes at or after the injection position
        for scene in scenes:
            current_pos = scene.properties.get("scene_order", 0)
            if current_pos >= position:
                scene.properties["scene_order"] = current_pos + 1
                self.graph.update_node(scene.id, properties=scene.properties)

    def _reanalyze_dependencies_after_injection(
        self, script_node_id: str, new_scene_id: str
    ) -> None:
        """Reanalyze dependencies after scene injection."""
        # This would analyze how the new scene affects existing dependencies
        # Currently a placeholder for future implementation
        pass
