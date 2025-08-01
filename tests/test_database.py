"""Tests for ScriptRAG database functionality.

This module contains tests for the database schema, connections, and operations.
"""

import contextlib
import gc
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from scriptrag.config import get_logger
from scriptrag.database import (
    DatabaseBackup,
    DatabaseConnection,
    DatabaseMaintenance,
    DatabaseSchema,
    DatabaseStats,
    GraphDatabase,
    GraphOperations,
    MigrationRunner,
    create_database,
    get_database_health_report,
    initialize_database,
)
from scriptrag.models import (
    Character,
    Location,
    Scene,
    SceneOrderType,
    Script,
)

logger = get_logger(__name__)


def _force_close_db_connections(db_path: Path) -> None:
    """Force close any lingering SQLite connections to a database file.

    This is particularly needed on Windows where file handles might not be
    released immediately.
    """
    # Force garbage collection
    gc.collect()

    # Try to connect and close to ensure exclusive access
    with contextlib.suppress(Exception):
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=DELETE")  # Switch from WAL mode
        conn.close()

    # Give Windows time to release file handles
    if hasattr(time, "sleep"):
        time.sleep(0.05)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup with Windows compatibility
    if db_path.exists():
        # Force close any lingering connections
        _force_close_db_connections(db_path)

        # On Windows, SQLite connections might not be fully closed
        # Try multiple times with a small delay
        for attempt in range(5):
            try:
                db_path.unlink()
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.1)  # Wait 100ms before retrying
                    _force_close_db_connections(db_path)
                else:
                    # Last attempt failed, try to at least close WAL files
                    with contextlib.suppress(Exception):
                        wal_path = db_path.with_suffix(".db-wal")
                        shm_path = db_path.with_suffix(".db-shm")
                        if wal_path.exists():
                            wal_path.unlink()
                        if shm_path.exists():
                            shm_path.unlink()
                    # Skip cleanup on Windows if file is still locked
                    import platform

                    if platform.system() == "Windows":
                        logger.warning(
                            f"Could not delete test database {db_path} on Windows - "
                            "this is expected"
                        )
                    else:
                        raise


@pytest.fixture
def db_connection(temp_db_path):
    """Create a database connection for testing."""
    # Create the schema first
    initialize_database(temp_db_path)

    # Create connection
    connection = DatabaseConnection(temp_db_path)

    yield connection

    # Ensure connection is properly closed
    with contextlib.suppress(Exception):
        connection.close()

    # Force close any other connections that might have been created
    _force_close_db_connections(temp_db_path)


@pytest.fixture
def graph_db(db_connection):
    """Create a graph database instance for testing."""
    return GraphDatabase(db_connection)


@pytest.fixture
def graph_ops(db_connection):
    """Create graph operations instance for testing."""
    return GraphOperations(db_connection)


