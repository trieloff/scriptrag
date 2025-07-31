"""Location-related operations for screenplay management.

This module handles location creation, connections, and analysis.
"""

import re
from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import Location

from .connection import DatabaseConnection
from .graph import GraphDatabase, GraphNode

# Constants
MAX_LOCATION_LENGTH = 200  # Maximum length for location strings to prevent ReDoS

logger = get_logger(__name__)


class LocationOperations:
    """Operations for managing locations and their relationships."""

    def __init__(self, connection: DatabaseConnection, graph: GraphDatabase) -> None:
        """Initialize location operations.

        Args:
            connection: Database connection instance
            graph: Graph database instance
        """
        self.connection = connection
        self.graph = graph

    def create_location_node(self, location: Location, script_node_id: str) -> str:
        """Create a location node in the graph.

        Args:
            location: Location model instance
            script_node_id: Parent script node ID

        Returns:
            Location node ID
        """
        # Validate location name length
        if len(location.name) > MAX_LOCATION_LENGTH:
            logger.warning(
                f"Location name too long ({len(location.name)} chars), truncating"
            )
            location.name = location.name[:MAX_LOCATION_LENGTH]

        # Create a unique entity ID for this location
        import hashlib

        entity_id = hashlib.md5(
            location.name.encode(), usedforsecurity=False
        ).hexdigest()[:16]

        # Create location node
        location_node_id = self.graph.add_node(
            node_type="location",
            entity_id=entity_id,
            label=location.name,
            properties={
                "interior": location.interior,
                "time": location.time,
                "raw_text": location.raw_text,
            },
        )

        # Connect to script
        self.graph.add_edge(
            from_node_id=script_node_id,
            to_node_id=location_node_id,
            edge_type="has_location",
            properties={"interior": location.interior},
        )

        logger.info(f"Created location node: {location_node_id} for {location.name}")
        return location_node_id

    def connect_scene_to_location(
        self, scene_node_id: str, location_node_id: str, time_of_day: str | None = None
    ) -> str | None:
        """Connect a scene to its location.

        Args:
            scene_node_id: Scene node ID
            location_node_id: Location node ID
            time_of_day: Optional time of day for the scene

        Returns:
            Edge ID if created
        """
        properties = {}
        if time_of_day:
            properties["time_of_day"] = time_of_day

        edge_id = self.graph.add_edge(
            from_node_id=scene_node_id,
            to_node_id=location_node_id,
            edge_type="takes_place_in",
            properties=properties,
        )

        logger.debug(f"Connected scene {scene_node_id} to location {location_node_id}")
        return edge_id

    def get_location_scenes(self, location_node_id: str) -> list[GraphNode]:
        """Get all scenes that take place in a location.

        Args:
            location_node_id: Location node ID

        Returns:
            List of scene nodes
        """
        scenes = self.graph.get_neighbors(
            location_node_id, direction="incoming", edge_type="takes_place_in"
        )
        logger.debug(f"Found {len(scenes)} scenes for location {location_node_id}")
        return scenes

    def update_scene_location_with_propagation(
        self,
        scene_node_id: str,
        new_location: str,
        script_node_id: str,
        _update_characters: bool = True,
    ) -> dict[str, Any]:
        """Update a scene's location with optional character propagation.

        Args:
            scene_node_id: Scene node ID to update
            new_location: New location name
            script_node_id: Script node ID
            update_characters: Whether to update character appearances

        Returns:
            Dictionary with update results
        """
        results: dict[str, Any] = {
            "location_updated": False,
            "new_location_created": False,
            "characters_updated": 0,
            "location_node_id": None,
        }

        try:
            # Remove existing location connections
            existing_edges = self.graph.find_edges(
                from_node_id=scene_node_id, edge_type="takes_place_in"
            )
            for edge in existing_edges:
                self.graph.delete_edge(edge.id)

            # Find or create location node
            location_nodes = self.graph.get_nodes_by_property(
                "location", "label", new_location
            )

            if location_nodes:
                # Use existing location
                location_node_id = location_nodes[0].id
            else:
                # Create new location
                location = Location(
                    name=new_location,
                    interior="INT" in new_location.upper(),
                    raw_text=new_location,
                )
                location_node_id = self.create_location_node(location, script_node_id)
                results["new_location_created"] = True

            results["location_node_id"] = location_node_id

            # Connect scene to new location
            self.connect_scene_to_location(scene_node_id, location_node_id)
            results["location_updated"] = True

            # Update scene properties
            scene_node = self.graph.get_node(scene_node_id)
            if scene_node:
                scene_node.properties["location"] = new_location
                self.graph.update_node(
                    scene_node_id,
                    properties=scene_node.properties,
                )

            logger.info(
                f"Updated scene {scene_node_id} location to {new_location} "
                f"(node: {location_node_id})"
            )

        except Exception as e:
            logger.error(f"Failed to update scene location: {e}")
            results["error"] = str(e)

        return results

    def analyze_location_flow(self, script_node_id: str) -> list[dict[str, Any]]:
        """Analyze the flow between locations in a script.

        Args:
            script_node_id: Script node ID

        Returns:
            List of location transitions
        """
        # Get all scenes in order
        scenes = self.graph.get_neighbors(
            script_node_id, direction="outgoing", edge_type="contains_scene"
        )

        # Sort by script order
        sorted_scenes = sorted(
            scenes, key=lambda s: s.properties.get("script_order", float("inf"))
        )

        transitions = []
        prev_location = None

        for scene in sorted_scenes:
            # Get scene's location
            location_edges = self.graph.find_edges(
                from_node_id=scene.id, edge_type="takes_place_in"
            )

            if location_edges:
                location_node = self.graph.get_node(location_edges[0].to_node_id)
                if location_node:
                    current_location = location_node.label

                    if prev_location and prev_location != current_location:
                        transitions.append(
                            {
                                "from_location": prev_location,
                                "to_location": current_location,
                                "scene_id": scene.id,
                                "script_order": scene.properties.get("script_order"),
                            }
                        )

                    prev_location = current_location

        return transitions

    def get_location_statistics(self, script_node_id: str) -> dict[str, Any]:
        """Get statistics about location usage in a script.

        Args:
            script_node_id: Script node ID

        Returns:
            Dictionary of location statistics
        """
        # Get all locations
        locations = self.graph.get_neighbors(
            script_node_id, direction="outgoing", edge_type="has_location"
        )

        stats: dict[str, Any] = {
            "total_locations": len(locations),
            "location_usage": {},
            "most_used_location": None,
            "interior_vs_exterior": {"INT": 0, "EXT": 0, "OTHER": 0},
        }

        max_usage = 0
        for location in locations:
            # Count scenes in this location
            scenes = self.get_location_scenes(location.id)
            usage_count = len(scenes)

            stats["location_usage"][location.label] = usage_count

            if usage_count > max_usage:
                max_usage = usage_count
                stats["most_used_location"] = {
                    "name": location.label,
                    "scene_count": usage_count,
                }

            # Count INT/EXT
            interior = location.properties.get("interior", None)
            if interior is True:
                stats["interior_vs_exterior"]["INT"] += 1
            elif interior is False:
                stats["interior_vs_exterior"]["EXT"] += 1
            else:
                stats["interior_vs_exterior"]["OTHER"] += 1

        return stats

    def parse_location_from_slug(self, slug_line: str) -> dict[str, Any]:
        """Parse location information from a scene slug line.

        Args:
            slug_line: Scene heading/slug line

        Returns:
            Dictionary with location info
        """
        # Basic pattern for slug lines: INT./EXT. LOCATION - TIME
        pattern = r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s+([^-]+)(?:\s*-\s*(.+))?$"
        match = re.match(pattern, slug_line.strip(), re.IGNORECASE)

        if match:
            setting = match.group(1).rstrip(".").upper()
            location = match.group(2).strip()
            time_of_day = match.group(3).strip() if match.group(3) else None

            return {
                "setting": setting,
                "location": location,
                "time_of_day": time_of_day,
                "is_valid": True,
            }

        return {
            "setting": None,
            "location": slug_line.strip(),  # Use whole line as location if no match
            "time_of_day": None,
            "is_valid": False,
        }
