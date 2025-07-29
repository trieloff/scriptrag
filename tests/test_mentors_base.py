"""Tests for the mentor base classes and models."""

from datetime import datetime
from uuid import uuid4

import pytest

from scriptrag.mentors.base import (
    AnalysisSeverity,
    BaseMentor,
    MentorAnalysis,
    MentorResult,
    MentorType,
)


class TestMentorAnalysis:
    """Test MentorAnalysis model."""

    def test_mentor_analysis_creation(self):
        """Test creating a MentorAnalysis instance."""
        scene_id = uuid4()
        analysis = MentorAnalysis(
            title="Test Analysis",
            description="This is a test analysis",
            severity=AnalysisSeverity.WARNING,
            category="test",
            mentor_name="test_mentor",
            scene_id=scene_id,
            recommendations=["Fix this issue", "Consider that approach"],
            confidence=0.8,
        )

        assert analysis.title == "Test Analysis"
        assert analysis.description == "This is a test analysis"
        assert analysis.severity == AnalysisSeverity.WARNING
        assert analysis.category == "test"
        assert analysis.mentor_name == "test_mentor"
        assert analysis.scene_id == scene_id
        assert analysis.recommendations == ["Fix this issue", "Consider that approach"]
        assert analysis.confidence == 0.8
        assert analysis.id is not None
        assert isinstance(analysis.id, type(uuid4()))

    def test_mentor_analysis_defaults(self):
        """Test MentorAnalysis default values."""
        analysis = MentorAnalysis(
            title="Test",
            description="Test description",
            severity=AnalysisSeverity.INFO,
            category="test",
            mentor_name="test_mentor",
        )

        assert analysis.scene_id is None
        assert analysis.character_id is None
        assert analysis.element_id is None
        assert analysis.confidence == 1.0
        assert analysis.recommendations == []
        assert analysis.examples == []
        assert analysis.metadata == {}

    def test_mentor_analysis_validation(self):
        """Test MentorAnalysis validation."""
        # Test confidence bounds
        with pytest.raises(ValueError):
            MentorAnalysis(
                title="Test",
                description="Test",
                severity=AnalysisSeverity.INFO,
                category="test",
                mentor_name="test_mentor",
                confidence=-0.1,  # Below minimum
            )

        with pytest.raises(ValueError):
            MentorAnalysis(
                title="Test",
                description="Test",
                severity=AnalysisSeverity.INFO,
                category="test",
                mentor_name="test_mentor",
                confidence=1.1,  # Above maximum
            )


class TestMentorResult:
    """Test MentorResult model."""

    def test_mentor_result_creation(self):
        """Test creating a MentorResult instance."""
        script_id = uuid4()
        analyses = [
            MentorAnalysis(
                title="Error 1",
                description="First error",
                severity=AnalysisSeverity.ERROR,
                category="structure",
                mentor_name="test_mentor",
            ),
            MentorAnalysis(
                title="Warning 1",
                description="First warning",
                severity=AnalysisSeverity.WARNING,
                category="pacing",
                mentor_name="test_mentor",
            ),
            MentorAnalysis(
                title="Suggestion 1",
                description="First suggestion",
                severity=AnalysisSeverity.SUGGESTION,
                category="dialogue",
                mentor_name="test_mentor",
            ),
        ]

        result = MentorResult(
            mentor_name="test_mentor",
            mentor_version="1.0.0",
            script_id=script_id,
            summary="Test analysis complete",
            score=85.5,
            analyses=analyses,
            execution_time_ms=1500,
        )

        assert result.mentor_name == "test_mentor"
        assert result.mentor_version == "1.0.0"
        assert result.script_id == script_id
        assert result.summary == "Test analysis complete"
        assert result.score == 85.5
        assert len(result.analyses) == 3
        assert result.execution_time_ms == 1500
        assert result.id is not None
        assert isinstance(result.analysis_date, datetime)

    def test_mentor_result_counts(self):
        """Test MentorResult severity counts."""
        analyses = [
            MentorAnalysis(
                title="Error 1",
                description="Error",
                severity=AnalysisSeverity.ERROR,
                category="test",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Error 2",
                description="Error",
                severity=AnalysisSeverity.ERROR,
                category="test",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Warning 1",
                description="Warning",
                severity=AnalysisSeverity.WARNING,
                category="test",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Suggestion 1",
                description="Suggestion",
                severity=AnalysisSeverity.SUGGESTION,
                category="test",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Info 1",
                description="Info",
                severity=AnalysisSeverity.INFO,
                category="test",
                mentor_name="test",
            ),
        ]

        result = MentorResult(
            mentor_name="test",
            mentor_version="1.0.0",
            script_id=uuid4(),
            summary="Test",
            analyses=analyses,
        )

        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.suggestion_count == 1

    def test_mentor_result_get_analyses_by_category(self):
        """Test getting analyses by category."""
        analyses = [
            MentorAnalysis(
                title="Structure 1",
                description="Structure",
                severity=AnalysisSeverity.ERROR,
                category="structure",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Pacing 1",
                description="Pacing",
                severity=AnalysisSeverity.WARNING,
                category="pacing",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Structure 2",
                description="Structure",
                severity=AnalysisSeverity.INFO,
                category="structure",
                mentor_name="test",
            ),
        ]

        result = MentorResult(
            mentor_name="test",
            mentor_version="1.0.0",
            script_id=uuid4(),
            summary="Test",
            analyses=analyses,
        )

        structure_analyses = result.get_analyses_by_category("structure")
        assert len(structure_analyses) == 2
        assert all(a.category == "structure" for a in structure_analyses)

        pacing_analyses = result.get_analyses_by_category("pacing")
        assert len(pacing_analyses) == 1
        assert pacing_analyses[0].category == "pacing"

    def test_mentor_result_get_analyses_by_scene(self):
        """Test getting analyses by scene."""
        scene_id = uuid4()
        other_scene_id = uuid4()

        analyses = [
            MentorAnalysis(
                title="Scene 1 Issue",
                description="Issue",
                severity=AnalysisSeverity.ERROR,
                category="test",
                mentor_name="test",
                scene_id=scene_id,
            ),
            MentorAnalysis(
                title="General Issue",
                description="Issue",
                severity=AnalysisSeverity.WARNING,
                category="test",
                mentor_name="test",
            ),
            MentorAnalysis(
                title="Scene 1 Other",
                description="Other",
                severity=AnalysisSeverity.INFO,
                category="test",
                mentor_name="test",
                scene_id=scene_id,
            ),
            MentorAnalysis(
                title="Scene 2 Issue",
                description="Issue",
                severity=AnalysisSeverity.ERROR,
                category="test",
                mentor_name="test",
                scene_id=other_scene_id,
            ),
        ]

        result = MentorResult(
            mentor_name="test",
            mentor_version="1.0.0",
            script_id=uuid4(),
            summary="Test",
            analyses=analyses,
        )

        scene_analyses = result.get_analyses_by_scene(scene_id)
        assert len(scene_analyses) == 2
        assert all(a.scene_id == scene_id for a in scene_analyses)


