"""Character Arc Conflict and Agency Analysis Module.

This module contains methods for analyzing character conflicts (internal/external)
and character agency progression throughout the screenplay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scriptrag.mentors.character_arc_markers import AGENCY_PHASES

if TYPE_CHECKING:
    from scriptrag.mentors.character_arc import CharacterArcMentor


class CharacterConflictAnalyzer:
    """Analyzes character conflicts and agency in screenplays."""

    def __init__(self, mentor: CharacterArcMentor):
        """Initialize with reference to parent mentor."""
        self.mentor = mentor

    def analyze_character_agency(
        self,
        character: dict,
        scenes: list[dict],
    ) -> dict[str, float]:
        """Analyze character's agency progression through the story."""
        character_id = character.get("id")
        character_name = character.get("name", "").upper()

        # Track agency levels across scenes
        agency_scores: dict[str, float] = {phase.name: 0.0 for phase in AGENCY_PHASES}
        scene_count = 0

        for scene in scenes:
            character_in_scene = False
            scene_agency_indicators = []

            for element in scene.get("elements", []):
                is_character_element = (
                    element.get("character_id") == character_id
                    or element.get("character_name", "").upper() == character_name
                )

                if is_character_element:
                    character_in_scene = True
                    element_text = element.get("text", "").lower()

                    # Check dialogue for agency indicators
                    if element.get("element_type") == "dialogue":
                        for phase in AGENCY_PHASES:
                            if any(
                                indicator in element_text
                                for indicator in phase.indicators
                            ):
                                scene_agency_indicators.append(phase.name)

                # Check action lines involving the character
                elif element.get("element_type") == "action":
                    action_text = element.get("text", "").lower()
                    if character_name.lower() in action_text:
                        for phase in AGENCY_PHASES:
                            if any(
                                indicator in action_text
                                for indicator in phase.indicators
                            ):
                                scene_agency_indicators.append(phase.name)

            # Score the predominant agency level in this scene
            if character_in_scene and scene_agency_indicators:
                scene_count += 1
                # Count occurrences and assign to highest
                for indicator in scene_agency_indicators:
                    agency_scores[indicator] += 1

        # Normalize scores
        if scene_count > 0:
            for phase_name in agency_scores:
                agency_scores[phase_name] = agency_scores[phase_name] / scene_count
        else:
            # Default distribution if character not found
            for phase in AGENCY_PHASES:
                agency_scores[phase.name] = phase.typical_percentage

        return agency_scores

    def analyze_internal_external_conflict(
        self,
        character: dict,
        scenes: list[dict],
    ) -> dict[str, Any]:
        """Analyze how internal and external conflicts intersect."""
        character_id = character.get("id")
        character_name = character.get("name", "").upper()

        internal_conflicts = set()
        external_conflicts = set()
        intersection_points = []

        # Track conflict progression
        early_conflicts: dict[str, set[str]] = {"internal": set(), "external": set()}
        late_conflicts: dict[str, set[str]] = {"internal": set(), "external": set()}

        total_scenes = len(scenes)
        early_threshold = total_scenes // 3
        late_threshold = 2 * total_scenes // 3

        for idx, scene in enumerate(scenes):
            scene_internal = set()
            scene_external = set()

            for element in scene.get("elements", []):
                is_character_element = (
                    element.get("character_id") == character_id
                    or element.get("character_name", "").upper() == character_name
                )

                if is_character_element and element.get("element_type") == "dialogue":
                    text = element.get("text", "").lower()

                    # Detect internal conflicts
                    if any(word in text for word in ["afraid", "scared", "fear"]):
                        scene_internal.add("fear")
                    if any(
                        word in text
                        for word in ["can't", "not good enough", "failure", "weak"]
                    ):
                        scene_internal.add("self-doubt")
                    if any(
                        word in text
                        for word in ["guilty", "my fault", "shouldn't have", "regret"]
                    ):
                        scene_internal.add("guilt")
                    if any(
                        word in text
                        for word in ["alone", "nobody", "isolated", "lonely"]
                    ):
                        scene_internal.add("isolation")
                    if any(
                        word in text
                        for word in [
                            "confused",
                            "don't understand",
                            "lost",
                            "uncertain",
                        ]
                    ):
                        scene_internal.add("confusion")

                # Check action lines for external conflicts
                elif element.get("element_type") == "action":
                    text = element.get("text", "").lower()
                    if character_name.lower() in text:
                        if any(
                            word in text
                            for word in ["attacks", "fights", "confronts", "battles"]
                        ):
                            scene_external.add("physical conflict")
                        if any(
                            word in text
                            for word in [
                                "argues",
                                "disputes",
                                "disagrees",
                                "conflicts with",
                            ]
                        ):
                            scene_external.add("interpersonal conflict")
                        if any(
                            word in text
                            for word in ["blocked", "prevented", "stopped", "obstacles"]
                        ):
                            scene_external.add("obstacles")
                        if any(
                            word in text
                            for word in [
                                "time running out",
                                "deadline",
                                "too late",
                                "hurry",
                            ]
                        ):
                            scene_external.add("time pressure")
                        if any(
                            word in text
                            for word in ["chased", "pursued", "hunted", "escapes"]
                        ):
                            scene_external.add("pursuit")

            # Add to overall conflict sets
            internal_conflicts.update(scene_internal)
            external_conflicts.update(scene_external)

            # Track progression
            if idx < early_threshold:
                early_conflicts["internal"].update(scene_internal)
                early_conflicts["external"].update(scene_external)
            elif idx > late_threshold:
                late_conflicts["internal"].update(scene_internal)
                late_conflicts["external"].update(scene_external)

            # Identify intersection points
            if scene_internal and scene_external:
                intersection_desc = f"Scene {idx + 1}: "
                if "fear" in scene_internal and "physical conflict" in scene_external:
                    intersection_desc += "External danger triggers internal fear"
                elif "self-doubt" in scene_internal and "obstacles" in scene_external:
                    intersection_desc += "External obstacles reinforce self-doubt"
                elif (
                    "guilt" in scene_internal
                    and "interpersonal conflict" in scene_external
                ):
                    intersection_desc += "Relationship conflicts stem from guilt"
                else:
                    intersection_desc += (
                        f"{next(iter(scene_internal))} meets "
                        f"{next(iter(scene_external))}"
                    )

                intersection_points.append(intersection_desc)

        # Determine if conflicts escalate
        conflict_escalation = len(late_conflicts["internal"]) >= len(
            early_conflicts["internal"]
        ) or len(late_conflicts["external"]) >= len(early_conflicts["external"])

        return {
            "internal_conflicts": (
                list(internal_conflicts)
                if internal_conflicts
                else ["unspecified internal struggle"]
            ),
            "external_conflicts": (
                list(external_conflicts)
                if external_conflicts
                else ["unspecified external challenge"]
            ),
            "intersection_points": (
                intersection_points[:5]
                if intersection_points
                else [("Internal and external conflicts operate independently")]
            ),
            "conflict_escalation": conflict_escalation,
        }
