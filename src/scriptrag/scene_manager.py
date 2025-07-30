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

        # Enhanced dependency analysis
        self._analyze_prop_dependencies(scenes, dependencies)
        self._analyze_technical_dependencies(scenes, dependencies)
        self._analyze_location_continuity(scenes, dependencies)
        self._analyze_dialogue_references(scenes, dependencies)

        return dependencies

    def _analyze_prop_dependencies(
        self, scenes: list[GraphNode], dependencies: dict[str, list[str]]
    ) -> None:
        """Analyze prop dependencies between scenes.

        Identifies props mentioned in action lines and tracks their first appearance
        and subsequent uses to establish dependencies.

        Args:
            scenes: List of scene nodes
            dependencies: Dictionary to update with prop dependencies
        """
        # Track prop appearances: prop_name -> list of scene_ids
        prop_scenes: dict[str, list[str]] = {}

        for scene in scenes:
            scene_id = scene.id
            scene_props = self._extract_props_from_scene(scene)

            for prop in scene_props:
                if prop not in prop_scenes:
                    prop_scenes[prop] = []
                prop_scenes[prop].append(scene_id)

        # Establish dependencies based on prop introduction
        for _prop_name, scene_list in prop_scenes.items():
            if len(scene_list) > 1:
                # First appearance is a dependency for later uses
                first_scene = scene_list[0]
                for later_scene in scene_list[1:]:
                    if first_scene not in dependencies[later_scene]:
                        dependencies[later_scene].append(first_scene)

    def _extract_props_from_scene(self, scene_node: GraphNode) -> set[str]:
        """Extract props mentioned in a scene.

        Looks for:
        - Capitalized objects in action lines (e.g., "picks up the GUN")
        - Items mentioned with articles (e.g., "the briefcase", "a knife")
        - Common prop patterns

        Args:
            scene_node: Scene node to analyze

        Returns:
            Set of prop names found in the scene
        """
        props = set()

        # Get scene elements (action lines, dialogue, etc.)
        elements = scene_node.properties.get("elements", [])

        # Pattern to find likely props
        # Matches: THE/A/AN followed by capitalized word(s)
        # Or standalone capitalized words that are likely objects
        prop_patterns = [
            # "the GUN", "a BRIEFCASE"
            r"\b(?:the|a|an)\s+([A-Z][A-Z]*(?:\s+[A-Z]+)?)\b",
            r"\b([A-Z]{2,})\b",  # "GUN", "BULLETS" - standalone all-caps words
            # Action verbs with objects
            r"\b(?:picks up|grabs|holds|takes|drops|throws|uses|carries|"
            # lowercase objects after verbs
            r"opens|closes)\s+(?:the\s+|a\s+)?([a-z]+)\b",
        ]

        # Common prop words to exclude (character names, locations, etc.)
        exclude_words = {
            "INT",
            "EXT",
            "CUT",
            "FADE",
            "DISSOLVE",
            "CONTINUOUS",
            "DAY",
            "NIGHT",
            "MORNING",
            "EVENING",
            "LATER",
            "MOMENTS",
            "CLOSE",
            "WIDE",
            "ANGLE",
            "SHOT",
            "VIEW",
            "BACK",
            "YES",
            "NO",
            "OKAY",
            "BEAT",
            "PAUSE",
            "SILENCE",
            "TO",
            "FROM",
            "THE",
            "AND",
            "OR",
            "IN",
            "ON",
            "AT",
            "HE",
            "SHE",
            "THEY",
            "WE",
            "IT",
            "SARAH",
            "JOHN",
            "INTO",
            "UP",
            "DOWN",
            "OVER",
            "UNDER",
            "THROUGH",
            "FADE OUT",
            "CUT TO",
            "OFFICE",
            "STREET",
            "HOME",
            "ENTERS",
            "EXITS",
            "WALKS",
            "RUNS",
            "STANDS",
            "SITS",
        }

        for element in elements:
            if isinstance(element, dict):
                element_type = element.get("type", "")
                text = element.get("text", "")

                # Only analyze action lines
                if element_type == "action" and text:
                    # Apply each pattern
                    for pattern in prop_patterns:
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            prop = match.group(1).strip().upper()
                            # Filter out common non-prop words
                            if prop and prop not in exclude_words and len(prop) > 1:
                                props.add(prop)

        return props

    def _analyze_technical_dependencies(
        self, scenes: list[GraphNode], dependencies: dict[str, list[str]]
    ) -> None:
        """Analyze technical requirements and dependencies.

        Identifies:
        - Sound cues (SFX:, MUSIC:)
        - VFX requirements (VFX:, CGI:, SPECIAL EFFECT:)
        - Costume changes and requirements

        Args:
            scenes: List of scene nodes
            dependencies: Dictionary to update with technical dependencies
        """
        # Track technical elements: element_type -> {element_name -> list of scene_ids}
        tech_elements: dict[str, dict[str, list[str]]] = {
            "sound": {},
            "vfx": {},
            "costume": {},
        }

        for scene in scenes:
            scene_id = scene.id
            tech_reqs = self._extract_technical_requirements(scene)

            # Track each type of technical requirement
            for req_type, requirements in tech_reqs.items():
                for req_name in requirements:
                    if req_name not in tech_elements[req_type]:
                        tech_elements[req_type][req_name] = []
                    tech_elements[req_type][req_name].append(scene_id)

        # Establish dependencies for recurring technical elements
        for req_type, elements in tech_elements.items():
            for _element_name, scene_list in elements.items():
                if len(scene_list) > 1 and req_type in ["costume", "vfx"]:
                    # For costumes and recurring effects, first appearance matters
                    first_scene = scene_list[0]
                    for later_scene in scene_list[1:]:
                        if first_scene not in dependencies[later_scene]:
                            dependencies[later_scene].append(first_scene)

    def _extract_technical_requirements(
        self, scene_node: GraphNode
    ) -> dict[str, set[str]]:
        """Extract technical requirements from a scene.

        Args:
            scene_node: Scene node to analyze

        Returns:
            Dictionary with sets of requirements by type (sound, vfx, costume)
        """
        requirements: dict[str, set[str]] = {
            "sound": set(),
            "vfx": set(),
            "costume": set(),
        }

        elements = scene_node.properties.get("elements", [])

        # Patterns for technical requirements
        sound_patterns = [
            r"(?:SFX|SOUND|MUSIC):\s*(.+?)(?:\.|$)",
            r"\b(?:plays|hear|sounds? of|sound of)\s+(.+?)(?:\.|,|$)",
            r"\[([^\]]+(?:music|sound|song)[^\]]*)\]",
        ]

        vfx_patterns = [
            r"(?:VFX|CGI|SPECIAL EFFECT|VISUAL EFFECT):\s*(.+?)(?:\.|$)",
            r"\[([^\]]+(?:morphs?|transforms?|disappears?|appears?|explodes?)[^\]]*)\]",
            r"\b(?:magical|supernatural|impossible)\s+(.+?)(?:\.|,|$)",
        ]

        costume_patterns = [
            r"(?:wearing|dressed in|changes into|puts on)\s+(.+?)(?:\.|,|$)",
            r"(?:COSTUME|WARDROBE):\s*(.+?)(?:\.|$)",
            r"\b(?:uniform|costume|outfit|clothes?)\s+(?:of\s+)?(.+?)(?:\.|,|$)",
        ]

        for element in elements:
            if isinstance(element, dict):
                text = element.get("text", "")
                if not text:
                    continue

                # Extract sound requirements
                for pattern in sound_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        sound = match.group(1).strip()
                        if sound:
                            requirements["sound"].add(sound)

                # Extract VFX requirements
                for pattern in vfx_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        vfx = match.group(1).strip()
                        if vfx:
                            requirements["vfx"].add(vfx)

                # Extract costume requirements
                for pattern in costume_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        costume = match.group(1).strip()
                        if costume and len(costume) < 100:  # Avoid overly long matches
                            requirements["costume"].add(costume)

        return requirements

    def _analyze_location_continuity(
        self, scenes: list[GraphNode], dependencies: dict[str, list[str]]
    ) -> None:
        """Analyze location continuity between scenes.

        Tracks when locations are established and creates dependencies
        for scenes that return to previously established locations.

        Args:
            scenes: List of scene nodes
            dependencies: Dictionary to update with location dependencies
        """
        # Track location appearances
        location_scenes: dict[str, list[str]] = {}

        for scene in scenes:
            scene_id = scene.id
            location = scene.properties.get("heading", "")

            if location:
                # Normalize location for comparison
                location_key = self._normalize_location(location)
                if location_key not in location_scenes:
                    location_scenes[location_key] = []
                location_scenes[location_key].append(scene_id)

        # Establish dependencies for returning to locations
        for _location, scene_list in location_scenes.items():
            if len(scene_list) > 1:
                # First scene at location establishes it
                first_scene = scene_list[0]
                for later_scene in scene_list[1:]:
                    # Only add dependency if scenes are not consecutive
                    # (consecutive scenes at same location don't need dependency)
                    first_idx = next(
                        i for i, s in enumerate(scenes) if s.id == first_scene
                    )
                    later_idx = next(
                        i for i, s in enumerate(scenes) if s.id == later_scene
                    )
                    if (
                        later_idx - first_idx > 1
                        and first_scene not in dependencies[later_scene]
                    ):
                        dependencies[later_scene].append(first_scene)

    def _normalize_location(self, location: str) -> str:
        """Normalize location string for comparison.

        Args:
            location: Location string from scene heading

        Returns:
            Normalized location key
        """
        # Remove time of day and standardize format
        location = location.upper().strip()
        # Remove common time indicators
        time_indicators = [
            "- DAY",
            "- NIGHT",
            "- MORNING",
            "- EVENING",
            "- CONTINUOUS",
            "- LATER",
        ]
        for time_indicator in time_indicators:
            location = location.replace(time_indicator, "")
        return location.strip()

    def _analyze_dialogue_references(
        self, scenes: list[GraphNode], dependencies: dict[str, list[str]]
    ) -> None:
        """Analyze dialogue references between scenes.

        Identifies when dialogue references events, information, or objects
        from previous scenes.

        Args:
            scenes: List of scene nodes
            dependencies: Dictionary to update with dialogue dependencies
        """
        # Track key information revealed in dialogue (unused for now)
        _revealed_info: dict[str, tuple[str, str]] = {}

        # Common patterns for referencing previous events
        reference_patterns = [
            r"\b(?:remember when|recall|as I (?:said|mentioned|told you))\b",
            r"\b(?:like|just like|same as) (?:before|last time|yesterday|earlier)\b",
            r"\b(?:you (?:said|mentioned|told me)|we (?:discussed|talked about))\b",
            r"\b(?:the|that) (?:thing|incident|event|time) (?:when|where|that)\b",
        ]

        for i, scene in enumerate(scenes):
            scene_id = scene.id
            elements = scene.properties.get("elements", [])

            for element in elements:
                if isinstance(element, dict):
                    element_type = element.get("type", "")
                    text = element.get("text", "")

                    if element_type == "dialogue" and text:
                        # Check for references to previous scenes
                        for pattern in reference_patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                # Look for the referenced scene (simplified heuristic)
                                # In a more sophisticated implementation, we'd use NLP
                                # For now, create dependency on previous scenes with
                                # same character
                                character = element.get("character", "")
                                if character:
                                    for j in range(i):
                                        prev_scene = scenes[j]
                                        prev_chars = self._get_scene_characters(
                                            prev_scene
                                        )
                                        if (
                                            character in prev_chars
                                            and prev_scene.id
                                            not in dependencies[scene_id]
                                        ):
                                            dependencies[scene_id].append(prev_scene.id)
                                            break

    def _get_scene_characters(self, scene_node: GraphNode) -> set[str]:
        """Get character names appearing in a scene.

        Args:
            scene_node: Scene node to analyze

        Returns:
            Set of character names
        """
        characters = set()
        elements = scene_node.properties.get("elements", [])

        for element in elements:
            if isinstance(element, dict) and element.get("type") == "dialogue":
                character = element.get("character", "")
                if character:
                    characters.add(character)

        return characters

    def get_scene_dependencies_detailed(self, scene_node_id: str) -> dict[str, Any]:
        """Get detailed dependency information for a scene.

        Args:
            scene_node_id: Scene node ID

        Returns:
            Dictionary with detailed dependency information including:
            - character_deps: Character introduction dependencies
            - prop_deps: Prop introduction dependencies
            - tech_deps: Technical requirement dependencies
            - location_deps: Location continuity dependencies
            - dialogue_deps: Dialogue reference dependencies
        """
        # Get the script this scene belongs to
        script_edges = self.graph.find_edges(
            to_node_id=scene_node_id, edge_type="HAS_SCENE"
        )
        if not script_edges:
            return {}

        script_node_id = script_edges[0].from_node_id

        # Get all dependencies for the script
        all_deps = self.analyze_scene_dependencies(script_node_id)
        scene_deps = all_deps.get(scene_node_id, [])

        # Get detailed information about each dependency
        detailed_deps: dict[str, Any] = {
            "character_deps": [],
            "prop_deps": [],
            "tech_deps": [],
            "location_deps": [],
            "dialogue_deps": [],
            "props_in_scene": [],
            "tech_requirements": {},
        }

        # For now, return the basic dependencies
        # In a full implementation, we'd categorize each dependency
        for dep_scene_id in scene_deps:
            dep_node = self.graph.get_node(dep_scene_id)
            if dep_node:
                # Simplified categorization - in practice, we'd track the reason
                detailed_deps["character_deps"].append(
                    {
                        "scene_id": dep_scene_id,
                        "heading": dep_node.properties.get("heading", ""),
                        "reason": "Character or element introduction",
                    }
                )

        # Also extract current scene requirements
        scene_node = self.graph.get_node(scene_node_id)
        if scene_node:
            props = self._extract_props_from_scene(scene_node)
            tech_reqs = self._extract_technical_requirements(scene_node)

            detailed_deps["props_in_scene"] = list(props)
            detailed_deps["tech_requirements"] = {
                k: list(v) for k, v in tech_reqs.items() if v
            }

        return detailed_deps

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
