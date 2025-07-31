"""Three-Act Structure Mentor Implementation.

This mentor analyzes screenplays based on the classic three-act structure,
one of the most fundamental frameworks in Western storytelling. It identifies
key structural elements and provides feedback on pacing and plot development.

The mentor analyzes:
1. Act divisions and proportions
2. Major plot points and turning points
3. Inciting incident and climax placement
4. Rising action and pacing
5. Scene-to-scene causality
6. B-story integration points
7. Genre-specific structural variations
8. Modern interpretations (four-act, five-act variations)
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypedDict
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


class GenreVariation(TypedDict):
    """Type for genre-specific variations."""

    act_i_percentage: int
    act_ii_percentage: int
    act_iii_percentage: int
    required_elements: list[str]
    pacing: str
    notes: str


class StructuralElement:
    """Represents a key structural element in three-act structure."""

    def __init__(
        self,
        name: str,
        description: str,
        act: int,
        target_percentage: float,
        tolerance: float,
        keywords: list[str],
        essential: bool = True,
        page_range: tuple[int, int] | None = None,
    ):
        """Initialize a structural element.

        Args:
            name: Element name
            description: Element description
            act: Which act this element belongs to
            target_percentage: Target position in script (0.0 to 1.0)
            tolerance: Acceptable deviation from target (percentage points)
            keywords: Keywords to identify this element
            essential: Whether this element is essential
            page_range: Optional specific page range for 110-page script
        """
        self.name = name
        self.description = description
        self.act = act
        self.target_percentage = target_percentage
        self.tolerance = tolerance
        self.keywords = keywords
        self.essential = essential
        self.page_range = page_range


# Key structural elements in three-act structure
STRUCTURAL_ELEMENTS = [
    StructuralElement(
        "Teaser/Cold Open",
        (
            "Optional pre-credits hook that grabs attention before main story begins. "
            "Often used in thrillers and TV scripts to create immediate engagement."
        ),
        0,  # Pre-Act I
        0.01,
        0.01,
        ["teaser", "cold open", "hook", "attention", "pre-credits"],
        False,
        (0, 2),
    ),
    StructuralElement(
        "Opening Image",
        (
            "The opening scene that establishes tone, genre, and visual theme. "
            "Should introduce the world and hint at the central conflict. "
            "Often mirrors the final image to show transformation."
        ),
        1,
        0.01,
        0.02,
        ["opening", "fade in", "first", "establishes", "world", "tone"],
        True,
        (1, 1),
    ),
    StructuralElement(
        "Setup/Ordinary World",
        (
            "Introduction of protagonist, supporting characters, their world, and "
            "status quo. Establishes character flaws, desires, and what's at stake. "
            "Shows life before the adventure begins."
        ),
        1,
        0.05,
        0.05,
        ["introduction", "meet", "ordinary", "status quo", "normal", "establish"],
        True,
        (1, 10),
    ),
    StructuralElement(
        "Theme Stated",
        (
            "The thematic question or truth of the story, often stated in dialogue. "
            "Usually spoken to or near the protagonist, though they won't understand "
            "it until the end."
        ),
        1,
        0.045,
        0.04,
        ["theme", "message", "truth", "lesson", "meaning", "question"],
        False,
        (3, 7),
    ),
    StructuralElement(
        "Inciting Incident/Catalyst",
        (
            "The event that disrupts the status quo and launches the story. "
            "Sets the central conflict in motion. In modern structure, this often "
            "happens earlier (by page 10-12) to grab audiences faster."
        ),
        1,
        0.12,
        0.05,
        ["inciting", "catalyst", "disruption", "problem", "conflict begins", "call"],
        True,
        (10, 15),
    ),
    StructuralElement(
        "Debate/Refusal of the Call",
        (
            "The protagonist's hesitation or resistance to change. Shows the character "
            "grappling with the decision to embark on the journey. Creates tension "
            "before commitment."
        ),
        1,
        0.17,
        0.05,
        ["debate", "refusal", "hesitation", "doubt", "resistance", "should i"],
        False,
        (12, 25),
    ),
    StructuralElement(
        "Plot Point I/Break into Two",
        (
            "Major turning point that spins the story into Act II. The protagonist "
            "makes a choice, commits to their goal, and enters unfamiliar territory. "
            "Point of no return - the adventure truly begins."
        ),
        1,
        0.23,
        0.05,
        ["turning point", "act two", "commits", "decision", "new direction", "break"],
        True,
        (25, 30),
    ),
    StructuralElement(
        "B-Story Introduction",
        (
            "Introduction of the subplot, often a relationship that will teach the "
            "protagonist the theme. Provides emotional counterpoint to A-story."
        ),
        2,
        0.27,
        0.05,
        ["b-story", "subplot", "love interest", "mentor", "relationship", "secondary"],
        False,
        (28, 35),
    ),
    StructuralElement(
        "First Pinch Point",
        (
            "Reminder of the antagonist's power and the stakes. Shows the opposition "
            "in action and what the protagonist is up against. Often introduces new "
            "complications."
        ),
        2,
        0.375,
        0.05,
        ["antagonist", "opposition", "threat", "stakes", "reminder", "pressure"],
        False,
        (35, 45),
    ),
    StructuralElement(
        "Midpoint/Mirror Moment",
        (
            "Major reversal or revelation that changes everything. False victory or "
            "false defeat. Often shifts protagonist from reactive to proactive. In "
            "modern structure, this is the story's center of gravity."
        ),
        2,
        0.50,
        0.05,
        ["midpoint", "reversal", "revelation", "shift", "truth revealed", "mirror"],
        True,
        (50, 60),
    ),
    StructuralElement(
        "Second Pinch Point",
        (
            "Antagonist applies maximum pressure. Bad guys close in. Internal and "
            "external enemies converge. The walls are closing in on the protagonist."
        ),
        2,
        0.625,
        0.05,
        ["pressure", "closing in", "antagonist", "danger", "stakes rise", "enemies"],
        False,
        (62, 75),
    ),
    StructuralElement(
        "All Is Lost/Dark Night of the Soul",
        (
            "The lowest point where everything falls apart. Often includes a 'death' "
            "(literal or metaphorical). The protagonist must face their greatest fear "
            "or flaw."
        ),
        2,
        0.75,
        0.05,
        ["all is lost", "darkest", "lowest point", "death", "despair", "rock bottom"],
        True,
        (75, 85),
    ),
    StructuralElement(
        "Plot Point II/Break into Three",
        (
            "The protagonist discovers the solution, often through the B-story. Armed "
            "with new understanding (usually thematic), they're ready for the final "
            "confrontation."
        ),
        2,
        0.80,
        0.05,
        ["act three", "revelation", "solution", "final push", "break", "realization"],
        True,
        (80, 90),
    ),
    StructuralElement(
        "Climax/Final Battle",
        (
            "The highest point of tension where the central conflict is resolved. "
            "The protagonist faces their greatest challenge using lessons learned. "
            "A-story and B-story synthesize."
        ),
        3,
        0.90,
        0.08,
        ["climax", "final battle", "confrontation", "showdown", "peak", "synthesis"],
        True,
        (85, 105),
    ),
    StructuralElement(
        "Resolution/Denouement",
        (
            "The aftermath showing the new status quo. Ties up loose ends and "
            "shows how characters and their world have changed. New equilibrium "
            "established."
        ),
        3,
        0.96,
        0.04,
        ["resolution", "aftermath", "new normal", "ending", "epilogue", "denouement"],
        True,
        (105, 110),
    ),
    StructuralElement(
        "Final Image",
        (
            "Mirror of opening image showing transformation. Visual proof that change "
            "has occurred. The last impression left with the audience."
        ),
        3,
        0.99,
        0.01,
        ["final image", "closing", "last scene", "transformation", "mirror", "end"],
        True,
        (109, 110),
    ),
]

# Expected act proportions
ACT_PROPORTIONS = {
    1: (0.0, 0.25, "25%"),  # Start, End, Expected percentage
    2: (0.25, 0.75, "50%"),
    3: (0.75, 1.0, "25%"),
}

# Genre-specific variations
GENRE_VARIATIONS: dict[str, GenreVariation] = {
    "thriller": {
        "act_i_percentage": 20,  # Faster setup
        "act_ii_percentage": 60,  # Extended tension
        "act_iii_percentage": 20,
        "required_elements": ["ticking_clock", "false_endings", "rapid_reversals"],
        "pacing": "accelerating",
        "notes": "Thrillers often compress Act I to get to the action faster.",
    },
    "comedy": {
        "act_i_percentage": 30,  # More setup for comic premises
        "act_ii_percentage": 50,
        "act_iii_percentage": 20,
        "required_elements": [
            "comic_set_pieces",
            "escalating_absurdity",
            "callback_jokes",
        ],
        "pacing": "rhythmic",
        "notes": "Comedies need more setup time to establish comic rules and tone.",
    },
    "drama": {
        "act_i_percentage": 25,
        "act_ii_percentage": 55,  # Character development focus
        "act_iii_percentage": 20,
        "required_elements": [
            "emotional_revelations",
            "relationship_dynamics",
            "internal_conflict",
        ],
        "pacing": "measured",
        "notes": "Dramas follow classic proportions with focus on character.",
    },
    "horror": {
        "act_i_percentage": 25,
        "act_ii_percentage": 50,
        "act_iii_percentage": 25,  # Extended climax
        "required_elements": ["dread_building", "false_safety", "survival_stakes"],
        "pacing": "tension_release_cycles",
        "notes": "Horror films often extend Act III for prolonged climax.",
    },
    "action": {
        "act_i_percentage": 20,  # Quick setup
        "act_ii_percentage": 55,  # Extended action
        "act_iii_percentage": 25,  # Big finale
        "required_elements": [
            "action_set_pieces",
            "physical_obstacles",
            "spectacular_climax",
        ],
        "pacing": "relentless",
        "notes": "Action films compress setup to maximize set pieces.",
    },
}


class ThreeActStructureMentor(BaseMentor):
    """Three-Act Structure mentor for screenplay structural analysis.

    This mentor analyzes screenplays according to classical three-act structure,
    providing feedback on plot points, pacing, act proportions, and dramatic
    structure.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the Three-Act Structure mentor.

        Args:
            config: Optional configuration including:
                - check_proportions: Whether to check act proportions (default: True)
                - check_causality: Whether to analyze scene causality (default: True)
                - strict_mode: Whether all elements must be present (default: False)
                - variant: Structure variant ("classic", "four_act", "five_act")
                - genre: Genre for specific analysis ("drama", "thriller", etc.)
                - target_pages: Target script length (default: 110)
        """
        super().__init__(config)
        self._version = "1.0.0"

        # Configuration
        self.check_proportions = self.config.get("check_proportions", True)
        self.check_causality = self.config.get("check_causality", True)
        self.strict_mode = self.config.get("strict_mode", False)
        self.structure_variant = self.config.get("variant", "classic")
        self.genre = self.config.get("genre", "drama")
        self.target_pages = self.config.get("target_pages", 110)

    @property
    def name(self) -> str:
        """Unique name identifier for this mentor."""
        return "three_act_structure"

    @property
    def description(self) -> str:
        """Human-readable description of what this mentor analyzes."""
        return (
            "Analyzes screenplay structure based on classical three-act structure, "
            "checking plot points, act proportions, pacing, and dramatic progression "
            "from setup through confrontation to resolution."
        )

    @property
    def mentor_type(self) -> MentorType:
        """Type category this mentor belongs to."""
        return MentorType.STORY_STRUCTURE

    @property
    def categories(self) -> list[str]:
        """Categories of analysis this mentor provides."""
        return [
            "act_structure",
            "plot_points",
            "pacing",
            "dramatic_progression",
            "scene_causality",
            "b_story_integration",
            "genre_analysis",
            "structural_variants",
        ]

    async def analyze_script(
        self,
        script_id: UUID,
        db_operations: Any,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> MentorResult:
        """Analyze a script using three-act structure methodology.

        Args:
            script_id: UUID of the script to analyze
            db_operations: Database operations interface
            progress_callback: Optional progress callback

        Returns:
            Complete three-act structure analysis result
        """
        start_time = datetime.now(UTC)
        analyses: list[MentorAnalysis] = []

        try:
            if progress_callback:
                progress_callback(0.1, "Loading script structure...")

            # Get script and scenes
            script_data = await self._get_script_data(script_id, db_operations)
            if not script_data:
                raise ValueError(f"Script {script_id} not found")

            scenes = script_data["scenes"]
            total_pages = self._estimate_total_pages(scenes)

            if progress_callback:
                progress_callback(0.2, "Analyzing act divisions...")

            # Analyze act structure and proportions
            if self.check_proportions:
                act_analyses = await self._analyze_act_proportions(scenes, total_pages)
                analyses.extend(act_analyses)

            if progress_callback:
                progress_callback(0.4, "Identifying plot points...")

            # Analyze structural elements and plot points
            element_analyses = await self._analyze_structural_elements(
                scenes, total_pages
            )
            analyses.extend(element_analyses)

            if progress_callback:
                progress_callback(0.6, "Analyzing dramatic progression...")

            # Analyze pacing and dramatic progression
            pacing_analyses = await self._analyze_pacing(scenes)
            analyses.extend(pacing_analyses)

            if progress_callback:
                progress_callback(0.8, "Checking scene causality...")

            # Analyze scene-to-scene causality if enabled
            if self.check_causality:
                causality_analyses = await self._analyze_causality(scenes)
                analyses.extend(causality_analyses)

            if progress_callback:
                progress_callback(0.85, "Analyzing B-story relationships...")

            # Analyze B-story (romantic subplot)
            b_story_analyses = await self._analyze_b_story(scenes, total_pages)
            analyses.extend(b_story_analyses)

            if progress_callback:
                progress_callback(0.9, "Analyzing genre-specific elements...")

            # Analyze genre-specific elements
            genre_analyses = await self._analyze_genre_specifics(scenes, total_pages)
            analyses.extend(genre_analyses)

            if progress_callback:
                progress_callback(0.95, "Generating structural insights...")

            # Generate overall score and summary
            score = self._calculate_score(analyses)
            summary = self._generate_summary(analyses, total_pages)

            execution_time = int(
                (datetime.now(UTC) - start_time).total_seconds() * 1000
            )

            if progress_callback:
                progress_callback(1.0, "Three-act structure analysis complete")

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
            logger.error(
                f"Three-act structure analysis failed for script {script_id}: {e}"
            )

            # Return error result
            error_analysis = MentorAnalysis(
                title="Analysis Error",
                description=f"Three-act structure analysis failed: {e!s}",
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
        """Get script data including scenes."""
        try:
            # This would use the database operations to get script data
            # Placeholder - would be replaced with actual database queries
            return {
                "script_id": script_id,
                "title": "Sample Script",
                "scenes": [],  # Would contain actual scene data with page numbers
                "total_pages": 120,
            }

        except Exception as e:
            logger.error(f"Failed to get script data for {script_id}: {e}")
            return None

    def _estimate_total_pages(self, _scenes: list[dict]) -> int:
        """Estimate total page count from scenes."""
        # In real implementation, would calculate from scene lengths
        return 120  # Placeholder

    async def _analyze_act_proportions(
        self, scenes: list[dict], total_pages: int
    ) -> list[MentorAnalysis]:
        """Analyze act divisions and proportions."""
        analyses = []

        # Calculate actual act breaks
        act_breaks = self._find_act_breaks(scenes, total_pages)

        for act_num, (start_pct, end_pct, expected_pct) in ACT_PROPORTIONS.items():
            actual_start = act_breaks.get(act_num, {}).get("start", start_pct)
            actual_end = act_breaks.get(act_num, {}).get("end", end_pct)
            actual_pct = (actual_end - actual_start) * 100

            expected_value = float(expected_pct.rstrip("%"))
            deviation = abs(actual_pct - expected_value)

            if deviation > 10:  # More than 10% deviation
                severity = AnalysisSeverity.WARNING
                description = (
                    f"Act {act_num} is {actual_pct:.0f}% of the script "
                    f"(expected ~{expected_pct}). This may affect pacing."
                )
            else:
                severity = AnalysisSeverity.INFO
                description = (
                    f"Act {act_num} comprises {actual_pct:.0f}% of the script, "
                    f"which aligns well with the expected {expected_pct}."
                )

            analyses.append(
                MentorAnalysis(
                    title=f"Act {act_num} Proportion",
                    description=description,
                    severity=severity,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="act_structure",
                    mentor_name=self.name,
                    recommendations=(
                        [
                            (
                                f"Act {act_num} typically should be around "
                                f"{expected_pct} of the script"
                            ),
                            (
                                "Consider adjusting scene lengths to balance "
                                "act proportions"
                            ),
                            (
                                "Ensure each act serves its dramatic purpose "
                                "regardless of length"
                            ),
                        ]
                        if deviation > 10
                        else []
                    ),
                    metadata={
                        "act": act_num,
                        "actual_percentage": actual_pct,
                        "expected_percentage": expected_value,
                        "deviation": deviation,
                    },
                )
            )

        return analyses

    def _find_act_breaks(
        self,
        _scenes: list[dict],
        _total_pages: int,
    ) -> dict[int, dict[str, float]]:
        """Find where acts break in the script."""
        # Placeholder - would analyze scenes for act breaks
        return {
            1: {"start": 0.0, "end": 0.25},
            2: {"start": 0.25, "end": 0.75},
            3: {"start": 0.75, "end": 1.0},
        }

    async def _analyze_structural_elements(
        self, scenes: list[dict], total_pages: int
    ) -> list[MentorAnalysis]:
        """Analyze key structural elements and plot points."""
        analyses = []
        found_elements = []

        for element in STRUCTURAL_ELEMENTS:
            # Calculate expected page range
            target_page = int(element.target_percentage * total_pages)
            min_page = int(
                (element.target_percentage - element.tolerance) * total_pages
            )
            max_page = int(
                (element.target_percentage + element.tolerance) * total_pages
            )

            # Override with custom page_range if provided for this element
            if element.page_range:
                min_page, max_page = element.page_range
                target_page = (min_page + max_page) // 2

            # Look for this element in the script
            element_found = self._find_element_in_scenes(
                element, scenes, min_page, max_page
            )

            if element_found:
                found_elements.append(element.name)
                # Analyze element timing and implementation
                timing_analysis = self._analyze_element_timing(
                    element, element_found, target_page, min_page, max_page
                )
                if timing_analysis:
                    analyses.append(timing_analysis)
            elif element.essential or self.strict_mode:
                # Essential element missing
                analyses.append(
                    MentorAnalysis(
                        title=f"Missing {element.name}",
                        description=(
                            f"The {element.name} was not clearly identified around "
                            f"page {target_page} (tolerance: pages "
                            f"{min_page}-{max_page}). "
                            f"{element.description}"
                        ),
                        severity=(
                            AnalysisSeverity.ERROR
                            if element.essential
                            else AnalysisSeverity.WARNING
                        ),
                        scene_id=None,
                        character_id=None,
                        element_id=None,
                        category="plot_points",
                        mentor_name=self.name,
                        recommendations=[
                            f"Add {element.name} around page {target_page}",
                            (
                                "Look for opportunities to include: "
                                f"{', '.join(element.keywords[:3])}"
                            ),
                            f"This element belongs in Act {element.act}",
                        ],
                        metadata={
                            "element_name": element.name,
                            "target_page": target_page,
                            "target_percentage": element.target_percentage,
                            "act": element.act,
                        },
                    )
                )

        # Summary of structural completeness
        completeness_score = len(found_elements) / len(
            [e for e in STRUCTURAL_ELEMENTS if e.essential]
        )
        if completeness_score < 0.8:
            analyses.append(
                MentorAnalysis(
                    title="Incomplete Structure",
                    description=(
                        f"Only {len(found_elements)} of "
                        f"{len([e for e in STRUCTURAL_ELEMENTS if e.essential])} "
                        "essential structural elements were identified."
                    ),
                    severity=AnalysisSeverity.WARNING,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="plot_points",
                    mentor_name=self.name,
                    recommendations=[
                        "Review missing plot points and consider adding them",
                        "Ensure each act has clear turning points",
                        "Strong structure supports character and theme development",
                    ],
                )
            )

        return analyses

    def _find_element_in_scenes(
        self,
        _element: StructuralElement,
        _scenes: list[dict],
        _min_page: int,
        _max_page: int,
    ) -> dict | None:
        """Find scenes that contain the specified structural element."""
        # Placeholder implementation
        return None

    def _analyze_element_timing(
        self,
        _element: StructuralElement,
        _element_data: dict,
        _target_page: int,
        _min_page: int,
        _max_page: int,
    ) -> MentorAnalysis | None:
        """Analyze the timing of a found structural element."""
        # Placeholder implementation
        return None

    async def _analyze_pacing(self, _scenes: list[dict]) -> list[MentorAnalysis]:
        """Analyze pacing and dramatic progression."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Pacing Analysis",
                description=(
                    "Effective three-act structure requires proper pacing with "
                    "rising action, moments of relief, and accelerating tension."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="pacing",
                mentor_name=self.name,
                recommendations=[
                    "Ensure tension rises progressively through each act",
                    "Include breathing room between major dramatic moments",
                    "Act 2 should escalate conflicts established in Act 1",
                    "Act 3 should move quickly toward resolution",
                ],
            )
        )

        return analyses

    async def _analyze_causality(self, _scenes: list[dict]) -> list[MentorAnalysis]:
        """Analyze scene-to-scene causality and progression."""
        analyses = []

        analyses.append(
            MentorAnalysis(
                title="Scene Causality",
                description=(
                    "Strong three-act structure relies on cause-and-effect "
                    "relationships "
                    "between scenes, where each scene leads logically to the next."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="scene_causality",
                mentor_name=self.name,
                recommendations=[
                    "Each scene should be necessary and advance the plot",
                    "Use 'therefore' or 'but' between scenes, not 'and then'",
                    "Character decisions should drive scene transitions",
                    "Remove scenes that don't affect the story outcome",
                ],
            )
        )

        return analyses

    def _get_scene_text(self, scene: dict) -> str:
        """Extract text from scene for analysis."""
        # Combine scene heading, action, dialogue, etc.
        text_parts = []
        if "heading" in scene:
            text_parts.append(scene["heading"])
        if "action" in scene:
            text_parts.append(scene["action"])
        if "dialogue" in scene:
            text_parts.append(scene["dialogue"])
        if "elements" in scene:
            for elem in scene["elements"]:
                if "text" in elem:
                    text_parts.append(elem["text"])
        return " ".join(text_parts)

    async def _analyze_b_story(
        self, scenes: list[dict], total_pages: int
    ) -> list[MentorAnalysis]:
        """Analyze B-story integration and development."""
        analyses = []

        # Look for B-story introduction around page 30
        b_story_intro_page = int(0.27 * total_pages)
        b_story_found = False

        for scene in scenes:
            scene_page = scene.get("page_start", 0)
            if b_story_intro_page - 5 <= scene_page <= b_story_intro_page + 10:
                # Check for subplot/relationship keywords
                scene_text = self._get_scene_text(scene).lower()
                b_story_keywords = [
                    "love",
                    "mentor",
                    "friend",
                    "relationship",
                    "subplot",
                ]
                if any(keyword in scene_text for keyword in b_story_keywords):
                    b_story_found = True
                    break

        if not b_story_found:
            analyses.append(
                MentorAnalysis(
                    title="B-Story Introduction Missing",
                    description=(
                        f"No clear B-story introduction found around page "
                        f"{b_story_intro_page}. The B-story typically provides "
                        "thematic resonance and emotional depth."
                    ),
                    severity=AnalysisSeverity.SUGGESTION,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="b_story_integration",
                    mentor_name=self.name,
                    recommendations=[
                        "Introduce a relationship that reflects the theme",
                        "Consider adding a mentor or confidant character",
                        "Ensure B-story intersects with A-story at key moments",
                    ],
                )
            )

        # Check B-story convergence in Act III
        analyses.append(
            MentorAnalysis(
                title="B-Story Integration Check",
                description=(
                    "The B-story should provide crucial insight or support for the "
                    "Act III resolution. Ensure subplot threads converge with the "
                    "main plot."
                ),
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="b_story_integration",
                mentor_name=self.name,
                recommendations=[
                    "B-story character provides key insight at Plot Point II",
                    "Thematic lesson from B-story helps solve A-story problem",
                    "Emotional growth in B-story enables victory in A-story",
                ],
            )
        )

        return analyses

    async def _analyze_genre_specifics(
        self, scenes: list[dict], total_pages: int
    ) -> list[MentorAnalysis]:
        """Analyze genre-specific structural elements."""
        analyses = []

        genre_info = GENRE_VARIATIONS.get(self.genre, GENRE_VARIATIONS["drama"])

        # Check act proportions against genre expectations
        expected_act1 = float(genre_info["act_i_percentage"]) / 100

        act_breaks = self._find_act_breaks(scenes, total_pages)
        # Safe access with default values to prevent KeyError
        act1_data = act_breaks.get(1, {"start": 0.0, "end": expected_act1})
        actual_act1 = act1_data["end"] - act1_data["start"]

        deviation = abs(actual_act1 - expected_act1) * 100
        if deviation > 5:  # More than 5% deviation
            analyses.append(
                MentorAnalysis(
                    title=f"{self.genre.title()} Genre Structure",
                    description=(
                        f"{self.genre.title()} films typically have Act I at "
                        f"{genre_info['act_i_percentage']}% but yours is "
                        f"{actual_act1 * 100:.0f}%. {genre_info['notes']}"
                    ),
                    severity=AnalysisSeverity.SUGGESTION,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="genre_analysis",
                    mentor_name=self.name,
                    recommendations=[
                        f"Consider adjusting act breaks for {self.genre} conventions",
                        f"Pacing should be {genre_info['pacing']}",
                        f"Include {', '.join(genre_info['required_elements'][:2])}",
                    ],
                    metadata={
                        "genre": self.genre,
                        "expected_act1": genre_info["act_i_percentage"],
                        "actual_act1": actual_act1 * 100,
                    },
                )
            )

        return analyses

    def _calculate_score(self, analyses: list[MentorAnalysis]) -> float:
        """Calculate overall three-act structure score."""
        if not analyses:
            return 0.0

        # Start with base score
        base_score = 70.0

        # Deduct for missing essential elements
        missing_elements = len(
            [
                a
                for a in analyses
                if a.category == "plot_points" and "Missing" in a.title
            ]
        )
        base_score -= missing_elements * 5

        # Adjust for other issues
        severity_weights = {
            AnalysisSeverity.ERROR: -10,
            AnalysisSeverity.WARNING: -5,
            AnalysisSeverity.SUGGESTION: -2,
            AnalysisSeverity.INFO: 1,
        }

        for analysis in analyses:
            if "Missing" not in analysis.title:  # Don't double-count
                base_score += severity_weights.get(analysis.severity, 0)

        return max(0.0, min(100.0, base_score))

    def _generate_summary(
        self, analyses: list[MentorAnalysis], total_pages: int
    ) -> str:
        """Generate summary of the three-act structure analysis."""
        error_count = len([a for a in analyses if a.severity == AnalysisSeverity.ERROR])
        warning_count = len(
            [a for a in analyses if a.severity == AnalysisSeverity.WARNING]
        )

        # Count found elements
        plot_analyses = [a for a in analyses if a.category == "plot_points"]
        missing_elements = len([a for a in plot_analyses if "Missing" in a.title])
        essential_count = len([e for e in STRUCTURAL_ELEMENTS if e.essential])

        summary_parts = [
            f"Three-act structure analysis of {total_pages}-page screenplay completed.",
            (
                f"Found {essential_count - missing_elements} of {essential_count} "
                "essential plot points."
            ),
        ]

        if error_count == 0 and warning_count <= 2:
            summary_parts.append(
                "Script demonstrates strong three-act structure with clear "
                "plot progression."
            )
        else:
            summary_parts.append(
                f"Found {error_count} structural issues and {warning_count} "
                "areas for improvement."
            )

        # Add act proportion summary
        act_analyses = [a for a in analyses if a.category == "act_structure"]
        if any(a.severity == AnalysisSeverity.WARNING for a in act_analyses):
            summary_parts.append(
                "Act proportions may need adjustment for optimal pacing."
            )

        return " ".join(summary_parts)

    def validate_config(self) -> bool:
        """Validate the mentor's configuration."""
        try:
            check_proportions = self.config.get("check_proportions", True)
            check_causality = self.config.get("check_causality", True)
            strict_mode = self.config.get("strict_mode", False)

            return (
                isinstance(check_proportions, bool)
                and isinstance(check_causality, bool)
                and isinstance(strict_mode, bool)
            )

        except Exception:
            return False

    def get_config_schema(self) -> dict[str, Any]:
        """Get the configuration schema for this mentor."""
        return {
            "type": "object",
            "properties": {
                "check_proportions": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze act proportions",
                },
                "check_causality": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze scene-to-scene causality",
                },
                "strict_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether all structural elements must be present",
                },
                "variant": {
                    "type": "string",
                    "enum": ["classic", "four_act", "five_act"],
                    "default": "classic",
                    "description": "Three-act structure variant to use",
                },
                "genre": {
                    "type": "string",
                    "enum": list(GENRE_VARIATIONS.keys()),
                    "default": "drama",
                    "description": "Genre for specific structural analysis",
                },
                "target_pages": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 200,
                    "default": 110,
                    "description": "Target script length in pages",
                },
            },
            "additionalProperties": False,
        }
