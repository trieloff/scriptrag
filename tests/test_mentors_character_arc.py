"""Tests for the Character Arc mentor."""

from uuid import uuid4

import pytest

from scriptrag.mentors.base import AnalysisSeverity, MentorType
from scriptrag.mentors.character_arc import (
    CHARACTER_ARC_TYPES,
    DEVELOPMENT_STAGES,
    CharacterArcMentor,
)


class TestCharacterArcMentor:
    """Test the Character Arc mentor implementation."""

    def test_mentor_properties(self):
        """Test basic mentor properties."""
        mentor = CharacterArcMentor()

        assert mentor.name == "character_arc"
        assert mentor.mentor_type == MentorType.CHARACTER_ARC
        assert mentor.version == "1.0.0"
        assert "character development" in mentor.description.lower()
        assert "transformation" in mentor.description.lower()

        # Check categories
        expected_categories = [
            "character_transformation",
            "want_vs_need",
            "internal_conflict",
            "emotional_journey",
            "character_relationships",
        ]
        assert set(mentor.categories) == set(expected_categories)

    def test_mentor_configuration(self):
        """Test mentor configuration options."""
        # Default configuration
        mentor = CharacterArcMentor()
        assert mentor.analyze_supporting is True
        assert mentor.min_arc_characters == 1
        assert mentor.track_relationships is True

        # Custom configuration
        config = {
            "analyze_supporting": False,
            "min_arc_characters": 3,
            "track_relationships": False,
        }
        mentor = CharacterArcMentor(config)
        assert mentor.analyze_supporting is False
        assert mentor.min_arc_characters == 3
        assert mentor.track_relationships is False

    def test_config_validation(self):
        """Test configuration validation."""
        mentor = CharacterArcMentor()

        # Valid configuration
        assert mentor.validate_config() is True

        # Test with valid custom config
        mentor = CharacterArcMentor(
            {
                "analyze_supporting": False,
                "min_arc_characters": 2,
                "track_relationships": True,
            }
        )
        assert mentor.validate_config() is True

        # Test with invalid config
        mentor = CharacterArcMentor(
            {
                "min_arc_characters": -1,  # Negative not allowed
            }
        )
        assert mentor.validate_config() is False

        mentor = CharacterArcMentor(
            {
                "analyze_supporting": "not a boolean",
            }
        )
        assert mentor.validate_config() is False

    def test_config_schema(self):
        """Test configuration schema."""
        mentor = CharacterArcMentor()
        schema = mentor.get_config_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "analyze_supporting" in schema["properties"]
        assert "min_arc_characters" in schema["properties"]
        assert "track_relationships" in schema["properties"]

        # Check property types
        assert schema["properties"]["analyze_supporting"]["type"] == "boolean"
        assert schema["properties"]["min_arc_characters"]["type"] == "integer"
        assert schema["properties"]["min_arc_characters"]["minimum"] == 0
        assert schema["properties"]["track_relationships"]["type"] == "boolean"

    def test_character_arc_types(self):
        """Test character arc type definitions."""
        assert len(CHARACTER_ARC_TYPES) == 4

        # Check positive change arc
        positive_arc = CHARACTER_ARC_TYPES[0]
        assert positive_arc.name == "Positive Change Arc"
        assert "overcomes" in positive_arc.indicators
        assert len(positive_arc.journey_pattern) == 6
        assert "Believes lie/has flaw" in positive_arc.journey_pattern

        # Check negative change arc
        negative_arc = CHARACTER_ARC_TYPES[1]
        assert negative_arc.name == "Negative Change Arc"
        assert "corrupted" in negative_arc.indicators
        assert "Tragic ending" in negative_arc.journey_pattern

        # Check flat arc
        flat_arc = CHARACTER_ARC_TYPES[2]
        assert flat_arc.name == "Flat Arc"
        assert "steadfast" in flat_arc.indicators
        assert "Already knows truth" in flat_arc.journey_pattern[0]

        # Check failed arc
        failed_arc = CHARACTER_ARC_TYPES[3]
        assert failed_arc.name == "Failed Arc"
        assert "refuses" in failed_arc.indicators

    def test_development_stages(self):
        """Test character development stage definitions."""
        assert len(DEVELOPMENT_STAGES) == 8

        # Check establishment stage
        establishment = DEVELOPMENT_STAGES[0]
        assert establishment.name == "Establishment"
        assert establishment.typical_position == 0.05
        assert "introduction" in establishment.indicators

        # Check crisis point
        crisis = next(s for s in DEVELOPMENT_STAGES if s.name == "Crisis Point")
        assert crisis.typical_position == 0.60
        assert "lowest point" in crisis.indicators

        # Check transformation
        transformation = next(
            s for s in DEVELOPMENT_STAGES if s.name == "Transformation"
        )
        assert transformation.typical_position == 0.85
        assert "transformed" in transformation.indicators

    @pytest.mark.asyncio
    async def test_analyze_script_error_handling(self):
        """Test error handling in script analysis."""
        mentor = CharacterArcMentor()
        script_id = uuid4()

        # Mock database operations that raises an error
        class MockDBOps:
            pass

        # This will fail because _get_script_data returns None (simulating a db error)
        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "character_arc"
        assert result.script_id == script_id
        assert result.score == 0.0
        assert len(result.analyses) == 1
        assert result.analyses[0].severity == AnalysisSeverity.ERROR
        assert "failed" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_analyze_script_no_characters(self):
        """Test analysis when no characters are found."""
        mentor = CharacterArcMentor()
        script_id = uuid4()

        # Mock database operations with no characters
        class MockDBOps:
            async def get_script(self, script_id):
                return {
                    "script_id": script_id,
                    "title": "Test Script",
                    "characters": [],  # No characters
                    "scenes": [],
                }

        # Need to patch _get_script_data to return our mock data
        async def mock_get_script_data(self, script_id, db_ops):  # noqa: ARG001
            return await db_ops.get_script(script_id)

        mentor._get_script_data = mock_get_script_data.__get__(
            mentor, CharacterArcMentor
        )

        result = await mentor.analyze_script(script_id, MockDBOps())

        assert len(result.analyses) == 1
        assert result.analyses[0].title == "No Characters Found"
        assert result.analyses[0].severity == AnalysisSeverity.ERROR

    @pytest.mark.asyncio
    async def test_analyze_script_with_progress_callback(self):
        """Test progress callback functionality."""
        mentor = CharacterArcMentor()
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
                    "characters": [{"id": uuid4(), "name": "Hero"}],
                    "scenes": [],
                }

        # This will run analysis
        await mentor.analyze_script(script_id, MockDBOps(), progress_callback)

        # Check progress updates were made
        assert len(progress_updates) > 0
        assert progress_updates[0][0] == 0.1
        assert progress_updates[-1][0] == 1.0
        assert "complete" in progress_updates[-1][1].lower()

    def test_score_calculation(self):
        """Test score calculation logic."""
        mentor = CharacterArcMentor()

        # Test with no analyses
        score = mentor._calculate_score([])
        assert score == 0.0

        # Test with good character arc
        from scriptrag.mentors.base import MentorAnalysis

        analyses = [
            MentorAnalysis(
                title="Complete Arc",
                description="Character has full arc",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_transformation",
                mentor_name="character_arc",
            ),
            MentorAnalysis(
                title="Want vs Need",
                description="Clear want vs need",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="want_vs_need",
                mentor_name="character_arc",
            ),
        ]

        # Base 70 + 10 (transformation) + 10 (want/need) + 2 (INFO bonuses) = 92
        score = mentor._calculate_score(analyses)
        assert 90 <= score <= 95

    def test_summary_generation(self):
        """Test summary generation."""
        mentor = CharacterArcMentor()

        from scriptrag.mentors.base import MentorAnalysis

        # Test with good character development
        analyses = [
            MentorAnalysis(
                title="Complete Character Journey",
                description="All stages present",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_transformation",
                mentor_name="character_arc",
            )
        ]

        summary = mentor._generate_summary(analyses, 5)
        assert "5 characters" in summary
        assert "clear, compelling transformation" in summary
        assert "satisfying development trajectory" in summary

        # Test with issues
        analyses = [
            MentorAnalysis(
                title="Incomplete Development",
                description="Missing stages",
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="character_transformation",
                mentor_name="character_arc",
            )
        ]

        summary = mentor._generate_summary(analyses, 3)
        assert "3 characters" in summary
        assert "1 areas for character development improvement" in summary
        assert "needs additional development stages" in summary

    def test_analyze_supporting_config(self):
        """Test that supporting character analysis can be disabled."""
        mentor = CharacterArcMentor({"analyze_supporting": False})
        assert mentor.analyze_supporting is False

    def test_min_arc_characters_config(self):
        """Test minimum arc characters configuration."""
        # Test different values
        for min_chars in [0, 1, 3, 5]:
            mentor = CharacterArcMentor({"min_arc_characters": min_chars})
            assert mentor.min_arc_characters == min_chars

    def test_track_relationships_config(self):
        """Test that relationship tracking can be disabled."""
        mentor = CharacterArcMentor({"track_relationships": False})
        assert mentor.track_relationships is False

    def test_arc_type_indicators(self):
        """Test that arc types have proper indicators."""
        for arc_type in CHARACTER_ARC_TYPES:
            assert len(arc_type.indicators) > 0
            assert len(arc_type.journey_pattern) > 0
            assert isinstance(arc_type.name, str)
            assert isinstance(arc_type.description, str)

    def test_development_stage_positions(self):
        """Test that development stages have proper positions."""
        positions = [stage.typical_position for stage in DEVELOPMENT_STAGES]

        # Positions should be in ascending order
        assert positions == sorted(positions)

        # Should span the story
        assert positions[0] < 0.1  # Early
        assert positions[-1] > 0.9  # Late

        # All positions should be between 0 and 1
        assert all(0 <= pos <= 1 for pos in positions)
