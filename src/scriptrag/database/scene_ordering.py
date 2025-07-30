"""Scene ordering functionality for managing script, temporal, and logical order.

This module provides operations for:
- Tracking and maintaining original script order
- Inferring temporal (chronological) order from scene content
- Analyzing and creating logical dependencies between scenes
- Reordering scenes while maintaining consistency
"""

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from scriptrag.config import get_logger
from scriptrag.models import (
    SceneDependency,
    SceneDependencyType,
    SceneOrderType,
)

from .connection import DatabaseConnection

logger = get_logger(__name__)


class SceneOrderingOperations:
    """Handles scene ordering and dependency management."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize scene ordering operations.

        Args:
            connection: Database connection instance
        """
        self.connection = connection

    # Script order tracking
    def ensure_script_order(self, script_id: str) -> bool:
        """Ensure all scenes have proper script_order values.

        Args:
            script_id: Script ID to check

        Returns:
            True if successful
        """
        try:
            with self.connection.transaction() as conn:
                # Get all scenes without proper ordering
                cursor = conn.execute(
                    """
                    SELECT id, heading, script_order
                    FROM scenes
                    WHERE script_id = ?
                    ORDER BY created_at, id
                    """,
                    (script_id,),
                )
                scenes = cursor.fetchall()

                # Check if reordering is needed
                needs_reorder = False
                for i, (_scene_id, _heading, current_order) in enumerate(scenes):
                    if current_order != i + 1:
                        needs_reorder = True
                        break

                if needs_reorder:
                    # Update script order based on creation order
                    for i, (scene_id, _, _) in enumerate(scenes):
                        conn.execute(
                            "UPDATE scenes SET script_order = ? WHERE id = ?",
                            (i + 1, scene_id),
                        )
                    logger.info(f"Updated script order for {len(scenes)} scenes")

            return True
        except Exception as e:
            logger.error(f"Failed to ensure script order: {e}")
            return False

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
        try:
            with self.connection.transaction() as conn:
                # Verify all scenes belong to the script
                placeholders = ",".join("?" * len(scene_order))
                cursor = conn.execute(
                    f"""
                    SELECT COUNT(*) FROM scenes
                    WHERE script_id = ? AND id IN ({placeholders})
                    """,
                    [script_id, *scene_order],
                )
                count = cursor.fetchone()[0]

                if count != len(scene_order):
                    logger.error("Some scenes do not belong to the specified script")
                    return False

                # Update the appropriate order field
                field_name = f"{order_type.value}_order"
                for i, scene_id in enumerate(scene_order):
                    conn.execute(
                        f"UPDATE scenes SET {field_name} = ? WHERE id = ?",
                        (i + 1, scene_id),
                    )

                logger.info(
                    f"Updated {order_type.value} order for {len(scene_order)} scenes"
                )

            return True
        except Exception as e:
            logger.error(f"Failed to reorder scenes: {e}")
            return False

    # Temporal order inference
    def infer_temporal_order(self, script_id: str) -> dict[str, int]:
        """Infer temporal (chronological) order of scenes.

        Analyzes scene content for temporal markers like:
        - Time references (morning, evening, later, etc.)
        - Date indicators
        - Flashback/flashforward markers
        - Character age references

        Args:
            script_id: Script ID to analyze

        Returns:
            Dictionary mapping scene_id to temporal_order
        """
        try:
            # Get all scenes with their content
            with self.connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT s.id, s.heading, s.time_of_day, s.date_in_story,
                           s.script_order, se.text
                    FROM scenes s
                    LEFT JOIN scene_elements se ON s.id = se.scene_id
                    WHERE s.script_id = ?
                    ORDER BY s.script_order, se.order_in_scene
                    """,
                    (script_id,),
                )

                # Group content by scene
                scene_data: dict[str, dict[str, Any]] = {}
                for row in cursor.fetchall():
                    scene_id = row[0]
                    if scene_id not in scene_data:
                        scene_data[scene_id] = {
                            "heading": row[1],
                            "time_of_day": row[2],
                            "date_in_story": row[3],
                            "script_order": row[4],
                            "content": [],
                        }
                    if row[5]:  # scene element text
                        scene_data[scene_id]["content"].append(row[5])

            # Analyze temporal markers
            temporal_scores = {}
            flashback_scenes = set()
            flashforward_scenes = set()

            for scene_id, data in scene_data.items():
                content = " ".join(str(c) for c in data["content"] if c).lower()
                heading = (data["heading"] or "").lower()

                # Check for flashback/flashforward markers
                if any(
                    marker in content or marker in heading
                    for marker in ["flashback", "years earlier", "years ago", "past"]
                ):
                    flashback_scenes.add(scene_id)
                elif any(
                    marker in content or marker in heading
                    for marker in ["flashforward", "years later", "future"]
                ):
                    flashforward_scenes.add(scene_id)

                # Calculate base temporal score (default to script order)
                base_score = data["script_order"] * 100

                # Adjust for explicit temporal markers
                if scene_id in flashback_scenes:
                    base_score -= 10000  # Move to beginning
                elif scene_id in flashforward_scenes:
                    base_score += 10000  # Move to end

                # Fine-tune based on time of day progression
                time_adjustments = {
                    "dawn": -3,
                    "morning": -2,
                    "day": -1,
                    "afternoon": 0,
                    "dusk": 1,
                    "evening": 2,
                    "night": 3,
                }

                time_of_day = (data.get("time_of_day") or "").lower()
                for time_key, adjustment in time_adjustments.items():
                    if time_key in time_of_day:
                        base_score += adjustment
                        break

                temporal_scores[scene_id] = base_score

            # Sort scenes by temporal score and assign order
            sorted_scenes = sorted(temporal_scores.items(), key=lambda x: x[1])
            temporal_order = {
                scene_id: order + 1 for order, (scene_id, _) in enumerate(sorted_scenes)
            }

            # Update database with inferred temporal order
            with self.connection.transaction() as conn:
                for scene_id, order in temporal_order.items():
                    conn.execute(
                        "UPDATE scenes SET temporal_order = ? WHERE id = ?",
                        (order, scene_id),
                    )

            logger.info(f"Inferred temporal order for {len(temporal_order)} scenes")
            return temporal_order

        except Exception as e:
            logger.error(f"Failed to infer temporal order: {e}")
            return {}

    # Logical dependency analysis
    def analyze_logical_dependencies(self, script_id: str) -> list[SceneDependency]:
        """Analyze and create logical dependencies between scenes.

        Identifies dependencies based on:
        - Character introductions and appearances
        - Plot elements that require prior setup
        - Location establishment
        - Object/prop continuity
        - Dialogue references to past events

        Args:
            script_id: Script ID to analyze

        Returns:
            List of SceneDependency objects created
        """
        dependencies = []

        try:
            # Get all scenes with their elements
            with self.connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT s.id, s.heading, s.script_order,
                           se.element_type, se.text, se.character_name,
                           c.name as character_name_normalized
                    FROM scenes s
                    LEFT JOIN scene_elements se ON s.id = se.scene_id
                    LEFT JOIN characters c ON se.character_id = c.id
                    WHERE s.script_id = ?
                    ORDER BY s.script_order, se.order_in_scene
                    """,
                    (script_id,),
                )

                # Build scene information
                scenes_info: dict[str, dict[str, Any]] = {}
                for row in cursor.fetchall():
                    scene_id = row[0]
                    if scene_id not in scenes_info:
                        scenes_info[scene_id] = {
                            "heading": row[1],
                            "script_order": row[2],
                            "characters": set(),
                            "dialogue": [],
                            "action": [],
                            "all_text": [],
                        }

                    if row[3] == "dialogue" and row[6]:
                        scenes_info[scene_id]["characters"].add(row[6])
                        if row[4]:
                            scenes_info[scene_id]["dialogue"].append(row[4])
                    elif row[3] == "action" and row[4]:
                        scenes_info[scene_id]["action"].append(row[4])

                    if row[4]:
                        scenes_info[scene_id]["all_text"].append(row[4])

            # Sort scenes by script order for analysis
            sorted_scenes = sorted(
                scenes_info.items(), key=lambda x: x[1]["script_order"]
            )

            # Track character introductions
            character_introduced_in: dict[str, str] = {}

            # Analyze dependencies
            for i, (scene_id, scene_data) in enumerate(sorted_scenes):
                # Character introduction dependencies
                for character in scene_data["characters"]:
                    if character not in character_introduced_in:
                        character_introduced_in[character] = scene_id
                    elif character_introduced_in[character] != scene_id:
                        # This scene requires the character introduction scene
                        dep = self._create_dependency(
                            from_scene_id=scene_id,
                            to_scene_id=character_introduced_in[character],
                            dependency_type=SceneDependencyType.REQUIRES,
                            description=(
                                f"Character {character} must be introduced first"
                            ),
                            strength=0.8,
                        )
                        if dep:
                            dependencies.append(dep)

                # Analyze dialogue for references to previous scenes
                all_text = " ".join(str(t) for t in scene_data["all_text"] if t).lower()

                # Look for explicit references
                for _j, (other_scene_id, other_data) in enumerate(sorted_scenes[:i]):
                    if self._scenes_are_related(scene_data, other_data, all_text):
                        dep = self._create_dependency(
                            from_scene_id=scene_id,
                            to_scene_id=other_scene_id,
                            dependency_type=SceneDependencyType.REFERENCES,
                            description="Scene contains references to earlier events",
                            strength=0.6,
                        )
                        if dep:
                            dependencies.append(dep)

                # Check for direct continuations
                if i > 0:
                    prev_scene_id, prev_data = sorted_scenes[i - 1]
                    if self._is_continuation(scene_data, prev_data):
                        dep = self._create_dependency(
                            from_scene_id=scene_id,
                            to_scene_id=prev_scene_id,
                            dependency_type=SceneDependencyType.CONTINUES,
                            description="Scene directly continues from previous",
                            strength=0.9,
                        )
                        if dep:
                            dependencies.append(dep)

            # Store dependencies in database
            self._store_dependencies(dependencies)

            logger.info(f"Analyzed and created {len(dependencies)} scene dependencies")
            return dependencies

        except Exception as e:
            logger.error(f"Failed to analyze logical dependencies: {e}")
            return []

    def _scenes_are_related(
        self,
        scene_data: dict[str, Any],
        other_data: dict[str, Any],
        scene_text: str,
    ) -> bool:
        """Check if two scenes are related through references."""
        # Check for shared characters
        shared_chars = scene_data["characters"].intersection(other_data["characters"])
        if not shared_chars:
            return False

        # Look for temporal references
        temporal_refs = [
            "earlier",
            "before",
            "previously",
            "last time",
            "remember when",
            "like when",
            "that time",
        ]

        return any(ref in scene_text for ref in temporal_refs)

    def _is_continuation(
        self,
        scene_data: dict[str, Any],
        prev_data: dict[str, Any],
    ) -> bool:
        """Check if a scene directly continues from the previous one."""
        # Check for continuous action markers
        scene_heading = (scene_data.get("heading") or "").upper()
        prev_heading = (prev_data.get("heading") or "").upper()

        # Common continuation patterns
        if "CONTINUOUS" in scene_heading:
            return True

        if "MOMENTS LATER" in scene_heading:
            return True

        # Same location suggests continuation
        scene_location = self._extract_location(scene_heading)
        prev_location = self._extract_location(prev_heading)

        if scene_location and scene_location == prev_location:
            # Check for shared characters
            shared_chars = scene_data["characters"].intersection(
                prev_data["characters"]
            )
            return len(shared_chars) > 0

        return False

    def _extract_location(self, heading: str) -> str | None:
        """Extract location from scene heading."""
        # Remove INT./EXT. and time of day
        heading = re.sub(r"^(INT\.|EXT\.|INT/EXT\.)\s*", "", heading)
        heading = re.sub(
            r"\s*-\s*(DAY|NIGHT|MORNING|EVENING|CONTINUOUS).*$", "", heading
        )
        return heading.strip() if heading else None

    def _create_dependency(
        self,
        from_scene_id: str,
        to_scene_id: str,
        dependency_type: SceneDependencyType,
        description: str,
        strength: float,
    ) -> SceneDependency | None:
        """Create a scene dependency object."""
        try:
            return SceneDependency(
                id=uuid4(),
                from_scene_id=UUID(from_scene_id),
                to_scene_id=UUID(to_scene_id),
                dependency_type=dependency_type,
                description=description,
                strength=strength,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        except Exception as e:
            logger.error(f"Failed to create dependency: {e}")
            return None

    def _store_dependencies(self, dependencies: list[SceneDependency]) -> int:
        """Store dependencies in the database."""
        stored_count = 0

        with self.connection.transaction() as conn:
            for dep in dependencies:
                try:
                    # Check if dependency already exists
                    cursor = conn.execute(
                        """
                        SELECT id FROM scene_dependencies
                        WHERE from_scene_id = ? AND to_scene_id = ?
                        AND dependency_type = ?
                        """,
                        (
                            str(dep.from_scene_id),
                            str(dep.to_scene_id),
                            dep.dependency_type.value,
                        ),
                    )

                    if cursor.fetchone():
                        continue  # Skip existing dependency

                    # Insert new dependency
                    metadata = json.dumps(dep.metadata) if dep.metadata else None

                    conn.execute(
                        """
                        INSERT INTO scene_dependencies
                        (id, from_scene_id, to_scene_id, dependency_type,
                         description, strength, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(dep.id),
                            str(dep.from_scene_id),
                            str(dep.to_scene_id),
                            dep.dependency_type.value,
                            dep.description,
                            dep.strength,
                            metadata,
                        ),
                    )
                    stored_count += 1

                except Exception as e:
                    logger.error(f"Failed to store dependency: {e}")
                    continue

        return stored_count

    # Dependency queries
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
        dependencies = []

        try:
            with self.connection.get_connection() as conn:
                if direction in ["from", "both"]:
                    cursor = conn.execute(
                        """
                        SELECT sd.*, s.heading as to_scene_heading
                        FROM scene_dependencies sd
                        JOIN scenes s ON sd.to_scene_id = s.id
                        WHERE sd.from_scene_id = ?
                        """,
                        (scene_id,),
                    )

                    for row in cursor.fetchall():
                        dependencies.append(
                            {
                                "id": row[0],
                                "from_scene_id": row[1],
                                "to_scene_id": row[2],
                                "dependency_type": row[3],
                                "description": row[4],
                                "strength": row[5],
                                "to_scene_heading": row[-1],
                                "direction": "outgoing",
                            }
                        )

                if direction in ["to", "both"]:
                    cursor = conn.execute(
                        """
                        SELECT sd.*, s.heading as from_scene_heading
                        FROM scene_dependencies sd
                        JOIN scenes s ON sd.from_scene_id = s.id
                        WHERE sd.to_scene_id = ?
                        """,
                        (scene_id,),
                    )

                    for row in cursor.fetchall():
                        dependencies.append(
                            {
                                "id": row[0],
                                "from_scene_id": row[1],
                                "to_scene_id": row[2],
                                "dependency_type": row[3],
                                "description": row[4],
                                "strength": row[5],
                                "from_scene_heading": row[-1],
                                "direction": "incoming",
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to get scene dependencies: {e}")

        return dependencies

    def get_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order based on dependencies.

        Uses topological sorting to determine an order that respects
        all dependencies.

        Args:
            script_id: Script ID

        Returns:
            List of scene IDs in logical order
        """
        try:
            # Get all scenes and their dependencies
            with self.connection.get_connection() as conn:
                # Get all scenes
                cursor = conn.execute(
                    "SELECT id FROM scenes WHERE script_id = ? ORDER BY script_order",
                    (script_id,),
                )
                all_scenes = [row[0] for row in cursor.fetchall()]

                # Get all dependencies
                cursor = conn.execute(
                    """
                    SELECT sd.from_scene_id, sd.to_scene_id, sd.strength
                    FROM scene_dependencies sd
                    JOIN scenes s1 ON sd.from_scene_id = s1.id
                    JOIN scenes s2 ON sd.to_scene_id = s2.id
                    WHERE s1.script_id = ? AND s2.script_id = ?
                    AND sd.strength >= 0.7  -- Only strong dependencies
                    """,
                    (script_id, script_id),
                )

                # Build adjacency list
                dependencies: dict[str, set[str]] = {
                    scene: set() for scene in all_scenes
                }
                in_degree: dict[str, int] = dict.fromkeys(all_scenes, 0)

                for from_scene, to_scene, _strength in cursor.fetchall():
                    # from_scene depends on to_scene, so to_scene must come
                    # before from_scene. In the adjacency list, we add:
                    # to_scene -> from_scene
                    if from_scene not in dependencies[to_scene]:
                        dependencies[to_scene].add(from_scene)
                        in_degree[from_scene] += 1

            # Topological sort using Kahn's algorithm
            queue = [scene for scene in all_scenes if in_degree[scene] == 0]
            logical_order = []

            while queue:
                # Sort queue by script order for deterministic results
                queue.sort(key=lambda x: all_scenes.index(x))
                current = queue.pop(0)
                logical_order.append(current)

                # Update in-degrees
                for dependent in dependencies[current]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            # Check for cycles
            if len(logical_order) != len(all_scenes):
                logger.warning(
                    "Dependency cycle detected, falling back to script order"
                )
                return all_scenes

            # Update database with logical order
            with self.connection.transaction() as conn:
                for i, scene_id in enumerate(logical_order):
                    conn.execute(
                        "UPDATE scenes SET logical_order = ? WHERE id = ?",
                        (i + 1, scene_id),
                    )

            return logical_order

        except Exception as e:
            logger.error(f"Failed to calculate logical order: {e}")
            return []

    def validate_ordering_consistency(self, script_id: str) -> dict[str, Any]:
        """Validate consistency across different ordering systems.

        Args:
            script_id: Script ID to validate

        Returns:
            Dictionary with validation results and any conflicts found
        """
        results: dict[str, Any] = {
            "is_valid": True,
            "conflicts": [],
            "warnings": [],
        }

        try:
            with self.connection.get_connection() as conn:
                # Get all scene orderings
                cursor = conn.execute(
                    """
                    SELECT id, heading, script_order, temporal_order, logical_order
                    FROM scenes
                    WHERE script_id = ?
                    """,
                    (script_id,),
                )

                scenes = []
                for row in cursor.fetchall():
                    scenes.append(
                        {
                            "id": row[0],
                            "heading": row[1],
                            "script_order": row[2],
                            "temporal_order": row[3],
                            "logical_order": row[4],
                        }
                    )

                # Check for missing orders
                for scene in scenes:
                    if not scene["script_order"]:
                        results["is_valid"] = False
                        results["conflicts"].append(
                            {
                                "type": "missing_order",
                                "scene_id": scene["id"],
                                "message": "Scene missing script order",
                            }
                        )

                # Check for duplicate orders
                for order_type in ["script_order", "temporal_order", "logical_order"]:
                    order_values = [s[order_type] for s in scenes if s[order_type]]
                    if len(order_values) != len(set(order_values)):
                        results["warnings"].append(
                            {
                                "type": "duplicate_order",
                                "order_type": order_type,
                                "message": f"Duplicate {order_type} values found",
                            }
                        )

                # Check logical consistency with dependencies
                cursor = conn.execute(
                    """
                    SELECT sd.from_scene_id, sd.to_scene_id,
                           s1.logical_order as from_order,
                           s2.logical_order as to_order
                    FROM scene_dependencies sd
                    JOIN scenes s1 ON sd.from_scene_id = s1.id
                    JOIN scenes s2 ON sd.to_scene_id = s2.id
                    WHERE s1.script_id = ? AND sd.strength >= 0.7
                    """,
                    (script_id,),
                )

                for from_id, to_id, from_order, to_order in cursor.fetchall():
                    if from_order and to_order and from_order <= to_order:
                        results["conflicts"].append(
                            {
                                "type": "dependency_violation",
                                "from_scene_id": from_id,
                                "to_scene_id": to_id,
                                "message": "Logical order violates dependency",
                            }
                        )
                        results["is_valid"] = False

        except Exception as e:
            logger.error(f"Failed to validate ordering: {e}")
            results["is_valid"] = False
            results["conflicts"].append(
                {
                    "type": "error",
                    "message": str(e),
                }
            )

        return results
