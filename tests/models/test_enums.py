"""Tests for model enums."""

from scriptrag.models import (
    AcquisitionMethod,
    BibleStatus,
    BibleType,
    ElementType,
    EventType,
    KnowledgeType,
    NoteSeverity,
    NoteStatus,
    NoteType,
    PlotThreadStatus,
    PlotThreadType,
    SceneDependencyType,
    SceneOrderType,
    TimelineType,
    VerificationStatus,
    WorldElementType,
)


class TestElementType:
    """Test ElementType enum."""

    def test_element_type_values(self):
        """Test ElementType has expected values."""
        assert ElementType.ACTION.value == "action"
        assert ElementType.SCENE_HEADING.value == "scene_heading"
        assert ElementType.CHARACTER.value == "character"
        assert ElementType.DIALOGUE.value == "dialogue"
        assert ElementType.PARENTHETICAL.value == "parenthetical"
        assert ElementType.TRANSITION.value == "transition"
        assert ElementType.SHOT.value == "shot"
        assert ElementType.BONEYARD.value == "boneyard"
        assert ElementType.PAGE_BREAK.value == "page_break"
        assert ElementType.SYNOPSIS.value == "synopsis"
        assert ElementType.SECTION.value == "section"

    def test_element_type_count(self):
        """Test ElementType has expected number of values."""
        assert len(ElementType) == 11

    def test_element_type_string_conversion(self):
        """Test ElementType string conversion."""
        # In Python 3.11+, str() of an enum returns the full name
        assert ElementType.ACTION.value == "action"
        assert ElementType.DIALOGUE.value == "dialogue"
        # String representation includes the enum name
        assert str(ElementType.ACTION) == "ElementType.ACTION"
        assert str(ElementType.DIALOGUE) == "ElementType.DIALOGUE"


class TestSceneOrderType:
    """Test SceneOrderType enum."""

    def test_scene_order_type_values(self):
        """Test SceneOrderType has expected values."""
        assert SceneOrderType.SCRIPT.value == "script"
        assert SceneOrderType.TEMPORAL.value == "temporal"
        assert SceneOrderType.LOGICAL.value == "logical"

    def test_scene_order_type_count(self):
        """Test SceneOrderType has expected number of values."""
        assert len(SceneOrderType) == 3

    def test_scene_order_type_descriptions(self):
        """Test SceneOrderType values represent different orderings."""
        # Script order - as written
        assert SceneOrderType.SCRIPT.value == "script"
        # Temporal order - chronological
        assert SceneOrderType.TEMPORAL.value == "temporal"
        # Logical order - dependency based
        assert SceneOrderType.LOGICAL.value == "logical"


class TestSceneDependencyType:
    """Test SceneDependencyType enum."""

    def test_scene_dependency_type_values(self):
        """Test SceneDependencyType has expected values."""
        assert SceneDependencyType.REQUIRES.value == "requires"
        assert SceneDependencyType.REFERENCES.value == "references"
        assert SceneDependencyType.CONTINUES.value == "continues"
        assert SceneDependencyType.FLASHBACK_TO.value == "flashback_to"

    def test_scene_dependency_type_count(self):
        """Test SceneDependencyType has expected number of values."""
        assert len(SceneDependencyType) == 4


class TestBibleEnums:
    """Test Script Bible related enums."""

    def test_bible_type_values(self):
        """Test BibleType has expected values."""
        assert BibleType.SERIES.value == "series"
        assert BibleType.MOVIE.value == "movie"
        assert BibleType.ANTHOLOGY.value == "anthology"
        assert len(BibleType) == 3

    def test_bible_status_values(self):
        """Test BibleStatus has expected values."""
        assert BibleStatus.ACTIVE.value == "active"
        assert BibleStatus.ARCHIVED.value == "archived"
        assert BibleStatus.DRAFT.value == "draft"
        assert len(BibleStatus) == 3


class TestWorldElementType:
    """Test WorldElementType enum."""

    def test_world_element_type_values(self):
        """Test WorldElementType has expected values."""
        assert WorldElementType.LOCATION.value == "location"
        assert WorldElementType.PROP.value == "prop"
        assert WorldElementType.CONCEPT.value == "concept"
        assert WorldElementType.RULE.value == "rule"
        assert WorldElementType.TECHNOLOGY.value == "technology"
        assert WorldElementType.CULTURE.value == "culture"

    def test_world_element_type_count(self):
        """Test WorldElementType has expected number of values."""
        assert len(WorldElementType) == 6


class TestTimelineEnums:
    """Test Timeline related enums."""

    def test_timeline_type_values(self):
        """Test TimelineType has expected values."""
        assert TimelineType.MAIN.value == "main"
        assert TimelineType.FLASHBACK.value == "flashback"
        assert TimelineType.ALTERNATE.value == "alternate"
        assert TimelineType.PARALLEL.value == "parallel"
        assert len(TimelineType) == 4

    def test_event_type_values(self):
        """Test EventType has expected values."""
        assert EventType.PLOT.value == "plot"
        assert EventType.CHARACTER.value == "character"
        assert EventType.WORLD.value == "world"
        assert EventType.BACKSTORY.value == "backstory"
        assert len(EventType) == 4


