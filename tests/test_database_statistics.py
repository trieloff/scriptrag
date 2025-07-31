"""Tests for database statistics collection."""

import json
import sqlite3
from uuid import uuid4

import pytest

from scriptrag.database import (
    DatabaseConnection,
    DatabaseStatistics,
    initialize_database,
)


class TestDatabaseStatistics:
    """Test database statistics collection and calculations."""

    def test_empty_database_statistics(self, tmp_path):
        """Test statistics on empty database."""
        db_path = tmp_path / "empty.db"
        initialize_database(db_path)

        with DatabaseConnection(db_path) as conn:
            stats = DatabaseStatistics(conn)

            # Test database metrics
            db_metrics = stats.get_database_metrics()
            assert db_metrics["file_size"] > 0  # Schema takes some space
            assert db_metrics["total_scripts"] == 0
            assert db_metrics["total_scenes"] == 0
            assert db_metrics["total_characters"] == 0
            assert db_metrics["total_locations"] == 0
            assert db_metrics["total_episodes"] == 0
            assert db_metrics["total_seasons"] == 0

            # Test graph statistics
            graph_stats = stats.get_graph_statistics()
            assert graph_stats["total_nodes"] == 0
            assert graph_stats["total_edges"] == 0
            assert graph_stats["avg_degree"] == 0.0
            assert graph_stats["graph_density"] == 0.0

            # Test embedding stats
            embedding_stats = stats.get_embedding_statistics()
            assert embedding_stats["total_embeddings"] == 0
            assert embedding_stats["coverage_percentage"] == 0.0

            # Test usage patterns
            usage = stats.get_usage_patterns()
            assert usage["most_connected_characters"] == []
            assert usage["longest_scripts"] == []
            assert usage["busiest_locations"] == []
            assert usage["common_times_of_day"] == {}

    def test_populated_database_statistics(self, tmp_path):
        """Test statistics on populated database."""
        db_path = tmp_path / "populated.db"
        initialize_database(db_path)

        conn = DatabaseConnection(db_path)
        with conn.transaction() as tx:
            # Add test data
            script_id = str(uuid4())
            tx.execute(
                """INSERT INTO scripts (id, title, author, description)
                   VALUES (?, ?, ?, ?)""",
                (script_id, "Test Script", "Test Author", "A test script"),
            )

            # Add characters
            char_ids = []
            for name in ["Alice", "Bob", "Charlie"]:
                char_id = str(uuid4())
                char_ids.append(char_id)
                tx.execute(
                    """INSERT INTO characters (id, script_id, name)
                       VALUES (?, ?, ?)""",
                    (char_id, script_id, name),
                )

                # Add to graph as nodes
                tx.execute(
                    """INSERT INTO nodes (id, node_type, entity_id, properties_json)
                       VALUES (?, ?, ?, ?)""",
                    (char_id, "CHARACTER", char_id, json.dumps({"name": name})),
                )

            # Add character relationships (edges)
            # Alice -> Bob
            tx.execute(
                """INSERT INTO edges (id, from_node_id, to_node_id, edge_type)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid4()), char_ids[0], char_ids[1], "TALKS_TO"),
            )
            # Bob -> Charlie
            tx.execute(
                """INSERT INTO edges (id, from_node_id, to_node_id, edge_type)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid4()), char_ids[1], char_ids[2], "TALKS_TO"),
            )

            # Add locations and scenes
            location_id = str(uuid4())
            tx.execute(
                """INSERT INTO locations
                   (id, script_id, interior, name, time_of_day, raw_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (location_id, script_id, True, "Office", "DAY", "INT. OFFICE - DAY"),
            )

            for i in range(5):
                scene_id = str(uuid4())
                tx.execute(
                    """INSERT INTO scenes
                       (id, script_id, location_id, heading, script_order, time_of_day)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (scene_id, script_id, location_id, "INT. OFFICE - DAY", i, "DAY"),
                )

            # Add embeddings for coverage test
            tx.execute(
                """INSERT INTO embeddings
                   (id, entity_type, entity_id, content, embedding_model,
                    dimension, vector_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid4()),
                    "character",
                    char_ids[0],
                    "test content",
                    "test-model",
                    1,
                    "[0.1]",
                ),
            )

        # Now test statistics using the connection
        with DatabaseConnection(db_path) as conn:
            stats = DatabaseStatistics(conn)

            # Test database metrics
            db_metrics = stats.get_database_metrics()
            assert db_metrics["total_scripts"] == 1
            assert db_metrics["total_scenes"] == 5
            assert db_metrics["total_characters"] == 3
            assert db_metrics["total_locations"] == 1

            # Test graph statistics
            graph_stats = stats.get_graph_statistics()
            assert graph_stats["total_nodes"] == 3
            assert graph_stats["total_edges"] == 2
            assert graph_stats["node_types"]["CHARACTER"] == 3
            assert graph_stats["edge_types"]["TALKS_TO"] == 2
            assert graph_stats["avg_degree"] > 0

            # Test embedding stats
            embedding_stats = stats.get_embedding_statistics()
            assert embedding_stats["total_embeddings"] == 1
            assert embedding_stats["entity_types"]["character"] == 1
            # Coverage is based on scenes, not characters
            assert embedding_stats["coverage_percentage"] == 0.0  # No scene embeddings

            # Test usage patterns
            usage = stats.get_usage_patterns()
            assert len(usage["most_connected_characters"]) > 0
            assert usage["longest_scripts"][0]["title"] == "Test Script"
            assert usage["busiest_locations"][0]["name"] == "Office"
            assert usage["common_times_of_day"]["DAY"] == 5

    def test_all_statistics(self, tmp_path):
        """Test get_all_statistics aggregation."""
        db_path = tmp_path / "all_stats.db"
        initialize_database(db_path)

        with DatabaseConnection(db_path) as conn:
            stats = DatabaseStatistics(conn)
            all_stats = stats.get_all_statistics()

            # Verify all sections are present
            assert "database" in all_stats
            assert "graph" in all_stats
            assert "embeddings" in all_stats
            assert "usage" in all_stats

            # Verify structure
            assert "file_size" in all_stats["database"]
            assert "total_nodes" in all_stats["graph"]
            assert "total_embeddings" in all_stats["embeddings"]
            assert "most_connected_characters" in all_stats["usage"]

    def test_sql_injection_prevention(self, tmp_path):
        """Test that SQL injection is prevented."""
        db_path = tmp_path / "injection_test.db"
        initialize_database(db_path)

        conn = DatabaseConnection(db_path)
        with conn.transaction() as tx:
            # Create a malicious table name that shouldn't be queried
            malicious_table = "users; DROP TABLE scripts; --"
            try:
                tx.execute(f"CREATE TABLE '{malicious_table}' (id INTEGER PRIMARY KEY)")
            except sqlite3.OperationalError:
                # Some SQLite versions might reject this table name
                pytest.skip("SQLite rejected malicious table name")

        with DatabaseConnection(db_path) as conn:
            stats = DatabaseStatistics(conn)

            # This should not cause any damage due to whitelist
            db_metrics = stats.get_database_metrics()

            # Verify scripts table still exists
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scripts'"
            ).fetchone()
            assert result is not None

            # The malicious table should not be in table_counts
            assert malicious_table not in db_metrics.get("table_counts", {})

    def test_error_handling(self, tmp_path):
        """Test error handling in statistics collection."""
        db_path = tmp_path / "error_test.db"
        initialize_database(db_path)

        conn = DatabaseConnection(db_path)
        with conn.transaction() as tx:
            # Drop a table to simulate corruption
            tx.execute("DROP TABLE edges")

        with DatabaseConnection(db_path) as conn:
            stats = DatabaseStatistics(conn)

            # Should handle missing table gracefully
            graph_stats = stats.get_graph_statistics()
            # Should return 0 since edges table is missing
            assert graph_stats["total_edges"] == 0

            # Other stats should still work
            db_metrics = stats.get_database_metrics()
            assert db_metrics["total_scripts"] == 0
