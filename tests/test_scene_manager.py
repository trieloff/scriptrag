"""Tests for SceneManager functionality.

This module contains comprehensive tests for the SceneManager class,
including temporal order inference, scene dependency analysis, and
scene reordering operations.
"""

from datetime import time
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from scriptrag.database.graph import GraphDatabase
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Scene, SceneOrderType
from scriptrag.scene_manager import SceneManager


class TestSceneManager:
    """Test SceneManager functionality."""

    def test_initialization(self, db_connection):
        """Test SceneManager initialization."""
        manager = SceneManager(db_connection)

        assert manager.connection == db_connection
        assert isinstance(manager.graph, GraphDatabase)
        assert isinstance(manager.operations, GraphOperations)

    def test_time_constants(self):
        """Test time constants are properly defined."""
        assert SceneManager.DEFAULT_SCENE_DURATION_MINUTES == 5
        assert SceneManager.MINUTES_PER_HOUR == 60
        assert SceneManager.MINUTES_PER_DAY == 1440
        assert SceneManager.MINUTES_PER_WEEK == 10080
        assert SceneManager.MINUTES_PER_MONTH == 43200
        assert SceneManager.MINUTES_PER_YEAR == 525600


class TestTemporalOrderInference:
    """Test temporal order inference functionality."""

    def test_infer_temporal_order_empty_script(self, scene_manager):
        """Test temporal order inference with no scenes."""
        script_node_id = "test-script"

        # Mock empty scenes
        scene_manager.operations.get_script_scenes = Mock(return_value=[])

        result = scene_manager.infer_temporal_order(script_node_id)

        assert result == {}

    def test_infer_temporal_order_basic_progression(self, scene_manager):
        """Test basic temporal order inference without time jumps."""
        script_node_id = "test-script"

        # Mock scenes without temporal indicators
        mock_scenes = [
            Mock(id="scene1", properties={"heading": "INT. OFFICE - DAY"}),
            Mock(id="scene2", properties={"heading": "EXT. STREET - DAY"}),
            Mock(id="scene3", properties={"heading": "INT. HOME - NIGHT"}),
        ]

        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        result = scene_manager.infer_temporal_order(script_node_id)

        expected = {"scene1": 1, "scene2": 2, "scene3": 3}
        assert result == expected

    def test_infer_temporal_order_with_time_jumps(self, scene_manager):
        """Test temporal order inference with time jump indicators."""
        script_node_id = "test-script"

        mock_scenes = [
            Mock(
                id="scene1",
                properties={
                    "heading": "INT. OFFICE - DAY",
                    "description": "Character at work",
                },
            ),
            Mock(
                id="scene2",
                properties={
                    "heading": "EXT. STREET - DAY",
                    "description": "HOURS LATER, character walking",
                },
            ),
            Mock(
                id="scene3",
                properties={
                    "heading": "INT. HOME - NIGHT",
                    "description": "THE NEXT DAY, character at home",
                },
            ),
        ]

        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        result = scene_manager.infer_temporal_order(script_node_id)

        # Scene 1 at position 0, scene 2 at 120 (2 hours), scene 3 at
        # 1440+120 (next day)
        expected = {"scene1": 1, "scene2": 2, "scene3": 3}
        assert result == expected

    def test_infer_temporal_order_with_flashback(self, scene_manager):
        """Test temporal order inference with flashback."""
        script_node_id = "test-script"

        mock_scenes = [
            Mock(
                id="scene1",
                properties={
                    "heading": "INT. OFFICE - DAY",
                    "description": "Character at work",
                },
            ),
            Mock(
                id="scene2",
                properties={
                    "heading": "INT. CHILDHOOD HOME - DAY",
                    "description": "FLASHBACK: character as child",
                },
            ),
            Mock(
                id="scene3",
                properties={
                    "heading": "INT. OFFICE - DAY",
                    "description": "Back to present",
                },
            ),
        ]

        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        result = scene_manager.infer_temporal_order(script_node_id)

        # Flashback should be first in temporal order
        expected = {"scene2": 1, "scene1": 2, "scene3": 3}
        assert result == expected

    def test_extract_time_from_heading_standard_times(self, scene_manager):
        """Test time extraction from standard time indicators."""
        test_cases = [
            ("INT. OFFICE - DAWN", time(6, 0)),
            ("EXT. STREET - MORNING", time(6, 0)),
            ("INT. CAFÉ - DAY", time(12, 0)),
            ("EXT. PARK - AFTERNOON", time(12, 0)),
            ("INT. HOME - EVENING", time(18, 0)),
            ("EXT. STREET - NIGHT", time(0, 0)),
            ("INT. BAR - MIDNIGHT", time(0, 0)),
        ]

        for heading, expected_time in test_cases:
            result = scene_manager._extract_time_from_heading(heading)
            assert result == expected_time, f"Failed for heading: {heading}"

    def test_extract_time_from_heading_specific_times(self, scene_manager):
        """Test time extraction from specific time formats."""
        test_cases = [
            ("INT. OFFICE - 9:30 AM", time(9, 30)),
            ("EXT. STREET - 2:15 PM", time(14, 15)),
            ("INT. HOME - 12:00 AM", time(0, 0)),
            ("EXT. PARK - 12:00 PM", time(12, 0)),
        ]

        for heading, expected_time in test_cases:
            result = scene_manager._extract_time_from_heading(heading)
            assert result == expected_time, f"Failed for heading: {heading}"

    def test_extract_time_from_heading_no_time(self, scene_manager):
        """Test time extraction when no time indicator present."""
        headings = [
            "INT. OFFICE",
            "EXT. MYSTERIOUS LOCATION",
            "FADE IN:",
            "",
        ]

        for heading in headings:
            result = scene_manager._extract_time_from_heading(heading)
            assert result is None, f"Expected None for heading: {heading}"

    def test_detect_temporal_jump_patterns(self, scene_manager):
        """Test detection of temporal jump patterns."""
        test_cases = [
            ("LATER that evening", 1.0),
            ("MOMENTS LATER", 1.0),
            ("MINUTES LATER, he arrives", 1.0),  # "LATER" matches first
            ("HOURS LATER", 1.0),  # "LATER" matches first
            ("THE NEXT DAY", 1440.0),
            ("DAYS LATER", 1.0),  # "LATER" matches first
            ("WEEKS LATER", 1.0),  # "LATER" matches first
            ("MONTHS LATER", 1.0),  # "LATER" matches first
            ("YEARS LATER", 1.0),  # "LATER" matches first
            ("FLASHBACK to childhood", -1.0),
        ]

        for description, expected_minutes in test_cases:
            mock_scene = Mock(properties={"description": description})
            result = scene_manager._detect_temporal_jump(mock_scene)
            assert result == expected_minutes, f"Failed for description: {description}"

    def test_detect_temporal_jump_no_indicator(self, scene_manager):
        """Test temporal jump detection with no indicators."""
        descriptions = [
            "Character walks down the street",
            "A normal conversation",
            "",
            "No time indicators here",
        ]

        for description in descriptions:
            mock_scene = Mock(properties={"description": description})
            result = scene_manager._detect_temporal_jump(mock_scene)
            assert result is None, f"Expected None for description: {description}"


