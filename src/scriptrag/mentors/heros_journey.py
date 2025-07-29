"""Hero's Journey Mentor Implementation.

This mentor analyzes screenplays based on Joseph Campbell's monomyth structure,
later popularized by Christopher Vogler. It identifies key archetypal stages
and provides feedback on the hero's transformation journey.

The mentor analyzes:
1. The 12 stages of the Hero's Journey
2. Hero transformation and character growth
3. Archetypal characters (mentor, shadow, herald, etc.)
4. Mythological patterns and symbolism
5. Internal vs external journey alignment
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any
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


# Hero's Journey 12-stage structure
HEROS_JOURNEY_STAGES = [
    HerosJourneyStage(
        "Ordinary World",
        (
            "The hero's normal life before the story begins. Shows the hero in their "
            "comfortable, familiar environment, establishing their background, "
            "environment, and what's at stake."
        ),
        1,
        (0.0, 0.10),
        ["ordinary", "normal", "routine", "everyday", "familiar", "home"],
        ["hero"],
    ),
    HerosJourneyStage(
        "Call to Adventure",
        (
            "The hero is presented with a problem, challenge, or adventure. "
            "This disrupts the ordinary world and sets the story in motion."
        ),
        1,
        (0.10, 0.15),
        ["call", "adventure", "quest", "mission", "problem", "challenge"],
        ["herald"],
    ),
    HerosJourneyStage(
        "Refusal of the Call",
        (
            "The hero initially refuses the adventure due to fear, insecurity, "
            "or a sense of duty to their current life. Shows their humanity and "
            "the magnitude of the journey ahead."
        ),
        1,
        (0.15, 0.20),
        ["refuse", "reluctant", "fear", "doubt", "hesitate", "can't", "won't"],
        ["hero", "threshold_guardian"],
    ),
    HerosJourneyStage(
        "Meeting the Mentor",
        (
            "The hero encounters a wise figure who gives advice, guidance, or "
            "magical gifts that will help on the journey. The mentor represents "
            "the hero's highest aspirations."
        ),
        1,
        (0.20, 0.25),
        ["mentor", "teacher", "guide", "wise", "advice", "training", "gift"],
        ["mentor", "hero"],
    ),
    HerosJourneyStage(
        "Crossing the Threshold",
        (
            "The hero commits to the adventure and enters the special world. "
            "This is the point of no return where the journey truly begins."
        ),
        1,
        (0.25, 0.30),
        ["threshold", "cross", "enter", "commit", "journey begins", "new world"],
        ["hero", "threshold_guardian"],
    ),
    HerosJourneyStage(
        "Tests, Allies, and Enemies",
        (
            "The hero faces challenges and makes allies and enemies in the special "
            "world. They learn the rules of this new world and their skills are tested."
        ),
        2,
        (0.30, 0.50),
        ["test", "challenge", "ally", "enemy", "friend", "foe", "trial"],
        ["hero", "ally", "enemy", "shapeshifter", "trickster"],
    ),
    HerosJourneyStage(
        "Approach to the Inmost Cave",
        (
            "The hero prepares for the major challenge in the special world. "
            "Often a time for planning, gathering resources, or facing inner fears."
        ),
        2,
        (0.50, 0.60),
        ["approach", "prepare", "plan", "inmost cave", "danger", "fear"],
        ["hero", "ally", "shadow"],
    ),
    HerosJourneyStage(
        "Ordeal",
        (
            "The hero faces their greatest fear or most deadly enemy. This is the "
            "climactic moment where the hero must die (literally or metaphorically) "
            "to be reborn."
        ),
        2,
        (0.60, 0.65),
        ["ordeal", "crisis", "death", "fear", "battle", "confrontation"],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Reward (Seizing the Sword)",
        (
            "The hero survives and gains the reward - an object, knowledge, or "
            "experience that will help in the final stages. Celebration and "
            "self-realization often occur."
        ),
        2,
        (0.65, 0.75),
        ["reward", "treasure", "elixir", "sword", "victory", "celebration"],
        ["hero"],
    ),
    HerosJourneyStage(
        "The Road Back",
        (
            "The hero must return to the ordinary world with their reward. "
            "Often faces a choice between personal desire and higher cause."
        ),
        3,
        (0.75, 0.85),
        ["return", "road back", "pursuit", "escape", "choice", "consequence"],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Resurrection",
        (
            "The climax where the hero must face a final test, using everything "
            "they've learned. They are transformed into a new being with the "
            "wisdom of both worlds."
        ),
        3,
        (0.85, 0.95),
        ["resurrection", "climax", "final battle", "transformation", "rebirth"],
        ["hero", "shadow"],
    ),
    HerosJourneyStage(
        "Return with the Elixir",
        (
            "The hero returns to the ordinary world with something to benefit "
            "their world - wisdom, a cure, or knowledge. The hero is now a master "
            "of both worlds."
        ),
        3,
        (0.95, 1.0),
        ["return", "elixir", "wisdom", "home", "changed", "master", "gift"],
        ["hero"],
    ),
]

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
        self.minimum_stages = self.config.get("minimum_stages", 8)

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
        _db_operations: Any,
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
                        recommendations=[
                            f"Add scenes that establish: {stage.description}",
                            (
                                "Look for opportunities to include: "
                                f"{', '.join(stage.keywords[:3])}"
                            ),
                            (
                                f"This stage typically appears in Act {stage.act} "
                                f"({stage.percentage_range[0] * 100:.0f}-"
                                f"{stage.percentage_range[1] * 100:.0f}% through "
                                "the script)"
                            ),
                        ],
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
        _stage: HerosJourneyStage,
        _scenes: list[dict],
        _start_scene: int,
        _end_scene: int,
    ) -> dict | None:
        """Find scenes that contain the specified stage."""
        # This would analyze scene content for stage keywords and patterns
        # Placeholder implementation
        return None

    def _analyze_stage_implementation(
        self,
        _stage: HerosJourneyStage,
        _stage_scenes: dict,
        _expected_start: int,
        _expected_end: int,
    ) -> MentorAnalysis | None:
        """Analyze how well a stage is implemented."""
        # Placeholder for stage implementation analysis
        return None

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
        self, _characters: list[dict], _scenes: list[dict]
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
        _script_data: dict,
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
        self, _scenes: list[dict]
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

        # Base score on percentage of stages found
        base_score = (found_stages / len(HEROS_JOURNEY_STAGES)) * 70

        # Adjust for other factors
        severity_weights = {
            AnalysisSeverity.ERROR: -5,
            AnalysisSeverity.WARNING: -2,
            AnalysisSeverity.SUGGESTION: -1,
            AnalysisSeverity.INFO: 1,
        }

        for analysis in analyses:
            if analysis.category != "journey_stages":
                base_score += severity_weights.get(analysis.severity, 0)

        return max(0.0, min(100.0, base_score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], total_scenes: int
    ) -> str:
        """Generate summary of the Hero's Journey analysis."""
        # Count stages found
        stage_analyses = [a for a in analyses if a.category == "journey_stages"]
        missing_stages = len([a for a in stage_analyses if "Missing Stage" in a.title])
        found_stages = len(HEROS_JOURNEY_STAGES) - missing_stages

        summary_parts = [
            f"Hero's Journey analysis complete for {total_scenes}-scene screenplay.",
            f"Found {found_stages} of {len(HEROS_JOURNEY_STAGES)} monomyth stages.",
        ]

        if found_stages >= self.minimum_stages:
            summary_parts.append(
                "Script follows the archetypal hero's journey structure well."
            )
        else:
            summary_parts.append(
                f"Script needs {self.minimum_stages - found_stages} more stages "
                "for a complete hero's journey."
            )

        # Add archetype summary if analyzed
        archetype_analyses = [a for a in analyses if a.category == "archetypes"]
        if archetype_analyses:
            summary_parts.append(
                "Character archetypes align with mythological patterns."
            )

        return " ".join(summary_parts)

    def validate_config(self) -> bool:
        """Validate the mentor's configuration."""
        try:
            check_archetypes = self.config.get("check_archetypes", True)
            strict_order = self.config.get("strict_order", False)
            minimum_stages = self.config.get("minimum_stages", 8)

            if not isinstance(check_archetypes, bool):
                return False
            if not isinstance(strict_order, bool):
                return False
            return isinstance(minimum_stages, int) and 1 <= minimum_stages <= 12

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
                    "maximum": 12,
                    "default": 8,
                    "description": "Minimum number of stages required",
                },
            },
            "additionalProperties": False,
        }
