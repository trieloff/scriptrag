"""Tests for the MCP server implementation."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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


@pytest.fixture
def store_script_in_db(mcp_server):
    """Helper function to properly store a script in the database."""
    from scriptrag.database.connection import DatabaseConnection

    def _store_script(script):
        """Store script and return the database ID."""
        db_path = str(mcp_server.config.get_database_path())
        with DatabaseConnection(db_path) as conn, conn.transaction() as tx:
            # Store the script in the database
            tx.execute(
                """
                    INSERT INTO scripts (id, title, author, format, genre,
                    description, is_series)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    str(script.id),
                    script.title,
                    script.author,
                    script.format,
                    script.genre,
                    script.description,
                    script.is_series,
                ),
            )
        return script.id

    return _store_script


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


class TestParseScriptTool:
    """Comprehensive tests for parse_script tool."""

    @pytest.mark.asyncio
    async def test_parse_script_success(self, mcp_server, tmp_path):
        """Test successful script parsing."""
        test_file = tmp_path / "test.fountain"
        test_file.write_text("Title: Test Script\n\nFADE IN:")

        mock_script = Script(title="Test Script", source_file=str(test_file))
        mock_script.scenes = [MagicMock(), MagicMock()]
        mock_script.characters = {"JOHN", "JANE"}
        mcp_server.scriptrag.parse_fountain = MagicMock(return_value=mock_script)

        result = await mcp_server._tool_parse_script({"path": str(test_file)})

        assert result["title"] == "Test Script"
        assert result["source_file"] == str(test_file)
        assert result["scenes_count"] == 2
        assert set(result["characters"]) == {"JOHN", "JANE"}
        assert "script_id" in result
        assert result["script_id"].startswith("script_")

    @pytest.mark.asyncio
    async def test_parse_script_file_not_found(self, mcp_server):
        """Test parsing non-existent file."""
        with pytest.raises(ValueError, match="File not found"):
            await mcp_server._tool_parse_script({"path": "/nonexistent/file.fountain"})

    @pytest.mark.asyncio
    async def test_parse_script_directory_path(self, mcp_server, tmp_path):
        """Test parsing directory instead of file."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(ValueError, match="Path is not a file"):
            await mcp_server._tool_parse_script({"path": str(test_dir)})

    @pytest.mark.asyncio
    async def test_parse_script_invalid_extension(self, mcp_server, tmp_path):
        """Test parsing file with invalid extension."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("not a fountain file")

        with pytest.raises(ValueError, match="Invalid file type"):
            await mcp_server._tool_parse_script({"path": str(test_file)})

    @pytest.mark.asyncio
    async def test_parse_script_valid_extensions(self, mcp_server, tmp_path):
        """Test parsing files with all valid extensions."""
        mock_script = Script(title="Test", source_file="test")
        mcp_server.scriptrag.parse_fountain = MagicMock(return_value=mock_script)

        for ext in [".fountain", ".spmd", ".txt", ".FOUNTAIN", ".SPMD", ".TXT"]:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("Title: Test")

            result = await mcp_server._tool_parse_script({"path": str(test_file)})
            assert "script_id" in result

    @pytest.mark.asyncio
    async def test_parse_script_cache_limit(self, mcp_server, tmp_path):
        """Test script cache size limit."""
        mcp_server._max_cache_size = 3
        mock_script = Script(title="Test", source_file="test")
        mcp_server.scriptrag.parse_fountain = MagicMock(return_value=mock_script)

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Title: Test")

        # Add scripts until cache is full
        script_ids = []
        for _ in range(5):
            result = await mcp_server._tool_parse_script({"path": str(test_file)})
            script_ids.append(result["script_id"])

        # Cache should only contain last 3 scripts
        assert len(mcp_server._scripts_cache) == 3
        assert script_ids[0] not in mcp_server._scripts_cache
        assert script_ids[1] not in mcp_server._scripts_cache
        assert script_ids[2] in mcp_server._scripts_cache
        assert script_ids[3] in mcp_server._scripts_cache
        assert script_ids[4] in mcp_server._scripts_cache


