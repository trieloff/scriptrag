"""Character Arc Mentor Implementation.

This mentor analyzes character development and transformation throughout
a screenplay. It tracks how characters change, their internal/external
conflicts, and the authenticity of their emotional journeys.

The mentor analyzes:
1. Arc type classification (positive, negative, flat, corruption)
2. Transformation markers and journey waypoints
3. Character want vs need dynamics
4. Internal vs external conflict intersection
5. Character agency and decision architecture
6. Relationship dynamics as change catalysts
7. Theme integration with character journey
8. Supporting and ensemble character arcs
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
        examples: list[str],
        thematic_focus: str,
    ):
        """Initialize a character arc type.

        Args:
            name: Arc type name
            description: Arc description
            indicators: Keywords/patterns that indicate this arc type
            journey_pattern: Expected stages in this arc
            examples: Famous examples of this arc type
            thematic_focus: What theme this arc typically explores
        """
        self.name = name
        self.description = description
        self.indicators = indicators
        self.journey_pattern = journey_pattern
        self.examples = examples
        self.thematic_focus = thematic_focus


# Comprehensive character arc types based on screenplay expertise
CHARACTER_ARC_TYPES = [
    CharacterArcType(
        "Positive Change Arc",
        (
            "Character overcomes their false belief (The Lie) to embrace truth. "
            "They transform from flawed to fulfilled through trials and revelation. "
            "Most common arc where protagonist grows and changes for the better."
        ),
        [
            "growth",
            "learns",
            "realizes",
            "overcomes",
            "transforms",
            "becomes",
            "discovers",
            "accepts",
            "embraces",
            "evolves",
            "heals",
            "forgives",
        ],
        [
            "The Lie They Believe (initial false belief)",
            "Comfort Zone (where they hide from growth)",
            "Catalyst Moment (forced out of hiding)",
            "First Act Resistance (clinging to the lie)",
            "Education Phase (learning but not changing inside)",
            "Midpoint Mirror (seeing who they could become)",
            "Dark Night Moment (everything fails, lie seems true)",
            "The Revelation (visceral understanding of truth)",
            "Climactic Choice (choosing new self over old)",
            "New Equilibrium (fundamentally changed)",
        ],
        ["Luke Skywalker", "Erin Brockovich", "Andy Dufresne", "Katniss Everdeen"],
        "Personal growth through adversity",
    ),
    CharacterArcType(
        "Negative Change Arc",
        (
            "Character had every opportunity to change but refused them all. "
            "Their fatal flaw and pride lead to systematic destruction of everything "
            "they claimed to value. The tragedy of stubborn blindness."
        ),
        [
            "corrupted",
            "falls",
            "descends",
            "loses",
            "deteriorates",
            "pride",
            "refuses",
            "justifies",
            "rationalizes",
            "betrays",
            "isolates",
            "destroys",
        ],
        [
            "The Pride Point (where they cannot bend)",
            "Initial Compromise ('just this once')",
            "The Rationalization (justifying the means)",
            "First Warning (consequences appear)",
            "Doubling Down (going deeper instead of pulling back)",
            "Rejected Redemptions (speeding past offramps)",
            "The Betrayal Cascade (betraying more important values)",
            "Point of No Return (the damning choice)",
            "Systematic Destruction (losing what they protected)",
            "The Isolation Endpoint (alone with their pride)",
        ],
        ["Walter White", "Michael Corleone", "Anakin Skywalker", "Macbeth"],
        "How pride and fear corrupt absolutely",
    ),
    CharacterArcType(
        "Flat Arc",
        (
            "Character doesn't change - they change everyone around them. "
            "They enter a world that has forgotten truth and through steadfast "
            "demonstration of their values, bend the world to accommodate their truth."
        ),
        [
            "steadfast",
            "unchanging",
            "principled",
            "inspires",
            "influences",
            "demonstrates",
            "consistent",
            "unwavering",
            "catalyst",
            "transforms others",
        ],
        [
            "Core Truth (what they know that world forgot)",
            "Truth vs World (entering corrupt environment)",
            "Pressure Points (attempts to change them)",
            "Standing Firm (maintaining principles under pressure)",
            "The Demonstration (showing truth through action)",
            "First Convert (someone sees their truth)",
            "The Conversion Wave (others adopt worldview)",
            "Testing Crucibles (extreme tests of truth)",
            "Influence Ripples (change spreading outward)",
            "World Reformed (environment bent to their truth)",
        ],
        ["Ellen Ripley", "Paddington Bear", "Captain America", "Atticus Finch"],
        "How integrity changes the world",
    ),
    CharacterArcType(
        "Corruption Arc",
        (
            "Good person becomes monster through incremental moral compromises. "
            "Starting with noble intentions, they're seduced by power/fear into "
            "becoming everything they once fought against."
        ),
        [
            "corrupts",
            "seduced",
            "tempted",
            "compromises",
            "justifies",
            "transforms negatively",
            "becomes monster",
            "loses soul",
            "darkness",
        ],
        [
            "Innocence Established (who they were)",
            "The Wound Inflicted (breaking their faith)",
            "Noble Intention (initial good purpose)",
            "The Dark Invitation (offered power through corruption)",
            "First Sin (framed as necessity)",
            "The Mentor Figure (guide into darkness)",
            "Justified Atrocity (terrible but 'necessary')",
            "The Slippery Slope (each act requires worse)",
            "Moral Event Horizon (act they can't return from)",
            "Final Transformation (becoming the monster)",
        ],
        ["Michael Corleone", "Harvey Dent", "Smeagol/Gollum", "Carrie White"],
        "How good intentions pave the road to hell",
    ),
]


class TransformationMarker:
    """Represents a key transformation moment in a character's journey."""

    def __init__(
        self,
        name: str,
        description: str,
        arc_types: list[str],
        severity_if_missing: AnalysisSeverity,
        indicators: list[str],
    ):
        """Initialize a transformation marker.

        Args:
            name: Marker name
            description: What this marker represents
            arc_types: Which arc types this applies to
            severity_if_missing: How severe if this marker is missing
            indicators: Keywords/patterns that indicate this marker
        """
        self.name = name
        self.description = description
        self.arc_types = arc_types
        self.severity_if_missing = severity_if_missing
        self.indicators = indicators