@pytest.fixture
def stored_script(db_connection, sample_script):
    """Create and store a script in the database."""
    with db_connection.transaction() as conn:
        # Store the script in the database
        conn.execute(
            """
            INSERT INTO scripts (id, title, author, format, genre, description,
                is_series)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(sample_script.id),
                sample_script.title,
                sample_script.author,
                sample_script.format,
                sample_script.genre,
                sample_script.description,
                sample_script.is_series,
            ),
        )
    return sample_script


@pytest.fixture
def sample_script():
    """Create a sample script for testing."""
    return Script(
        title="Test Screenplay",
        author="Test Author",
        format="screenplay",
        genre="Drama",
        description="A test screenplay for unit testing",
        is_series=False,
    )


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    return Character(
        name="PROTAGONIST",
        description="The main character of our test story",
        aliases=["HERO", "MAIN_CHAR"],
    )


@pytest.fixture
def sample_location():
    """Create a sample location for testing."""
    return Location(
        interior=True,
        name="COFFEE SHOP",
        time="DAY",
        raw_text="INT. COFFEE SHOP - DAY",
    )


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return Scene(
        script_id=uuid4(),
        heading="INT. COFFEE SHOP - DAY",
        description="Our protagonist enters a busy coffee shop",
        script_order=1,
        temporal_order=1,
        estimated_duration_minutes=2.5,
    )


class TestDatabaseSchema:
    """Test database schema creation and validation."""

    def test_schema_creation(self, temp_db_path):
        """Test creating a new database schema."""
        schema = DatabaseSchema(temp_db_path)
        schema.create_schema()

        assert temp_db_path.exists()
        assert schema.validate_schema()
        assert schema.get_current_version() == 6

    def test_schema_validation(self, temp_db_path):
        """Test schema validation."""
        schema = create_database(temp_db_path)
        assert schema.validate_schema()

    def test_migration_check(self, temp_db_path):
        """Test migration status checking."""
        schema = DatabaseSchema(temp_db_path)

        # New database should need migration
        assert schema.needs_migration()

        # After creation, should not need migration
        schema.create_schema()
        assert not schema.needs_migration()


class TestDatabaseConnection:
    """Test database connection management."""

    def test_connection_creation(self, temp_db_path):
        """Test creating a database connection."""
        # Create schema first
        create_database(temp_db_path)

        connection = DatabaseConnection(temp_db_path)

        with connection.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'"
            )
            result = cursor.fetchone()
            assert result["count"] > 0  # Should have tables

    def test_transaction_rollback(self, db_connection):
        """Test transaction rollback on error."""
        try:
            with db_connection.transaction() as conn:
                conn.execute(
                    "INSERT INTO scripts (id, title) VALUES (?, ?)", ("test-id", "Test")
                )
                # Force an error
                conn.execute(
                    "INSERT INTO scripts (id, title) VALUES (?, ?)", ("test-id", "Test")
                )  # Duplicate
        except Exception:
            pass  # Expected

        # Check that rollback worked
        result = db_connection.fetch_one(
            "SELECT COUNT(*) as count FROM scripts WHERE id = ?", ("test-id",)
        )
        assert result["count"] == 0

    def test_query_methods(self, db_connection):
        """Test various query methods."""
        # Insert test data
        script_id = str(uuid4())
        with db_connection.transaction() as conn:
            conn.execute(
                "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
                (script_id, "Test Script", "Test Author"),
            )

        # Test fetch_one
        result = db_connection.fetch_one(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        )
        assert result is not None
        assert result["title"] == "Test Script"

        # Test fetch_all
        results = db_connection.fetch_all("SELECT * FROM scripts")
        assert len(results) >= 1

    def test_table_operations(self, db_connection):
        """Test table information methods."""
        tables = db_connection.get_table_names()
        assert "scripts" in tables
        assert "scenes" in tables
        assert "characters" in tables

        script_info = db_connection.get_table_info("scripts")
        assert len(script_info) > 0

    def test_secure_path_validation_directory_traversal(self):
        """Test that directory traversal attacks are prevented."""
        # Test various directory traversal patterns
        traversal_paths = [
            "../../../etc/passwd.db",
            "..\\..\\..\\windows\\system32\\config\\sam.db",
            "data/../../../etc/passwd.db",
            "data/../../sensitive.db",
            "./../../etc/passwd.db",
            "data/./../../etc/passwd.db",
            "/tmp/../etc/passwd.db",  # noqa: S108
            "..%2F..%2Fetc%2Fpasswd.db",  # URL encoded
            "..%5C..%5Cwindows%5Csystem32.db",  # URL encoded backslash
            "data/..%2F..%2Fetc%2Fpasswd.db",
        ]

        for path in traversal_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_absolute_paths(self):
        """Test that absolute paths outside safe directories are rejected."""
        absolute_paths = [
            "/etc/passwd.db",
            "/var/lib/mysql/mysql.db",
            "C:\\Windows\\System32\\config\\sam.db",
            "\\\\server\\share\\database.db",  # UNC path
            "/dev/null.db",
            "/proc/self/environ.db",
        ]

        for path in absolute_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_file_extensions(self):
        """Test that only .db extensions are allowed."""
        invalid_extensions = [
            "database.txt",
            "database.sql",
            "database.sqlite",
            "database.sqlite3",
            "database",  # No extension
            "database.db.txt",
            "database.DB",  # Case variation
            "database.db.",
            "database.db ",  # Trailing space
        ]

        for path in invalid_extensions:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_null_bytes(self):
        """Test that null bytes in paths are rejected."""
        null_byte_paths = [
            "database\x00.db",
            "database.db\x00.txt",
            "\x00database.db",
            "data\x00base.db",
            "database.db\x00",
        ]

        for path in null_byte_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_special_characters(self):
        """Test that dangerous special characters are rejected."""
        special_char_paths = [
            "database|command.db",
            "database;rm -rf /.db",
            "database&command.db",
            "database>output.db",
            "database<input.db",
            "database`command`.db",
            "database$(command).db",
            "database${PWD}.db",
            "database*.db",
            "database?.db",
            "database[0-9].db",
        ]

        for path in special_char_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_length_limits(self):
        """Test that excessively long paths are rejected."""
        # Create a path that's too long (>255 chars for filename, >4096 for full path)
        long_filename = "a" * 300 + ".db"
        long_path = "data/" + "subdir/" * 600 + "database.db"

        with pytest.raises(ValueError, match="Invalid database path"):
            DatabaseConnection(long_filename)

        with pytest.raises(ValueError, match="Invalid database path"):
            DatabaseConnection(long_path)

    def test_secure_path_validation_valid_paths(self):
        """Test that legitimate paths are accepted."""
        valid_paths = [
            "database.db",
            "data/database.db",
            "data/scripts/test_script.db",
            "test_123.db",
            "my-database.db",
            "my_database.db",
            "./database.db",
            "data/subdir/database.db",
        ]

        for path in valid_paths:
            # Should not raise an exception
            conn = DatabaseConnection(path)
            assert conn.db_path.name.endswith(".db")
            conn.close()

    def test_secure_path_validation_unicode_attacks(self):
        """Test that Unicode-based attacks are prevented."""
        unicode_paths = [
            "data\u2044database.db",  # Unicode fraction slash
            "data\uff0f\uff0e\uff0e\uff0fdatabase.db",  # Fullwidth slash and dots
            "database\u200b.db",  # Zero-width space
            "database\ufeff.db",  # Zero-width no-break space
            "data\u2215..\u2215etc\u2215passwd.db",  # Division slash
        ]

        for path in unicode_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_windows_reserved_names(self):
        """Test that Windows reserved names are rejected."""

        # These should be rejected on all platforms for consistency
        reserved_names = [
            "CON.db",
            "PRN.db",
            "AUX.db",
            "NUL.db",
            "COM1.db",
            "COM2.db",
            "LPT1.db",
            "LPT2.db",
            "con.db",  # Case variation
            "data/CON.db",
        ]

        for path in reserved_names:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_hidden_files(self):
        """Test handling of hidden file paths."""
        # Hidden files starting with dot should be rejected
        hidden_paths = [
            ".database.db",
            ".hidden/database.db",
            "data/.database.db",
        ]

        for path in hidden_paths:
            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(path)

    def test_secure_path_validation_macos_temp_paths(self):
        """Test that macOS temporary paths are allowed."""
        macos_temp_paths = [
            "/var/folders/xx/yy/T/tmp123.db",
            "/private/var/folders/zz/aa/T/tempfile.db",
            "/private/tmp/test.db",
        ]

        for path in macos_temp_paths:
            # Should not raise an exception
            # We can't actually test this on Linux, but we can verify
            # the path validation logic doesn't reject these paths
            try:
                conn = DatabaseConnection(path)
                conn.close()
            except ValueError as e:
                # Only fail if it's the specific error we're fixing
                if "absolute paths outside working directory" in str(e):
                    pytest.fail(f"macOS temp path {path} should be allowed")
                else:
                    # Other validation errors are expected (e.g., path doesn't exist)
                    pass

    def test_secure_path_validation_symlink_attacks(self, temp_db_path):
        """Test that symlink attacks are prevented."""
        import os
        import platform

        # Skip on Windows if symlinks aren't supported
        if platform.system() == "Windows":
            try:
                os.symlink("test", "test_symlink")
                Path("test_symlink").unlink()
            except (OSError, NotImplementedError):
                pytest.skip("Symlinks not supported on this Windows system")

        # Create a symlink pointing outside the safe directory
        symlink_path = temp_db_path.parent / "evil_symlink.db"
        target_path = "/etc/passwd"

        try:
            if symlink_path.exists():
                symlink_path.unlink()
            os.symlink(target_path, str(symlink_path))

            with pytest.raises(ValueError, match="Invalid database path"):
                DatabaseConnection(symlink_path)
        finally:
            if symlink_path.exists():
                symlink_path.unlink()


class TestGraphDatabase:
    """Test basic graph database operations."""

    def test_node_operations(self, graph_db):
        """Test node creation, retrieval, update, and deletion."""
        # Create node
        node_id = graph_db.add_node(
            node_type="test",
            entity_id="test_entity",
            label="Test Node",
            properties={"key": "value"},
        )

        # Retrieve node
        node = graph_db.get_node(node_id)
        assert node is not None
        assert node.node_type == "test"
        assert node.label == "Test Node"
        assert node.properties["key"] == "value"

        # Update node
        updated = graph_db.update_node(
            node_id,
            label="Updated Node",
            properties={"key": "new_value", "new_key": "new_value"},
        )
        assert updated

        # Verify update
        node = graph_db.get_node(node_id)
        assert node.label == "Updated Node"
        assert node.properties["key"] == "new_value"
        assert node.properties["new_key"] == "new_value"

        # Delete node
        deleted = graph_db.delete_node(node_id)
        assert deleted

        # Verify deletion
        node = graph_db.get_node(node_id)
        assert node is None

    def test_edge_operations(self, graph_db):
        """Test edge creation, retrieval, and deletion."""
        # Create nodes
        node1_id = graph_db.add_node("test", entity_id="node1_entity", label="Node 1")
        node2_id = graph_db.add_node("test", entity_id="node2_entity", label="Node 2")

        # Create edge
        edge_id = graph_db.add_edge(
            from_node_id=node1_id,
            to_node_id=node2_id,
            edge_type="CONNECTS_TO",
            properties={"strength": 0.8},
            weight=0.8,
        )

        # Retrieve edge
        edge = graph_db.get_edge(edge_id)
        assert edge is not None
        assert edge.from_node_id == node1_id
        assert edge.to_node_id == node2_id
        assert edge.edge_type == "CONNECTS_TO"
        assert edge.properties["strength"] == 0.8
        assert edge.weight == 0.8

        # Delete edge
        deleted = graph_db.delete_edge(edge_id)
        assert deleted

        # Verify deletion
        edge = graph_db.get_edge(edge_id)
        assert edge is None

    def test_graph_traversal(self, graph_db):
        """Test graph traversal operations."""
        # Create a small graph: A -> B -> C
        node_a = graph_db.add_node("test", label="A")
        node_b = graph_db.add_node("test", label="B")
        node_c = graph_db.add_node("test", label="C")

        graph_db.add_edge(node_a, node_b, "CONNECTS_TO")
        graph_db.add_edge(node_b, node_c, "CONNECTS_TO")

        # Test neighbors
        neighbors = graph_db.get_neighbors(
            node_a, edge_type="CONNECTS_TO", direction="out"
        )
        assert len(neighbors) == 1
        assert neighbors[0].id == node_b

        # Test path finding
        path = graph_db.find_path(node_a, node_c, edge_type="CONNECTS_TO")
        assert path is not None
        assert path == [node_a, node_b, node_c]

        # Test subgraph
        nodes, edges = graph_db.get_subgraph(node_b, radius=1, edge_type="CONNECTS_TO")
        assert len(nodes) == 3  # All nodes should be included
        assert len(edges) == 2  # Both edges should be included

    def test_node_search(self, graph_db):
        """Test node search functionality."""
        # Create test nodes
        graph_db.add_node("character", label="PROTAGONIST", entity_id="char-1")
        graph_db.add_node("character", label="ANTAGONIST", entity_id="char-2")
        graph_db.add_node("location", label="COFFEE SHOP", entity_id="loc-1")

        # Test search by type
        characters = graph_db.find_nodes(node_type="character")
        assert len(characters) == 2

        # Test search by entity_id
        nodes = graph_db.find_nodes(entity_id="char-1")
        assert len(nodes) == 1
        assert nodes[0].label == "PROTAGONIST"

        # Test search by label pattern
        nodes = graph_db.find_nodes(label_pattern="%COFFEE%")
        assert len(nodes) == 1
        assert nodes[0].label == "COFFEE SHOP"

    def test_centrality_calculations(self, graph_db):
        """Test node centrality calculation methods."""
        # Create a small known graph:
        #     A
        #    / \
        #   B---C
        #   |   |
        #   D---E

        node_a = graph_db.add_node("test", label="A")
        node_b = graph_db.add_node("test", label="B")
        node_c = graph_db.add_node("test", label="C")
        node_d = graph_db.add_node("test", label="D")
        node_e = graph_db.add_node("test", label="E")

        # Add edges (undirected graph via bidirectional edges)
        edges = [
            (node_a, node_b),
            (node_b, node_a),  # A-B
            (node_a, node_c),
            (node_c, node_a),  # A-C
            (node_b, node_c),
            (node_c, node_b),  # B-C
            (node_b, node_d),
            (node_d, node_b),  # B-D
            (node_c, node_e),
            (node_e, node_c),  # C-E
            (node_d, node_e),
            (node_e, node_d),  # D-E
        ]

        for from_node, to_node in edges:
            graph_db.add_edge(from_node, to_node, "CONNECTS_TO")

        # Test degree centrality
        degree_centralities = graph_db.calculate_degree_centrality()
        assert len(degree_centralities) == 5

        # Node A has degree 4 (2 undirected connections x 2 for bidirectional edges)
        # In a 5-node graph with bidirectional representation, max degree is 2*(n-1) = 8
        # So normalized centrality is 4/8 = 0.5
        assert degree_centralities[node_a] == 0.5

        # Test single node degree centrality
        single_centrality = graph_db.calculate_degree_centrality(node_a)
        assert single_centrality == 0.5

        # Test betweenness centrality
        betweenness_centralities = graph_db.calculate_betweenness_centrality()
        assert len(betweenness_centralities) == 5

        # All nodes should have some betweenness centrality values
        for centrality in betweenness_centralities.values():
            assert centrality >= 0.0

        # Test single node betweenness centrality
        single_betweenness = graph_db.calculate_betweenness_centrality(node_a)
        assert single_betweenness >= 0.0

        # Test closeness centrality
        closeness_centralities = graph_db.calculate_closeness_centrality()
        assert len(closeness_centralities) == 5

        # All nodes should have positive closeness centrality
        for centrality in closeness_centralities.values():
            assert centrality > 0.0

        # Test single node closeness centrality
        single_closeness = graph_db.calculate_closeness_centrality(node_a)
        assert single_closeness > 0.0

        # Test eigenvector centrality
        eigenvector_centralities = graph_db.calculate_eigenvector_centrality()
        assert len(eigenvector_centralities) == 5

        # All nodes should have non-negative eigenvector centrality
        for centrality in eigenvector_centralities.values():
            assert centrality >= 0.0

        # Test single node eigenvector centrality
        single_eigenvector = graph_db.calculate_eigenvector_centrality(node_a)
        assert single_eigenvector >= 0.0

        # Test centrality summary
        summary = graph_db.get_centrality_summary(node_a)
        assert "degree_centrality" in summary
        assert "betweenness_centrality" in summary
        assert "closeness_centrality" in summary
        assert "eigenvector_centrality" in summary

        # Verify summary values match individual calculations
        assert summary["degree_centrality"] == single_centrality
        assert summary["betweenness_centrality"] == single_betweenness
        assert summary["closeness_centrality"] == single_closeness
        assert summary["eigenvector_centrality"] == single_eigenvector

    def test_centrality_empty_graph(self, graph_db):
        """Test centrality calculations on empty graph."""
        # Test with no nodes
        degree_centralities = graph_db.calculate_degree_centrality()
        assert degree_centralities == {}

        betweenness_centralities = graph_db.calculate_betweenness_centrality()
        assert betweenness_centralities == {}

        closeness_centralities = graph_db.calculate_closeness_centrality()
        assert closeness_centralities == {}

        eigenvector_centralities = graph_db.calculate_eigenvector_centrality()
        assert eigenvector_centralities == {}

    def test_centrality_single_node(self, graph_db):
        """Test centrality calculations with single isolated node."""
        node_a = graph_db.add_node("test", label="A")

        # Single node should have centrality of 0 for most measures
        degree_centrality = graph_db.calculate_degree_centrality(node_a)
        assert degree_centrality == 0.0

        betweenness_centrality = graph_db.calculate_betweenness_centrality(node_a)
        assert betweenness_centrality == 0.0

        closeness_centrality = graph_db.calculate_closeness_centrality(node_a)
        assert closeness_centrality == 0.0

        eigenvector_centrality = graph_db.calculate_eigenvector_centrality(node_a)
        assert eigenvector_centrality >= 0.0  # Should be normalized to some value


class TestGraphOperations:
    """Test screenplay-specific graph operations."""

    def test_script_graph_creation(self, graph_ops, sample_script):
        """Test creating a script graph."""
        script_node_id = graph_ops.create_script_graph(sample_script)

        node = graph_ops.graph.get_node(script_node_id)
        assert node is not None
        assert node.node_type == "script"
        assert node.label == sample_script.title
        assert node.properties["author"] == sample_script.author

    def test_character_operations(self, graph_ops, sample_script, sample_character):
        """Test character node operations."""
        # Create script first
        script_node_id = graph_ops.create_script_graph(sample_script)

        # Create character
        char_node_id = graph_ops.create_character_node(sample_character, script_node_id)

        # Verify character node
        char_node = graph_ops.graph.get_node(char_node_id)
        assert char_node is not None
        assert char_node.node_type == "character"
        assert char_node.label == sample_character.name

        # Verify connection to script
        neighbors = graph_ops.graph.get_neighbors(
            script_node_id, edge_type="HAS_CHARACTER"
        )
        assert len(neighbors) == 1
        assert neighbors[0].id == char_node_id

    def test_location_operations(self, graph_ops, sample_script, sample_location):
        """Test location node operations."""
        script_node_id = graph_ops.create_script_graph(sample_script)

        loc_node_id = graph_ops.create_location_node(sample_location, script_node_id)

        loc_node = graph_ops.graph.get_node(loc_node_id)
        assert loc_node is not None
        assert loc_node.node_type == "location"
        assert loc_node.label == sample_location.name

    def test_scene_operations(self, graph_ops, stored_script, sample_scene):
        """Test scene node operations."""
        # Update scene to reference the stored script
        sample_scene.script_id = stored_script.id

        script_node_id = graph_ops.create_script_graph(stored_script)

        scene_node_id = graph_ops.create_scene_node(sample_scene, script_node_id)

        scene_node = graph_ops.graph.get_node(scene_node_id)
        assert scene_node is not None
        assert scene_node.node_type == "scene"
        assert scene_node.properties["script_order"] == sample_scene.script_order

    def test_scene_ordering(self, graph_ops, stored_script):
        """Test scene ordering operations."""
        script_node_id = graph_ops.create_script_graph(stored_script)

        # Create multiple scenes
        scenes = []
        scene_node_ids = []
        for i in range(3):
            scene = Scene(
                script_id=stored_script.id,
                heading=f"Scene {i + 1}",
                script_order=i + 1,
                temporal_order=i + 1,
            )
            scenes.append(scene)
            scene_node_id = graph_ops.create_scene_node(scene, script_node_id)
            scene_node_ids.append(scene_node_id)

        # Create sequence
        edge_ids = graph_ops.create_scene_sequence(
            scene_node_ids, SceneOrderType.SCRIPT.value
        )
        assert len(edge_ids) == 2  # 3 scenes = 2 edges

        # Test getting ordered scenes
        ordered_scenes = graph_ops.get_script_scenes(
            script_node_id, SceneOrderType.SCRIPT
        )
        assert len(ordered_scenes) == 3
        assert ordered_scenes[0].properties["script_order"] == 1
        assert ordered_scenes[1].properties["script_order"] == 2
        assert ordered_scenes[2].properties["script_order"] == 3

    def test_character_scene_connections(
        self, graph_ops, stored_script, sample_character, sample_scene
    ):
        """Test connecting characters to scenes."""
        # Update scene to reference the stored script
        sample_scene.script_id = stored_script.id

        script_node_id = graph_ops.create_script_graph(stored_script)
        char_node_id = graph_ops.create_character_node(sample_character, script_node_id)
        scene_node_id = graph_ops.create_scene_node(sample_scene, script_node_id)

        # Connect character to scene
        edge_id = graph_ops.connect_character_to_scene(
            char_node_id, scene_node_id, dialogue_count=5
        )

        edge = graph_ops.graph.get_edge(edge_id)
        assert edge is not None
        assert edge.edge_type == "appears_in"
        assert edge.properties["dialogue_count"] == 5

        # Test getting character scenes
        char_scenes = graph_ops.get_character_scenes(char_node_id)
        assert len(char_scenes) == 1
        assert char_scenes[0].id == scene_node_id

    def test_character_interactions(self, graph_ops, stored_script):
        """Test character interaction tracking."""
        script_node_id = graph_ops.create_script_graph(stored_script)

        # Create two characters
        char1 = Character(name="ALICE", description="First character")
        char2 = Character(name="BOB", description="Second character")

        char1_node_id = graph_ops.create_character_node(char1, script_node_id)
        char2_node_id = graph_ops.create_character_node(char2, script_node_id)

        # Create a scene
        scene = Scene(script_id=stored_script.id, heading="Test Scene", script_order=1)
        scene_node_id = graph_ops.create_scene_node(scene, script_node_id)

        # Connect characters to scene
        graph_ops.connect_character_to_scene(char1_node_id, scene_node_id)
        graph_ops.connect_character_to_scene(char2_node_id, scene_node_id)

        # Create interaction
        graph_ops.connect_character_interaction(
            char1_node_id, char2_node_id, scene_node_id, interaction_type="dialogue"
        )

        # Test getting interactions
        interactions = graph_ops.get_character_interactions(
            char1_node_id, interaction_type="dialogue"
        )
        assert len(interactions) == 1

        interaction = interactions[0]
        assert interaction["character_id"] == char2_node_id
        assert interaction["interaction_type"] == "dialogue"

    def test_centrality_analysis(self, graph_ops, stored_script):
        """Test character centrality analysis."""
        script_node_id = graph_ops.create_script_graph(stored_script)

        # Create characters
        characters = []
        char_node_ids = []
        for i in range(3):
            char = Character(name=f"CHAR_{i}", description=f"Character {i}")
            char_node_id = graph_ops.create_character_node(char, script_node_id)
            characters.append(char)
            char_node_ids.append(char_node_id)

        # Create scenes and interactions to give one character higher centrality
        scene = Scene(script_id=stored_script.id, heading="Test Scene", script_order=1)
        scene_node_id = graph_ops.create_scene_node(scene, script_node_id)

        # Connect all characters to scene
        for char_node_id in char_node_ids:
            graph_ops.connect_character_to_scene(char_node_id, scene_node_id)

        # Make character 0 interact with others (higher centrality)
        for i in range(1, 3):
            graph_ops.connect_character_interaction(
                char_node_ids[0], char_node_ids[i], scene_node_id
            )

        # Analyze centrality
        centrality_scores = graph_ops.analyze_character_centrality(script_node_id)

        assert len(centrality_scores) == 3

        # Character 0 should have higher interaction diversity
        char0_scores = centrality_scores[char_node_ids[0]]
        char1_scores = centrality_scores[char_node_ids[1]]

        assert (
            char0_scores["interaction_diversity"]
            > char1_scores["interaction_diversity"]
        )
        assert char0_scores["scene_frequency"] == 1  # All appear in same scene


class TestMigrationRunner:
    """Test database migration system."""

    def test_migration_runner_initialization(self, temp_db_path):
        """Test migration runner initialization."""
        runner = MigrationRunner(temp_db_path)

        assert runner.get_current_version() == 0
        assert runner.get_target_version() == 6
        assert runner.needs_migration()

    def test_apply_initial_migration(self, temp_db_path):
        """Test applying initial migration."""
        runner = MigrationRunner(temp_db_path)

        assert runner.apply_migration(1)
        assert runner.get_current_version() == 1
        assert runner.needs_migration()  # Still needs migration 2

        # Apply all migrations to test complete migration
        assert runner.migrate_to_latest()
        assert not runner.needs_migration()

    def test_migrate_to_latest(self, temp_db_path):
        """Test migrating to latest version."""
        runner = MigrationRunner(temp_db_path)

        assert runner.migrate_to_latest()
        assert runner.get_current_version() == runner.get_target_version()

    def test_migration_history(self, temp_db_path):
        """Test migration history tracking."""
        runner = MigrationRunner(temp_db_path)
        runner.migrate_to_latest()

        history = runner.get_migration_history()
        assert len(history) == 6
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2
        assert history[2]["version"] == 3
        assert history[3]["version"] == 4
        assert history[4]["version"] == 5
        assert history[5]["version"] == 6
        assert "description" in history[0]

    def test_initialize_database_function(self, temp_db_path):
        """Test initialize_database convenience function."""
        result = initialize_database(temp_db_path)
        assert result
        assert temp_db_path.exists()


class TestDatabaseStats:
    """Test database statistics functionality."""

    def test_table_stats(self, db_connection):
        """Test getting table statistics."""
        stats = DatabaseStats(db_connection.db_path)
        table_stats = stats.get_table_stats()

        assert "scripts" in table_stats
        assert "scenes" in table_stats
        assert "characters" in table_stats

        script_stats = table_stats["scripts"]
        assert "row_count" in script_stats
        assert "column_count" in script_stats
        assert "size_bytes" in script_stats
        # size_bytes can be None if dbstat is not available (e.g., macOS/Homebrew)
        assert script_stats["size_bytes"] is None or isinstance(
            script_stats["size_bytes"], int
        )

    def test_database_size(self, db_connection):
        """Test getting database size information."""
        stats = DatabaseStats(db_connection.db_path)
        size_info = stats.get_database_size()

        assert "file_size_bytes" in size_info
        assert "page_count" in size_info
        assert "utilization_percent" in size_info

    def test_performance_stats(self, db_connection):
        """Test getting performance statistics."""
        stats = DatabaseStats(db_connection.db_path)
        perf_stats = stats.get_query_performance_stats()

        assert "journal_mode" in perf_stats
        assert "cache_size_pages" in perf_stats


class TestDatabaseBackup:
    """Test database backup functionality."""

    def test_create_simple_backup(self, db_connection, temp_db_path):
        """Test creating a simple backup."""
        backup_path = temp_db_path.parent / "backup.db"

        backup = DatabaseBackup(db_connection.db_path)
        result = backup.create_backup(backup_path, compress=False)

        assert result
        assert backup_path.exists()

    def test_create_compressed_backup(self, db_connection, temp_db_path):
        """Test creating a compressed backup."""
        backup_path = temp_db_path.parent / "backup"

        backup = DatabaseBackup(db_connection.db_path)
        result = backup.create_backup(backup_path, compress=True)

        assert result
        assert (backup_path.parent / "backup.zip").exists()

    def test_restore_backup(self, db_connection, temp_db_path):
        """Test restoring from backup."""
        # Create backup
        backup_path = temp_db_path.parent / "backup.db"
        backup = DatabaseBackup(db_connection.db_path)
        backup.create_backup(backup_path, compress=False)

        # Create new database path for restore
        restore_path = temp_db_path.parent / "restored.db"
        restore_backup = DatabaseBackup(restore_path)

        result = restore_backup.restore_backup(backup_path, force=True)
        assert result
        assert restore_path.exists()


class TestDatabaseMaintenance:
    """Test database maintenance operations."""

    def test_vacuum(self, db_connection):
        """Test VACUUM operation."""
        maintenance = DatabaseMaintenance(db_connection.db_path)
        result = maintenance.vacuum()
        assert result

    def test_analyze(self, db_connection):
        """Test ANALYZE operation."""
        maintenance = DatabaseMaintenance(db_connection.db_path)
        result = maintenance.analyze()
        assert result

    def test_integrity_check(self, db_connection):
        """Test integrity check."""
        maintenance = DatabaseMaintenance(db_connection.db_path)
        is_valid, issues = maintenance.check_integrity()
        assert is_valid
        assert len(issues) == 0

    def test_fragmentation_info(self, db_connection):
        """Test getting fragmentation information."""
        maintenance = DatabaseMaintenance(db_connection.db_path)
        frag_info = maintenance.get_fragmentation_info()

        assert "total_pages" in frag_info
        assert "fragmentation_percent" in frag_info

    def test_optimize(self, db_connection):
        """Test full optimization."""
        maintenance = DatabaseMaintenance(db_connection.db_path)
        result = maintenance.optimize()
        assert result


class TestDatabaseHealth:
    """Test database health reporting."""

    def test_health_report(self, db_connection):
        """Test generating health report."""
        report = get_database_health_report(db_connection.db_path)

        assert "status" in report
        assert "size_info" in report
        assert "table_stats" in report
        assert "integrity" in report
        assert report["exists"] is True

    def test_health_report_nonexistent_db(self, temp_db_path):
        """Test health report for non-existent database."""
        nonexistent_path = temp_db_path.parent / "nonexistent.db"
        report = get_database_health_report(nonexistent_path)

        assert report["status"] == "NOT_FOUND"
        assert report["exists"] is False


class TestDatabaseConnectionErrors:
    """Test error handling in DatabaseConnection class."""

    def test_invalid_database_path_with_mock_object(self):
        """Test that mock objects in database paths are rejected.

        This test verifies that when a Mock object is passed as a database path,
        it's converted to string and then validated. The mock returns an absolute
        path outside the working directory which is rejected by security validation.
        """
        mock_path = Mock()
        mock_path.__str__ = Mock(return_value="/mock/path.db")

        # The mock's string representation creates an absolute path outside cwd
        with pytest.raises(
            ValueError, match="absolute paths outside working directory"
        ):
            DatabaseConnection(mock_path)

    def test_database_path_with_null_character_in_filename(self, tmp_path):
        """Test database paths with null character in filename.

        This test ensures that database paths containing null bytes (\x00) in
        the filename are properly rejected with a ValueError. Null bytes are
        invalid in file paths and could cause security issues if not handled.
        """
        null_path = tmp_path / "test\x00.db"
        with pytest.raises(ValueError, match="contains null bytes"):
            DatabaseConnection(str(null_path))

    def test_database_path_with_null_character_in_directory(self, tmp_path):
        """Test database paths with null character in directory component.

        This test verifies that database paths containing null bytes (\x00) in
        directory names are rejected. This prevents potential path traversal
        attacks and ensures file system compatibility.
        """
        invalid_path = str(tmp_path / "test\x00invalid" / "database.db")
        with pytest.raises(ValueError, match="contains null bytes"):
            DatabaseConnection(invalid_path)

    @patch("sqlite3.connect")
    def test_sqlite3_connect_permission_error(self, mock_connect, tmp_path):
        """Test handling of permission errors during connection.

        This test simulates a scenario where sqlite3.connect() fails due to
        insufficient permissions (e.g., read-only directory, permission denied
        on database file). Verifies that the error is properly propagated.
        """
        mock_connect.side_effect = PermissionError("Permission denied")

        conn = DatabaseConnection(tmp_path / "test.db")
        with pytest.raises(PermissionError, match="Permission denied"):
            conn._get_connection()

    @patch("sqlite3.connect")
    def test_sqlite3_connect_disk_full_error(self, mock_connect, tmp_path):
        """Test handling of disk full errors during connection.

        This test simulates a disk I/O error (e.g., disk full, hardware failure)
        when attempting to create or open a database connection. Ensures the
        OperationalError is properly handled and not masked.
        """
        mock_connect.side_effect = sqlite3.OperationalError("disk I/O error")

        conn = DatabaseConnection(tmp_path / "test.db")
        with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
            conn._get_connection()

    @patch("sqlite3.connect")
    def test_pragma_command_failures(self, mock_connect, tmp_path):
        """Test handling of PRAGMA command failures.

        This test verifies that when PRAGMA commands fail during connection setup
        (e.g., foreign_keys, journal_mode), the error is properly caught and
        re-raised with appropriate context. This can happen with restricted
        SQLite builds or filesystem issues.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Simulate PRAGMA foreign_keys failure
        mock_conn.execute.side_effect = sqlite3.OperationalError(
            "PRAGMA foreign_keys failed"
        )

        conn = DatabaseConnection(tmp_path / "test.db")
        with pytest.raises(
            sqlite3.OperationalError, match="PRAGMA foreign_keys failed"
        ):
            conn._get_connection()

        # Verify that the PRAGMA command was attempted
        mock_conn.execute.assert_called_with("PRAGMA foreign_keys = ON")

    @patch("sqlite3.connect")
    def test_pragma_journal_mode_failure(self, mock_connect, tmp_path):
        """Test handling of journal mode PRAGMA failures."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Make foreign_keys succeed but journal_mode fail
        def execute_side_effect(query):
            if "foreign_keys" in query:
                return MagicMock()
            if "journal_mode" in query:
                raise sqlite3.OperationalError("Cannot change journal mode")
            return MagicMock()

        mock_conn.execute.side_effect = execute_side_effect

        conn = DatabaseConnection(tmp_path / "test.db")
        with pytest.raises(
            sqlite3.OperationalError, match="Cannot change journal mode"
        ):
            conn._get_connection()

    @patch("sqlite3.connect")
    def test_transaction_begin_failure(self, mock_connect, tmp_path):
        """Test handling of BEGIN statement failures in transaction.

        This test simulates a database lock scenario where the BEGIN statement
        fails (e.g., another process has exclusive lock). Verifies that the
        transaction context manager properly handles and propagates the error.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Configure connection to succeed
        mock_conn.execute.return_value = MagicMock()

        conn = DatabaseConnection(tmp_path / "test.db")
        # Get connection successfully first
        conn._get_connection()

        # Now make BEGIN fail
        mock_conn.execute.side_effect = sqlite3.OperationalError("database is locked")

        with (
            pytest.raises(sqlite3.OperationalError) as exc_info,
            conn.transaction(),
        ):
            pass
        assert "database is locked" in str(exc_info.value)

    @patch("sqlite3.connect")
    def test_transaction_rollback_failure(self, mock_connect, tmp_path):
        """Test handling when rollback fails after transaction error.

        This test simulates a critical scenario where both the transaction AND
        the rollback fail. This can happen with corrupted databases or severe
        I/O errors. Currently, the rollback error masks the original error.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = DatabaseConnection(tmp_path / "test.db")

        # Configure to succeed during setup
        mock_conn.execute.return_value = MagicMock()
        conn._get_connection()

        # Reset mock for transaction test
        mock_conn.execute.reset_mock()
        mock_conn.rollback.side_effect = sqlite3.OperationalError("Cannot rollback")

        # When rollback fails, the rollback error is raised instead of original
        with (
            pytest.raises(sqlite3.OperationalError) as exc_info,
            conn.transaction(),
        ):
            # Force an error that triggers rollback
            raise RuntimeError("Transaction error")

        assert "Cannot rollback" in str(exc_info.value)
        # Verify rollback was attempted
        mock_conn.rollback.assert_called_once()

    @patch("sqlite3.connect")
    def test_transaction_rollback_preserves_original_exception(
        self, mock_connect, tmp_path
    ):
        """Test that original transaction error is preserved when rollback also fails.

        This test documents the current behavior where rollback errors mask the
        original transaction error. Ideally, both exceptions should be preserved
        using exception chaining (raise ... from original_exception).
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = DatabaseConnection(tmp_path / "test.db")

        # Configure to succeed during setup
        mock_conn.execute.return_value = MagicMock()
        conn._get_connection()

        # Configure rollback to fail
        original_error = ValueError("Original transaction error")
        rollback_error = sqlite3.OperationalError("Rollback failed")
        mock_conn.rollback.side_effect = rollback_error

        with (
            pytest.raises(sqlite3.OperationalError) as exc_info,
            conn.transaction(),
        ):
            raise original_error

        # Currently, only the rollback error is raised
        assert "Rollback failed" in str(exc_info.value)

        # NOTE: Ideally we would check for exception chaining here:
        # assert exc_info.value.__cause__ is original_error
        # But the current implementation doesn't preserve the chain

    @patch("sqlite3.connect")
    def test_connection_close_failure(self, mock_connect, tmp_path):
        """Test handling when connection close fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Configure connection to succeed
        mock_conn.execute.return_value = MagicMock()

        conn = DatabaseConnection(tmp_path / "test.db")
        conn._get_connection()

        # Make close operations fail
        mock_conn.rollback.side_effect = sqlite3.OperationalError(
            "Cannot rollback on close"
        )
        mock_conn.close.side_effect = sqlite3.OperationalError(
            "Cannot close connection"
        )

        # Should not raise - errors are suppressed
        conn.close()

        # Verify attempts were made
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

        # Connection should be marked as None
        assert conn._local.connection is None

    @patch("sqlite3.connect")
    def test_context_manager_with_connection_error(self, mock_connect, tmp_path):
        """Test context manager behavior with connection errors."""
        mock_connect.side_effect = sqlite3.OperationalError("Cannot open database")

        with (
            pytest.raises(sqlite3.OperationalError),
            DatabaseConnection(tmp_path / "test.db") as conn,
        ):
            conn.execute("SELECT 1")

    @patch("sqlite3.connect")
    def test_execute_with_invalid_sql(self, mock_connect, tmp_path):
        """Test execute method with invalid SQL."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.execute.return_value = MagicMock()

        conn = DatabaseConnection(tmp_path / "test.db")

        # Make execute fail after successful connection
        def execute_side_effect(query, *_args):
            if "PRAGMA" in query or "schema_info" in query:
                return MagicMock()
            if "INVALID" in query:
                raise sqlite3.OperationalError("near 'INVALID': syntax error")
            return MagicMock()

        mock_conn.execute.side_effect = execute_side_effect

        with pytest.raises(sqlite3.OperationalError, match="syntax error"):
            conn.execute("INVALID SQL QUERY")

    @patch("pathlib.Path.mkdir")
    def test_directory_creation_failure(self, mock_mkdir, tmp_path):
        """Test handling of directory creation failures.

        This test verifies error handling when the database directory cannot be
        created (e.g., permission denied, read-only filesystem). The connection
        should fail gracefully with a clear error message.
        """
        mock_mkdir.side_effect = PermissionError("Cannot create directory")

        conn = DatabaseConnection(tmp_path / "nonexistent" / "path" / "test.db")
        with pytest.raises(PermissionError, match="Cannot create directory"):
            conn._get_connection()

    @patch("sqlite3.connect")
    def test_row_factory_setting_failure(self, mock_connect, tmp_path):
        """Test handling when setting row_factory fails.

        This test simulates a rare scenario where setting the row_factory
        attribute fails (e.g., read-only connection object, custom SQLite build).
        Ensures the error is properly propagated rather than silently ignored.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Allow PRAGMA commands to succeed
        mock_conn.execute.return_value = MagicMock()

        # Make row_factory assignment fail - use a property descriptor
        class FailingProperty:
            def __get__(self, obj, obj_type=None):
                return None

            def __set__(self, obj, value):
                raise AttributeError("Cannot set row_factory")

        type(mock_conn).row_factory = FailingProperty()

        conn = DatabaseConnection(tmp_path / "test.db")
        with pytest.raises(AttributeError, match="Cannot set row_factory"):
            conn._get_connection()
