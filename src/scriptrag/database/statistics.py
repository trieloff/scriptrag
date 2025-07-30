"""Database statistics collection and analysis.

This module provides comprehensive statistics about the ScriptRAG database,
including entity counts, graph metrics, embedding coverage, and usage patterns.
"""

from pathlib import Path
from typing import Any

from scriptrag.config import get_logger

from .connection import DatabaseConnection

logger = get_logger(__name__)


class DatabaseStatistics:
    """Collects and calculates database statistics."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize database statistics collector.

        Args:
            connection: Database connection instance
        """
        self.connection = connection

    def get_database_metrics(self) -> dict[str, Any]:
        """Get basic database metrics.

        Returns:
            Dictionary containing:
                - file_size: Database file size in bytes
                - total_scripts: Number of scripts
                - total_scenes: Number of scenes
                - total_characters: Number of characters
                - total_locations: Number of locations
                - table_counts: Row counts for all tables
        """
        db_path = Path(self.connection.db_path)
        file_size = db_path.stat().st_size if db_path.exists() else 0

        # Basic entity counts
        metrics = {
            "file_size": file_size,
            "total_scripts": self.connection.execute(
                "SELECT COUNT(*) FROM scripts"
            ).fetchone()[0],
            "total_scenes": self.connection.execute(
                "SELECT COUNT(*) FROM scenes"
            ).fetchone()[0],
            "total_characters": self.connection.execute(
                "SELECT COUNT(*) FROM characters"
            ).fetchone()[0],
            "total_locations": self.connection.execute(
                "SELECT COUNT(*) FROM locations"
            ).fetchone()[0],
            "total_episodes": self.connection.execute(
                "SELECT COUNT(*) FROM episodes"
            ).fetchone()[0],
            "total_seasons": self.connection.execute(
                "SELECT COUNT(*) FROM seasons"
            ).fetchone()[0],
        }

        # Get all table row counts
        table_counts = {}
        tables = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        for table in tables:
            table_name = table[0]
            # Skip FTS tables as they have different structure
            if "_fts" in table_name:
                continue
            try:
                count = self.connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                table_counts[table_name] = count
            except Exception as e:
                logger.warning(
                    "Failed to count rows in table", table=table_name, error=str(e)
                )
                continue

        metrics["table_counts"] = table_counts

        return metrics

    def get_graph_statistics(self) -> dict[str, Any]:
        """Calculate graph statistics.

        Returns:
            Dictionary containing:
                - total_nodes: Total number of graph nodes
                - total_edges: Total number of graph edges
                - node_types: Count by node type
                - edge_types: Count by edge type
                - avg_degree: Average node degree
                - graph_density: Graph density metric
        """
        # Node statistics
        total_nodes = self.connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[
            0
        ]
        node_types = dict(
            self.connection.execute(
                "SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type"
            ).fetchall()
        )

        # Edge statistics
        total_edges = self.connection.execute("SELECT COUNT(*) FROM edges").fetchone()[
            0
        ]
        edge_types = dict(
            self.connection.execute(
                "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"
            ).fetchall()
        )

        # Calculate average degree
        avg_degree = 0.0
        if total_nodes > 0:
            # Count degrees for all nodes
            degree_query = """
            SELECT node_id, COUNT(*) as degree FROM (
                SELECT from_node_id as node_id FROM edges
                UNION ALL
                SELECT to_node_id as node_id FROM edges
            ) GROUP BY node_id
            """
            degrees = self.connection.execute(degree_query).fetchall()
            if degrees:
                total_degree = sum(d[1] for d in degrees)
                avg_degree = total_degree / len(degrees)

        # Calculate graph density
        # For directed graphs: density = edges / (nodes * (nodes - 1))
        max_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 1
        density = total_edges / max_edges if max_edges > 0 else 0.0

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_types": node_types,
            "edge_types": edge_types,
            "avg_degree": round(avg_degree, 2),
            "graph_density": round(density, 4),
        }

    def get_embedding_statistics(self) -> dict[str, Any]:
        """Analyze embedding coverage.

        Returns:
            Dictionary containing:
                - total_embeddings: Total number of embeddings
                - embedded_scripts: Scripts with embeddings
                - embedded_scenes: Scenes with embeddings
                - embedding_models: Count by model
                - coverage_percentage: Percentage of entities with embeddings
        """
        # Total embeddings
        total_embeddings = self.connection.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]

        # Embeddings by entity type
        entity_types = dict(
            self.connection.execute(
                "SELECT entity_type, COUNT(*) FROM embeddings GROUP BY entity_type"
            ).fetchall()
        )

        # Embedding models used
        models = dict(
            self.connection.execute(
                "SELECT embedding_model, COUNT(*) FROM embeddings "
                "GROUP BY embedding_model"
            ).fetchall()
        )

        # Calculate coverage
        total_scenes = self.connection.execute(
            "SELECT COUNT(*) FROM scenes"
        ).fetchone()[0]
        embedded_scenes = self.connection.execute(
            "SELECT COUNT(DISTINCT entity_id) FROM embeddings "
            "WHERE entity_type = 'scene'"
        ).fetchone()[0]

        coverage = (embedded_scenes / total_scenes * 100) if total_scenes > 0 else 0.0

        # Scripts with embeddings
        embedded_scripts = self.connection.execute("""
            SELECT COUNT(DISTINCT s.id)
            FROM scripts s
            WHERE EXISTS (
                SELECT 1 FROM embeddings e
                WHERE e.entity_id IN (
                    SELECT id FROM scenes WHERE script_id = s.id
                ) AND e.entity_type = 'scene'
            )
        """).fetchone()[0]

        return {
            "total_embeddings": total_embeddings,
            "entity_types": entity_types,
            "embedding_models": models,
            "embedded_scripts": embedded_scripts,
            "embedded_scenes": embedded_scenes,
            "coverage_percentage": round(coverage, 2),
        }

    def get_usage_patterns(self) -> dict[str, Any]:
        """Analyze usage patterns in the database.

        Returns:
            Dictionary containing:
                - most_connected_characters: Characters with most relationships
                - longest_scripts: Scripts by scene count
                - busiest_locations: Locations with most scenes
                - common_times_of_day: Distribution of scene times
                - dialogue_distribution: Characters with most dialogue
        """
        # Most connected characters (by edge count in graph)
        connected_chars = self.connection.execute("""
            SELECT c.name, COUNT(DISTINCT e.id) as connections
            FROM characters c
            JOIN nodes n ON n.entity_id = c.id AND n.node_type = 'character'
            LEFT JOIN edges e ON e.from_node_id = n.id OR e.to_node_id = n.id
            GROUP BY c.id, c.name
            ORDER BY connections DESC
            LIMIT 10
        """).fetchall()

        # Longest scripts by scene count
        longest_scripts = self.connection.execute("""
            SELECT s.title, COUNT(sc.id) as scene_count
            FROM scripts s
            LEFT JOIN scenes sc ON sc.script_id = s.id
            GROUP BY s.id, s.title
            ORDER BY scene_count DESC
            LIMIT 10
        """).fetchall()

        # Busiest locations
        busiest_locations = self.connection.execute("""
            SELECT l.name, l.interior, COUNT(s.id) as scene_count
            FROM locations l
            LEFT JOIN scenes s ON s.location_id = l.id
            GROUP BY l.id, l.name, l.interior
            ORDER BY scene_count DESC
            LIMIT 10
        """).fetchall()

        # Common times of day
        times = self.connection.execute("""
            SELECT time_of_day, COUNT(*) as count
            FROM scenes
            WHERE time_of_day IS NOT NULL
            GROUP BY time_of_day
            ORDER BY count DESC
        """).fetchall()

        # Characters with most dialogue
        dialogue_dist = self.connection.execute("""
            SELECT c.name, COUNT(se.id) as dialogue_count
            FROM characters c
            LEFT JOIN scene_elements se ON se.character_id = c.id
                AND se.element_type = 'dialogue'
            GROUP BY c.id, c.name
            HAVING dialogue_count > 0
            ORDER BY dialogue_count DESC
            LIMIT 10
        """).fetchall()

        return {
            "most_connected_characters": [
                {"name": name, "connections": count} for name, count in connected_chars
            ],
            "longest_scripts": [
                {"title": title, "scenes": count} for title, count in longest_scripts
            ],
            "busiest_locations": [
                {"name": name, "interior": bool(interior), "scenes": count}
                for name, interior, count in busiest_locations
            ],
            "common_times_of_day": dict(times),
            "dialogue_distribution": [
                {"character": name, "lines": count} for name, count in dialogue_dist
            ],
        }

    def get_all_statistics(self) -> dict[str, Any]:
        """Get all database statistics.

        Returns:
            Dictionary containing all statistics categories
        """
        return {
            "database": self.get_database_metrics(),
            "graph": self.get_graph_statistics(),
            "embeddings": self.get_embedding_statistics(),
            "usage": self.get_usage_patterns(),
        }
