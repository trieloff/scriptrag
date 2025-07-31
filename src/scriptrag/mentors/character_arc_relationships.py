"""Character Arc Relationship Analysis Module.

This module contains methods for analyzing various character relationships
including mentor-student, shadow/antagonist, and romantic dynamics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scriptrag.mentors.base import AnalysisSeverity, MentorAnalysis
from scriptrag.mentors.character_arc_analysis_types import (
    MentorCandidate,
    RomanceCandidate,
    ShadowCandidate,
)

if TYPE_CHECKING:
    from scriptrag.mentors.character_arc import CharacterArcMentor


class CharacterRelationshipAnalyzer:
    """Analyzes character relationships in screenplays."""

    def __init__(self, mentor: CharacterArcMentor):
        """Initialize with reference to parent mentor."""
        self.mentor = mentor

    async def analyze_relationships(
        self,
        characters: list[dict],
        scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze character relationship dynamics."""
        analyses = []

        # Analyze key relationships
        if len(characters) >= 2:
            protagonist = characters[0]
            protagonist_name = protagonist.get("name", "Protagonist")

            # Analyze mentor relationships
            mentor_analysis = self.analyze_mentor_relationships(
                protagonist, characters[1:], scenes
            )
            if mentor_analysis:
                analyses.append(mentor_analysis)

            # Analyze shadow/antagonist relationships
            shadow_analysis = self.analyze_shadow_relationships(
                protagonist, characters[1:], scenes
            )
            if shadow_analysis:
                analyses.append(shadow_analysis)

            # Analyze romantic relationships
            romance_analysis = self.analyze_romance_dynamics(
                protagonist, characters[1:], scenes
            )
            if romance_analysis:
                analyses.append(romance_analysis)

            # Overall relationship dynamics
            analyses.append(
                MentorAnalysis(
                    title=f"{protagonist_name}: Relationship Web",
                    description=(
                        "Character relationships form a web that drives and reflects "
                        "the protagonist's transformation journey."
                    ),
                    severity=AnalysisSeverity.INFO,
                    scene_id=None,
                    character_id=protagonist.get("id"),
                    element_id=None,
                    category="character_relationships",
                    mentor_name=self.mentor.name,
                    recommendations=[
                        "Each relationship should serve the character arc",
                        "Mentors see potential; shadows show dark path",
                        "Allies provide support; romance mirrors growth",
                        "Relationships should evolve with character",
                    ],
                    metadata={
                        "relationship_types": ["mentor", "shadow", "ally", "romance"],
                        "protagonist": protagonist_name,
                    },
                    confidence=0.85,
                )
            )

        return analyses

    def analyze_mentor_relationships(
        self,
        protagonist: dict,
        other_characters: list[dict],
        scenes: list[dict],
    ) -> MentorAnalysis | None:
        """Analyze mentor-student dynamics."""
        protagonist_id = protagonist.get("id")
        protagonist_name = protagonist.get("name", "").upper()

        mentor_candidates: list[MentorCandidate] = []

        # Find potential mentors based on scene interactions
        for character in other_characters:
            if character.get("id") == protagonist_id:
                continue

            mentor_score = 0
            teaching_moments: list[dict[str, str]] = []

            for scene in scenes:
                scene_has_both = False
                protagonist_present = False
                mentor_present = False
                mentor_dialogue = []

                for element in scene.get("elements", []):
                    # Check for protagonist
                    if (
                        element.get("character_id") == protagonist_id
                        or element.get("character_name", "").upper() == protagonist_name
                    ):
                        protagonist_present = True

                    # Check for potential mentor
                    if element.get("character_id") == character.get("id") or (
                        element.get("character_name", "").upper()
                        == character.get("name", "").upper()
                    ):
                        mentor_present = True
                        if element.get("element_type") == "dialogue":
                            mentor_dialogue.append(element.get("text", ""))

                scene_has_both = protagonist_present and mentor_present

                # Analyze mentor dialogue for teaching indicators
                if scene_has_both and mentor_dialogue:
                    for dialogue in mentor_dialogue:
                        text = dialogue.lower()
                        if any(
                            word in text
                            for word in [
                                "remember",
                                "learn",
                                "understand",
                                "know",
                                "wisdom",
                                "lesson",
                                "teach",
                                "show you",
                                "guide",
                                "help you",
                                "you must",
                                "you need to",
                                "listen",
                                "trust",
                            ]
                        ):
                            mentor_score += 1
                            teaching_moments.append(
                                {
                                    "scene": scene.get("heading", ""),
                                    "lesson": (
                                        dialogue[:100] + "..."
                                        if len(dialogue) > 100
                                        else dialogue
                                    ),
                                }
                            )

            if mentor_score > 0:
                mentor_candidates.append(
                    MentorCandidate(
                        character=character,
                        score=mentor_score,
                        teaching_moments=teaching_moments[:3],  # Top 3 moments
                    )
                )

        if not mentor_candidates:
            return None

        # Select the best mentor candidate
        best_mentor = max(mentor_candidates, key=lambda x: x["score"])

        mentor_char = best_mentor["character"]
        mentor_name = (
            mentor_char.get("name", "Unknown")
            if isinstance(mentor_char, dict)
            else "Unknown"
        )

        description = (
            f"{mentor_name} serves as a mentor figure with "
            f"{best_mentor['score']} teaching moments. Key lessons include: "
        )
        if best_mentor["teaching_moments"]:
            lessons = []
            for m in best_mentor["teaching_moments"][:2]:
                if isinstance(m, dict) and "lesson" in m:
                    lesson_text = m["lesson"]
                    lessons.append(
                        lesson_text[:50] + "..."
                        if len(lesson_text) > 50
                        else lesson_text
                    )
            if lessons:
                description += "; ".join(lessons)

        return MentorAnalysis(
            title=f"Mentor Relationship: {mentor_name}",
            description=description,
            severity=AnalysisSeverity.INFO,
            scene_id=None,
            character_id=protagonist_id,
            element_id=None,
            category="character_relationships",
            mentor_name=self.mentor.name,
            recommendations=[
                "Consider strengthening the mentor relationship in Act 2",
                (
                    f"Add a scene where {mentor_name} directly challenges "
                    f"{protagonist_name}'s beliefs"
                ),
            ],
            metadata={
                "mentor_score": best_mentor["score"],
                "teaching_moments_count": len(best_mentor.get("teaching_moments", [])),
            },
            confidence=min(1.0, best_mentor["score"] * 0.2),
        )

    def analyze_shadow_relationships(
        self,
        protagonist: dict,
        other_characters: list[dict],
        scenes: list[dict],
    ) -> MentorAnalysis | None:
        """Analyze shadow/antagonist relationships."""
        protagonist_id = protagonist.get("id")
        protagonist_name = protagonist.get("name", "").upper()

        shadow_candidates: list[ShadowCandidate] = []

        # Find potential shadow characters based on conflict and mirroring
        for character in other_characters:
            if character.get("id") == protagonist_id:
                continue

            conflict_score = 0
            mirror_moments = []
            direct_conflicts = []

            for scene in scenes:
                protagonist_present = False
                shadow_present = False
                scene_dialogue: dict[str, list[str]] = {"protagonist": [], "shadow": []}

                for element in scene.get("elements", []):
                    # Check for protagonist
                    if (
                        element.get("character_id") == protagonist_id
                        or element.get("character_name", "").upper() == protagonist_name
                    ):
                        protagonist_present = True
                        if element.get("element_type") == "dialogue":
                            scene_dialogue["protagonist"].append(
                                element.get("text", "")
                            )

                    # Check for potential shadow
                    if element.get("character_id") == character.get("id") or (
                        element.get("character_name", "").upper()
                        == character.get("name", "").upper()
                    ):
                        shadow_present = True
                        if element.get("element_type") == "dialogue":
                            scene_dialogue["shadow"].append(element.get("text", ""))

                # Analyze conflict and mirroring
                if protagonist_present and shadow_present:
                    # Check for direct conflict
                    for p_dialogue in scene_dialogue["protagonist"]:
                        p_text = p_dialogue.lower()
                        if character.get("name", "").lower() in p_text and any(
                            word in p_text
                            for word in [
                                "against",
                                "stop",
                                "fight",
                                "oppose",
                                "never be like",
                            ]
                        ):
                            conflict_score += 2
                            direct_conflicts.append(scene.get("heading", ""))

                    # Check for philosophical opposition
                    for s_dialogue in scene_dialogue["shadow"]:
                        s_text = s_dialogue.lower()
                        if any(
                            word in s_text
                            for word in [
                                "weak",
                                "fool",
                                "naive",
                                "could have been",
                                "like me",
                                "join me",
                                "understand",
                                "same",
                                "no different",
                            ]
                        ):
                            conflict_score += 1
                            mirror_moments.append(
                                {
                                    "scene": scene.get("heading", ""),
                                    "dialogue": (
                                        s_dialogue[:100] + "..."
                                        if len(s_dialogue) > 100
                                        else s_dialogue
                                    ),
                                }
                            )

                # Check action lines for confrontation
                elif protagonist_present or shadow_present:
                    for element in scene.get("elements", []):
                        if element.get("element_type") == "action":
                            action_text = element.get("text", "").lower()
                            if (
                                protagonist_name.lower() in action_text
                                and character.get("name", "").lower() in action_text
                                and any(
                                    word in action_text
                                    for word in [
                                        "confronts",
                                        "faces",
                                        "battles",
                                        "opposes",
                                        "challenges",
                                    ]
                                )
                            ):
                                conflict_score += 1

            if conflict_score > 0:
                shadow_candidates.append(
                    ShadowCandidate(
                        character=character,
                        score=conflict_score,
                        mirror_moments=mirror_moments[:3],
                        direct_conflicts=direct_conflicts[:3],
                    )
                )

        if not shadow_candidates:
            return None

        # Select the best shadow candidate
        best_shadow = max(shadow_candidates, key=lambda x: x["score"])

        shadow_char = best_shadow["character"]
        shadow_name = (
            shadow_char.get("name", "Unknown")
            if isinstance(shadow_char, dict)
            else "Unknown"
        )

        description = (
            f"{shadow_name} serves as a shadow/antagonist with "
            f"{best_shadow['score']} conflict points. "
        )
        if best_shadow["mirror_moments"]:
            description += "Shadow relationship shows philosophical opposition. "
        if best_shadow["direct_conflicts"]:
            conflicts = best_shadow["direct_conflicts"]
            if isinstance(conflicts, list) and conflicts:
                description += f"Direct confrontations in: {', '.join(conflicts[:2])}"

        return MentorAnalysis(
            title=f"Shadow Relationship: {shadow_name}",
            description=description,
            severity=AnalysisSeverity.INFO,
            scene_id=None,
            character_id=protagonist_id,
            element_id=None,
            category="character_relationships",
            mentor_name=self.mentor.name,
            recommendations=[
                (
                    f"Deepen the philosophical conflict between "
                    f"{protagonist_name} and {shadow_name}"
                ),
                (
                    "Consider adding a scene where the shadow represents the "
                    "protagonist's potential dark future"
                ),
                (
                    "Ensure the shadow's motivations mirror or invert the "
                    "protagonist's core values"
                ),
            ],
            metadata={
                "conflict_score": best_shadow["score"],
                "mirror_moments_count": len(best_shadow.get("mirror_moments", [])),
                "direct_conflicts_count": len(best_shadow.get("direct_conflicts", [])),
            },
            confidence=min(1.0, best_shadow["score"] * 0.1),
        )

    def analyze_romance_dynamics(
        self,
        protagonist: dict,
        other_characters: list[dict],
        scenes: list[dict],
    ) -> MentorAnalysis | None:
        """Analyze romantic relationships as character growth catalysts."""
        protagonist_id = protagonist.get("id")
        protagonist_name = protagonist.get("name", "").upper()

        romance_candidates: list[RomanceCandidate] = []

        # Find potential romantic interests based on interactions
        for character in other_characters:
            if character.get("id") == protagonist_id:
                continue

            intimacy_score = 0
            romantic_moments = []
            growth_catalysts = []

            for scene in scenes:
                protagonist_dialogue = []
                love_interest_dialogue = []
                scene_has_both = False

                for element in scene.get("elements", []):
                    # Check for protagonist
                    if (
                        element.get("character_id") == protagonist_id
                        or element.get("character_name", "").upper() == protagonist_name
                    ) and element.get("element_type") == "dialogue":
                        protagonist_dialogue.append(element.get("text", ""))

                    # Check for potential love interest
                    if (
                        element.get("character_id") == character.get("id")
                        or (
                            element.get("character_name", "").upper()
                            == character.get("name", "").upper()
                        )
                    ) and element.get("element_type") == "dialogue":
                        love_interest_dialogue.append(element.get("text", ""))

                scene_has_both = bool(protagonist_dialogue and love_interest_dialogue)

                if scene_has_both:
                    # Check for romantic indicators
                    for p_dialogue in protagonist_dialogue:
                        p_text = p_dialogue.lower()
                        if any(
                            word in p_text
                            for word in [
                                "love",
                                "care about",
                                "need you",
                                "miss",
                                "feel",
                                "heart",
                                "together",
                                "us",
                                "beautiful",
                                "special",
                            ]
                        ):
                            intimacy_score += 2
                            romantic_moments.append(
                                {
                                    "scene": scene.get("heading", ""),
                                    "moment": (
                                        p_dialogue[:80] + "..."
                                        if len(p_dialogue) > 80
                                        else p_dialogue
                                    ),
                                }
                            )

                        # Check for vulnerability (growth catalyst)
                        if any(
                            word in p_text
                            for word in [
                                "afraid",
                                "trust",
                                "never told anyone",
                                "truth",
                                "real me",
                                "scared",
                                "open up",
                            ]
                        ):
                            intimacy_score += 1
                            growth_catalysts.append("vulnerability")

                    # Check love interest's impact on protagonist
                    for l_dialogue in love_interest_dialogue:
                        l_text = l_dialogue.lower()
                        if any(
                            word in l_text
                            for word in [
                                "believe in you",
                                "strong",
                                "changed",
                                "better",
                                "proud",
                                "see you",
                                "know you can",
                            ]
                        ):
                            intimacy_score += 1
                            growth_catalysts.append("encouragement")

                # Check action lines for romantic moments
                for element in scene.get("elements", []):
                    if element.get("element_type") == "action":
                        action_text = element.get("text", "").lower()
                        if (
                            protagonist_name.lower() in action_text
                            and character.get("name", "").lower() in action_text
                            and any(
                                word in action_text
                                for word in [
                                    "kiss",
                                    "embrace",
                                    "holds",
                                    "touches",
                                    "looks into",
                                    "takes hand",
                                    "close",
                                    "intimate",
                                ]
                            )
                        ):
                            intimacy_score += 2
                            romantic_moments.append(
                                {
                                    "scene": scene.get("heading", ""),
                                    "moment": "Physical intimacy",
                                }
                            )

            if intimacy_score > 0:
                romance_candidates.append(
                    RomanceCandidate(
                        character=character,
                        score=intimacy_score,
                        romantic_moments=romantic_moments[:3],
                        growth_catalysts=list(set(growth_catalysts)),
                    )
                )

        if not romance_candidates:
            return None

        # Select the strongest romantic relationship
        best_romance = max(romance_candidates, key=lambda x: x["score"])

        romance_char = best_romance["character"]
        romance_name = (
            romance_char.get("name", "Unknown")
            if isinstance(romance_char, dict)
            else "Unknown"
        )

        description = (
            f"Romantic relationship with {romance_name} shows "
            f"{best_romance['score']} intimacy points. "
        )
        if best_romance["growth_catalysts"]:
            catalysts = best_romance["growth_catalysts"]
            if isinstance(catalysts, list) and catalysts:
                description += (
                    f"Romance catalyzes growth through: {', '.join(catalysts)}. "
                )

        return MentorAnalysis(
            title=f"Romance Arc: {romance_name}",
            description=description,
            severity=AnalysisSeverity.INFO,
            scene_id=None,
            character_id=protagonist_id,
            element_id=None,
            category="character_relationships",
            mentor_name=self.mentor.name,
            recommendations=[
                f"Ensure the romance mirrors {protagonist_name}'s internal journey",
                "Add a scene where romantic conflict forces character growth",
                "Consider how the relationship tests the protagonist's arc theme",
            ],
            metadata={
                "intimacy_score": best_romance["score"],
                "growth_catalysts": best_romance.get("growth_catalysts", []),
                "romantic_moments_count": len(best_romance.get("romantic_moments", [])),
            },
            confidence=min(1.0, best_romance["score"] * 0.1),
        )