# Key transformation markers to track
TRANSFORMATION_MARKERS = [
    TransformationMarker(
        "The Lie/False Belief",
        "Character's initial false belief that drives their flawed behavior",
        ["Positive Change Arc", "Negative Change Arc"],
        AnalysisSeverity.ERROR,
        ["believes", "thinks", "assumes", "fear", "flaw", "mistaken", "wrong about"],
    ),
    TransformationMarker(
        "The Wound",
        "Past trauma or experience that created the false belief",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.WARNING,
        ["past", "trauma", "hurt", "loss", "abandoned", "betrayed", "failed"],
    ),
    TransformationMarker(
        "The Want",
        "External goal the character pursues (what they think will make them happy)",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.ERROR,
        ["wants", "desires", "pursues", "goal", "seeks", "after", "needs to"],
    ),
    TransformationMarker(
        "The Need",
        "Internal truth the character must embrace for fulfillment",
        ["Positive Change Arc"],
        AnalysisSeverity.ERROR,
        ["needs to learn", "must understand", "truth is", "realize", "accept"],
    ),
    TransformationMarker(
        "Catalyst Crisis",
        "Event that forces character out of their comfort zone",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.ERROR,
        ["forced", "catalyst", "inciting", "disrupts", "changes everything", "must"],
    ),
    TransformationMarker(
        "Moment of Truth",
        "Character faces choice between old self and potential new self",
        ["Positive Change Arc", "Negative Change Arc"],
        AnalysisSeverity.ERROR,
        ["chooses", "decides", "moment of truth", "crossroads", "ultimatum"],
    ),
    TransformationMarker(
        "The Cost",
        "What the character must sacrifice for their transformation",
        ["Positive Change Arc", "Corruption Arc"],
        AnalysisSeverity.WARNING,
        ["sacrifice", "lose", "give up", "cost", "price", "let go"],
    ),
    TransformationMarker(
        "Core Truth",
        "The unchanging principle the character embodies",
        ["Flat Arc"],
        AnalysisSeverity.ERROR,
        ["believes in", "stands for", "principle", "truth", "values", "integrity"],
    ),
    TransformationMarker(
        "World's Lie",
        "The false belief the world around the character holds",
        ["Flat Arc"],
        AnalysisSeverity.WARNING,
        ["world believes", "everyone thinks", "corrupt", "forgotten", "lost"],
    ),
]


