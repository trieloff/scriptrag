"""Tests for the script bible resource functionality in MCP server."""

import json
import uuid
from unittest.mock import MagicMock

import mcp.types as types
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.migrations import initialize_database
from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.models import Script


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    mcp_settings = MagicMock()
    mcp_settings.host = "localhost"
    mcp_settings.port = 8080
    mcp_settings.max_resources = 1000
    mcp_settings.enable_all_tools = True
    settings.mcp = mcp_settings

    # Create a temporary database for testing
    test_db_path = tmp_path / "test_bible.db"
    settings.database = MagicMock()
    settings.database.path = test_db_path
    settings.get_database_path = MagicMock(return_value=test_db_path)

    return settings


@pytest.fixture
def test_ids():
    """Generate consistent test IDs."""
    return {
        "script_id": "a1b2c3d4-e5f6-4789-0123-456789abcdef",
        "loc_1": "b1b2c3d4-e5f6-4789-0123-456789abcdef",
        "loc_2": "c1b2c3d4-e5f6-4789-0123-456789abcdef",
        "loc_3": "d1b2c3d4-e5f6-4789-0123-456789abcdef",
        "char_1": "e1b2c3d4-e5f6-4789-0123-456789abcdef",
        "char_2": "f1b2c3d4-e5f6-4789-0123-456789abcdef",
        "char_3": "a2b2c3d4-e5f6-4789-0123-456789abcdef",
        "scene_1": "b2b2c3d4-e5f6-4789-0123-456789abcdef",
        "scene_2": "c2b2c3d4-e5f6-4789-0123-456789abcdef",
        "scene_3": "d2b2c3d4-e5f6-4789-0123-456789abcdef",
    }


