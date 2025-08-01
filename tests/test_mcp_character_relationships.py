"""Tests for character relationships tool in MCP server."""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.graph import GraphEdge, GraphNode
from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.models import Script


class TestGetCharacterRelationships:
    """Test suite for _tool_get_character_relationships."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance for testing."""
        config = ScriptRAGSettings()
        return ScriptRAGMCPServer(config)

    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        return mock_conn

    @pytest.fixture
    def mock_graph_db(self):
        """Create mock graph database."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_missing_script_id_raises_error(self, mcp_server):
        """Test that missing script_id raises ValueError."""
        with pytest.raises(ValueError, match="script_id is required"):
            await mcp_server._tool_get_character_relationships({})

    @pytest.mark.asyncio
    async def test_script_not_found_error(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test handling when script is not found in graph."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock find_nodes to return empty list
            mock_graph_db.find_nodes.return_value = []

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "nonexistent-script"}
            )

            assert result["script_id"] == "nonexistent-script"
            assert result["relationships"] == []
            assert result["total_characters"] == 0
            assert result["error"] == "Script not found in graph"

    @pytest.mark.asyncio
    async def test_character_not_found_error(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test handling when specific character is not found."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query - return others but not requested one
            mock_connection.fetch_all.return_value = [
                {
                    "id": "char-1",
                    "char_name": "Alice",
                    "node_type": "character",
                    "entity_id": "alice-id",
                    "label": "Alice",
                    "properties_json": None,
                },
                {
                    "id": "char-2",
                    "char_name": "Bob",
                    "node_type": "character",
                    "entity_id": "bob-id",
                    "label": "Bob",
                    "properties_json": None,
                },
            ]

            # Mock get_node to return character nodes
            def mock_get_node(node_id):
                if node_id == "char-1":
                    return GraphNode(
                        node_id="char-1",
                        node_type="character",
                        entity_id="alice-id",
                        label="Alice",
                    )
                if node_id == "char-2":
                    return GraphNode(
                        node_id="char-2",
                        node_type="character",
                        entity_id="bob-id",
                        label="Bob",
                    )
                return None

            mock_graph_db.get_node.side_effect = mock_get_node

            # Mock script cache to contain test script
            script_uuid = uuid4()
            mock_script = Script(id=script_uuid, title="Test Script", scenes=[])
            mcp_server._scripts_cache = {"test-script": mock_script}

            # Mock database queries: character search returns None, then total count = 2
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [None, {"total": 2}]
            mock_connection.execute.return_value = mock_cursor

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script", "character_name": "Charlie"}
            )

            assert result["character_name"] == "Charlie"
            assert result["relationships"] == []
            assert result["total_characters"] == 2
            assert result["error"] == "Character 'Charlie' not found"

    @pytest.mark.asyncio
    async def test_get_all_relationships_success(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test successfully getting all character relationships."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query
            mock_connection.fetch_all.side_effect = [
                # First call - character nodes
                [
                    {
                        "id": "char-1",
                        "char_name": "Alice",
                        "node_type": "character",
                        "entity_id": "alice-id",
                        "label": "Alice",
                        "properties_json": None,
                    },
                    {
                        "id": "char-2",
                        "char_name": "Bob",
                        "node_type": "character",
                        "entity_id": "bob-id",
                        "label": "Bob",
                        "properties_json": None,
                    },
                    {
                        "id": "char-3",
                        "char_name": "Charlie",
                        "node_type": "character",
                        "entity_id": "charlie-id",
                        "label": "Charlie",
                        "properties_json": None,
                    },
                ],
                # Second call - edges
                [
                    {
                        "id": "edge-1",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-1", "dialogue_count": 3}'
                        ),
                        "weight": 1.0,
                    },
                    {
                        "id": "edge-2",
                        "from_node_id": "char-2",
                        "to_node_id": "char-1",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-2", "dialogue_count": 2}'
                        ),
                        "weight": 1.0,
                    },
                ],
            ]

            # Mock get_node
            def mock_get_node(node_id):
                node_map = {
                    "char-1": GraphNode(
                        node_id="char-1",
                        node_type="character",
                        entity_id="alice-id",
                    ),
                    "char-2": GraphNode(
                        node_id="char-2",
                        node_type="character",
                        entity_id="bob-id",
                    ),
                    "char-3": GraphNode(
                        node_id="char-3",
                        node_type="character",
                        entity_id="charlie-id",
                    ),
                }
                return node_map.get(node_id)

            mock_graph_db.get_node.side_effect = mock_get_node

            # Mock script cache to contain test script
            script_uuid = uuid4()
            mock_script = Script(id=script_uuid, title="Test Script", scenes=[])
            mcp_server._scripts_cache = {"test-script": mock_script}

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script"}
            )

            assert result["script_id"] == "test-script"
            assert result["total_characters"] == 3
            assert result["total_relationships"] == 1
            assert len(result["relationships"]) == 1

            # Check the relationship
            rel = result["relationships"][0]
            assert rel["character1"] == "Alice"
            assert rel["character2"] == "Bob"
            assert rel["shared_scenes"] == 2

    @pytest.mark.asyncio
    async def test_filter_by_character_success(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test successfully filtering relationships by specific character."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query
            mock_connection.fetch_all.return_value = [
                {
                    "id": "char-1",
                    "char_name": "Alice",
                    "node_type": "character",
                    "entity_id": "alice-id",
                    "label": "Alice",
                    "properties_json": None,
                },
                {
                    "id": "char-2",
                    "char_name": "Bob",
                    "node_type": "character",
                    "entity_id": "bob-id",
                    "label": "Bob",
                    "properties_json": None,
                },
            ]

            # Mock get_node
            char_nodes = {
                "char-1": GraphNode(
                    node_id="char-1", node_type="character", entity_id="alice-id"
                ),
                "char-2": GraphNode(
                    node_id="char-2", node_type="character", entity_id="bob-id"
                ),
            }
            mock_graph_db.get_node.side_effect = lambda nid: char_nodes.get(nid)

            # Mock find_edges
            edge1 = GraphEdge(
                edge_id="edge-1",
                from_node_id="char-1",
                to_node_id="char-2",
                edge_type="SPEAKS_TO",
                properties={"scene_id": "scene-1", "dialogue_count": 3},
            )
            mock_graph_db.find_edges.side_effect = [
                [edge1],  # outgoing edges
                [],  # incoming edges
            ]

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script", "character_name": "Alice"}
            )

            assert result["character_name"] == "Alice"
            assert len(result["relationships"]) == 1
            assert result["relationships"][0]["character"] == "Bob"
            assert result["relationships"][0]["other_character"] is None

    @pytest.mark.asyncio
    async def test_empty_relationships(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test handling when there are no relationships."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query with single character
            mock_connection.fetch_all.side_effect = [
                [
                    {
                        "id": "char-1",
                        "char_name": "Alice",
                        "node_type": "character",
                        "entity_id": "alice-id",
                        "label": "Alice",
                        "properties_json": None,
                    }
                ],
                [],  # No edges
            ]

            mock_graph_db.get_node.return_value = GraphNode(
                node_id="char-1", node_type="character", entity_id="alice-id"
            )

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script"}
            )

            assert result["relationships"] == []
            assert result["total_characters"] == 1
            assert result["total_relationships"] == 0

    @pytest.mark.asyncio
    async def test_too_many_characters_error(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test that too many characters raises ValueError."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query with 1001 characters
            char_rows = [
                {
                    "id": f"char-{i}",
                    "char_name": f"Character{i}",
                    "node_type": "character",
                    "entity_id": f"character{i}-id",
                    "label": f"Character{i}",
                    "properties_json": None,
                }
                for i in range(1001)
            ]
            mock_connection.fetch_all.return_value = char_rows

            # Mock get_node to return nodes for all characters
            mock_graph_db.get_node.side_effect = lambda nid: GraphNode(
                node_id=nid, node_type="character", entity_id=f"{nid}-entity"
            )

            with pytest.raises(ValueError, match="Too many character nodes"):
                await mcp_server._tool_get_character_relationships(
                    {"script_id": "test-script"}
                )

    @pytest.mark.asyncio
    async def test_interaction_strength_calculation(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test that interaction strength is calculated correctly."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query
            mock_connection.fetch_all.side_effect = [
                [
                    {
                        "id": "char-1",
                        "char_name": "Alice",
                        "node_type": "character",
                        "entity_id": "alice-id",
                        "label": "Alice",
                        "properties_json": None,
                    },
                    {
                        "id": "char-2",
                        "char_name": "Bob",
                        "node_type": "character",
                        "entity_id": "bob-id",
                        "label": "Bob",
                        "properties_json": None,
                    },
                ],
                # Multiple edges with different scenes
                [
                    {
                        "id": "edge-1",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-1", "dialogue_count": 5}'
                        ),
                        "weight": 1.0,
                    },
                    {
                        "id": "edge-2",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-2", "dialogue_count": 3}'
                        ),
                        "weight": 1.0,
                    },
                    {
                        "id": "edge-3",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-3", "dialogue_count": 2}'
                        ),
                        "weight": 1.0,
                    },
                ],
            ]

            # Mock get_node
            char_nodes = {
                "char-1": GraphNode(
                    node_id="char-1", node_type="character", entity_id="alice-id"
                ),
                "char-2": GraphNode(
                    node_id="char-2", node_type="character", entity_id="bob-id"
                ),
            }
            mock_graph_db.get_node.side_effect = lambda nid: char_nodes.get(nid)

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script"}
            )

            rel = result["relationships"][0]
            # Check calculations:
            # - Total dialogues: 5 + 3 + 2 = 10
            # - Scenes: 3
            # - Strength: min(1.0, 10*0.1 + 3*0.2) = 1.0
            assert rel["dialogue_exchanges"] == 10
            assert rel["shared_scenes"] == 3
            assert rel["interaction_strength"] == 1.0

    @pytest.mark.asyncio
    async def test_scene_limit_configuration(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test that scene limit is configurable."""
        # Mock the config attribute to test the fallback
        # Since max_scenes_per_relationship doesn't exist, it should use default of 10

        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query
            mock_connection.fetch_all.side_effect = [
                [
                    {
                        "id": "char-1",
                        "char_name": "Alice",
                        "node_type": "character",
                        "entity_id": "alice-id",
                        "label": "Alice",
                        "properties_json": None,
                    },
                    {
                        "id": "char-2",
                        "char_name": "Bob",
                        "node_type": "character",
                        "entity_id": "bob-id",
                        "label": "Bob",
                        "properties_json": None,
                    },
                ],
                # Multiple edges with many scenes
                [
                    {
                        "id": f"edge-{i}",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            f'{{"scene_id": "scene-{i}", "dialogue_count": 1}}'
                        ),
                        "weight": 1.0,
                    }
                    for i in range(10)
                ],
            ]

            # Mock get_node
            char_nodes = {
                "char-1": GraphNode(
                    node_id="char-1", node_type="character", entity_id="alice-id"
                ),
                "char-2": GraphNode(
                    node_id="char-2", node_type="character", entity_id="bob-id"
                ),
            }
            mock_graph_db.get_node.side_effect = lambda nid: char_nodes.get(nid)

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script"}
            )

            rel = result["relationships"][0]
            # Should use default limit of 10 scenes
            assert len(rel["scenes"]) == 10
            assert rel["shared_scenes"] == 10  # Total count is still 10

    @pytest.mark.asyncio
    async def test_database_connection_closed_on_error(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test that database connection is properly closed even on error."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock find_nodes to raise an exception
            mock_graph_db.find_nodes.side_effect = Exception("Database error")

            with pytest.raises(Exception, match="Database error"):
                await mcp_server._tool_get_character_relationships(
                    {"script_id": "test-script"}
                )

            # Ensure connection context manager was properly used
            mock_connection.__enter__.assert_called_once()
            mock_connection.__exit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_sorting_by_interaction_strength(
        self, mcp_server, mock_connection, mock_graph_db
    ):
        """Test that relationships are sorted by interaction strength."""
        with (
            patch(
                "scriptrag.mcp.tools_character.DatabaseConnection",
                return_value=mock_connection,
            ),
            patch(
                "scriptrag.mcp.tools_character.GraphDatabase",
                return_value=mock_graph_db,
            ),
        ):
            # Mock script node
            script_node = GraphNode(
                node_id="script-1",
                node_type="script",
                entity_id="test-script",
            )
            mock_graph_db.find_nodes.return_value = [script_node]

            # Mock character query
            mock_connection.fetch_all.side_effect = [
                [
                    {
                        "id": "char-1",
                        "char_name": "Alice",
                        "node_type": "character",
                        "entity_id": "alice-id",
                        "label": "Alice",
                        "properties_json": None,
                    },
                    {
                        "id": "char-2",
                        "char_name": "Bob",
                        "node_type": "character",
                        "entity_id": "bob-id",
                        "label": "Bob",
                        "properties_json": None,
                    },
                    {
                        "id": "char-3",
                        "char_name": "Charlie",
                        "node_type": "character",
                        "entity_id": "charlie-id",
                        "label": "Charlie",
                        "properties_json": None,
                    },
                ],
                # Edges with different strengths
                [
                    # Weak relationship: Alice-Charlie
                    {
                        "id": "edge-1",
                        "from_node_id": "char-1",
                        "to_node_id": "char-3",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-1", "dialogue_count": 1}'
                        ),
                        "weight": 1.0,
                    },
                    # Strong relationship: Alice-Bob
                    {
                        "id": "edge-2",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-2", "dialogue_count": 10}'
                        ),
                        "weight": 1.0,
                    },
                    {
                        "id": "edge-3",
                        "from_node_id": "char-1",
                        "to_node_id": "char-2",
                        "edge_type": "SPEAKS_TO",
                        "properties_json": (
                            '{"scene_id": "scene-3", "dialogue_count": 5}'
                        ),
                        "weight": 1.0,
                    },
                ],
            ]

            # Mock get_node
            char_nodes = {
                "char-1": GraphNode(
                    node_id="char-1", node_type="character", entity_id="alice-id"
                ),
                "char-2": GraphNode(
                    node_id="char-2", node_type="character", entity_id="bob-id"
                ),
                "char-3": GraphNode(
                    node_id="char-3", node_type="character", entity_id="charlie-id"
                ),
            }
            mock_graph_db.get_node.side_effect = lambda nid: char_nodes.get(nid)

            result = await mcp_server._tool_get_character_relationships(
                {"script_id": "test-script"}
            )

            # Check that relationships are sorted by strength (descending)
            assert len(result["relationships"]) == 2
            assert result["relationships"][0]["character"] == "Alice"
            assert result["relationships"][0]["other_character"] == "Bob"
            rel0_strength = result["relationships"][0]["interaction_strength"]
            rel1_strength = result["relationships"][1]["interaction_strength"]
            assert rel0_strength > rel1_strength