class TestSceneDependencyAnalysis:
    """Test scene dependency analysis functionality."""

    def test_analyze_scene_dependencies_empty_script(self, scene_manager):
        """Test dependency analysis with no scenes."""
        script_node_id = "test-script"

        scene_manager.operations.get_script_scenes = Mock(return_value=[])

        result = scene_manager.analyze_scene_dependencies(script_node_id)

        assert result == {}

    def test_analyze_scene_dependencies_character_introductions(self, scene_manager):
        """Test dependency analysis based on character introductions."""
        script_node_id = "test-script"

        # Mock scenes
        mock_scenes = [
            Mock(id="scene1"),
            Mock(id="scene2"),
            Mock(id="scene3"),
        ]

        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        # Mock database query results for character appearances
        mock_results = [
            ("char1", "scene1"),  # Character 1 first appears in scene 1
            ("char1", "scene3"),  # Character 1 also appears in scene 3
            ("char2", "scene2"),  # Character 2 only appears in scene 2
        ]

        with patch.object(scene_manager.connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_conn.execute.return_value.fetchall.return_value = mock_results
            mock_transaction.return_value.__enter__.return_value = mock_conn

            result = scene_manager.analyze_scene_dependencies(script_node_id)

        # Scene 3 should depend on scene 1 (character 1 introduction)
        expected = {
            "scene1": [],
            "scene2": [],
            "scene3": ["scene1"],
        }
        assert result == expected

    def test_analyze_scene_dependencies_multiple_characters(self, scene_manager):
        """Test dependency analysis with multiple character introductions."""
        script_node_id = "test-script"

        mock_scenes = [
            Mock(id="scene1"),
            Mock(id="scene2"),
            Mock(id="scene3"),
            Mock(id="scene4"),
        ]

        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        # Multiple characters with different introduction patterns
        mock_results = [
            ("char1", "scene1"),  # Char1: scene1 -> scene3
            ("char1", "scene3"),
            ("char2", "scene2"),  # Char2: scene2 -> scene3, scene4
            ("char2", "scene3"),
            ("char2", "scene4"),
            ("char3", "scene4"),  # Char3: only scene4
        ]

        with patch.object(scene_manager.connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_conn.execute.return_value.fetchall.return_value = mock_results
            mock_transaction.return_value.__enter__.return_value = mock_conn

            result = scene_manager.analyze_scene_dependencies(script_node_id)

        expected = {
            "scene1": [],
            "scene2": [],
            "scene3": [
                "scene1",
                "scene2",
            ],  # Depends on both char1 and char2 introductions
            "scene4": ["scene2"],  # Depends on char2 introduction
        }
        assert result == expected

    def test_analyze_scene_dependencies_for_single_scene(self, scene_manager):
        """Test dependency analysis for a single scene."""
        scene_node_id = "scene3"

        # Mock characters in the scene
        mock_characters = [
            Mock(id="char1", label="PROTAGONIST"),
            Mock(id="char2", label="SIDEKICK"),
        ]

        scene_manager.graph.get_neighbors = Mock(return_value=mock_characters)

        # Mock character scenes for each character
        def mock_get_character_scenes(char_id):
            if char_id == "char1":
                return [
                    Mock(
                        id="scene1",
                        properties={"script_order": 1, "heading": "INT. OFFICE - DAY"},
                    ),
                    Mock(
                        id="scene3",
                        properties={"script_order": 3, "heading": "INT. CAFÉ - DAY"},
                    ),
                ]
            if char_id == "char2":
                return [
                    Mock(
                        id="scene2",
                        properties={"script_order": 2, "heading": "EXT. STREET - DAY"},
                    ),
                    Mock(
                        id="scene3",
                        properties={"script_order": 3, "heading": "INT. CAFÉ - DAY"},
                    ),
                ]
            return []

        scene_manager.operations.get_character_scenes = Mock(
            side_effect=mock_get_character_scenes
        )

        result = scene_manager.analyze_scene_dependencies_for_single(scene_node_id)

        expected = [
            {
                "type": "character_introduction",
                "character": "PROTAGONIST",
                "scene_id": "scene1",
                "scene_heading": "INT. OFFICE - DAY",
            },
            {
                "type": "character_introduction",
                "character": "SIDEKICK",
                "scene_id": "scene2",
                "scene_heading": "EXT. STREET - DAY",
            },
        ]
        assert result == expected


class TestSceneReordering:
    """Test scene reordering functionality."""

    def test_update_scene_order_success(self, scene_manager):
        """Test successful scene reordering."""
        scene_node_id = "scene2"
        new_position = 1
        order_type = SceneOrderType.SCRIPT

        # Mock finding script for scene
        mock_script_edges = [Mock(from_node_id="script1")]
        scene_manager.graph.find_edges = Mock(return_value=mock_script_edges)

        # Mock current scenes
        mock_scenes = [
            Mock(id="scene1"),
            Mock(id="scene2"),
            Mock(id="scene3"),
        ]
        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        # Mock successful update
        scene_manager.operations.update_scene_order = Mock(return_value=True)

        result = scene_manager.update_scene_order(
            scene_node_id, new_position, order_type
        )

        assert result is True

        # Verify the order mapping was calculated correctly
        expected_mapping = {"scene2": 1, "scene1": 2, "scene3": 3}
        scene_manager.operations.update_scene_order.assert_called_once_with(
            "script1", expected_mapping, order_type
        )

    def test_update_scene_order_scene_not_in_script(self, scene_manager):
        """Test scene reordering when scene not found in any script."""
        scene_node_id = "nonexistent-scene"
        new_position = 1

        # Mock no script edges found
        scene_manager.graph.find_edges = Mock(return_value=[])

        result = scene_manager.update_scene_order(scene_node_id, new_position)

        assert result is False

    def test_update_scene_order_scene_not_in_order(self, scene_manager):
        """Test scene reordering when scene not found in current order."""
        scene_node_id = "missing-scene"
        new_position = 1

        # Mock finding script
        mock_script_edges = [Mock(from_node_id="script1")]
        scene_manager.graph.find_edges = Mock(return_value=mock_script_edges)

        # Mock scenes that don't include the target scene
        mock_scenes = [
            Mock(id="scene1"),
            Mock(id="scene2"),
        ]
        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)

        result = scene_manager.update_scene_order(scene_node_id, new_position)

        assert result is False

    def test_update_scene_order_position_bounds(self, scene_manager):
        """Test scene reordering with various position bounds."""
        scene_node_id = "scene2"

        # Mock setup
        mock_script_edges = [Mock(from_node_id="script1")]
        scene_manager.graph.find_edges = Mock(return_value=mock_script_edges)

        mock_scenes = [
            Mock(id="scene1"),
            Mock(id="scene2"),
            Mock(id="scene3"),
        ]
        scene_manager.operations.get_script_scenes = Mock(return_value=mock_scenes)
        scene_manager.operations.update_scene_order = Mock(return_value=True)

        # Test position too low (should clamp to 1)
        scene_manager.update_scene_order(scene_node_id, -1)
        args = scene_manager.operations.update_scene_order.call_args[0]
        order_mapping = args[1]
        assert order_mapping["scene2"] == 1  # Should be clamped to position 1

        # Reset mock
        scene_manager.operations.update_scene_order.reset_mock()

        # Test position too high (should clamp to last position)
        scene_manager.update_scene_order(scene_node_id, 10)
        args = scene_manager.operations.update_scene_order.call_args[0]
        order_mapping = args[1]
        assert order_mapping["scene2"] == 3  # Should be clamped to last position

    def test_update_scene_order_exception_handling(self, scene_manager):
        """Test scene reordering exception handling."""
        scene_node_id = "scene1"
        new_position = 1

        # Mock exception during processing
        scene_manager.graph.find_edges = Mock(side_effect=Exception("Database error"))

        result = scene_manager.update_scene_order(scene_node_id, new_position)

        assert result is False


class TestSceneLocationUpdate:
    """Test scene location update functionality."""

    def test_update_scene_location_standard_format(self, scene_manager):
        """Test updating scene location with standard format."""
        scene_node_id = "scene1"
        new_location = "INT. OFFICE - DAY"

        # Mock successful database update
        with patch.object(scene_manager.connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_transaction.return_value.__enter__.return_value = mock_conn

            # Mock finding existing location (none found)
            mock_conn.execute.return_value = []

            # Mock finding script for scene
            mock_conn.execute.return_value = [("script1",)]

            # Mock location node creation
            scene_manager.operations.create_location_node = Mock(
                return_value="location1"
            )
            scene_manager.operations.connect_scene_to_location = Mock()

            result = scene_manager.update_scene_location(scene_node_id, new_location)

        assert result is True

    def test_update_scene_location_existing_location(self, scene_manager):
        """Test updating scene location when location already exists."""
        scene_node_id = "scene1"
        new_location = "INT. OFFICE - DAY"

        with patch.object(scene_manager.connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_transaction.return_value.__enter__.return_value = mock_conn

            # Mock finding existing location
            def mock_execute(query, _params=None):
                if "SELECT id FROM nodes" in query and "location" in query:
                    return [("existing-location-id",)]
                if "SELECT from_node_id FROM edges" in query:
                    return [("script1",)]
                return Mock(fetchall=Mock(return_value=[]))

            mock_conn.execute = Mock(side_effect=mock_execute)
            scene_manager.operations.connect_scene_to_location = Mock()

            result = scene_manager.update_scene_location(scene_node_id, new_location)

        assert result is True

    def test_update_scene_location_flexible_format(self, scene_manager):
        """Test updating scene location with flexible format parsing."""
        test_cases = [
            "INT. OFFICE - DAY",  # Standard format
            "EXT. STREET - NIGHT",  # Standard format with time
        ]

        for new_location in test_cases:
            scene_node_id = "scene1"

            with patch.object(
                scene_manager.connection, "transaction"
            ) as mock_transaction:
                mock_conn = Mock()
                mock_transaction.return_value.__enter__.return_value = mock_conn

                # Mock the execute method to handle different queries
                def mock_execute(query, _params=None):
                    if "SELECT id FROM nodes" in query:
                        return []  # No existing location
                    if "SELECT from_node_id FROM edges" in query:
                        return [("script1",)]  # Return script ID
                    return Mock()

                mock_conn.execute.side_effect = mock_execute
                mock_transaction.return_value.__enter__.return_value = mock_conn

                scene_manager.operations.create_location_node = Mock(
                    return_value="location1"
                )
                scene_manager.operations.connect_scene_to_location = Mock()

                result = scene_manager.update_scene_location(
                    scene_node_id, new_location
                )

                assert result is True, f"Failed for location: {new_location}"

    def test_update_scene_location_exception_handling(self, scene_manager):
        """Test scene location update exception handling."""
        scene_node_id = "scene1"
        new_location = "INT. OFFICE - DAY"

        # Mock exception during database operation
        with patch.object(scene_manager.connection, "transaction") as mock_transaction:
            mock_transaction.side_effect = Exception("Database error")

            result = scene_manager.update_scene_location(scene_node_id, new_location)

        assert result is False


class TestSceneInfoRetrieval:
    """Test scene information retrieval functionality."""

    def test_get_scene_info_complete(self, scene_manager):
        """Test getting complete scene information."""
        scene_node_id = "scene1"

        # Mock scene node
        mock_scene_node = Mock(
            properties={
                "heading": "INT. OFFICE - DAY",
                "script_order": 1,
                "temporal_order": 2,
                "logical_order": 1,
                "description": "Character at work",
                "time_of_day": "DAY",
                "estimated_duration": 5.0,
            }
        )
        scene_manager.graph.get_node = Mock(return_value=mock_scene_node)

        # Mock location connection
        mock_location_edges = [Mock(to_node_id="location1")]
        mock_location_node = Mock(label="OFFICE")

        def mock_find_edges(*, edge_type=None):
            if edge_type == "AT_LOCATION":
                return mock_location_edges
            return []

        scene_manager.graph.find_edges = Mock(side_effect=mock_find_edges)
        scene_manager.graph.get_node = Mock(
            side_effect=lambda node_id: {
                "scene1": mock_scene_node,
                "location1": mock_location_node,
            }.get(node_id)
        )

        # Mock characters
        mock_characters = [
            Mock(id="char1", label="PROTAGONIST"),
            Mock(id="char2", label="SIDEKICK"),
        ]
        scene_manager.graph.get_neighbors = Mock(return_value=mock_characters)

        # Mock dependencies
        scene_manager.analyze_scene_dependencies_for_single = Mock(return_value=[])

        result = scene_manager.get_scene_info(scene_node_id)

        expected = {
            "id": "scene1",
            "heading": "INT. OFFICE - DAY",
            "script_order": 1,
            "temporal_order": 2,
            "logical_order": 1,
            "description": "Character at work",
            "time_of_day": "DAY",
            "estimated_duration": 5.0,
            "location": "OFFICE",
            "characters": [
                {"id": "char1", "name": "PROTAGONIST"},
                {"id": "char2", "name": "SIDEKICK"},
            ],
            "dependencies": [],
        }
        assert result == expected

    def test_get_scene_info_nonexistent_scene(self, scene_manager):
        """Test getting info for nonexistent scene."""
        scene_node_id = "nonexistent"

        scene_manager.graph.get_node = Mock(return_value=None)

        result = scene_manager.get_scene_info(scene_node_id)

        assert result == {}

    def test_get_scene_info_minimal_data(self, scene_manager):
        """Test getting scene info with minimal data."""
        scene_node_id = "scene1"

        # Mock scene node with minimal properties
        mock_scene_node = Mock(properties={"heading": "INT. OFFICE - DAY"})
        scene_manager.graph.get_node = Mock(return_value=mock_scene_node)

        # Mock no location, characters, or dependencies
        scene_manager.graph.find_edges = Mock(return_value=[])
        scene_manager.graph.get_neighbors = Mock(return_value=[])
        scene_manager.analyze_scene_dependencies_for_single = Mock(return_value=[])

        result = scene_manager.get_scene_info(scene_node_id)

        expected = {
            "id": "scene1",
            "heading": "INT. OFFICE - DAY",
            "script_order": 0,
            "temporal_order": None,
            "logical_order": None,
            "description": "",
            "time_of_day": None,
            "estimated_duration": None,
            "characters": [],
            "dependencies": [],
        }
        assert result == expected


# Fixtures
@pytest.fixture
def scene_manager(db_connection):
    """Create a SceneManager instance for testing."""
    return SceneManager(db_connection)


@pytest.fixture
def sample_scenes():
    """Create sample scenes for testing."""
    script_id = uuid4()
    return [
        Scene(
            script_id=script_id,
            heading="INT. OFFICE - DAY",
            description="Character at work",
            script_order=1,
        ),
        Scene(
            script_id=script_id,
            heading="EXT. STREET - DAY",
            description="Character walking",
            script_order=2,
        ),
        Scene(
            script_id=script_id,
            heading="INT. HOME - NIGHT",
            description="Character at home",
            script_order=3,
        ),
    ]
