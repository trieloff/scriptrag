"""Analysis-related MCP tools."""

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.continuity import ContinuityValidator


class AnalysisTools:
    """Tools for script analysis."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize analysis tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def analyze_timeline(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze script timeline."""
        script_id = args.get("script_id")
        analysis_type = args.get("analysis_type", "chronological")

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Analyze timeline based on type
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            if analysis_type == "chronological":
                # Get scenes in chronological order
                timeline_query = """
                    SELECT
                        s.id,
                        s.heading,
                        s.script_order,
                        s.temporal_order,
                        s.time_of_day,
                        n.properties_json
                    FROM scenes s
                    JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                    WHERE s.script_id = ?
                    ORDER BY COALESCE(s.temporal_order, s.script_order)
                """
                cursor = connection.execute(timeline_query, (str(script.id),))

                timeline = []
                current_day = 0
                last_time = None

                for row in cursor.fetchall():
                    # Parse properties for temporal info
                    properties = {}
                    if row["properties_json"]:
                        from contextlib import suppress

                        with suppress(json.JSONDecodeError):
                            properties = json.loads(row["properties_json"])

                    # Determine if this is a new day
                    time_of_day = row["time_of_day"] or "DAY"
                    if last_time and _is_earlier_time(time_of_day, last_time):
                        current_day += 1
                    last_time = time_of_day

                    timeline.append(
                        {
                            "scene_id": row["id"],
                            "heading": row["heading"],
                            "script_order": row["script_order"],
                            "temporal_order": row["temporal_order"],
                            "time_of_day": time_of_day,
                            "estimated_day": current_day,
                            "temporal_notes": properties.get("temporal_notes"),
                        }
                    )

                # Calculate timeline statistics
                total_days = current_day + 1
                scenes_per_day: dict[int, int] = defaultdict(int)
                for scene in timeline:
                    scenes_per_day[scene["estimated_day"]] += 1

                return {
                    "script_id": script_id,
                    "analysis_type": analysis_type,
                    "timeline": timeline,
                    "statistics": {
                        "total_scenes": len(timeline),
                        "estimated_days": total_days,
                        "scenes_per_day": dict(scenes_per_day),
                        "average_scenes_per_day": len(timeline) / total_days
                        if total_days > 0
                        else 0,
                    },
                }

            if analysis_type == "character_journey":
                # Analyze character appearances over time
                character_name = args.get("character_name")
                if not character_name:
                    # Get all characters
                    char_query = """
                        SELECT DISTINCT c.name
                        FROM characters c
                        WHERE c.script_id = ?
                        ORDER BY c.name
                    """
                    char_cursor = connection.execute(char_query, (str(script.id),))
                    characters = [row["name"] for row in char_cursor.fetchall()]
                else:
                    characters = [character_name]

                journeys = {}
                for char_name in characters:
                    # Get character's scene appearances in order
                    journey_query = """
                        SELECT
                            s.id,
                            s.heading,
                            s.script_order,
                            s.temporal_order,
                            s.time_of_day
                        FROM scenes s
                        JOIN nodes sn ON sn.entity_id = s.id AND sn.node_type = 'scene'
                        JOIN edges e ON (
                            e.to_node_id = sn.id AND e.edge_type = 'APPEARS_IN'
                        )
                        JOIN nodes cn ON (
                            cn.id = e.from_node_id AND cn.node_type = 'character'
                        )
                        JOIN characters c ON c.id = cn.entity_id
                        WHERE s.script_id = ? AND UPPER(c.name) LIKE UPPER(?)
                        ORDER BY s.script_order
                    """
                    journey_cursor = connection.execute(
                        journey_query, (str(script.id), f"%{char_name}%")
                    )

                    appearances = []
                    for row in journey_cursor.fetchall():
                        appearances.append(
                            {
                                "scene_id": row["id"],
                                "heading": row["heading"],
                                "script_order": row["script_order"],
                                "temporal_order": row["temporal_order"],
                                "time_of_day": row["time_of_day"],
                            }
                        )

                    if appearances:
                        journeys[char_name] = {
                            "appearances": appearances,
                            "total_scenes": len(appearances),
                            "first_appearance": appearances[0],
                            "last_appearance": appearances[-1],
                            "absence_gaps": _find_absence_gaps(appearances),
                        }

                return {
                    "script_id": script_id,
                    "analysis_type": analysis_type,
                    "character_journeys": journeys,
                }

            if analysis_type == "location_flow":
                # Analyze movement between locations
                location_query = """
                    SELECT
                        s.id,
                        s.heading,
                        s.script_order,
                        l.label as location
                    FROM scenes s
                    JOIN nodes sn ON sn.entity_id = s.id AND sn.node_type = 'scene'
                    LEFT JOIN edges le ON (
                        le.from_node_id = sn.id AND le.edge_type = 'AT_LOCATION'
                    )
                    LEFT JOIN nodes l ON l.id = le.to_node_id
                    WHERE s.script_id = ?
                    ORDER BY s.script_order
                """
                cursor = connection.execute(location_query, (str(script.id),))

                locations = []
                location_transitions: dict[str, dict[str, int]] = defaultdict(
                    lambda: defaultdict(int)
                )
                location_counts: dict[str, int] = defaultdict(int)
                last_location = None

                for row in cursor.fetchall():
                    location = row["location"] or "UNKNOWN"
                    locations.append(
                        {
                            "scene_id": row["id"],
                            "heading": row["heading"],
                            "script_order": row["script_order"],
                            "location": location,
                        }
                    )

                    location_counts[location] += 1

                    if last_location and last_location != location:
                        location_transitions[last_location][location] += 1

                    last_location = location

                # Convert transitions to list format
                transitions = []
                for from_loc, to_locs in location_transitions.items():
                    for to_loc, count in to_locs.items():
                        transitions.append(
                            {
                                "from": from_loc,
                                "to": to_loc,
                                "count": count,
                            }
                        )

                return {
                    "script_id": script_id,
                    "analysis_type": analysis_type,
                    "location_flow": locations,
                    "location_statistics": {
                        "unique_locations": len(location_counts),
                        "location_counts": dict(location_counts),
                        "transitions": sorted(
                            transitions, key=lambda x: x["count"], reverse=True
                        ),
                    },
                }

            raise ValueError(f"Unknown analysis type: {analysis_type}")

    async def check_continuity(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check script continuity."""
        script_id = args.get("script_id")
        check_type = args.get("check_type", "all")

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Run continuity check
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            checker = ContinuityValidator(connection)

            if check_type == "all":
                # Run all continuity checks
                all_continuity_issues = checker.validate_script_continuity(
                    str(script.id)
                )
                # TODO: Categorize issues when specific methods are available
                timeline_issues: list[Any] = []
                character_issues: list[Any] = []
                location_issues: list[Any] = []
                prop_issues: list[Any] = []

                all_issues = all_continuity_issues

                return {
                    "script_id": script_id,
                    "check_type": check_type,
                    "issues": all_issues,
                    "summary": {
                        "total_issues": len(all_issues),
                        "timeline_issues": len(timeline_issues),
                        "character_issues": len(character_issues),
                        "location_issues": len(location_issues),
                        "prop_issues": len(prop_issues),
                    },
                }

            if check_type == "timeline":
                issues = checker.validate_script_continuity(str(script.id))
                return {
                    "script_id": script_id,
                    "check_type": check_type,
                    "issues": issues,
                    "total_issues": len(issues),
                }

            if check_type == "characters":
                issues = checker.validate_script_continuity(str(script.id))
                return {
                    "script_id": script_id,
                    "check_type": check_type,
                    "issues": issues,
                    "total_issues": len(issues),
                }

            if check_type == "locations":
                issues = checker.validate_script_continuity(str(script.id))
                return {
                    "script_id": script_id,
                    "check_type": check_type,
                    "issues": issues,
                    "total_issues": len(issues),
                }

            if check_type == "props":
                issues = checker.validate_script_continuity(str(script.id))
                return {
                    "script_id": script_id,
                    "check_type": check_type,
                    "issues": issues,
                    "total_issues": len(issues),
                }
            raise ValueError(f"Unknown check type: {check_type}")

    async def get_continuity_report(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get comprehensive continuity report."""
        script_id = args.get("script_id")

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Generate full continuity report
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            checker = ContinuityValidator(connection)

            # Get all continuity issues
            report = checker.generate_continuity_report(str(script.id))

            # Add script metadata
            report["script_id"] = script_id
            report["script_title"] = script.title

            # Calculate severity breakdown
            severity_counts: dict[str, int] = defaultdict(int)
            for category_issues in report["issues_by_category"].values():
                for issue in category_issues:
                    severity_counts[issue.get("severity", "info")] += 1

            report["severity_summary"] = dict(severity_counts)

            return report


def _is_earlier_time(time1: str, time2: str) -> bool:
    """Check if time1 is earlier in the day than time2."""
    time_order = {
        "MORNING": 1,
        "DAY": 2,
        "AFTERNOON": 3,
        "EVENING": 4,
        "NIGHT": 5,
        "LATE NIGHT": 6,
    }

    t1_order = time_order.get(time1.upper(), 2)  # Default to DAY
    t2_order = time_order.get(time2.upper(), 2)

    return t1_order < t2_order


def _find_absence_gaps(appearances: list[dict]) -> list[dict]:
    """Find gaps in character appearances."""
    gaps = []

    for i in range(1, len(appearances)):
        prev_order = appearances[i - 1]["script_order"]
        curr_order = appearances[i]["script_order"]

        gap_size = curr_order - prev_order - 1
        if gap_size > 5:  # Significant gap
            gaps.append(
                {
                    "after_scene": appearances[i - 1]["heading"],
                    "before_scene": appearances[i]["heading"],
                    "gap_size": gap_size,
                }
            )

    return gaps