class MockMentor(BaseMentor):
    """Mock mentor for testing."""

    @property
    def name(self) -> str:
        return "mock_mentor"

    @property
    def description(self) -> str:
        return "A mock mentor for testing"

    @property
    def mentor_type(self) -> MentorType:
        return MentorType.STORY_STRUCTURE

    @property
    def categories(self) -> list[str]:
        return ["structure", "pacing"]

    async def analyze_script(
        self,
        script_id,
        db_operations,
        progress_callback=None,
    ):
        """Mock script analysis."""
        analyses = [
            MentorAnalysis(
                title="Mock Analysis",
                description="This is a mock analysis",
                severity=AnalysisSeverity.INFO,
                category="structure",
                mentor_name=self.name,
            )
        ]

        # Silence unused parameter warnings in mock
        _ = db_operations
        _ = progress_callback

        return MentorResult(
            mentor_name=self.name,
            mentor_version=self.version,
            script_id=script_id,
            summary="Mock analysis completed",
            score=75.0,
            analyses=analyses,
            config=self.config,
        )


class TestBaseMentor:
    """Test BaseMentor abstract base class."""

    def test_mentor_creation(self):
        """Test creating a mentor instance."""
        config = {"test_param": "test_value"}
        mentor = MockMentor(config)

        assert mentor.name == "mock_mentor"
        assert mentor.description == "A mock mentor for testing"
        assert mentor.mentor_type == MentorType.STORY_STRUCTURE
        assert mentor.version == "1.0.0"
        assert mentor.categories == ["structure", "pacing"]
        assert mentor.config == config

    def test_mentor_default_config(self):
        """Test mentor with default config."""
        mentor = MockMentor()
        assert mentor.config == {}

    def test_mentor_validate_config_default(self):
        """Test default config validation."""
        mentor = MockMentor()
        assert mentor.validate_config() is True

    def test_mentor_get_config_schema_default(self):
        """Test default config schema."""
        mentor = MockMentor()
        schema = mentor.get_config_schema()

        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema["additionalProperties"] is True

    @pytest.mark.asyncio
    async def test_mentor_analyze_script(self):
        """Test mentor script analysis."""
        from uuid import uuid4

        mentor = MockMentor()
        script_id = uuid4()

        result = await mentor.analyze_script(script_id, None)

        assert isinstance(result, MentorResult)
        assert result.mentor_name == "mock_mentor"
        assert result.script_id == script_id
        assert result.score == 75.0
        assert len(result.analyses) == 1
        assert result.analyses[0].title == "Mock Analysis"

    @pytest.mark.asyncio
    async def test_mentor_analyze_scene_default(self):
        """Test default scene analysis returns empty list."""
        mentor = MockMentor()
        scene_id = uuid4()
        script_id = uuid4()

        analyses = await mentor.analyze_scene(scene_id, script_id, None)
        assert analyses == []

    @pytest.mark.asyncio
    async def test_mentor_analyze_character_default(self):
        """Test default character analysis returns empty list."""
        mentor = MockMentor()
        character_id = uuid4()
        script_id = uuid4()

        analyses = await mentor.analyze_character(character_id, script_id, None)
        assert analyses == []

    def test_mentor_string_representation(self):
        """Test mentor string representations."""
        mentor = MockMentor()

        str_repr = str(mentor)
        assert "mock_mentor" in str_repr
        assert "1.0.0" in str_repr
        assert "story_structure" in str_repr

        repr_str = repr(mentor)
        assert "MockMentor" in repr_str
        assert "mock_mentor" in repr_str
        assert "1.0.0" in repr_str


class TestEnums:
    """Test mentor enums."""

    def test_mentor_type_enum(self):
        """Test MentorType enum values."""
        assert MentorType.STORY_STRUCTURE == "story_structure"
        assert MentorType.CHARACTER_ARC == "character_arc"
        assert MentorType.DIALOGUE == "dialogue"
        assert MentorType.PACING == "pacing"
        assert MentorType.THEME == "theme"
        assert MentorType.GENRE == "genre"
        assert MentorType.FORMATTING == "formatting"

    def test_analysis_severity_enum(self):
        """Test AnalysisSeverity enum values."""
        assert AnalysisSeverity.INFO == "info"
        assert AnalysisSeverity.SUGGESTION == "suggestion"
        assert AnalysisSeverity.WARNING == "warning"
        assert AnalysisSeverity.ERROR == "error"
