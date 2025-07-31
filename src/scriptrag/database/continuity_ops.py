"""Continuity and validation operations for screenplay analysis.

This module handles story continuity validation, dependency analysis,
and temporal ordering checks.
"""

from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import SceneDependency

from .connection import DatabaseConnection
from .graph import GraphDatabase
from .scene_ordering import SceneOrderingOperations

# Constants
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


class ContinuityOperations:
    """Operations for managing story continuity and validation."""

    def __init__(self, connection: DatabaseConnection, graph: GraphDatabase) -> None:
        """Initialize continuity operations.

        Args:
            connection: Database connection instance
            graph: Graph database instance
        """
        self.connection = connection
        self.graph = graph
        self.scene_ordering = SceneOrderingOperations(connection)

    def infer_temporal_order(self, _script_id: str) -> dict[str, int]:
        """Infer temporal order of scenes based on time of day.

        Args:
            script_id: Script ID

        Returns:
            Dictionary mapping scene IDs to temporal positions
        """
        # Implementation would analyze time_of_day properties
        # and create a temporal ordering
        return {}

    def analyze_scene_dependencies(self, _script_id: str) -> list[SceneDependency]:
        """Analyze dependencies between scenes.

        Args:
            script_id: Script ID

        Returns:
            List of scene dependencies
        """
        # Implementation would analyze character/prop/information flow
        # to determine scene dependencies
        return []

    def calculate_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order of scenes based on dependencies.

        Args:
            script_id: Script ID

        Returns:
            List of scene IDs in logical order
        """
        return self.scene_ordering.get_logical_order(script_id)

    def validate_scene_ordering(self, _script_id: str) -> dict[str, Any]:
        """Validate the current scene ordering for consistency.

        Args:
            script_id: Script ID

        Returns:
            Validation results with any issues found
        """
        # Implementation would check:
        # - Temporal consistency
        # - Dependency violations
        # - Character continuity
        # - Location flow

        return {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "conflicts": [],
            "suggestions": [],
        }

    def validate_story_continuity(self, script_node_id: str) -> dict[str, Any]:
        """Validate story continuity across all scenes.

        Args:
            script_node_id: Script node ID

        Returns:
            Validation results with detailed continuity analysis
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "character_continuity": {},
            "location_continuity": {},
            "temporal_continuity": [],
        }

        try:
            # Get all scenes in order
            scenes = self.graph.get_neighbors(
                script_node_id, direction="outgoing", edge_type="contains_scene"
            )

            if not scenes:
                if isinstance(results["warnings"], list):
                    results["warnings"].append(
                        {"type": "no_scenes", "message": "No scenes found in script"}
                    )
                return results

            # Sort scenes by order
            scenes = sorted(
                scenes, key=lambda s: s.properties.get("script_order", float("inf"))
            )

            # Check character continuity
            character_last_seen: dict[str, int] = {}
            character_appearances: dict[str, list[dict[str, Any]]] = {}

            for scene_idx, scene in enumerate(scenes):
                # Get characters in this scene
                char_edges = self.graph.find_edges(
                    to_node_id=scene.id, edge_type="appears_in"
                )

                for edge in char_edges:
                    char_node = self.graph.get_node(edge.from_node_id)
                    if char_node and char_node.label:
                        char_name = char_node.label

                        if char_name not in character_appearances:
                            character_appearances[char_name] = []

                        character_appearances[char_name].append(
                            {
                                "scene_idx": scene_idx,
                                "scene_id": scene.id,
                                "script_order": scene.properties.get("script_order"),
                            }
                        )

                        # Check for long gaps in appearances
                        if char_name in character_last_seen:
                            gap = scene_idx - character_last_seen[char_name]
                            if (
                                gap > 10  # More than 10 scenes gap
                                and isinstance(results["warnings"], list)
                            ):
                                results["warnings"].append(
                                    {
                                        "type": "character_gap",
                                        "message": (
                                            f"{char_name} disappears for {gap} scenes"
                                        ),
                                        "last_scene": scenes[
                                            character_last_seen[char_name]
                                        ].id,
                                        "current_scene": scene.id,
                                    }
                                )

                        character_last_seen[char_name] = scene_idx

            results["character_continuity"] = character_appearances

            # Check location continuity
            location_usage = {}

            for scene in scenes:
                # Get scene location
                loc_edges = self.graph.find_edges(
                    from_node_id=scene.id, edge_type="takes_place_in"
                )

                if loc_edges:
                    loc_node = self.graph.get_node(loc_edges[0].to_node_id)
                    if loc_node:
                        loc_name = loc_node.label
                        if loc_name not in location_usage:
                            location_usage[loc_name] = 0
                        location_usage[loc_name] += 1

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
                        "message": (
                            f"Found {len(temporal_issues)} potential "
                            "temporal regressions"
                        ),
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
        """Check if there's a temporal regression between times.

        Args:
            current_time: Current scene time
            next_time: Next scene time

        Returns:
            True if there's a regression
        """
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

    def check_character_arcs(self, script_node_id: str) -> dict[str, Any]:
        """Analyze character arcs for consistency.

        Args:
            script_node_id: Script node ID

        Returns:
            Character arc analysis
        """
        arcs: dict[str, dict[str, Any]] = {}

        # Get all characters
        characters = self.graph.get_neighbors(
            script_node_id, direction="outgoing", edge_type="has_character"
        )

        for char in characters:
            # Get all scenes where character appears
            scenes = self.graph.get_neighbors(
                char.id, direction="outgoing", edge_type="appears_in"
            )

            # Sort by scene order
            sorted_scenes = sorted(
                scenes, key=lambda s: s.properties.get("script_order", float("inf"))
            )

            if sorted_scenes and char.label:
                arcs[char.label] = {
                    "first_appearance": sorted_scenes[0].properties.get("script_order"),
                    "last_appearance": sorted_scenes[-1].properties.get("script_order"),
                    "total_scenes": len(sorted_scenes),
                    "scene_orders": [
                        s.properties.get("script_order") for s in sorted_scenes
                    ],
                }

        return arcs

    def check_prop_continuity(self, _script_node_id: str) -> dict[str, Any]:
        """Check continuity of props and important objects.

        Args:
            script_node_id: Script node ID

        Returns:
            Prop continuity analysis
        """
        # This would analyze prop usage across scenes
        # Currently a placeholder for future implementation
        return {
            "props": {},
            "continuity_issues": [],
        }

    def validate_information_flow(self, _script_node_id: str) -> dict[str, Any]:
        """Validate that information flows logically through the script.

        Args:
            script_node_id: Script node ID

        Returns:
            Information flow analysis
        """
        # This would check that characters only know information
        # they've been exposed to in previous scenes
        return {
            "information_dependencies": [],
            "violations": [],
        }

    def suggest_scene_reordering(self, script_node_id: str) -> list[dict[str, Any]]:
        """Suggest potential scene reorderings to improve flow.

        Args:
            script_node_id: Script node ID

        Returns:
            List of reordering suggestions
        """
        suggestions: list[dict[str, Any]] = []

        # Analyze current ordering issues
        validation = self.validate_scene_ordering(script_node_id)

        # Generate suggestions based on issues found
        if (
            isinstance(validation.get("errors"), list)
            and len(validation.get("errors", [])) > 0
        ) or (
            isinstance(validation.get("warnings"), list)
            and len(validation.get("warnings", [])) > 0
        ):
            # Analyze and suggest fixes
            pass

        return suggestions

    def get_continuity_report(self, script_node_id: str) -> dict[str, Any]:
        """Generate comprehensive continuity report.

        Args:
            script_node_id: Script node ID

        Returns:
            Full continuity analysis report
        """
        report: dict[str, Any] = {
            "story_continuity": self.validate_story_continuity(script_node_id),
            "character_arcs": self.check_character_arcs(script_node_id),
            "prop_continuity": self.check_prop_continuity(script_node_id),
            "information_flow": self.validate_information_flow(script_node_id),
            "suggestions": self.suggest_scene_reordering(script_node_id),
        }

        # Calculate overall score
        story_continuity = report["story_continuity"]
        errors = (
            story_continuity.get("errors", [])
            if isinstance(story_continuity.get("errors"), list)
            else []
        )
        warnings = (
            story_continuity.get("warnings", [])
            if isinstance(story_continuity.get("warnings"), list)
            else []
        )
        issues_count = len(errors) + len(warnings)

        report["overall_score"] = max(0, 100 - (issues_count * 5))
        report["summary"] = {
            "total_issues": issues_count,
            "critical_errors": len(errors),
            "warnings": len(warnings),
        }

        return report