class TestSearchScenesTool:
    """Comprehensive tests for search_scenes tool."""

    @pytest.mark.asyncio
    async def test_search_scenes_invalid_script_id(self, mcp_server):
        """Test searching with invalid script ID."""
        with pytest.raises(ValueError, match="Script not found"):
            await mcp_server._tool_search_scenes({"script_id": "invalid_id"})

    @pytest.mark.asyncio
    async def test_search_scenes_with_all_filters(self, mcp_server, _tmp_path):
        """Test searching scenes with all filter types."""
        # Setup database with test data
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Character, Location, Scene

        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"  # Use script's UUID to create ID
        mcp_server._scripts_cache[script_id] = script

        # Create test data in database
        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)

            # Create script graph and get script node
            script_node_id = graph_ops.create_script_graph(script)
            # Update the script entity_id to match our test ID
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

            # Create scene with location and characters
            scene = Scene(
                id=uuid4(),
                heading="INT. COFFEE SHOP - DAY",
                description="John meets Mary for coffee",
                script_order=1,
                script_id=script.id,  # Use script's actual UUID
                time_of_day="DAY",
            )
            scene_node_id = graph_ops.create_scene_node(scene, script_node_id)

            # Create characters
            john = Character(id=uuid4(), name="JOHN", description="")
            mary = Character(id=uuid4(), name="MARY", description="")
            john_node_id = graph_ops.create_character_node(john, script_node_id)
            mary_node_id = graph_ops.create_character_node(mary, script_node_id)

            # Create location
            location = Location(
                interior=True,
                name="COFFEE SHOP",
                time="DAY",
                raw_text="INT. COFFEE SHOP - DAY",
            )
            location_node_id = graph_ops.create_location_node(location, script_node_id)

            # Create relationships
            graph_ops.graph.add_edge(john_node_id, scene_node_id, "APPEARS_IN")
            graph_ops.graph.add_edge(mary_node_id, scene_node_id, "APPEARS_IN")
            graph_ops.graph.add_edge(scene_node_id, location_node_id, "AT_LOCATION")

        # Test search with all filters
        result = await mcp_server._tool_search_scenes(
            {
                "script_id": script_id,
                "query": "coffee",
                "location": "COFFEE SHOP",
                "characters": ["JOHN", "MARY"],
                "limit": 10,
            }
        )

        assert result["script_id"] == script_id
        assert result["total_matches"] == 1
        assert len(result["results"]) == 1
        scene_result = result["results"][0]
        assert "coffee" in scene_result["description"].lower()
        assert scene_result["location"] == "COFFEE SHOP"
        assert "JOHN" in scene_result["characters"]
        assert "MARY" in scene_result["characters"]

    @pytest.mark.asyncio
    async def test_search_scenes_empty_results(self, mcp_server):
        """Test search returning no results."""
        script = Script(title="Test", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        result = await mcp_server._tool_search_scenes(
            {"script_id": "script_0", "query": "nonexistent"}
        )

        assert result["total_matches"] == 0
        assert result["results"] == []


class TestGetCharacterInfoTool:
    """Comprehensive tests for get_character_info tool."""

    @pytest.mark.asyncio
    async def test_get_character_info_missing_params(self, mcp_server):
        """Test with missing required parameters."""
        with pytest.raises(
            ValueError, match="script_id and character_name are required"
        ):
            await mcp_server._tool_get_character_info({"script_id": "test"})

        with pytest.raises(
            ValueError, match="script_id and character_name are required"
        ):
            await mcp_server._tool_get_character_info({"character_name": "JOHN"})

    @pytest.mark.asyncio
    async def test_get_character_info_not_found(self, mcp_server):
        """Test getting info for non-existent character."""
        script = Script(title="Test", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        result = await mcp_server._tool_get_character_info(
            {"script_id": "script_0", "character_name": "NONEXISTENT"}
        )

        assert result["error"] == "Character 'NONEXISTENT' not found in script"
        assert result["scenes_count"] == 0
        assert result["dialogue_lines"] == 0

    @pytest.mark.asyncio
    async def test_get_character_info_with_relationships(
        self, mcp_server, store_script_in_db
    ):
        """Test getting character info with relationships."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Character, Scene

        script = Script(title="Test", source_file="test.fountain")
        # CONSPIRACY FIX: Store script in database first
        stored_script_id = store_script_in_db(script)
        script.id = stored_script_id

        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)

            # Create script and characters
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )
            john = Character(id=uuid4(), name="JOHN", description="Main character")
            jane = Character(
                id=uuid4(), name="JANE", description="Supporting character"
            )
            john_node_id = graph_ops.create_character_node(john, script_node_id)
            jane_node_id = graph_ops.create_character_node(jane, script_node_id)

            # Create scene where both appear
            scene = Scene(
                id=uuid4(),
                heading="INT. ROOM - DAY",
                description="",
                script_order=1,
                script_id=script.id,
            )
            scene_node_id = graph_ops.create_scene_node(scene, script_node_id)

            # Create relationships
            graph_ops.graph.add_edge(john_node_id, scene_node_id, "APPEARS_IN")
            graph_ops.graph.add_edge(jane_node_id, scene_node_id, "APPEARS_IN")
            graph_ops.graph.add_edge(john_node_id, jane_node_id, "SPEAKS_TO")

            # Add dialogue
            conn.execute(
                """
                INSERT INTO scene_elements (id, element_type, text, raw_text, scene_id,
                                    order_in_scene, character_id, character_name,
                                    created_at, updated_at)
                VALUES (?, 'dialogue', 'Hello Jane', 'Hello Jane', ?, 0, ?, 'JOHN',
                        datetime('now'), datetime('now'))
            """,
                (str(uuid4()), str(scene.id), str(john.id)),
            )

        result = await mcp_server._tool_get_character_info(
            {"script_id": script_id, "character_name": "JOHN"}
        )

        assert result["character_name"] == "JOHN"
        assert result["description"] == "Main character"
        assert result["scenes_count"] == 1
        assert result["dialogue_lines"] == 1
        assert len(result["relationships"]) > 0


class TestAnalyzeTimelineTool:
    """Comprehensive tests for analyze_timeline tool."""

    @pytest.mark.asyncio
    async def test_analyze_timeline_no_script_id(self, mcp_server):
        """Test without script_id."""
        with pytest.raises(ValueError, match="script_id is required"):
            await mcp_server._tool_analyze_timeline({})

    @pytest.mark.asyncio
    async def test_analyze_timeline_non_linear(self, mcp_server):
        """Test analyzing non-linear timeline with flashbacks."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Scene

        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

            # Create scenes with non-linear temporal order
            scenes = [
                Scene(
                    id=uuid4(),
                    heading="INT. PRESENT - DAY",
                    description="",
                    script_order=1,
                    temporal_order=3,
                    script_id=script.id,
                    time_of_day="DAY",
                ),
                Scene(
                    id=uuid4(),
                    heading="INT. PAST - NIGHT",
                    description="",
                    script_order=2,
                    temporal_order=1,
                    script_id=script.id,
                    time_of_day="NIGHT",
                ),
                Scene(
                    id=uuid4(),
                    heading="INT. PRESENT - DAY",
                    description="",
                    script_order=3,
                    temporal_order=4,
                    script_id=script.id,
                    time_of_day="DAY",
                ),
            ]

            for scene in scenes:
                graph_ops.create_scene_node(scene, script_node_id)

        result = await mcp_server._tool_analyze_timeline(
            {"script_id": script_id, "include_flashbacks": True}
        )

        assert result["timeline_type"] == "non_linear"
        assert result["flashbacks_detected"] > 0
        assert len(result["temporal_jumps"]) > 0
        assert result["time_distribution"]["DAY"] == 2
        assert result["time_distribution"]["NIGHT"] == 1


class TestUpdateSceneTool:
    """Comprehensive tests for update_scene tool."""

    @pytest.mark.asyncio
    async def test_update_scene_missing_params(self, mcp_server):
        """Test with missing required parameters."""
        with pytest.raises(ValueError, match="script_id and scene_id are required"):
            await mcp_server._tool_update_scene({"script_id": "test"})

    @pytest.mark.asyncio
    async def test_update_scene_not_found(self, mcp_server):
        """Test updating non-existent scene."""
        script = Script(title="Test", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        with pytest.raises(ValueError, match="Scene .* not found in script"):
            await mcp_server._tool_update_scene(
                {"script_id": "script_0", "scene_id": 999}
            )

    @pytest.mark.asyncio
    async def test_update_scene_with_dialogue(self, mcp_server):
        """Test updating scene with new dialogue."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Character, Scene

        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

            # Create scene
            scene = Scene(
                id=uuid4(),
                heading="INT. ROOM - DAY",
                description="Original",
                script_order=1,
                script_id=script.id,
            )
            graph_ops.create_scene_node(scene, script_node_id)

            # Create character
            john = Character(id=uuid4(), name="JOHN", description="")
            graph_ops.create_character_node(john, script_node_id)

        result = await mcp_server._tool_update_scene(
            {
                "script_id": script_id,
                "scene_id": scene.id,
                "heading": "EXT. GARDEN - NIGHT",
                "action": "Updated action",
                "dialogue": [
                    {
                        "character": "JOHN",
                        "text": "Hello world!",
                        "parenthetical": "smiling",
                    }
                ],
            }
        )

        assert result["updated"] is True
        assert result["changes"]["heading"] == "EXT. GARDEN - NIGHT"
        assert result["changes"]["action"] == "Updated action"
        assert "dialogue" in result["changes"]


class TestDeleteSceneTool:
    """Comprehensive tests for delete_scene tool."""

    @pytest.mark.asyncio
    async def test_delete_scene_with_reordering(self, mcp_server):
        """Test deleting scene with automatic reordering."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Scene

        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

            # Create multiple scenes
            scenes = []
            for i in range(3):
                scene = Scene(
                    id=uuid4(),
                    heading=f"SCENE {i + 1}",
                    description="",
                    script_order=i + 1,
                    script_id=script.id,
                )
                graph_ops.create_scene_node(scene, script_node_id)
                scenes.append(scene)

        # Delete middle scene
        result = await mcp_server._tool_delete_scene(
            {"script_id": script_id, "scene_id": scenes[1].id}
        )

        assert result["deleted"] is True
        assert result["scenes_reordered"] == 1  # Third scene should be reordered


class TestInjectSceneTool:
    """Comprehensive tests for inject_scene tool."""

    @pytest.mark.asyncio
    async def test_inject_scene_invalid_position(self, mcp_server):
        """Test injecting scene at invalid position."""
        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

        with pytest.raises(ValueError, match="Invalid position"):
            await mcp_server._tool_inject_scene(
                {"script_id": script_id, "position": -1, "heading": "INT. ROOM - DAY"}
            )

    @pytest.mark.asyncio
    async def test_inject_scene_with_parsed_location(self, mcp_server):
        """Test injecting scene with automatic location parsing."""
        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server._scripts_cache[script_id] = script

        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations

        with DatabaseConnection(str(mcp_server.config.get_database_path())) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

        result = await mcp_server._tool_inject_scene(
            {
                "script_id": script_id,
                "position": 0,
                "heading": "INT. COFFEE SHOP - MORNING",
                "action": "The shop is busy",
                "dialogue": [{"character": "BARISTA", "text": "Next customer!"}],
            }
        )

        assert result["injected"] is True
        assert result["position"] == 0
        assert result["heading"] == "INT. COFFEE SHOP - MORNING"
        assert result["characters_added"] == 1
        assert result["dialogue_entries"] == 1


class TestExportDataTool:
    """Comprehensive tests for export_data tool."""

    @pytest.mark.asyncio
    async def test_export_data_missing_params(self, mcp_server):
        """Test with missing required parameters."""
        with pytest.raises(ValueError, match="script_id and format are required"):
            await mcp_server._tool_export_data({"script_id": "test"})

    @pytest.mark.asyncio
    async def test_export_data_formats(self, mcp_server):
        """Test different export formats."""
        for format_type in ["json", "csv", "graphml", "fountain"]:
            result = await mcp_server._tool_export_data(
                {
                    "script_id": "script_0",
                    "format": format_type,
                    "include_metadata": False,
                }
            )

            assert result["exported"] is True
            assert result["format"] == format_type
            assert result["include_metadata"] is False


class TestBibleTools:
    """Tests for Script Bible management tools."""

    @pytest.mark.asyncio
    async def test_create_series_bible(self, mcp_server):
        """Test creating a series bible."""
        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible:
            mock_bible.return_value.create_series_bible.return_value = "bible_123"

            result = await mcp_server._tool_create_series_bible(
                {
                    "script_id": "script_0",
                    "title": "Test Series Bible",
                    "description": "Bible for test series",
                    "bible_type": "series",
                    "created_by": "Test User",
                }
            )

            assert result["bible_id"] == "bible_123"
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_add_character_knowledge_invalid_character(self, mcp_server):
        """Test adding knowledge for non-existent character."""
        from scriptrag.database.connection import DatabaseConnection

        with (
            DatabaseConnection(str(mcp_server.config.get_database_path())),
            pytest.raises(ValueError, match="Character .* not found"),
        ):
            await mcp_server._tool_add_character_knowledge(
                {
                    "script_id": "script_0",
                    "character_name": "NONEXISTENT",
                    "knowledge_type": "fact",
                    "knowledge_subject": "test",
                }
            )

    @pytest.mark.asyncio
    async def test_check_continuity(self, mcp_server):
        """Test continuity checking."""
        with patch(
            "scriptrag.database.continuity.ContinuityValidator"
        ) as mock_validator:
            mock_issues = [
                MagicMock(
                    issue_type="timeline",
                    severity="high",
                    title="Issue 1",
                    description="Desc 1",
                ),
                MagicMock(
                    issue_type="character",
                    severity="medium",
                    title="Issue 2",
                    description="Desc 2",
                ),
            ]
            mock_validator.return_value.validate_script_continuity.return_value = (
                mock_issues
            )
            mock_notes_method = (
                mock_validator.return_value.create_continuity_notes_from_issues
            )
            mock_notes_method.return_value = ["note1", "note2"]

            result = await mcp_server._tool_check_continuity(
                {"script_id": "script_0", "create_notes": True}
            )

            assert result["total_issues"] == 2
            assert result["notes_created"] == 2
            assert result["by_severity"]["high"] == 1
            assert result["by_severity"]["medium"] == 1


class TestMentorTools:
    """Tests for Mentor analysis tools."""

    @pytest.mark.asyncio
    async def test_list_mentors(self, mcp_server):
        """Test listing available mentors."""
        with patch("scriptrag.mentors.get_mentor_registry") as mock_registry:
            mock_registry.return_value.list_mentors.return_value = [
                {"name": "McKee", "description": "Story structure expert"},
                {"name": "Snyder", "description": "Save the Cat methodology"},
            ]

            result = await mcp_server._tool_list_mentors({})

            assert result["total_count"] == 2
            assert len(result["mentors"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_script_with_mentor_invalid_mentor(self, mcp_server):
        """Test analyzing with invalid mentor name."""
        with patch("scriptrag.mentors.get_mentor_registry") as mock_registry:
            mock_registry.return_value.is_registered.return_value = False
            mock_registry.return_value.__iter__.return_value = iter(["McKee", "Snyder"])

            with pytest.raises(ValueError, match="Mentor .* not found"):
                await mcp_server._tool_analyze_script_with_mentor(
                    {"script_id": "script_0", "mentor_name": "InvalidMentor"}
                )

    @pytest.mark.asyncio
    async def test_search_mentor_analyses(self, mcp_server):
        """Test searching mentor analyses."""
        with (
            patch("scriptrag.database.connection.DatabaseConnection"),
            patch("scriptrag.mentors.MentorDatabaseOperations") as mock_db,
        ):
            mock_analysis = MagicMock()
            mock_analysis.id = uuid4()
            mock_analysis.title = "Test Finding"
            mock_analysis.description = "Test description"
            mock_analysis.severity.value = "warning"
            mock_analysis.category = "structure"
            mock_analysis.mentor_name = "McKee"
            mock_analysis.confidence = 0.85
            mock_analysis.recommendations = ["Fix this"]
            mock_analysis.examples = []
            mock_analysis.scene_id = None
            mock_analysis.character_id = None

            mock_db.return_value.search_analyses.return_value = [mock_analysis]

            result = await mcp_server._tool_search_mentor_analyses(
                {
                    "query": "test finding",
                    "mentor_name": "McKee",
                    "severity": "warning",
                    "limit": 10,
                }
            )

            assert result["results_count"] == 1
            assert result["results"][0]["title"] == "Test Finding"
            assert result["results"][0]["severity"] == "warning"


class TestErrorHandling:
    """Tests for error handling across all tools."""

    @pytest.mark.asyncio
    async def test_tool_call_exception_handling(self, mcp_server):
        """Test that exceptions in tools are properly handled."""
        # Make parse_script raise an exception
        mcp_server._tool_parse_script = AsyncMock(side_effect=Exception("Test error"))

        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="parse_script", arguments={"path": "/test.fountain"}
            ),
        )

        result = await mcp_server._handle_tool_call(request)

        assert result.root.isError
        assert "Test error" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_validate_script_id_helper(self, mcp_server):
        """Test the _validate_script_id helper method."""
        # Test valid script ID
        script = Script(title="Test", source_file="test.fountain")
        mcp_server._scripts_cache["valid_id"] = script

        result = mcp_server._validate_script_id("valid_id")
        assert result == script

        # Test invalid script ID
        with pytest.raises(ValueError, match="Script not found"):
            mcp_server._validate_script_id("invalid_id")

    def test_add_to_cache_size_limit(self, mcp_server):
        """Test cache size limiting in _add_to_cache method."""
        mcp_server._max_cache_size = 2

        script1 = Script(title="Script 1", source_file="1.fountain")
        script2 = Script(title="Script 2", source_file="2.fountain")
        script3 = Script(title="Script 3", source_file="3.fountain")

        mcp_server._add_to_cache("id1", script1)
        assert len(mcp_server._scripts_cache) == 1

        mcp_server._add_to_cache("id2", script2)
        assert len(mcp_server._scripts_cache) == 2

        # Adding third should remove first (oldest)
        mcp_server._add_to_cache("id3", script3)
        assert len(mcp_server._scripts_cache) == 2
        assert "id1" not in mcp_server._scripts_cache
        assert "id2" in mcp_server._scripts_cache
        assert "id3" in mcp_server._scripts_cache
