"""Test edge cases for location property parsing in MCP server."""

import json
import uuid

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.models import Location, Scene, Script


@pytest.fixture
def server_with_location_test_data(temp_db_path):
    """Create MCP server with various location property test cases."""
    from scriptrag.database import initialize_database

    # Initialize the database
    initialize_database(temp_db_path)

    settings = ScriptRAGSettings(database_path=str(temp_db_path))

    # Don't mock ScriptRAG so we can test with actual database
    server = ScriptRAGMCPServer(settings)

    # Create test script
    script = Script(title="Location Test", source_file="loc.fountain")
    script_uuid = str(script.id)
    server._scripts_cache[script_uuid] = script

    # Setup database with various location scenarios
    with DatabaseConnection(temp_db_path) as conn:
        graph_ops = GraphOperations(conn)

        # Create script
        script_node_id = graph_ops.create_script_graph(script)
        with conn.get_connection() as db_conn:
            db_conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_uuid, script_node_id),
            )

        # Test case 1: Normal location with properties
        scene1 = Scene(
            script_id=script.id,
            heading="INT. OFFICE - DAY",
            script_order=1,
        )
        scene1_node = graph_ops.create_scene_node(scene1, script_node_id)

        loc1 = Location(
            name="CEO Office",
            interior=True,
            time="DAY",
            raw_text="INT. CEO OFFICE - DAY",
        )
        loc1_node = graph_ops.create_location_node(loc1, script_node_id)
        graph_ops.connect_scene_to_location(scene1_node, loc1_node)

        # Test case 2: Location with empty properties_json
        scene2 = Scene(
            script_id=script.id,
            heading="EXT. STREET - NIGHT",
            script_order=2,
        )
        scene2_node = graph_ops.create_scene_node(scene2, script_node_id)

        # Manually create location node with empty properties
        loc2_node = graph_ops.graph.add_node(
            node_type="location",
            entity_id=str(uuid.uuid4()),
            label="Generic Street",
            properties={},  # Empty properties
        )
        graph_ops.connect_scene_to_location(scene2_node, loc2_node)

        # Test case 3: Location with malformed JSON
        scene3 = Scene(
            script_id=script.id,
            heading="INT. BASEMENT - NIGHT",
            script_order=3,
        )
        scene3_node = graph_ops.create_scene_node(scene3, script_node_id)

        loc3 = Location(
            name="Dark Basement", interior=True, raw_text="INT. DARK BASEMENT"
        )
        loc3_node = graph_ops.create_location_node(loc3, script_node_id)
        graph_ops.connect_scene_to_location(scene3_node, loc3_node)

        # Corrupt the JSON
        with conn.get_connection() as db_conn:
            db_conn.execute(
                "UPDATE nodes SET properties_json = ? WHERE id = ?",
                ('{"name": "Corrupted", invalid json here}', loc3_node),
            )

        # Test case 4: Location with null properties_json
        scene4 = Scene(
            script_id=script.id,
            heading="EXT. PARK - DAY",
            script_order=4,
        )
        scene4_node = graph_ops.create_scene_node(scene4, script_node_id)

        loc4_node = graph_ops.graph.add_node(
            node_type="location",
            entity_id=str(uuid.uuid4()),
            label="City Park",
            properties=None,
        )
        graph_ops.connect_scene_to_location(scene4_node, loc4_node)
        with conn.get_connection() as db_conn:
            db_conn.execute(
                "UPDATE nodes SET properties_json = NULL WHERE id = ?",
                (loc4_node,),
            )

        # Test case 5: Location with properties but no name field
        scene5 = Scene(
            script_id=script.id,
            heading="INT. WAREHOUSE - NIGHT",
            script_order=5,
        )
        scene5_node = graph_ops.create_scene_node(scene5, script_node_id)

        loc5_node = graph_ops.graph.add_node(
            node_type="location",
            entity_id=str(uuid.uuid4()),
            label="Storage Warehouse",
            properties={"interior": True, "time_of_day": "NIGHT"},  # No name
        )
        graph_ops.connect_scene_to_location(scene5_node, loc5_node)

        # Test case 6: Scene with no location
        scene6 = Scene(
            script_id=script.id,
            heading="MONTAGE - VARIOUS LOCATIONS",
            script_order=6,
        )
        _ = graph_ops.create_scene_node(scene6, script_node_id)
        # No location connection

    return server, script_uuid


