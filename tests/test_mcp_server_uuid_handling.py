"""Test MCP server script UUID handling improvements."""

import uuid
from unittest.mock import patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.mcp_server import ScriptRAGMCPServer
from scriptrag.models import Character, Location, Scene, Script


@pytest.fixture
def mcp_server_with_data():
    """Create MCP server with test data."""
    settings = ScriptRAGSettings(database_path=":memory:")

    with patch("scriptrag.mcp_server.ScriptRAG"):
        server = ScriptRAGMCPServer(settings)

        # Create test script with full UUID
        script = Script(
            title="UUID Test Script",
            source_file="test.fountain",
            author="Test Author",
            genre="Drama",
        )
        script_uuid = str(script.id)

        # Add to cache with full UUID (not truncated)
        server._scripts_cache[script_uuid] = script

        # Setup database
        with DatabaseConnection(":memory:") as conn:
            graph_ops = GraphOperations(conn)

            # Create script in database
            script_node_id = graph_ops.create_script_graph(script)

            # Update node with correct entity_id
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_uuid, script_node_id),
            )

            # Create test scenes
            scenes = []
            for i in range(3):
                scene = Scene(
                    script_id=script.id,
                    heading=f"INT. ROOM {i + 1} - DAY",
                    description=f"Test scene {i + 1}",
                    script_order=i + 1,
                    temporal_order=i + 1,
                )
                scene_node_id = graph_ops.create_scene_node(scene, script_node_id)
                scenes.append(scene)

                # Create location with properties
                location = Location(
                    name=f"Room {i + 1}",
                    interior=True,
                    time_of_day="DAY",
                )
                loc_node_id = graph_ops.create_location_node(location, script_node_id)
                graph_ops.connect_scene_to_location(scene_node_id, loc_node_id)

            # Create characters
            john = Character(name="JOHN", description="Main character")
            jane = Character(name="JANE", description="Supporting character")

            john_node_id = graph_ops.create_character_node(john, script_node_id)
            jane_node_id = graph_ops.create_character_node(jane, script_node_id)

            # Add characters to scenes
            for scene_node in graph_ops.graph.get_nodes_by_type("scene"):
                graph_ops.add_character_to_scene(john_node_id, scene_node.id)
                if scene_node.label == "INT. ROOM 2 - DAY":
                    graph_ops.add_character_to_scene(jane_node_id, scene_node.id)

        return server, script, script_uuid