class CharacterAgencyPhase:
    """Represents a phase in character agency development."""

    def __init__(
        self,
        name: str,
        description: str,
        indicators: list[str],
        typical_percentage: float,
    ):
        """Initialize an agency phase.

        Args:
            name: Phase name
            description: Character behavior in this phase
            indicators: Keywords indicating this phase
            typical_percentage: Typical % of story in this phase
        """
        self.name = name
        self.description = description
        self.indicators = indicators
        self.typical_percentage = typical_percentage


# Character agency progression phases
AGENCY_PHASES = [
    CharacterAgencyPhase(
        "Victim Stage",
        "Things happen TO the character - 'Why is this happening to me?'",
        ["happens to", "victim", "powerless", "why me", "unfair", "can't"],
        0.15,
    ),
    CharacterAgencyPhase(
        "Survivor Stage",
        "Character reacts to survive - 'I'll do whatever it takes to get through'",
        ["survives", "reacts", "defends", "escapes", "endures", "gets through"],
        0.25,
    ),
    CharacterAgencyPhase(
        "Navigator Stage",
        "Character makes active choices - 'I choose my path'",
        ["decides", "chooses", "plans", "pursues", "takes action", "determines"],
        0.35,
    ),
    CharacterAgencyPhase(
        "Creator Stage",
        "Character shapes their world - 'I create my reality'",
        ["creates", "transforms", "influences", "changes", "shapes", "builds"],
        0.25,
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
        db_operations: Any,  # noqa: ARG002
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
        self,
        characters: list[dict],
        scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze the protagonist's character arc."""
        analyses: list[MentorAnalysis] = []

        # In real implementation, would identify protagonist from character data
        # For now, assume first character is protagonist
        if not characters:
            return analyses

        protagonist = characters[0]
        protagonist_id = protagonist.get("id")

        # Detect arc type based on character journey
        arc_type = self._detect_arc_type(protagonist, scenes)

        if arc_type:
            analyses.append(
                MentorAnalysis(
                    title=f"Protagonist Arc: {arc_type.name}",
                    description=(
                        f"{arc_type.description} "
                        f"Examples include: {', '.join(arc_type.examples[:2])}."
                    ),
                    severity=AnalysisSeverity.INFO,
                    scene_id=None,
                    character_id=protagonist_id,
                    element_id=None,
                    category="character_transformation",
                    mentor_name=self.name,
                    recommendations=[
                        f"Theme focus: {arc_type.thematic_focus}",
                        "Ensure all journey waypoints are present and earned",
                        "Character decisions should drive the transformation",
                    ],
                    metadata={
                        "arc_type": arc_type.name,
                        "journey_stages": arc_type.journey_pattern,
                        "protagonist_name": protagonist.get("name", "Unknown"),
                    },
                    confidence=0.85,
                )
            )

            # Check for missing journey waypoints
            missing_waypoints = self._check_journey_waypoints(
                protagonist, scenes, arc_type
            )
            if missing_waypoints:
                analyses.append(
                    MentorAnalysis(
                        title="Missing Arc Waypoints",
                        description=(
                            f"The {arc_type.name} is missing {len(missing_waypoints)} "
                            f"critical stages: {', '.join(missing_waypoints[:3])}"
                        ),
                        severity=AnalysisSeverity.WARNING,
                        scene_id=None,
                        character_id=protagonist_id,
                        element_id=None,
                        category="character_transformation",
                        mentor_name=self.name,
                        recommendations=[
                            f"Add scenes showing: {waypoint}"
                            for waypoint in missing_waypoints[:3]
                        ],
                        metadata={"missing_waypoints": missing_waypoints},
                    )
                )
        else:
            analyses.append(
                MentorAnalysis(
                    title="Unclear Character Arc",
                    description=(
                        "The protagonist's arc type is unclear. Strong character "
                        "arcs follow recognizable patterns of transformation."
                    ),
                    severity=AnalysisSeverity.ERROR,
                    scene_id=None,
                    character_id=protagonist_id,
                    element_id=None,
                    category="character_transformation",
                    mentor_name=self.name,
                    recommendations=[
                        "Clarify whether character changes (positive/negative arc)",
                        "Or if they change the world (flat arc)",
                        "Establish clear initial state and end state",
                        "Show transformation through actions, not just dialogue",
                    ],
                )
            )

        return analyses

    async def _analyze_want_vs_need(
        self,
        characters: list[dict],
        scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze character want vs need dynamics."""
        analyses = []

        for character in characters[:3]:  # Analyze top 3 characters
            character_id = character.get("id")
            character_name = character.get("name", "Unknown")

            # Detect want and need from character journey
            want_markers = self._find_transformation_marker(
                character, scenes, "The Want"
            )
            need_markers = self._find_transformation_marker(
                character, scenes, "The Need"
            )

            if want_markers and need_markers:
                analyses.append(
                    MentorAnalysis(
                        title=f"{character_name}: Clear Want vs Need",
                        description=(
                            f"{character_name} has both external want and internal "
                            "need "
                            "established, creating meaningful transformation potential."
                        ),
                        severity=AnalysisSeverity.INFO,
                        scene_id=None,
                        character_id=character_id,
                        element_id=None,
                        category="want_vs_need",
                        mentor_name=self.name,
                        recommendations=[
                            "Ensure want and need conflict for dramatic tension",
                            "Show character choosing between them at climax",
                            "Resolution should satisfy need, not necessarily want",
                        ],
                        metadata={
                            "has_want": True,
                            "has_need": True,
                            "character_name": character_name,
                        },
                        confidence=0.9,
                    )
                )
            elif want_markers and not need_markers:
                analyses.append(
                    MentorAnalysis(
                        title=f"{character_name}: Missing Internal Need",
                        description=(
                            f"{character_name} has clear external want but no defined "
                            "internal need. This limits transformation potential."
                        ),
                        severity=AnalysisSeverity.WARNING,
                        scene_id=None,
                        character_id=character_id,
                        element_id=None,
                        category="want_vs_need",
                        mentor_name=self.name,
                        recommendations=[
                            "Define what the character truly needs for fulfillment",
                            "The need should address their core flaw or wound",
                            "Need often opposes want (revenge vs forgiveness)",
                            "Show character gradually discovering their need",
                        ],
                        metadata={"has_want": True, "has_need": False},
                    )
                )
            elif not want_markers:
                analyses.append(
                    MentorAnalysis(
                        title=f"{character_name}: Unclear Motivation",
                        description=(
                            f"{character_name} lacks clear external want, making it "
                            "difficult for audience to invest in their journey."
                        ),
                        severity=AnalysisSeverity.ERROR,
                        scene_id=None,
                        character_id=character_id,
                        element_id=None,
                        category="want_vs_need",
                        mentor_name=self.name,
                        recommendations=[
                            "Establish concrete external goal early in the story",
                            "Make the want specific and visual (not abstract)",
                            "Show why this want matters deeply to character",
                            "Connect want to character's wound or backstory",
                        ],
                        metadata={"has_want": False, "has_need": bool(need_markers)},
                    )
                )

        return analyses

    async def _analyze_development_stages(
        self,
        characters: list[dict],
        scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze character development stages."""
        analyses = []

        for character in characters[:2]:  # Analyze main characters
            character_id = character.get("id")
            character_name = character.get("name", "Unknown")

            # Analyze transformation markers
            transformation_analysis = self._analyze_transformation_markers(
                character, scenes
            )
            if transformation_analysis:
                analyses.append(transformation_analysis)

            # Analyze character agency progression
            agency_distribution = self._analyze_character_agency(character, scenes)
            agency_analysis = self._create_agency_analysis(
                character_id, character_name, agency_distribution
            )
            if agency_analysis:
                analyses.append(agency_analysis)

            # Analyze internal vs external conflict
            conflict_data = self._analyze_internal_external_conflict(character, scenes)
            if conflict_data["intersection_points"]:
                analyses.append(
                    MentorAnalysis(
                        title=f"{character_name}: Conflict Integration",
                        description=(
                            "Character's internal and external conflicts effectively "
                            "intersect, creating layered dramatic tension."
                        ),
                        severity=AnalysisSeverity.INFO,
                        scene_id=None,
                        character_id=character_id,
                        element_id=None,
                        category="internal_conflict",
                        mentor_name=self.name,
                        recommendations=[
                            "Use external events to reveal internal struggles",
                            "Ensure internal growth enables external victory",
                            "Let character choices reflect internal change",
                        ],
                        metadata=conflict_data,
                        confidence=0.85,
                    )
                )

        return analyses

    def _analyze_transformation_markers(
        self, character: dict, scenes: list[dict]
    ) -> MentorAnalysis | None:
        """Analyze which transformation markers are present/missing."""
        character_id = character.get("id")
        character_name = character.get("name", "Unknown")

        # Check for key transformation markers
        missing_markers = []
        found_markers = []

        for marker in TRANSFORMATION_MARKERS:
            if self._find_transformation_marker(character, scenes, marker.name):
                found_markers.append(marker.name)
            else:
                missing_markers.append((marker.name, marker.severity_if_missing))

        # Report critical missing markers
        critical_missing = [
            name
            for name, severity in missing_markers
            if severity == AnalysisSeverity.ERROR
        ]

        if critical_missing:
            return MentorAnalysis(
                title=f"{character_name}: Missing Critical Arc Elements",
                description=(
                    f"Character arc lacks {len(critical_missing)} essential elements: "
                    f"{', '.join(critical_missing[:3])}. These are necessary for "
                    "a believable transformation."
                ),
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=character_id,
                element_id=None,
                category="character_transformation",
                mentor_name=self.name,
                recommendations=[
                    f"Establish {element} clearly in early scenes"
                    for element in critical_missing[:3]
                ],
                metadata={
                    "found_markers": found_markers,
                    "missing_markers": [name for name, _ in missing_markers],
                },
            )

        return None

    def _create_agency_analysis(
        self,
        character_id: UUID | None,
        character_name: str,
        agency_distribution: dict[str, float],
    ) -> MentorAnalysis | None:
        """Create analysis for character agency progression."""
        # Check if agency progression is balanced
        victim_percentage = agency_distribution.get("Victim Stage", 0)
        creator_percentage = agency_distribution.get("Creator Stage", 0)

        if victim_percentage > 0.3:
            return MentorAnalysis(
                title=f"{character_name}: Excessive Victim Phase",
                description=(
                    f"Character spends {victim_percentage * 100:.0f}% as victim. "
                    "This reduces audience engagement and character appeal."
                ),
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=character_id,
                element_id=None,
                category="character_transformation",
                mentor_name=self.name,
                recommendations=[
                    "Move character to active choices earlier in story",
                    "Show character taking initiative, even if failing",
                    "Reduce passive 'things happen to me' scenes",
                    "Give character small victories to build agency",
                ],
                metadata={"agency_distribution": agency_distribution},
            )
        if creator_percentage >= 0.2:
            return MentorAnalysis(
                title=f"{character_name}: Strong Agency Arc",
                description=(
                    "Character progresses from victim to creator, demonstrating "
                    "clear growth in personal agency and empowerment."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=character_id,
                element_id=None,
                category="character_transformation",
                mentor_name=self.name,
                metadata={"agency_distribution": agency_distribution},
                confidence=0.9,
            )

        return None

    async def _analyze_supporting_arcs(
        self,
        supporting_characters: list[dict],
        scenes: list[dict],
    ) -> list[MentorAnalysis]:
        """Analyze supporting character arcs."""
        analyses = []

        for character in supporting_characters[:3]:  # Top 3 supporting
            character_id = character.get("id")
            character_name = character.get("name", "Unknown")

            # Detect if character has any arc
            arc_type = self._detect_arc_type(character, scenes)

            if arc_type:
                analyses.append(
                    MentorAnalysis(
                        title=f"{character_name}: Supporting Arc Present",
                        description=(
                            f"{character_name} has a {arc_type.name} that enriches "
                            "the main story and provides thematic resonance."
                        ),
                        severity=AnalysisSeverity.INFO,
                        scene_id=None,
                        character_id=character_id,
                        element_id=None,
                        category="character_transformation",
                        mentor_name=self.name,
                        recommendations=[
                            "Ensure supporting arc doesn't overshadow protagonist",
                            "Use arc to reflect or contrast main theme",
                            "Keep arc resolution tied to protagonist's journey",
                        ],
                        metadata={
                            "character_name": character_name,
                            "arc_type": arc_type.name,
                            "is_supporting": True,
                        },
                        confidence=0.8,
                    )
                )
            else:
                # Check if this character needs an arc
                scene_count = len(
                    [s for s in scenes if character_id in s.get("character_ids", [])]
                )
                if scene_count > 5:  # Significant presence
                    analyses.append(
                        MentorAnalysis(
                            title=f"{character_name}: Flat Supporting Character",
                            description=(
                                f"{character_name} appears in {scene_count} scenes but "
                                "shows no development. Consider adding a mini-arc."
                            ),
                            severity=AnalysisSeverity.SUGGESTION,
                            scene_id=None,
                            character_id=character_id,
                            element_id=None,
                            category="character_transformation",
                            mentor_name=self.name,
                            recommendations=[
                                "Give character a small want that evolves",
                                "Show how protagonist's journey affects them",
                                "Or establish them as intentionally flat (mentor/sage)",
                                "Even small changes add depth",
                            ],
                            metadata={
                                "scene_count": scene_count,
                                "has_arc": False,
                            },
                        )
                    )

        return analyses

    async def _analyze_relationships(
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
            mentor_analysis = self._analyze_mentor_relationships(
                protagonist, characters[1:], scenes
            )
            if mentor_analysis:
                analyses.append(mentor_analysis)

            # Analyze shadow/antagonist relationships
            shadow_analysis = self._analyze_shadow_relationships(
                protagonist, characters[1:], scenes
            )
            if shadow_analysis:
                analyses.append(shadow_analysis)

            # Analyze romantic relationships
            romance_analysis = self._analyze_romance_dynamics(
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
                    mentor_name=self.name,
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

    def _analyze_mentor_relationships(
        self,
        protagonist: dict,  # noqa: ARG002
        other_characters: list[dict],  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> MentorAnalysis | None:
        """Analyze mentor-student dynamics."""
        # Would identify mentor figures and analyze their impact
        # Placeholder implementation
        return None

    def _analyze_shadow_relationships(
        self,
        protagonist: dict,  # noqa: ARG002
        other_characters: list[dict],  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> MentorAnalysis | None:
        """Analyze shadow/antagonist relationships."""
        # Would identify shadow characters who reflect what protagonist could become
        # Placeholder implementation
        return None

    def _analyze_romance_dynamics(
        self,
        protagonist: dict,  # noqa: ARG002
        other_characters: list[dict],  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> MentorAnalysis | None:
        """Analyze romantic relationships as character growth catalysts."""
        # Would analyze how romance mirrors internal journey
        # Placeholder implementation
        return None

    def _calculate_score(self, analyses: list[MentorAnalysis]) -> float:
        """Calculate overall character arc score."""
        if not analyses:
            return 0.0

        # Start with perfect score and deduct for issues
        score = 100.0

        # Count critical elements
        arc_elements = {
            "has_clear_arc_type": False,
            "has_want_vs_need": False,
            "has_transformation_markers": False,
            "has_agency_progression": False,
            "has_relationship_dynamics": False,
            "has_complete_journey": False,
        }

        # Check which elements are present
        for analysis in analyses:
            if (
                "Arc Type" in analysis.title
                and analysis.severity == AnalysisSeverity.INFO
            ):
                arc_elements["has_clear_arc_type"] = True
            elif (
                "Want vs Need" in analysis.title
                and analysis.severity == AnalysisSeverity.INFO
            ):
                arc_elements["has_want_vs_need"] = True
            elif (
                "transformation" in analysis.category
                and analysis.severity == AnalysisSeverity.INFO
            ):
                arc_elements["has_transformation_markers"] = True
            elif "Strong Agency Arc" in analysis.title:
                arc_elements["has_agency_progression"] = True
            elif "Relationship Web" in analysis.title:
                arc_elements["has_relationship_dynamics"] = True
            elif "Complete" in analysis.title and "Journey" in analysis.title:
                arc_elements["has_complete_journey"] = True

        # Deduct for missing critical elements
        element_weights = {
            "has_clear_arc_type": 15,
            "has_want_vs_need": 15,
            "has_transformation_markers": 10,
            "has_agency_progression": 10,
            "has_relationship_dynamics": 5,
            "has_complete_journey": 10,
        }

        for element, has_it in arc_elements.items():
            if not has_it:
                score -= element_weights.get(element, 0)

        # Additional deductions for errors and warnings
        error_count = sum(1 for a in analyses if a.severity == AnalysisSeverity.ERROR)
        warning_count = sum(
            1 for a in analyses if a.severity == AnalysisSeverity.WARNING
        )
        suggestion_count = sum(
            1 for a in analyses if a.severity == AnalysisSeverity.SUGGESTION
        )

        score -= error_count * 10
        score -= warning_count * 5
        score -= suggestion_count * 2

        # Bonus points for exceptional elements
        info_analyses = [a for a in analyses if a.severity == AnalysisSeverity.INFO]
        high_confidence = sum(
            1 for a in info_analyses if a.confidence and a.confidence >= 0.9
        )

        if high_confidence >= 3:
            score += 5  # Bonus for multiple high-confidence positive findings

        return max(0.0, min(100.0, score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], character_count: int
    ) -> str:
        """Generate summary of character arc analysis."""
        error_count = len([a for a in analyses if a.severity == AnalysisSeverity.ERROR])
        warning_count = len(
            [a for a in analyses if a.severity == AnalysisSeverity.WARNING]
        )
        info_count = len([a for a in analyses if a.severity == AnalysisSeverity.INFO])

        # Detect arc types found
        arc_types_found = set()
        for analysis in analyses:
            if "Arc:" in analysis.title:
                for arc_type in CHARACTER_ARC_TYPES:
                    if arc_type.name in analysis.title:
                        arc_types_found.add(arc_type.name)

        summary_parts = [
            f"Character arc analysis complete for {character_count} characters."
        ]

        if arc_types_found:
            summary_parts.append(f"Found {', '.join(arc_types_found)} arc type(s).")

        if error_count == 0 and warning_count == 0:
            summary_parts.append(
                "Characters demonstrate strong, well-structured transformation arcs "
                "with clear want/need dynamics and compelling agency progression."
            )
        elif error_count > 0:
            summary_parts.append(
                f"Critical issues found: {error_count} missing arc elements that "
                "need attention for believable character transformation."
            )
        else:
            summary_parts.append(
                f"Good foundation with {info_count} positive elements, but "
                f"{warning_count} areas could strengthen character development."
            )

        # Specific insights
        has_agency_issue = any("Excessive Victim" in a.title for a in analyses)
        has_strong_agency = any("Strong Agency Arc" in a.title for a in analyses)

        if has_agency_issue:
            summary_parts.append(
                "Character agency needs work - too much time in passive/victim mode."
            )
        elif has_strong_agency:
            summary_parts.append(
                "Excellent character agency progression from victim to creator."
            )

        # Arc completeness
        missing_waypoints = any("Missing Arc Waypoints" in a.title for a in analyses)
        if missing_waypoints:
            summary_parts.append(
                "Key waypoints missing - arc may feel rushed or unearned."
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

    def _detect_arc_type(
        self,
        character: dict,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> CharacterArcType | None:
        """Detect the character's arc type based on their journey."""
        # In real implementation, would analyze character's scenes and dialogue
        # to detect transformation patterns and match to arc types
        # For now, return a placeholder

        # Would analyze character's journey through scenes
        # Look for arc type indicators in dialogue and actions
        # Match patterns to CHARACTER_ARC_TYPES

        # Placeholder - would be sophisticated analysis
        return CHARACTER_ARC_TYPES[0]  # Positive Change Arc as default

    def _check_journey_waypoints(
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

    def _find_transformation_marker(
        self,
        character: dict,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
        marker_name: str,
    ) -> list[dict]:
        """Find scenes containing a specific transformation marker."""
        # Would search character's scenes for transformation marker indicators
        # Return scenes that contain the marker

        marker = next(
            (m for m in TRANSFORMATION_MARKERS if m.name == marker_name), None
        )
        if not marker:
            return []

        # Placeholder - would search for marker indicators in scenes
        # involving this character
        return []  # Would return actual scene matches

    def _analyze_character_agency(
        self,
        character: dict,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> dict[str, float]:
        """Analyze character's agency progression through the story."""
        agency_distribution = {phase.name: 0.0 for phase in AGENCY_PHASES}

        # Would analyze character's actions in each scene
        # Categorize into agency phases
        # Calculate percentage of story in each phase

        # Placeholder distribution
        agency_distribution["Victim Stage"] = 0.15
        agency_distribution["Survivor Stage"] = 0.25
        agency_distribution["Navigator Stage"] = 0.35
        agency_distribution["Creator Stage"] = 0.25

        return agency_distribution

    def _analyze_internal_external_conflict(
        self,
        character: dict,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Analyze how internal and external conflicts intersect."""
        # Would identify internal conflicts (fears, flaws, beliefs)
        # and external conflicts (obstacles, antagonists, challenges)
        # Then analyze how they intersect and reinforce each other

        return {
            "internal_conflicts": ["self-doubt", "fear of failure"],
            "external_conflicts": ["antagonist opposition", "time pressure"],
            "intersection_points": ["external pressure reveals internal weakness"],
            "conflict_escalation": True,
        }
