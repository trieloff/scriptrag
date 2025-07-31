"""Save the Cat Mentor Implementation.

This mentor analyzes screenplays based on Blake Snyder's "Save the Cat!"
beat sheet methodology. It identifies key story beats and provides feedback
on story structure, pacing, and adherence to the Save the Cat framework.

The mentor analyzes:
1. 15-beat structure adherence
2. Page count timing for each beat
3. Character arc progression
4. Theme and transformation
5. Catalyst and fun & games effectiveness
"""

from collections.abc import Callable
from datetime import UTC, datetime
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


class SaveTheCatBeat:
    """Represents a Save the Cat story beat."""

    def __init__(
        self,
        name: str,
        description: str,
        page_range: tuple[int, int],
        keywords: list[str],
        required: bool = True,
    ):
        """Initialize a Save the Cat beat.

        Args:
            name: Beat name
            description: Beat description
            page_range: Expected page range for this beat
            keywords: Keywords to look for in scenes
            required: Whether this beat is required
        """
        self.name = name
        self.description = description
        self.page_range = page_range  # (min_page, max_page) for 110-page script
        self.keywords = keywords
        self.required = required


# Save the Cat 15-beat structure for feature films
SAVE_THE_CAT_BEATS = [
    SaveTheCatBeat(
        "Opening Image",
        (
            "A visual that represents the struggle & tone of the story. "
            "A snapshot of the main character's problem, before the adventure begins."
        ),
        (1, 1),
        ["opening", "first scene", "establishing", "tone", "visual"],
        True,
    ),
    SaveTheCatBeat(
        "Theme Stated",
        (
            "What your story is about; the message, the truth. Usually, it is spoken "
            "to the main character or in their presence, but they don't understand "
            "the truth... not until they have some life experience."
        ),
        (1, 5),
        ["theme", "message", "lesson", "truth", "meaning"],
        True,
    ),
    SaveTheCatBeat(
        "Set-Up",
        (
            "Expand on the 'before' snapshot. Present the main character's world "
            "as it is, and what is missing in their life."
        ),
        (1, 10),
        ["introduction", "world", "character", "normal life", "routine"],
        True,
    ),
    SaveTheCatBeat(
        "Catalyst",
        (
            "The moment where life as it is changes. It is the telegram, the act of "
            "catching your loved-one cheating, allowing a monster on-board the ship, "
            "meeting the true love of your life, etc. The 'before' world is no more, "
            "change is underway."
        ),
        (12, 12),
        ["inciting incident", "call to adventure", "catalyst", "change", "disruption"],
        True,
    ),
    SaveTheCatBeat(
        "Debate",
        (
            "But change is scary and for a moment, or a brief number of moments, "
            "the main character doubts the journey they must take. Can I face this "
            "challenge? Do I have what it takes? Should I go at all?"
        ),
        (12, 25),
        ["doubt", "hesitation", "fear", "uncertainty", "should I"],
        True,
    ),
    SaveTheCatBeat(
        "Break Into Two",
        (
            "The main character makes a choice and the journey begins. We leave the "
            "'Thesis' world and enter the upside-down, opposite world of Act Two."
        ),
        (25, 25),
        ["decision", "choice", "journey begins", "act two", "new world"],
        True,
    ),
    SaveTheCatBeat(
        "B Story",
        (
            "This is when a new character or characters are introduced. Often love "
            "interests and/or sidekicks. The B Story is discussed throughout script."
        ),
        (30, 30),
        ["subplot", "love interest", "mentor", "helper", "secondary character"],
        True,
    ),
    SaveTheCatBeat(
        "Fun and Games",
        (
            "This is when Craig gets to beat up thugs in Chinatown, when Indiana Jones "
            "tries to trap-proof his way to the Ark of the Covenant, when detective "
            "finds the most clues and dodges the most bullets. This is when the main "
            "character explores the new world and the audience is entertained by the "
            "premise they have been promised."
        ),
        (30, 55),
        ["fun", "entertainment", "premise", "exploration", "adventure"],
        True,
    ),
    SaveTheCatBeat(
        "Midpoint",
        (
            "Dependent upon the story, this moment is when everything is 'great' or "
            "everything is 'awful'. The main character either gets everything they "
            "want ('great') or doesn't get what they think they want at all "
            "('awful'). But not what they 'need'."
        ),
        (55, 55),
        ["midpoint", "false victory", "false defeat", "turning point", "shift"],
        True,
    ),
    SaveTheCatBeat(
        "Bad Guys Close In",
        (
            "Doubt, jealousy, fear, foes both physical and emotional regroup to defeat "
            "the main character's goal, and their 'want' vs. their 'need' is no longer "
            "enough."
        ),
        (55, 75),
        ["obstacles", "opposition", "enemies", "pressure", "complications"],
        True,
    ),
    SaveTheCatBeat(
        "All Is Lost",
        (
            "The opposite moment from the Midpoint: 'awful' or 'great'. The moment "
            "that the main character realizes they've lost everything they gained, or "
            "everything they now have has no meaning. The initial goal now looks even "
            "more impossible than before. And here, something or someone dies. It can "
            "be physical or emotional, but the death of something old makes way for "
            "something new to be born."
        ),
        (75, 75),
        ["all is lost", "dark moment", "death", "lowest point", "despair"],
        True,
    ),
    SaveTheCatBeat(
        "Dark Night of the Soul",
        (
            "The main character hits bottom, and wallows in hopelessness. The Why hast "
            "thou forsaken me, Lord? moment. Mourning the loss of what has 'died' - "
            "the dream, the goal, the mentor character, the love of your life, etc. "
            "But, you must fall completely before you can pick yourself back up and "
            "try again."
        ),
        (75, 85),
        ["despair", "hopelessness", "mourning", "rock bottom", "reflection"],
        True,
    ),
    SaveTheCatBeat(
        "Break Into Three",
        (
            "Thanks to a fresh idea, new inspiration, or last-minute Thematic advice "
            "from the B Story (usually the love interest), the main character chooses "
            "to try again."
        ),
        (85, 85),
        ["revelation", "inspiration", "choice", "act three", "final attempt"],
        True,
    ),
    SaveTheCatBeat(
        "Finale",
        (
            "This time around, the main character incorporates the Theme - the nugget "
            "of truth that now makes sense to them - into their fight for the goal "
            "because they have experience from A Story and context from B Story. "
            "Act Three is about Synthesis!"
        ),
        (85, 110),
        ["finale", "climax", "synthesis", "resolution", "final battle"],
        True,
    ),
    SaveTheCatBeat(
        "Final Image",
        (
            "opposite of Opening Image, proving, visually, that a change has occurred "
            "within the character."
        ),
        (110, 110),
        ["final image", "ending", "transformation", "change", "resolution"],
        True,
    ),
]


