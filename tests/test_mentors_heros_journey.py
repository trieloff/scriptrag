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
        assert mentor.minimum_stages == 12  # 12 of 17 stages by default

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
                "minimum_stages": 15,  # Valid now (max is 17)
            }
        )
        assert mentor.validate_config() is True  # This is now valid

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
        assert min_stages_schema["maximum"] == 17

    def test_heros_journey_stages(self):
        """Test Hero's Journey stage definitions."""
        assert len(HEROS_JOURNEY_STAGES) == 17  # Full Campbell monomyth

        # Check first few stages
        ordinary_world = HEROS_JOURNEY_STAGES[0]
        assert ordinary_world.name == "Ordinary World"
        assert ordinary_world.act == 1
        assert ordinary_world.percentage_range == (0.0, 0.10)
        assert "ordinary" in ordinary_world.keywords
        assert "hero" in ordinary_world.archetypes

        # Check midpoint
        ordeal = HEROS_JOURNEY_STAGES[8]  # The Ordeal is now at index 8
        assert ordeal.name == "The Ordeal"
        assert ordeal.act == 2
        assert ordeal.percentage_range == (0.50, 0.55)  # At midpoint
        assert "ordeal" in ordeal.keywords

        # Check unique Campbell stages
        belly_whale = HEROS_JOURNEY_STAGES[5]
        assert belly_whale.name == "Belly of the Whale"
        assert "metamorphosis" in belly_whale.keywords

        goddess = HEROS_JOURNEY_STAGES[9]
        assert goddess.name == "Meeting with the Goddess"
        assert "goddess" in goddess.archetypes

        # Check final stage
        return_elixir = HEROS_JOURNEY_STAGES[16]
        assert return_elixir.name == "Return with the Elixir"
        assert return_elixir.act == 3
        assert return_elixir.percentage_range == (0.90, 1.0)

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
        # With no stages found and 2 INFO analyses, score should be low but not 0
        assert result.score <= 10.0  # Very low score
        assert len(result.analyses) >= 17  # At least 17 missing stages
        assert any(a.severity == AnalysisSeverity.ERROR for a in result.analyses)
        assert "0 of 17" in result.summary.lower()

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

        # With 4 missing stages out of 17, we found 13
        # Base score should be (13/17) * 50 = ~38.24, plus bonuses
        score = mentor._calculate_score(analyses)
        assert 35 <= score <= 45  # Allow some variance

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
        assert "17 Campbell stages" in summary
        assert "mythological journey structure well" in summary

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
        assert "Found 11 of 17" in summary  # 17 - 6 = 11
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

        mentor = HerosJourneyMentor({"minimum_stages": 18})  # Too high, max is 17
        assert mentor.validate_config() is False

    def test_genre_configuration(self):
        """Test genre-specific configuration."""
        # Test default genre
        mentor = HerosJourneyMentor()
        assert mentor.genre == "general"

        # Test each genre
        for genre in [
            "action",
            "drama",
            "comedy",
            "romance",
            "thriller",
            "scifi_fantasy",
        ]:
            mentor = HerosJourneyMentor({"genre": genre})
            assert mentor.genre == genre
            assert mentor.validate_config() is True

        # Test invalid genre
        mentor = HerosJourneyMentor({"genre": "invalid_genre"})
        assert mentor.validate_config() is False

    def test_practical_beats_configuration(self):
        """Test practical beats configuration."""
        # Test default
        mentor = HerosJourneyMentor()
        assert mentor.use_practical_beats is True

        # Test disabled
        mentor = HerosJourneyMentor({"use_practical_beats": False})
        assert mentor.use_practical_beats is False
        assert mentor.validate_config() is True

    def test_stage_match_scoring(self):
        """Test stage match scoring logic."""
        mentor = HerosJourneyMentor()

        # Create a test scene
        scene = {
            "scene_heading": "INT. TATOOINE FARM - DAY",
            "action": (
                "Luke stares at the binary sunset, dreaming of adventure "
                "beyond his ordinary life."
            ),
            "dialogue": [
                {"text": "I want to go to the academy this year.", "character": "LUKE"}
            ],
            "order": 5,  # Early in script
            "characters": ["LUKE", "UNCLE OWEN"],
        }

        # Test against Ordinary World stage
        ordinary_world = HEROS_JOURNEY_STAGES[0]
        score = mentor._calculate_stage_match_score(ordinary_world, scene)
        assert score > 2.0  # Should match well (has "ordinary" keyword)

        # Test against a later stage (should score lower)
        resurrection = HEROS_JOURNEY_STAGES[15]
        score = mentor._calculate_stage_match_score(resurrection, scene)
        assert score < 2.0  # Should not match well

    def test_get_scene_text(self):
        """Test scene text extraction."""
        mentor = HerosJourneyMentor()

        scene = {
            "scene_heading": "INT. DEATH STAR - NIGHT",
            "action": "Luke faces Vader in the trench.",
            "dialogue": [
                {
                    "text": "Use the Force, Luke.",
                    "character": "OBI-WAN",
                    "parenthetical": "(V.O.)",
                }
            ],
            "elements": [{"text": "The targeting computer switches off."}],
        }

        text = mentor._get_scene_text(scene)
        assert "DEATH STAR" in text
        assert "Luke faces Vader" in text
        assert "Use the Force" in text
        assert "V.O." in text
        assert "targeting computer" in text

    def test_stage_recommendations(self):
        """Test stage recommendation generation."""
        mentor = HerosJourneyMentor({"genre": "action"})

        # Test recommendations for Ordinary World
        ordinary_world = HEROS_JOURNEY_STAGES[0]
        recommendations = mentor._get_stage_recommendations(ordinary_world)

        assert len(recommendations) >= 3
        assert any("ordinary" in r.lower() for r in recommendations)
        assert any("Act 1" in r for r in recommendations)

        # Should include film examples
        assert any("Star Wars" in r or "Matrix" in r for r in recommendations)

        # Should include genre-specific advice for action
        assert any("action" in r.lower() for r in recommendations)

    def test_practical_coverage_calculation(self):
        """Test practical beat coverage calculation."""
        mentor = HerosJourneyMentor()

        from scriptrag.mentors.base import MentorAnalysis

        # Create analyses representing found stages
        analyses = [
            MentorAnalysis(
                title="Ordinary World Found",
                description="Found ordinary world",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="journey_stages",
                mentor_name="heros_journey",
                metadata={"stage_name": "Ordinary World"},
            ),
            MentorAnalysis(
                title="Call to Adventure Found",
                description="Found call",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="journey_stages",
                mentor_name="heros_journey",
                metadata={"stage_name": "Call to Adventure"},
            ),
        ]

        coverage = mentor._calculate_practical_coverage(analyses)

        assert coverage["Ordinary World"] is True
        assert coverage["Call to Adventure"] is True
        assert coverage["Crossing the Threshold"] is False  # Not found
        assert len(coverage) == 8  # 8 practical beats
