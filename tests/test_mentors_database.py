"""Tests for mentor database operations."""

import tempfile
from pathlib import Path
from uuid import uuid4

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.schema import create_database
from scriptrag.mentors.base import (
    AnalysisSeverity,
    MentorAnalysis,
    MentorResult,
)
from scriptrag.mentors.database import MentorDatabaseOperations


class TestMentorDatabaseOperations:
    """Test MentorDatabaseOperations class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"

        # Create database with schema
        create_database(self.db_path)

        # Set up database operations
        self.connection = DatabaseConnection(str(self.db_path))
        self.mentor_db = MentorDatabaseOperations(self.connection)

    def teardown_method(self):
        """Clean up test fixtures."""
        if hasattr(self, "connection"):
            self.connection.close()

        # Clean up temporary files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_result(self, script_id=None, mentor_name="test_mentor"):
        """Create a test MentorResult."""
        if script_id is None:
            script_id = uuid4()

        analyses = [
            MentorAnalysis(
                title="Test Error",
                description="This is a test error",
                severity=AnalysisSeverity.ERROR,
                category="structure",
                mentor_name=mentor_name,
                scene_id=uuid4(),
                recommendations=["Fix this", "Try that"],
                confidence=0.9,
            ),
            MentorAnalysis(
                title="Test Warning",
                description="This is a test warning",
                severity=AnalysisSeverity.WARNING,
                category="pacing",
                mentor_name=mentor_name,
                character_id=uuid4(),
                examples=["Example 1", "Example 2"],
                confidence=0.7,
            ),
            MentorAnalysis(
                title="Test Suggestion",
                description="This is a test suggestion",
                severity=AnalysisSeverity.SUGGESTION,
                category="dialogue",
                mentor_name=mentor_name,
                metadata={"custom_field": "custom_value"},
            ),
        ]

        return MentorResult(
            mentor_name=mentor_name,
            mentor_version="1.0.0",
            script_id=script_id,
            summary="Test analysis completed successfully",
            score=75.5,
            analyses=analyses,
            execution_time_ms=1500,
            config={"test_param": "test_value"},
        )

    def test_store_mentor_result(self):
        """Test storing a mentor result."""
        result = self._create_test_result()

        success = self.mentor_db.store_mentor_result(result)
        assert success is True

    def test_store_mentor_result_with_duplicate_id(self):
        """Test storing a mentor result with duplicate ID (should replace)."""
        result = self._create_test_result()

        # Store first time
        success1 = self.mentor_db.store_mentor_result(result)
        assert success1 is True

        # Modify and store again with same ID
        result.summary = "Updated summary"
        success2 = self.mentor_db.store_mentor_result(result)
        assert success2 is True

        # Retrieve and verify update
        retrieved = self.mentor_db.get_mentor_result(result.id)
        assert retrieved is not None
        assert retrieved.summary == "Updated summary"

    def test_get_mentor_result(self):
        """Test retrieving a mentor result."""
        result = self._create_test_result()

        # Store result
        self.mentor_db.store_mentor_result(result)

        # Retrieve result
        retrieved = self.mentor_db.get_mentor_result(result.id)

        assert retrieved is not None
        assert retrieved.id == result.id
        assert retrieved.mentor_name == result.mentor_name
        assert retrieved.mentor_version == result.mentor_version
        assert retrieved.script_id == result.script_id
        assert retrieved.summary == result.summary
        assert retrieved.score == result.score
        assert len(retrieved.analyses) == len(result.analyses)

        # Check analyses
        assert retrieved.error_count == result.error_count
        assert retrieved.warning_count == result.warning_count
        assert retrieved.suggestion_count == result.suggestion_count

    def test_get_nonexistent_mentor_result(self):
        """Test retrieving a non-existent mentor result."""
        nonexistent_id = uuid4()
        result = self.mentor_db.get_mentor_result(nonexistent_id)
        assert result is None

    def test_get_script_mentor_results(self):
        """Test getting all mentor results for a script."""
        script_id = uuid4()

        # Create multiple results for the same script
        result1 = self._create_test_result(script_id, "mentor_1")
        result2 = self._create_test_result(script_id, "mentor_2")
        result3 = self._create_test_result(uuid4(), "mentor_1")  # Different script

        # Store results
        self.mentor_db.store_mentor_result(result1)
        self.mentor_db.store_mentor_result(result2)
        self.mentor_db.store_mentor_result(result3)

        # Get results for the script
        results = self.mentor_db.get_script_mentor_results(script_id)

        assert len(results) == 2
        result_ids = {r.id for r in results}
        assert result1.id in result_ids
        assert result2.id in result_ids
        assert result3.id not in result_ids

    def test_get_script_mentor_results_filtered_by_mentor(self):
        """Test getting script results filtered by mentor name."""
        script_id = uuid4()

        # Create results from different mentors
        result1 = self._create_test_result(script_id, "mentor_1")
        result2 = self._create_test_result(script_id, "mentor_2")
        result3 = self._create_test_result(script_id, "mentor_1")

        # Store results
        self.mentor_db.store_mentor_result(result1)
        self.mentor_db.store_mentor_result(result2)
        self.mentor_db.store_mentor_result(result3)

        # Get results filtered by mentor
        results = self.mentor_db.get_script_mentor_results(script_id, "mentor_1")

        assert len(results) == 2
        assert all(r.mentor_name == "mentor_1" for r in results)

    def test_get_scene_analyses(self):
        """Test getting analyses for a specific scene."""
        scene_id = uuid4()
        other_scene_id = uuid4()

        # Create result with analyses for different scenes
        result = self._create_test_result()
        result.analyses[0].scene_id = scene_id  # First analysis for our scene
        result.analyses[1].scene_id = other_scene_id  # Second analysis for other scene
        result.analyses[2].scene_id = None  # Third analysis not scene-specific

        # Store result
        self.mentor_db.store_mentor_result(result)

        # Get analyses for the scene
        analyses = self.mentor_db.get_scene_analyses(scene_id)

        assert len(analyses) == 1
        assert analyses[0].scene_id == scene_id
        assert analyses[0].title == "Test Error"

    def test_get_scene_analyses_filtered_by_mentor(self):
        """Test getting scene analyses filtered by mentor."""
        scene_id = uuid4()

        # Create results from different mentors with same scene
        result1 = self._create_test_result(mentor_name="mentor_1")
        result1.analyses[0].scene_id = scene_id

        result2 = self._create_test_result(mentor_name="mentor_2")
        result2.analyses[0].scene_id = scene_id

        # Store results
        self.mentor_db.store_mentor_result(result1)
        self.mentor_db.store_mentor_result(result2)

        # Get analyses filtered by mentor
        analyses = self.mentor_db.get_scene_analyses(scene_id, "mentor_1")

        assert len(analyses) == 1
        assert analyses[0].mentor_name == "mentor_1"

    def test_delete_mentor_result(self):
        """Test deleting a mentor result."""
        result = self._create_test_result()

        # Store result
        self.mentor_db.store_mentor_result(result)

        # Verify it exists
        retrieved = self.mentor_db.get_mentor_result(result.id)
        assert retrieved is not None

        # Delete result
        success = self.mentor_db.delete_mentor_result(result.id)
        assert success is True

        # Verify it's gone
        retrieved = self.mentor_db.get_mentor_result(result.id)
        assert retrieved is None

    def test_delete_nonexistent_mentor_result(self):
        """Test deleting a non-existent mentor result."""
        nonexistent_id = uuid4()
        success = self.mentor_db.delete_mentor_result(nonexistent_id)
        assert success is False

    def test_search_analyses(self):
        """Test searching mentor analyses."""
        result = self._create_test_result()
        self.mentor_db.store_mentor_result(result)

        # Search for "error"
        analyses = self.mentor_db.search_analyses("error")
        assert len(analyses) >= 1

        # Should find the "Test Error" analysis
        error_analysis = next((a for a in analyses if a.title == "Test Error"), None)
        assert error_analysis is not None

    def test_search_analyses_with_filters(self):
        """Test searching analyses with filters."""
        result = self._create_test_result()
        self.mentor_db.store_mentor_result(result)

        # Search with mentor filter
        analyses = self.mentor_db.search_analyses("test", mentor_name="test_mentor")
        assert len(analyses) >= 1
        assert all(a.mentor_name == "test_mentor" for a in analyses)

        # Search with category filter
        analyses = self.mentor_db.search_analyses("test", category="structure")
        assert len(analyses) >= 1
        assert all(a.category == "structure" for a in analyses)

        # Search with severity filter
        analyses = self.mentor_db.search_analyses(
            "test", severity=AnalysisSeverity.ERROR
        )
        assert len(analyses) >= 1
        assert all(a.severity == AnalysisSeverity.ERROR for a in analyses)

    def test_get_mentor_statistics(self):
        """Test getting mentor statistics."""
        script_id = uuid4()

        # Create result with various severity levels
        result = self._create_test_result(script_id)
        self.mentor_db.store_mentor_result(result)

        # Get statistics
        stats = self.mentor_db.get_mentor_statistics(script_id)

        assert "total_analyses" in stats
        assert "error_count" in stats
        assert "warning_count" in stats
        assert "suggestion_count" in stats
        assert "info_count" in stats
        assert "average_confidence" in stats
        assert "unique_mentors" in stats

        assert stats["total_analyses"] == 3
        assert stats["error_count"] == 1
        assert stats["warning_count"] == 1
        assert stats["suggestion_count"] == 1
        assert stats["info_count"] == 0
        assert stats["unique_mentors"] == 1
        assert 0.0 <= stats["average_confidence"] <= 1.0

    def test_get_mentor_statistics_empty_script(self):
        """Test getting statistics for script with no analyses."""
        script_id = uuid4()
        stats = self.mentor_db.get_mentor_statistics(script_id)

        assert stats["total_analyses"] == 0
        assert stats["error_count"] == 0
        assert stats["warning_count"] == 0
        assert stats["suggestion_count"] == 0
        assert stats["info_count"] == 0
        assert stats["average_confidence"] == 0.0
        assert stats["unique_mentors"] == 0

    def test_mentor_schema_creation(self):
        """Test that mentor schema is created properly."""
        # The schema should be created in setup_method
        # Let's verify the tables exist
        with self.connection.transaction() as conn:
            # Check mentor_results table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='mentor_results'"
            )
            assert cursor.fetchone() is not None

            # Check mentor_analyses table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='mentor_analyses'"
            )
            assert cursor.fetchone() is not None

            # Check mentor_analyses_fts table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='mentor_analyses_fts'"
            )
            assert cursor.fetchone() is not None

    def test_analysis_serialization_round_trip(self):
        """Test that analyses can be serialized and deserialized correctly."""
        # Create analysis with complex data
        original_analysis = MentorAnalysis(
            title="Complex Analysis",
            description='Analysis with unicode: café, emoji: 🎬, quotes: "test"',
            severity=AnalysisSeverity.WARNING,
            category="complex",
            mentor_name="test_mentor",
            scene_id=uuid4(),
            character_id=uuid4(),
            element_id=uuid4(),
            recommendations=["Fix unicode", "Handle special chars"],
            examples=["Example with 'quotes'", "Example with unicode: café"],
            metadata={"unicode": "café", "emoji": "🎬", "nested": {"key": "value"}},
            confidence=0.85,
        )

        result = MentorResult(
            mentor_name="test_mentor",
            mentor_version="1.0.0",
            script_id=uuid4(),
            summary="Complex test",
            analyses=[original_analysis],
        )

        # Store and retrieve
        self.mentor_db.store_mentor_result(result)
        retrieved_result = self.mentor_db.get_mentor_result(result.id)

        assert retrieved_result is not None
        assert len(retrieved_result.analyses) == 1

        retrieved_analysis = retrieved_result.analyses[0]

        # Verify all fields are preserved
        assert retrieved_analysis.title == original_analysis.title
        assert retrieved_analysis.description == original_analysis.description
        assert retrieved_analysis.severity == original_analysis.severity
        assert retrieved_analysis.category == original_analysis.category
        assert retrieved_analysis.mentor_name == original_analysis.mentor_name
        assert retrieved_analysis.scene_id == original_analysis.scene_id
        assert retrieved_analysis.character_id == original_analysis.character_id
        assert retrieved_analysis.element_id == original_analysis.element_id
        assert retrieved_analysis.recommendations == original_analysis.recommendations
        assert retrieved_analysis.examples == original_analysis.examples
        assert retrieved_analysis.metadata == original_analysis.metadata
        assert retrieved_analysis.confidence == original_analysis.confidence