@pytest.fixture
def populated_database(mock_settings, test_ids):
    """Create and populate a test database with screenplay data."""
    db_path = mock_settings.get_database_path()

    # Initialize database with schema
    initialize_database(db_path)

    # Populate test data
    with (
        DatabaseConnection(str(db_path)) as connection,
        connection.get_connection() as conn,
    ):
        # Insert test script
        conn.execute(
            """
                INSERT INTO scripts (id, title, source_file, format, author, genre)
                VALUES (?, 'Test Screenplay', 'test.fountain',
                        'screenplay', 'Test Author', 'Drama')
            """,
            (test_ids["script_id"],),
        )

        # Insert locations
        conn.execute(
            """
                INSERT INTO locations (
                    id, script_id, interior, name, time_of_day, raw_text
                )
                VALUES
                (?, ?, 1, 'Coffee Shop', 'DAY', 'INT. COFFEE SHOP - DAY'),
                (?, ?, 0, 'Park', 'NIGHT', 'EXT. PARK - NIGHT'),
                (?, ?, 1, 'Office', 'DAY', 'INT. OFFICE - DAY')
            """,
            (
                test_ids["loc_1"],
                test_ids["script_id"],
                test_ids["loc_2"],
                test_ids["script_id"],
                test_ids["loc_3"],
                test_ids["script_id"],
            ),
        )

        # Insert characters
        conn.execute(
            """
                INSERT INTO characters (id, script_id, name, description)
                VALUES
                (?, ?, 'ALICE', 'Main protagonist, a detective'),
                (?, ?, 'BOB', 'Supporting character, a witness'),
                (?, ?, 'CHARLIE', 'Antagonist')
            """,
            (
                test_ids["char_1"],
                test_ids["script_id"],
                test_ids["char_2"],
                test_ids["script_id"],
                test_ids["char_3"],
                test_ids["script_id"],
            ),
        )

        # Insert scenes
        conn.execute(
            """
                INSERT INTO scenes (
                    id, script_id, location_id, heading, description,
                    script_order, temporal_order, logical_order,
                    time_of_day, date_in_story, estimated_duration_minutes
                )
                VALUES
                (?, ?, ?, 'INT. COFFEE SHOP - DAY',
                 'Opening scene in coffee shop', 1, 1, 1, 'DAY', 'Day 1', 3.5),
                (?, ?, ?, 'EXT. PARK - NIGHT',
                 'Investigation at the park', 2, 3, 2, 'NIGHT', 'Day 1', 5.0),
                (?, ?, ?, 'INT. OFFICE - DAY',
                 'Flashback to earlier meeting', 3, 2, 3, 'DAY', 'Day 0', 2.5)
            """,
            (
                test_ids["scene_1"],
                test_ids["script_id"],
                test_ids["loc_1"],
                test_ids["scene_2"],
                test_ids["script_id"],
                test_ids["loc_2"],
                test_ids["scene_3"],
                test_ids["script_id"],
                test_ids["loc_3"],
            ),
        )

        # Insert scene elements with dialogue
        elem_ids = [f"elem_{i}" for i in range(1, 7)]
        conn.execute(
            """
                INSERT INTO scene_elements (id, scene_id, element_type, text, raw_text,
                                          order_in_scene, character_id, character_name)
                VALUES
                -- Scene 1 dialogue
                (?, ?, 'dialogue', 'Have you seen anything unusual?',
                 'Have you seen anything unusual?', 1, ?, 'ALICE'),
                (?, ?, 'dialogue', 'Not really, just the usual crowd.',
                 'Not really, just the usual crowd.', 2, ?, 'BOB'),
                (?, ?, 'dialogue', 'Think carefully. It matters.',
                 'Think carefully. It matters.', 3, ?, 'ALICE'),
                -- Scene 2 dialogue
                (?, ?, 'dialogue', 'This is where it happened.',
                 'This is where it happened.', 1, ?, 'ALICE'),
                (?, ?, 'dialogue', 'I know what you did.',
                 'I know what you did.', 2, ?, 'CHARLIE'),
                -- Scene 3 dialogue
                (?, ?, 'dialogue', 'We need to talk about the plan.',
                 'We need to talk about the plan.', 1, ?, 'CHARLIE')
            """,
            (
                elem_ids[0],
                test_ids["scene_1"],
                test_ids["char_1"],
                elem_ids[1],
                test_ids["scene_1"],
                test_ids["char_2"],
                elem_ids[2],
                test_ids["scene_1"],
                test_ids["char_1"],
                elem_ids[3],
                test_ids["scene_2"],
                test_ids["char_1"],
                elem_ids[4],
                test_ids["scene_2"],
                test_ids["char_3"],
                elem_ids[5],
                test_ids["scene_3"],
                test_ids["char_3"],
            ),
        )

        # Insert scene dependencies
        dep_ids = ["dep_1", "dep_2"]
        conn.execute(
            """
                INSERT INTO scene_dependencies (id, from_scene_id, to_scene_id,
                                              dependency_type, description, strength)
                VALUES
                (?, ?, ?, 'continues',
                 'Investigation continues from coffee shop to park', 0.8),
                (?, ?, ?, 'flashback_to',
                 'Flashback reveals earlier connection', 0.6)
            """,
            (
                dep_ids[0],
                test_ids["scene_1"],
                test_ids["scene_2"],
                dep_ids[1],
                test_ids["scene_2"],
                test_ids["scene_3"],
            ),
        )

        # Insert character profiles
        prof_id = "prof_1"
        conn.execute(
            """
                INSERT INTO character_profiles (
                    id, character_id, script_id, full_name,
                    age, occupation, background, personality_traits,
                    motivations, fears, goals, physical_description,
                    character_arc
                )
                VALUES
                (
                    ?, ?, ?, 'Alice Johnson', 35, 'Detective',
                    'Former military, joined police force',
                    'Determined, analytical, empathetic',
                    'Seeking justice for victims', 'Losing another case',
                    'Solve the mystery',
                    'Tall, athletic build, sharp eyes', 'From skeptic to believer'
                )
            """,
            (prof_id, test_ids["char_1"], test_ids["script_id"]),
        )

        # Insert nodes for character relationships
        node_ids = ["node_char_1", "node_char_2", "node_char_3"]
        conn.execute(
            """
                INSERT INTO nodes (id, node_type, entity_id, label)
                VALUES
                (?, 'character', ?, 'ALICE'),
                (?, 'character', ?, 'BOB'),
                (?, 'character', ?, 'CHARLIE')
            """,
            (
                node_ids[0],
                test_ids["char_1"],
                node_ids[1],
                test_ids["char_2"],
                node_ids[2],
                test_ids["char_3"],
            ),
        )

        # Insert edges for character relationships
        edge_ids = ["edge_1", "edge_2"]
        conn.execute(
            """
                INSERT INTO edges (id, from_node_id, to_node_id, edge_type, weight)
                VALUES
                (?, ?, ?, 'INTERACTS_WITH', 0.7),
                (?, ?, ?, 'SPEAKS_TO', 0.9)
            """,
            (
                edge_ids[0],
                node_ids[0],
                node_ids[1],
                edge_ids[1],
                node_ids[0],
                node_ids[2],
            ),
        )

        # Insert plot threads
        thread_ids = ["thread_1", "thread_2"]
        conn.execute(
            """
                INSERT INTO plot_threads (id, script_id, name, thread_type, priority,
                                        description, status, primary_characters_json,
                                        key_scenes_json)
                VALUES
                (?, ?, 'Mystery Investigation', 'main', 5,
                 'Alice investigates mysterious events', 'active',
                 ?, ?),
                (?, ?, 'Hidden Past', 'subplot', 3,
                 'Charlies secret connection revealed', 'resolved',
                 ?, ?)
            """,
            (
                thread_ids[0],
                test_ids["script_id"],
                json.dumps([test_ids["char_1"], test_ids["char_3"]]),
                json.dumps([test_ids["scene_1"], test_ids["scene_2"]]),
                thread_ids[1],
                test_ids["script_id"],
                json.dumps([test_ids["char_3"]]),
                json.dumps([test_ids["scene_3"]]),
            ),
        )

        conn.commit()

    return db_path


