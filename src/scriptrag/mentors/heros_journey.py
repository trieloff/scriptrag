"""Hero's Journey Mentor Implementation.

This mentor analyzes screenplays based on Joseph Campbell's monomyth structure,
adapted for practical screenplay analysis. It identifies key archetypal stages
and provides feedback on the hero's transformation journey.

The mentor analyzes:
1. Campbell's 17-stage monomyth consolidated for screenwriting
2. Hero transformation and character growth
3. Archetypal characters (mentor, shadow, herald, etc.)
4. Mythological patterns and symbolism
5. Internal vs external journey alignment
6. Genre-specific adaptations of the journey
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from scriptrag.config import get_logger
from scriptrag.mentors.base import (
    AnalysisSeverity,
    BaseMentor,
    MentorAnalysis,
    MentorResult,
    MentorType,
)

logger = get_logger(__name__)


class HerosJourneyStage:
    """Represents a stage in the Hero's Journey."""

    def __init__(
        self,
        name: str,
        description: str,
        act: int,
        percentage_range: tuple[float, float],
        keywords: list[str],
        archetypes: list[str],
    ):
        """Initialize a Hero's Journey stage.

        Args:
            name: Stage name
            description: Stage description
            act: Which act this stage typically appears in (1, 2, or 3)
            percentage_range: Expected position in script (0.0 to 1.0)
            keywords: Keywords to look for in scenes
            archetypes: Character archetypes associated with this stage
        """
        self.name = name
        self.description = description
        self.act = act
        self.percentage_range = percentage_range
        self.keywords = keywords
        self.archetypes = archetypes


