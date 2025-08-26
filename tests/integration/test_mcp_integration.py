"""Integration tests for MCP server."""

import tempfile
from pathlib import Path

import pytest

from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings
from scriptrag.mcp.server import create_server


@pytest.fixture
def temp_db_settings():
    """Create settings with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        query_dir = Path(tmpdir) / "queries"
        query_dir.mkdir()

        # Create a test query file
        test_query = query_dir / "test-query.sql"
        test_query.write_text("""-- description: Test query for MCP
-- param: name: str = 'default' - Filter by name
SELECT 'test' as result WHERE :name = :name;
""")

        settings = ScriptRAGSettings(
            database_path=db_path,
            query_directory=str(query_dir),
            enable_llm=False,
        )

        # Initialize database
        db_api = DatabaseInitializer()
        db_api.initialize_database(settings=settings)

        yield settings


@pytest.fixture
def sample_fountain_script():
    """Create a sample Fountain script."""
    return """Title: Test Script
Author: Test Author

INT. TEST LOCATION - DAY

ALICE
Hello, this is a test.

BOB
(whispers)
Indeed it is.

Alice walks across the room.

CUT TO:

EXT. ANOTHER LOCATION - NIGHT

CHARLIE
The adventure begins here!
"""


@pytest.mark.asyncio
@pytest.mark.requires_llm
async def test_mcp_server_search_integration(temp_db_settings, sample_fountain_script):
    """Test MCP server search functionality with real data."""
    from unittest.mock import patch

    from scriptrag.api.analyze import AnalyzeCommand

    # Index the sample script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
        f.write(sample_fountain_script)
        script_path = f.name

    try:
        # First analyze the script to add boneyard metadata
        analyze_api = AnalyzeCommand()
        await analyze_api.analyze(Path(script_path))

        # Now index the analyzed script
        index_api = IndexCommand(temp_db_settings)
        await index_api.index(Path(script_path))

        # Create MCP server with the test settings
        with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
            server = create_server()

            # Find the search tool
            tools = await server.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            assert search_tool_name is not None

            # Test basic search
            response = await server.call_tool(search_tool_name, {"query": "adventure"})
            # Extract result - call_tool returns tuple (text_content_list, raw_result)
            result_data = response[1]  # Use the raw dictionary result
            assert result_data["success"] is True
            assert result_data["total_count"] > 0
            assert "adventure" in result_data["results"][0]["scene_content"].lower()

            # Test character search
            response = await server.call_tool(search_tool_name, {"query": "ALICE"})
            result_data = response[1]
            assert result_data["success"] is True
            assert result_data["total_count"] > 0
            # Check that ALICE appears in either character_name or scene_content
            assert any(
                "ALICE" in r.get("character_name", "")
                or "ALICE" in r.get("scene_content", "")
                for r in result_data["results"]
            )

            # Test dialogue search - query is always required
            response = await server.call_tool(
                search_tool_name, {"query": "", "dialogue": "Hello"}
            )
            result_data = response[1]
            assert result_data["success"] is True
            assert result_data["total_count"] > 0

            # Test parenthetical search - query is always required
            response = await server.call_tool(
                search_tool_name, {"query": "", "parenthetical": "whispers"}
            )
            result_data = response[1]
            assert result_data["success"] is True
            assert result_data["total_count"] > 0

    finally:
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.requires_llm
async def test_mcp_server_query_integration(temp_db_settings):
    """Test MCP server query functionality."""
    from unittest.mock import patch

    # Add some test data to the database
    from scriptrag.api.database_operations import DatabaseOperations

    db_api = DatabaseOperations(temp_db_settings)
    with db_api.transaction() as conn:
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test_table (name) VALUES ('test1'), ('test2')")

    # Create MCP server with the test settings
    with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
        with patch(
            "scriptrag.mcp.tools.query.get_settings", return_value=temp_db_settings
        ):
            server = create_server()

            # Find the query list tool
            tools = await server.list_tools()
            list_tool_name = None
            test_tool_name = None
            for tool in tools:
                if "scriptrag_query_list" in tool.name:
                    list_tool_name = tool.name
                elif "scriptrag_query_test_list_scripts" in tool.name:
                    test_tool_name = tool.name

            assert list_tool_name is not None

            # List available queries
            response = await server.call_tool(list_tool_name, {})
            result_data = response[1]
            assert result_data["success"] is True
            assert len(result_data["queries"]) > 0
            # Check for an actual query that exists
            assert any(q["name"] == "test_list_scripts" for q in result_data["queries"])

            # If the test query tool exists, test it
            if test_tool_name:
                response = await server.call_tool(
                    test_tool_name, {"kwargs": {"name": "test"}}
                )
                result_data = response[1]
                assert result_data["success"] is True
                assert "results" in result_data


@pytest.mark.asyncio
@pytest.mark.requires_llm
async def test_mcp_server_full_workflow(temp_db_settings, sample_fountain_script):
    """Test complete MCP server workflow."""
    from unittest.mock import patch

    # Index the sample script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
        f.write(sample_fountain_script)
        script_path = f.name

    try:
        # Index the script
        index_api = IndexCommand(temp_db_settings)
        await index_api.index(Path(script_path))

        # Create MCP server
        with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
            server = create_server()

            # Get search tool
            tools = await server.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Perform various searches

            # 1. Search for dialogue with character filter
            response = await server.call_tool(
                search_tool_name,
                {
                    "query": "test",
                    "character": "ALICE",
                    "limit": 10,
                },
            )
            result_data = response[1]
            assert result_data["success"] is True

            # 2. Search with pagination
            response1 = await server.call_tool(
                search_tool_name,
                {
                    "query": "the",
                    "limit": 1,
                    "offset": 0,
                },
            )
            response2 = await server.call_tool(
                search_tool_name,
                {
                    "query": "the",
                    "limit": 1,
                    "offset": 1,
                },
            )
            result1_data = response1[1]
            result2_data = response2[1]
            assert result1_data["success"] is True
            assert result2_data["success"] is True
            # Results should be different due to offset
            if result1_data["results"] and result2_data["results"]:
                r1_id = result1_data["results"][0]["scene_id"]
                r2_id = result2_data["results"][0]["scene_id"]
                assert r1_id != r2_id

            # 3. Test auto-detection of search components
            response = await server.call_tool(
                search_tool_name,
                {
                    "query": 'ALICE "Hello" (whispers)',
                },
            )
            result_data = response[1]
            assert result_data["success"] is True

            # 4. Test fuzzy search
            response = await server.call_tool(
                search_tool_name,
                {
                    "query": "greetings salutations",
                    "fuzzy": True,
                },
            )
            result_data = response[1]
            assert result_data["success"] is True

            # 5. Test strict search
            response = await server.call_tool(
                search_tool_name,
                {
                    "query": "exact phrase that doesn't exist",
                    "strict": True,
                },
            )
            result_data = response[1]
            assert result_data["success"] is True
            assert result_data["total_count"] == 0

    finally:
        Path(script_path).unlink(missing_ok=True)


def test_mcp_server_main_entry_point():
    """Test the main entry point."""
    from unittest.mock import MagicMock, patch

    mock_server = MagicMock(spec=object)
    mock_server.run = MagicMock(spec=object)

    with patch("scriptrag.mcp.server.create_server", return_value=mock_server):
        from scriptrag.mcp.server import main

        main()

        # Verify server.run() was called
        mock_server.run.assert_called_once()
