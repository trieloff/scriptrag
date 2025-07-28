"""Tests for the Three-Act Structure mentor."""

from uuid import uuid4

import pytest

from scriptrag.mentors.base import AnalysisSeverity, MentorType
from scriptrag.mentors.three_act_structure import (
    ACT_PROPORTIONS,
    STRUCTURAL_ELEMENTS,
    ThreeActStructureMentor,
)


class TestThreeActStructureMentor:
    """Test the Three-Act Structure mentor implementation."""

    def test_mentor_properties(self):
        """Test basic mentor properties."""
        mentor = ThreeActStructureMentor()

        assert mentor.name == "three_act_structure"
        assert mentor.mentor_type == MentorType.STORY_STRUCTURE
        assert mentor.version == "1.0.0"
        assert "three-act" in mentor.description.lower()
        assert "plot points" in mentor.description.lower()

        # Check categories
        expected_categories = [
            "act_structure",
            "plot_points",
            "pacing",
            "dramatic_progression",
            "scene_causality",
        ]
        assert set(mentor.categories) == set(expected_categories)

    def test_mentor_configuration(self):
        """Test mentor configuration options."""
        # Default configuration
        mentor = ThreeActStructureMentor()
        assert mentor.check_proportions is True
        assert mentor.check_causality is True
        assert mentor.strict_mode is False

        # Custom configuration
        config = {
            "check_proportions": False,
            "check_causality": False,
            "strict_mode": True,
        }
        mentor = ThreeActStructureMentor(config)
        assert mentor.check_proportions is False
        assert mentor.check_causality is False
        assert mentor.strict_mode is True

    def test_config_validation(self):
        """Test configuration validation."""
        mentor = ThreeActStructureMentor()

        # Valid configuration
        assert mentor.validate_config() is True

        # Test with valid custom config
        mentor = ThreeActStructureMentor(
            {
                "check_proportions": False,
                "check_causality": True,
                "strict_mode": True,
            }
        )
        assert mentor.validate_config() is True

        # Test with invalid config
        mentor = ThreeActStructureMentor(
            {
                "check_proportions": "not a boolean",
            }
        )
        assert mentor.validate_config() is False

    def test_config_schema(self):
        """Test configuration schema."""
        mentor = ThreeActStructureMentor()
        schema = mentor.get_config_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "check_proportions" in schema["properties"]
        assert "check_causality" in schema["properties"]
        assert "strict_mode" in schema["properties"]

        # Check all properties are boolean
        for prop in ["check_proportions", "check_causality", "strict_mode"]:
            assert schema["properties"][prop]["type"] == "boolean"

    def test_structural_elements(self):
        """Test structural element definitions."""
        assert len(STRUCTURAL_ELEMENTS) == 10

        # Check opening
        opening = STRUCTURAL_ELEMENTS[0]
        assert opening.name == "Opening"
        assert opening.act == 1
        assert opening.target_percentage == 0.01
        assert opening.essential is True

        # Check inciting incident
        inciting = next(e for e in STRUCTURAL_ELEMENTS if e.name == "Inciting Incident")
        assert inciting.act == 1
        assert inciting.target_percentage == 0.10
        assert inciting.tolerance == 0.05
        assert "catalyst" in inciting.keywords

        # Check midpoint
        midpoint = next(e for e in STRUCTURAL_ELEMENTS if e.name == "Midpoint")
        assert midpoint.act == 2
        assert midpoint.target_percentage == 0.50
        assert midpoint.essential is True

        # Check non-essential elements
        pinch1 = next(e for e in STRUCTURAL_ELEMENTS if e.name == "Pinch Point 1")
        assert pinch1.essential is False

    def test_act_proportions(self):
        """Test act proportion definitions."""
        assert len(ACT_PROPORTIONS) == 3

        # Act 1: 25%
        assert ACT_PROPORTIONS[1] == (0.0, 0.25, "25%")

        # Act 2: 50%
        assert ACT_PROPORTIONS[2] == (0.25, 0.75, "50%")

        # Act 3: 25%
        assert ACT_PROPORTIONS[3] == (0.75, 1.0, "25%")

    @pytest.mark.asyncio
    async def test_analyze_script_error_handling(self):
        """Test error handling in script analysis."""
        mentor = ThreeActStructureMentor()
        script_id = uuid4()

        # Mock database operations that raises an error
        class MockDBOps:
            pass

        # This will fail because _get_script_data returns None (simulating a db error)
        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "three_act_structure"
        assert result.script_id == script_id
        assert result.score == 0.0
        assert len(result.analyses) == 1
        assert result.analyses[0].severity == AnalysisSeverity.ERROR
        assert "failed" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_analyze_script_with_progress_callback(self):
        """Test progress callback functionality."""
        mentor = ThreeActStructureMentor()
        script_id = uuid4()
        progress_updates = []

        def progress_callback(progress: float, message: str):
            progress_updates.append((progress, message))

        # Mock successful database operations
        class MockDBOps:
            async def get_script(self, script_id):
                return {
                    "script_id": script_id,
                    "title": "Test Script",
                    "scenes": [],
                    "total_pages": 120,
                }

        # This will run analysis
        await mentor.analyze_script(script_id, MockDBOps(), progress_callback)

        # Check progress updates were made
        assert len(progress_updates) > 0
        assert progress_updates[0][0] == 0.1
        assert progress_updates[-1][0] == 1.0
        assert "complete" in progress_updates[-1][1].lower()

    @pytest.mark.asyncio
    async def test_act_proportion_analysis(self):
        """Test act proportion analysis logic."""
        mentor = ThreeActStructureMentor()

        scenes = []  # Empty scenes for testing
        total_pages = 120

        analyses = await mentor._analyze_act_proportions(scenes, total_pages)

        # Should have one analysis per act
        assert len(analyses) == 3

        # Check that each act is analyzed
        act_analyses = {a.metadata["act"]: a for a in analyses}
        assert 1 in act_analyses
        assert 2 in act_analyses
        assert 3 in act_analyses

        # With default proportions, all should be INFO level
        for analysis in analyses:
            assert analysis.category == "act_structure"
            assert analysis.severity == AnalysisSeverity.INFO

    def test_page_estimation(self):
        """Test page count estimation."""
        mentor = ThreeActStructureMentor()

        # Test with empty scenes
        pages = mentor._estimate_total_pages([])
        assert pages == 120  # Default placeholder

        # Test with scenes (placeholder implementation)
        scenes = [{"id": i} for i in range(100)]
        pages = mentor._estimate_total_pages(scenes)
        assert pages == 120  # Still placeholder

    def test_score_calculation(self):
        """Test score calculation logic."""
        mentor = ThreeActStructureMentor()

        # Test with no analyses
        score = mentor._calculate_score([])
        assert score == 0.0

        # Test with missing essential elements
        from scriptrag.mentors.base import MentorAnalysis

        analyses = []
        # Add some missing element analyses
        for i in range(3):  # 3 missing elements
            analyses.append(
                MentorAnalysis(
                    title=f"Missing Element {i}",
                    description="Element missing",
                    severity=AnalysisSeverity.ERROR,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="plot_points",
                    mentor_name="three_act_structure",
                )
            )

        # Base score 70 - (3 * 5) = 55
        score = mentor._calculate_score(analyses)
        assert 50 <= score <= 60

    def test_summary_generation(self):
        """Test summary generation."""
        mentor = ThreeActStructureMentor()

        from scriptrag.mentors.base import MentorAnalysis

        # Test with good structure
        analyses = [
            MentorAnalysis(
                title="Complete Structure",
                description="All elements found",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="plot_points",
                mentor_name="three_act_structure",
            )
        ]

        summary = mentor._generate_summary(analyses, 120)
        assert "120-page screenplay" in summary
        assert "strong three-act structure" in summary

        # Test with issues
        analyses = [
            MentorAnalysis(
                title="Missing Inciting Incident",
                description="Element missing",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="plot_points",
                mentor_name="three_act_structure",
            ),
            MentorAnalysis(
                title="Act 2 Proportion",
                description="Act too long",
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="act_structure",
                mentor_name="three_act_structure",
            ),
        ]

        summary = mentor._generate_summary(analyses, 120)
        assert "1 structural issues" in summary
        assert "1 areas for improvement" in summary
        assert "Act proportions may need adjustment" in summary

    def test_check_proportions_config(self):
        """Test that proportion checking can be disabled."""
        mentor = ThreeActStructureMentor({"check_proportions": False})
        assert mentor.check_proportions is False

    def test_check_causality_config(self):
        """Test that causality checking can be disabled."""
        mentor = ThreeActStructureMentor({"check_causality": False})
        assert mentor.check_causality is False

    def test_strict_mode_config(self):
        """Test strict mode configuration."""
        # Non-strict mode (default)
        mentor = ThreeActStructureMentor()
        assert mentor.strict_mode is False

        # Strict mode
        mentor = ThreeActStructureMentor({"strict_mode": True})
        assert mentor.strict_mode is True

    def test_essential_vs_optional_elements(self):
        """Test handling of essential vs optional structural elements."""
        # Count essential elements
        essential_count = len([e for e in STRUCTURAL_ELEMENTS if e.essential])
        optional_count = len([e for e in STRUCTURAL_ELEMENTS if not e.essential])

        assert essential_count == 8  # Most are essential
        assert optional_count == 2  # Pinch points are optional

        # Verify pinch points are optional
        pinch_points = [e for e in STRUCTURAL_ELEMENTS if "Pinch Point" in e.name]
        assert len(pinch_points) == 2
        assert all(not e.essential for e in pinch_points)
