"""Script-level operations for screenplay management.

This module handles script and series-level operations including
scripts, seasons, and episodes.
"""

from scriptrag.config import get_logger
from scriptrag.models import Episode, Script, Season

from .connection import DatabaseConnection
from .graph import GraphDatabase

logger = get_logger(__name__)


class ScriptOperations:
    """Operations for managing scripts, seasons, and episodes."""

    def __init__(self, connection: DatabaseConnection, graph: GraphDatabase) -> None:
        """Initialize script operations.

        Args:
            connection: Database connection instance
            graph: Graph database instance
        """
        self.connection = connection
        self.graph = graph

    def create_script_graph(self, script: Script) -> str:
        """Create graph representation of a script.

        Args:
            script: Script model instance

        Returns:
            Script node ID
        """
        # First, ensure the script exists in the scripts table
        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO scripts (
                    id, title, author, format, genre, is_series,
                    source_file, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(script.id),
                    script.title,
                    script.author,
                    script.format,
                    script.genre,
                    script.is_series,
                    script.source_file,
                ),
            )

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

        logger.info(f"Created script graph node: {script_node_id} for {script.title}")
        return script_node_id

    def add_season_to_script(self, season: Season, script_node_id: str) -> str:
        """Add a season to a series script.

        Args:
            season: Season model instance
            script_node_id: Parent script node ID

        Returns:
            Season node ID
        """
        # Create season node
        season_node_id = self.graph.add_node(
            node_type="season",
            entity_id=str(season.id),
            label=f"Season {season.number}",
            properties={
                "season_number": season.number,
                "title": season.title,
                "episode_count": len(season.episodes),
            },
        )

        # Connect to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=season_node_id,
            edge_type="has_season",
            properties={"season_number": season.number},
        )

        logger.info(
            f"Added season {season.number} to script: "
            f"{script_node_id} -> {season_node_id}"
        )
        return season_node_id

    def add_episode_to_season(
        self,
        episode: Episode,
        season_node_id: str,
        script_node_id: str | None = None,
    ) -> str:
        """Add an episode to a season.

        Args:
            episode: Episode model instance
            season_node_id: Parent season node ID
            script_node_id: Optional script node ID for direct connection

        Returns:
            Episode node ID
        """
        # Create episode node
        episode_node_id = self.graph.add_node(
            node_type="episode",
            entity_id=str(episode.id),
            label=episode.title,
            properties={
                "episode_number": episode.number,
                "season_id": str(episode.season_id),
                "air_date": episode.air_date.isoformat() if episode.air_date else None,
                "director": episode.director,
                "writer": episode.writer,
            },
        )

        # Connect to season
        self.graph.add_edge(
            from_node_id=season_node_id,
            to_node_id=episode_node_id,
            edge_type="has_episode",
            properties={"episode_number": episode.number},
        )

        # Optionally connect directly to script
        if script_node_id:
            self.graph.add_edge(
                from_node_id=script_node_id,
                to_node_id=episode_node_id,
                edge_type="contains_episode",
                properties={
                    "season_id": str(episode.season_id),
                    "episode_number": episode.number,
                },
            )

        logger.info(
            f"Added episode {episode.number} to season: "
            f"{season_node_id} -> {episode_node_id}"
        )
        return episode_node_id

    def ensure_script_order(self, script_id: str) -> bool:
        """Ensure scenes in a script have proper ordering.

        Args:
            script_id: Script ID

        Returns:
            True if order was established/maintained
        """
        # Get script node
        script_nodes = self.graph.get_nodes_by_property(
            "script", "entity_id", script_id
        )
        if not script_nodes:
            logger.warning(f"Script node not found for ID: {script_id}")
            return False

        script_node_id = script_nodes[0].id

        # Get all scenes for this script
        scenes = self.graph.get_neighbors(
            script_node_id, direction="outgoing", edge_type="contains_scene"
        )

        if not scenes:
            logger.info(f"No scenes found for script: {script_id}")
            return True

        # Sort scenes by their position property if available
        sorted_scenes = sorted(
            scenes, key=lambda s: s.properties.get("scene_order", float("inf"))
        )

        # Create follows edges between consecutive scenes
        for i in range(len(sorted_scenes) - 1):
            current_scene = sorted_scenes[i]
            next_scene = sorted_scenes[i + 1]

            # Check if edge already exists
            existing_edges = self.graph.find_edges(
                from_node_id=current_scene.id,
                to_node_id=next_scene.id,
                edge_type="follows",
            )

            if not existing_edges:
                self.graph.add_edge(
                    from_node_id=current_scene.id,
                    to_node_id=next_scene.id,
                    edge_type="follows",
                    properties={"order_type": "script"},
                )

        logger.info(
            f"Ensured script order for {len(scenes)} scenes in script: {script_id}"
        )
        return True
