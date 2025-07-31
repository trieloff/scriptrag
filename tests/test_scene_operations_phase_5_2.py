"""Tests for Phase 5.2 Scene Operations Implementation.

Tests the enhanced scene operations including:
- Update operations with graph propagation
- Delete operations with reference maintenance
- Inject operations with full re-indexing
- Story continuity validation
"""

from unittest.mock import Mock

import pytest

from scriptrag.database import DatabaseConnection
from scriptrag.database.operations import GraphOperations as GraphOps
from scriptrag.models import Scene


class TestPhase52SceneOperations:
    """Test enhanced scene operations for Phase 5.2."""

    @pytest.fixture
    def db_connection(self, tmp_path):
        """Create a test database connection."""
        db_path = tmp_path / "test_scene_ops.db"
        conn = DatabaseConnection(str(db_path))

        # Initialize database schema
        from scriptrag.database import initialize_database

        initialize_database(str(db_path))

        return conn

    @pytest.fixture
    def graph_ops(self, db_connection):
        """Create graph operations instance."""
        return GraphOps(db_connection)

    @pytest.fixture
    def sample_script_data(self):
        """Create sample script data for testing."""
        return {
            "script_node_id": "script_001",
            "scenes": [
                {
                    "id": "scene_001",
                    "heading": "INT. OFFICE - DAY",
                    "content": "JOHN sits at his desk.\n\nJOHN\n"
                    "I need to finish this report.",
                    "script_order": 1,
                },
                {
                    "id": "scene_002",
                    "heading": "EXT. PARKING LOT - DAY",
                    "content": "JOHN walks to his car.\n\nJOHN\nAnother day done.",
                    "script_order": 2,
                },
                {
                    "id": "scene_003",
                    "heading": "INT. JOHN'S CAR - CONTINUOUS",
                    "content": "John starts the engine.",
                    "script_order": 3,
                },
            ],
        }

    def test_update_scene_metadata_with_graph_propagation(
        self, graph_ops, sample_script_data
    ):
        """Test updating scene metadata with graph propagation."""
        # Setup: Create mock nodes and edges
        scene_node = Mock()
        scene_node.id = sample_script_data["scenes"][0]["id"]
        scene_node.properties = sample_script_data["scenes"][0].copy()

        graph_ops.graph.get_node = Mock(return_value=scene_node)
        graph_ops.graph.update_node = Mock(return_value=True)
        graph_ops.graph.find_edges = Mock(
            return_value=[Mock(from_node_id="script_001")]
        )
        graph_ops._update_scene_location_with_propagation = Mock()
        graph_ops._update_character_appearances = Mock()

        # Test metadata update
        result = graph_ops.update_scene_metadata(
            scene_node_id="scene_001",
            heading="INT. OFFICE - NIGHT",
            description="JOHN works late at his desk.\n\nJOHN\nJust a bit more.",
            time_of_day="NIGHT",
            location="INT. OFFICE - NIGHT",
            propagate_to_graph=True,
        )

        # Assertions
        assert result is True
        graph_ops.graph.update_node.assert_called_once()
        graph_ops._update_scene_location_with_propagation.assert_called_once()
        graph_ops._update_character_appearances.assert_called_once()

    def test_extract_characters_from_content(self, graph_ops):
        """Test character extraction from scene content."""
        content = """INT. OFFICE - DAY

JOHN sits at his desk, typing furiously.

JOHN
I need to finish this report before the meeting.

SARAH enters the office.

SARAH
John, the clients are here early.

JOHN
(surprised)
Already? Give me two minutes.
"""

        characters = graph_ops._extract_characters_from_content(content)

        # Should extract character names in uppercase
        assert "JOHN" in characters
        assert "SARAH" in characters
        # Should not extract scene headings or actions
        assert "INT. OFFICE - DAY" not in characters
        assert len(characters) == 2

    def test_update_character_appearances(self, graph_ops):
        """Test updating character appearances in scene."""
        # Setup mocks
        scene_id = "scene_001"
        new_content = "JOHN\nHello there.\n\nMARY\nHi John!"

        graph_ops.graph.find_edges = Mock(
            return_value=[Mock(from_node_id="script_001")]
        )
        graph_ops.graph.delete_edge = Mock()
        graph_ops.graph.find_nodes = Mock(return_value=[])
        graph_ops.create_character_node = Mock(return_value="char_001")
        graph_ops.connect_character_to_scene = Mock()

        # Test character update
        graph_ops._update_character_appearances(scene_id, new_content)

        # Should have called methods to update character connections
        assert graph_ops.graph.delete_edge.called
        assert graph_ops.create_character_node.called
        assert graph_ops.connect_character_to_scene.called

    def test_delete_scene_with_references(self, graph_ops, sample_script_data):
        """Test deleting scene while maintaining reference integrity."""
        scene_id = "scene_002"  # Middle scene from sample data
        script_data = sample_script_data

        # Use the sample script data to get proper scene information
        target_scene = next(s for s in script_data["scenes"] if s["id"] == scene_id)

        # Setup mocks
        scene_node = Mock()
        scene_node.id = scene_id
        scene_node.properties = {"script_order": target_scene["script_order"]}

        graph_ops.graph.get_node = Mock(return_value=scene_node)
        graph_ops.graph.find_edges = Mock(
            return_value=[Mock(from_node_id="script_001")]
        )
        graph_ops.graph.delete_edge = Mock()
        graph_ops.graph.delete_node = Mock()
        graph_ops._remove_scene_dependencies = Mock()
        graph_ops._reindex_scenes_after_deletion = Mock()

        # Test deletion
        result = graph_ops.delete_scene_with_references(scene_id)

        # Assertions
        assert result is True
        graph_ops.graph.delete_node.assert_called_once_with(scene_id)
        graph_ops._remove_scene_dependencies.assert_called_once_with(scene_id)
        graph_ops._reindex_scenes_after_deletion.assert_called_once()

    def test_reindex_scenes_after_deletion(self, graph_ops):
        """Test scene re-indexing after deletion."""
        script_node_id = "script_001"
        deleted_scene_order = 2

        # Mock remaining scenes
        scene1 = Mock()
        scene1.id = "scene_001"
        scene1.properties = {"script_order": 1}

        scene3 = Mock()
        scene3.id = "scene_003"
        scene3.properties = {"script_order": 3}

        scene4 = Mock()
        scene4.id = "scene_004"
        scene4.properties = {"script_order": 4}

        graph_ops.get_script_scenes = Mock(return_value=[scene1, scene3, scene4])
        graph_ops.graph.update_node = Mock()

        # Test re-indexing
        graph_ops._reindex_scenes_after_deletion(script_node_id, deleted_scene_order)

        # Should update scenes with order > deleted_scene_order
        assert graph_ops.graph.update_node.call_count == 2
        # Scene 3 should become order 2, Scene 4 should become order 3

    def test_inject_scene_at_position(self, graph_ops):
        """Test injecting scene at specific position with full re-indexing."""
        script_node_id = "script_001"
        position = 2

        from uuid import uuid4

        # Use a proper UUID for script_id
        script_uuid = uuid4()
        scene = Scene(
            id=uuid4(),
            heading="INT. HALLWAY - DAY",
            description="JOHN walks down the hallway.",
            script_order=0,  # Will be set by position
            script_id=script_uuid,
        )

        # Mock existing scenes
        existing_scenes = [
            Mock(id="scene_001", properties={"script_order": 1}),
            Mock(id="scene_002", properties={"script_order": 2}),
            Mock(id="scene_003", properties={"script_order": 3}),
        ]

        graph_ops.get_script_scenes = Mock(return_value=existing_scenes)
        graph_ops._shift_scenes_for_injection = Mock()
        graph_ops.create_scene_node = Mock(return_value="new_scene_001")
        graph_ops.graph.update_node = Mock()
        graph_ops._reanalyze_dependencies_after_injection = Mock()

        # The scene is already properly created above

        # Test injection
        result = graph_ops.inject_scene_at_position(script_node_id, scene, position)

        # Assertions
        assert result == "new_scene_001"
        graph_ops._shift_scenes_for_injection.assert_called_once_with(
            script_node_id, position
        )
        graph_ops.create_scene_node.assert_called_once()
        graph_ops._reanalyze_dependencies_after_injection.assert_called_once()

    def test_shift_scenes_for_injection(self, graph_ops):
        """Test shifting scene orders for injection."""
        script_node_id = "script_001"
        injection_position = 2

        # Mock scenes
        scene1 = Mock(id="scene_001", properties={"script_order": 1})
        scene2 = Mock(
            id="scene_002", properties={"script_order": 2}
        )  # Should shift to 3
        scene3 = Mock(
            id="scene_003", properties={"script_order": 3}
        )  # Should shift to 4

        graph_ops.get_script_scenes = Mock(return_value=[scene1, scene2, scene3])
        graph_ops.graph.update_node = Mock()

        # Test shifting
        graph_ops._shift_scenes_for_injection(script_node_id, injection_position)

        # Should update scenes at and after injection position
        assert graph_ops.graph.update_node.call_count == 2

    def test_validate_story_continuity(self, graph_ops):
        """Test story continuity validation."""
        script_node_id = "script_001"

        # Mock scenes with different issues
        scene1 = Mock()
        scene1.id = "scene_001"
        scene1.properties = {"script_order": 1, "time_of_day": "DAY"}

        scene2 = Mock()
        scene2.id = "scene_002"
        scene2.properties = {"script_order": 2, "time_of_day": "NIGHT"}

        scene3 = Mock()
        scene3.id = "scene_003"
        scene3.properties = {
            "script_order": 3,
            "time_of_day": "MORNING",
        }  # Temporal regression

        graph_ops.get_script_scenes = Mock(return_value=[scene1, scene2, scene3])
        graph_ops.graph.find_edges = Mock(
            return_value=[]
        )  # No character/location edges

        # Test validation
        results = graph_ops.validate_story_continuity(script_node_id)

        # Should detect temporal regression from NIGHT to MORNING
        assert "temporal_continuity" in results
        assert "character_continuity" in results
        assert "location_continuity" in results
        assert isinstance(results["warnings"], list)

    def test_temporal_regression_detection(self, graph_ops):
        """Test temporal regression detection logic."""
        # Test cases for temporal progression
        assert (
            graph_ops._is_temporal_regression("DAY", "NIGHT") is False
        )  # Normal progression
        assert graph_ops._is_temporal_regression("NIGHT", "DAY") is True  # Regression
        assert (
            graph_ops._is_temporal_regression("EVENING", "MORNING") is True
        )  # Regression
        assert (
            graph_ops._is_temporal_regression("DAWN", "DUSK") is False
        )  # Normal progression

        # Cases where time isn't recognized should return False
        assert graph_ops._is_temporal_regression("UNKNOWN", "DAY") is False
        assert graph_ops._is_temporal_regression("DAY", "UNKNOWN") is False

    def test_inject_invalid_position(self, graph_ops):
        """Test injecting scene at invalid position."""
        script_node_id = "script_001"

        # Mock only 2 existing scenes
        existing_scenes = [Mock(), Mock()]
        graph_ops.get_script_scenes = Mock(return_value=existing_scenes)

        from uuid import uuid4

        # Use a proper UUID for script_id
        script_uuid = uuid4()
        scene = Scene(
            id=uuid4(),
            heading="Test",
            description="Test",
            script_order=1,
            script_id=script_uuid,
        )

        # Test invalid positions
        assert (
            graph_ops.inject_scene_at_position(script_node_id, scene, 0) is None
        )  # Too low
        assert (
            graph_ops.inject_scene_at_position(script_node_id, scene, 4) is None
        )  # Too high

    def test_location_parsing_and_propagation(self, graph_ops):
        """Test location parsing and graph propagation."""
        scene_id = "scene_001"
        new_location = "EXT. BEACH - SUNSET"

        # Setup mocks
        graph_ops.graph.find_edges = Mock(
            return_value=[Mock(from_node_id="script_001")]
        )
        graph_ops.graph.delete_edge = Mock()
        graph_ops.graph.find_nodes = Mock(return_value=[])  # No existing location
        graph_ops.create_location_node = Mock(return_value="location_001")
        graph_ops.connect_scene_to_location = Mock()

        # Test location update
        graph_ops._update_scene_location_with_propagation(scene_id, new_location)

        # Should parse location and create/connect nodes
        graph_ops.create_location_node.assert_called_once()
        graph_ops.connect_scene_to_location.assert_called_once_with(
            scene_id, "location_001"
        )

    def test_remove_scene_dependencies(self, graph_ops, db_connection):
        """Test removal of scene dependencies."""
        scene_id = "scene_001"

        # Use the actual db_connection fixture
        graph_ops.connection = db_connection

        # Create a mock that we'll assign to the connection
        mock_conn = Mock()
        mock_execute = Mock()
        mock_conn.execute = mock_execute

        # Replace the connection with our mock
        graph_ops.connection = mock_conn

        # Test dependency removal
        graph_ops._remove_scene_dependencies(scene_id)

        # Should execute DELETE query for dependencies
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "DELETE FROM scene_dependencies" in call_args[0][0]
        assert scene_id in call_args[0][1]

    def test_character_extraction_edge_cases(self, graph_ops):
        """Test character extraction with edge cases."""
        # Test content with various formatting
        content = """INT. OFFICE - DAY

Some action description.

JOHN DOE
(speaking loudly)
This is dialogue!

MARY-JANE WATSON
Another character name.

THE NARRATOR
(V.O.)
Voice over dialogue.

FADE OUT.

CUT TO:
"""

        characters = graph_ops._extract_characters_from_content(content)

        # Should extract valid character names
        assert "JOHN DOE" in characters
        assert "MARY-JANE WATSON" in characters
        assert "THE NARRATOR" in characters

        # Should not extract technical terms
        assert "FADE OUT." not in characters
        assert "CUT TO:" not in characters
        assert "INT. OFFICE - DAY" not in characters

    def test_complex_scene_update_scenario(self, graph_ops):
        """Test complex scene update with multiple changes."""
        scene_id = "scene_001"

        # Setup comprehensive mocks
        scene_node = Mock()
        scene_node.id = scene_id
        scene_node.properties = {
            "heading": "OLD HEADING",
            "description": "OLD CONTENT",
            "script_order": 1,
        }

        graph_ops.graph.get_node = Mock(return_value=scene_node)
        graph_ops.graph.update_node = Mock(return_value=True)
        graph_ops._update_scene_location_with_propagation = Mock()
        graph_ops._update_character_appearances = Mock()

        # Test comprehensive update
        result = graph_ops.update_scene_metadata(
            scene_node_id=scene_id,
            heading="INT. NEW LOCATION - NIGHT",
            description="ALICE\nNew dialogue here.\n\nBOB\nResponse.",
            time_of_day="NIGHT",
            location="INT. NEW LOCATION - NIGHT",
            propagate_to_graph=True,
        )

        # All update methods should be called
        assert result is True
        graph_ops.graph.update_node.assert_called_once()
        graph_ops._update_scene_location_with_propagation.assert_called_once_with(
            scene_id, "INT. NEW LOCATION - NIGHT"
        )
        graph_ops._update_character_appearances.assert_called_once()


