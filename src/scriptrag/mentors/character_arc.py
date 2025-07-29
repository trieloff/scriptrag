"""Character Arc Mentor Implementation.

This mentor analyzes character development and transformation throughout
a screenplay. It tracks how characters change, their internal/external
conflicts, and the authenticity of their emotional journeys.

The mentor analyzes:
1. Character want vs need dynamics
2. Internal and external conflicts
3. Character transformation milestones
4. Emotional journey authenticity
5. Supporting character arcs
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


class CharacterArcType:
    """Represents a type of character arc."""

    def __init__(
        self,
        name: str,
        description: str,
        indicators: list[str],
        journey_pattern: list[str],
    ):
        """Initialize a character arc type.

        Args:
            name: Arc type name
            description: Arc description
            indicators: Keywords/patterns that indicate this arc type
            journey_pattern: Expected stages in this arc
        """
        self.name = name
        self.description = description
        self.indicators = indicators
        self.journey_pattern = journey_pattern


# Common character arc types
CHARACTER_ARC_TYPES = [
    CharacterArcType(
        "Positive Change Arc",
        (
            "Character overcomes their flaws and false beliefs to embrace truth. "
            "Most common arc where protagonist grows and changes for the better."
        ),
        ["growth", "learns", "realizes", "overcomes", "transforms", "becomes"],
        [
            "Believes lie/has flaw",
            "Encounters conflict",
            "Resists change",
            "Forced to confront truth",
            "Embraces truth",
            "Transformed person",
        ],
    ),
    CharacterArcType(
        "Negative Change Arc",
        (
            "Character descends into worse state, often embracing destructive beliefs. "
            "Common in tragedies where the protagonist's flaws lead to downfall."
        ),
        ["corrupted", "falls", "descends", "loses", "becomes worse", "tragic"],
        [
            "Has positive traits",
            "Encounters temptation",
            "Makes poor choices",
            "Justifies actions",
            "Embraces darkness",
            "Tragic ending",
        ],
    ),
    CharacterArcType(
        "Flat Arc",
        (
            "Character maintains their truth and changes the world around them. "
            "Often seen with already-heroic characters who inspire others."
        ),
        ["steadfast", "unchanging", "inspires", "influences", "stands firm"],
        [
            "Already knows truth",
            "World challenges belief",
            "Stands firm",
            "Tests resolve",
            "Influences others",
            "Changes world",
        ],
    ),
    CharacterArcType(
        "Failed Arc",
        (
            "Character has opportunity to change but fails to do so. "
            "Creates dramatic irony and often leads to tragic consequences."
        ),
        ["fails to change", "refuses", "stuck", "repeats mistakes", "stagnant"],
        [
            "Confronted with need to change",
            "Resists",
            "Given opportunities",
            "Continues to resist",
            "Misses chance",
            "Consequences",
        ],
    ),
]


class CharacterDevelopmentStage:
    """Represents a stage in character development."""

    def __init__(
        self,
        name: str,
        description: str,
        typical_position: float,
        indicators: list[str],
    ):
        """Initialize a character development stage.

        Args:
            name: Stage name
            description: What happens in this stage
            typical_position: Where in the story this typically occurs (0.0-1.0)
            indicators: Keywords that indicate this stage
        """
        self.name = name
        self.description = description
        self.typical_position = typical_position
        self.indicators = indicators


# Universal character development stages
DEVELOPMENT_STAGES = [
    CharacterDevelopmentStage(
        "Establishment",
        "Introduction showing character's initial state, flaws, and false beliefs",
        0.05,
        ["introduction", "first appearance", "establishes", "normal", "flaw"],
    ),
    CharacterDevelopmentStage(
        "Want Revealed",
        (
            "Character's external goal becomes clear - what they think "
            "will make them happy"
        ),
        0.15,
        ["wants", "desires", "goal", "pursues", "thinks needs"],
    ),
    CharacterDevelopmentStage(
        "First Test",
        "Initial challenge that reveals character's limitations and approach",
        0.25,
        ["challenged", "tested", "fails", "struggles", "confronts"],
    ),
    CharacterDevelopmentStage(
        "Deepening Conflict",
        "Internal conflict intensifies as want and need clash",
        0.40,
        ["conflict", "torn between", "doubts", "questions", "internal struggle"],
    ),
    CharacterDevelopmentStage(
        "Crisis Point",
        "Major setback forces character to question their approach",
        0.60,
        ["crisis", "lowest point", "devastated", "loses", "questioned"],
    ),
    CharacterDevelopmentStage(
        "Moment of Truth",
        "Character must choose between want and need",
        0.75,
        ["chooses", "decides", "realization", "epiphany", "moment of truth"],
    ),
    CharacterDevelopmentStage(
        "Transformation",
        "Character demonstrates their change through action",
        0.85,
        ["transformed", "changed", "different", "new person", "demonstrates"],
    ),
    CharacterDevelopmentStage(
        "New Equilibrium",
        "Character's new state is established, showing lasting change",
        0.95,
        ["new normal", "changed forever", "resolution", "peace", "fulfilled"],
    ),
]


class CharacterArcMentor(BaseMentor):
    """Character Arc mentor for analyzing character development in screenplays.

    This mentor tracks character transformation, analyzes want vs need dynamics,
    and evaluates the authenticity of character growth throughout the story.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the Character Arc mentor.

        Args:
            config: Optional configuration including:
                - analyze_supporting: Analyze supporting character arcs (default: True)
                - min_arc_characters: Min characters needing arcs (default: 1)
                - track_relationships: Track relationship dynamics (default: True)
        """
        super().__init__(config)
        self._version = "1.0.0"

        # Configuration
        self.analyze_supporting = self.config.get("analyze_supporting", True)
        self.min_arc_characters = self.config.get("min_arc_characters", 1)
        self.track_relationships = self.config.get("track_relationships", True)

    @property
    def name(self) -> str:
        """Unique name identifier for this mentor."""
        return "character_arc"

    @property
    def description(self) -> str:
        """Human-readable description of what this mentor analyzes."""
        return (
            "Analyzes character development and transformation arcs, tracking "
            "want vs need dynamics, internal/external conflicts, and emotional "
            "authenticity throughout the screenplay."
        )

    @property
    def mentor_type(self) -> MentorType:
        """Type category this mentor belongs to."""
        return MentorType.CHARACTER_ARC

    @property
    def categories(self) -> list[str]:
        """Categories of analysis this mentor provides."""
        return [
            "character_transformation",
            "want_vs_need",
            "internal_conflict",
            "emotional_journey",
            "character_relationships",
        ]

    async def analyze_script(
        self,
        script_id: UUID,
        db_operations: Any,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> MentorResult:
        """Analyze character arcs in the script.

        Args:
            script_id: UUID of the script to analyze
            db_operations: Database operations interface
            progress_callback: Optional progress callback

        Returns:
            Complete character arc analysis result
        """
        start_time = datetime.utcnow()
        analyses: list[MentorAnalysis] = []

        try:
            if progress_callback:
                progress_callback(0.1, "Loading characters and scenes...")

            # Get script data including characters and their scenes
            script_data = await self._get_script_data(script_id, db_operations)
            if not script_data:
                raise ValueError(f"Script {script_id} not found")

            characters = script_data["characters"]
            scenes = script_data["scenes"]

            if not characters:
                analyses.append(
                    MentorAnalysis(
                        title="No Characters Found",
                        description="No characters were found to analyze.",
                        severity=AnalysisSeverity.ERROR,
                        scene_id=None,
                        character_id=None,
                        element_id=None,
                        category="character_transformation",
                        mentor_name=self.name,
                    )
                )
            else:
                if progress_callback:
                    progress_callback(0.2, "Analyzing protagonist arc...")

                # Analyze main character(s)
                protagonist_analyses = await self._analyze_protagonist_arc(
                    characters, scenes
                )
                analyses.extend(protagonist_analyses)

                if progress_callback:
                    progress_callback(0.4, "Analyzing want vs need dynamics...")

                # Analyze want vs need for main characters
                want_need_analyses = await self._analyze_want_vs_need(
                    characters, scenes
                )
                analyses.extend(want_need_analyses)

                if progress_callback:
                    progress_callback(0.6, "Tracking transformation milestones...")

                # Track character development stages
                development_analyses = await self._analyze_development_stages(
                    characters, scenes
                )
                analyses.extend(development_analyses)

                if self.analyze_supporting and len(characters) > 1:
                    if progress_callback:
                        progress_callback(0.7, "Analyzing supporting characters...")

                    # Analyze supporting character arcs
                    supporting_analyses = await self._analyze_supporting_arcs(
                        characters[1:],
                        scenes,  # Assuming first is protagonist
                    )
                    analyses.extend(supporting_analyses)

                if self.track_relationships:
                    if progress_callback:
                        progress_callback(0.8, "Analyzing character relationships...")

                    # Analyze relationship dynamics
                    relationship_analyses = await self._analyze_relationships(
                        characters, scenes
                    )
                    analyses.extend(relationship_analyses)

            if progress_callback:
                progress_callback(0.9, "Generating character insights...")

            # Generate overall score and summary
            score = self._calculate_score(analyses)
            summary = self._generate_summary(analyses, len(characters))

            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            if progress_callback:
                progress_callback(1.0, "Character arc analysis complete")

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
            logger.error(f"Character arc analysis failed for script {script_id}: {e}")

            # Return error result
            error_analysis = MentorAnalysis(
                title="Analysis Error",
                description=f"Character arc analysis failed: {e!s}",
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
        """Get script data including characters and their appearances."""
        try:
            # This would use the database operations to get:
            # - Characters with their scene appearances
            # - Scene content to track character behavior
            # - Dialogue to understand character voice
            # Placeholder - would be replaced with actual database queries
            return {
                "script_id": script_id,
                "title": "Sample Script",
                "characters": [],  # Would contain character data with scene appearances
                "scenes": [],  # Would contain scene data with character actions
            }

        except Exception as e:
            logger.error(f"Failed to get script data for {script_id}: {e}")
            return None

    async def _analyze_protagonist_arc(
        self, _characters: list[dict], _scenes: list[dict]
    ) -> list[MentorAnalysis]:
        """Analyze the protagonist's character arc."""
        analyses = []

        # Identify arc type
        analyses.append(
            MentorAnalysis(
                title="Protagonist Arc Type",
                description=(
                    "Identifying the type of character arc helps understand "
                    "the story's emotional core and thematic statement."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,  # Would be protagonist's ID
                element_id=None,
                category="character_transformation",
                mentor_name=self.name,
                recommendations=[
                    "Ensure arc type aligns with genre expectations",
                    "Make character change feel earned through challenges",
                    "Connect arc resolution to story's theme",
                ],
                metadata={
                    "arc_type": "Positive Change Arc",  # Would be detected
                    "transformation_clear": True,
                },
            )
        )

        return analyses

    async def _analyze_want_vs_need(
        self, _characters: list[dict], _scenes: list[dict]
    ) -> list[MentorAnalysis]:
        """Analyze character want vs need dynamics."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Want vs Need Dynamics",
                description=(
                    "Strong character arcs clearly establish what the character "
                    "wants (external goal) versus what they need (internal growth) "
                    "for true fulfillment."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="want_vs_need",
                mentor_name=self.name,
                recommendations=[
                    "Make the want concrete and achievable",
                    "The need should address character's deep flaw",
                    "Want and need should conflict for maximum drama",
                    "Resolution should favor need over want",
                ],
            )
        )

        return analyses

    async def _analyze_development_stages(
        self, _characters: list[dict], _scenes: list[dict]
    ) -> list[MentorAnalysis]:
        """Analyze character development stages."""
        analyses = []

        # Check for missing development stages
        missing_stages: list[str] = []  # Would be populated by analysis

        if missing_stages:
            analyses.append(
                MentorAnalysis(
                    title="Incomplete Character Development",
                    description=(
                        f"Character arc is missing {len(missing_stages)} key "
                        "development stages, which may make transformation "
                        "feel unearned."
                    ),
                    severity=AnalysisSeverity.WARNING,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="character_transformation",
                    mentor_name=self.name,
                    recommendations=[
                        "Add scenes showing character's initial flaws clearly",
                        "Include moments of doubt and internal conflict",
                        "Show character actively choosing change",
                        "Demonstrate change through actions, not just words",
                    ],
                )
            )
        else:
            analyses.append(
                MentorAnalysis(
                    title="Complete Character Journey",
                    description=(
                        "Character progresses through all major development stages, "
                        "creating a satisfying transformation arc."
                    ),
                    severity=AnalysisSeverity.INFO,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="character_transformation",
                    mentor_name=self.name,
                    confidence=0.9,
                )
            )

        return analyses

    async def _analyze_supporting_arcs(
        self,
        _supporting_characters: list[dict],
        _scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze supporting character arcs."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Supporting Character Development",
                description=(
                    "Well-developed supporting characters have their own arcs "
                    "that complement and enhance the protagonist's journey."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_transformation",
                mentor_name=self.name,
                recommendations=[
                    "Give supporting characters their own wants and needs",
                    "Supporting arcs should intersect with main arc",
                    "Avoid flat supporting characters unless intentional",
                    "Use supporting characters to reflect theme",
                ],
            )
        )

        return analyses

    async def _analyze_relationships(
        self, _characters: list[dict], _scenes: list[dict]
    ) -> list[MentorAnalysis]:
        """Analyze character relationship dynamics."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Character Relationship Dynamics",
                description=(
                    "Character relationships should evolve throughout the story, "
                    "reflecting and influencing character growth."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_relationships",
                mentor_name=self.name,
                recommendations=[
                    "Show how relationships change as characters grow",
                    "Use relationships to reveal character traits",
                    "Conflict in relationships drives character development",
                    "Resolution should reflect character transformation",
                ],
            )
        )

        return analyses

    def _calculate_score(self, analyses: list[MentorAnalysis]) -> float:
        """Calculate overall character arc score."""
        if not analyses:
            return 0.0

        # Base score
        base_score = 70.0

        # Check for complete arc elements
        has_transformation = any(
            a.category == "character_transformation"
            and a.severity == AnalysisSeverity.INFO
            for a in analyses
        )
        has_want_need = any(a.category == "want_vs_need" for a in analyses)

        if has_transformation:
            base_score += 10
        if has_want_need:
            base_score += 10

        # Adjust for issues
        severity_weights = {
            AnalysisSeverity.ERROR: -15,
            AnalysisSeverity.WARNING: -5,
            AnalysisSeverity.SUGGESTION: -2,
            AnalysisSeverity.INFO: 1,
        }

        for analysis in analyses:
            base_score += severity_weights.get(analysis.severity, 0)

        return max(0.0, min(100.0, base_score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], character_count: int
    ) -> str:
        """Generate summary of character arc analysis."""
        error_count = len([a for a in analyses if a.severity == AnalysisSeverity.ERROR])
        warning_count = len(
            [a for a in analyses if a.severity == AnalysisSeverity.WARNING]
        )

        summary_parts = [
            f"Character arc analysis complete for {character_count} characters."
        ]

        if error_count == 0 and warning_count == 0:
            summary_parts.append(
                "Characters demonstrate clear, compelling transformation arcs."
            )
        else:
            summary_parts.append(
                f"Found {error_count + warning_count} areas for "
                "character development improvement."
            )

        # Check specific elements
        has_complete_arc = any(
            "Complete Character Journey" in a.title for a in analyses
        )
        if has_complete_arc:
            summary_parts.append(
                "Protagonist follows satisfying development trajectory."
            )
        else:
            summary_parts.append(
                "Character transformation needs additional development stages."
            )

        return " ".join(summary_parts)

    def validate_config(self) -> bool:
        """Validate the mentor's configuration."""
        try:
            analyze_supporting = self.config.get("analyze_supporting", True)
            min_arc_characters = self.config.get("min_arc_characters", 1)
            track_relationships = self.config.get("track_relationships", True)

            return (
                isinstance(analyze_supporting, bool)
                and isinstance(min_arc_characters, int)
                and min_arc_characters >= 0
                and isinstance(track_relationships, bool)
            )

        except Exception:
            return False

    def get_config_schema(self) -> dict[str, Any]:
        """Get the configuration schema for this mentor."""
        return {
            "type": "object",
            "properties": {
                "analyze_supporting": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze supporting character arcs",
                },
                "min_arc_characters": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 1,
                    "description": "Minimum number of characters needing arcs",
                },
                "track_relationships": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to track character relationship dynamics",
                },
            },
            "additionalProperties": False,
        }