class SaveTheCatMentor(BaseMentor):
    """Save the Cat mentor for screenplay structure analysis.

    This mentor analyzes screenplays according to Blake Snyder's Save the Cat!
    beat sheet methodology, providing feedback on story structure, pacing,
    and adherence to the 15-beat framework.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the Save the Cat mentor.

        Args:
            config: Optional configuration including:
                - target_page_count: Expected total pages (default: 110)
                - tolerance: Page tolerance for beat timing (default: 5)
                - strict_mode: Whether to require all beats (default: False)
        """
        super().__init__(config)
        self._version = "1.0.0"

        # Configuration
        self.target_page_count = self.config.get("target_page_count", 110)
        self.tolerance = self.config.get("tolerance", 5)
        self.strict_mode = self.config.get("strict_mode", False)

    @property
    def name(self) -> str:
        """Unique name identifier for this mentor."""
        return "save_the_cat"

    @property
    def description(self) -> str:
        """Human-readable description of what this mentor analyzes."""
        return (
            "Analyzes screenplay structure based on Blake Snyder's Save the Cat! "
            "15-beat methodology, checking story beats, pacing, and character arcs."
        )

    @property
    def mentor_type(self) -> MentorType:
        """Type category this mentor belongs to."""
        return MentorType.STORY_STRUCTURE

    @property
    def categories(self) -> list[str]:
        """Categories of analysis this mentor provides."""
        return ["beat_sheet", "story_structure", "pacing", "character_arc", "theme"]

    async def analyze_script(
        self,
        script_id: UUID,
        db_operations: Any,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> MentorResult:
        """Analyze a script using Save the Cat methodology.

        Args:
            script_id: UUID of the script to analyze
            db_operations: Database operations interface
            progress_callback: Optional progress callback

        Returns:
            Complete Save the Cat analysis result
        """
        start_time = datetime.now(UTC)
        analyses: list[MentorAnalysis] = []

        try:
            if progress_callback:
                progress_callback(0.1, "Loading script data...")

            # Get script and scenes
            script_data = await self._get_script_data(script_id, db_operations)
            if not script_data:
                raise ValueError(f"Script {script_id} not found")

            scenes = script_data["scenes"]
            total_pages = self._estimate_total_pages(scenes)

            if progress_callback:
                progress_callback(0.3, "Analyzing story structure...")

            # Analyze each Save the Cat beat
            beat_analyses = await self._analyze_beats(scenes, total_pages)
            analyses.extend(beat_analyses)

            if progress_callback:
                progress_callback(0.6, "Checking pacing and timing...")

            # Analyze overall structure and pacing
            structure_analyses = await self._analyze_structure(scenes, total_pages)
            analyses.extend(structure_analyses)

            if progress_callback:
                progress_callback(0.8, "Analyzing character arc...")

            # Analyze character development
            character_analyses = await self._analyze_character_arc(script_data)
            analyses.extend(character_analyses)

            if progress_callback:
                progress_callback(0.9, "Generating summary...")

            # Generate overall score and summary
            score = self._calculate_score(analyses)
            summary = self._generate_summary(analyses, total_pages)

            execution_time = int(
                (datetime.now(UTC) - start_time).total_seconds() * 1000
            )

            if progress_callback:
                progress_callback(1.0, "Analysis complete")

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
            logger.error(f"Save the Cat analysis failed for script {script_id}: {e}")

            # Return error result
            error_analysis = MentorAnalysis(
                title="Analysis Error",
                description=f"Save the Cat analysis failed: {e!s}",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="analysis_error",
                mentor_name=self.name,
            )

            execution_time = int(
                (datetime.now(UTC) - start_time).total_seconds() * 1000
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
            # - Characters

            # Placeholder - would be replaced with actual database queries
            return {
                "script_id": script_id,
                "title": "Sample Script",
                "scenes": [],  # Would contain actual scene data
                "characters": [],  # Would contain character data
                "total_pages": 110,
            }

        except Exception as e:
            logger.error(f"Failed to get script data for {script_id}: {e}")
            return None

    def _estimate_total_pages(self, scenes: list[dict]) -> int:
        """Estimate total page count from scenes."""
        # Rough estimation: 1 page per minute, 1 minute per page of dialogue/action
        # This would be more sophisticated in real implementation
        return max(int(self.target_page_count), len(scenes))  # Placeholder

    async def _analyze_beats(
        self, scenes: list[dict], total_pages: int
    ) -> list[MentorAnalysis]:
        """Analyze Save the Cat beats in the script."""
        analyses = []

        # Scale beat page ranges to actual script length
        page_scale = total_pages / self.target_page_count

        for beat in SAVE_THE_CAT_BEATS:
            # Scale the expected page range
            expected_start = int(beat.page_range[0] * page_scale)
            expected_end = int(beat.page_range[1] * page_scale)

            # Look for this beat in the script
            found_scenes = self._find_beat_in_scenes(
                beat, scenes, expected_start, expected_end
            )

            if found_scenes:
                # Beat found - analyze timing and content
                analysis = self._analyze_beat_timing(
                    beat, found_scenes, expected_start, expected_end
                )
                if analysis:
                    analyses.append(analysis)
            else:
                # Beat missing
                severity = (
                    AnalysisSeverity.ERROR
                    if beat.required
                    else AnalysisSeverity.WARNING
                )

                analyses.append(
                    MentorAnalysis(
                        title=f"Missing Beat: {beat.name}",
                        description=(
                            f"The '{beat.name}' beat was not found in expected "
                            f"location (pages {expected_start}-{expected_end}). "
                            f"{beat.description}"
                        ),
                        severity=severity,
                        scene_id=None,
                        character_id=None,
                        element_id=None,
                        category="beat_sheet",
                        mentor_name=self.name,
                        recommendations=[
                            (
                                f"Add a scene around page {expected_start} that "
                                f"establishes: {beat.description}"
                            ),
                            f"Look for keywords: {', '.join(beat.keywords[:3])}",
                            "Consider how this beat serves the overall story structure",
                        ],
                    )
                )

        return analyses

    def _find_beat_in_scenes(
        self,
        _beat: SaveTheCatBeat,
        _scenes: list[dict],
        _expected_start: int,
        _expected_end: int,
    ) -> list[dict]:
        """Find scenes that likely contain the specified beat."""
        # This would analyze scene content for beat keywords and positioning
        # Placeholder implementation
        return []

    def _analyze_beat_timing(
        self,
        _beat: SaveTheCatBeat,
        _scenes: list[dict],
        _expected_start: int,
        _expected_end: int,
    ) -> MentorAnalysis | None:
        """Analyze the timing of a found beat."""
        # Placeholder for beat timing analysis
        return None

    async def _analyze_structure(
        self,
        _scenes: list[dict],
        total_pages: int,
    ) -> list[MentorAnalysis]:
        """Analyze overall story structure."""
        analyses = []

        # Check three-act structure
        act_1_end = total_pages * 0.25
        act_2_end = total_pages * 0.75

        analyses.append(
            MentorAnalysis(
                title="Three-Act Structure",
                description=(
                    f"Script follows three-act structure with Act I ending around "
                    f"page {act_1_end:.0f}, Act II ending around page {act_2_end:.0f}"
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="story_structure",
                mentor_name=self.name,
                recommendations=[
                    "Ensure major plot points align with act breaks",
                    "Check that each act serves its structural purpose",
                ],
            )
        )

        return analyses

    async def _analyze_character_arc(
        self,
        _script_data: dict,
    ) -> list[MentorAnalysis]:
        """Analyze character development and arcs."""
        analyses = []

        # Placeholder character arc analysis
        analyses.append(
            MentorAnalysis(
                title="Character Arc Analysis",
                description=(
                    "Character transformation analysis based on Save the Cat principles"
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_arc",
                mentor_name=self.name,
                recommendations=[
                    "Ensure protagonist has clear want vs. need",
                    "Show character growth through actions, not just dialogue",
                    "Connect character arc to thematic elements",
                ],
            )
        )

        return analyses

    def _calculate_score(self, analyses: list[MentorAnalysis]) -> float:
        """Calculate overall Save the Cat score."""
        if not analyses:
            return 0.0

        # Weight different severities
        severity_weights = {
            AnalysisSeverity.ERROR: -10,
            AnalysisSeverity.WARNING: -5,
            AnalysisSeverity.SUGGESTION: -2,
            AnalysisSeverity.INFO: 1,
        }

        total_score = 50  # Base score
        for analysis in analyses:
            total_score += severity_weights.get(analysis.severity, 0)

        return max(0.0, min(100.0, total_score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], total_pages: int
    ) -> str:
        """Generate summary of the Save the Cat analysis."""
        error_count = len([a for a in analyses if a.severity == AnalysisSeverity.ERROR])
        warning_count = len(
            [a for a in analyses if a.severity == AnalysisSeverity.WARNING]
        )

        summary_parts = [
            f"Save the Cat analysis of {total_pages}-page screenplay completed.",
            (
                f"Found {error_count} structural issues and {warning_count} "
                "areas for improvement."
            ),
        ]

        if error_count == 0:
            summary_parts.append(
                "Script follows Save the Cat beat sheet structure well."
            )
        else:
            summary_parts.append(
                "Several key story beats need attention for optimal structure."
            )

        return " ".join(summary_parts)

    def validate_config(self) -> bool:
        """Validate the mentor's configuration."""
        try:
            page_count = self.config.get("target_page_count", 110)
            tolerance = self.config.get("tolerance", 5)

            if not isinstance(page_count, int) or page_count < 30:
                return False

            return isinstance(tolerance, int) and tolerance >= 0

        except Exception:
            return False

    def get_config_schema(self) -> dict[str, Any]:
        """Get the configuration schema for this mentor."""
        return {
            "type": "object",
            "properties": {
                "target_page_count": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 200,
                    "default": 110,
                    "description": "Expected total page count for the screenplay",
                },
                "tolerance": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 20,
                    "default": 5,
                    "description": "Page tolerance for beat timing (pages)",
                },
                "strict_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to require all beats to be present",
                },
            },
            "additionalProperties": False,
        }