# Campbell's full 17-stage monomyth structure adapted for screenwriting
HEROS_JOURNEY_STAGES = [
    # Act 1: Departure (0-25%)
    HerosJourneyStage(
        "Ordinary World",
        (
            "The hero's normal life before the story begins. Establishes the hero's "
            "background, environment, character wound, and what's at stake. This is "
            "the 'before' snapshot that will contrast with the hero's transformation."
        ),
        1,
        (0.0, 0.10),
        ["ordinary", "normal", "routine", "everyday", "familiar", "home", "status quo"],
        ["hero"],
    ),
    HerosJourneyStage(
        "Call to Adventure",
        (
            "The inciting incident that disrupts the ordinary world. A problem, "
            "challenge, or adventure presents itself, demanding action. This is the "
            "story's catalyst that sets everything in motion."
        ),
        1,
        (0.10, 0.12),
        [
            "call",
            "adventure",
            "quest",
            "mission",
            "problem",
            "challenge",
            "inciting",
            "catalyst",
        ],
        ["herald"],
    ),
    HerosJourneyStage(
        "Refusal of the Call",
        (
            "The hero's initial reluctance or fear. Shows their humanity, the stakes "
            "involved, and the magnitude of the journey ahead. Often manifests as "
            "doubt, fear, or conflicting obligations."
        ),
        1,
        (0.12, 0.18),
        [
            "refuse",
            "reluctant",
            "fear",
            "doubt",
            "hesitate",
            "can't",
            "won't",
            "afraid",
        ],
        ["hero", "threshold_guardian"],
    ),
    HerosJourneyStage(
        "Meeting the Mentor",
        (
            "The hero encounters a wise figure who provides advice, guidance, magical "
            "gifts, or training. The mentor represents the hero's highest aspirations "
            "and often embodies what the hero can become."
        ),
        1,
        (0.18, 0.22),
        ["mentor", "teacher", "guide", "wise", "advice", "training", "gift", "lesson"],
        ["mentor", "hero"],
    ),
    HerosJourneyStage(
        "Crossing the First Threshold",
        (
            "The hero commits to the adventure and enters the special world. This is "
            "the first plot point, the moment of no return where the journey truly "
            "begins and Act Two starts."
        ),
        1,
        (0.22, 0.25),
        [
            "threshold",
            "cross",
            "enter",
            "commit",
            "journey begins",
            "new world",
            "decision",
        ],
        ["hero", "threshold_guardian"],
    ),
    # Act 2A: Initiation/Descent (25-50%)
    HerosJourneyStage(
        "Belly of the Whale",
        (
            "The hero is fully separated from the known world and self. Often a moment "
            "of apparent defeat or being swallowed by the unknown. Represents the "
            "hero's willingness to undergo metamorphosis."
        ),
        2,
        (0.25, 0.30),
        ["trapped", "swallowed", "separated", "isolated", "consumed", "metamorphosis"],
        ["hero"],
    ),
    HerosJourneyStage(
        "Tests, Allies, and Enemies",
        (
            "The hero faces challenges and makes allies and enemies in the special "
            "world. They learn the rules of this new world, their skills are tested, "
            "and the fun and games of the premise play out."
        ),
        2,
        (0.30, 0.45),
        ["test", "challenge", "ally", "enemy", "friend", "foe", "trial", "learn"],
        ["hero", "ally", "enemy", "shapeshifter", "trickster"],
    ),
    HerosJourneyStage(
        "Approach to the Inmost Cave",
        (
            "The hero prepares for the major challenge in the special world. Often "
            "involves planning, gathering resources, facing inner fears, or crossing "
            "a second threshold into the most dangerous place."
        ),
        2,
        (0.45, 0.50),
        ["approach", "prepare", "plan", "inmost cave", "danger", "fear", "preparation"],
        ["hero", "ally", "shadow"],
    ),
    # Act 2B: The Abyss and Transformation (50-75%)
    HerosJourneyStage(
        "The Ordeal",
        (
            "The midpoint crisis where the hero faces their greatest fear or most "
            "deadly enemy. A major setback or the death of the ego. The hero must "
            "die (literally or metaphorically) to be reborn."
        ),
        2,
        (0.50, 0.55),
        ["ordeal", "crisis", "death", "fear", "battle", "confrontation", "midpoint"],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Meeting with the Goddess",
        (
            "The hero experiences unconditional love or a profound connection. Often "
            "represents the hero's encounter with their anima/animus or a moment of "
            "spiritual awakening and self-realization."
        ),
        2,
        (0.55, 0.58),
        [
            "love",
            "goddess",
            "connection",
            "spiritual",
            "awakening",
            "anima",
            "understanding",
        ],
        ["hero", "goddess", "shapeshifter"],
    ),
    HerosJourneyStage(
        "Woman as Temptress",
        (
            "The hero faces temptation that could derail the quest. Not always "
            "literally a woman - represents any temptation away from the spiritual "
            "journey toward material or selfish concerns."
        ),
        2,
        (0.58, 0.62),
        ["temptation", "distraction", "desire", "material", "selfish", "abandon"],
        ["hero", "temptress", "shapeshifter"],
    ),
    HerosJourneyStage(
        "Atonement with the Father",
        (
            "The hero confronts whatever holds ultimate power in their life. Often "
            "a father figure, authority, or the hero's greatest fear. Represents "
            "confronting and transcending one's limitations."
        ),
        2,
        (0.62, 0.68),
        ["father", "authority", "confrontation", "power", "atonement", "face"],
        ["hero", "father_figure", "shadow"],
    ),
    HerosJourneyStage(
        "Apotheosis",
        (
            "The hero's moment of divine knowledge or realization. A period of rest "
            "and fulfillment before the final push. The hero achieves a greater "
            "understanding of purpose and self."
        ),
        2,
        (0.68, 0.72),
        [
            "realization",
            "divine",
            "understanding",
            "enlightenment",
            "peace",
            "knowledge",
        ],
        ["hero"],
    ),
    HerosJourneyStage(
        "The Ultimate Boon",
        (
            "The achievement of the quest's goal. The hero gains what they came for - "
            "the elixir, knowledge, or experience. This reward often transcends the "
            "original goal with deeper meaning."
        ),
        2,
        (0.72, 0.75),
        ["reward", "treasure", "elixir", "boon", "achievement", "goal", "victory"],
        ["hero"],
    ),
    # Act 3: Return (75-100%)
    HerosJourneyStage(
        "The Road Back",
        (
            "The hero begins the journey back to the ordinary world. Often faces a "
            "choice between personal desire and higher cause, or a moment of "
            "rededication to completing the journey."
        ),
        3,
        (0.75, 0.80),
        ["return", "road back", "choice", "consequence", "rededication", "pursuit"],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Resurrection",
        (
            "The climax where the hero faces a final life-or-death test. Using all "
            "lessons learned, the hero is purified and transformed into a new being "
            "with the wisdom of both worlds."
        ),
        3,
        (0.80, 0.90),
        [
            "resurrection",
            "climax",
            "final battle",
            "transformation",
            "rebirth",
            "purification",
        ],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Return with the Elixir",
        (
            "The hero returns to the ordinary world with something to heal it - "
            "wisdom, a cure, or knowledge. The hero is now master of both the inner "
            "and outer worlds, bringing renewal to their community."
        ),
        3,
        (0.90, 1.0),
        ["return", "elixir", "wisdom", "home", "changed", "master", "gift", "healing"],
        ["hero"],
    ),
]

