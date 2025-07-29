#!/usr/bin/env python3
"""
Unit tests for database CRUD operations, graph operations, and transactions.
"""

import sqlite3
from datetime import datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from scriptrag.database import DatabaseConnection
from scriptrag.database.connection import DatabaseError, TransactionError
from scriptrag.database.graph import GraphEdge, GraphNode, GraphQueryError
from scriptrag.models import (
    Character,
    EdgeType,
    Location,
    NodeType,
    Scene,
    SceneOrderType,
    Script,
)


class TestDatabaseConnection:
    """Test DatabaseConnection class."""

    def test_connection_initialization(self, temp_db_path):
        """Test database connection initialization."""
        conn = DatabaseConnection(temp_db_path)
        assert conn.db_path == temp_db_path
        assert conn._connection is None
        assert conn._in_transaction is False

    def test_connection_context_manager(self, temp_db_path):
        """Test connection as context manager."""
        with DatabaseConnection(temp_db_path) as conn:
            # Connection should be established
            assert conn._connection is not None
            # Should be able to execute queries
            result = conn.fetch_one("SELECT 1 as test")
            assert result["test"] == 1

        # Connection should be closed after context
        assert conn._connection is None

    def test_execute_query(self, db_connection):
        """Test executing queries."""
        # Test SELECT
        result = db_connection.fetch_one("SELECT 1 as num, 'test' as str")
        assert result["num"] == 1
        assert result["str"] == "test"

        # Test parameterized query
        result = db_connection.fetch_one(
            "SELECT ? as param1, ? as param2", ("value1", 42)
        )
        assert result["param1"] == "value1"
        assert result["param2"] == 42

    def test_fetch_all(self, db_connection):
        """Test fetching multiple rows."""
        # Create test table
        with db_connection.transaction() as conn:
            conn.execute("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test_items (name) VALUES (?)", ("item1",))
            conn.execute("INSERT INTO test_items (name) VALUES (?)", ("item2",))
            conn.execute("INSERT INTO test_items (name) VALUES (?)", ("item3",))

        # Fetch all rows
        rows = db_connection.fetch_all("SELECT * FROM test_items ORDER BY id")
        assert len(rows) == 3
        assert rows[0]["name"] == "item1"
        assert rows[1]["name"] == "item2"
        assert rows[2]["name"] == "item3"

    def test_transaction_commit(self, db_connection):
        """Test transaction commit."""
        with db_connection.transaction() as conn:
            conn.execute("CREATE TABLE test_trans (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_trans (value) VALUES (?)", ("test",))

        # Data should be persisted
        result = db_connection.fetch_one("SELECT COUNT(*) as cnt FROM test_trans")
        assert result["cnt"] == 1

    def test_transaction_rollback(self, db_connection):
        """Test transaction rollback on error."""
        # Create table first
        with db_connection.transaction() as conn:
            conn.execute(
                "CREATE TABLE test_rollback "
                "(id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )

        # Try to insert invalid data
        with pytest.raises(sqlite3.IntegrityError), db_connection.transaction() as conn:
            conn.execute("INSERT INTO test_rollback (value) VALUES (?)", ("valid",))
            # This should fail due to NOT NULL constraint
            conn.execute(
                "INSERT INTO test_rollback (id, value) VALUES (?, ?)", (1, None)
            )

        # No data should be persisted due to rollback
        result = db_connection.fetch_one("SELECT COUNT(*) as cnt FROM test_rollback")
        assert result["cnt"] == 0

    def test_nested_transactions_not_allowed(self, db_connection):
        """Test that nested transactions raise error."""
        with (
            pytest.raises(TransactionError, match="nested transaction"),
            db_connection.transaction(),
            db_connection.transaction(),
        ):
            pass

    def test_connection_closed_error(self, temp_db_path):
        """Test operations on closed connection."""
        conn = DatabaseConnection(temp_db_path)
        # Don't open connection

        with pytest.raises(DatabaseError, match="closed"):
            conn.fetch_one("SELECT 1")

    def test_execute_many(self, db_connection):
        """Test bulk insert operations."""
        with db_connection.transaction() as conn:
            conn.execute("CREATE TABLE test_bulk (id INTEGER PRIMARY KEY, name TEXT)")

            # Bulk insert
            data = [(i, f"item_{i}") for i in range(100)]
            conn.executemany("INSERT INTO test_bulk (id, name) VALUES (?, ?)", data)

        # Verify all inserted
        result = db_connection.fetch_one("SELECT COUNT(*) as cnt FROM test_bulk")
        assert result["cnt"] == 100

    def test_connection_pragma_settings(self, temp_db_path):
        """Test that connection sets proper pragmas."""
        with DatabaseConnection(temp_db_path) as conn:
            # Check foreign keys are enabled
            result = conn.fetch_one("PRAGMA foreign_keys")
            assert result["foreign_keys"] == 1

            # Check journal mode
            result = conn.fetch_one("PRAGMA journal_mode")
            assert result["journal_mode"] == "WAL"


class TestGraphDatabase:
    """Test GraphDatabase class."""

    def test_create_node(self, graph_db):
        """Test node creation."""
        # Create a script node
        node_data = {
            "title": "Test Script",
            "author": "Test Author",
            "created_at": datetime.utcnow().isoformat(),
        }

        node = graph_db.create_node(NodeType.SCRIPT, node_data)

        assert isinstance(node, GraphNode)
        assert node.type == NodeType.SCRIPT
        assert node.properties["title"] == "Test Script"
        assert node.properties["author"] == "Test Author"
        assert isinstance(node.id, str)
        assert UUID(node.id)  # Valid UUID

    def test_get_node(self, graph_db):
        """Test node retrieval."""
        # Create a node
        node = graph_db.create_node(
            NodeType.CHARACTER, {"name": "PROTAGONIST", "description": "Main character"}
        )

        # Retrieve it
        retrieved = graph_db.get_node(node.id)
        assert retrieved is not None
        assert retrieved.id == node.id
        assert retrieved.type == NodeType.CHARACTER
        assert retrieved.properties["name"] == "PROTAGONIST"

    def test_get_nonexistent_node(self, graph_db):
        """Test getting non-existent node."""
        fake_id = str(uuid4())
        node = graph_db.get_node(fake_id)
        assert node is None

    def test_update_node(self, graph_db):
        """Test node update."""
        # Create a node
        node = graph_db.create_node(
            NodeType.SCENE, {"heading": "INT. ROOM - DAY", "description": "Original"}
        )

        # Update it
        updated = graph_db.update_node(
            node.id, {"description": "Updated description", "page_number": 42}
        )

        assert updated is not None
        assert updated.properties["heading"] == "INT. ROOM - DAY"  # Unchanged
        assert updated.properties["description"] == "Updated description"
        assert updated.properties["page_number"] == 42

    def test_delete_node(self, graph_db):
        """Test node deletion."""
        # Create a node
        node = graph_db.create_node(NodeType.LOCATION, {"name": "COFFEE SHOP"})

        # Delete it
        success = graph_db.delete_node(node.id)
        assert success is True

        # Verify it's gone
        retrieved = graph_db.get_node(node.id)
        assert retrieved is None

    def test_delete_node_with_edges(self, graph_db):
        """Test that deleting node also deletes its edges."""
        # Create nodes
        script = graph_db.create_node(NodeType.SCRIPT, {"title": "Test"})
        scene = graph_db.create_node(NodeType.SCENE, {"heading": "INT. ROOM - DAY"})

        # Create edge
        graph_db.create_edge(script.id, scene.id, EdgeType.HAS_SCENE)

        # Delete scene node
        graph_db.delete_node(scene.id)

        # Edge should also be deleted
        edges = graph_db.get_edges(source_id=script.id)
        assert len(edges) == 0

    def test_create_edge(self, graph_db):
        """Test edge creation."""
        # Create nodes
        char1 = graph_db.create_node(NodeType.CHARACTER, {"name": "ALICE"})
        char2 = graph_db.create_node(NodeType.CHARACTER, {"name": "BOB"})

        # Create edge
        edge = graph_db.create_edge(
            char1.id,
            char2.id,
            EdgeType.INTERACTS_WITH,
            {"context": "They are friends", "weight": 5},
        )

        assert isinstance(edge, GraphEdge)
        assert edge.source_id == char1.id
        assert edge.target_id == char2.id
        assert edge.type == EdgeType.INTERACTS_WITH
        assert edge.properties["context"] == "They are friends"
        assert edge.properties["weight"] == 5

    def test_create_duplicate_edge(self, graph_db):
        """Test creating duplicate edge updates existing."""
        # Create nodes
        node1 = graph_db.create_node(NodeType.SCENE, {"heading": "Scene 1"})
        node2 = graph_db.create_node(NodeType.SCENE, {"heading": "Scene 2"})

        # Create edge
        edge1 = graph_db.create_edge(node1.id, node2.id, EdgeType.FOLLOWS, {"order": 1})

        # Create duplicate with different properties
        edge2 = graph_db.create_edge(
            node1.id, node2.id, EdgeType.FOLLOWS, {"order": 2, "direct": True}
        )

        # Should be same edge ID but updated properties
        assert edge2.id == edge1.id
        assert edge2.properties["order"] == 2
        assert edge2.properties["direct"] is True

    def test_get_edges_various_filters(self, graph_db):
        """Test getting edges with various filters."""
        # Create test graph
        script = graph_db.create_node(NodeType.SCRIPT, {"title": "Test"})
        scene1 = graph_db.create_node(NodeType.SCENE, {"heading": "Scene 1"})
        scene2 = graph_db.create_node(NodeType.SCENE, {"heading": "Scene 2"})
        char = graph_db.create_node(NodeType.CHARACTER, {"name": "ALICE"})

        # Create edges
        graph_db.create_edge(script.id, scene1.id, EdgeType.HAS_SCENE)
        graph_db.create_edge(script.id, scene2.id, EdgeType.HAS_SCENE)
        graph_db.create_edge(scene1.id, char.id, EdgeType.FEATURES_CHARACTER)
        graph_db.create_edge(scene1.id, scene2.id, EdgeType.FOLLOWS)

        # Test source filter
        edges = graph_db.get_edges(source_id=script.id)
        assert len(edges) == 2
        assert all(e.source_id == script.id for e in edges)

        # Test target filter
        edges = graph_db.get_edges(target_id=char.id)
        assert len(edges) == 1
        assert edges[0].target_id == char.id

        # Test type filter
        edges = graph_db.get_edges(edge_type=EdgeType.HAS_SCENE)
        assert len(edges) == 2
        assert all(e.type == EdgeType.HAS_SCENE for e in edges)

        # Test combined filters
        edges = graph_db.get_edges(
            source_id=scene1.id, edge_type=EdgeType.FEATURES_CHARACTER
        )
        assert len(edges) == 1
        assert edges[0].source_id == scene1.id
        assert edges[0].target_id == char.id

    def test_delete_edge(self, graph_db):
        """Test edge deletion."""
        # Create nodes and edge
        node1 = graph_db.create_node(NodeType.LOCATION, {"name": "ROOM A"})
        node2 = graph_db.create_node(NodeType.LOCATION, {"name": "ROOM B"})
        edge = graph_db.create_edge(node1.id, node2.id, EdgeType.CONNECTS_TO)

        # Delete edge
        success = graph_db.delete_edge(edge.id)
        assert success is True

        # Verify it's gone
        edges = graph_db.get_edges(source_id=node1.id)
        assert len(edges) == 0

    def test_query_nodes(self, graph_db):
        """Test querying nodes."""
        # Create test nodes
        graph_db.create_node(NodeType.CHARACTER, {"name": "ALICE", "age": 25})
        graph_db.create_node(NodeType.CHARACTER, {"name": "BOB", "age": 30})
        graph_db.create_node(NodeType.CHARACTER, {"name": "CHARLIE", "age": 25})
        graph_db.create_node(NodeType.LOCATION, {"name": "PARK"})

        # Query by type
        chars = graph_db.query_nodes(node_type=NodeType.CHARACTER)
        assert len(chars) == 3

        # Query by properties
        young_chars = graph_db.query_nodes(
            node_type=NodeType.CHARACTER, properties={"age": 25}
        )
        assert len(young_chars) == 2

        # Query with limit
        limited = graph_db.query_nodes(node_type=NodeType.CHARACTER, limit=2)
        assert len(limited) == 2

    def test_get_neighbors(self, graph_db):
        """Test getting node neighbors."""
        # Create a small graph
        center = graph_db.create_node(NodeType.SCENE, {"heading": "Center Scene"})
        char1 = graph_db.create_node(NodeType.CHARACTER, {"name": "CHAR1"})
        char2 = graph_db.create_node(NodeType.CHARACTER, {"name": "CHAR2"})
        loc = graph_db.create_node(NodeType.LOCATION, {"name": "LOCATION"})

        # Create edges
        graph_db.create_edge(center.id, char1.id, EdgeType.FEATURES_CHARACTER)
        graph_db.create_edge(center.id, char2.id, EdgeType.FEATURES_CHARACTER)
        graph_db.create_edge(center.id, loc.id, EdgeType.LOCATED_AT)

        # Get all neighbors
        neighbors = graph_db.get_neighbors(center.id)
        assert len(neighbors) == 3

        # Get neighbors of specific type
        char_neighbors = graph_db.get_neighbors(
            center.id, edge_type=EdgeType.FEATURES_CHARACTER
        )
        assert len(char_neighbors) == 2
        assert all(n.type == NodeType.CHARACTER for n in char_neighbors)

    def test_graph_transaction_rollback(self, graph_db):
        """Test that graph operations rollback properly."""
        # Create initial node
        node1 = graph_db.create_node(NodeType.SCRIPT, {"title": "Initial"})

        try:
            with graph_db.connection.transaction():
                # Create node in transaction
                node2 = graph_db.create_node(
                    NodeType.SCRIPT, {"title": "In Transaction"}
                )
                # Force an error
                raise ValueError("Forced error")
        except ValueError:
            pass

        # node2 should not exist due to rollback
        assert graph_db.get_node(node2.id) is None
        # node1 should still exist
        assert graph_db.get_node(node1.id) is not None


class TestGraphOperations:
    """Test GraphOperations class for screenplay-specific operations."""

    @pytest.fixture
    def sample_script_node(self, graph_ops):
        """Create a sample script node."""
        script = Script(
            title="Test Screenplay",
            author="Test Author",
            genre="Drama",
            description="A test screenplay",
        )
        return graph_ops.create_script(script)

    def test_create_script(self, graph_ops):
        """Test script creation."""
        script = Script(
            title="New Script",
            author="Author Name",
            genre="Action",
            description="An action script",
            is_series=False,
        )

        node = graph_ops.create_script(script)

        assert node.type == NodeType.SCRIPT
        assert node.properties["title"] == "New Script"
        assert node.properties["author"] == "Author Name"
        assert node.properties["genre"] == "Action"
        assert node.properties["is_series"] is False

    def test_create_scene(self, graph_ops, sample_script_node):
        """Test scene creation."""
        scene = Scene(
            script_id=UUID(sample_script_node.id),
            heading="INT. COFFEE SHOP - DAY",
            description="A busy coffee shop",
            script_order=1,
            page_number=5,
        )

        scene_node = graph_ops.create_scene(scene, sample_script_node.id)

        assert scene_node.type == NodeType.SCENE
        assert scene_node.properties["heading"] == "INT. COFFEE SHOP - DAY"
        assert scene_node.properties["script_order"] == 1

        # Check edge created
        edges = graph_ops.graph.get_edges(
            source_id=sample_script_node.id,
            target_id=scene_node.id,
            edge_type=EdgeType.HAS_SCENE,
        )
        assert len(edges) == 1

    def test_create_character(self, graph_ops):
        """Test character creation."""
        character = Character(
            name="PROTAGONIST",
            description="The main character",
            aliases=["HERO", "MAIN CHARACTER"],
        )

        char_node = graph_ops.create_character(character)

        assert char_node.type == NodeType.CHARACTER
        assert char_node.properties["name"] == "PROTAGONIST"
        assert char_node.properties["description"] == "The main character"
        assert "HERO" in char_node.properties["aliases"]

    def test_create_location(self, graph_ops):
        """Test location creation."""
        location = Location(
            interior=True,
            name="APARTMENT",
            time="NIGHT",
            raw_text="INT. APARTMENT - NIGHT",
        )

        loc_node = graph_ops.create_location(location)

        assert loc_node.type == NodeType.LOCATION
        assert loc_node.properties["interior"] is True
        assert loc_node.properties["name"] == "APARTMENT"
        assert loc_node.properties["time"] == "NIGHT"

    def test_link_scene_character(self, graph_ops, sample_script_node):
        """Test linking scene to character."""
        # Create scene and character
        scene = Scene(
            script_id=UUID(sample_script_node.id),
            heading="INT. ROOM - DAY",
            script_order=1,
        )
        scene_node = graph_ops.create_scene(scene, sample_script_node.id)

        character = Character(name="ALICE")
        char_node = graph_ops.create_character(character)

        # Link them
        edge = graph_ops.link_scene_character(
            scene_node.id, char_node.id, {"dialogue_count": 5}
        )

        assert edge.type == EdgeType.FEATURES_CHARACTER
        assert edge.properties["dialogue_count"] == 5

    def test_link_scene_location(self, graph_ops, sample_script_node):
        """Test linking scene to location."""
        # Create scene and location
        scene = Scene(
            script_id=UUID(sample_script_node.id),
            heading="INT. PARK - DAY",
            script_order=1,
        )
        scene_node = graph_ops.create_scene(scene, sample_script_node.id)

        location = Location(interior=False, name="PARK", time="DAY")
        loc_node = graph_ops.create_location(location)

        # Link them
        edge = graph_ops.link_scene_location(scene_node.id, loc_node.id)

        assert edge.type == EdgeType.LOCATED_AT

    def test_get_script_scenes(self, graph_ops, sample_script_node):
        """Test retrieving script scenes in order."""
        # Create scenes with different orders
        scenes = []
        for i in [3, 1, 2]:  # Create out of order
            scene = Scene(
                script_id=UUID(sample_script_node.id),
                heading=f"INT. SCENE {i} - DAY",
                script_order=i,
                temporal_order=i * 2,  # Different temporal order
            )
            scenes.append(graph_ops.create_scene(scene, sample_script_node.id))

        # Get in script order
        script_ordered = graph_ops.get_script_scenes(
            sample_script_node.id, SceneOrderType.SCRIPT
        )
        assert len(script_ordered) == 3
        assert script_ordered[0].properties["script_order"] == 1
        assert script_ordered[1].properties["script_order"] == 2
        assert script_ordered[2].properties["script_order"] == 3

        # Get in temporal order
        temporal_ordered = graph_ops.get_script_scenes(
            sample_script_node.id, SceneOrderType.TEMPORAL
        )
        assert temporal_ordered[0].properties["temporal_order"] == 2
        assert temporal_ordered[1].properties["temporal_order"] == 4
        assert temporal_ordered[2].properties["temporal_order"] == 6

    def test_get_scene_characters(self, graph_ops, sample_script_node):
        """Test getting characters in a scene."""
        # Create scene and characters
        scene = Scene(
            script_id=UUID(sample_script_node.id),
            heading="INT. ROOM - DAY",
            script_order=1,
        )
        scene_node = graph_ops.create_scene(scene, sample_script_node.id)

        char1 = Character(name="ALICE")
        char2 = Character(name="BOB")
        char1_node = graph_ops.create_character(char1)
        char2_node = graph_ops.create_character(char2)

        # Link characters to scene
        graph_ops.link_scene_character(scene_node.id, char1_node.id)
        graph_ops.link_scene_character(scene_node.id, char2_node.id)

        # Get characters
        characters = graph_ops.get_scene_characters(scene_node.id)
        assert len(characters) == 2
        char_names = [c.properties["name"] for c in characters]
        assert "ALICE" in char_names
        assert "BOB" in char_names

    def test_find_character_interactions(self, graph_ops, sample_script_node):
        """Test finding character interactions."""
        # Create scenes and characters
        char1 = Character(name="ALICE")
        char2 = Character(name="BOB")
        char3 = Character(name="CHARLIE")

        char1_node = graph_ops.create_character(char1)
        char2_node = graph_ops.create_character(char2)
        char3_node = graph_ops.create_character(char3)

        # Create scenes where characters appear together
        for i in range(3):
            scene = Scene(
                script_id=UUID(sample_script_node.id),
                heading=f"INT. SCENE {i} - DAY",
                script_order=i,
            )
            scene_node = graph_ops.create_scene(scene, sample_script_node.id)

            if i < 2:  # Alice and Bob in first 2 scenes
                graph_ops.link_scene_character(scene_node.id, char1_node.id)
                graph_ops.link_scene_character(scene_node.id, char2_node.id)
            else:  # Bob and Charlie in last scene
                graph_ops.link_scene_character(scene_node.id, char2_node.id)
                graph_ops.link_scene_character(scene_node.id, char3_node.id)

        # Build interaction graph
        graph_ops.build_character_interactions(sample_script_node.id)

        # Check interactions
        edges = graph_ops.graph.get_edges(
            source_id=char1_node.id, edge_type=EdgeType.INTERACTS_WITH
        )
        assert len(edges) == 1
        assert edges[0].target_id == char2_node.id
        assert edges[0].properties.get("scene_count", 0) >= 2

    def test_update_scene_order(self, graph_ops, sample_script_node):
        """Test updating scene order."""
        # Create scenes
        scenes = []
        for i in range(3):
            scene = Scene(
                script_id=UUID(sample_script_node.id),
                heading=f"INT. SCENE {i} - DAY",
                script_order=i + 1,
            )
            scenes.append(graph_ops.create_scene(scene, sample_script_node.id))

        # Update middle scene order
        new_order = 10
        updated = graph_ops.update_scene_order(
            scenes[1].id, SceneOrderType.SCRIPT, new_order
        )

        assert updated.properties["script_order"] == new_order

        # Verify order is updated
        ordered_scenes = graph_ops.get_script_scenes(
            sample_script_node.id, SceneOrderType.SCRIPT
        )
        assert ordered_scenes[0].id == scenes[0].id  # First unchanged
        assert ordered_scenes[1].id == scenes[2].id  # Third moved up
        assert ordered_scenes[2].id == scenes[1].id  # Second moved to end

    def test_delete_scene_cascade(self, graph_ops, sample_script_node):
        """Test that deleting a scene removes all its relationships."""
        # Create scene with relationships
        scene = Scene(
            script_id=UUID(sample_script_node.id),
            heading="INT. ROOM - DAY",
            script_order=1,
        )
        scene_node = graph_ops.create_scene(scene, sample_script_node.id)

        character = Character(name="ALICE")
        char_node = graph_ops.create_character(character)

        location = Location(interior=True, name="ROOM", time="DAY")
        loc_node = graph_ops.create_location(location)

        # Create relationships
        graph_ops.link_scene_character(scene_node.id, char_node.id)
        graph_ops.link_scene_location(scene_node.id, loc_node.id)

        # Delete scene
        graph_ops.graph.delete_node(scene_node.id)

        # Verify relationships are gone
        char_edges = graph_ops.graph.get_edges(target_id=char_node.id)
        assert len(char_edges) == 0

        loc_edges = graph_ops.graph.get_edges(target_id=loc_node.id)
        assert len(loc_edges) == 0

    def test_error_handling(self, graph_ops):
        """Test error handling in graph operations."""
        # Try to create scene without script
        scene = Scene(
            script_id=uuid4(), heading="INT. ORPHAN SCENE - DAY", script_order=1
        )

        fake_script_id = str(uuid4())
        with pytest.raises(GraphQueryError):
            graph_ops.create_scene(scene, fake_script_id)

    @patch("scriptrag.database.graph.GraphDatabase.create_node")
    def test_database_error_propagation(self, mock_create, graph_ops):
        """Test that database errors are properly propagated."""
        mock_create.side_effect = sqlite3.DatabaseError("Database locked")

        script = Script(title="Test", author="Author")
        with pytest.raises(sqlite3.DatabaseError):
            graph_ops.create_script(script)
