"""Tests for Script Bible MCP server tools."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.continuity import ContinuityIssue
from scriptrag.mcp_server import ScriptRAGMCPServer


@pytest.fixture
def mcp_settings():
    """Create MCP settings for testing."""
    settings = ScriptRAGSettings()
    settings.mcp.enable_all_tools = True
    return settings


@pytest.fixture
def mock_scriptrag():
    """Create a mock ScriptRAG instance."""
    mock = MagicMock()
    mock.connection = MagicMock()
    return mock


@pytest.fixture
def mcp_server(mcp_settings, mock_scriptrag):
    """Create MCP server instance for testing."""
    with patch("scriptrag.mcp_server.ScriptRAG", return_value=mock_scriptrag):
        server = ScriptRAGMCPServer(mcp_settings)
        server.scriptrag = mock_scriptrag
        return server


class TestScriptBibleMCPTools:
    """Test Script Bible MCP tools."""

    def test_bible_tools_in_available_tools(self, mcp_server):
        """Test that Script Bible tools are included in available tools."""
        tools = mcp_server.get_available_tools()
        tool_names = {tool["name"] for tool in tools}

        expected_bible_tools = {
            "create_series_bible",
            "create_character_profile",
            "add_world_element",
            "create_timeline_event",
            "check_continuity",
            "add_character_knowledge",
            "get_continuity_report",
        }

        assert expected_bible_tools.issubset(tool_names)

    @pytest.mark.asyncio
    async def test_create_series_bible_tool(self, mcp_server):
        """Test create_series_bible MCP tool."""
        script_id = str(uuid4())

        # Mock the bible operations
        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible_ops:
            mock_ops = mock_bible_ops.return_value
            mock_ops.create_series_bible.return_value = "bible123"

            args = {
                "script_id": script_id,
                "title": "Test Bible",
                "description": "Test description",
                "bible_type": "series",
                "created_by": "Test Creator",
            }

            result = await mcp_server._tool_create_series_bible(args)

            assert result["bible_id"] == "bible123"
            assert result["script_id"] == script_id
            assert result["title"] == "Test Bible"
            assert result["created"] is True

            mock_ops.create_series_bible.assert_called_once_with(
                script_id=script_id,
                title="Test Bible",
                description="Test description",
                created_by="Test Creator",
                bible_type="series",
            )

    @pytest.mark.asyncio
    async def test_create_series_bible_missing_required(self, mcp_server):
        """Test create_series_bible with missing required parameters."""
        args = {"title": "Test Bible"}  # Missing script_id

        with pytest.raises(KeyError, match="script_id"):
            await mcp_server._tool_create_series_bible(args)

    @pytest.mark.asyncio
    async def test_create_character_profile_tool(self, mcp_server):
        """Test create_character_profile MCP tool."""
        script_id = str(uuid4())
        character_id = str(uuid4())

        # Mock database queries
        mcp_server.scriptrag.connection.fetch_one.return_value = {"id": character_id}

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible_ops:
            mock_ops = mock_bible_ops.return_value
            mock_ops.create_character_profile.return_value = "profile123"

            args = {
                "script_id": script_id,
                "character_id": character_id,
                "age": 35,
                "occupation": "Detective",
                "background": "Former military",
            }

            result = await mcp_server._tool_create_character_profile(args)

            assert result["profile_id"] == "profile123"
            assert result["character_id"] == character_id
            assert result["script_id"] == script_id
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_create_character_profile_missing_character_id(self, mcp_server):
        """Test create_character_profile with missing character_id."""
        args = {"script_id": str(uuid4()), "age": 35}

        with pytest.raises(KeyError, match="character_id"):
            await mcp_server._tool_create_character_profile(args)

    @pytest.mark.asyncio
    async def test_add_world_element_tool(self, mcp_server):
        """Test add_world_element MCP tool."""
        script_id = str(uuid4())

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible_ops:
            mock_ops = mock_bible_ops.return_value
            mock_ops.create_world_element.return_value = "element123"

            args = {
                "script_id": script_id,
                "name": "Police Station",
                "element_type": "location",
                "description": "Main headquarters",
                "importance_level": 4,
            }

            result = await mcp_server._tool_add_world_element(args)

            assert result["element_id"] == "element123"
            assert result["name"] == "Police Station"
            assert result["element_type"] == "location"
            assert result["script_id"] == script_id
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_check_continuity_tool(self, mcp_server):
        """Test check_continuity MCP tool."""
        script_id = str(uuid4())

        # Mock continuity issues
        mock_issues = [
            ContinuityIssue(
                issue_type="test_error",
                severity="high",
                title="Test Issue 1",
                description="First issue",
                character_id="char1",
            ),
            ContinuityIssue(
                issue_type="test_warning",
                severity="medium",
                title="Test Issue 2",
                description="Second issue",
                episode_id="ep1",
            ),
        ]

        with patch(
            "scriptrag.database.continuity.ContinuityValidator"
        ) as mock_validator:
            mock_val = mock_validator.return_value
            mock_val.validate_script_continuity.return_value = mock_issues
            mock_val.create_continuity_notes_from_issues.return_value = [
                "note1",
                "note2",
            ]

            args = {
                "script_id": script_id,
                "create_notes": True,
            }

            result = await mcp_server._tool_check_continuity(args)

            assert result["script_id"] == script_id
            assert result["total_issues"] == 2  # Both issues returned
            assert result["by_severity"]["high"] == 1
            assert result["by_severity"]["medium"] == 1
            assert result["notes_created"] == 2
            assert len(result["issues"]) == 2
            assert result["issues"][0]["title"] == "Test Issue 1"
            assert result["issues"][1]["title"] == "Test Issue 2"

    @pytest.mark.asyncio
    async def test_get_continuity_report_tool(self, mcp_server):
        """Test get_continuity_report MCP tool."""
        script_id = str(uuid4())

        mock_report = {
            "script_id": script_id,
            "script_title": "Test Script",
            "is_series": True,
            "generated_at": "2024-01-01T00:00:00",
            "validation_results": {
                "issue_statistics": {
                    "total_issues": 5,
                    "by_severity": {"high": 2, "medium": 2, "low": 1},
                }
            },
            "existing_notes": {
                "note_statistics": {
                    "total_notes": 3,
                    "by_status": {"open": 2, "resolved": 1},
                }
            },
            "recommendations": ["Fix high severity issues", "Review character arcs"],
        }

        with patch(
            "scriptrag.database.continuity.ContinuityValidator"
        ) as mock_validator:
            mock_val = mock_validator.return_value
            mock_val.generate_continuity_report.return_value = mock_report

            args = {"script_id": script_id}

            result = await mcp_server._tool_get_continuity_report(args)

            assert result["script_id"] == script_id
            assert result["script_title"] == "Test Script"
            assert result["is_series"] is True
            assert result["total_issues"] == 5
            assert result["by_severity"]["high"] == 2
            assert result["open_notes"] == 2
            assert len(result["recommendations"]) == 2

    @pytest.mark.asyncio
    async def test_add_character_knowledge_tool(self, mcp_server):
        """Test add_character_knowledge MCP tool."""
        script_id = str(uuid4())
        character_id = str(uuid4())
        episode_id = str(uuid4())

        # Mock database connection and queries
        mock_connection = MagicMock()
        mock_connection.fetch_one.side_effect = [
            {"id": character_id},  # Character lookup
            {"id": episode_id},  # Episode lookup
        ]

        with patch("scriptrag.database.connection.DatabaseConnection") as mock_db_conn:
            mock_db_conn.return_value.__enter__.return_value = mock_connection

            with patch(
                "scriptrag.database.bible.ScriptBibleOperations"
            ) as mock_bible_ops:
                mock_ops = mock_bible_ops.return_value
                mock_ops.add_character_knowledge.return_value = "knowledge123"

                args = {
                    "script_id": script_id,
                    "character_name": "JOHN",
                    "knowledge_type": "secret",
                    "knowledge_subject": "The villain's plan",
                    "knowledge_description": "John discovered the plan",
                    "acquired_episode": "Episode 2",
                    "acquisition_method": "discovered",
                }

                result = await mcp_server._tool_add_character_knowledge(args)

                assert result["knowledge_id"] == "knowledge123"
                assert result["character_id"] == character_id
                assert result["character_name"] == "JOHN"
                assert result["knowledge_type"] == "secret"
                assert result["knowledge_subject"] == "The villain's plan"
                assert result["created"] is True

    @pytest.mark.asyncio
    async def test_create_timeline_event_tool(self, mcp_server):
        """Test create_timeline_event MCP tool."""
        script_id = str(uuid4())

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible_ops:
            mock_ops = mock_bible_ops.return_value
            mock_ops.add_timeline_event.return_value = "event123"

            args = {
                "timeline_id": str(uuid4()),
                "script_id": script_id,
                "event_name": "Murder Investigation",
                "event_type": "story",
                "description": "Main investigation plot",
                "story_date": "Day 1",
                "episode_id": str(uuid4()),
            }

            result = await mcp_server._tool_create_timeline_event(args)

            assert result["event_id"] == "event123"
            assert result["timeline_id"] == args["timeline_id"]
            assert result["event_name"] == "Murder Investigation"
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, mcp_server):
        """Test error handling in MCP tools."""
        # Test with missing required parameters
        with pytest.raises(KeyError):
            await mcp_server._tool_create_series_bible({"title": "Test"})

        with pytest.raises(KeyError):
            await mcp_server._tool_add_world_element({"script_id": "test"})

        with pytest.raises(KeyError):
            await mcp_server._tool_check_continuity({})


class TestScriptBibleMCPIntegration:
    """Integration tests for Script Bible MCP functionality."""

    def test_bible_tool_schemas_valid(self, mcp_server):
        """Test that all Script Bible tool schemas are valid."""
        tools = mcp_server.get_available_tools()
        bible_tools = [
            t
            for t in tools
            if "bible" in t["name"]
            or "continuity" in t["name"]
            or "character" in t["name"]
            or "world" in t["name"]
            or "timeline" in t["name"]
        ]

        for tool in bible_tools:
            # Verify required schema fields
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

            schema = tool["inputSchema"]
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema

            # Check that all required fields are in properties
            if "required" in schema:
                for required_field in schema["required"]:
                    assert required_field in schema["properties"]

    def test_bible_tool_descriptions(self, mcp_server):
        """Test that Script Bible tools have appropriate descriptions."""
        tools = mcp_server.get_available_tools()
        tool_dict = {t["name"]: t for t in tools}

        # Check specific tool descriptions
        assert "bible" in tool_dict["create_series_bible"]["description"].lower()
        assert "continuity" in tool_dict["create_series_bible"]["description"].lower()

        assert (
            "character" in tool_dict["create_character_profile"]["description"].lower()
        )
        assert "profile" in tool_dict["create_character_profile"]["description"].lower()

        assert "continuity" in tool_dict["check_continuity"]["description"].lower()
        assert "validation" in tool_dict["check_continuity"]["description"].lower()

        assert "world" in tool_dict["add_world_element"]["description"].lower()
        assert "element" in tool_dict["add_world_element"]["description"].lower()

    def test_bible_tool_parameter_validation(self, mcp_server):
        """Test parameter validation for Script Bible tools."""
        tools = mcp_server.get_available_tools()
        tool_dict = {t["name"]: t for t in tools}

        # Test create_series_bible parameters
        bible_tool = tool_dict["create_series_bible"]
        required_params = bible_tool["inputSchema"]["required"]
        assert "script_id" in required_params
        assert "title" in required_params

        properties = bible_tool["inputSchema"]["properties"]
        assert "bible_type" in properties
        assert "enum" in properties["bible_type"]
        assert "series" in properties["bible_type"]["enum"]

        # Test add_world_element parameters
        world_tool = tool_dict["add_world_element"]
        world_properties = world_tool["inputSchema"]["properties"]
        assert "element_type" in world_properties
        assert "enum" in world_properties["element_type"]
        assert "location" in world_properties["element_type"]["enum"]

        # Test importance level validation
        assert "importance_level" in world_properties
        assert world_properties["importance_level"]["minimum"] == 1
        assert world_properties["importance_level"]["maximum"] == 5

        # Test continuity check parameters
        continuity_tool = tool_dict["check_continuity"]
        continuity_properties = continuity_tool["inputSchema"]["properties"]
        assert "script_id" in continuity_properties
        assert "create_notes" in continuity_properties
        assert continuity_properties["create_notes"]["type"] == "boolean"
        assert continuity_properties["create_notes"]["default"] is False
