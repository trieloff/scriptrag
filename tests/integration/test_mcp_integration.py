"""Integration tests for MCP server."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

from scriptrag.api.database import DatabaseAPI
from scriptrag.api.index import IndexAPI
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
            database_url=f"sqlite:///{db_path}",
            query_directory=str(query_dir),
            enable_llm=False,
        )

        # Initialize database
        db_api = DatabaseAPI(settings)
        db_api.init_database()

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
async def test_mcp_server_search_integration(temp_db_settings, sample_fountain_script):
    """Test MCP server search functionality with real data."""
    from unittest.mock import patch

    # Index the sample script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
        f.write(sample_fountain_script)
        script_path = f.name

    try:
        # Index the script
        index_api = IndexAPI(temp_db_settings)
        index_api.index_file(script_path)

        # Create MCP server with the test settings
        with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
            server = create_server()

            # Find the search tool
            search_tool = None
            for name, func in server._tools.items():
                if "scriptrag_search" in name:
                    search_tool = func
                    break

            assert search_tool is not None

            # Test basic search
            result = await search_tool(query="adventure")
            assert result["success"] is True
            assert result["total_results"] > 0
            assert "adventure" in result["results"][0]["content"].lower()

            # Test character search
            result = await search_tool(query="ALICE")
            assert result["success"] is True
            assert any("ALICE" in r.get("characters", []) for r in result["results"])

            # Test dialogue search
            result = await search_tool(dialogue="Hello")
            assert result["success"] is True
            assert result["total_results"] > 0

            # Test parenthetical search
            result = await search_tool(parenthetical="whispers")
            assert result["success"] is True
            assert result["total_results"] > 0

    finally:
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_mcp_server_query_integration(temp_db_settings):
    """Test MCP server query functionality."""
    from unittest.mock import patch

    # Add some test data to the database
    db_api = DatabaseAPI(temp_db_settings)
    with db_api.get_session() as session:
        session.execute(
            text("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        )
        session.execute(
            text("INSERT INTO test_table (name) VALUES ('test1'), ('test2')")
        )
        session.commit()

    # Create MCP server with the test settings
    with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
        with patch(
            "scriptrag.mcp.tools.query.get_settings", return_value=temp_db_settings
        ):
            server = create_server()

            # Find the query list tool
            list_tool = None
            for name, func in server._tools.items():
                if "scriptrag_query_list" in name:
                    list_tool = func
                    break

            assert list_tool is not None

            # List available queries
            result = await list_tool()
            assert result["success"] is True
            assert len(result["queries"]) > 0
            assert any(q["name"] == "test-query" for q in result["queries"])

            # Find the test query tool
            test_tool = None
            for name, func in server._tools.items():
                if "scriptrag_query_test_query" in name:
                    test_tool = func
                    break

            # If the tool exists, test it
            if test_tool:
                result = await test_tool(name="test")
                assert result["success"] is True
                assert "results" in result


@pytest.mark.asyncio
async def test_mcp_server_full_workflow(temp_db_settings, sample_fountain_script):
    """Test complete MCP server workflow."""
    from unittest.mock import patch

    # Index the sample script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
        f.write(sample_fountain_script)
        script_path = f.name

    try:
        # Index the script
        index_api = IndexAPI(temp_db_settings)
        index_api.index_file(script_path)

        # Create MCP server
        with patch("scriptrag.config.get_settings", return_value=temp_db_settings):
            server = create_server()

            # Get search tool
            search_tool = None
            for name, func in server._tools.items():
                if "scriptrag_search" in name:
                    search_tool = func
                    break

            # Perform various searches

            # 1. Search for dialogue with character filter
            result = await search_tool(
                query="test",
                character="ALICE",
                limit=10,
            )
            assert result["success"] is True

            # 2. Search with pagination
            result1 = await search_tool(
                query="the",
                limit=1,
                offset=0,
            )
            result2 = await search_tool(
                query="the",
                limit=1,
                offset=1,
            )
            assert result1["success"] is True
            assert result2["success"] is True
            # Results should be different due to offset
            if result1["results"] and result2["results"]:
                r1_id = result1["results"][0]["scene_id"]
                r2_id = result2["results"][0]["scene_id"]
                assert r1_id != r2_id

            # 3. Test auto-detection of search components
            result = await search_tool(
                query='ALICE "Hello" (whispers)',
            )
            assert result["success"] is True

            # 4. Test fuzzy search
            result = await search_tool(
                query="greetings salutations",
                fuzzy=True,
            )
            assert result["success"] is True

            # 5. Test strict search
            result = await search_tool(
                query="exact phrase that doesn't exist",
                strict=True,
            )
            assert result["success"] is True
            assert result["total_results"] == 0

    finally:
        Path(script_path).unlink(missing_ok=True)


def test_mcp_server_main_entry_point():
    """Test the main entry point."""
    from unittest.mock import MagicMock, patch

    mock_server = MagicMock()
    mock_run = MagicMock()
    mock_server.run.return_value = mock_run

    with patch("scriptrag.mcp.server.create_server", return_value=mock_server):
        with patch("asyncio.run") as mock_asyncio_run:
            from scriptrag.mcp.server import main

            main()

            # Verify server was created and run
            mock_asyncio_run.assert_called_once_with(mock_run)
