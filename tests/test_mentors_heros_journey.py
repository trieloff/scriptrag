"""Tests for the Hero's Journey mentor."""

from uuid import uuid4

import pytest

from scriptrag.mentors.base import AnalysisSeverity, MentorType
from scriptrag.mentors.heros_journey import (
    HEROS_JOURNEY_STAGES,
    HerosJourneyMentor,
)


class TestHerosJourneyMentor:
    """Test the Hero's Journey mentor implementation."""

    def test_mentor_properties(self):
        """Test basic mentor properties."""
        mentor = HerosJourneyMentor()

        assert mentor.name == "heros_journey"
        assert mentor.mentor_type == MentorType.STORY_STRUCTURE
        assert mentor.version == "1.0.0"
        assert "monomyth" in mentor.description.lower()
        assert "campbell" in mentor.description.lower()

        # Check categories
        expected_categories = [
            "monomyth",
            "hero_transformation",
            "archetypes",
            "mythological_structure",
            "journey_stages",
        ]
        assert set(mentor.categories) == set(expected_categories)

    def test_mentor_configuration(self):
        """Test mentor configuration options."""
        # Default configuration
        mentor = HerosJourneyMentor()
        assert mentor.check_archetypes is True
        assert mentor.strict_order is False
        assert mentor.minimum_stages == 8

        # Custom configuration
        config = {
            "check_archetypes": False,
            "strict_order": True,
            "minimum_stages": 10,
        }
        mentor = HerosJourneyMentor(config)
        assert mentor.check_archetypes is False
        assert mentor.strict_order is True
        assert mentor.minimum_stages == 10

    def test_config_validation(self):
        """Test configuration validation."""
        mentor = HerosJourneyMentor()

        # Valid configuration
        assert mentor.validate_config() is True

        # Test with valid custom config
        mentor = HerosJourneyMentor(
            {
                "check_archetypes": False,
                "strict_order": True,
                "minimum_stages": 6,
            }
        )
        assert mentor.validate_config() is True

        # Test with invalid config
        mentor = HerosJourneyMentor(
            {
                "minimum_stages": 15,  # Too high
            }
        )
        assert mentor.validate_config() is False

        mentor = HerosJourneyMentor(
            {
                "minimum_stages": "not a number",
            }
        )
        assert mentor.validate_config() is False

    def test_config_schema(self):
        """Test configuration schema."""
        mentor = HerosJourneyMentor()
        schema = mentor.get_config_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "check_archetypes" in schema["properties"]
        assert "strict_order" in schema["properties"]
        assert "minimum_stages" in schema["properties"]

        # Check minimum_stages constraints
        min_stages_schema = schema["properties"]["minimum_stages"]
        assert min_stages_schema["type"] == "integer"
        assert min_stages_schema["minimum"] == 1
        assert min_stages_schema["maximum"] == 12

    def test_heros_journey_stages(self):
        """Test Hero's Journey stage definitions."""
        assert len(HEROS_JOURNEY_STAGES) == 12

        # Check first few stages
        ordinary_world = HEROS_JOURNEY_STAGES[0]
        assert ordinary_world.name == "Ordinary World"
        assert ordinary_world.act == 1
        assert ordinary_world.percentage_range == (0.0, 0.10)
        assert "ordinary" in ordinary_world.keywords
        assert "hero" in ordinary_world.archetypes

        # Check midpoint
        ordeal = HEROS_JOURNEY_STAGES[7]
        assert ordeal.name == "Ordeal"
        assert ordeal.act == 2
        assert ordeal.percentage_range == (0.60, 0.65)
        assert "crisis" in ordeal.keywords

        # Check final stage
        return_elixir = HEROS_JOURNEY_STAGES[11]
        assert return_elixir.name == "Return with the Elixir"
        assert return_elixir.act == 3
        assert return_elixir.percentage_range == (0.95, 1.0)

    @pytest.mark.asyncio
    async def test_analyze_script_error_handling(self):
        """Test error handling in script analysis."""
        mentor = HerosJourneyMentor()
        script_id = uuid4()

        # Mock database operations that raises an error
        class MockDBOps:
            pass

        # This will fail because _get_script_data returns None (simulating a db error)
        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "heros_journey"
        assert result.script_id == script_id
        assert result.score == 2.0  # Base 0 + 2 for INFO analyses
        assert len(result.analyses) == 14  # 12 missing stages + 2 info
        assert result.analyses[0].severity == AnalysisSeverity.ERROR
        assert "0 of 12" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_analyze_script_with_progress_callback(self):
        """Test progress callback functionality."""
        mentor = HerosJourneyMentor()
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
                    "characters": [],
                }

        # This will fail but we're testing progress updates
        await mentor.analyze_script(script_id, MockDBOps(), progress_callback)

        # Check progress updates were made
        assert len(progress_updates) > 0
        assert progress_updates[0][0] == 0.1
        assert progress_updates[-1][0] == 1.0
        assert "complete" in progress_updates[-1][1].lower()

    def test_stage_order_checking(self):
        """Test stage order validation logic."""
        mentor = HerosJourneyMentor({"strict_order": True})

        # Test with correct order
        found_stages = ["Ordinary World", "Call to Adventure", "Crossing the Threshold"]
        analysis = mentor._check_stage_order(found_stages)
        assert analysis is None  # No issue

        # Test with incorrect order
        found_stages = ["Crossing the Threshold", "Call to Adventure", "Ordinary World"]
        analysis = mentor._check_stage_order(found_stages)
        assert analysis is not None
        assert analysis.severity == AnalysisSeverity.WARNING
        assert "out of traditional order" in analysis.description

    def test_score_calculation(self):
        """Test score calculation logic."""
        mentor = HerosJourneyMentor()

        # Test with no analyses
        score = mentor._calculate_score([])
        assert score == 0.0

        # Test with missing stages
        from scriptrag.mentors.base import MentorAnalysis

        analyses = []
        # Add some missing stage analyses
        for i in range(4):  # 4 missing stages
            analyses.append(
                MentorAnalysis(
                    title=f"Missing Stage: Stage {i}",
                    description="Stage missing",
                    severity=AnalysisSeverity.ERROR,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="journey_stages",
                    mentor_name="heros_journey",
                )
            )

        # With 4 missing stages out of 12, we found 8
        # Base score should be (8/12) * 70 = ~46.67
        score = mentor._calculate_score(analyses)
        assert 40 <= score <= 50  # Allow some variance

    def test_summary_generation(self):
        """Test summary generation."""
        mentor = HerosJourneyMentor()

        from scriptrag.mentors.base import MentorAnalysis

        # Test with good analysis
        analyses = [
            MentorAnalysis(
                title="Complete Journey",
                description="All stages found",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="journey_stages",
                mentor_name="heros_journey",
            )
        ]

        summary = mentor._generate_summary(analyses, 120)
        assert "12 monomyth stages" in summary
        assert "archetypal hero's journey structure well" in summary

        # Test with missing stages
        analyses = []
        for i in range(6):  # 6 missing stages
            analyses.append(
                MentorAnalysis(
                    title=f"Missing Stage: Stage {i}",
                    description="Stage missing",
                    severity=AnalysisSeverity.ERROR,
                    scene_id=None,
                    character_id=None,
                    element_id=None,
                    category="journey_stages",
                    mentor_name="heros_journey",
                )
            )

        summary = mentor._generate_summary(analyses, 120)
        assert "Found 6 of 12" in summary
        assert "needs" in summary.lower()

    def test_archetype_analysis_enabled(self):
        """Test that archetype analysis can be enabled/disabled."""
        # With archetypes enabled
        mentor = HerosJourneyMentor({"check_archetypes": True})
        assert mentor.check_archetypes is True

        # With archetypes disabled
        mentor = HerosJourneyMentor({"check_archetypes": False})
        assert mentor.check_archetypes is False

    def test_minimum_stages_configuration(self):
        """Test minimum stages requirement configuration."""
        # Test different minimum stage requirements
        for min_stages in [1, 6, 8, 12]:
            mentor = HerosJourneyMentor({"minimum_stages": min_stages})
            assert mentor.minimum_stages == min_stages

        # Test invalid values
        mentor = HerosJourneyMentor({"minimum_stages": 0})
        assert mentor.validate_config() is False

        mentor = HerosJourneyMentor({"minimum_stages": 13})
        assert mentor.validate_config() is False