# Practical consolidated stages for screenwriters (8 key beats)
PRACTICAL_STAGES = {
    "Ordinary World": ["Ordinary World"],
    "Call to Adventure": ["Call to Adventure"],
    "Crossing the Threshold": [
        "Refusal of the Call",
        "Meeting the Mentor",
        "Crossing the First Threshold",
    ],
    "Tests & Allies": ["Belly of the Whale", "Tests, Allies, and Enemies"],
    "Ordeal": ["Approach to the Inmost Cave", "The Ordeal"],
    "Reward/Road Back": [
        "Meeting with the Goddess",
        "Woman as Temptress",
        "Atonement with the Father",
        "Apotheosis",
        "The Ultimate Boon",
        "The Road Back",
    ],
    "Resurrection": ["Resurrection"],
    "Return with Elixir": ["Return with the Elixir"],
}

# Genre-specific adaptations
GENRE_ADAPTATIONS = {
    "action": {
        "ordinary_world_weight": 0.07,  # Compressed setup
        "tests_allies_weight": 0.35,  # Extended action sequences
        "physical_emphasis": True,
        "multiple_resurrections": True,
    },
    "drama": {
        "ordinary_world_weight": 0.15,  # Extended character setup
        "internal_journey": True,
        "psychological_ordeal": True,
        "emotional_resurrection": True,
    },
    "comedy": {
        "subverted_expectations": True,
        "mentor_as_comic_relief": True,
        "ordeal_as_embarrassment": True,
        "return_with_wisdom": True,
    },
    "romance": {
        "enemy_as_love_interest": True,
        "goddess_meeting_central": True,
        "internal_external_balance": True,
    },
    "thriller": {
        "compressed_setup": True,
        "extended_approach": True,
        "psychological_focus": True,
        "trust_themes": True,
    },
    "scifi_fantasy": {
        "world_building_emphasis": True,
        "literal_transformation": True,
        "magical_mentors": True,
        "epic_scope": True,
    },
}

# Character archetypes in the Hero's Journey
ARCHETYPES = {
    "hero": "The protagonist who goes on the journey",
    "mentor": "Wise figure who aids the hero",
    "herald": "Character who brings the call to adventure",
    "threshold_guardian": "Tests the hero's resolve",
    "shapeshifter": "Character whose loyalty/nature is unclear",
    "shadow": "The antagonist or dark force",
    "ally": "Companions who help the hero",
    "trickster": "Comic relief and catalyst for change",
    "goddess": "Represents unconditional love or spiritual connection",
    "temptress": "Represents material temptations",
    "father_figure": "Authority figure or ultimate power",
}

# Classic film examples for each stage
STAGE_EXAMPLES = {
    "Ordinary World": {
        "Star Wars": "Luke on Tatooine, farming moisture",
        "The Matrix": "Neo in his cubicle, living a double life",
        "The Hobbit": "Bilbo in the Shire, comfortable and routine",
    },
    "Call to Adventure": {
        "Star Wars": "Leia's hologram message",
        "The Matrix": "Follow the white rabbit message",
        "The Hobbit": "Gandalf's invitation to adventure",
    },
    "Refusal of the Call": {
        "Star Wars": "Luke must stay for the harvest",
        "The Matrix": "Neo doesn't believe he's the One",
        "The Hobbit": "Bilbo: 'Adventures make you late for dinner'",
    },
    "Meeting the Mentor": {
        "Star Wars": "Obi-Wan teaches Luke about the Force",
        "The Matrix": "Morpheus offers the pills",
        "The Hobbit": "Gandalf provides guidance and Sting",
    },
    "Crossing the First Threshold": {
        "Star Wars": "Luke leaves Tatooine",
        "The Matrix": "Neo takes the red pill",
        "The Hobbit": "Bilbo runs out his door",
    },
    "The Ordeal": {
        "Star Wars": "Trash compactor scene",
        "The Matrix": "Neo's first fight with Agent Smith",
        "The Hobbit": "Riddles in the dark with Gollum",
    },
    "Resurrection": {
        "Star Wars": "Trench run with Vader",
        "The Matrix": "Neo dies and returns as the One",
        "The Hobbit": "Battle of Five Armies",
    },
    "Return with the Elixir": {
        "Star Wars": "Medal ceremony, hope restored",
        "The Matrix": "Neo's phone call, promising freedom",
        "The Hobbit": "Bilbo returns changed, writes his story",
    },
}