class TestMCPServerUUIDHandling:
    """Test that MCP server properly handles full script UUIDs."""

    @pytest.mark.asyncio
    async def test_search_scenes_uses_full_uuid(self, mcp_server_with_data):
        """Test that search_scenes uses full script UUID in queries."""
        server, script, script_uuid = mcp_server_with_data

        # Search scenes with full UUID
        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "Room",
            }
        )

        assert result["script_id"] == script_uuid
        assert len(result["scenes"]) == 3
        assert all("Room" in scene["heading"] for scene in result["scenes"])

    @pytest.mark.asyncio
    async def test_search_scenes_location_property_parsing(self, mcp_server_with_data):
        """Test that search_scenes properly parses location properties."""
        server, script, script_uuid = mcp_server_with_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
            }
        )

        # Verify location names are extracted from properties
        for scene in result["scenes"]:
            assert scene["location"] is not None
            assert "Room" in scene["location"]
            assert scene["location"] != "location"  # Not using generic label

    @pytest.mark.asyncio
    async def test_search_scenes_handles_invalid_location_json(
        self, mcp_server_with_data
    ):
        """Test graceful handling of invalid location property JSON."""
        server, script, script_uuid = mcp_server_with_data

        # Corrupt location properties
        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            conn.execute(
                "UPDATE nodes SET properties_json = ? WHERE node_type = ? LIMIT 1",
                ("{invalid json}", "location"),
            )

        # Should still work, falling back to label
        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
            }
        )

        assert len(result["scenes"]) == 3

    @pytest.mark.asyncio
    async def test_get_character_info_uses_full_uuid(self, mcp_server_with_data):
        """Test that get_character_info uses full script UUID."""
        server, script, script_uuid = mcp_server_with_data

        result = await server._tool_get_character_info(
            {
                "script_id": script_uuid,
                "character_name": "JOHN",
            }
        )

        assert result["script_id"] == script_uuid
        assert result["character"]["name"] == "JOHN"
        assert result["statistics"]["scene_count"] > 0

    @pytest.mark.asyncio
    async def test_get_character_info_dialogue_count_from_scene_elements(
        self, mcp_server_with_data
    ):
        """Test that dialogue count is properly retrieved from scene_elements table."""
        server, script, script_uuid = mcp_server_with_data

        # Add dialogue to scene_elements
        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            # Get character and scene IDs
            char_cursor = conn.execute(
                "SELECT id FROM characters WHERE name = ?", ("JOHN",)
            )
            char_id = char_cursor.fetchone()["id"]

            scene_cursor = conn.execute("SELECT id FROM scenes LIMIT 1")
            scene_id = scene_cursor.fetchone()["id"]

            # Add dialogue elements
            for i in range(5):
                conn.execute(
                    """
                    INSERT INTO scene_elements (
                        id, scene_id, element_type, character_id, text, order_in_scene
                    )
                    VALUES (?, ?, 'dialogue', ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), scene_id, char_id, f"Test dialogue {i}", i),
                )

        result = await server._tool_get_character_info(
            {
                "script_id": script_uuid,
                "character_name": "JOHN",
            }
        )

        assert result["statistics"]["dialogue_count"] == 5

    @pytest.mark.asyncio
    async def test_analyze_timeline_uses_full_uuid(self, mcp_server_with_data):
        """Test that analyze_timeline uses full script UUID."""
        server, script, script_uuid = mcp_server_with_data

        result = await server._tool_analyze_timeline(
            {
                "script_id": script_uuid,
                "include_flashbacks": True,
            }
        )

        assert result["script_id"] == script_uuid
        assert result["total_scenes"] == 3
        assert result["is_linear"] is True

    @pytest.mark.asyncio
    async def test_update_scene_validates_with_full_uuid(self, mcp_server_with_data):
        """Test that update_scene properly validates using full UUID."""
        server, script, script_uuid = mcp_server_with_data

        # Get a scene ID
        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            cursor = conn.execute(
                "SELECT id FROM scenes WHERE script_id = ? LIMIT 1",
                (str(script.id),),
            )
            scene_id = cursor.fetchone()["id"]

        # Update scene
        result = await server._tool_update_scene(
            {
                "script_id": script_uuid,
                "scene_id": scene_id,
                "heading": "INT. UPDATED ROOM - NIGHT",
            }
        )

        assert result["success"] is True
        assert result["scene_id"] == scene_id

    @pytest.mark.asyncio
    async def test_uuid_validation_with_truncated_id(self, mcp_server_with_data):
        """Test that truncated script IDs are properly handled."""
        server, script, script_uuid = mcp_server_with_data

        # Use truncated ID (first 8 chars of hex)
        truncated_id = f"script_{script.id.hex[:8]}"

        # Add mapping in cache
        server._scripts_cache[truncated_id] = script

        # Should still work with truncated ID
        result = await server._tool_search_scenes(
            {
                "script_id": truncated_id,
                "query": "Room",
            }
        )

        # Result uses truncated ID but queries use full UUID
        assert result["script_id"] == truncated_id
        assert len(result["scenes"]) == 3

    @pytest.mark.asyncio
    async def test_character_not_found_with_correct_uuid(self, mcp_server_with_data):
        """Test proper error when character not found even with correct UUID."""
        server, script, script_uuid = mcp_server_with_data

        with pytest.raises(
            ValueError, match="Character 'NONEXISTENT' not found in script"
        ):
            await server._tool_get_character_info(
                {
                    "script_id": script_uuid,
                    "character_name": "NONEXISTENT",
                }
            )

    @pytest.mark.asyncio
    async def test_scene_update_wrong_script_rejected(self, mcp_server_with_data):
        """Test that scene updates are rejected for wrong script."""
        server, script, script_uuid = mcp_server_with_data

        # Create another script
        other_script = Script(title="Other Script", source_file="other.fountain")
        other_uuid = str(other_script.id)
        server._scripts_cache[other_uuid] = other_script

        # Get scene from first script
        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            cursor = conn.execute(
                "SELECT id FROM scenes WHERE script_id = ? LIMIT 1",
                (str(script.id),),
            )
            scene_id = cursor.fetchone()["id"]

        # Try to update with wrong script ID
        with pytest.raises(ValueError, match="Scene not found in script"):
            await server._tool_update_scene(
                {
                    "script_id": other_uuid,
                    "scene_id": scene_id,
                    "heading": "SHOULD FAIL",
                }
            )