class TestNoteEnums:
    """Test Continuity Note related enums."""

    def test_note_type_values(self):
        """Test NoteType has expected values."""
        assert NoteType.ERROR.value == "error"
        assert NoteType.INCONSISTENCY.value == "inconsistency"
        assert NoteType.RULE.value == "rule"
        assert NoteType.REMINDER.value == "reminder"
        assert NoteType.QUESTION.value == "question"
        assert len(NoteType) == 5

    def test_note_severity_values(self):
        """Test NoteSeverity has expected values."""
        assert NoteSeverity.LOW.value == "low"
        assert NoteSeverity.MEDIUM.value == "medium"
        assert NoteSeverity.HIGH.value == "high"
        assert NoteSeverity.CRITICAL.value == "critical"
        assert len(NoteSeverity) == 4

    def test_note_status_values(self):
        """Test NoteStatus has expected values."""
        assert NoteStatus.OPEN.value == "open"
        assert NoteStatus.RESOLVED.value == "resolved"
        assert NoteStatus.IGNORED.value == "ignored"
        assert NoteStatus.DEFERRED.value == "deferred"
        assert len(NoteStatus) == 4


class TestKnowledgeEnums:
    """Test Character Knowledge related enums."""

    def test_knowledge_type_values(self):
        """Test KnowledgeType has expected values."""
        assert KnowledgeType.FACT.value == "fact"
        assert KnowledgeType.SECRET.value == "secret"
        assert KnowledgeType.SKILL.value == "skill"
        assert KnowledgeType.RELATIONSHIP.value == "relationship"
        assert KnowledgeType.LOCATION.value == "location"
        assert KnowledgeType.EVENT.value == "event"
        assert len(KnowledgeType) == 6

    def test_acquisition_method_values(self):
        """Test AcquisitionMethod has expected values."""
        assert AcquisitionMethod.WITNESSED.value == "witnessed"
        assert AcquisitionMethod.TOLD.value == "told"
        assert AcquisitionMethod.DISCOVERED.value == "discovered"
        assert AcquisitionMethod.ASSUMED.value == "assumed"
        assert len(AcquisitionMethod) == 4

    def test_verification_status_values(self):
        """Test VerificationStatus has expected values."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.UNVERIFIED.value == "unverified"
        assert VerificationStatus.VIOLATED.value == "violated"
        assert len(VerificationStatus) == 3


class TestPlotThreadEnums:
    """Test Plot Thread related enums."""

    def test_plot_thread_type_values(self):
        """Test PlotThreadType has expected values."""
        assert PlotThreadType.MAIN.value == "main"
        assert PlotThreadType.SUBPLOT.value == "subplot"
        assert PlotThreadType.ARC.value == "arc"
        assert PlotThreadType.MYSTERY.value == "mystery"
        assert PlotThreadType.ROMANCE.value == "romance"
        assert len(PlotThreadType) == 5

    def test_plot_thread_status_values(self):
        """Test PlotThreadStatus has expected values."""
        assert PlotThreadStatus.ACTIVE.value == "active"
        assert PlotThreadStatus.RESOLVED.value == "resolved"
        assert PlotThreadStatus.ABANDONED.value == "abandoned"
        assert PlotThreadStatus.SUSPENDED.value == "suspended"
        assert len(PlotThreadStatus) == 4


class TestEnumInheritance:
    """Test that all enums properly inherit from str, Enum."""

    def test_all_enums_are_string_enums(self):
        """Test all enums inherit from str and Enum."""
        enums_to_test = [
            ElementType,
            SceneOrderType,
            SceneDependencyType,
            BibleType,
            BibleStatus,
            WorldElementType,
            TimelineType,
            EventType,
            NoteType,
            NoteSeverity,
            NoteStatus,
            KnowledgeType,
            AcquisitionMethod,
            VerificationStatus,
            PlotThreadType,
            PlotThreadStatus,
        ]

        for enum_class in enums_to_test:
            # Get first value
            first_value = next(iter(enum_class))
            # Should be both string and enum
            assert isinstance(first_value, str)
            assert isinstance(first_value.value, str)
            # Value attribute gives the string value
            assert first_value.value == first_value.value


class TestEnumUsageInModels:
    """Test enum usage patterns in models."""

    def test_enum_field_assignment(self):
        """Test that enums can be assigned to model fields."""
        from uuid import uuid4

        from scriptrag.models import SeriesBible

        # Test with BibleStatus
        bible = SeriesBible(
            script_id=uuid4(),  # Use actual UUID
            title="Test Bible",
            status=BibleStatus.DRAFT,  # Using enum directly
        )
        assert bible.status == BibleStatus.DRAFT
        assert bible.status.value == "draft"

    def test_enum_comparison(self):
        """Test enum comparison operations."""
        # Same enum values should be equal
        assert ElementType.ACTION == ElementType.ACTION
        assert BibleStatus.ACTIVE == BibleStatus.ACTIVE

        # Different enum values should not be equal
        assert ElementType.ACTION != ElementType.DIALOGUE
        assert NoteStatus.OPEN != NoteStatus.RESOLVED

        # Can compare with string value
        assert ElementType.ACTION.value == "action"
        assert NoteType.ERROR.value == "error"
