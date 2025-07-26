"""Scene Management Operations.

This module provides advanced scene management functionality including
temporal order inference, logical dependency analysis, and scene reordering
operations.
"""

import re
from datetime import time
from typing import Any, ClassVar

from scriptrag.config import get_logger
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.graph import GraphDatabase, GraphNode
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Location, SceneOrderType

logger = get_logger(__name__)


class SceneManager:
    """Manages scene ordering, dependencies, and relationships."""

    # Constants for temporal analysis
    DEFAULT_SCENE_DURATION_MINUTES: ClassVar[int] = 5  # Default duration per scene

    # Time constants in minutes
    MINUTES_PER_HOUR: ClassVar[int] = 60
    MINUTES_PER_DAY: ClassVar[int] = 1440
    MINUTES_PER_WEEK: ClassVar[int] = 10080
    MINUTES_PER_MONTH: ClassVar[int] = 43200  # Approx 30 days
    MINUTES_PER_YEAR: ClassVar[int] = 525600

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize scene manager.

        Args:
            connection: Database connection instance
        """
        self.connection = connection
        self.graph = GraphDatabase(connection)
        self.operations = GraphOperations(connection)

    # Time patterns for temporal analysis
    TIME_PATTERNS: ClassVar[list[tuple[str, time | None]]] = [
        # Standard DAY/NIGHT/MORNING/etc
        (r"\b(DAWN|SUNRISE|EARLY MORNING|MORNING)\b", time(6, 0)),
        (r"\b(DAY|AFTERNOON|NOON|MIDDAY)\b", time(12, 0)),
        (r"\b(DUSK|SUNSET|EVENING|TWILIGHT)\b", time(18, 0)),
        (r"\b(NIGHT|MIDNIGHT|LATE NIGHT)\b", time(0, 0)),
        # Specific times like "3:00 PM"
        (r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", None),
        # Military time
        (r"\b(\d{2})(\d{2})\s*HOURS\b", None),
    ]

    # Temporal indicators in action/dialogue
    TEMPORAL_INDICATORS: ClassVar[list[tuple[str, int]]] = [
        (r"\b(LATER|MOMENTS LATER|SECONDS LATER)\b", 1),  # Very short time jump
        (r"\b(MINUTES LATER|SHORTLY AFTER)\b", 10),  # Minutes
        (r"\b(HOURS LATER|LATER THAT DAY)\b", MINUTES_PER_HOUR * 2),  # 2 hours
        (r"\b(THE NEXT DAY|NEXT MORNING|FOLLOWING DAY)\b", MINUTES_PER_DAY),  # Day
        (r"\b(DAYS LATER|FEW DAYS LATER)\b", MINUTES_PER_DAY * 3),  # 3 days
        (r"\b(WEEKS LATER|WEEK LATER)\b", MINUTES_PER_WEEK),  # Week
        (r"\b(MONTHS LATER|MONTH LATER)\b", MINUTES_PER_MONTH),  # Month
        (r"\b(YEARS LATER|YEAR LATER)\b", MINUTES_PER_YEAR),  # Year
        # Flashback indicators (negative time)
        (r"\b(FLASHBACK|EARLIER|PREVIOUSLY|YEARS AGO)\b", -1),
    ]

    def infer_temporal_order(self, script_node_id: str) -> dict[str, int]:
        """Infer temporal order of scenes based on time indicators.

        Args:
            script_node_id: Script node ID

        Returns:
            Dictionary mapping scene_node_id to temporal_order
        """
        # Get all scenes in script order
        scenes = self.operations.get_script_scenes(
            script_node_id, SceneOrderType.SCRIPT
        )

        if not scenes:
            return {}

        temporal_positions: dict[str, float] = {}
        current_time_minutes = 0.0

        for scene_node in scenes:
            scene_id = scene_node.id
            heading = scene_node.properties.get("heading", "")

            # Extract time from heading (not used yet, but will be in future)
            _ = self._extract_time_from_heading(heading)

            # Check for temporal jumps in scene content
            time_jump = self._detect_temporal_jump(scene_node)

            if time_jump is not None:
                if time_jump < 0:
                    # Flashback - assign negative temporal position
                    temporal_positions[scene_id] = time_jump
                else:
                    current_time_minutes += time_jump
                    temporal_positions[scene_id] = current_time_minutes
            else:
                # Normal progression
                temporal_positions[scene_id] = current_time_minutes
                # Add small increment for scene duration
                current_time_minutes += self.DEFAULT_SCENE_DURATION_MINUTES

        # Convert positions to integer order
        sorted_scenes = sorted(temporal_positions.items(), key=lambda x: x[1])
        return {scene_id: idx + 1 for idx, (scene_id, _) in enumerate(sorted_scenes)}

    def _extract_time_from_heading(self, heading: str) -> time | None:
        """Extract time of day from scene heading."""
        if not heading:
            return None

        heading_upper = heading.upper()

        for pattern, default_time in self.TIME_PATTERNS:
            match = re.search(pattern, heading_upper)
            if match:
                if default_time:
                    return default_time
                # Parse specific time
                if "AM" in pattern or "PM" in pattern:
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    is_pm = match.group(3) == "PM"
                    if is_pm and hour != 12:
                        hour += 12
                    elif not is_pm and hour == 12:
                        hour = 0
                    return time(hour, minute)

        return None

    def _detect_temporal_jump(self, scene_node: GraphNode) -> float | None:
        """Detect temporal jumps in scene content."""
        # This would normally analyze scene elements, but for now
        # we'll just check the description
        description = scene_node.properties.get("description", "")

        if description:
            for pattern, minutes in self.TEMPORAL_INDICATORS:
                if re.search(pattern, description.upper()):
                    return float(minutes)

        return None

    def analyze_scene_dependencies(self, script_node_id: str) -> dict[str, list[str]]:
        """Analyze logical dependencies between scenes.

        Args:
            script_node_id: Script node ID

        Returns:
            Dictionary mapping scene_node_id to list of dependency scene_node_ids
        """
        scenes = self.operations.get_script_scenes(
            script_node_id, SceneOrderType.SCRIPT
        )

        dependencies: dict[str, list[str]] = {}

        # Build character appearance map
        character_scenes: dict[str, list[str]] = {}

        # Initialize dependencies dict
        for scene in scenes:
            dependencies[scene.id] = []

        # Batch fetch all character appearances for all scenes
        scene_ids = [scene.id for scene in scenes]
        if scene_ids:
            with self.connection.transaction() as conn:
                # Get all character appearances in one query
                results = conn.execute(
                    f"""
                    SELECT e.from_node_id as char_id, e.to_node_id as scene_id
                    FROM edges e
                    JOIN nodes n ON e.from_node_id = n.id
                    WHERE e.to_node_id IN ({",".join("?" * len(scene_ids))})
                    AND e.edge_type = 'APPEARS_IN'
                    AND n.node_type = 'character'
                    ORDER BY e.to_node_id
                    """,
                    scene_ids,
                ).fetchall()

                # Build the character_scenes map from results
                for char_id, scene_id in results:
                    if char_id not in character_scenes:
                        character_scenes[char_id] = []
                    character_scenes[char_id].append(scene_id)

        # Analyze dependencies based on character introductions
        for _, scene_list in character_scenes.items():
            if len(scene_list) > 1:
                # First appearance is a dependency for all later appearances
                first_scene = scene_list[0]
                for later_scene in scene_list[1:]:
                    if first_scene not in dependencies[later_scene]:
                        dependencies[later_scene].append(first_scene)

        # TODO: Add more dependency analysis:
        # - Plot elements (objects, information revealed)
        # - Location continuity
        # - Dialogue references

        return dependencies

    def update_scene_order(
        self,
        scene_node_id: str,
        new_position: int,
        order_type: SceneOrderType = SceneOrderType.SCRIPT,
    ) -> bool:
        """Update the position of a scene in the specified ordering.

        Args:
            scene_node_id: Scene node ID to move
            new_position: New position (1-based)
            order_type: Type of ordering to update

        Returns:
            True if successful
        """
        try:
            # Get the script this scene belongs to
            script_edges = self.graph.find_edges(
                to_node_id=scene_node_id, edge_type="HAS_SCENE"
            )

            if not script_edges:
                logger.error(f"Scene {scene_node_id} not found in any script")
                return False

            script_node_id = script_edges[0].from_node_id

            # Get all scenes in current order
            scenes = self.operations.get_script_scenes(script_node_id, order_type)

            # Find current scene
            current_idx = None
            for idx, scene in enumerate(scenes):
                if scene.id == scene_node_id:
                    current_idx = idx
                    break

            if current_idx is None:
                logger.error(f"Scene {scene_node_id} not found in {order_type} order")
                return False

            # Remove from current position and insert at new position
            scene_to_move = scenes.pop(current_idx)
            new_idx = max(0, min(new_position - 1, len(scenes)))
            scenes.insert(new_idx, scene_to_move)

            # Create new ordering map
            order_mapping = {scene.id: idx + 1 for idx, scene in enumerate(scenes)}

            # Update the database
            return self.operations.update_scene_order(
                script_node_id, order_mapping, order_type
            )

        except Exception as e:
            logger.error(f"Failed to update scene order: {e}")
            return False

    def update_scene_location(self, scene_node_id: str, new_location: str) -> bool:
        """Update the location of a scene.

        Args:
            scene_node_id: Scene node ID
            new_location: New location string (e.g., "INT. OFFICE - DAY")

        Returns:
            True if successful
        """
        try:
            # Parse the new location - more flexible regex
            location_match = re.match(
                r"^(INT\.|EXT\.|I/E\.|INT\s|EXT\s|I/E\s)?\s*(.+?)(?:\s+-\s+(.+))?$",
                new_location.strip(),
                re.IGNORECASE,
            )

            if location_match:
                int_ext, location_name, time_of_day = location_match.groups()
                # Normalize INT/EXT format
                if int_ext:
                    int_ext = int_ext.strip().upper()
                    if not int_ext.endswith("."):
                        int_ext += "."
            else:
                # Fallback: treat entire string as location name
                logger.warning(
                    f"Location format not standard, using as-is: {new_location}"
                )
                int_ext = ""
                location_name = new_location.strip()
                time_of_day = None

            # Update scene node properties
            with self.connection.transaction() as conn:
                conn.execute(
                    """
                    UPDATE nodes
                    SET properties_json = json_set(
                        properties_json,
                        '$.heading', ?,
                        '$.time_of_day', ?
                    )
                    WHERE id = ?
                    """,
                    (new_location, time_of_day, scene_node_id),
                )

                # Also update or create location node connection
                # First, remove existing location connection
                conn.execute(
                    """
                    DELETE FROM edges
                    WHERE from_node_id = ? AND edge_type = 'AT_LOCATION'
                    """,
                    (scene_node_id,),
                )

                # Find or create location node
                location_nodes = list(
                    conn.execute(
                        """
                        SELECT id FROM nodes
                        WHERE node_type = 'location'
                        AND json_extract(properties_json, '$.name') = ?
                        """,
                        (location_name.upper(),),
                    )
                )

                if location_nodes:
                    location_node_id = location_nodes[0][0]
                else:
                    # Create new location node
                    # Get script node for this scene
                    script_edges = list(
                        conn.execute(
                            """
                            SELECT from_node_id FROM edges
                            WHERE to_node_id = ? AND edge_type = 'HAS_SCENE'
                            """,
                            (scene_node_id,),
                        )
                    )

                    if script_edges:
                        script_node_id = script_edges[0][0]
                        location = Location(
                            interior=int_ext.upper() == "INT.",
                            name=location_name,
                            time=time_of_day,
                            raw_text=new_location,
                        )
                        location_node_id = self.operations.create_location_node(
                            location, script_node_id
                        )

                # Connect scene to location
                self.operations.connect_scene_to_location(
                    scene_node_id, location_node_id
                )

            logger.info(f"Updated location for scene {scene_node_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update scene location: {e}")
            return False

    def get_scene_info(self, scene_node_id: str) -> dict[str, Any]:
        """Get detailed information about a scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            Dictionary with scene information
        """
        scene_node = self.graph.get_node(scene_node_id)
        if not scene_node:
            return {}

        info = {
            "id": scene_node_id,
            "heading": scene_node.properties.get("heading", ""),
            "script_order": scene_node.properties.get("script_order", 0),
            "temporal_order": scene_node.properties.get("temporal_order"),
            "logical_order": scene_node.properties.get("logical_order"),
            "description": scene_node.properties.get("description", ""),
            "time_of_day": scene_node.properties.get("time_of_day"),
            "estimated_duration": scene_node.properties.get("estimated_duration"),
        }

        # Get location
        location_edges = self.graph.find_edges(
            from_node_id=scene_node_id, edge_type="AT_LOCATION"
        )
        if location_edges:
            location_node = self.graph.get_node(location_edges[0].to_node_id)
            if location_node:
                info["location"] = location_node.label

        # Get characters
        character_nodes = self.graph.get_neighbors(
            scene_node_id, edge_type="APPEARS_IN", direction="in"
        )
        info["characters"] = [
            {"id": char.id, "name": char.label} for char in character_nodes
        ]

        # Get dependencies
        deps = self.analyze_scene_dependencies_for_single(scene_node_id)
        info["dependencies"] = deps

        return info

    def analyze_scene_dependencies_for_single(
        self, scene_node_id: str
    ) -> list[dict[str, Any]]:
        """Analyze dependencies for a single scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            List of dependency information
        """
        dependencies = []

        # Get characters in this scene
        characters = self.graph.get_neighbors(
            scene_node_id, edge_type="APPEARS_IN", direction="in"
        )

        for char in characters:
            # Find first appearance of this character
            char_scenes = self.operations.get_character_scenes(char.id)

            # Sort by script order
            char_scenes.sort(
                key=lambda s: s.properties.get("script_order", float("inf"))
            )

            if char_scenes and char_scenes[0].id != scene_node_id:
                # This character was introduced earlier
                first_scene = char_scenes[0]
                dependencies.append(
                    {
                        "type": "character_introduction",
                        "character": char.label,
                        "scene_id": first_scene.id,
                        "scene_heading": first_scene.properties.get("heading", ""),
                    }
                )

        return dependencies