class HerosJourneyMentor(BaseMentor):
    """Hero's Journey mentor for screenplay mythological structure analysis.

    This mentor analyzes screenplays according to Joseph Campbell's monomyth
    structure, providing feedback on archetypal patterns, hero transformation,
    and mythological storytelling elements.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the Hero's Journey mentor.

        Args:
            config: Optional configuration including:
                - check_archetypes: Whether to analyze character archetypes (default: Tr
                - strict_order: Whether stages must appear in order (default: False)
                - minimum_stages: Minimum stages required (default: 8 of 12)
        """
        super().__init__(config)
        self._version = "1.0.0"

        # Configuration
        self.check_archetypes = self.config.get("check_archetypes", True)
        self.strict_order = self.config.get("strict_order", False)
        self.minimum_stages = self.config.get("minimum_stages", 12)  # 12 of 17 stages
        self.use_practical_beats = self.config.get("use_practical_beats", True)
        self.genre = self.config.get("genre", "general")

    @property
    def name(self) -> str:
        """Unique name identifier for this mentor."""
        return "heros_journey"

    @property
    def description(self) -> str:
        """Human-readable description of what this mentor analyzes."""
        return (
            "Analyzes screenplay structure based on Joseph Campbell's Hero's Journey "
            "monomyth, identifying archetypal stages, character roles, and the hero's "
            "transformation arc through mythological patterns."
        )

    @property
    def mentor_type(self) -> MentorType:
        """Type category this mentor belongs to."""
        return MentorType.STORY_STRUCTURE

    @property
    def categories(self) -> list[str]:
        """Categories of analysis this mentor provides."""
        return [
            "monomyth",
            "hero_transformation",
            "archetypes",
            "mythological_structure",
            "journey_stages",
        ]

    async def analyze_script(
        self,
        script_id: UUID,
        db_operations: Any,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> MentorResult:
        """Analyze a script using Hero's Journey methodology.

        Args:
            script_id: UUID of the script to analyze
            db_operations: Database operations interface
            progress_callback: Optional progress callback

        Returns:
            Complete Hero's Journey analysis result
        """
        start_time = datetime.utcnow()
        analyses: list[MentorAnalysis] = []

        try:
            if progress_callback:
                progress_callback(0.1, "Loading script and identifying hero...")

            # Get script and scenes
            script_data = await self._get_script_data(script_id, db_operations)
            if not script_data:
                raise ValueError(f"Script {script_id} not found")

            scenes = script_data["scenes"]
            characters = script_data["characters"]

            if progress_callback:
                progress_callback(0.2, "Analyzing mythological stages...")

            # Analyze Hero's Journey stages
            stage_analyses = await self._analyze_stages(scenes)
            analyses.extend(stage_analyses)

            if progress_callback:
                progress_callback(0.4, "Identifying archetypal characters...")

            # Analyze character archetypes if enabled
            if self.check_archetypes and characters:
                archetype_analyses = await self._analyze_archetypes(characters, scenes)
                analyses.extend(archetype_analyses)

            if progress_callback:
                progress_callback(0.6, "Tracking hero transformation...")

            # Analyze hero's transformation arc
            transformation_analyses = await self._analyze_transformation(script_data)
            analyses.extend(transformation_analyses)

            if progress_callback:
                progress_callback(0.8, "Analyzing internal vs external journey...")

            # Analyze internal vs external journey alignment
            journey_analyses = await self._analyze_journey_alignment(scenes)
            analyses.extend(journey_analyses)

            if progress_callback:
                progress_callback(0.9, "Generating mythological insights...")

            # Generate overall score and summary
            score = self._calculate_score(analyses)
            summary = self._generate_summary(analyses, len(scenes))

            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            if progress_callback:
                progress_callback(1.0, "Hero's Journey analysis complete")

            return MentorResult(
                mentor_name=self.name,
                mentor_version=self.version,
                script_id=script_id,
                analyses=analyses,
                summary=summary,
                score=score,
                execution_time_ms=execution_time,
                config=self.config,
            )

        except Exception as e:
            logger.error(f"Hero's Journey analysis failed for script {script_id}: {e}")

            # Return error result
            error_analysis = MentorAnalysis(
                title="Analysis Error",
                description=f"Hero's Journey analysis failed: {e!s}",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="analysis_error",
                mentor_name=self.name,
            )

            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            return MentorResult(
                mentor_name=self.name,
                mentor_version=self.version,
                script_id=script_id,
                analyses=[error_analysis],
                summary=f"Analysis failed due to error: {e!s}",
                score=0.0,
                execution_time_ms=execution_time,
                config=self.config,
            )

    async def _get_script_data(
        self,
        script_id: UUID,
        db_operations: Any,  # noqa: ARG002
    ) -> dict | None:
        """Get script data including scenes and characters."""
        try:
            # This would use the database operations to get script data
            # For now, return a placeholder structure
            # In real implementation, this would query:
            # - Script metadata
            # - All scenes in script order
            # - Scene elements (dialogue, action, etc.)
            # - Characters with their appearances

            # Placeholder - would be replaced with actual database queries
            return {
                "script_id": script_id,
                "title": "Sample Script",
                "scenes": [],  # Would contain actual scene data
                "characters": [],  # Would contain character data
            }

        except Exception as e:
            logger.error(f"Failed to get script data for {script_id}: {e}")
            return None

    async def _analyze_stages(self, scenes: list[dict]) -> list[MentorAnalysis]:
        """Analyze Hero's Journey stages in the script."""
        analyses = []
        total_scenes = len(scenes) if scenes else 100
        found_stages = []

        for stage in HEROS_JOURNEY_STAGES:
            # Calculate expected scene range
            start_scene = int(stage.percentage_range[0] * total_scenes)
            end_scene = int(stage.percentage_range[1] * total_scenes)

            # Look for this stage in the script
            stage_found = self._find_stage_in_scenes(
                stage, scenes, start_scene, end_scene
            )

            if stage_found:
                found_stages.append(stage.name)
                # Analyze stage implementation
                analysis = self._analyze_stage_implementation(
                    stage, stage_found, start_scene, end_scene
                )
                if analysis:
                    analyses.append(analysis)
            else:
                # Stage missing
                severity = (
                    AnalysisSeverity.WARNING
                    if len(found_stages) >= self.minimum_stages
                    else AnalysisSeverity.ERROR
                )

                analyses.append(
                    MentorAnalysis(
                        title=f"Missing Stage: {stage.name}",
                        description=(
                            f"The '{stage.name}' stage was not clearly identified. "
                            f"{stage.description}"
                        ),
                        severity=severity,
                        scene_id=None,
                        character_id=None,
                        element_id=None,
                        category="journey_stages",
                        mentor_name=self.name,
                        recommendations=self._get_stage_recommendations(stage),
                        metadata={
                            "stage_name": stage.name,
                            "expected_position": stage.percentage_range,
                            "act": stage.act,
                        },
                    )
                )

        # Check stage ordering if strict mode
        if self.strict_order and len(found_stages) > 1:
            order_analysis = self._check_stage_order(found_stages)
            if order_analysis:
                analyses.append(order_analysis)

        return analyses

    def _find_stage_in_scenes(
        self,
        stage: HerosJourneyStage,
        scenes: list[dict],
        start_scene: int,
        end_scene: int,
    ) -> dict | None:
        """Find scenes that contain the specified stage."""
        if not scenes:
            return None

        # Search within expected range, but also a bit beyond for flexibility
        search_start = max(0, start_scene - 2)
        search_end = min(len(scenes), end_scene + 2)

        best_match = None
        best_score = 0.0

        for i in range(search_start, search_end):
            if i >= len(scenes):
                break

            scene = scenes[i]
            score = self._calculate_stage_match_score(stage, scene)

            if score > best_score:
                best_score = score
                best_match = {
                    "scene_index": i,
                    "scene": scene,
                    "score": score,
                    "position": i / len(scenes) if scenes else 0,
                }

        # Require minimum score for match
        return best_match if best_score >= 2.0 else None

    def _calculate_stage_match_score(
        self, stage: HerosJourneyStage, scene: dict
    ) -> float:
        """Calculate how well a scene matches a stage."""
        score = 0.0

        # Get scene text content
        scene_text = self._get_scene_text(scene).lower()

        # Check for keyword matches
        for keyword in stage.keywords:
            if keyword in scene_text:
                score += 1.0
                # Bonus for multiple occurrences
                count = scene_text.count(keyword)
                if count > 1:
                    score += min(count - 1, 2) * 0.3

        # Check scene heading/slug
        scene_heading = scene.get("scene_heading", "").lower()
        for keyword in stage.keywords[:3]:  # Check top keywords in heading
            if keyword in scene_heading:
                score += 0.5

        # Check for archetypal characters
        characters = scene.get("characters", [])
        for archetype in stage.archetypes:
            # This would match character names/roles to archetypes
            # For now, simple heuristic
            if archetype == "hero" and characters:
                score += 0.2  # Hero likely present
            elif archetype == "mentor" and len(characters) >= 2:
                score += 0.3
            elif archetype in ["shadow", "enemy"] and any(
                word in scene_text for word in ["antagonist", "enemy", "villain"]
            ):
                score += 0.5

        # Bonus for position matching
        scene_position = scene.get("order", 0) / 100.0  # Normalized position
        expected_position = (stage.percentage_range[0] + stage.percentage_range[1]) / 2
        position_diff = abs(scene_position - expected_position)
        if position_diff < 0.05:
            score += 1.0
        elif position_diff < 0.10:
            score += 0.5

        return score

    def _get_scene_text(self, scene: dict) -> str:
        """Extract all text content from a scene."""
        text_parts = []

        # Add scene heading
        if "scene_heading" in scene:
            text_parts.append(scene["scene_heading"])

        # Add action lines
        if "action" in scene:
            text_parts.append(scene["action"])

        # Add dialogue
        if "dialogue" in scene:
            for dialogue in scene["dialogue"]:
                text_parts.append(dialogue.get("text", ""))
                if "parenthetical" in dialogue:
                    text_parts.append(dialogue["parenthetical"])

        # Add elements if available
        if "elements" in scene:
            for element in scene["elements"]:
                if "text" in element:
                    text_parts.append(element["text"])

        return " ".join(text_parts)

    def _analyze_stage_implementation(
        self,
        stage: HerosJourneyStage,
        stage_match: dict,
        expected_start: int,  # noqa: ARG002
        expected_end: int,  # noqa: ARG002
    ) -> MentorAnalysis | None:
        """Analyze how well a stage is implemented."""
        scene_index = stage_match["scene_index"]
        score = stage_match["score"]
        position = stage_match["position"]

        # Calculate timing accuracy
        expected_position = (stage.percentage_range[0] + stage.percentage_range[1]) / 2
        timing_diff = abs(position - expected_position)

        # Determine severity based on implementation quality
        if score >= 4.0 and timing_diff < 0.05:
            severity = AnalysisSeverity.INFO
            title = f"Strong {stage.name} Implementation"
            desc_prefix = "Excellent implementation of"
        elif score >= 3.0 and timing_diff < 0.10:
            severity = AnalysisSeverity.SUGGESTION
            title = f"{stage.name} - Good with Room for Enhancement"
            desc_prefix = "Good implementation of"
        else:
            severity = AnalysisSeverity.WARNING
            title = f"{stage.name} - Weak Implementation"
            desc_prefix = "Weak implementation of"

        # Calculate percentage coverage
        scene_range = (scene_index, scene_index + 1)
        coverage = ((scene_range[1] - scene_range[0]) / 100.0) * 100

        recommendations = []

        # Timing recommendations
        if timing_diff > 0.10:
            if position < expected_position:
                recommendations.append(
                    f"This stage appears early (scene {scene_index + 1}). "
                    f"Consider delaying until around {int(expected_position * 100)}% "
                    "of the script for better pacing."
                )
            else:
                recommendations.append(
                    f"This stage appears late (scene {scene_index + 1}). "
                    f"Consider moving earlier to around "
                    f"{int(expected_position * 100)}% of the script."
                )

        # Content recommendations
        if score < 3.0:
            recommendations.extend(
                [
                    f"Strengthen {stage.name} by incorporating more key elements: "
                    f"{', '.join(stage.keywords[:3])}",
                    "Ensure the scene clearly communicates this stage's purpose",
                ]
            )

        # Genre-specific recommendations
        if self.genre in GENRE_ADAPTATIONS:
            genre_adapt = cast(dict[str, Any], GENRE_ADAPTATIONS[self.genre])
            if (
                stage.name == "Ordinary World"
                and "ordinary_world_weight" in genre_adapt
            ):
                target_weight = genre_adapt["ordinary_world_weight"]
                recommendations.append(
                    f"For {self.genre}, aim for {int(target_weight * 100)}% "
                    "of script for setup"
                )

        description = (
            f"{desc_prefix} '{stage.name}' at scene {scene_index + 1} "
            f"({position * 100:.1f}% through script). {stage.description}"
        )

        return MentorAnalysis(
            title=title,
            description=description,
            severity=severity,
            scene_id=stage_match["scene"].get("id"),
            character_id=None,
            element_id=None,
            category="journey_stages",
            mentor_name=self.name,
            recommendations=recommendations,
            metadata={
                "stage_name": stage.name,
                "match_score": score,
                "position": position,
                "expected_position": expected_position,
                "timing_accuracy": 1.0 - min(timing_diff * 10, 1.0),
                "coverage_percentage": coverage,
            },
        )

    def _check_stage_order(self, found_stages: list[str]) -> MentorAnalysis | None:
        """Check if stages appear in the correct order."""
        # Check if found stages are in the canonical order
        canonical_order = [stage.name for stage in HEROS_JOURNEY_STAGES]
        found_indices = [
            canonical_order.index(stage)
            for stage in found_stages
            if stage in canonical_order
        ]

        if found_indices != sorted(found_indices):
            return MentorAnalysis(
                title="Stage Order Issue",
                description=(
                    "The Hero's Journey stages appear out of traditional order. "
                    "While creative reordering can work, ensure it serves the story."
                ),
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="journey_stages",
                mentor_name=self.name,
                recommendations=[
                    "Consider if the non-linear structure enhances the story",
                    "Ensure audience can still follow the hero's transformation",
                    "Use clear transitions between time periods if non-linear",
                ],
            )
        return None

    async def _analyze_archetypes(
        self,
        characters: list[dict],  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> list[MentorAnalysis]:
        """Analyze character archetypes in the script."""
        analyses = []

        # Identify key archetypes
        analyses.append(
            MentorAnalysis(
                title="Archetypal Character Analysis",
                description=(
                    "Identifying character archetypes helps understand their "
                    "mythological functions in the hero's journey."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="archetypes",
                mentor_name=self.name,
                recommendations=[
                    "Ensure each archetype serves their mythological function",
                    "Consider if key archetypes are missing (mentor, shadow, herald)",
                    "Archetypes can be combined in single characters for complexity",
                ],
                metadata={
                    "identified_archetypes": [],  # Would list found archetypes
                },
            )
        )

        return analyses

    async def _analyze_transformation(
        self,
        script_data: dict,  # noqa: ARG002
    ) -> list[MentorAnalysis]:
        """Analyze the hero's transformation arc."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Hero Transformation Arc",
                description=(
                    "The hero's journey is fundamentally about transformation. "
                    "The hero should be profoundly changed by their experiences."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="hero_transformation",
                mentor_name=self.name,
                recommendations=[
                    "Show clear contrast between hero at start vs end",
                    "Transformation should be earned through trials",
                    "Internal change should mirror external journey",
                    "Character growth should feel inevitable yet surprising",
                ],
            )
        )

        return analyses

    async def _analyze_journey_alignment(
        self,
        scenes: list[dict],  # noqa: ARG002
    ) -> list[MentorAnalysis]:
        """Analyze alignment between internal and external journeys."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Internal vs External Journey",
                description=(
                    "The best hero's journeys align the external plot with the "
                    "hero's internal emotional and spiritual journey."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="mythological_structure",
                mentor_name=self.name,
                recommendations=[
                    "External obstacles should reflect internal conflicts",
                    "Physical journey milestones should mark emotional growth",
                    "The ordeal should test the hero's deepest fear/flaw",
                    "Victory should represent internal transformation",
                ],
            )
        )

        return analyses

    def _calculate_score(self, analyses: list[MentorAnalysis]) -> float:
        """Calculate overall Hero's Journey score."""
        if not analyses:
            return 0.0

        # Count found stages
        stage_analyses = [a for a in analyses if a.category == "journey_stages"]
        missing_stages = len([a for a in stage_analyses if "Missing Stage" in a.title])
        found_stages = len(HEROS_JOURNEY_STAGES) - missing_stages

        # Calculate implementation quality for found stages
        quality_scores = []
        for analysis in stage_analyses:
            if "Missing Stage" not in analysis.title and analysis.metadata:
                # Combine match score and timing accuracy
                match_score = analysis.metadata.get("match_score", 0)
                timing_accuracy = analysis.metadata.get("timing_accuracy", 0)
                quality_scores.append((match_score / 5.0) * 0.6 + timing_accuracy * 0.4)

        # Base score calculation
        # 50% for having stages, 30% for quality, 20% for other factors
        stage_presence_score = (found_stages / len(HEROS_JOURNEY_STAGES)) * 50

        quality_score = 0
        if quality_scores:
            quality_score = (sum(quality_scores) / len(quality_scores)) * 30

        base_score = stage_presence_score + quality_score

        # Adjust for other factors
        severity_weights = {
            AnalysisSeverity.ERROR: -3,
            AnalysisSeverity.WARNING: -1,
            AnalysisSeverity.SUGGESTION: 0,
            AnalysisSeverity.INFO: 1,
        }

        other_score = 0
        for analysis in analyses:
            if analysis.category != "journey_stages":
                other_score += severity_weights.get(analysis.severity, 0)

        # Bonus for meeting minimum stages
        if found_stages >= self.minimum_stages:
            base_score += 5

        # Genre-specific adjustments
        if self.genre != "general" and found_stages >= 10:
            base_score += 3  # Bonus for genre-aware implementation

        return max(0.0, min(100.0, base_score + other_score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], total_scenes: int
    ) -> str:
        """Generate summary of the Hero's Journey analysis."""
        # Count stages found
        stage_analyses = [a for a in analyses if a.category == "journey_stages"]
        missing_stages = len([a for a in stage_analyses if "Missing Stage" in a.title])
        found_stages = len(HEROS_JOURNEY_STAGES) - missing_stages

        # Identify which practical beats are covered
        practical_coverage = self._calculate_practical_coverage(stage_analyses)

        summary_parts = [
            f"Hero's Journey analysis complete for {total_scenes}-scene screenplay.",
            f"Found {found_stages} of {len(HEROS_JOURNEY_STAGES)} Campbell stages.",
        ]

        # Add practical beat coverage
        if self.use_practical_beats:
            covered_beats = len([b for b in practical_coverage.values() if b])
            summary_parts.append(
                f"Covers {covered_beats} of 8 essential screenplay beats."
            )

        if found_stages >= self.minimum_stages:
            summary_parts.append(
                "Script follows the mythological journey structure well."
            )
        else:
            summary_parts.append(
                f"Script needs {self.minimum_stages - found_stages} more stages "
                "for a complete hero's journey."
            )

        # Add genre-specific note
        if self.genre != "general":
            summary_parts.append(f"Analyzed with {self.genre} genre adaptations.")

        # Add archetype summary if analyzed
        archetype_analyses = [a for a in analyses if a.category == "archetypes"]
        if archetype_analyses:
            summary_parts.append(
                "Character archetypes align with mythological patterns."
            )

        # Add transformation insight
        transformation_analyses = [
            a for a in analyses if a.category == "hero_transformation"
        ]
        if transformation_analyses:
            summary_parts.append("Hero transformation arc analyzed.")

        return " ".join(summary_parts)

    def _calculate_practical_coverage(
        self, stage_analyses: list[MentorAnalysis]
    ) -> dict[str, bool]:
        """Calculate which practical screenplay beats are covered."""
        found_stage_names = []
        for analysis in stage_analyses:
            if "Missing Stage" not in analysis.title and analysis.metadata:
                stage_name = analysis.metadata.get("stage_name")
                if stage_name:
                    found_stage_names.append(stage_name)

        coverage = {}
        for beat_name, stage_list in PRACTICAL_STAGES.items():
            coverage[beat_name] = any(
                stage in found_stage_names for stage in stage_list
            )

        return coverage

    def _get_stage_recommendations(self, stage: HerosJourneyStage) -> list[str]:
        """Get recommendations for implementing a missing stage."""
        recommendations = [
            f"Add scenes that establish: {stage.description}",
            f"Look for opportunities to include: {', '.join(stage.keywords[:3])}",
            (
                f"This stage typically appears in Act {stage.act} "
                f"({stage.percentage_range[0] * 100:.0f}-"
                f"{stage.percentage_range[1] * 100:.0f}% through the script)"
            ),
        ]

        # Add film examples if available
        if stage.name in STAGE_EXAMPLES:
            examples = STAGE_EXAMPLES[stage.name]
            example_list = [
                f"{film}: {scene}" for film, scene in list(examples.items())[:2]
            ]
            recommendations.append(f"Classic examples: {'; '.join(example_list)}")

        # Add genre-specific advice
        if self.genre in GENRE_ADAPTATIONS:
            genre_adapt = cast(dict[str, Any], GENRE_ADAPTATIONS[self.genre])
            if (
                stage.name == "Ordinary World"
                and "ordinary_world_weight" in genre_adapt
            ):
                recommendations.append(
                    f"For {self.genre} genre, keep setup brief "
                    f"({int(genre_adapt['ordinary_world_weight'] * 100)}% of script)"
                )
            elif (
                stage.name == "Tests, Allies, and Enemies"
                and "tests_allies_weight" in genre_adapt
            ):
                recommendations.append(
                    f"For {self.genre} genre, extend this section "
                    f"({int(genre_adapt.get('tests_allies_weight', 0.25) * 100)}% "
                    "of script)"
                )

        return recommendations

    def validate_config(self) -> bool:
        """Validate the mentor's configuration."""
        try:
            check_archetypes = self.config.get("check_archetypes", True)
            strict_order = self.config.get("strict_order", False)
            minimum_stages = self.config.get("minimum_stages", 8)

            use_practical_beats = self.config.get("use_practical_beats", True)
            genre = self.config.get("genre", "general")

            if not isinstance(check_archetypes, bool):
                return False
            if not isinstance(strict_order, bool):
                return False
            if not isinstance(use_practical_beats, bool):
                return False
            if not isinstance(minimum_stages, int) or not (1 <= minimum_stages <= 17):
                return False

            valid_genres = [
                "general",
                "action",
                "drama",
                "comedy",
                "romance",
                "thriller",
                "scifi_fantasy",
            ]
            return genre in valid_genres

        except Exception:
            return False

    def get_config_schema(self) -> dict[str, Any]:
        """Get the configuration schema for this mentor."""
        return {
            "type": "object",
            "properties": {
                "check_archetypes": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze character archetypes",
                },
                "strict_order": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether stages must appear in canonical order",
                },
                "minimum_stages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 17,
                    "default": 12,
                    "description": "Minimum number of stages required (out of 17)",
                },
                "use_practical_beats": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Show consolidated 8-beat structure for screenwriters"
                    ),
                },
                "genre": {
                    "type": "string",
                    "enum": [
                        "general",
                        "action",
                        "drama",
                        "comedy",
                        "romance",
                        "thriller",
                        "scifi_fantasy",
                    ],
                    "default": "general",
                    "description": "Genre-specific adaptations for journey analysis",
                },
            },
            "additionalProperties": False,
        }
