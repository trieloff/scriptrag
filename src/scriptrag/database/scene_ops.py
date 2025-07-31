"""Scene-related operations for screenplay management.

This module handles scene creation, connections, ordering, and management.
"""

from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import Scene, SceneDependency, SceneDependencyType, SceneOrderType

from .connection import DatabaseConnection
from .graph import GraphDatabase, GraphNode

logger = get_logger(__name__)


class SceneOperations:
    """Operations for managing scenes and their relationships."""

    def __init__(self, connection: DatabaseConnection, graph: GraphDatabase) -> None:
        """Initialize scene operations.

        Args:
            connection: Database connection instance
            graph: Graph database instance
        """
        self.connection = connection
        self.graph = graph

    def create_scene_node(
        self,
        scene: Scene,
        script_node_id: str,
        location_node_id: str | None = None,
        episode_node_id: str | None = None,
    ) -> str:
        """Create a scene node in the graph.

        Args:
            scene: Scene model instance
            script_node_id: Parent script node ID
            location_node_id: Optional location node ID
            episode_node_id: Optional episode node ID for series

        Returns:
            Scene node ID
        """
        # Create scene node
        scene_node_id = self.graph.add_node(
            node_type="scene",
            entity_id=str(scene.id),
            label=f"Scene {scene.script_order}",
            properties={
                "script_order": scene.script_order,
                "temporal_order": scene.temporal_order,
                "logical_order": scene.logical_order,
                "description": scene.description,
                "heading": scene.heading,
                "time_of_day": scene.time_of_day,
                "estimated_duration_minutes": scene.estimated_duration_minutes,
            },
        )

        # Connect to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=scene_node_id,
            edge_type="contains_scene",
            properties={
                "script_order": scene.script_order,
                "temporal_order": scene.temporal_order,
                "logical_order": scene.logical_order,
            },
        )

        # Connect to episode if applicable
        if episode_node_id:
            self.graph.add_edge(
                from_node_id=episode_node_id,
                to_node_id=scene_node_id,
                edge_type="contains_scene",
                properties={"script_order": scene.script_order},
            )

        # Connect to location if provided
        if location_node_id:
            self.graph.add_edge(
                from_node_id=scene_node_id,
                to_node_id=location_node_id,
                edge_type="takes_place_in",
                properties={"time_of_day": scene.time_of_day}
                if scene.time_of_day
                else {},
            )

        logger.info(
            f"Created scene node: {scene_node_id} for scene {scene.script_order}"
        )
        return scene_node_id

    def create_scene_sequence(
        self, scene_ids: list[str], sequence_type: str = "follows"
    ) -> int:
        """Create sequential relationships between scenes.

        Args:
            scene_ids: Ordered list of scene node IDs
            sequence_type: Type of sequence relationship

        Returns:
            Number of edges created
        """
        edges_created = 0

        for i in range(len(scene_ids) - 1):
            edge_id = self.graph.add_edge(
                from_node_id=scene_ids[i],
                to_node_id=scene_ids[i + 1],
                edge_type=sequence_type,
                properties={"position": i},
            )
            if edge_id:
                edges_created += 1

        logger.info(
            f"Created {edges_created} {sequence_type} edges for {len(scene_ids)} scenes"
        )
        return edges_created

    def update_scene_order(
        self, script_node_id: str, scene_positions: dict[str, int]
    ) -> bool:
        """Update the order of scenes in a script.

        Args:
            script_node_id: Script node ID
            scene_positions: Dictionary mapping scene IDs to positions

        Returns:
            True if successful
        """
        try:
            # Update scene properties with new positions
            for scene_id, position in scene_positions.items():
                scene_node = self.graph.get_node(scene_id)
                if scene_node:
                    scene_node.properties["script_order"] = position
                    self.graph.update_node(scene_id, properties=scene_node.properties)

            # Update edges to reflect new order
            scene_edges = self.graph.find_edges(
                from_node_id=script_node_id, edge_type="contains_scene"
            )

            for edge in scene_edges:
                if edge.to_node_id in scene_positions:
                    edge.properties["script_order"] = scene_positions[edge.to_node_id]
                    self.graph.update_edge(edge.id, properties=edge.properties)

            logger.info(
                f"Updated scene order for {len(scene_positions)} scenes in script"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update scene order: {e}")
            return False

    def get_script_scenes(
        self, script_node_id: str, order_type: SceneOrderType = SceneOrderType.SCRIPT
    ) -> list[GraphNode]:
        """Get all scenes for a script in specified order.

        Args:
            script_node_id: Script node ID
            order_type: Type of ordering to apply

        Returns:
            Ordered list of scene nodes
        """
        # Get all scenes
        scenes = self.graph.get_neighbors(
            script_node_id, direction="out", edge_type="contains_scene"
        )

        if not scenes:
            return []

        # Apply ordering based on type
        if order_type == SceneOrderType.SCRIPT:
            return self._get_ordered_scenes(scenes, "script_order")
        if order_type == SceneOrderType.TEMPORAL:
            return self._get_ordered_scenes(scenes, "temporal_order")
        if order_type == SceneOrderType.LOGICAL:
            return self._get_ordered_scenes(scenes, "logical_order")
        return scenes

    def _get_ordered_scenes(
        self, scenes: list[GraphNode], order_property: str
    ) -> list[GraphNode]:
        """Order scenes by a specific property.

        Args:
            scenes: List of scene nodes
            order_property: Property to order by

        Returns:
            Ordered list of scenes
        """
        return sorted(
            scenes, key=lambda s: s.properties.get(order_property, float("inf"))
        )

    def get_scene_character_network(self, scene_node_id: str) -> dict[str, list[str]]:
        """Get the character interaction network for a scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            Dictionary of character relationships in the scene
        """
        # Get all characters in the scene
        character_edges = self.graph.find_edges(
            to_node_id=scene_node_id, edge_type="appears_in"
        )

        characters = []
        for edge in character_edges:
            char_node = self.graph.get_node(edge.from_node_id)
            if char_node:
                characters.append(char_node)

        # Build interaction network
        network: dict[str, list[str]] = {}
        for char in characters:
            char_interactions = []

            # Get interactions with other characters in this scene
            for other_char in characters:
                if char.id != other_char.id:
                    # Check for interaction edges
                    interactions = self.graph.find_edges(
                        from_node_id=char.id,
                        to_node_id=other_char.id,
                        edge_type="interacts_with",
                    )

                    for interaction in interactions:
                        if interaction.properties.get("scene_id") == scene_node_id:
                            other_label = other_char.label or "Unknown"
                            char_interactions.append(other_label)

            char_label = char.label or "Unknown"
            network[char_label] = char_interactions

        return network

    def reorder_scenes(
        self,
        script_node_id: str,
        order_type: SceneOrderType,
        custom_order: list[str] | None = None,
    ) -> bool:
        """Reorder scenes based on specified criteria.

        Args:
            script_node_id: Script node ID
            order_type: Type of ordering to apply
            custom_order: Optional custom ordering of scene IDs

        Returns:
            True if successful
        """
        try:
            if custom_order:
                # Apply custom order
                scene_positions = {
                    scene_id: idx for idx, scene_id in enumerate(custom_order)
                }
                return self.update_scene_order(script_node_id, scene_positions)

            # Get scenes and apply algorithmic ordering
            scenes = self.get_script_scenes(script_node_id, SceneOrderType.SCRIPT)

            if order_type == SceneOrderType.TEMPORAL:
                # Order by time of day
                ordered_scenes = self._order_by_temporal(scenes)
            elif order_type == SceneOrderType.LOGICAL:
                # Order by dependencies
                ordered_scenes = self._order_by_dependencies(scenes)
            else:
                # Default to script order
                ordered_scenes = scenes

            # Update positions
            scene_positions = {
                scene.id: idx for idx, scene in enumerate(ordered_scenes)
            }
            return self.update_scene_order(script_node_id, scene_positions)

        except Exception as e:
            logger.error(f"Failed to reorder scenes: {e}")
            return False

    def _order_by_temporal(self, scenes: list[GraphNode]) -> list[GraphNode]:
        """Order scenes by temporal progression.

        Args:
            scenes: List of scene nodes

        Returns:
            Temporally ordered scenes
        """
        time_order = [
            "dawn",
            "morning",
            "day",
            "afternoon",
            "dusk",
            "evening",
            "night",
        ]

        def get_time_index(scene: GraphNode) -> int:
            time_of_day = scene.properties.get("time_of_day", "").lower()
            for idx, time_word in enumerate(time_order):
                if time_word in time_of_day:
                    return idx
            return len(time_order)  # Unknown times go last

        return sorted(scenes, key=get_time_index)

    def _order_by_dependencies(self, scenes: list[GraphNode]) -> list[GraphNode]:
        """Order scenes based on their dependencies.

        Args:
            scenes: List of scene nodes

        Returns:
            Dependency-ordered scenes
        """
        # This is a simplified version - real implementation would use
        # topological sorting based on scene dependencies
        return scenes

    def delete_scene_with_references(self, scene_node_id: str) -> bool:
        """Delete a scene and clean up all references.

        Args:
            scene_node_id: Scene node ID to delete

        Returns:
            True if successful
        """
        try:
            # Get the scene node first
            scene_node = self.graph.get_node(scene_node_id)
            if not scene_node:
                logger.warning(f"Scene node {scene_node_id} not found")
                return False

            # Remove all edges connected to this scene
            edges_to_delete = []

            # Outgoing edges
            edges_to_delete.extend(self.graph.find_edges(from_node_id=scene_node_id))
            # Incoming edges
            edges_to_delete.extend(self.graph.find_edges(to_node_id=scene_node_id))

            for edge in edges_to_delete:
                self.graph.delete_edge(edge.id)

            # Delete the scene node itself
            self.graph.delete_node(scene_node_id)

            # Remove from scenes table if it exists
            with self.connection.transaction() as conn:
                conn.execute(
                    "DELETE FROM scenes WHERE id = ?",
                    (scene_node.properties.get("entity_id", scene_node_id),),
                )

            logger.info(
                f"Deleted scene {scene_node_id} and {len(edges_to_delete)} edges"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete scene: {e}")
            return False

    def inject_scene_at_position(
        self,
        new_scene: Scene,
        script_node_id: str,
        position: int,
        location_node_id: str | None = None,
    ) -> str | None:
        """Inject a new scene at a specific position.

        Args:
            new_scene: Scene to inject
            script_node_id: Script node ID
            position: Position to inject at (0-based)
            location_node_id: Optional location node ID

        Returns:
            New scene node ID if successful
        """
        try:
            # Get existing scenes in order
            scenes = self.get_script_scenes(script_node_id, SceneOrderType.SCRIPT)

            # Create the new scene node
            new_scene_id = self.create_scene_node(
                new_scene, script_node_id, location_node_id
            )

            # Shift positions of scenes after injection point
            scene_positions = {}
            for idx, scene in enumerate(scenes):
                if idx < position:
                    scene_positions[scene.id] = idx
                else:
                    scene_positions[scene.id] = idx + 1

            # Add the new scene at the specified position
            scene_positions[new_scene_id] = position

            # Update all positions
            self.update_scene_order(script_node_id, scene_positions)

            logger.info(f"Injected scene {new_scene_id} at position {position}")
            return new_scene_id

        except Exception as e:
            logger.error(f"Failed to inject scene: {e}")
            return None

    def update_scene_metadata(
        self,
        scene_node_id: str,
        metadata: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update scene metadata.

        Args:
            scene_node_id: Scene node ID
            metadata: Metadata to update
            merge: Whether to merge with existing metadata

        Returns:
            True if successful
        """
        try:
            scene_node = self.graph.get_node(scene_node_id)
            if not scene_node:
                return False

            if merge:
                # Merge with existing properties
                scene_node.properties.update(metadata)
            else:
                # Replace properties
                scene_node.properties = metadata

            self.graph.update_node(scene_node_id, properties=scene_node.properties)

            logger.debug(f"Updated metadata for scene {scene_node_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update scene metadata: {e}")
            return False

    def get_scene_dependencies(self, scene_node_id: str) -> list[SceneDependency]:
        """Get dependencies for a specific scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            List of scene dependencies
        """
        dependencies = []

        # Get depends_on edges
        dep_edges = self.graph.find_edges(
            from_node_id=scene_node_id, edge_type="depends_on"
        )

        for edge in dep_edges:
            target_scene = self.graph.get_node(edge.to_node_id)
            if target_scene:
                # Create a UUID from the scene_node_id string if needed
                from uuid import UUID

                try:
                    from_scene_uuid = (
                        UUID(scene_node_id)
                        if isinstance(scene_node_id, str)
                        else scene_node_id
                    )
                    to_scene_uuid = (
                        UUID(edge.to_node_id)
                        if isinstance(edge.to_node_id, str)
                        else edge.to_node_id
                    )
                except ValueError:
                    # If conversion fails, skip this dependency
                    continue

                dependencies.append(
                    SceneDependency(
                        from_scene_id=from_scene_uuid,
                        to_scene_id=to_scene_uuid,
                        dependency_type=SceneDependencyType(
                            edge.properties.get("dependency_type", "requires")
                        ),
                        strength=edge.properties.get("strength", 1.0),
                    )
                )

        return dependencies
