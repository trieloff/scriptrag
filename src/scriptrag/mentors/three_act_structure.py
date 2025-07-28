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
        """
        self.name = name
        self.description = description
        self.act = act
        self.target_percentage = target_percentage
        self.tolerance = tolerance
        self.keywords = keywords
        self.essential = essential


# Key structural elements in three-act structure
STRUCTURAL_ELEMENTS = [
    StructuralElement(
        "Opening",
        (
            "The opening scene that establishes tone, genre, and hooks the audience. "
            "Should introduce the world and hint at the central conflict."
        ),
        1,
        0.01,
        0.02,
        ["opening", "fade in", "first", "establishes", "world"],
        True,
    ),
    StructuralElement(
        "Setup",
        (
            "Introduction of main characters, their world, and the status quo. "
            "Establishes what's normal before everything changes."
        ),
        1,
        0.05,
        0.05,
        ["introduction", "meet", "ordinary", "status quo", "normal"],
        True,
    ),
    StructuralElement(
        "Inciting Incident",
        (
            "The event that disrupts the status quo and launches the story. "
            "Sets the central conflict in motion and forces the protagonist to act."
        ),
        1,
        0.10,
        0.05,
        ["inciting", "catalyst", "disruption", "problem", "conflict begins"],
        True,
    ),
    StructuralElement(
        "Plot Point 1",
        (
            "Major turning point that spins the story into Act 2. The protagonist "
            "commits to their goal and enters unfamiliar territory."
        ),
        1,
        0.25,
        0.05,
        ["turning point", "act two", "commits", "decision", "new direction"],
        True,
    ),
    StructuralElement(
        "Pinch Point 1",
        (
            "Reminder of the antagonist's power and the stakes. Shows the opposition "
            "in action and what the protagonist is up against."
        ),
        2,
        0.375,
        0.05,
        ["antagonist", "opposition", "threat", "stakes", "reminder"],
        False,
    ),
    StructuralElement(
        "Midpoint",
        (
            "Major reversal or revelation that changes the protagonist's approach. "
            "Often shifts from reaction to action, raises stakes dramatically."
        ),
        2,
        0.50,
        0.05,
        ["midpoint", "reversal", "revelation", "shift", "truth revealed"],
        True,
    ),
    StructuralElement(
        "Pinch Point 2",
        (
            "Second reminder of opposition's power, often showing the antagonist "
            "closing in. Increases pressure on the protagonist."
        ),
        2,
        0.625,
        0.05,
        ["pressure", "closing in", "antagonist", "danger", "stakes rise"],
        False,
    ),
    StructuralElement(
        "Plot Point 2",
        (
            "Major turning point that launches Act 3. Often the darkest moment "
            "that forces the protagonist to find their final approach."
        ),
        2,
        0.75,
        0.05,
        ["act three", "darkest", "all is lost", "final push", "revelation"],
        True,
    ),
    StructuralElement(
        "Climax",
        (
            "The highest point of tension where the central conflict is resolved. "
            "The protagonist faces their greatest challenge."
        ),
        3,
        0.90,
        0.05,
        ["climax", "final battle", "confrontation", "showdown", "resolution"],
        True,
    ),
    StructuralElement(
        "Resolution",
        (
            "The aftermath showing the new status quo. Ties up loose ends and "
            "shows how characters and their world have changed."
        ),
        3,
        0.95,
        0.05,
        ["resolution", "aftermath", "new normal", "ending", "epilogue"],
        True,
    ),
]

# Expected act proportions
ACT_PROPORTIONS = {
    1: (0.0, 0.25, "25%"),  # Start, End, Expected percentage
    2: (0.25, 0.75, "50%"),
    3: (0.75, 1.0, "25%"),
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
        """
        super().__init__(config)
        self._version = "1.0.0"

        # Configuration
        self.check_proportions = self.config.get("check_proportions", True)
        self.check_causality = self.config.get("check_causality", True)
        self.strict_mode = self.config.get("strict_mode", False)

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
        start_time = datetime.utcnow()
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
                progress_callback(0.9, "Generating structural insights...")

            # Generate overall score and summary
            score = self._calculate_score(analyses)
            summary = self._generate_summary(analyses, total_pages)

            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
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

    def _estimate_total_pages(self, scenes: list[dict]) -> int:  # noqa: ARG002
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
        total_pages: int,  # noqa: ARG002
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
        element: StructuralElement,  # noqa: ARG002
        scenes: list[dict],  # noqa: ARG002
        min_page: int,  # noqa: ARG002
        max_page: int,  # noqa: ARG002
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

    async def _analyze_pacing(
        self,
        scenes: list[dict],  # noqa: ARG002
    ) -> list[MentorAnalysis]:
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

    async def _analyze_causality(
        self,
        scenes: list[dict],  # noqa: ARG002
    ) -> list[MentorAnalysis]:
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
            },
            "additionalProperties": False,
        }