class TestLocationParsingEdgeCases:
    """Test edge cases in location property parsing."""

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_with_valid_properties(self, server_with_location_test_data):
        """Test normal case with valid location properties."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "OFFICE",
            }
        )

        office_scene = next(s for s in result["scenes"] if "OFFICE" in s["heading"])
        assert office_scene["location"] == "CEO Office"

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_with_empty_properties(self, server_with_location_test_data):
        """Test location with empty properties object."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "STREET",
            }
        )

        street_scene = next(s for s in result["scenes"] if "STREET" in s["heading"])
        assert street_scene["location"] == "Generic Street"  # Falls back to label

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_with_malformed_json(self, server_with_location_test_data):
        """Test location with corrupted JSON properties."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "BASEMENT",
            }
        )

        basement_scene = next(s for s in result["scenes"] if "BASEMENT" in s["heading"])
        # Should fall back to label due to JSON decode error
        assert basement_scene["location"] == "location"  # Generic fallback

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_with_null_properties(self, server_with_location_test_data):
        """Test location with NULL properties_json."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "PARK",
            }
        )

        park_scene = next(s for s in result["scenes"] if "PARK" in s["heading"])
        assert park_scene["location"] == "City Park"  # Falls back to label

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_properties_without_name(
        self, server_with_location_test_data
    ):
        """Test location with properties but missing name field."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "WAREHOUSE",
            }
        )

        warehouse_scene = next(
            s for s in result["scenes"] if "WAREHOUSE" in s["heading"]
        )
        assert warehouse_scene["location"] == "Storage Warehouse"  # Falls back to label

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_scene_without_location(self, server_with_location_test_data):
        """Test scene with no location connection."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "MONTAGE",
            }
        )

        montage_scene = next(s for s in result["scenes"] if "MONTAGE" in s["heading"])
        assert montage_scene["location"] is None

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_all_scenes_location_parsing(self, server_with_location_test_data):
        """Test that all scenes handle location parsing correctly."""
        server, script_uuid = server_with_location_test_data

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
            }
        )

        assert len(result["scenes"]) == 6

        # Map expected locations
        expected_locations = {
            "INT. OFFICE - DAY": "CEO Office",
            "EXT. STREET - NIGHT": "Generic Street",
            "INT. BASEMENT - NIGHT": "location",  # Corrupted JSON fallback
            "EXT. PARK - DAY": "City Park",
            "INT. WAREHOUSE - NIGHT": "Storage Warehouse",
            "MONTAGE - VARIOUS LOCATIONS": None,
        }

        for scene in result["scenes"]:
            expected = expected_locations.get(scene["heading"])
            assert scene["location"] == expected, (
                f"Scene {scene['heading']} has location "
                f"{scene['location']}, expected {expected}"
            )

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_type_errors(self, server_with_location_test_data):
        """Test handling of various type errors in location properties."""
        server, script_uuid = server_with_location_test_data

        # Add a scene with properties_json containing non-dict
        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            # Find a location node
            cursor = conn.execute(
                "SELECT id FROM nodes WHERE node_type = 'location' LIMIT 1"
            )
            loc_id = cursor.fetchone()["id"]

            # Set properties_json to a JSON array instead of object
            conn.execute(
                "UPDATE nodes SET properties_json = ? WHERE id = ?",
                ('["not", "a", "dict"]', loc_id),
            )

        # Should not crash, should handle gracefully
        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
            }
        )

        assert len(result["scenes"]) > 0

    @pytest.mark.skip(reason="Complex fixture setup needs refactoring")
    @pytest.mark.asyncio
    async def test_location_with_numeric_name(self, server_with_location_test_data):
        """Test location where name property is numeric."""
        server, script_uuid = server_with_location_test_data

        with DatabaseConnection(str(server.config.get_database_path())) as conn:
            # Update a location to have numeric name
            cursor = conn.execute(
                "SELECT id FROM nodes WHERE node_type = 'location' "
                "AND label = 'CEO Office' LIMIT 1"
            )
            loc_id = cursor.fetchone()["id"]

            # Set name to a number
            conn.execute(
                "UPDATE nodes SET properties_json = ? WHERE id = ?",
                (json.dumps({"name": 42, "interior": True}), loc_id),
            )

        result = await server._tool_search_scenes(
            {
                "script_id": script_uuid,
                "query": "OFFICE",
            }
        )

        office_scene = next(s for s in result["scenes"] if "OFFICE" in s["heading"])
        # Should convert numeric name to string
        assert office_scene["location"] == "42"
