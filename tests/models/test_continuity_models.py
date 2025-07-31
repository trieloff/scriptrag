"""Tests for continuity management models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from scriptrag.models import (
    AcquisitionMethod,
    BibleStatus,
    BibleType,
    CharacterKnowledge,
    CharacterProfile,
    ContinuityNote,
    EventType,
    KnowledgeType,
    NoteSeverity,
    NoteStatus,
    NoteType,
    PlotThread,
    PlotThreadStatus,
    PlotThreadType,
    SeriesBible,
    StoryTimeline,
    TimelineEvent,
    TimelineType,
    VerificationStatus,
    WorldElement,
    WorldElementType,
)


class TestSeriesBible:
    """Test SeriesBible model."""

    def test_series_bible_creation(self):
        """Test creating a series bible."""
        script_id = uuid4()

        bible = SeriesBible(
            script_id=script_id,
            title="Breaking Bad Series Bible",
            description="Complete guide to the Breaking Bad universe",
            version=2,
            created_by="Vince Gilligan",
            status=BibleStatus.ACTIVE,
            bible_type=BibleType.SERIES,
        )

        assert bible.script_id == script_id
        assert bible.title == "Breaking Bad Series Bible"
        assert bible.description == "Complete guide to the Breaking Bad universe"
        assert bible.version == 2
        assert bible.created_by == "Vince Gilligan"
        assert bible.status == BibleStatus.ACTIVE
        assert bible.bible_type == BibleType.SERIES

    def test_series_bible_defaults(self):
        """Test series bible default values."""
        bible = SeriesBible(script_id=uuid4(), title="Test Bible")

        assert bible.description is None
        assert bible.version == 1
        assert bible.created_by is None
        assert bible.status == BibleStatus.ACTIVE
        assert bible.bible_type == BibleType.SERIES

    def test_series_bible_title_validation(self):
        """Test bible title validation."""
        with pytest.raises(ValidationError) as exc_info:
            SeriesBible(script_id=uuid4(), title="")
        assert "Bible title cannot be empty" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            SeriesBible(script_id=uuid4(), title="   ")
        assert "Bible title cannot be empty" in str(exc_info.value)

    def test_series_bible_title_normalization(self):
        """Test bible title is normalized."""
        bible = SeriesBible(script_id=uuid4(), title="  Test Bible  ")
        assert bible.title == "Test Bible"

    def test_series_bible_types(self):
        """Test different bible types."""
        script_id = uuid4()

        # Series bible
        series_bible = SeriesBible(
            script_id=script_id, title="TV Series Bible", bible_type=BibleType.SERIES
        )
        assert series_bible.bible_type == BibleType.SERIES

        # Movie bible
        movie_bible = SeriesBible(
            script_id=script_id, title="Movie Bible", bible_type=BibleType.MOVIE
        )
        assert movie_bible.bible_type == BibleType.MOVIE

        # Anthology bible
        anthology_bible = SeriesBible(
            script_id=script_id, title="Anthology Bible", bible_type=BibleType.ANTHOLOGY
        )
        assert anthology_bible.bible_type == BibleType.ANTHOLOGY

    def test_series_bible_statuses(self):
        """Test different bible statuses."""
        script_id = uuid4()

        # Active bible
        active = SeriesBible(
            script_id=script_id, title="Active Bible", status=BibleStatus.ACTIVE
        )
        assert active.status == BibleStatus.ACTIVE

        # Draft bible
        draft = SeriesBible(
            script_id=script_id, title="Draft Bible", status=BibleStatus.DRAFT
        )
        assert draft.status == BibleStatus.DRAFT

        # Archived bible
        archived = SeriesBible(
            script_id=script_id, title="Archived Bible", status=BibleStatus.ARCHIVED
        )
        assert archived.status == BibleStatus.ARCHIVED


class TestCharacterProfile:
    """Test CharacterProfile model."""

    def test_character_profile_creation(self):
        """Test creating a character profile."""
        character_id = uuid4()
        script_id = uuid4()
        bible_id = uuid4()

        profile = CharacterProfile(
            character_id=character_id,
            script_id=script_id,
            series_bible_id=bible_id,
            full_name="Walter Hartwell White",
            age=50,
            occupation="High School Chemistry Teacher",
            background="Former co-founder of Gray Matter Technologies",
            personality_traits="Prideful, methodical, increasingly ruthless",
            motivations="Provide for family, build legacy",
            fears="Death, being forgotten, losing control",
            goals="Build meth empire, secure family's future",
        )

        assert profile.character_id == character_id
        assert profile.full_name == "Walter Hartwell White"
        assert profile.age == 50
        assert profile.occupation == "High School Chemistry Teacher"

    def test_character_profile_minimal(self):
        """Test character profile with minimal data."""
        profile = CharacterProfile(character_id=uuid4(), script_id=uuid4())

        assert profile.series_bible_id is None
        assert profile.full_name is None
        assert profile.age is None
        assert profile.total_appearances == 0

    def test_character_profile_age_validation(self):
        """Test age validation."""
        # Valid ages
        for age in [0, 1, 50, 100, 200]:
            profile = CharacterProfile(character_id=uuid4(), script_id=uuid4(), age=age)
            assert profile.age == age

        # Invalid ages
        for age in [-1, -50, 201, 300]:
            with pytest.raises(ValidationError) as exc_info:
                CharacterProfile(character_id=uuid4(), script_id=uuid4(), age=age)
            assert "Age must be between 0 and 200" in str(exc_info.value)

    def test_character_profile_complete(self):
        """Test complete character profile."""
        profile = CharacterProfile(
            character_id=uuid4(),
            script_id=uuid4(),
            # Basic info
            full_name="Jesse Bruce Pinkman",
            age=24,
            occupation="Meth Cook",
            # Background
            background="Small-time meth manufacturer, former student",
            personality_traits="Impulsive, sensitive, loyal",
            motivations="Approval, redemption, escape",
            fears="Abandonment, violence, becoming like Walt",
            goals="Find peace, make amends",
            # Physical
            physical_description="Slim build, often wears baggy clothes",
            distinguishing_features="Tattoos, occasional facial hair",
            # Relationships
            family_background="Dysfunctional family, disappointed parents",
            relationship_status="Single, troubled romantic history",
            # Arc
            initial_state="Directionless small-time criminal",
            character_arc="From student to partner to victim to survivor",
            growth_trajectory="Learns consequences, develops conscience",
            # Tracking
            first_appearance_episode_id=uuid4(),
            last_appearance_episode_id=uuid4(),
            total_appearances=62,
            # Notes
            notes="Key relationship with Walter White",
        )

        assert profile.full_name == "Jesse Bruce Pinkman"
        assert profile.age == 24
        assert profile.total_appearances == 62
        assert "conscience" in profile.growth_trajectory


class TestWorldElement:
    """Test WorldElement model."""

    def test_world_element_creation(self):
        """Test creating a world element."""
        script_id = uuid4()
        bible_id = uuid4()

        element = WorldElement(
            script_id=script_id,
            series_bible_id=bible_id,
            element_type=WorldElementType.LOCATION,
            name="Los Pollos Hermanos",
            category="Restaurant/Front Business",
            description="Fast food chicken restaurant chain",
            rules_and_constraints="Must maintain legitimate appearance",
            visual_description="Clean, bright, typical fast food interior",
            importance_level=5,
        )

        assert element.element_type == WorldElementType.LOCATION
        assert element.name == "Los Pollos Hermanos"
        assert element.importance_level == 5

    def test_world_element_types(self):
        """Test different world element types."""
        script_id = uuid4()

        # Location
        location = WorldElement(
            script_id=script_id, element_type=WorldElementType.LOCATION, name="The Lab"
        )
        assert location.element_type == WorldElementType.LOCATION

        # Prop
        prop = WorldElement(
            script_id=script_id, element_type=WorldElementType.PROP, name="Blue Meth"
        )
        assert prop.element_type == WorldElementType.PROP

        # Technology
        tech = WorldElement(
            script_id=script_id,
            element_type=WorldElementType.TECHNOLOGY,
            name="RV Mobile Lab",
        )
        assert tech.element_type == WorldElementType.TECHNOLOGY

    def test_world_element_importance_validation(self):
        """Test importance level validation (1-5)."""
        # Valid importance levels
        for level in range(1, 6):
            element = WorldElement(
                script_id=uuid4(),
                element_type=WorldElementType.PROP,
                name="Test",
                importance_level=level,
            )
            assert element.importance_level == level

    def test_world_element_name_validation(self):
        """Test element name validation."""
        with pytest.raises(ValidationError) as exc_info:
            WorldElement(
                script_id=uuid4(), element_type=WorldElementType.LOCATION, name=""
            )
        assert "Element name cannot be empty" in str(exc_info.value)

    def test_world_element_relationships(self):
        """Test world element relationships."""
        location_ids = [uuid4() for _ in range(3)]
        character_ids = [uuid4() for _ in range(2)]

        element = WorldElement(
            script_id=uuid4(),
            element_type=WorldElementType.PROP,
            name="Ricin Cigarette",
            related_locations=location_ids,
            related_characters=character_ids,
        )

        assert len(element.related_locations) == 3
        assert len(element.related_characters) == 2


class TestStoryTimeline:
    """Test StoryTimeline model."""

    def test_story_timeline_creation(self):
        """Test creating a story timeline."""
        script_id = uuid4()

        timeline = StoryTimeline(
            script_id=script_id,
            name="Main Timeline",
            timeline_type=TimelineType.MAIN,
            description="Primary story chronology",
            start_date="September 7, 2008",
            end_date="September 28, 2010",
            duration_description="2 years, 3 weeks",
        )

        assert timeline.name == "Main Timeline"
        assert timeline.timeline_type == TimelineType.MAIN
        assert timeline.start_date == "September 7, 2008"

    def test_story_timeline_types(self):
        """Test different timeline types."""
        script_id = uuid4()

        # Main timeline
        main = StoryTimeline(
            script_id=script_id, name="Main", timeline_type=TimelineType.MAIN
        )
        assert main.timeline_type == TimelineType.MAIN

        # Flashback timeline
        flashback = StoryTimeline(
            script_id=script_id,
            name="Gray Matter Days",
            timeline_type=TimelineType.FLASHBACK,
        )
        assert flashback.timeline_type == TimelineType.FLASHBACK

    def test_story_timeline_name_validation(self):
        """Test timeline name validation."""
        with pytest.raises(ValidationError) as exc_info:
            StoryTimeline(script_id=uuid4(), name="")
        assert "Timeline name cannot be empty" in str(exc_info.value)


class TestTimelineEvent:
    """Test TimelineEvent model."""

    def test_timeline_event_creation(self):
        """Test creating a timeline event."""
        timeline_id = uuid4()
        script_id = uuid4()
        scene_id = uuid4()

        event = TimelineEvent(
            timeline_id=timeline_id,
            script_id=script_id,
            event_name="Walt's Cancer Diagnosis",
            event_type=EventType.PLOT,
            description="Walter White is diagnosed with lung cancer",
            story_date="September 7, 2008",
            relative_order=1,
            duration_minutes=30,
            scene_id=scene_id,
        )

        assert event.event_name == "Walt's Cancer Diagnosis"
        assert event.event_type == EventType.PLOT
        assert event.duration_minutes == 30

    def test_timeline_event_continuity(self):
        """Test timeline event continuity tracking."""
        event = TimelineEvent(
            timeline_id=uuid4(),
            script_id=uuid4(),
            event_name="Jesse Meets Jane",
            event_type=EventType.CHARACTER,
            establishes=["Jesse's relationship", "Jane's addiction"],
            requires=["Jesse living next door"],
            affects=["Jesse's sobriety", "Future plot events"],
        )

        assert len(event.establishes) == 2
        assert len(event.requires) == 1
        assert len(event.affects) == 2

    def test_timeline_event_name_validation(self):
        """Test event name validation."""
        with pytest.raises(ValidationError) as exc_info:
            TimelineEvent(timeline_id=uuid4(), script_id=uuid4(), event_name="")
        assert "Event name cannot be empty" in str(exc_info.value)


class TestContinuityNote:
    """Test ContinuityNote model."""

    def test_continuity_note_creation(self):
        """Test creating a continuity note."""
        script_id = uuid4()
        scene_id = uuid4()

        note = ContinuityNote(
            script_id=script_id,
            note_type=NoteType.INCONSISTENCY,
            severity=NoteSeverity.HIGH,
            status=NoteStatus.OPEN,
            title="Character Knowledge Error",
            description="Character references event they shouldn't know about",
            suggested_resolution="Add scene where character learns information",
            scene_id=scene_id,
            reported_by="Script Supervisor",
            tags=["timeline", "character-knowledge"],
        )

        assert note.note_type == NoteType.INCONSISTENCY
        assert note.severity == NoteSeverity.HIGH
        assert note.status == NoteStatus.OPEN
        assert len(note.tags) == 2

    def test_continuity_note_validation(self):
        """Test continuity note validation."""
        # Empty title
        with pytest.raises(ValidationError) as exc_info:
            ContinuityNote(
                script_id=uuid4(),
                note_type=NoteType.ERROR,
                title="",
                description="Test",
            )
        assert "Note title cannot be empty" in str(exc_info.value)

        # Empty description
        with pytest.raises(ValidationError) as exc_info:
            ContinuityNote(
                script_id=uuid4(),
                note_type=NoteType.ERROR,
                title="Test",
                description="",
            )
        assert "Note description cannot be empty" in str(exc_info.value)

    def test_continuity_note_resolution(self):
        """Test resolving a continuity note."""
        note = ContinuityNote(
            script_id=uuid4(),
            note_type=NoteType.ERROR,
            title="Timeline Issue",
            description="Event happens before it should",
            status=NoteStatus.OPEN,
        )

        # Resolve the note
        resolution_time = datetime.now(UTC).replace(tzinfo=None)
        note.status = NoteStatus.RESOLVED
        note.resolution_notes = "Reordered scenes to fix timeline"
        note.resolved_at = resolution_time
        note.assigned_to = "Editor"

        assert note.status == NoteStatus.RESOLVED
        assert note.resolved_at == resolution_time
        assert "Reordered scenes" in note.resolution_notes


class TestCharacterKnowledge:
    """Test CharacterKnowledge model."""

    def test_character_knowledge_creation(self):
        """Test creating character knowledge."""
        character_id = uuid4()
        script_id = uuid4()
        scene_id = uuid4()

        knowledge = CharacterKnowledge(
            character_id=character_id,
            script_id=script_id,
            knowledge_type=KnowledgeType.SECRET,
            knowledge_subject="Jesse is manufacturing meth",
            knowledge_description="Walt knows Jesse cooks meth",
            acquired_scene_id=scene_id,
            acquisition_method=AcquisitionMethod.DISCOVERED,
            confidence_level=0.95,
        )

        assert knowledge.knowledge_type == KnowledgeType.SECRET
        assert knowledge.acquisition_method == AcquisitionMethod.DISCOVERED
        assert knowledge.confidence_level == 0.95

    def test_character_knowledge_validation(self):
        """Test knowledge validation."""
        # Empty subject
        with pytest.raises(ValidationError) as exc_info:
            CharacterKnowledge(
                character_id=uuid4(),
                script_id=uuid4(),
                knowledge_type=KnowledgeType.FACT,
                knowledge_subject="",
            )
        assert "Knowledge subject cannot be empty" in str(exc_info.value)

        # Invalid confidence level
        for level in [-0.1, 1.1, 2.0]:
            with pytest.raises(ValidationError) as exc_info:
                CharacterKnowledge(
                    character_id=uuid4(),
                    script_id=uuid4(),
                    knowledge_type=KnowledgeType.FACT,
                    knowledge_subject="Test",
                    confidence_level=level,
                )

    def test_character_knowledge_verification(self):
        """Test knowledge verification status."""
        knowledge = CharacterKnowledge(
            character_id=uuid4(),
            script_id=uuid4(),
            knowledge_type=KnowledgeType.FACT,
            knowledge_subject="Gus owns Los Pollos Hermanos",
            verification_status=VerificationStatus.VERIFIED,
        )

        assert knowledge.verification_status == VerificationStatus.VERIFIED

        # Change to violated
        knowledge.verification_status = VerificationStatus.VIOLATED
        assert knowledge.verification_status == VerificationStatus.VIOLATED


class TestPlotThread:
    """Test PlotThread model."""

    def test_plot_thread_creation(self):
        """Test creating a plot thread."""
        script_id = uuid4()
        introduced_ep = uuid4()
        resolved_ep = uuid4()

        thread = PlotThread(
            script_id=script_id,
            name="Walt's Cancer Journey",
            thread_type=PlotThreadType.MAIN,
            priority=5,
            description="Walter's cancer diagnosis and treatment",
            initial_setup="Walt diagnosed with terminal lung cancer",
            central_conflict="Mortality vs legacy",
            resolution="Goes into remission but consequences remain",
            status=PlotThreadStatus.RESOLVED,
            introduced_episode_id=introduced_ep,
            resolved_episode_id=resolved_ep,
            total_episodes_involved=20,
        )

        assert thread.name == "Walt's Cancer Journey"
        assert thread.thread_type == PlotThreadType.MAIN
        assert thread.priority == 5
        assert thread.status == PlotThreadStatus.RESOLVED

    def test_plot_thread_types(self):
        """Test different plot thread types."""
        script_id = uuid4()

        # Main plot
        main = PlotThread(
            script_id=script_id, name="Main Plot", thread_type=PlotThreadType.MAIN
        )
        assert main.thread_type == PlotThreadType.MAIN

        # Romance subplot
        romance = PlotThread(
            script_id=script_id, name="Love Story", thread_type=PlotThreadType.ROMANCE
        )
        assert romance.thread_type == PlotThreadType.ROMANCE

    def test_plot_thread_priority_validation(self):
        """Test priority validation (1-5)."""
        # Valid priorities
        for priority in range(1, 6):
            thread = PlotThread(script_id=uuid4(), name="Test", priority=priority)
            assert thread.priority == priority

    def test_plot_thread_character_involvement(self):
        """Test character involvement in plot threads."""
        primary_chars = [uuid4() for _ in range(2)]
        supporting_chars = [uuid4() for _ in range(5)]

        thread = PlotThread(
            script_id=uuid4(),
            name="Heist Plot",
            primary_characters=primary_chars,
            supporting_characters=supporting_chars,
        )

        assert len(thread.primary_characters) == 2
        assert len(thread.supporting_characters) == 5