@pytest.fixture
def mcp_server_with_data(mock_settings, populated_database, test_ids):  # noqa: ARG001
    """Create MCP server instance with populated test database."""
    server = ScriptRAGMCPServer(mock_settings)

    # Add script to cache
    script = Script(
        id=uuid.UUID(test_ids["script_id"]),
        title="Test Screenplay",
        source_file="test.fountain",
    )
    server._scripts_cache = {test_ids["script_id"]: script}

    return server


class TestScriptBibleResource:
    """Test script bible resource functionality."""

    @pytest.mark.asyncio
    async def test_read_script_resource_with_scenes(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns scene data."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ReadResourceResult)

        content = json.loads(result.root.contents[0].text)

        # Check basic info
        assert content["script_id"] == test_ids["script_id"]
        assert content["title"] == "Test Screenplay"

        # Check scenes
        assert "scenes" in content
        assert len(content["scenes"]) == 3

        # Verify scene data
        scene1 = content["scenes"][0]
        assert scene1["id"] == test_ids["scene_1"]
        assert scene1["heading"] == "INT. COFFEE SHOP - DAY"
        assert scene1["description"] == "Opening scene in coffee shop"
        assert scene1["script_order"] == 1
        assert scene1["duration_minutes"] == 3.5
        assert scene1["location"]["name"] == "Coffee Shop"
        assert scene1["location"]["interior"] is True

        # Check scene has characters
        assert len(scene1["characters"]) == 2
        assert any(c["name"] == "ALICE" for c in scene1["characters"])
        assert any(c["name"] == "BOB" for c in scene1["characters"])

        # Check dialogue counts
        alice_in_scene1 = next(c for c in scene1["characters"] if c["name"] == "ALICE")
        assert alice_in_scene1["dialogue_count"] == 2

    @pytest.mark.asyncio
    async def test_read_script_resource_with_characters(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns character data."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Check characters
        assert "characters" in content
        assert len(content["characters"]) == 3

        # Find Alice
        alice = next(c for c in content["characters"] if c["name"] == "ALICE")
        assert alice["description"] == "Main protagonist, a detective"
        assert alice["scene_count"] == 2
        assert alice["dialogue_count"] == 3
        assert len(alice["scenes"]) == 2

        # Check character profile data
        assert alice["full_name"] == "Alice Johnson"
        assert alice["age"] == 35
        assert alice["occupation"] == "Detective"
        assert alice["personality_traits"] == "Determined, analytical, empathetic"
        assert alice["character_arc"] == "From skeptic to believer"

        # Check character relationships
        assert "relationships" in alice
        assert len(alice["relationships"]) == 2
        bob_rel = next(
            r for r in alice["relationships"] if r["character_name"] == "BOB"
        )
        assert bob_rel["relationship_type"] == "INTERACTS_WITH"
        assert bob_rel["strength"] == 0.7

    @pytest.mark.asyncio
    async def test_read_script_resource_with_scene_dependencies(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns scene relationships."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Check scene relationships
        scene1 = content["scenes"][0]
        assert "relationships" in scene1
        assert len(scene1["relationships"]) == 1

        rel = scene1["relationships"][0]
        assert rel["to_scene_id"] == test_ids["scene_2"]
        assert rel["type"] == "continues"
        assert rel["description"] == "Investigation continues from coffee shop to park"
        assert rel["strength"] == 0.8

    @pytest.mark.asyncio
    async def test_read_script_resource_with_plot_threads(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns plot threads."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Check plot threads
        assert "plot_threads" in content
        assert len(content["plot_threads"]) == 2

        main_thread = next(t for t in content["plot_threads"] if t["type"] == "main")
        assert main_thread["name"] == "Mystery Investigation"
        assert main_thread["priority"] == 5
        assert main_thread["status"] == "active"
        assert len(main_thread["primary_characters"]) == 2
        assert len(main_thread["key_scenes"]) == 2

    @pytest.mark.asyncio
    async def test_read_script_resource_with_timeline(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns timeline data."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Check timeline
        assert "timeline" in content
        timeline = content["timeline"]

        # Check chronological order
        assert "chronological" in timeline
        assert len(timeline["chronological"]) == 3
        # Should be ordered by temporal_order (scene3, scene1, scene2)
        assert timeline["chronological"][0]["scene_id"] == test_ids["scene_1"]
        assert timeline["chronological"][1]["scene_id"] == test_ids["scene_3"]
        assert timeline["chronological"][2]["scene_id"] == test_ids["scene_2"]

        # Check location grouping
        assert "by_location" in timeline
        assert len(timeline["by_location"]) == 3
        assert "Coffee Shop" in timeline["by_location"]
        assert test_ids["scene_1"] in timeline["by_location"]["Coffee Shop"]

        # Check act structure
        assert "by_act" in timeline
        # With 3 scenes: act 1 gets none (≤0.75), act 2 gets scenes 1&2, act 3 gets 3
        assert len(timeline["by_act"]["act_1"]) == 0  # No scenes in first 25%
        assert len(timeline["by_act"]["act_2"]) == 2  # Scenes 1 and 2
        assert len(timeline["by_act"]["act_3"]) == 1  # Scene 3

    @pytest.mark.asyncio
    async def test_read_script_resource_with_stats(
        self, mcp_server_with_data, test_ids
    ):
        """Test reading script resource returns correct statistics."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Check stats
        assert "stats" in content
        stats = content["stats"]

        assert stats["total_scenes"] == 3
        assert stats["total_characters"] == 3
        assert stats["total_dialogue"] == 6
        assert stats["estimated_runtime_minutes"] == 11.0  # 3.5 + 5.0 + 2.5
        assert stats["locations"] == 3
        assert stats["active_plot_threads"] == 1

    @pytest.mark.asyncio
    async def test_read_script_resource_empty_database(self, mock_settings):
        """Test reading script resource with no data in database."""
        # Create server with empty database
        db_path = mock_settings.get_database_path()
        initialize_database(db_path)

        empty_script_id = "e1b2c3d4-e5f6-4789-0123-456789abcdef"

        server = ScriptRAGMCPServer(mock_settings)
        script = Script(
            id=uuid.UUID(empty_script_id),
            title="Empty Script",
            source_file="empty.fountain",
        )
        server._scripts_cache = {empty_script_id: script}

        # Insert only the script
        with (
            DatabaseConnection(str(db_path)) as connection,
            connection.get_connection() as conn,
        ):
            conn.execute(
                """
                        INSERT INTO scripts (id, title, source_file)
                        VALUES (?, 'Empty Script', 'empty.fountain')
                    """,
                (empty_script_id,),
            )
            conn.commit()

        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{empty_script_id}")
            ),
        )

        result = await server._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Should have empty arrays but valid structure
        assert content["script_id"] == empty_script_id
        assert len(content["scenes"]) == 0
        assert len(content["characters"]) == 0
        assert len(content["plot_threads"]) == 0
        assert content["stats"]["total_scenes"] == 0
        assert content["stats"]["total_characters"] == 0

    @pytest.mark.asyncio
    async def test_read_script_resource_character_sorting(
        self, mcp_server_with_data, test_ids
    ):
        """Test characters are sorted by dialogue count."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl(f"screenplay://{test_ids['script_id']}")
            ),
        )

        result = await mcp_server_with_data._handle_read_resource(request)
        content = json.loads(result.root.contents[0].text)

        # Characters should be sorted by dialogue count (descending)
        characters = content["characters"]
        assert characters[0]["name"] == "ALICE"  # 3 dialogues
        assert characters[1]["name"] in ["BOB", "CHARLIE"]  # 1 dialogue each

        # Verify descending order
        for i in range(len(characters) - 1):
            assert (
                characters[i]["dialogue_count"] >= characters[i + 1]["dialogue_count"]
            )
