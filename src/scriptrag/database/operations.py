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

from .connection import DatabaseConnection
from .graph import GraphDatabase, GraphEdge, GraphNode
from .scene_ordering import SceneOrderingOperations
from .vectors import VectorOperations

logger = get_logger(__name__)


class GraphOperations:
    """High-level operations for screenplay graph database."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize graph operations.

        Args:
            connection: Database connection instance
        """
        self.connection = connection
        self.graph = GraphDatabase(connection)
        self.vectors = VectorOperations(connection)
        self.ordering = SceneOrderingOperations(connection)

    # Script-level operations
    def create_script_graph(self, script: Script) -> str:
        """Create graph representation of a script.

        Args:
            script: Script model instance

        Returns:
            Script node ID
        """
        # Create script node
        script_node_id = self.graph.add_node(
            node_type="script",
            entity_id=str(script.id),
            label=script.title,
            properties={
                "format": script.format,
                "author": script.author,
                "genre": script.genre,
                "is_series": script.is_series,
            },
        )

        logger.info(f"Created script graph node {script_node_id} for '{script.title}'")
        return script_node_id

    def add_season_to_script(self, season: Season, script_node_id: str) -> str:
        """Add a season node and connect to script.

        Args:
            season: Season model instance
            script_node_id: Parent script node ID

        Returns:
            Season node ID
        """
        season_node_id = self.graph.add_node(
            node_type="season",
            entity_id=str(season.id),
            label=f"Season {season.number}"
            + (f": {season.title}" if season.title else ""),
            properties={
                "number": season.number,
                "year": season.year,
            },
        )

        # Connect season to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=season_node_id,
            edge_type="HAS_SEASON",
            properties={"season_number": season.number},
        )

        logger.debug(f"Added season {season.number} to script graph")
        return season_node_id

    def add_episode_to_season(
        self, episode: Episode, season_node_id: str, script_node_id: str
    ) -> str:
        """Add an episode node and connect to season and script.

        Args:
            episode: Episode model instance
            season_node_id: Parent season node ID
            script_node_id: Root script node ID

        Returns:
            Episode node ID
        """
        episode_node_id = self.graph.add_node(
            node_type="episode",
            entity_id=str(episode.id),
            label=f"Episode {episode.number}: {episode.title}",
            properties={
                "number": episode.number,
                "writer": episode.writer,
                "director": episode.director,
                "air_date": episode.air_date.isoformat() if episode.air_date else None,
            },
        )

        # Connect episode to season
        self.graph.add_edge(
            from_node_id=season_node_id,
            to_node_id=episode_node_id,
            edge_type="HAS_EPISODE",
            properties={"episode_number": episode.number},
        )

        # Connect episode to script for easy traversal
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=episode_node_id,
            edge_type="CONTAINS_EPISODE",
            properties={"episode_number": episode.number},
        )

        logger.debug(f"Added episode {episode.number} to season graph")
        return episode_node_id

    # Character operations
    def create_character_node(self, character: Character, script_node_id: str) -> str:
        """Create a character node and connect to script.

        Args:
            character: Character model instance
            script_node_id: Parent script node ID

        Returns:
            Character node ID
        """
        character_node_id = self.graph.add_node(
            node_type="character",
            entity_id=str(character.id),
            label=character.name,
            properties={
                "name": character.name,
                "description": character.description,
                "aliases": character.aliases,
            },
        )

        # Connect character to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=character_node_id,
            edge_type="HAS_CHARACTER",
            properties={"character_name": character.name},
        )

        logger.debug(f"Created character node for {character.name}")
        return character_node_id

    # Location operations
    def create_location_node(self, location: Location, script_node_id: str) -> str:
        """Create a location node and connect to script.

        Args:
            location: Location model instance
            script_node_id: Parent script node ID

        Returns:
            Location node ID
        """
        location_node_id = self.graph.add_node(
            node_type="location",
            entity_id=None,  # Location model doesn't have an id field
            label=str(location),
            properties={
                "interior": location.interior,
                "name": location.name,
                "time": location.time,
                "raw_text": location.raw_text,
            },
        )

        # Connect location to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=location_node_id,
            edge_type="HAS_LOCATION",
            properties={"location_name": location.name},
        )

        logger.debug(f"Created location node for {location}")
        return location_node_id

    # Scene operations
    def create_scene_node(
        self,
        scene: Scene,
        script_node_id: str,
        episode_node_id: str | None = None,
        season_node_id: str | None = None,
    ) -> str:
        """Create a scene node and connect to appropriate parents.

        Args:
            scene: Scene model instance
            script_node_id: Parent script node ID
            episode_node_id: Parent episode node ID (if applicable)
            season_node_id: Parent season node ID (if applicable)

        Returns:
            Scene node ID
        """
        scene_node_id = self.graph.add_node(
            node_type="scene",
            entity_id=str(scene.id),
            label=scene.heading or f"Scene {scene.script_order}",
            properties={
                "script_order": scene.script_order,
                "temporal_order": scene.temporal_order,
                "logical_order": scene.logical_order,
                "heading": scene.heading,
                "description": scene.description,
                "estimated_duration": scene.estimated_duration_minutes,
                "time_of_day": scene.time_of_day,
                "date_in_story": scene.date_in_story,
            },
        )

        # Connect scene to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=scene_node_id,
            edge_type="HAS_SCENE",
            properties={"script_order": scene.script_order},
        )

        # Connect to episode if provided
        if episode_node_id:
            self.graph.add_edge(
                from_node_id=episode_node_id,
                to_node_id=scene_node_id,
                edge_type="HAS_SCENE",
                properties={"script_order": scene.script_order},
            )

        # Connect to season if provided
        if season_node_id:
            self.graph.add_edge(
                from_node_id=season_node_id,
                to_node_id=scene_node_id,
                edge_type="HAS_SCENE",
                properties={"script_order": scene.script_order},
            )

        logger.debug(f"Created scene node {scene.script_order}")
        return scene_node_id

    def connect_scene_to_location(
        self, scene_node_id: str, location_node_id: str
    ) -> str:
        """Connect a scene to its location.

        Args:
            scene_node_id: Scene node ID
            location_node_id: Location node ID

        Returns:
            Edge ID
        """
        return self.graph.add_edge(
            from_node_id=scene_node_id,
            to_node_id=location_node_id,
            edge_type="AT_LOCATION",
        )

    def connect_character_to_scene(
        self,
        character_node_id: str,
        scene_node_id: str,
        speaking_lines: int = 0,
        action_mentions: int = 0,
    ) -> str:
        """Connect a character to a scene they appear in.

        Args:
            character_node_id: Character node ID
            scene_node_id: Scene node ID
            speaking_lines: Number of dialogue lines
            action_mentions: Number of action mentions

        Returns:
            Edge ID
        """
        return self.graph.add_edge(
            from_node_id=character_node_id,
            to_node_id=scene_node_id,
            edge_type="APPEARS_IN",
            properties={
                "speaking_lines": speaking_lines,
                "action_mentions": action_mentions,
            },
        )

    def connect_character_interaction(
        self,
        from_character_node_id: str,
        to_character_node_id: str,
        scene_node_id: str,
        dialogue_count: int = 1,
    ) -> str:
        """Connect two characters who interact in a scene.

        Args:
            from_character_node_id: Speaking character node ID
            to_character_node_id: Receiving character node ID
            scene_node_id: Scene where interaction occurs
            dialogue_count: Number of dialogue exchanges

        Returns:
            Edge ID
        """
        return self.graph.add_edge(
            from_node_id=from_character_node_id,
            to_node_id=to_character_node_id,
            edge_type="SPEAKS_TO",
            properties={
                "scene_id": scene_node_id,
                "dialogue_count": dialogue_count,
            },
        )

    # Scene ordering operations
    def create_scene_sequence(
        self,
        scene_node_ids: list[str],
        order_type: SceneOrderType,
    ) -> list[str]:
        """Create sequence relationships between scenes.

        Args:
            scene_node_ids: List of scene node IDs in order
            order_type: Type of ordering (script, temporal, logical)

        Returns:
            List of edge IDs created
        """
        edge_ids = []

        for i in range(len(scene_node_ids) - 1):
            current_scene = scene_node_ids[i]
            next_scene = scene_node_ids[i + 1]

            edge_id = self.graph.add_edge(
                from_node_id=current_scene,
                to_node_id=next_scene,
                edge_type="FOLLOWS",
                properties={
                    "order_type": order_type.value,
                    "sequence_position": i,
                },
            )
            edge_ids.append(edge_id)

        logger.debug(
            f"Created {order_type.value} sequence for {len(scene_node_ids)} scenes"
        )
        return edge_ids

    def update_scene_order(
        self,
        script_node_id: str,
        scene_order_mapping: dict[str, int],
        order_type: SceneOrderType,
    ) -> bool:
        """Update scene ordering in the graph.

        Args:
            script_node_id: Script node ID
            scene_order_mapping: Map of scene_node_id -> order_position
            order_type: Type of ordering to update

        Returns:
            True if successful
        """
        try:
            with self.connection.transaction() as conn:
                # Remove existing FOLLOWS edges of this order type
                conn.execute(
                    """
                    DELETE FROM edges
                    WHERE edge_type = 'FOLLOWS'
                    AND json_extract(properties_json, '$.order_type') = ?
                    AND from_node_id IN (
                        SELECT to_node_id FROM edges
                        WHERE from_node_id = ? AND edge_type = 'HAS_SCENE'
                    )
                    """,
                    (order_type.value, script_node_id),
                )

                # Create new sequence based on mapping
                sorted_scenes = sorted(scene_order_mapping.items(), key=lambda x: x[1])
                scene_node_ids = [scene_id for scene_id, _ in sorted_scenes]

                # Use existing method to create sequence
                self.create_scene_sequence(scene_node_ids, order_type)

            logger.info(
                f"Updated {order_type.value} ordering for "
                f"{len(scene_order_mapping)} scenes"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update scene order: {e}")
            return False

    # Query operations
    def get_script_scenes(
        self,
        script_node_id: str,
        order_type: SceneOrderType | None = None,
    ) -> list[GraphNode]:
        """Get all scenes for a script in specified order.

        Args:
            script_node_id: Script node ID
            order_type: Type of ordering (None for script order)

        Returns:
            List of scene nodes in order
        """
        if order_type is None:
            order_type = SceneOrderType.SCRIPT

        # Get scenes connected to script
        scene_nodes = self.graph.get_neighbors(
            script_node_id,
            edge_type="HAS_SCENE",
            direction="out",
        )

        if order_type == SceneOrderType.SCRIPT:
            # Sort by script_order property
            return sorted(
                scene_nodes,
                key=lambda n: n.properties.get("script_order", 0),
            )
        # For temporal/logical order, follow FOLLOWS edges
        return self._get_ordered_scenes(scene_nodes, order_type)

    def _get_ordered_scenes(
        self,
        scene_nodes: list[GraphNode],
        order_type: SceneOrderType,
    ) -> list[GraphNode]:
        """Get scenes in temporal or logical order by following FOLLOWS edges.

        Args:
            scene_nodes: List of scene nodes to order
            order_type: Type of ordering

        Returns:
            Ordered list of scene nodes
        """
        # Create a map for quick lookup
        scene_map = {node.id: node for node in scene_nodes}
        scene_ids = set(scene_map.keys())

        # Find the starting scene (no incoming FOLLOWS edge of this type)
        follows_edges = []
        for scene_id in scene_ids:
            edges = self.graph.find_edges(
                from_node_id=scene_id,
                edge_type="FOLLOWS",
            )
            follows_edges.extend(
                [
                    edge
                    for edge in edges
                    if edge.properties.get("order_type") == order_type.value
                    and edge.to_node_id in scene_ids
                ]
            )

        # Find scenes with no incoming FOLLOWS edges
        incoming_targets = {edge.to_node_id for edge in follows_edges}
        start_scenes = [
            scene_id for scene_id in scene_ids if scene_id not in incoming_targets
        ]

        # Build ordered list by following edges
        ordered_scenes = []

        for start_scene_id in start_scenes:
            current_id: str | None = start_scene_id
            visited = set()

            while current_id and current_id not in visited:
                if current_id in scene_map:
                    ordered_scenes.append(scene_map[current_id])
                    visited.add(current_id)

                # Find next scene
                next_edges = [
                    edge for edge in follows_edges if edge.from_node_id == current_id
                ]

                current_id = next_edges[0].to_node_id if next_edges else None

        # Add any scenes not connected by FOLLOWS edges
        connected_ids = {node.id for node in ordered_scenes}
        disconnected_scenes = [
            scene_map[scene_id]
            for scene_id in scene_ids
            if scene_id not in connected_ids
        ]

        # Sort disconnected scenes by script order as fallback
        disconnected_scenes.sort(key=lambda n: n.properties.get("script_order", 0))

        return ordered_scenes + disconnected_scenes

    def get_character_scenes(self, character_node_id: str) -> list[GraphNode]:
        """Get all scenes where a character appears.

        Args:
            character_node_id: Character node ID

        Returns:
            List of scene nodes
        """
        return self.graph.get_neighbors(
            character_node_id,
            edge_type="APPEARS_IN",
            direction="out",
        )

    def get_location_scenes(self, location_node_id: str) -> list[GraphNode]:
        """Get all scenes at a location.

        Args:
            location_node_id: Location node ID

        Returns:
            List of scene nodes
        """
        return self.graph.get_neighbors(
            location_node_id,
            edge_type="AT_LOCATION",
            direction="in",
        )

    def get_character_interactions(
        self,
        character_node_id: str,
        scene_node_id: str | None = None,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Get characters that interact with the given character.

        Args:
            character_node_id: Character node ID
            scene_node_id: Optional scene filter

        Returns:
            List of (character_node, interaction_edge) tuples
        """
        # Get outgoing SPEAKS_TO edges
        edges = self.graph.find_edges(
            from_node_id=character_node_id,
            edge_type="SPEAKS_TO",
        )

        results = []
        for edge in edges:
            # Filter by scene if specified
            if scene_node_id and edge.properties.get("scene_id") != scene_node_id:
                continue

            # Get the target character node
            target_node = self.graph.get_node(edge.to_node_id)
            if target_node:
                results.append((target_node, edge))

        return results

    def get_scene_character_network(
        self, scene_node_id: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Get the character interaction network for a scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            Tuple of (character_nodes, interaction_edges)
        """
        # Get all characters in the scene
        characters = self.graph.get_neighbors(
            scene_node_id,
            edge_type="APPEARS_IN",
            direction="in",
        )

        # Get all interactions between these characters in this scene
        character_ids = {char.id for char in characters}
        all_interactions = []

        for char_id in character_ids:
            edges = self.graph.find_edges(
                from_node_id=char_id,
                edge_type="SPEAKS_TO",
            )

            scene_interactions = [
                edge
                for edge in edges
                if edge.properties.get("scene_id") == scene_node_id
                and edge.to_node_id in character_ids
            ]

            all_interactions.extend(scene_interactions)

        return characters, all_interactions

    def analyze_character_centrality(
        self, script_node_id: str
    ) -> dict[str, dict[str, float | str]]:
        """Analyze character centrality in the script's interaction network.

        Args:
            script_node_id: Script node ID

        Returns:
            Dictionary mapping character_node_id to centrality metrics
        """
        # Get all characters in the script
        characters = self.graph.get_neighbors(
            script_node_id,
            edge_type="HAS_CHARACTER",
            direction="out",
        )

        centrality_scores: dict[str, dict[str, float | str]] = {}

        for character in characters:
            char_id = character.id

            # Degree centrality (number of connections)
            degree = self.graph.get_node_degree(char_id, direction="both")

            # Appearance frequency (number of scenes)
            scene_count = len(self.get_character_scenes(char_id))

            # Interaction diversity (number of unique characters interacted with)
            interactions = self.get_character_interactions(char_id)
            unique_interactions = len({edge.to_node_id for _, edge in interactions})

            centrality_scores[char_id] = {
                "degree_centrality": float(degree),
                "scene_frequency": float(scene_count),
                "interaction_diversity": float(unique_interactions),
                "character_name": str(character.label or "Unknown"),
            }

        return centrality_scores

    # Vector operations for semantic search
    def store_scene_embedding(
        self, scene_id: str, content: str, embedding: list[float], model_name: str
    ) -> bool:
        """Store embedding for a scene.

        Args:
            scene_id: Scene entity ID
            content: Text content that was embedded
            embedding: Vector embedding
            model_name: Name of the embedding model

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="scene",
            entity_id=scene_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def store_character_embedding(
        self, character_id: str, content: str, embedding: list[float], model_name: str
    ) -> bool:
        """Store embedding for a character.

        Args:
            character_id: Character entity ID
            content: Text content that was embedded
            embedding: Vector embedding
            model_name: Name of the embedding model

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="character",
            entity_id=character_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def store_dialogue_embedding(
        self, dialogue_id: str, content: str, embedding: list[float], model_name: str
    ) -> bool:
        """Store embedding for dialogue.

        Args:
            dialogue_id: Dialogue entity ID
            content: Text content that was embedded
            embedding: Vector embedding
            model_name: Name of the embedding model

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="dialogue",
            entity_id=dialogue_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def find_similar_scenes(
        self,
        query_scene_id: str,
        model_name: str,
        limit: int = 10,
        distance_metric: str = "cosine",
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Find scenes similar to a given scene.

        Args:
            query_scene_id: ID of the scene to find similarities for
            model_name: Embedding model name
            limit: Maximum number of results
            distance_metric: Distance metric to use

        Returns:
            List of (scene_id, distance, metadata) tuples
        """
        results = self.vectors.find_similar_to_entity(
            entity_type="scene",
            entity_id=query_scene_id,
            model_name=model_name,
            target_entity_type="scene",
            distance_metric=distance_metric,
            limit=limit,
            exclude_self=True,
        )

        return [
            (entity_id, distance, metadata)
            for _, entity_id, distance, metadata in results
        ]

    def find_similar_characters(
        self,
        query_character_id: str,
        model_name: str,
        limit: int = 10,
        distance_metric: str = "cosine",
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Find characters similar to a given character.

        Args:
            query_character_id: ID of the character to find similarities for
            model_name: Embedding model name
            limit: Maximum number of results
            distance_metric: Distance metric to use

        Returns:
            List of (character_id, distance, metadata) tuples
        """
        results = self.vectors.find_similar_to_entity(
            entity_type="character",
            entity_id=query_character_id,
            model_name=model_name,
            target_entity_type="character",
            distance_metric=distance_metric,
            limit=limit,
            exclude_self=True,
        )

        return [
            (entity_id, distance, metadata)
            for _, entity_id, distance, metadata in results
        ]

    def semantic_search_scenes(
        self,
        query_embedding: list[float],
        model_name: str,
        limit: int = 10,
        distance_metric: str = "cosine",
        threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for scenes using semantic similarity.

        Args:
            query_embedding: Query vector for similarity search
            model_name: Embedding model name
            limit: Maximum number of results
            distance_metric: Distance metric to use
            threshold: Minimum similarity threshold

        Returns:
            List of (scene_id, distance, metadata) tuples
        """
        results = self.vectors.find_similar(
            query_vector=query_embedding,
            entity_type="scene",
            model_name=model_name,
            distance_metric=distance_metric,
            limit=limit,
            threshold=threshold,
        )

        return [
            (entity_id, distance, metadata)
            for _, entity_id, distance, metadata in results
        ]

    def semantic_search_dialogue(
        self,
        query_embedding: list[float],
        model_name: str,
        limit: int = 10,
        distance_metric: str = "cosine",
        threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for dialogue using semantic similarity.

        Args:
            query_embedding: Query vector for similarity search
            model_name: Embedding model name
            limit: Maximum number of results
            distance_metric: Distance metric to use
            threshold: Minimum similarity threshold

        Returns:
            List of (dialogue_id, distance, metadata) tuples
        """
        results = self.vectors.find_similar(
            query_vector=query_embedding,
            entity_type="dialogue",
            model_name=model_name,
            distance_metric=distance_metric,
            limit=limit,
            threshold=threshold,
        )

        return [
            (entity_id, distance, metadata)
            for _, entity_id, distance, metadata in results
        ]

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about stored embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        return self.vectors.get_vector_stats()

    def delete_entity_embeddings(
        self, entity_type: str, entity_id: str, model_name: str | None = None
    ) -> int:
        """Delete embeddings for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            model_name: Optional model name filter

        Returns:
            Number of embeddings deleted
        """
        return self.vectors.delete_embeddings(
            entity_type=entity_type, entity_id=entity_id, model_name=model_name
        )

    def batch_store_embeddings(
        self, embeddings_data: list[dict[str, Any]]
    ) -> list[bool]:
        """Store multiple embeddings in batch.

        Args:
            embeddings_data: List of embedding data dictionaries with keys:
                - entity_type: str
                - entity_id: str
                - content: str
                - embedding: List[float]
                - model_name: str

        Returns:
            List of success flags for each embedding
        """
        results = []
        for data in embeddings_data:
            success = self.vectors.store_embedding(
                entity_type=data["entity_type"],
                entity_id=data["entity_id"],
                content=data["content"],
                embedding=data["embedding"],
                model_name=data["model_name"],
            )
            results.append(success)

        logger.info(
            f"Batch stored {sum(results)}/{len(results)} embeddings successfully"
        )
        return results

    # Scene ordering operations (delegated to SceneOrderingOperations)
    def ensure_script_order(self, script_id: str) -> bool:
        """Ensure all scenes have proper script_order values.

        Args:
            script_id: Script ID to check

        Returns:
            True if successful
        """
        return self.ordering.ensure_script_order(script_id)

    def reorder_scenes(
        self,
        script_id: str,
        scene_order: list[str],
        order_type: SceneOrderType = SceneOrderType.SCRIPT,
    ) -> bool:
        """Reorder scenes according to provided order.

        Args:
            script_id: Script ID
            scene_order: List of scene IDs in desired order
            order_type: Type of ordering to update

        Returns:
            True if successful
        """
        success = self.ordering.reorder_scenes(script_id, scene_order, order_type)

        # Update graph edges if successful
        if success and order_type != SceneOrderType.SCRIPT:
            # Get scene nodes
            scene_nodes = []
            for scene_id in scene_order:
                nodes = self.graph.find_nodes(node_type="scene", entity_id=scene_id)
                if nodes:
                    scene_nodes.append(nodes[0].id)

            # Update scene sequence in graph
            if scene_nodes:
                self.update_scene_order(
                    script_id,
                    {node_id: i for i, node_id in enumerate(scene_nodes)},
                    order_type,
                )

        return success

    def infer_temporal_order(self, script_id: str) -> dict[str, int]:
        """Infer temporal (chronological) order of scenes.

        Args:
            script_id: Script ID to analyze

        Returns:
            Dictionary mapping scene_id to temporal_order
        """
        return self.ordering.infer_temporal_order(script_id)

    def analyze_scene_dependencies(self, script_id: str) -> list[SceneDependency]:
        """Analyze and create logical dependencies between scenes.

        Args:
            script_id: Script ID to analyze

        Returns:
            List of SceneDependency objects created
        """
        return self.ordering.analyze_logical_dependencies(script_id)

    def get_scene_dependencies(
        self,
        scene_id: str,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get dependencies for a specific scene.

        Args:
            scene_id: Scene ID
            direction: 'from' (outgoing), 'to' (incoming), or 'both'

        Returns:
            List of dependency dictionaries
        """
        return self.ordering.get_scene_dependencies(scene_id, direction)

    def calculate_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order based on dependencies.

        Args:
            script_id: Script ID

        Returns:
            List of scene IDs in logical order
        """
        return self.ordering.get_logical_order(script_id)

    def validate_scene_ordering(self, script_id: str) -> dict[str, Any]:
        """Validate consistency across different ordering systems.

        Args:
            script_id: Script ID to validate

        Returns:
            Dictionary with validation results
        """
        return self.ordering.validate_ordering_consistency(script_id)
