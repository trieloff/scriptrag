"""Tests for the MCP server implementation."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as types
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.mcp_server import ScriptRAGMCPServer
from scriptrag.models import Script


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    mcp_settings = MagicMock()
    mcp_settings.host = "localhost"
    mcp_settings.port = 8080
    mcp_settings.max_resources = 1000
    mcp_settings.enable_all_tools = True
    settings.mcp = mcp_settings
    return settings


@pytest.fixture
def mcp_server(mock_settings, tmp_path):
    """Create MCP server instance for testing."""
    # Create a temporary database for testing
    test_db_path = tmp_path / "test.db"
    mock_settings.database = MagicMock()
    mock_settings.database.path = test_db_path
    mock_settings.get_database_path = MagicMock(return_value=test_db_path)

    # Initialize database with schema
    from scriptrag.database.migrations import initialize_database

    initialize_database(test_db_path)

    with patch("scriptrag.mcp_server.ScriptRAG"):
        return ScriptRAGMCPServer(mock_settings)


class TestScriptRAGMCPServer:
    """Test ScriptRAGMCPServer class."""

    def test_initialization(self, mock_settings):
        """Test server initialization."""
        with patch("scriptrag.mcp_server.ScriptRAG") as mock_scriptrag:
            server = ScriptRAGMCPServer(mock_settings)

            assert server.config == mock_settings
            assert server.scriptrag is not None
            assert server.server is not None
            assert server._scripts_cache == {}
            mock_scriptrag.assert_called_once_with(config=mock_settings)

    def test_get_available_tools_all_enabled(self, mcp_server):
        """Test getting available tools when all are enabled."""
        tools = mcp_server.get_available_tools()

        assert len(tools) == 23  # 11 original + 5 mentor tools + 7 bible tools
        tool_names = [t["name"] for t in tools]
        assert "parse_script" in tool_names
        assert "search_scenes" in tool_names
        assert "get_character_info" in tool_names
        assert "analyze_timeline" in tool_names
        assert "list_scripts" in tool_names

    def test_get_available_tools_filtered(self, mcp_server):
        """Test getting available tools with filtering."""
        mcp_server.config.mcp.enable_all_tools = False
        mcp_server.config.mcp.enabled_tools = ["parse_script", "search_scenes"]

        tools = mcp_server.get_available_tools()

        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "parse_script" in tool_names
        assert "search_scenes" in tool_names

    def test_get_available_resources(self, mcp_server):
        """Test getting available resources."""
        resources = mcp_server.get_available_resources()

        assert len(resources) == 5
        assert resources[0]["uri"] == "screenplay://list"
        assert resources[1]["uri"] == "screenplay://{script_id}"
        assert resources[2]["uri"] == "scene://{script_id}/{scene_id}"
        assert resources[3]["uri"] == "character://{script_id}/{character_name}"
        assert resources[4]["uri"] == "timeline://{script_id}"

    @pytest.mark.asyncio
    async def test_handle_list_tools(self, mcp_server):
        """Test handling list tools request."""
        request = types.ListToolsRequest(method="tools/list")
        result = await mcp_server._handle_list_tools(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListToolsResult)
        assert (
            len(result.root.tools) == 23
        )  # 11 original + 5 mentor tools + 7 bible tools
        assert all(isinstance(tool, types.Tool) for tool in result.root.tools)

    @pytest.mark.asyncio
    async def test_tool_parse_script(self, mcp_server, tmp_path):
        """Test parse script tool."""
        # Create a temporary fountain file
        test_file = tmp_path / "test.fountain"
        test_file.write_text(
            "Title: Test Script\n\nFADE IN:\n\n"
            "INT. ROOM - DAY\n\nTest scene.\n\nFADE OUT."
        )

        # Mock the scriptrag.parse_fountain method
        mock_script = Script(title="Test Script", source_file=str(test_file))
        mcp_server.scriptrag.parse_fountain = MagicMock(return_value=mock_script)

        args = {"path": str(test_file), "title": "Override Title"}
        result = await mcp_server._tool_parse_script(args)

        assert result["title"] == "Override Title"
        assert result["source_file"] == str(test_file)
        assert len(mcp_server._scripts_cache) == 1
        # Check that a script was added to cache
        script_id = next(iter(mcp_server._scripts_cache.keys()))
        assert script_id.startswith("script_")
        assert result["script_id"] == script_id

        mcp_server.scriptrag.parse_fountain.assert_called_once_with(str(test_file))

    @pytest.mark.asyncio
    async def test_tool_parse_script_no_path(self, mcp_server):
        """Test parse script tool without path."""
        with pytest.raises(ValueError, match="path is required"):
            await mcp_server._tool_parse_script({})

    @pytest.mark.asyncio
    async def test_tool_search_scenes(self, mcp_server):
        """Test search scenes tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {
            "script_id": "script_0",
            "query": "coffee",
            "location": "INT. CAFE",
            "characters": ["JOHN", "MARY"],
            "limit": 5,
        }

        result = await mcp_server._tool_search_scenes(args)

        assert result["script_id"] == "script_0"
        assert result["results"] == []
        assert result["total_matches"] == 0
        assert result["search_criteria"]["query"] == "coffee"
        assert result["search_criteria"]["location"] == "INT. CAFE"
        assert result["search_criteria"]["characters"] == ["JOHN", "MARY"]

    @pytest.mark.asyncio
    async def test_tool_search_scenes_no_script_id(self, mcp_server):
        """Test search scenes tool without script_id."""
        with pytest.raises(ValueError, match="script_id is required"):
            await mcp_server._tool_search_scenes({})

    @pytest.mark.asyncio
    async def test_tool_get_character_info(self, mcp_server):
        """Test get character info tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {"script_id": "script_0", "character_name": "JOHN"}

        result = await mcp_server._tool_get_character_info(args)

        assert result["script_id"] == "script_0"
        assert result["character_name"] == "JOHN"
        assert result["scenes_count"] == 0
        assert result["dialogue_lines"] == 0
        assert result["relationships"] == []

    @pytest.mark.asyncio
    async def test_tool_analyze_timeline(self, mcp_server):
        """Test analyze timeline tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {"script_id": "script_0", "include_flashbacks": False}

        result = await mcp_server._tool_analyze_timeline(args)

        assert result["script_id"] == "script_0"
        assert result["timeline_type"] == "linear"
        assert result["flashbacks_detected"] is None
        assert result["time_periods"] == []

    @pytest.mark.asyncio
    async def test_tool_list_scripts(self, mcp_server):
        """Test list scripts tool."""
        # Add some scripts to cache
        script1 = Script(title="Script 1", source_file="script1.fountain")
        script2 = Script(title="Script 2", source_file="script2.fountain")
        mcp_server._scripts_cache = {"script_0": script1, "script_1": script2}

        result = await mcp_server._tool_list_scripts({})

        assert result["total"] == 2
        assert len(result["scripts"]) == 2
        assert result["scripts"][0]["script_id"] == "script_0"
        assert result["scripts"][0]["title"] == "Script 1"
        assert result["scripts"][1]["script_id"] == "script_1"
        assert result["scripts"][1]["title"] == "Script 2"

    @pytest.mark.asyncio
    async def test_handle_tool_call_success(self, mcp_server):
        """Test handling successful tool call."""
        # Mock parse_script tool
        mcp_server._tool_parse_script = AsyncMock(return_value={"script_id": "test"})

        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="parse_script", arguments={"path": "/test.fountain"}
            ),
        )

        result = await mcp_server._handle_tool_call(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.CallToolResult)
        assert not result.root.isError
        assert len(result.root.content) == 1
        assert isinstance(result.root.content[0], types.TextContent)
        assert "script_id" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_handle_tool_call_unknown_tool(self, mcp_server):
        """Test handling unknown tool call."""
        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="unknown_tool", arguments={}),
        )

        result = await mcp_server._handle_tool_call(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.CallToolResult)
        assert result.root.isError
        assert "Unknown tool" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_handle_list_resources(self, mcp_server):
        """Test handling list resources request."""
        # Add a script to cache
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache = {"script_0": script}

        request = types.ListResourcesRequest(method="resources/list")
        result = await mcp_server._handle_list_resources(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListResourcesResult)
        assert len(result.root.resources) == 2
        assert str(result.root.resources[0].uri) == "screenplay://list"
        assert str(result.root.resources[1].uri) == "screenplay://script_0"
        assert "Test Script" in result.root.resources[1].name

    @pytest.mark.asyncio
    async def test_handle_read_resource_list(self, mcp_server):
        """Test reading screenplay list resource."""
        # Add scripts to cache
        script1 = Script(title="Script 1", source_file="script1.fountain")
        mcp_server._scripts_cache = {"script_0": script1}

        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("screenplay://list")
            ),
        )

        result = await mcp_server._handle_read_resource(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ReadResourceResult)
        assert len(result.root.contents) == 1
        content = json.loads(result.root.contents[0].text)
        assert len(content["scripts"]) == 1
        assert content["scripts"][0]["script_id"] == "script_0"

    @pytest.mark.asyncio
    async def test_handle_read_resource_script(self, mcp_server):
        """Test reading specific script resource."""
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache = {"script_0": script}

        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("screenplay://script_0")
            ),
        )

        result = await mcp_server._handle_read_resource(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ReadResourceResult)
        content = json.loads(result.root.contents[0].text)
        assert content["script_id"] == "script_0"
        assert content["title"] == "Test Script"

    @pytest.mark.asyncio
    async def test_handle_read_resource_unknown(self, mcp_server):
        """Test reading unknown resource."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("unknown://resource")
            ),
        )

        with pytest.raises(ValueError, match="Unknown resource URI"):
            await mcp_server._handle_read_resource(request)

    @pytest.mark.asyncio
    async def test_handle_list_prompts(self, mcp_server):
        """Test handling list prompts request."""
        request = types.ListPromptsRequest(method="prompts/list")
        result = await mcp_server._handle_list_prompts(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListPromptsResult)
        assert len(result.root.prompts) == 3
        prompt_names = [p.name for p in result.root.prompts]
        assert "analyze_script_structure" in prompt_names
        assert "character_arc_analysis" in prompt_names
        assert "scene_improvement_suggestions" in prompt_names

    @pytest.mark.asyncio
    async def test_handle_get_prompt(self, mcp_server):
        """Test handling get prompt request."""
        request = types.GetPromptRequest(
            method="prompts/get",
            params=types.GetPromptRequestParams(
                name="analyze_script_structure", arguments={"script_id": "script_0"}
            ),
        )

        result = await mcp_server._handle_get_prompt(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.GetPromptResult)
        assert len(result.root.messages) == 1
        assert "three-act structure" in result.root.messages[0].content.text
        assert "script_0" in result.root.messages[0].content.text

    @pytest.mark.asyncio
    async def test_handle_get_prompt_unknown(self, mcp_server):
        """Test handling unknown prompt request."""
        request = types.GetPromptRequest(
            method="prompts/get",
            params=types.GetPromptRequestParams(name="unknown_prompt", arguments={}),
        )

        with pytest.raises(ValueError, match="Unknown prompt"):
            await mcp_server._handle_get_prompt(request)

    def test_get_version(self, mcp_server):
        """Test getting server version."""
        version = mcp_server._get_version()
        assert isinstance(version, str)
        assert version == "0.1.0"

    @pytest.mark.asyncio
    async def test_stop(self, mcp_server):
        """Test stopping the server."""
        # Add some cache data
        mcp_server._scripts_cache = {"script_0": MagicMock()}

        await mcp_server.stop()

        assert mcp_server._scripts_cache == {}

    @pytest.mark.asyncio
    async def test_tool_get_scene_details(self, mcp_server, tmp_path):  # noqa: ARG002
        """Test get scene details tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        script_id = "test_script_1"
        mcp_server._scripts_cache[script_id] = script

        # Setup test data in database
        from scriptrag.database.connection import DatabaseConnection

        db_connection = DatabaseConnection(str(mcp_server.config.get_database_path()))
        with db_connection.transaction() as conn:
            # Insert test script
            conn.execute(
                "INSERT INTO scripts (id, title) VALUES (?, ?)",
                (script_id, "Test Script"),
            )

            # Insert test location
            location_id = "loc_1"
            conn.execute(
                """INSERT INTO locations (id, script_id, name, interior,
                   time_of_day, raw_text) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    location_id,
                    script_id,
                    "COFFEE SHOP",
                    True,
                    "DAY",
                    "INT. COFFEE SHOP - DAY",
                ),
            )

            # Insert test scene
            scene_id = "scene_1"
            conn.execute(
                """INSERT INTO scenes (id, script_id, location_id, heading,
                   description, script_order, temporal_order, logical_order,
                   estimated_duration_minutes, time_of_day, date_in_story)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scene_id,
                    script_id,
                    location_id,
                    "INT. COFFEE SHOP - DAY",
                    "Opening scene in coffee shop",
                    1,
                    1,
                    1,
                    3.5,
                    "DAY",
                    "Day 1",
                ),
            )

            # Insert characters
            char1_id = "char_1"
            char2_id = "char_2"
            conn.execute(
                "INSERT INTO characters (id, script_id, name) VALUES (?, ?, ?)",
                (char1_id, script_id, "JOHN"),
            )
            conn.execute(
                "INSERT INTO characters (id, script_id, name) VALUES (?, ?, ?)",
                (char2_id, script_id, "MARY"),
            )

            # Insert scene elements
            elements = [
                (
                    1,
                    "action",
                    "The coffee shop bustles with morning activity.",
                    None,
                    None,
                ),
                (2, "character", "JOHN", char1_id, "JOHN"),
                (3, "dialogue", "I've been waiting for this moment.", char1_id, "JOHN"),
                (4, "parenthetical", "nervously", char1_id, "JOHN"),
                (5, "dialogue", "What took you so long?", char1_id, "JOHN"),
                (
                    6,
                    "action",
                    "Mary enters, shaking rain from her umbrella.",
                    None,
                    None,
                ),
                (7, "character", "MARY", char2_id, "MARY"),
                (8, "dialogue", "Traffic was terrible.", char2_id, "MARY"),
                (9, "parenthetical", "sitting down", char2_id, "MARY"),
                (10, "dialogue", "But I'm here now.", char2_id, "MARY"),
            ]

            for order, elem_type, text, char_id, char_name in elements:
                elem_id = f"elem_{order}"
                conn.execute(
                    """INSERT INTO scene_elements (id, scene_id, element_type, text,
                       raw_text, order_in_scene, character_id, character_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        elem_id,
                        scene_id,
                        elem_type,
                        text,
                        text,
                        order,
                        char_id,
                        char_name,
                    ),
                )

        # Test successful retrieval
        args = {"script_id": script_id, "scene_id": scene_id}
        result = await mcp_server._tool_get_scene_details(args)

        assert result["script_id"] == script_id
        assert result["scene_id"] == scene_id
        assert result["heading"] == "INT. COFFEE SHOP - DAY"
        assert "bustles with morning activity" in result["action"]
        assert "Mary enters" in result["action"]
        assert result["page_number"] == 1

        # Check dialogue structure
        assert len(result["dialogue"]) == 4  # 2 from John, 2 from Mary

        # First dialogue entry (John)
        assert result["dialogue"][0]["character"] == "JOHN"
        assert result["dialogue"][0]["text"] == "I've been waiting for this moment."
        assert result["dialogue"][0]["parentheticals"] == ["nervously"]

        # Second dialogue entry (John)
        assert result["dialogue"][1]["character"] == "JOHN"
        assert result["dialogue"][1]["text"] == "What took you so long?"
        assert result["dialogue"][1]["parentheticals"] == []

        # Third dialogue entry (Mary)
        assert result["dialogue"][2]["character"] == "MARY"
        assert result["dialogue"][2]["text"] == "Traffic was terrible."
        assert result["dialogue"][2]["parentheticals"] == ["sitting down"]

        # Check characters
        assert len(result["characters"]) == 2
        john_stats = next(c for c in result["characters"] if c["name"] == "JOHN")
        mary_stats = next(c for c in result["characters"] if c["name"] == "MARY")
        assert john_stats["line_count"] == 2
        assert mary_stats["line_count"] == 2

        # Check location info
        assert result["location"]["name"] == "COFFEE SHOP"
        assert result["location"]["interior"] == 1  # SQLite returns 1 for True
        assert result["location"]["time_of_day"] == "DAY"

        # Check additional metadata
        assert result["temporal_order"] == 1
        assert result["logical_order"] == 1
        assert result["estimated_duration_minutes"] == 3.5
        assert result["time_of_day"] == "DAY"
        assert result["date_in_story"] == "Day 1"
        assert result["description"] == "Opening scene in coffee shop"

    @pytest.mark.asyncio
    async def test_tool_get_scene_details_not_found(self, mcp_server):
        """Test get scene details tool with non-existent scene."""
        # Add a script to cache
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {"script_id": "script_0", "scene_id": "non_existent_scene"}

        with pytest.raises(ValueError, match="Scene not found"):
            await mcp_server._tool_get_scene_details(args)

    @pytest.mark.asyncio
    async def test_tool_get_scene_details_no_location(self, mcp_server):
        """Test get scene details tool for scene without location."""
        # Add a script to cache
        script = Script(title="Test Script", source_file="test.fountain")
        script_id = "test_script_2"
        mcp_server._scripts_cache[script_id] = script

        # Setup test data without location
        from scriptrag.database.connection import DatabaseConnection

        db_connection = DatabaseConnection(str(mcp_server.config.get_database_path()))
        with db_connection.transaction() as conn:
            # Insert test script
            conn.execute(
                "INSERT INTO scripts (id, title) VALUES (?, ?)",
                (script_id, "Test Script"),
            )

            # Insert test scene without location
            scene_id = "scene_no_loc"
            conn.execute(
                """INSERT INTO scenes (id, script_id, heading, script_order)
                   VALUES (?, ?, ?, ?)""",
                (scene_id, script_id, "FADE IN:", 1),
            )

        args = {"script_id": script_id, "scene_id": scene_id}
        result = await mcp_server._tool_get_scene_details(args)

        assert result["location"] is None
        assert result["heading"] == "FADE IN:"
        assert result["dialogue"] == []
        assert result["characters"] == []

    @pytest.mark.asyncio
    async def test_tool_get_scene_details_missing_params(self, mcp_server):
        """Test get scene details tool with missing parameters."""
        # Missing script_id
        with pytest.raises(ValueError, match="script_id and scene_id are required"):
            await mcp_server._tool_get_scene_details({"scene_id": "scene_1"})

        # Missing scene_id
        with pytest.raises(ValueError, match="script_id and scene_id are required"):
            await mcp_server._tool_get_scene_details({"script_id": "script_0"})

        # Both missing
        with pytest.raises(ValueError, match="script_id and scene_id are required"):
            await mcp_server._tool_get_scene_details({})

    @pytest.mark.asyncio
    async def test_tool_get_scene_details_invalid_script(self, mcp_server):
        """Test get scene details tool with invalid script_id."""
        args = {"script_id": "non_existent_script", "scene_id": "scene_1"}

        with pytest.raises(ValueError, match="Script not found"):
            await mcp_server._tool_get_scene_details(args)