class TestSceneOperationsIntegration:
    """Integration tests for scene operations."""

    @pytest.fixture
    def integration_setup(self, tmp_path):
        """Setup for integration tests."""
        db_path = tmp_path / "test_integration.db"

        # Initialize database
        from scriptrag.database import initialize_database

        initialize_database(str(db_path))

        conn = DatabaseConnection(str(db_path))
        graph_ops = GraphOps(conn)

        return {"connection": conn, "graph_ops": graph_ops, "db_path": str(db_path)}

    def test_full_scene_lifecycle(self, integration_setup):
        """Test complete scene lifecycle: create, update, inject, delete."""
        graph_ops = integration_setup["graph_ops"]

        # This would be a full integration test with real database operations
        # For now, we'll test the method signatures and basic functionality

        # Test that methods exist and accept expected parameters
        assert hasattr(graph_ops, "update_scene_metadata")
        assert hasattr(graph_ops, "delete_scene_with_references")
        assert hasattr(graph_ops, "inject_scene_at_position")
        assert hasattr(graph_ops, "validate_story_continuity")

        # Test method signatures
        import inspect

        update_sig = inspect.signature(graph_ops.update_scene_metadata)
        assert "scene_node_id" in update_sig.parameters
        assert "propagate_to_graph" in update_sig.parameters

        delete_sig = inspect.signature(graph_ops.delete_scene_with_references)
        assert "scene_node_id" in delete_sig.parameters

        inject_sig = inspect.signature(graph_ops.inject_scene_at_position)
        assert "script_node_id" in inject_sig.parameters
        assert "position" in inject_sig.parameters

        validate_sig = inspect.signature(graph_ops.validate_story_continuity)
        assert "script_node_id" in validate_sig.parameters


if __name__ == "__main__":
    pytest.main([__file__])
