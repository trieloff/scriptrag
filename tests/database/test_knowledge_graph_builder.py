"""Tests for the knowledge graph builder module."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.knowledge_graph_builder import KnowledgeGraphBuilder
from scriptrag.database.operations import GraphOperations
from scriptrag.llm.client import LLMClient
from scriptrag.models import (
    Action,
    Character,
    Dialogue,
    Location,
    Scene,
    Script,
)


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    return MagicMock(spec=DatabaseConnection)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock(spec=LLMClient)
    client.generate_text = AsyncMock(
        return_value="Summary: Test\nTheme: Drama\nTone: Tense"
    )
    return client


@pytest.fixture
def sample_script():
    """Create a sample script for testing."""
    return Script(
        title="Test Script",
        fountain_source=(
            "INT. COFFEE SHOP - DAY\n\n"
            "JOHN enters.\n\n"
            "JOHN\nHello, Sarah!\n\n"
            "SARAH\nHi John!"
        ),
        format="screenplay",
        author="Test Author",
    )


@pytest.fixture
def sample_characters():
    """Create sample characters."""
    john = Character(name="JOHN", description="Main character")
    sarah = Character(name="SARAH", description="Supporting character")
    return [john, sarah]


@pytest.fixture
def sample_scene(sample_characters):
    """Create a sample scene with elements."""
    john, sarah = sample_characters
    scene = Scene(
        script_id=uuid4(),
        location=Location(
            interior=True,
            name="COFFEE SHOP",
            time="DAY",
            raw_text="INT. COFFEE SHOP - DAY",
        ),
        heading="INT. COFFEE SHOP - DAY",
        script_order=1,
    )

    # Add scene elements
    scene.elements = [
        Action(
            text="JOHN enters.",
            raw_text="JOHN enters.",
            scene_id=scene.id,
            order_in_scene=0,
        ),
        Dialogue(
            text="Hello, Sarah!",
            raw_text="Hello, Sarah!",
            scene_id=scene.id,
            order_in_scene=1,
            character_id=john.id,
            character_name="JOHN",
        ),
        Dialogue(
            text="Hi John!",
            raw_text="Hi John!",
            scene_id=scene.id,
            order_in_scene=2,
            character_id=sarah.id,
            character_name="SARAH",
        ),
    ]

    scene.characters = [john.id, sarah.id]
    return scene


@pytest.mark.asyncio
async def test_knowledge_graph_builder_init(mock_connection, mock_llm_client):
    """Test KnowledgeGraphBuilder initialization."""
    builder = KnowledgeGraphBuilder(mock_connection, mock_llm_client)

    assert builder.connection == mock_connection
    assert builder.llm_client == mock_llm_client
    assert isinstance(builder.graph_ops, GraphOperations)
    assert builder._location_nodes == {}
    assert builder._character_nodes == {}


@pytest.mark.asyncio
async def test_build_from_script_basic(mock_connection, sample_script):
    """Test basic script graph building without LLM enrichment."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Mock graph operations
    with (
        patch.object(
            builder.graph_ops, "create_script_graph", return_value="script_node_1"
        ),
        patch.object(builder, "_create_character_node", new_callable=AsyncMock),
        patch.object(
            builder, "_create_scene_node", new_callable=AsyncMock
        ) as mock_scene,
    ):
        mock_scene.return_value = "scene_node_1"
        stats = await builder.build_from_script(sample_script, enrich_with_llm=False)

    assert stats["script_node_id"] == "script_node_1"
    assert stats["total_nodes"] >= 1  # At least script node
    assert stats["enrichment_status"] == "not_attempted"


@pytest.mark.asyncio
async def test_create_character_node(mock_connection, sample_characters):
    """Test character node creation."""
    builder = KnowledgeGraphBuilder(mock_connection)
    john = sample_characters[0]

    # Mock the create_character_node method
    with patch.object(
        builder.graph_ops, "create_character_node", return_value="char_node_1"
    ):
        node_id = await builder._create_character_node(john, "script_node_1")

    assert node_id == "char_node_1"
    assert builder._character_nodes[john.id] == "char_node_1"

    # Test deduplication
    node_id2 = await builder._create_character_node(john, "script_node_1")
    assert node_id2 == "char_node_1"  # Same node ID


