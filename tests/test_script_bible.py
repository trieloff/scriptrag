"""Tests for Script Bible and continuity management functionality."""

from datetime import datetime
from uuid import uuid4

import pytest

from scriptrag.database.bible import ScriptBibleOperations
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.continuity import ContinuityIssue, ContinuityValidator
from scriptrag.database.schema import create_database


@pytest.fixture
def bible_connection():
    """Create a temporary database connection for testing."""
    db_path = ":memory:"
    schema = create_database(db_path)
    schema.create_schema()  # Actually create the tables
    with DatabaseConnection(db_path) as connection:
        yield connection


@pytest.fixture
def sample_script_data(bible_connection):
    """Create sample script data for testing."""
    script_id = str(uuid4())
    character_id = str(uuid4())
    episode_id = str(uuid4())
    scene_id = str(uuid4())

    # Insert sample script
    bible_connection.execute(
        """
        INSERT INTO scripts (id, title, is_series, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            script_id,
            "Test Series",
            True,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )

    # Insert sample character
    bible_connection.execute(
        """
        INSERT INTO characters (id, script_id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            character_id,
            script_id,
            "JOHN",
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )

    # Insert sample episode
    bible_connection.execute(
        """
        INSERT INTO episodes (id, script_id, number, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            episode_id,
            script_id,
            1,
            "Pilot",
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )

    # Insert sample scene
    bible_connection.execute(
        """
        INSERT INTO scenes (id, script_id, episode_id, heading, script_order,
                           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scene_id,
            script_id,
            episode_id,
            "INT. OFFICE - DAY",
            1,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )

    return {
        "script_id": script_id,
        "character_id": character_id,
        "episode_id": episode_id,
        "scene_id": scene_id,
    }


class TestScriptBibleOperations:
    """Test Script Bible database operations."""

    def test_create_series_bible(self, bible_connection, sample_script_data):
        """Test creating a series bible."""
        bible_ops = ScriptBibleOperations(bible_connection)

        bible_id = bible_ops.create_series_bible(
            script_id=sample_script_data["script_id"],
            title="Test Series Bible",
            description="A comprehensive bible for testing",
            created_by="Test Creator",
            bible_type="series",
        )

        assert bible_id is not None

        # Verify the bible was created
        bible = bible_ops.get_series_bible(bible_id)
        assert bible is not None
        assert bible.title == "Test Series Bible"
        assert bible.description == "A comprehensive bible for testing"
        assert bible.created_by == "Test Creator"
        assert bible.bible_type == "series"
        assert bible.script_id == sample_script_data["script_id"]

    def test_get_series_bibles_for_script(self, bible_connection, sample_script_data):
        """Test getting all bibles for a script."""
        bible_ops = ScriptBibleOperations(bible_connection)

        # Create multiple bibles
        bible_ops.create_series_bible(
            script_id=sample_script_data["script_id"],
            title="Bible 1",
            bible_type="series",
        )
        bible_ops.create_series_bible(
            script_id=sample_script_data["script_id"],
            title="Bible 2",
            bible_type="movie",
        )

        bibles = bible_ops.get_series_bibles_for_script(sample_script_data["script_id"])
        assert len(bibles) == 2
        assert {bible.title for bible in bibles} == {"Bible 1", "Bible 2"}

    def test_update_series_bible(self, bible_connection, sample_script_data):
        """Test updating a series bible."""
        bible_ops = ScriptBibleOperations(bible_connection)

        bible_id = bible_ops.create_series_bible(
            script_id=sample_script_data["script_id"],
            title="Original Title",
            bible_type="series",
        )

        # Update the bible
        updated = bible_ops.update_series_bible(
            bible_id=bible_id,
            title="Updated Title",
            description="Updated description",
            status="archived",
            version=2,
        )

        assert updated is True

        # Verify updates
        bible = bible_ops.get_series_bible(bible_id)
        assert bible.title == "Updated Title"
        assert bible.description == "Updated description"
        assert bible.status == "archived"
        assert bible.version == 2

    def test_create_character_profile(self, bible_connection, sample_script_data):
        """Test creating a character profile."""
        bible_ops = ScriptBibleOperations(bible_connection)

        profile_id = bible_ops.create_character_profile(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            full_name="John Smith",
            age=35,
            occupation="Detective",
            background="Former military",
            personality_traits="Determined, stubborn",
            motivations="Justice for his partner",
            fears="Losing control",
            goals="Solve the case",
        )

        assert profile_id is not None

        # Verify the profile was created
        profile = bible_ops.get_character_profile(
            sample_script_data["character_id"], sample_script_data["script_id"]
        )
        assert profile is not None
        assert profile.full_name == "John Smith"
        assert profile.age == 35
        assert profile.occupation == "Detective"
        assert profile.background == "Former military"

    def test_update_character_appearances(self, bible_connection, sample_script_data):
        """Test updating character appearance tracking."""
        bible_ops = ScriptBibleOperations(bible_connection)

        # Update appearances (should create profile if none exists)
        bible_ops.update_character_appearances(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            episode_id=sample_script_data["episode_id"],
        )

        # Verify profile was created with appearance data
        profile = bible_ops.get_character_profile(
            sample_script_data["character_id"], sample_script_data["script_id"]
        )
        assert profile is not None
        assert profile.first_appearance_episode_id == sample_script_data["episode_id"]
        assert profile.last_appearance_episode_id == sample_script_data["episode_id"]
        assert profile.total_appearances == 1

    def test_create_world_element(self, bible_connection, sample_script_data):
        """Test creating a world element."""
        bible_ops = ScriptBibleOperations(bible_connection)

        element_id = bible_ops.create_world_element(
            script_id=sample_script_data["script_id"],
            element_type="location",
            name="Police Station",
            description="Main police headquarters",
            category="government",
            importance_level=4,
            rules_and_constraints="24/7 operations, high security",
            related_characters=[sample_script_data["character_id"]],
        )

        assert element_id is not None

        # Verify the element was created
        elements = bible_ops.get_world_elements_by_type(
            sample_script_data["script_id"], "location"
        )
        assert len(elements) == 1
        assert elements[0].name == "Police Station"
        assert elements[0].element_type == "location"
        assert elements[0].description == "Main police headquarters"
        assert elements[0].importance_level == 4

    def test_create_story_timeline(self, bible_connection, sample_script_data):
        """Test creating a story timeline."""
        bible_ops = ScriptBibleOperations(bible_connection)

        timeline_id = bible_ops.create_story_timeline(
            script_id=sample_script_data["script_id"],
            name="Main Timeline",
            timeline_type="main",
            description="Primary story chronology",
            start_date="Day 1",
            end_date="Day 7",
            reference_episodes=[sample_script_data["episode_id"]],
        )

        assert timeline_id is not None

    def test_add_timeline_event(self, bible_connection, sample_script_data):
        """Test adding a timeline event."""
        bible_ops = ScriptBibleOperations(bible_connection)

        timeline_id = bible_ops.create_story_timeline(
            script_id=sample_script_data["script_id"], name="Main Timeline"
        )

        event_id = bible_ops.add_timeline_event(
            timeline_id=timeline_id,
            script_id=sample_script_data["script_id"],
            event_name="Case Discovery",
            event_type="plot",
            description="John discovers the mysterious case",
            story_date="Day 1",
            relative_order=1,
            episode_id=sample_script_data["episode_id"],
            related_characters=[sample_script_data["character_id"]],
            establishes=["Main conflict", "Character motivation"],
        )

        assert event_id is not None

        # Verify the event was created
        events = bible_ops.get_timeline_events(timeline_id)
        assert len(events) == 1
        assert events[0].event_name == "Case Discovery"
        assert events[0].event_type == "plot"
        assert events[0].relative_order == 1

    def test_create_continuity_note(self, bible_connection, sample_script_data):
        """Test creating a continuity note."""
        bible_ops = ScriptBibleOperations(bible_connection)

        note_id = bible_ops.create_continuity_note(
            script_id=sample_script_data["script_id"],
            note_type="inconsistency",
            title="Character age discrepancy",
            description="John's age mentioned differently in episodes 1 and 3",
            severity="medium",
            episode_id=sample_script_data["episode_id"],
            character_id=sample_script_data["character_id"],
            suggested_resolution="Establish consistent age of 35",
            tags=["character", "age", "continuity"],
        )

        assert note_id is not None

        # Verify the note was created
        notes = bible_ops.get_continuity_notes(sample_script_data["script_id"])
        assert len(notes) == 1
        assert notes[0].title == "Character age discrepancy"
        assert notes[0].note_type == "inconsistency"
        assert notes[0].severity == "medium"
        assert notes[0].status == "open"

    def test_resolve_continuity_note(self, bible_connection, sample_script_data):
        """Test resolving a continuity note."""
        bible_ops = ScriptBibleOperations(bible_connection)

        note_id = bible_ops.create_continuity_note(
            script_id=sample_script_data["script_id"],
            note_type="error",
            title="Test Issue",
            description="Test description",
        )

        resolved = bible_ops.resolve_continuity_note(
            note_id=note_id,
            resolution_notes="Fixed age reference in episode 3",
            resolved_by="Script Editor",
        )

        assert resolved is True

        # Verify the note was resolved
        notes = bible_ops.get_continuity_notes(sample_script_data["script_id"])
        assert len(notes) == 1
        assert notes[0].status == "resolved"
        assert notes[0].resolution_notes == "Fixed age reference in episode 3"
        assert notes[0].resolved_at is not None

    def test_add_character_knowledge(self, bible_connection, sample_script_data):
        """Test adding character knowledge."""
        bible_ops = ScriptBibleOperations(bible_connection)

        knowledge_id = bible_ops.add_character_knowledge(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            knowledge_type="secret",
            knowledge_subject="The real killer's identity",
            knowledge_description="John discovered who really committed the murder",
            acquired_episode_id=sample_script_data["episode_id"],
            acquisition_method="discovered",
            confidence_level=0.9,
        )

        assert knowledge_id is not None

        # Verify the knowledge was added
        knowledge_list = bible_ops.get_character_knowledge(
            sample_script_data["character_id"], sample_script_data["script_id"]
        )
        assert len(knowledge_list) == 1
        assert knowledge_list[0].knowledge_type == "secret"
        assert knowledge_list[0].knowledge_subject == "The real killer's identity"
        assert knowledge_list[0].acquisition_method == "discovered"

    def test_create_plot_thread(self, bible_connection, sample_script_data):
        """Test creating a plot thread."""
        bible_ops = ScriptBibleOperations(bible_connection)

        thread_id = bible_ops.create_plot_thread(
            script_id=sample_script_data["script_id"],
            name="Murder Investigation",
            thread_type="main",
            priority=5,
            description="Main plot about solving the murder case",
            initial_setup="Body found in alley",
            central_conflict="Evidence points to innocent suspect",
            introduced_episode_id=sample_script_data["episode_id"],
            primary_characters=[sample_script_data["character_id"]],
        )

        assert thread_id is not None

        # Verify the thread was created
        threads = bible_ops.get_plot_threads(sample_script_data["script_id"])
        assert len(threads) == 1
        assert threads[0].name == "Murder Investigation"
        assert threads[0].thread_type == "main"
        assert threads[0].priority == 5
        assert threads[0].status == "active"


class TestContinuityValidator:
    """Test continuity validation functionality."""

    def test_create_continuity_issue(self):
        """Test creating a continuity issue."""
        issue = ContinuityIssue(
            issue_type="knowledge_temporal_violation",
            severity="high",
            title="Character knows secret before discovery",
            description="John references the killer's identity before discovering it",
            character_id="char123",
            episode_id="ep123",
        )

        assert issue.issue_type == "knowledge_temporal_violation"
        assert issue.severity == "high"
        assert issue.title == "Character knows secret before discovery"
        assert issue.character_id == "char123"

    def test_validate_character_knowledge(self, bible_connection, sample_script_data):
        """Test character knowledge validation."""
        bible_ops = ScriptBibleOperations(bible_connection)
        validator = ContinuityValidator(bible_connection)

        # Create episode 2
        episode2_id = str(uuid4())
        bible_connection.execute(
            """
            INSERT INTO episodes (id, script_id, number, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                episode2_id,
                sample_script_data["script_id"],
                2,
                "Episode 2",
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )

        # Add knowledge that violates temporal order (used before acquired)
        bible_ops.add_character_knowledge(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            knowledge_type="secret",
            knowledge_subject="The villain's plan",
            acquired_episode_id=episode2_id,  # Acquired in episode 2
            first_used_episode_id=sample_script_data[
                "episode_id"
            ],  # But used in episode 1
        )

        # Run validation
        issues = validator._validate_character_knowledge(
            sample_script_data["script_id"]
        )

        # Should find the temporal violation
        temporal_issues = [
            i for i in issues if i.issue_type == "knowledge_temporal_violation"
        ]
        assert len(temporal_issues) > 0
        assert temporal_issues[0].severity == "high"

    def test_validate_plot_threads(self, bible_connection, sample_script_data):
        """Test plot thread validation."""
        bible_ops = ScriptBibleOperations(bible_connection)
        validator = ContinuityValidator(bible_connection)

        # Create a high-priority thread that's been active for many episodes
        bible_ops.create_plot_thread(
            script_id=sample_script_data["script_id"],
            name="Stagnant Main Plot",
            thread_type="main",
            priority=5,
            total_episodes_involved=15,  # Many episodes
            introduced_episode_id=sample_script_data["episode_id"],
        )

        # Run validation
        issues = validator._validate_plot_threads(sample_script_data["script_id"])

        # Should find stagnant thread issue
        stagnant_issues = [i for i in issues if i.issue_type == "plot_thread_stagnant"]
        assert len(stagnant_issues) > 0
        assert stagnant_issues[0].severity == "medium"

    def test_validate_character_arcs(self, bible_connection, sample_script_data):
        """Test character arc validation."""
        bible_ops = ScriptBibleOperations(bible_connection)
        validator = ContinuityValidator(bible_connection)

        # Create character profile with many appearances but no arc
        bible_ops.create_character_profile(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            total_appearances=15,  # Many appearances, no arc defined
        )

        # Run validation
        issues = validator._validate_character_arcs(sample_script_data["script_id"])

        # Should find missing arc issue
        arc_issues = [i for i in issues if i.issue_type == "character_arc_missing"]
        assert len(arc_issues) > 0
        assert arc_issues[0].severity == "low"

    def test_comprehensive_continuity_validation(
        self, bible_connection, sample_script_data
    ):
        """Test comprehensive continuity validation."""
        validator = ContinuityValidator(bible_connection)

        # Run complete validation
        issues = validator.validate_script_continuity(sample_script_data["script_id"])

        # Should return a list (may be empty for minimal test data)
        assert isinstance(issues, list)

    def test_create_continuity_notes_from_issues(
        self, bible_connection, sample_script_data
    ):
        """Test creating continuity notes from validation issues."""
        validator = ContinuityValidator(bible_connection)
        bible_ops = ScriptBibleOperations(bible_connection)

        # Create some issues
        issues = [
            ContinuityIssue(
                issue_type="test_error",
                severity="high",
                title="Test Issue 1",
                description="First test issue",
                character_id=sample_script_data["character_id"],
            ),
            ContinuityIssue(
                issue_type="test_warning",
                severity="medium",
                title="Test Issue 2",
                description="Second test issue",
                episode_id=sample_script_data["episode_id"],
            ),
        ]

        # Create notes from issues
        note_ids = validator.create_continuity_notes_from_issues(
            script_id=sample_script_data["script_id"],
            issues=issues,
            reported_by="Test Suite",
        )

        assert len(note_ids) == 2

        # Verify notes were created
        notes = bible_ops.get_continuity_notes(sample_script_data["script_id"])
        assert len(notes) == 2
        assert {note.title for note in notes} == {"Test Issue 1", "Test Issue 2"}

    def test_generate_continuity_report(self, bible_connection, sample_script_data):
        """Test generating a continuity report."""
        validator = ContinuityValidator(bible_connection)
        bible_ops = ScriptBibleOperations(bible_connection)

        # Add some test data
        bible_ops.create_continuity_note(
            script_id=sample_script_data["script_id"],
            note_type="error",
            title="Test Note",
            description="Test description",
            severity="high",
        )

        # Generate report
        report = validator.generate_continuity_report(sample_script_data["script_id"])

        assert report["script_id"] == sample_script_data["script_id"]
        assert report["script_title"] == "Test Series"
        assert report["is_series"] is True
        assert "generated_at" in report
        assert "validation_results" in report
        assert "existing_notes" in report
        assert "recommendations" in report

        # Check report structure
        assert "issue_statistics" in report["validation_results"]
        assert "note_statistics" in report["existing_notes"]
        assert isinstance(report["recommendations"], list)


class TestScriptBibleIntegration:
    """Integration tests for Script Bible functionality."""

    def test_full_bible_workflow(self, bible_connection, sample_script_data):
        """Test a complete Script Bible workflow."""
        bible_ops = ScriptBibleOperations(bible_connection)
        validator = ContinuityValidator(bible_connection)

        # 1. Create a series bible
        bible_id = bible_ops.create_series_bible(
            script_id=sample_script_data["script_id"],
            title="Integration Test Bible",
            description="Complete workflow test",
        )

        # 2. Create character profile
        profile_id = bible_ops.create_character_profile(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            full_name="John Detective",
            age=35,
            character_arc="From naive rookie to experienced investigator",
        )

        # 3. Create world elements
        element_id = bible_ops.create_world_element(
            script_id=sample_script_data["script_id"],
            element_type="location",
            name="Crime Scene",
            importance_level=5,
        )

        # 4. Add character knowledge
        knowledge_id = bible_ops.add_character_knowledge(
            character_id=sample_script_data["character_id"],
            script_id=sample_script_data["script_id"],
            knowledge_type="fact",
            knowledge_subject="Victim's identity",
            acquired_episode_id=sample_script_data["episode_id"],
        )

        # 5. Create plot thread
        thread_id = bible_ops.create_plot_thread(
            script_id=sample_script_data["script_id"],
            name="Main Investigation",
            thread_type="main",
            priority=5,
        )

        # 6. Run continuity validation
        issues = validator.validate_script_continuity(sample_script_data["script_id"])

        # 7. Generate report
        report = validator.generate_continuity_report(sample_script_data["script_id"])

        # Verify all components were created
        assert bible_id is not None
        assert profile_id is not None
        assert element_id is not None
        assert knowledge_id is not None
        assert thread_id is not None
        assert isinstance(issues, list)
        assert report["script_id"] == sample_script_data["script_id"]

        # Verify relationships
        bible = bible_ops.get_series_bible(bible_id)
        assert bible.script_id == sample_script_data["script_id"]

        profile = bible_ops.get_character_profile(
            sample_script_data["character_id"], sample_script_data["script_id"]
        )
        assert profile.character_id == sample_script_data["character_id"]

        elements = bible_ops.get_world_elements_by_type(sample_script_data["script_id"])
        assert len(elements) == 1
        assert elements[0].name == "Crime Scene"

    def test_bible_filtering_and_search(self, bible_connection, sample_script_data):
        """Test filtering and search functionality."""
        bible_ops = ScriptBibleOperations(bible_connection)

        # Create multiple items with different attributes
        bible_ops.create_continuity_note(
            script_id=sample_script_data["script_id"],
            note_type="error",
            title="Critical Error",
            description="Critical issue",
            severity="critical",
            status="open",
        )

        bible_ops.create_continuity_note(
            script_id=sample_script_data["script_id"],
            note_type="reminder",
            title="Minor Reminder",
            description="Minor issue",
            severity="low",
            status="resolved",
        )

        # Test filtering by status
        open_notes = bible_ops.get_continuity_notes(
            sample_script_data["script_id"], status="open"
        )
        assert len(open_notes) == 1
        assert open_notes[0].title == "Critical Error"

        # Test filtering by severity
        critical_notes = bible_ops.get_continuity_notes(
            sample_script_data["script_id"], severity="critical"
        )
        assert len(critical_notes) == 1
        assert critical_notes[0].title == "Critical Error"

        # Test filtering by type
        error_notes = bible_ops.get_continuity_notes(
            sample_script_data["script_id"], note_type="error"
        )
        assert len(error_notes) == 1
        assert error_notes[0].title == "Critical Error"
