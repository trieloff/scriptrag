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

# Constants
MAX_LOCATION_LENGTH = 200  # Maximum length for location strings to prevent ReDoS
MAX_CHARACTER_NAME_WORDS = 3  # Maximum words in character names
TIME_ORDER = [
    "dawn",
    "morning",
    "day",
    "afternoon",
    "dusk",
    "evening",
    "night",
]  # Temporal progression order

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
                # Using parameterized queries to prevent SQL injection
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

    # Direct graph operations (for test compatibility)
    def add_node(
        self,
        node_type: str,
        entity_id: str | None = None,
        label: str | None = None,
        properties: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> str:
        """Add a new node to the graph.

        Args:
            node_type: Type of node
            entity_id: Reference to entity in another table
            label: Human-readable label
            properties: Additional properties
            node_id: Specific node ID (generated if None)

        Returns:
            Node ID
        """
        return self.graph.add_node(
            node_type=node_type,
            entity_id=entity_id,
            label=label,
            properties=properties,
            node_id=node_id,
        )

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID.

        Args:
            node_id: ID of the node to retrieve

        Returns:
            GraphNode if found, None otherwise
        """
        return self.graph.get_node(node_id)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> str:
        """Add an edge between two nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of edge
            properties: Additional properties
            edge_id: Specific edge ID (generated if None)

        Returns:
            Edge ID
        """
        return self.graph.add_edge(
            from_node_id=source_id,
            to_node_id=target_id,
            edge_type=edge_type,
            properties=properties,
            edge_id=edge_id,
        )

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

    # Enhanced Scene Operations for Phase 5.2
    def update_scene_metadata(
        self,
        scene_node_id: str,
        heading: str | None = None,
        description: str | None = None,
        time_of_day: str | None = None,
        location: str | None = None,
        propagate_to_graph: bool = True,
    ) -> bool:
        """Update scene metadata with graph propagation.

        Args:
            scene_node_id: Scene node ID to update
            heading: New scene heading
            description: New scene description/content
            time_of_day: New time of day
            location: New location (will update location graph relationships)
            propagate_to_graph: Whether to update graph relationships

        Returns:
            True if successful
        """
        try:
            # Get current scene node
            scene_node = self.graph.get_node(scene_node_id)
            if not scene_node:
                logger.error(f"Scene {scene_node_id} not found")
                return False

            # Update scene properties
            updates = {}
            if heading is not None:
                updates["heading"] = heading
            if description is not None:
                updates["description"] = description
            if time_of_day is not None:
                updates["time_of_day"] = time_of_day

            if updates:
                self.graph.update_node(scene_node_id, properties=updates)

            # Handle location changes with graph propagation
            if location is not None and propagate_to_graph:
                self._update_scene_location_with_propagation(scene_node_id, location)

            # Handle character appearances updates if content changed
            if description is not None and propagate_to_graph:
                self._update_character_appearances(scene_node_id, description)

            logger.info(f"Updated scene {scene_node_id} with graph propagation")
            return True

        except Exception as e:
            logger.error(f"Failed to update scene {scene_node_id}: {e}")
            return False

    def _update_scene_location_with_propagation(
        self, scene_node_id: str, new_location: str
    ) -> None:
        """Update scene location with graph relationship updates."""
        try:
            # Get script node for this scene
            script_edges = self.graph.find_edges(
                to_node_id=scene_node_id, edge_type="HAS_SCENE"
            )
            if not script_edges:
                logger.error(f"No script found for scene {scene_node_id}")
                return

            script_node_id = script_edges[0].from_node_id

            # Remove existing location connection
            existing_location_edges = self.graph.find_edges(
                from_node_id=scene_node_id, edge_type="AT_LOCATION"
            )
            for edge in existing_location_edges:
                self.graph.delete_edge(edge.id)

            # Parse location and find/create location node
            import re

            # Simplified regex to prevent ReDoS attacks
            # Limit input length and use more specific patterns
            location_str = new_location.strip()[:MAX_LOCATION_LENGTH]
            location_match = re.match(
                r"^(INT\.|EXT\.|I/E\.)?[\s]*([^-]+?)(?:[\s]*-[\s]*(.+))?$",
                location_str,
                re.IGNORECASE,
            )

            if location_match:
                int_ext, location_name, time_part = location_match.groups()
                if int_ext:
                    int_ext = int_ext.strip().upper()
                    if not int_ext.endswith("."):
                        int_ext += "."
                interior = int_ext == "INT." if int_ext else True
            else:
                location_name = new_location.strip()
                interior = True
                time_part = None

            # Create location model
            location_obj = Location(
                interior=interior,
                name=location_name,
                time=time_part,
                raw_text=new_location,
            )

            # Find or create location node
            existing_locations = self.graph.find_nodes(
                node_type="location",
                label_pattern=location_name.upper(),
            )

            if existing_locations:
                location_node_id = existing_locations[0].id
            else:
                location_node_id = self.create_location_node(
                    location_obj, script_node_id
                )

            # Connect scene to location
            self.connect_scene_to_location(scene_node_id, location_node_id)

        except Exception as e:
            logger.error(f"Failed to update location for scene {scene_node_id}: {e}")

    def _update_character_appearances(
        self, scene_node_id: str, new_content: str
    ) -> None:
        """Update character appearances based on new scene content."""
        try:
            # Get script node for this scene
            script_edges = self.graph.find_edges(
                to_node_id=scene_node_id, edge_type="HAS_SCENE"
            )
            if not script_edges:
                return

            script_node_id = script_edges[0].from_node_id

            # Remove existing character appearances
            existing_char_edges = self.graph.find_edges(
                to_node_id=scene_node_id, edge_type="APPEARS_IN"
            )
            for edge in existing_char_edges:
                self.graph.delete_edge(edge.id)

            # Extract characters from new content
            characters = self._extract_characters_from_content(new_content)

            # Connect characters to scene
            for char_name in characters:
                # Find or create character node
                existing_chars = self.graph.find_nodes(
                    node_type="character",
                    label_pattern=char_name.upper(),
                )

                if existing_chars:
                    char_node_id = existing_chars[0].id
                else:
                    character = Character(name=char_name)
                    char_node_id = self.create_character_node(character, script_node_id)

                # Connect character to scene
                self.connect_character_to_scene(char_node_id, scene_node_id)

        except Exception as e:
            logger.error(
                f"Failed to update character appearances for scene {scene_node_id}: {e}"
            )

    def _extract_characters_from_content(self, content: str) -> list[str]:
        """Extract character names from scene content.

        Uses Fountain format rules to identify character names:
        - Must be in uppercase
        - Appears on its own line
        - May have extensions in parentheses (V.O., O.S., etc.)
        - Not a scene heading or transition
        """
        import re

        characters = set()
        lines = content.split("\n")

        # Common screenplay transitions and technical terms to exclude
        exclusions = {
            "INT.",
            "EXT.",
            "I/E.",
            "FADE IN",
            "FADE OUT",
            "FADE TO",
            "CUT TO",
            "DISSOLVE TO",
            "THE END",
            "MONTAGE",
            "FLASHBACK",
            "CONTINUOUS",
            "LATER",
            "MOMENTS LATER",
            "SAME",
            "BACK TO",
            "INTERCUT",
            "TITLE",
            "SUPER",
            "CLOSE ON",
            "ANGLE ON",
            "INSERT",
            "POV",
            "REVERSE ANGLE",
            "WIDE",
            "TIGHT ON",
        }

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Character names must be uppercase
            if not line.isupper():
                continue

            # Remove parenthetical extensions (V.O.), (O.S.), (CONT'D), etc.
            character_base = re.sub(r"\s*\([^)]+\)\s*$", "", line).strip()

            # Skip if it's a known exclusion
            if any(excl in character_base for excl in exclusions):
                continue

            # Character names shouldn't start with parentheses or end with colons
            if character_base.startswith("(") or character_base.endswith(":"):
                continue

            # Check word count
            if len(character_base.split()) > MAX_CHARACTER_NAME_WORDS:
                continue

            # Look ahead to see if next non-empty line is dialogue or parenthetical
            # This helps confirm it's actually a character name
            is_character = False
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line:
                    # If next line is parenthetical or doesn't look like a scene heading
                    if next_line.startswith("(") or (
                        not next_line.isupper()
                        and not any(
                            next_line.startswith(prefix)
                            for prefix in ["INT.", "EXT.", "I/E."]
                        )
                    ):
                        is_character = True
                    break

            if is_character or (
                # Fallback: accept if it looks like a character name
                character_base
                and len(character_base) > 1
                and not character_base[0].isdigit()
            ):
                characters.add(character_base)

        return list(characters)

    def delete_scene_with_references(self, scene_node_id: str) -> bool:
        """Delete a scene while maintaining reference integrity.

        Args:
            scene_node_id: Scene node ID to delete

        Returns:
            True if successful
        """
        # Use transaction to ensure atomicity
        with self.connection.transaction():
            try:
                # Get scene node
                scene_node = self.graph.get_node(scene_node_id)
                if not scene_node:
                    logger.error(f"Scene {scene_node_id} not found")
                    return False

                # Get script for re-indexing
                script_edges = self.graph.find_edges(
                    to_node_id=scene_node_id, edge_type="HAS_SCENE"
                )
                if not script_edges:
                    logger.error(f"No script found for scene {scene_node_id}")
                    return False

                script_node_id = script_edges[0].from_node_id
                scene_order = scene_node.properties.get("script_order", 0)

                # Remove all dependencies involving this scene
                self._remove_scene_dependencies(scene_node_id)

                # Remove all edges connected to this scene
                all_edges = self.graph.find_edges(from_node_id=scene_node_id)
                all_edges.extend(self.graph.find_edges(to_node_id=scene_node_id))

                for edge in all_edges:
                    self.graph.delete_edge(edge.id)

                # Delete the scene node
                self.graph.delete_node(scene_node_id)

                # Re-index remaining scenes
                self._reindex_scenes_after_deletion(script_node_id, scene_order)

                logger.info(f"Deleted scene {scene_node_id} with reference integrity")
                return True

            except Exception as e:
                logger.error(f"Failed to delete scene {scene_node_id}: {e}")
                return False

    def _remove_scene_dependencies(self, scene_node_id: str) -> None:
        """Remove all dependencies involving a scene."""
        try:
            with self.connection.transaction() as conn:
                # Remove dependencies where this scene is involved
                conn.execute(
                    """
                    DELETE FROM scene_dependencies
                    WHERE from_scene_id = ? OR to_scene_id = ?
                    """,
                    (scene_node_id, scene_node_id),
                )

        except Exception as e:
            logger.error(
                f"Failed to remove dependencies for scene {scene_node_id}: {e}"
            )

    def _reindex_scenes_after_deletion(
        self, script_node_id: str, deleted_scene_order: int
    ) -> None:
        """Re-index scene orders after deletion."""
        try:
            # Get all remaining scenes
            scenes = self.get_script_scenes(script_node_id, SceneOrderType.SCRIPT)

            # Update script_order for scenes that come after deleted scene
            updates = []
            for scene in scenes:
                current_order = scene.properties.get("script_order", 0)
                if current_order > deleted_scene_order:
                    new_order = current_order - 1
                    updates.append((scene.id, new_order))

            # Apply updates
            for scene_id, new_order in updates:
                self.graph.update_node(scene_id, properties={"script_order": new_order})

            logger.info(f"Re-indexed {len(updates)} scenes after deletion")

        except Exception as e:
            logger.error(f"Failed to re-index scenes: {e}")

    def inject_scene_at_position(
        self,
        script_node_id: str,
        scene: Scene,
        position: int,
        characters: list[str] | None = None,
        location: str | None = None,
    ) -> str | None:
        """Inject a new scene at specified position with full re-indexing.

        Args:
            script_node_id: Script node ID
            scene: Scene model to inject
            position: Position to insert (1-based)
            characters: List of character names appearing in scene
            location: Location name if different from scene heading

        Returns:
            Scene node ID if successful, None otherwise
        """
        # Use transaction to ensure atomicity
        with self.connection.transaction():
            try:
                # Get current scenes to validate position
                current_scenes = self.get_script_scenes(
                    script_node_id, SceneOrderType.SCRIPT
                )
                max_position = len(current_scenes) + 1

                if position < 1 or position > max_position:
                    logger.error(
                        f"Invalid position {position}. Must be 1-{max_position}"
                    )
                    return None

                # Shift existing scenes to make room
                self._shift_scenes_for_injection(script_node_id, position)

                # Create the new scene with specified position
                scene_data = scene.model_dump()
                scene_data["script_order"] = position
                scene_node_id = self.create_scene_node(scene, script_node_id)

                # Update the node with correct position
                self.graph.update_node(
                    scene_node_id, properties={"script_order": position}
                )

                # Connect characters if provided
                if characters:
                    for char_name in characters:
                        # Find or create character
                        existing_chars = self.graph.find_nodes(
                            node_type="character",
                            label_pattern=char_name.upper(),
                        )

                        if existing_chars:
                            char_node_id = existing_chars[0].id
                        else:
                            character = Character(name=char_name)
                            char_node_id = self.create_character_node(
                                character, script_node_id
                            )

                        self.connect_character_to_scene(char_node_id, scene_node_id)

                # Connect location if provided
                if location:
                    self._update_scene_location_with_propagation(
                        scene_node_id, location
                    )

                # Re-analyze dependencies for affected scenes
                self._reanalyze_dependencies_after_injection(script_node_id, position)

                logger.info(f"Injected scene at position {position}")
                return scene_node_id

            except Exception as e:
                logger.error(f"Failed to inject scene at position {position}: {e}")
                return None

    def _shift_scenes_for_injection(self, script_node_id: str, position: int) -> None:
        """Shift scene orders to make room for injection."""
        try:
            scenes = self.get_script_scenes(script_node_id, SceneOrderType.SCRIPT)

            # Shift scenes at and after the insertion position
            for scene in scenes:
                current_order = scene.properties.get("script_order", 0)
                if current_order >= position:
                    new_order = current_order + 1
                    self.graph.update_node(
                        scene.id, properties={"script_order": new_order}
                    )

        except Exception as e:
            logger.error(f"Failed to shift scenes for injection: {e}")

    def _reanalyze_dependencies_after_injection(
        self, script_node_id: str, injection_position: int
    ) -> None:
        """Re-analyze dependencies after scene injection."""
        try:
            # Get script ID for dependency analysis
            script_node = self.graph.get_node(script_node_id)
            if script_node and "script_id" in script_node.properties:
                script_id = script_node.properties["script_id"]

                # Run dependency analysis
                self.ordering.analyze_logical_dependencies(script_id)

                logger.info(
                    f"Re-analyzed dependencies after injection at position "
                    f"{injection_position}"
                )
        except Exception as e:
            logger.error(f"Failed to re-analyze dependencies: {e}")

    def validate_story_continuity(self, script_node_id: str) -> dict[str, Any]:
        """Validate story continuity across all scenes.

        Args:
            script_node_id: Script node ID to validate

        Returns:
            Dictionary with continuity validation results
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "character_continuity": {},
            "location_continuity": {},
            "temporal_continuity": {},
        }

        try:
            scenes = self.get_script_scenes(script_node_id, SceneOrderType.SCRIPT)

            # Bulk fetch all character and location relationships
            scene_ids = [scene.id for scene in scenes]

            # Get all character edges in one query
            all_char_edges = []
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT from_node_id, to_node_id
                    FROM edges
                    WHERE edge_type = 'APPEARS_IN'
                    AND to_node_id IN ({",".join(["?" for _ in scene_ids])})
                    """,
                    scene_ids,
                )
                all_char_edges = cursor.fetchall()

            # Build scene-to-characters mapping
            scene_characters: dict[str, list[str]] = {}
            for from_id, to_id in all_char_edges:
                if to_id not in scene_characters:
                    scene_characters[to_id] = []
                scene_characters[to_id].append(from_id)

            # Check character continuity
            character_first_appearance = {}
            for scene in scenes:
                scene_order = scene.properties.get("script_order", 0)

                # Get characters in this scene from pre-fetched data
                char_node_ids = scene_characters.get(scene.id, [])

                for char_node_id in char_node_ids:
                    char_node = self.graph.get_node(char_node_id)
                    if char_node:
                        char_name = char_node.properties.get("name", "")
                        if char_name not in character_first_appearance:
                            character_first_appearance[char_name] = scene_order
                        else:
                            # Check if character appears without proper introduction
                            if scene_order < character_first_appearance[
                                char_name
                            ] and isinstance(results["warnings"], list):
                                results["warnings"].append(
                                    {
                                        "type": "character_continuity",
                                        "message": f"Character {char_name} appears "
                                        f"before introduction",
                                        "scene_id": scene.id,
                                        "scene_order": scene_order,
                                    }
                                )

            results["character_continuity"] = character_first_appearance

            # Bulk fetch all location relationships
            all_loc_edges = []
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT from_node_id, to_node_id
                    FROM edges
                    WHERE edge_type = 'AT_LOCATION'
                    AND from_node_id IN ({",".join(["?" for _ in scene_ids])})
                    """,
                    scene_ids,
                )
                all_loc_edges = cursor.fetchall()

            # Build scene-to-location mapping
            scene_locations = {}
            for from_id, to_id in all_loc_edges:
                scene_locations[from_id] = to_id

            # Check location consistency
            location_usage: dict[str, list[int]] = {}
            for scene in scenes:
                loc_node_id = scene_locations.get(scene.id)
                if loc_node_id:
                    loc_node = self.graph.get_node(loc_node_id)
                    if loc_node:
                        loc_name = loc_node.properties.get("name", "")
                        if loc_name not in location_usage:
                            location_usage[loc_name] = []
                        location_usage[loc_name].append(
                            scene.properties.get("script_order", 0)
                        )

            results["location_continuity"] = location_usage

            # Check temporal order consistency
            temporal_issues = []
            for i, scene in enumerate(scenes[:-1]):
                current_time = scene.properties.get("time_of_day", "")
                next_scene = scenes[i + 1]
                next_time = next_scene.properties.get("time_of_day", "")

                # Simple temporal progression check
                if (
                    current_time
                    and next_time
                    and self._is_temporal_regression(current_time, next_time)
                ):
                    temporal_issues.append(
                        {
                            "from_scene": scene.id,
                            "to_scene": next_scene.id,
                            "from_time": current_time,
                            "to_time": next_time,
                        }
                    )

            if temporal_issues and isinstance(results["warnings"], list):
                results["warnings"].append(
                    {
                        "type": "temporal_continuity",
                        "message": f"Found {len(temporal_issues)} potential "
                        f"temporal regressions",
                        "issues": temporal_issues,
                    }
                )

            results["temporal_continuity"] = temporal_issues

        except Exception as e:
            logger.error(f"Failed to validate story continuity: {e}")
            results["is_valid"] = False
            if isinstance(results["errors"], list):
                results["errors"].append(
                    {"type": "validation_error", "message": str(e)}
                )

        return results

    def _is_temporal_regression(self, current_time: str, next_time: str) -> bool:
        """Check if there's a temporal regression between times."""
        time_order = TIME_ORDER

        current_time_lower = current_time.lower()
        next_time_lower = next_time.lower()

        current_idx = -1
        next_idx = -1

        for i, time_word in enumerate(time_order):
            if time_word in current_time_lower:
                current_idx = i
                break

        for i, time_word in enumerate(time_order):
            if time_word in next_time_lower:
                next_idx = i
                break

        # If both times are recognized and next comes before current, it's a regression
        return current_idx != -1 and next_idx != -1 and next_idx < current_idx
