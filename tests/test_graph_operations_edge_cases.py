"""Test edge cases for GraphOperations database synchronization."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Character, Episode, Script, Season


@pytest.fixture
def test_db_with_ops(temp_db_path):
    """Database connection with GraphOperations."""
    from scriptrag.database import initialize_database

    # Initialize the database first
    initialize_database(temp_db_path)

    conn = DatabaseConnection(temp_db_path)
    with conn:
        yield conn, GraphOperations(conn)


class TestGraphOperationsEdgeCases:
    """Test edge cases and error handling in GraphOperations."""

    def test_create_script_with_minimal_data(self, test_db_with_ops):
        """Test creating script with only required fields."""
        conn, graph_ops = test_db_with_ops

        # Minimal script - only title and source_file
        script = Script(title="Minimal", source_file="min.fountain")

        _script_node_id = graph_ops.create_script_graph(script)

        # Verify in database with NULLs for optional fields
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (str(script.id),)
            )
            row = cursor.fetchone()

        assert row["title"] == "Minimal"
        assert row["source_file"] == "min.fountain"
        assert row["author"] is None
        assert row["genre"] is None
        assert row["format"] == "screenplay"  # Default value

    def test_create_script_with_very_long_title(self, test_db_with_ops):
        """Test script creation with extremely long title."""
        conn, graph_ops = test_db_with_ops

        # Create script with 500 character title
        long_title = "A" * 500
        script = Script(title=long_title, source_file="long.fountain")

        _script_node_id = graph_ops.create_script_graph(script)

        # Should handle long title gracefully
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT title FROM scripts WHERE id = ?", (str(script.id),)
            )
            row = cursor.fetchone()

        assert row["title"] == long_title

    def test_create_script_with_special_characters(self, test_db_with_ops):
        """Test script creation with special characters in fields."""
        conn, graph_ops = test_db_with_ops

        script = Script(
            title='Test\'s "Special" <Script> & More',
            author="O'Brien & Co.",
            genre="Sci-Fi/Fantasy",
            source_file="test's file.fountain",
        )

        _script_node_id = graph_ops.create_script_graph(script)

        # Verify special characters are preserved
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (str(script.id),)
            )
            row = cursor.fetchone()

        assert row["title"] == script.title
        assert row["author"] == script.author
        assert row["genre"] == script.genre

    @pytest.mark.skip(reason="create_season_node method not yet implemented")
    def test_create_season_with_null_title(self, test_db_with_ops):
        """Test season creation without title."""
        conn, graph_ops = test_db_with_ops

        script = Script(title="Series", is_series=True, source_file="series.fountain")
        script_node_id = graph_ops.create_script_graph(script)

        # Season with no title
        season = Season(script_id=script.id, number=1)

        _ = graph_ops.create_season_node(season, script_node_id)

        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM seasons WHERE id = ?", (str(season.id),)
            )
            row = cursor.fetchone()

        assert row["number"] == 1
        assert row["title"] is None
        assert row["year"] is None

    @pytest.mark.skip(reason="create_episode_node method not yet implemented")
    def test_create_episode_with_future_air_date(self, test_db_with_ops):
        """Test episode creation with future air date."""
        conn, graph_ops = test_db_with_ops

        script = Script(
            title="Future Show", is_series=True, source_file="future.fountain"
        )
        script_node_id = graph_ops.create_script_graph(script)

        # Episode airing in 2030
        future_date = datetime(2030, 12, 25)
        episode = Episode(
            script_id=script.id,
            number=1,
            title="Future Episode",
            air_date=future_date,
        )

        _ = graph_ops.create_episode_node(episode, script_node_id)

        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT air_date FROM episodes WHERE id = ?", (str(episode.id),)
            )
            row = cursor.fetchone()

        assert row["air_date"] == future_date.isoformat()

    @pytest.mark.skip(reason="Foreign key constraint behavior needs clarification")
    def test_create_character_when_script_node_missing(self, test_db_with_ops):
        """Test character creation when script node lookup fails."""
        conn, graph_ops = test_db_with_ops

        # Create character with invalid script node ID
        character = Character(name="ORPHAN", description="No script")

        # Mock the get_node to return None
        with patch.object(graph_ops.graph, "get_node", return_value=None):
            char_node_id = graph_ops.create_character_node(character, "invalid_node_id")

        # Should still create character node
        assert char_node_id is not None

        # Check character in database - should NOT be inserted without valid script
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM characters WHERE id = ?", (str(character.id),)
            )
            row = cursor.fetchone()

        # Character should not be in database without valid script
        assert row is None

    def test_create_character_when_node_lookup_raises_exception(self, test_db_with_ops):
        """Test character creation when node lookup raises exception."""
        conn, graph_ops = test_db_with_ops

        script = Script(title="Error Test", source_file="error.fountain")
        script_node_id = graph_ops.create_script_graph(script)

        character = Character(name="ERROR_CHAR")

        # Mock get_node to raise exception
        with patch.object(
            graph_ops.graph, "get_node", side_effect=Exception("Database error")
        ):
            # Should handle exception gracefully
            char_node_id = graph_ops.create_character_node(character, script_node_id)

        assert char_node_id is not None

    @pytest.mark.skip(
        reason="sqlite3.Connection execute is read-only - mock approach needs revision"
    )
    def test_concurrent_script_creation_race_condition(self, test_db_with_ops):
        """Test handling of concurrent script creation (race condition)."""
        conn, graph_ops = test_db_with_ops

        script = Script(title="Race Condition", source_file="race.fountain")

        # Simulate race condition - another process inserts the script
        # between our check and insert
        # Simulate race condition using the database connection
        with conn.get_connection() as db_conn:
            original_execute = db_conn.execute
            call_count = 0

            def mock_execute(query, params=None):
                nonlocal call_count
                call_count += 1

                # On first INSERT attempt, simulate constraint violation
                if "INSERT OR IGNORE INTO scripts" in query and call_count == 1:
                    # First insert the record
                    original_execute(query, params)
                    # Then return 0 rows affected to simulate race condition
                    return Mock(rowcount=0)

                return original_execute(query, params)

            with patch.object(db_conn, "execute", side_effect=mock_execute):
                # Should handle gracefully
                script_node_id = graph_ops.create_script_graph(script)

        assert script_node_id is not None

    @pytest.mark.skip(reason="create_episode_node method not yet implemented")
    def test_episode_with_very_long_credits(self, test_db_with_ops):
        """Test episode with extremely long writer/director credits."""
        conn, graph_ops = test_db_with_ops

        script = Script(
            title="Long Credits", is_series=True, source_file="credits.fountain"
        )
        script_node_id = graph_ops.create_script_graph(script)

        # Episode with multiple writers and directors
        long_writers = ", ".join([f"Writer {i}" for i in range(50)])
        long_directors = ", ".join([f"Director {i}" for i in range(30)])

        episode = Episode(
            script_id=script.id,
            number=1,
            title="Collaboration",
            writer=long_writers,
            director=long_directors,
        )

        _ = graph_ops.create_episode_node(episode, script_node_id)

        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT writer, director FROM episodes WHERE id = ?",
                (str(episode.id),),
            )
            row = cursor.fetchone()

        assert row["writer"] == long_writers
        assert row["director"] == long_directors

    @pytest.mark.skip(reason="create_season_node method not yet implemented")
    def test_season_with_duplicate_number_different_script(self, test_db_with_ops):
        """Test creating seasons with same number for different scripts."""
        conn, graph_ops = test_db_with_ops

        # Create two different scripts
        script1 = Script(title="Show 1", is_series=True, source_file="show1.fountain")
        script2 = Script(title="Show 2", is_series=True, source_file="show2.fountain")

        node1 = graph_ops.create_script_graph(script1)
        node2 = graph_ops.create_script_graph(script2)

        # Create season 1 for both scripts
        season1 = Season(script_id=script1.id, number=1, title="S1 of Show 1")
        season2 = Season(script_id=script2.id, number=1, title="S1 of Show 2")

        _s1_node = graph_ops.create_season_node(season1, node1)
        _s2_node = graph_ops.create_season_node(season2, node2)

        # Both should exist
        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT COUNT(*) as count FROM seasons WHERE number = 1"
            )
            count = cursor.fetchone()["count"]

        assert count == 2

    @pytest.mark.skip(reason="Unicode handling in database - needs investigation")
    def test_script_creation_with_unicode_content(self, test_db_with_ops):
        """Test script creation with Unicode characters."""
        conn, graph_ops = test_db_with_ops

        script = Script(
            title="日本語タイトル",
            author="François Müller",
            genre="Comedia/драма",
            description="A story with émojis 🎬🎭",
            source_file="unicode.fountain",
        )

        _script_node_id = graph_ops.create_script_graph(script)

        with conn.get_connection() as db_conn:
            cursor = db_conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (str(script.id),)
            )
            row = cursor.fetchone()

        assert row["title"] == script.title
        assert row["author"] == script.author
        assert row["genre"] == script.genre
        assert row["description"] == script.description