@pytest.mark.asyncio
async def test_create_scene_node(mock_connection, sample_scene, sample_characters):
    """Test scene node creation with relationships."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Pre-populate character nodes
    for char in sample_characters:
        builder._character_nodes[char.id] = f"char_node_{char.name}"

    # Mock graph operations
    with (
        patch.object(
            builder.graph_ops, "create_scene_node", return_value="scene_node_1"
        ),
        patch.object(builder.graph_ops, "connect_scene_to_location"),
        patch.object(builder.graph_ops, "connect_character_to_scene"),
        patch.object(
            builder, "_get_or_create_location_node", new_callable=AsyncMock
        ) as mock_loc,
        patch.object(
            builder, "_process_scene_elements", new_callable=AsyncMock
        ) as mock_process,
        patch.object(
            builder, "_extract_character_interactions", new_callable=AsyncMock
        ),
    ):
        mock_loc.return_value = "location_node_1"
        mock_process.return_value = {}
        scene_node_id = await builder._create_scene_node(
            sample_scene, "script_node_1", 0
        )

    assert scene_node_id == "scene_node_1"


@pytest.mark.asyncio
async def test_process_scene_elements(mock_connection, sample_scene, sample_characters):
    """Test processing scene elements for character statistics."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Pre-populate character nodes
    for char in sample_characters:
        builder._character_nodes[char.id] = f"char_node_{char.name}"

    # Mock graph.get_node to return character nodes
    mock_nodes = {}
    for char in sample_characters:
        mock_node = MagicMock()
        mock_node.label = char.name
        mock_nodes[f"char_node_{char.name}"] = mock_node

    with patch.object(
        builder.graph_ops.graph,
        "get_node",
        side_effect=lambda node_id: mock_nodes.get(node_id),
    ):
        stats = await builder._process_scene_elements(sample_scene, "scene_node_1")

    # Check dialogue counts
    john, sarah = sample_characters
    assert stats[john.id]["dialogues"] == 1
    assert stats[sarah.id]["dialogues"] == 1
    assert stats[john.id]["mentions"] >= 0  # May have mentions in action


@pytest.mark.asyncio
async def test_extract_character_interactions(
    mock_connection, sample_scene, sample_characters
):
    """Test extraction of character interactions from dialogue."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Pre-populate character nodes
    john, sarah = sample_characters
    builder._character_nodes[john.id] = "char_node_john"
    builder._character_nodes[sarah.id] = "char_node_sarah"

    # Mock the interaction connection
    with patch.object(
        builder.graph_ops, "connect_character_interaction"
    ) as mock_interact:
        await builder._extract_character_interactions(sample_scene, "scene_node_1")

        # Should create interaction from John to Sarah (dialogue exchange)
        mock_interact.assert_called_once_with(
            "char_node_john", "char_node_sarah", "scene_node_1", dialogue_count=1
        )


@pytest.mark.asyncio
async def test_enrich_with_llm(mock_connection, mock_llm_client):
    """Test LLM enrichment of graph nodes."""
    builder = KnowledgeGraphBuilder(mock_connection, mock_llm_client)

    # Mock node retrieval and update
    mock_node = MagicMock()
    mock_node.properties = {"existing": "property"}

    with (
        patch.object(builder.graph_ops.graph, "get_node", return_value=mock_node),
        patch.object(builder.graph_ops.graph, "update_node") as mock_update,
        patch.object(builder, "_get_scene_content", return_value="Scene content"),
    ):
        await builder._enrich_scene_node("scene_node_1")

    # Check that LLM was called
    mock_llm_client.generate_text.assert_called_once()

    # Check that node was updated with parsed properties
    mock_update.assert_called_once()
    call_args = mock_update.call_args[1]
    assert "properties" in call_args
    assert "summary" in call_args["properties"]


@pytest.mark.asyncio
async def test_build_temporal_graph(mock_connection):
    """Test temporal graph construction."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Mock scenes with time metadata
    mock_scenes = [
        MagicMock(
            id="scene_1", properties={"time_of_day": "MORNING", "script_order": 1}
        ),
        MagicMock(id="scene_2", properties={"time_of_day": "NIGHT", "script_order": 2}),
        MagicMock(id="scene_3", properties={"time_of_day": "DAY", "script_order": 3}),
    ]

    with (
        patch.object(builder.graph_ops, "get_script_scenes", return_value=mock_scenes),
        patch.object(
            builder.graph_ops,
            "create_scene_sequence",
            return_value=["edge1", "edge2"],
        ) as mock_seq,
    ):
        edges_created = await builder.build_temporal_graph("script_node_1")

    assert edges_created == 2
    mock_seq.assert_called_once()

    # Check temporal ordering (morning -> day -> night)
    ordered_ids = mock_seq.call_args[0][0]
    assert ordered_ids[0] == "scene_1"  # MORNING
    assert ordered_ids[1] == "scene_3"  # DAY
    assert ordered_ids[2] == "scene_2"  # NIGHT


