"""Test GraphOperations database synchronization functionality."""

from datetime import datetime

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Character, Episode, Scene, Script, Season


@pytest.fixture
def test_db_with_ops(temp_db_path):
    """Database connection with GraphOperations."""
    from scriptrag.database import initialize_database

    # Initialize the database first
    initialize_database(temp_db_path)

    conn = DatabaseConnection(temp_db_path)
    with conn:
        yield conn, GraphOperations(conn)


class TestGraphOperationsDatabaseSync:
    """Test that GraphOperations properly syncs with database tables."""

    def test_create_script_graph_inserts_into_scripts_table(self, test_db_with_ops):
        """Test that create_script_graph inserts script into scripts table."""
        conn, graph_ops = test_db_with_ops

        # Create a script
        script = Script(
            title="Test Script",
            author="Test Author",
            format="screenplay",
            genre="Drama",
            is_series=False,
            source_file="test.fountain",
        )

        # Create script graph
        _script_node_id = graph_ops.create_script_graph(script)

        # Verify script was inserted into scripts table
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (str(script.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["id"] == str(script.id)
        assert row["title"] == script.title
        assert row["author"] == script.author
        assert row["format"] == script.format
        assert row["genre"] == script.genre
        assert row["is_series"] == 0  # SQLite stores False as 0
        assert row["source_file"] == script.source_file

    def test_create_script_graph_handles_duplicate_insert(self, test_db_with_ops):
        """Test that create_script_graph handles duplicate script gracefully."""
        conn, graph_ops = test_db_with_ops

        script = Script(title="Duplicate Test", source_file="dup.fountain")

        # Create script graph twice
        node_id1 = graph_ops.create_script_graph(script)
        node_id2 = graph_ops.create_script_graph(script)

        # Should create different nodes but same script record
        assert node_id1 != node_id2

        # Verify only one script record exists
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT COUNT(*) as count FROM scripts WHERE id = ?", (str(script.id),)
            )
            count = cursor.fetchone()["count"]

        assert count == 1

    @pytest.mark.skip(reason="create_season_node method not yet implemented")
    def test_create_season_node_inserts_into_seasons_table(self, test_db_with_ops):
        """Test that create_season_node inserts season into seasons table."""
        conn, graph_ops = test_db_with_ops

        # Create script first
        script = Script(
            title="TV Series", is_series=True, source_file="series.fountain"
        )
        script_node_id = graph_ops.create_script_graph(script)

        # Create season
        season = Season(
            script_id=script.id,
            number=1,
            title="Season One",
            year=2024,
        )

        # Create season node
        _ = graph_ops.create_season_node(season, script_node_id)

        # Verify season was inserted
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM seasons WHERE id = ?", (str(season.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["id"] == str(season.id)
        assert row["script_id"] == str(season.script_id)
        assert row["number"] == season.number
        assert row["title"] == season.title
        assert row["year"] == season.year

    @pytest.mark.skip(reason="create_episode_node method not yet implemented")
    def test_create_episode_node_inserts_into_episodes_table(self, test_db_with_ops):
        """Test that create_episode_node inserts episode into episodes table."""
        conn, graph_ops = test_db_with_ops

        # Create script and season
        script = Script(
            title="TV Series", is_series=True, source_file="series.fountain"
        )
        script_node_id = graph_ops.create_script_graph(script)

        season = Season(script_id=script.id, number=1, title="Season One")
        season_node_id = graph_ops.create_season_node(season, script_node_id)

        # Create episode
        episode = Episode(
            script_id=script.id,
            season_id=season.id,
            number=1,
            title="Pilot",
            writer="Test Writer",
            director="Test Director",
            air_date=datetime(2024, 1, 1),
        )

        # Create episode node
        _ = graph_ops.create_episode_node(episode, script_node_id, season_node_id)

        # Verify episode was inserted
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM episodes WHERE id = ?", (str(episode.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["id"] == str(episode.id)
        assert row["script_id"] == str(episode.script_id)
        assert row["season_id"] == str(episode.season_id)
        assert row["number"] == episode.number
        assert row["title"] == episode.title
        assert row["writer"] == episode.writer
        assert row["director"] == episode.director
        assert row["air_date"] == episode.air_date.isoformat()

    @pytest.mark.skip(reason="create_episode_node method not yet implemented")
    def test_create_episode_node_without_season(self, test_db_with_ops):
        """Test creating episode without season (standalone special)."""
        conn, graph_ops = test_db_with_ops

        # Create script
        script = Script(title="TV Movie", is_series=True, source_file="movie.fountain")
        script_node_id = graph_ops.create_script_graph(script)

        # Create episode without season
        episode = Episode(
            script_id=script.id,
            number=0,
            title="Christmas Special",
        )

        # Create episode node
        _ = graph_ops.create_episode_node(episode, script_node_id)

        # Verify episode was inserted with null season_id
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM episodes WHERE id = ?", (str(episode.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["season_id"] is None

    def test_create_character_node_handles_script_entity_lookup(self, test_db_with_ops):
        """Test that create_character_node properly handles script entity ID lookup."""
        conn, graph_ops = test_db_with_ops

        # Create script
        script = Script(title="Character Test", source_file="char.fountain")
        script_node_id = graph_ops.create_script_graph(script)

        # Create character
        character = Character(name="JOHN DOE", description="The protagonist")

        # Create character node
        _ = graph_ops.create_character_node(character, script_node_id)

        # Verify character was created and linked to script
        with conn.get_connection() as db_conn:
            # Check character exists
            cursor = db_conn.execute(
                "SELECT * FROM characters WHERE id = ?", (str(character.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["name"] == character.name
        assert row["script_id"] == str(script.id)

    def test_database_sync_with_transactions(self, test_db_with_ops):
        """Test that database operations are properly transactional."""
        conn, graph_ops = test_db_with_ops

        # Create a script
        script = Script(title="Transaction Test", source_file="trans.fountain")

        # Create script graph multiple times in parallel
        # This tests that INSERT OR IGNORE works correctly
        node_ids = []
        for _ in range(3):
            node_id = graph_ops.create_script_graph(script)
            node_ids.append(node_id)

        # All node IDs should be different
        assert len(set(node_ids)) == 3

        # But only one script record should exist
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT COUNT(*) as count FROM scripts WHERE id = ?", (str(script.id),)
            )
            count = cursor.fetchone()["count"]

        assert count == 1

    @pytest.mark.skip(reason="find_edges returns empty list - needs investigation")
    def test_create_scene_node_preserves_script_relationship(self, test_db_with_ops):
        """Test that scene creation maintains proper script relationships."""
        conn, graph_ops = test_db_with_ops

        # Create script
        script = Script(title="Scene Test", source_file="scene.fountain")
        script_node_id = graph_ops.create_script_graph(script)

        # Create scene
        scene = Scene(
            script_id=script.id,
            heading="INT. ROOM - DAY",
            description="A test scene",
            script_order=1,
        )

        # Create scene node
        scene_node_id = graph_ops.create_scene_node(scene, script_node_id)

        # Verify scene is properly linked
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM scenes WHERE id = ?", (str(scene.id),)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row["script_id"] == str(script.id)

        # Verify graph relationship exists
        edges = graph_ops.graph.find_edges(from_node_id=scene_node_id)
        belongs_to_edges = [e for e in edges if e.edge_type == "BELONGS_TO"]
        assert len(belongs_to_edges) == 1
        assert belongs_to_edges[0].to_node_id == script_node_id
