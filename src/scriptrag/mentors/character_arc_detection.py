"""Character Arc Detection and Analysis Utilities.

This module contains methods for detecting character arc types and
finding transformation markers in screenplays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scriptrag.mentors.character_arc_markers import TRANSFORMATION_MARKERS
from scriptrag.mentors.character_arc_types import CHARACTER_ARC_TYPES, CharacterArcType

if TYPE_CHECKING:
    from scriptrag.mentors.character_arc import CharacterArcMentor


class CharacterArcDetector:
    """Detects and analyzes character arc types and transformation markers."""

    def __init__(self, mentor: CharacterArcMentor):
        """Initialize with reference to parent mentor."""
        self.mentor = mentor

    def detect_arc_type(
        self,
        character: dict,
        scenes: list[dict],
    ) -> CharacterArcType | None:
        """Detect the character's arc type based on their journey."""
        if not scenes:
            return None

        character_id = character.get("id")
        character_name = character.get("name", "").upper()

        # Analyze character's presence and dialogue across scenes
        first_appearance_idx = None
        last_appearance_idx = None
        dialogue_samples = []
        action_patterns = []

        for idx, scene in enumerate(scenes):
            for element in scene.get("elements", []):
                if element.get("character_id") == character_id or (
                    element.get("character_name", "").upper() == character_name
                ):
                    if first_appearance_idx is None:
                        first_appearance_idx = idx
                    last_appearance_idx = idx

                    if element.get("element_type") == "dialogue":
                        dialogue_samples.append(
                            {
                                "scene_idx": idx,
                                "text": element.get("text", ""),
                            }
                        )
                    elif (
                        element.get("element_type") == "action"
                        and character_name in element.get("text", "").upper()
                    ):
                        action_patterns.append(
                            {
                                "scene_idx": idx,
                                "text": element.get("text", ""),
                            }
                        )

        if first_appearance_idx is None or last_appearance_idx is None:
            return None

        # Calculate arc progression metrics
        total_scenes = last_appearance_idx - first_appearance_idx + 1
        if total_scenes < 3:
            return None  # Not enough scenes to determine arc

        # Analyze early vs late dialogue for transformation indicators
        early_dialogues = [
            d
            for d in dialogue_samples
            if d["scene_idx"] <= first_appearance_idx + total_scenes // 3
        ]
        late_dialogues = [
            d
            for d in dialogue_samples
            if d["scene_idx"] >= last_appearance_idx - total_scenes // 3
        ]

        # Look for transformation indicators
        positive_change_indicators = 0
        negative_change_indicators = 0
        flat_arc_indicators = 0

        # Analyze dialogue tone and content changes
        if early_dialogues and late_dialogues:
            # Check for confidence/assertiveness changes
            early_questions = sum(1 for d in early_dialogues if "?" in d["text"])
            late_questions = sum(1 for d in late_dialogues if "?" in d["text"])

            early_negatives = sum(
                1
                for d in early_dialogues
                if any(
                    word in d["text"].lower()
                    for word in ["can't", "won't", "never", "afraid", "sorry"]
                )
            )
            late_negatives = sum(
                1
                for d in late_dialogues
                if any(
                    word in d["text"].lower()
                    for word in ["can't", "won't", "never", "afraid", "sorry"]
                )
            )

            early_assertives = sum(
                1
                for d in early_dialogues
                if any(
                    word in d["text"].lower()
                    for word in ["will", "must", "know", "believe", "fight"]
                )
            )
            late_assertives = sum(
                1
                for d in late_dialogues
                if any(
                    word in d["text"].lower()
                    for word in ["will", "must", "know", "believe", "fight"]
                )
            )

            # Positive change: less questions, less negatives, more assertives
            if early_questions > late_questions and early_negatives > late_negatives:
                positive_change_indicators += 2
            if late_assertives > early_assertives:
                positive_change_indicators += 1

            # Negative change: more negatives, less assertives
            if late_negatives > early_negatives and late_assertives < early_assertives:
                negative_change_indicators += 2

            # Flat arc: consistent patterns
            question_diff = abs(early_questions - late_questions)
            negative_diff = abs(early_negatives - late_negatives)
            assertive_diff = abs(early_assertives - late_assertives)

            if question_diff <= 1 and negative_diff <= 1 and assertive_diff <= 1:
                flat_arc_indicators += 2

        # Determine arc type based on indicators
        max_indicators = max(
            positive_change_indicators, negative_change_indicators, flat_arc_indicators
        )

        if max_indicators == 0:
            # Default to positive change if no strong indicators
            return CHARACTER_ARC_TYPES[0]
        if positive_change_indicators == max_indicators:
            return CHARACTER_ARC_TYPES[0]  # Positive Change Arc
        if negative_change_indicators == max_indicators:
            return CHARACTER_ARC_TYPES[1]  # Negative Change Arc
        if flat_arc_indicators == max_indicators:
            return CHARACTER_ARC_TYPES[2]  # Flat Arc
        return CHARACTER_ARC_TYPES[0]  # Default to positive

    def check_journey_waypoints(
        self,
        character: dict,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
        arc_type: CharacterArcType,
    ) -> list[str]:
        """Check which journey waypoints are missing for the arc type."""
        # Would analyze character's scenes to find which waypoints are present
        # Return list of missing waypoints

        # Placeholder implementation
        found_waypoints: set[str] = set()
        missing_waypoints = []

        # In real implementation, would scan scenes for waypoint indicators
        for waypoint in arc_type.journey_pattern:
            if waypoint not in found_waypoints:
                missing_waypoints.append(waypoint)

        return missing_waypoints[:3]  # Return top 3 missing

    def find_transformation_marker(
        self,
        character: dict,
        scenes: list[dict],
        marker_name: str,
    ) -> list[dict]:
        """Find scenes containing a specific transformation marker."""
        marker = next(
            (m for m in TRANSFORMATION_MARKERS if m.name == marker_name), None
        )
        if not marker:
            return []

        character_id = character.get("id")
        character_name = character.get("name", "").upper()
        matching_scenes = []

        for scene in scenes:
            scene_has_character = False
            scene_indicators = []

            # Check if character appears in this scene
            for element in scene.get("elements", []):
                if element.get("character_id") == character_id or (
                    element.get("character_name", "").upper() == character_name
                ):
                    scene_has_character = True

                    # Check for marker indicators in dialogue
                    if element.get("element_type") == "dialogue":
                        text = element.get("text", "").lower()
                        for indicator in marker.indicators:
                            if indicator.lower() in text:
                                scene_indicators.append(indicator)

                # Also check action lines for character involvement in marker events
                elif element.get("element_type") == "action" and scene_has_character:
                    text = element.get("text", "").lower()
                    # Check for physical manifestations of the marker
                    if marker_name == "Dark Night of the Soul" and any(
                        word in text
                        for word in ["collapses", "breaks down", "defeated", "gives up"]
                    ):
                        scene_indicators.append("physical breakdown")
                    elif marker_name == "Point of No Return" and any(
                        word in text
                        for word in ["decides", "commits", "no turning back", "crosses"]
                    ):
                        scene_indicators.append("decisive action")
                    elif marker_name == "Mirror Moment" and any(
                        word in text
                        for word in ["realizes", "sees", "understands", "reflection"]
                    ):
                        scene_indicators.append("realization")

            # If scene has character and indicators, add to matches
            if scene_has_character and scene_indicators:
                matching_scenes.append(
                    {
                        "scene_id": scene.get("id"),
                        "heading": scene.get("heading", ""),
                        "script_order": scene.get("script_order", 0),
                        "indicators_found": scene_indicators,
                    }
                )

        # Sort by script order and return top matches
        matching_scenes.sort(key=lambda x: x["script_order"])
        return matching_scenes[:3]  # Return up to 3 best matches