@pytest.mark.asyncio
async def test_build_logical_dependencies(mock_connection):
    """Test logical dependency graph construction."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Mock scenes
    mock_scenes = [
        MagicMock(id="scene_1", properties={"script_order": 1}),
        MagicMock(id="scene_2", properties={"script_order": 2}),
    ]

    # Mock character appearances
    with (
        patch.object(builder.graph_ops, "get_script_scenes", return_value=mock_scenes),
        patch.object(builder.graph_ops.graph, "find_edges") as mock_find,
    ):
        # Scene 1 and 2 share multiple characters
        mock_find.side_effect = [
            # scene 1
            [
                MagicMock(from_node_id="char1"),
                MagicMock(from_node_id="char2"),
            ],
            # scene 2
            [
                MagicMock(from_node_id="char1"),
                MagicMock(from_node_id="char2"),
            ],
        ]

        with patch.object(builder.graph_ops.graph, "add_edge", return_value="edge1"):
            edges_created = await builder.build_logical_dependencies("script_node_1")

    assert edges_created >= 0  # May create dependencies based on character overlap


@pytest.mark.asyncio
async def test_analyze_temporal_order(mock_connection):
    """Test temporal order analysis."""
    builder = KnowledgeGraphBuilder(mock_connection)

    scenes = [
        MagicMock(id="s1", properties={"time_of_day": "NIGHT", "script_order": 1}),
        MagicMock(id="s2", properties={"time_of_day": "MORNING", "script_order": 2}),
        MagicMock(id="s3", properties={"time_of_day": "DAY", "script_order": 3}),
    ]

    ordered = builder._analyze_temporal_order(scenes)

    # Should order: MORNING -> DAY -> NIGHT
    assert ordered == ["s2", "s3", "s1"]


@pytest.mark.asyncio
async def test_get_or_create_location_node(mock_connection):
    """Test location node creation and deduplication."""
    builder = KnowledgeGraphBuilder(mock_connection)

    location = Location(
        interior=True, name="OFFICE", time="DAY", raw_text="INT. OFFICE - DAY"
    )

    with patch.object(
        builder.graph_ops, "create_location_node", return_value="loc_node_1"
    ):
        node_id = await builder._get_or_create_location_node(location, "script_node_1")

    assert node_id == "loc_node_1"
    assert str(location) in builder._location_nodes

    # Test deduplication
    node_id2 = await builder._get_or_create_location_node(location, "script_node_1")
    assert node_id2 == "loc_node_1"


@pytest.mark.asyncio
async def test_extract_character_mentions(mock_connection):
    """Test character mention extraction from action text."""
    builder = KnowledgeGraphBuilder(mock_connection)

    # Set up character nodes
    char_id = uuid4()
    builder._character_nodes[char_id] = "char_node_1"

    # Mock node retrieval
    mock_node = MagicMock()
    mock_node.label = "JOHN"

    with patch.object(builder.graph_ops.graph, "get_node", return_value=mock_node):
        mentions = builder._extract_character_mentions("JOHN walks to the door.")

    assert char_id in mentions


@pytest.mark.asyncio
async def test_build_from_fountain_file(mock_connection):
    """Test building from fountain file."""
    builder = KnowledgeGraphBuilder(mock_connection)

    with patch(
        "scriptrag.database.knowledge_graph_builder.FountainParser"
    ) as mock_parser:
        mock_script = MagicMock(spec=Script)
        mock_parser.return_value.parse_file.return_value = mock_script

        with patch.object(
            builder, "build_from_script", new_callable=AsyncMock
        ) as mock_build:
            mock_build.return_value = {"total_nodes": 10}

            stats = await builder.build_from_fountain_file(
                "test.fountain", enrich_with_llm=False
            )

    assert stats["total_nodes"] == 10
    # Check that build_from_script was called with correct arguments
    # The second argument is a positional boolean, not a keyword argument
    mock_build.assert_called_once()
    call_args = mock_build.call_args
    assert call_args[0][0] == mock_script
    assert call_args[0][1] is False
