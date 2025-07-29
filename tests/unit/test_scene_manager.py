#!/usr/bin/env python3
"""
Unit tests for scene manager - scene ordering, dependencies, and operations.
"""

import re
from datetime import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from scriptrag.database import GraphDatabase, GraphOperations
from scriptrag.database.graph import GraphNode
from scriptrag.models import (
    EdgeType,
    Location,
    NodeType,
    Scene,
    SceneOrderType,
)
from scriptrag.scene_manager import SceneManager


class TestSceneManager:
    """Test SceneManager class."""

    @pytest.fixture
    def scene_manager(self, db_connection):
        """Create scene manager instance."""
        return SceneManager(db_connection)

    @pytest.fixture
    def sample_script_node(self, graph_ops):
        """Create a sample script node."""
        return graph_ops.graph.create_node(
            NodeType.SCRIPT, {"title": "Test Script", "author": "Test Author"}
        )

    @pytest.fixture
    def sample_scenes(self, graph_ops, sample_script_node):
        """Create sample scene nodes."""
        scenes = []
        headings = [
            "INT. APARTMENT - MORNING",
            "EXT. STREET - DAY",
            "INT. OFFICE - DAY",
            "INT. RESTAURANT - EVENING",
            "INT. APARTMENT - NIGHT",
        ]

        for i, heading in enumerate(headings):
            scene = Scene(
                script_id=sample_script_node.id,
                heading=heading,
                description=f"Scene {i + 1} description",
                script_order=i + 1,
                temporal_order=i + 1,
                logical_order=i + 1,
            )
            scene_node = graph_ops.create_scene(scene, sample_script_node.id)
            scenes.append(scene_node)

        return scenes

    def test_scene_manager_initialization(self, scene_manager):
        """Test scene manager initialization."""
        assert isinstance(scene_manager.connection, type(scene_manager.connection))
        assert isinstance(scene_manager.graph, GraphDatabase)
        assert isinstance(scene_manager.operations, GraphOperations)

    def test_time_patterns(self, scene_manager):
        """Test time pattern constants."""
        # Test standard time patterns
        patterns = scene_manager.TIME_PATTERNS
        assert len(patterns) > 0

        # Verify pattern structure
        for pattern, expected_time in patterns:
            assert isinstance(pattern, str)
            assert expected_time is None or isinstance(expected_time, time)

        # Test a few specific patterns
        dawn_pattern = patterns[0][0]
        assert re.search(dawn_pattern, "DAWN") is not None
        assert re.search(dawn_pattern, "EARLY MORNING") is not None

    def test_temporal_indicators(self, scene_manager):
        """Test temporal indicator patterns."""
        indicators = scene_manager.TEMPORAL_INDICATORS
        assert len(indicators) > 0

        # Verify structure
        for pattern, minutes in indicators:
            assert isinstance(pattern, str)
            assert isinstance(minutes, int)

        # Test specific indicators
        later_pattern = indicators[0][0]
        assert re.search(later_pattern, "LATER") is not None
        assert re.search(later_pattern, "MOMENTS LATER") is not None

    def test_extract_time_from_heading(self, scene_manager):
        """Test extracting time from scene headings."""
        test_cases = [
            ("INT. ROOM - DAY", time(12, 0)),
            ("EXT. PARK - NIGHT", time(0, 0)),
            ("INT. CAFE - MORNING", time(6, 0)),
            ("EXT. STREET - DUSK", time(18, 0)),
            ("INT. OFFICE - 3:00 PM", time(15, 0)),
            ("EXT. BASE - 0600 HOURS", time(6, 0)),
            ("INT. ROOM - CONTINUOUS", None),
            ("INT. ROOM", None),
        ]

        for heading, expected in test_cases:
            result = scene_manager._extract_time_from_heading(heading)
            if expected is None:
                assert result is None
            else:
                assert result == expected

    def test_detect_temporal_jump(self, scene_manager):
        """Test detecting temporal jumps in scene content."""
        # Mock scene with temporal indicator
        scene_node = GraphNode(
            id=str(uuid4()),
            type=NodeType.SCENE,
            properties={
                "heading": "INT. ROOM - DAY",
                "action": "LATER\n\nJohn enters the room.",
                "elements": [
                    {"type": "action", "text": "LATER"},
                    {"type": "action", "text": "John enters the room."},
                ],
            },
        )

        jump = scene_manager._detect_temporal_jump(scene_node)
        assert jump == 1  # "LATER" indicates very short jump

        # Test flashback
        flashback_node = GraphNode(
            id=str(uuid4()),
            type=NodeType.SCENE,
            properties={
                "heading": "INT. ROOM - DAY",
                "action": "FLASHBACK TO:\n\nYears earlier...",
            },
        )

        jump = scene_manager._detect_temporal_jump(flashback_node)
        assert jump < 0  # Negative indicates flashback

    def test_infer_temporal_order(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test inferring temporal order of scenes."""
        # Add temporal indicators to some scenes
        sample_scenes[2].properties["action"] = "THE NEXT DAY\n\nWork continues."
        sample_scenes[4].properties["action"] = "FLASHBACK TO:\n\nEarlier that morning."

        temporal_order = scene_manager.infer_temporal_order(sample_script_node.id)

        assert len(temporal_order) > 0
        # Verify flashback has lower temporal order
        if (
            sample_scenes[4].id in temporal_order
            and sample_scenes[0].id in temporal_order
        ):
            assert (
                temporal_order[sample_scenes[4].id]
                < temporal_order[sample_scenes[0].id]
            )

    def test_analyze_scene_dependencies(self, scene_manager, sample_scenes, graph_ops):
        """Test analyzing dependencies between scenes."""
        # Create character that appears in multiple scenes
        char_node = graph_ops.create_character({"name": "JOHN"})

        # Link character to scenes 0, 2, and 4
        for i in [0, 2, 4]:
            graph_ops.link_scene_character(sample_scenes[i].id, char_node.id)

        # Create prop that's established in scene 1 and used in scene 3
        prop_node = graph_ops.graph.create_node(
            NodeType.PROP, {"name": "BRIEFCASE", "description": "Important briefcase"}
        )

        graph_ops.graph.create_edge(
            sample_scenes[1].id, prop_node.id, EdgeType.INTRODUCES, {"action": "found"}
        )

        graph_ops.graph.create_edge(
            sample_scenes[3].id, prop_node.id, EdgeType.USES, {"action": "opened"}
        )

        dependencies = scene_manager.analyze_scene_dependencies(sample_scenes[0].id)

        assert isinstance(dependencies, list)
        # Should find character-based dependencies
        char_deps = [
            d for d in dependencies if d.dependency_type == "character_continuity"
        ]
        assert len(char_deps) > 0

    def test_reorder_scenes_script_order(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test reordering scenes by script order."""
        # Create new order mapping (reverse the scenes)
        new_order = {
            sample_scenes[0].id: 5,
            sample_scenes[1].id: 4,
            sample_scenes[2].id: 3,
            sample_scenes[3].id: 2,
            sample_scenes[4].id: 1,
        }

        scene_manager.reorder_scenes(
            sample_script_node.id, new_order, SceneOrderType.SCRIPT
        )

        # Verify new order
        reordered = scene_manager.operations.get_script_scenes(
            sample_script_node.id, SceneOrderType.SCRIPT
        )

        assert reordered[0].id == sample_scenes[4].id
        assert reordered[1].id == sample_scenes[3].id
        assert reordered[2].id == sample_scenes[2].id
        assert reordered[3].id == sample_scenes[1].id
        assert reordered[4].id == sample_scenes[0].id

    def test_reorder_scenes_temporal_order(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test reordering scenes by temporal order."""
        # Set different temporal order
        new_order = {
            sample_scenes[0].id: 1,  # Morning first
            sample_scenes[4].id: 2,  # Night (flashback to earlier)
            sample_scenes[1].id: 3,  # Day
            sample_scenes[2].id: 4,  # Day continued
            sample_scenes[3].id: 5,  # Evening last
        }

        scene_manager.reorder_scenes(
            sample_script_node.id, new_order, SceneOrderType.TEMPORAL
        )

        # Verify temporal order updated
        for scene_id, order in new_order.items():
            scene = scene_manager.graph.get_node(scene_id)
            assert scene.properties.get("temporal_order") == order

    def test_suggest_scene_order_by_time(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test suggesting scene order based on time of day."""
        suggested = scene_manager.suggest_scene_order(
            sample_script_node.id, strategy="time_of_day"
        )

        assert isinstance(suggested, dict)
        assert len(suggested) == len(sample_scenes)

        # Morning should come before evening/night
        morning_order = suggested.get(sample_scenes[0].id, float("inf"))
        evening_order = suggested.get(sample_scenes[3].id, float("inf"))
        night_order = suggested.get(sample_scenes[4].id, float("inf"))

        assert morning_order < evening_order
        assert evening_order < night_order

    def test_suggest_scene_order_by_location(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test suggesting scene order to minimize location changes."""
        # Link scenes to locations
        locations = []
        location_names = ["APARTMENT", "STREET", "OFFICE", "RESTAURANT", "APARTMENT"]

        for scene, loc_name in zip(sample_scenes, location_names, strict=False):
            is_interior = "INT." in scene.properties["heading"]
            location = Location(
                interior=is_interior,
                name=loc_name,
                raw_text=f"{'INT' if is_interior else 'EXT'}. {loc_name}",
            )
            loc_node = scene_manager.operations.create_location(location)
            locations.append(loc_node)
            scene_manager.operations.link_scene_location(scene.id, loc_node.id)

        suggested = scene_manager.suggest_scene_order(
            sample_script_node.id, strategy="location_continuity"
        )

        assert isinstance(suggested, dict)
        # Scenes in same location should be grouped
        # Both apartment scenes should be close in order
        apt_orders = [suggested[sample_scenes[0].id], suggested[sample_scenes[4].id]]
        # Their order values should be closer than to other scenes
        assert abs(apt_orders[0] - apt_orders[1]) < len(sample_scenes)

    def test_validate_scene_order(
        self, scene_manager, sample_scenes, sample_script_node, graph_ops
    ):
        """Test validating scene order for continuity issues."""
        # Create a prop introduced in scene 3 but used in scene 1 (wrong order)
        prop_node = graph_ops.graph.create_node(
            NodeType.PROP, {"name": "MACGUFFIN", "description": "Important item"}
        )

        graph_ops.graph.create_edge(
            sample_scenes[3].id, prop_node.id, EdgeType.INTRODUCES
        )

        graph_ops.graph.create_edge(sample_scenes[1].id, prop_node.id, EdgeType.USES)

        issues = scene_manager.validate_scene_order(
            sample_script_node.id, SceneOrderType.SCRIPT
        )

        assert len(issues) > 0
        # Should detect prop used before introduced
        prop_issues = [i for i in issues if "MACGUFFIN" in i.description]
        assert len(prop_issues) > 0

    def test_merge_consecutive_scenes(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test merging consecutive scenes in same location."""
        # Scenes 0 and 4 are both INT. APARTMENT
        # Make them consecutive
        sample_scenes[1].properties["script_order"] = 10  # Move out of the way
        sample_scenes[2].properties["script_order"] = 11
        sample_scenes[3].properties["script_order"] = 12
        sample_scenes[4].properties["script_order"] = 2  # Right after scene 0

        # Link both to same location
        loc_node = scene_manager.operations.create_location(
            Location(interior=True, name="APARTMENT", raw_text="INT. APARTMENT")
        )
        scene_manager.operations.link_scene_location(sample_scenes[0].id, loc_node.id)
        scene_manager.operations.link_scene_location(sample_scenes[4].id, loc_node.id)

        merged = scene_manager.merge_consecutive_scenes(
            sample_script_node.id, sample_scenes[0].id, sample_scenes[4].id
        )

        assert merged is not None
        assert merged.properties["heading"] == sample_scenes[0].properties["heading"]
        # Should combine descriptions/content
        assert "Scene 1 description" in merged.properties.get("description", "")

    def test_split_scene(self, scene_manager, sample_scenes):
        """Test splitting a scene into multiple parts."""
        original_scene = sample_scenes[2]

        # Add content that could be split
        original_scene.properties["elements"] = [
            {"type": "action", "text": "First part of the scene."},
            {"type": "dialogue", "character": "JOHN", "text": "Hello."},
            {"type": "action", "text": "CUT TO:\n\nDifferent angle."},
            {"type": "action", "text": "Second part of the scene."},
        ]

        split_point = 2  # Split after the dialogue
        new_scenes = scene_manager.split_scene(original_scene.id, split_point)

        assert len(new_scenes) == 2
        # First part should have first elements
        assert len(new_scenes[0].properties.get("elements", [])) == 2
        # Second part should have remaining elements
        assert len(new_scenes[1].properties.get("elements", [])) == 2

    def test_calculate_scene_duration(self, scene_manager):
        """Test calculating estimated scene duration."""
        scene_data = {
            "heading": "INT. ROOM - DAY",
            "elements": [
                {"type": "action", "text": "A brief action line."},
                {"type": "dialogue", "character": "ALICE", "text": "Hello there."},
                {
                    "type": "action",
                    "text": "Another action that takes some time to read.",
                },
                {
                    "type": "dialogue",
                    "character": "BOB",
                    "text": "Hi! How are you doing today?",
                },
            ],
        }

        duration = scene_manager._calculate_scene_duration(scene_data)

        # Should be based on content length (implementation specific)
        assert duration > 0
        assert duration < 10  # Reasonable scene duration in minutes

    def test_auto_number_scenes(self, scene_manager, sample_scenes, sample_script_node):
        """Test automatic scene numbering."""
        # Remove any existing scene numbers
        for scene in sample_scenes:
            scene.properties.pop("scene_number", None)

        scene_manager.auto_number_scenes(sample_script_node.id)

        # Verify all scenes are numbered
        numbered_scenes = scene_manager.operations.get_script_scenes(
            sample_script_node.id, SceneOrderType.SCRIPT
        )

        for i, scene in enumerate(numbered_scenes):
            assert "scene_number" in scene.properties
            assert scene.properties["scene_number"] == str(i + 1)

    def test_find_scene_transitions(self, scene_manager, sample_scenes):
        """Test finding transition patterns between scenes."""
        # Add transition elements
        sample_scenes[0].properties["elements"] = [
            {"type": "action", "text": "Scene content."},
            {"type": "transition", "text": "CUT TO:"},
        ]

        sample_scenes[1].properties["elements"] = [
            {"type": "action", "text": "Scene content."},
            {"type": "transition", "text": "DISSOLVE TO:"},
        ]

        transitions = scene_manager.find_scene_transitions(sample_scenes[0].id)

        assert len(transitions) > 0
        assert transitions[0]["type"] == "CUT TO:"

    def test_location_flow_analysis(
        self, scene_manager, sample_scenes, sample_script_node
    ):
        """Test analyzing location flow through the script."""
        # Create and link locations
        location_map = {
            "APARTMENT": ["INT", [0, 4]],
            "STREET": ["EXT", [1]],
            "OFFICE": ["INT", [2]],
            "RESTAURANT": ["INT", [3]],
        }

        for loc_name, (int_ext, scene_indices) in location_map.items():
            loc_node = scene_manager.operations.create_location(
                Location(
                    interior=(int_ext == "INT"),
                    name=loc_name,
                    raw_text=f"{int_ext}. {loc_name}",
                )
            )

            for idx in scene_indices:
                scene_manager.operations.link_scene_location(
                    sample_scenes[idx].id, loc_node.id
                )

        flow = scene_manager.analyze_location_flow(sample_script_node.id)

        assert "transitions" in flow
        assert "location_counts" in flow
        assert flow["location_counts"]["APARTMENT"] == 2
        assert flow["total_locations"] == 4
        # Should identify the return to apartment

    def test_character_arc_tracking(
        self, scene_manager, sample_scenes, sample_script_node, graph_ops
    ):
        """Test tracking character appearances through scenes."""
        # Create character and link to specific scenes
        char_node = graph_ops.create_character({"name": "PROTAGONIST"})

        # Character appears in scenes 0, 2, 3, 4 (missing from scene 1)
        for i in [0, 2, 3, 4]:
            graph_ops.link_scene_character(
                sample_scenes[i].id,
                char_node.id,
                {"dialogue_count": i + 1},  # Increasing dialogue
            )

        arc = scene_manager.track_character_arc(char_node.id, sample_script_node.id)

        assert arc["character_name"] == "PROTAGONIST"
        assert arc["total_scenes"] == 4
        assert arc["first_appearance"] == 1  # Script order
        assert arc["last_appearance"] == 5
        assert len(arc["scene_gaps"]) > 0  # Gap at scene 2

    def test_parallel_action_detection(self, scene_manager, sample_scenes):
        """Test detecting parallel action sequences."""
        # Mark scenes as parallel action
        sample_scenes[1].properties["elements"] = [
            {"type": "action", "text": "INTERCUT - PHONE CONVERSATION"},
        ]
        sample_scenes[2].properties["elements"] = [
            {"type": "action", "text": "INTERCUT WITH:"},
        ]

        parallel = scene_manager.detect_parallel_action(
            [sample_scenes[1].id, sample_scenes[2].id]
        )

        assert parallel is True

    def test_scene_clustering_by_similarity(
        self, scene_manager, sample_scenes, graph_ops
    ):
        """Test clustering scenes by various similarity metrics."""
        # Create shared elements
        char1 = graph_ops.create_character({"name": "ALICE"})
        char2 = graph_ops.create_character({"name": "BOB"})

        # Scenes 0 and 2 have both characters
        for scene_id in [sample_scenes[0].id, sample_scenes[2].id]:
            graph_ops.link_scene_character(scene_id, char1.id)
            graph_ops.link_scene_character(scene_id, char2.id)

        # Scenes 1 and 3 have only one character each
        graph_ops.link_scene_character(sample_scenes[1].id, char1.id)
        graph_ops.link_scene_character(sample_scenes[3].id, char2.id)

        clusters = scene_manager.cluster_scenes_by_similarity(
            [s.id for s in sample_scenes], metric="character_overlap"
        )

        assert len(clusters) > 0
        # Scenes 0 and 2 should be in same cluster
        cluster_with_0 = next(c for c in clusters if sample_scenes[0].id in c)
        assert sample_scenes[2].id in cluster_with_0

    def test_export_scene_order(self, scene_manager, sample_scenes, sample_script_node):
        """Test exporting scene order data."""
        export_data = scene_manager.export_scene_order(
            sample_script_node.id, include_metadata=True
        )

        assert "script_title" in export_data
        assert "scenes" in export_data
        assert len(export_data["scenes"]) == len(sample_scenes)

        # Each scene should have order info
        for scene_data in export_data["scenes"]:
            assert "scene_id" in scene_data
            assert "heading" in scene_data
            assert "script_order" in scene_data
            assert "temporal_order" in scene_data

    def test_import_scene_order(self, scene_manager, sample_scenes, sample_script_node):
        """Test importing scene order from external data."""
        # Create import data with different order
        import_data = {
            "scenes": [
                {"scene_id": sample_scenes[4].id, "script_order": 1},
                {"scene_id": sample_scenes[3].id, "script_order": 2},
                {"scene_id": sample_scenes[2].id, "script_order": 3},
                {"scene_id": sample_scenes[1].id, "script_order": 4},
                {"scene_id": sample_scenes[0].id, "script_order": 5},
            ]
        }

        scene_manager.import_scene_order(sample_script_node.id, import_data)

        # Verify order was updated
        reordered = scene_manager.operations.get_script_scenes(
            sample_script_node.id, SceneOrderType.SCRIPT
        )

        assert reordered[0].id == sample_scenes[4].id
        assert reordered[4].id == sample_scenes[0].id

    @patch("scriptrag.scene_manager.SceneManager._calculate_scene_duration")
    def test_estimate_script_runtime(
        self, mock_duration, scene_manager, sample_script_node
    ):
        """Test estimating total script runtime."""
        # Mock duration calculation
        mock_duration.return_value = 2.5  # Each scene is 2.5 minutes

        runtime = scene_manager.estimate_script_runtime(sample_script_node.id)

        assert runtime["total_minutes"] == 12.5  # 5 scenes * 2.5 minutes
        assert runtime["total_formatted"] == "12:30"
        assert runtime["scene_count"] == 5
        assert runtime["average_scene_duration"] == 2.5

    def test_scene_manager_error_handling(self, scene_manager):
        """Test error handling in scene manager."""
        fake_id = str(uuid4())

        # Should handle non-existent script gracefully
        result = scene_manager.infer_temporal_order(fake_id)
        assert result == {}

        # Should handle non-existent scene
        issues = scene_manager.analyze_scene_dependencies(fake_id)
        assert issues == []

        # Should handle invalid order type
        with pytest.raises(ValueError):
            scene_manager.reorder_scenes(fake_id, {}, "invalid_order_type")
