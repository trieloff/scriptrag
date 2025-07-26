"""Graph database interface for ScriptRAG.

This module provides the core graph database functionality, including
node and edge management, graph traversal, and query operations.
"""

import json
import math
from collections import defaultdict, deque
from typing import Any
from uuid import uuid4

from scriptrag.config import get_logger

# Removed unused import
from .connection import DatabaseConnection

logger = get_logger(__name__)


class GraphNode:
    """Represents a node in the graph database."""

    def __init__(
        self,
        node_id: str,
        node_type: str,
        entity_id: str | None = None,
        label: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a graph node.

        Args:
            node_id: Unique node identifier
            node_type: Type of node (script, scene, character, etc.)
            entity_id: Reference to entity in another table
            label: Human-readable label
            properties: Additional properties as key-value pairs
        """
        self.id = node_id
        self.node_type = node_type
        self.entity_id = entity_id
        self.label = label
        self.properties = properties or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            "id": self.id,
            "node_type": self.node_type,
            "entity_id": self.entity_id,
            "label": self.label,
            "properties": self.properties,
        }

    @classmethod
    def from_row(cls, row: Any) -> "GraphNode":
        """Create GraphNode from database row.

        Args:
            row: Database row object

        Returns:
            GraphNode instance
        """
        properties = {}
        if row["properties_json"]:
            try:
                properties = json.loads(row["properties_json"])
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON in node properties: {row['properties_json']}"
                )

        return cls(
            node_id=row["id"],
            node_type=row["node_type"],
            entity_id=row["entity_id"],
            label=row["label"],
            properties=properties,
        )


class GraphEdge:
    """Represents an edge in the graph database."""

    def __init__(
        self,
        edge_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
        weight: float = 1.0,
    ) -> None:
        """Initialize a graph edge.

        Args:
            edge_id: Unique edge identifier
            from_node_id: Source node ID
            to_node_id: Target node ID
            edge_type: Type of relationship
            properties: Additional properties as key-value pairs
            weight: Edge weight for weighted graphs
        """
        self.id = edge_id
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.edge_type = edge_type
        self.properties = properties or {}
        self.weight = weight

    def to_dict(self) -> dict[str, Any]:
        """Convert edge to dictionary representation."""
        return {
            "id": self.id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "properties": self.properties,
            "weight": self.weight,
        }

    @classmethod
    def from_row(cls, row: Any) -> "GraphEdge":
        """Create GraphEdge from database row.

        Args:
            row: Database row object

        Returns:
            GraphEdge instance
        """
        properties = {}
        if row["properties_json"]:
            try:
                properties = json.loads(row["properties_json"])
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON in edge properties: {row['properties_json']}"
                )

        return cls(
            edge_id=row["id"],
            from_node_id=row["from_node_id"],
            to_node_id=row["to_node_id"],
            edge_type=row["edge_type"],
            properties=properties,
            weight=row["weight"] or 1.0,
        )


class GraphDatabase:
    """Main interface for graph database operations."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize graph database.

        Args:
            connection: Database connection instance
        """
        self.connection = connection

    # Node operations
    def add_node(
        self,
        node_type: str,
        entity_id: str | None = None,
        label: str | None = None,
        properties: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> str:
        """Add a new node to the graph.

        Args:
            node_type: Type of node
            entity_id: Reference to entity in another table
            label: Human-readable label
            properties: Additional properties
            node_id: Specific node ID (generated if None)

        Returns:
            Node ID
        """
        if node_id is None:
            node_id = str(uuid4())

        properties_json = json.dumps(properties) if properties else None

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO nodes (id, node_type, entity_id, label, properties_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (node_id, node_type, entity_id, label, properties_json),
            )

        logger.debug(f"Added node {node_id} of type {node_type}")
        return node_id

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID.

        Args:
            node_id: Node identifier

        Returns:
            GraphNode instance or None if not found
        """
        row = self.connection.fetch_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
        return GraphNode.from_row(row) if row else None

    def update_node(
        self,
        node_id: str,
        node_type: str | None = None,
        entity_id: str | None = None,
        label: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing node.

        Args:
            node_id: Node identifier
            node_type: New node type
            entity_id: New entity reference
            label: New label
            properties: New properties (replaces existing)

        Returns:
            True if node was updated
        """
        # Build dynamic update query
        updates = []
        params = []

        if node_type is not None:
            updates.append("node_type = ?")
            params.append(node_type)

        if entity_id is not None:
            updates.append("entity_id = ?")
            params.append(entity_id)

        if label is not None:
            updates.append("label = ?")
            params.append(label)

        if properties is not None:
            updates.append("properties_json = ?")
            params.append(json.dumps(properties))

        if not updates:
            return False

        params.append(node_id)
        sql = f"UPDATE nodes SET {', '.join(updates)} WHERE id = ?"

        with self.connection.transaction() as conn:
            cursor = conn.execute(sql, params)
            updated = cursor.rowcount > 0

        if updated:
            logger.debug(f"Updated node {node_id}")

        return updated

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges.

        Args:
            node_id: Node identifier

        Returns:
            True if node was deleted
        """
        with self.connection.transaction() as conn:
            # Delete edges first (foreign key constraints)
            conn.execute(
                "DELETE FROM edges WHERE from_node_id = ? OR to_node_id = ?",
                (node_id, node_id),
            )

            # Delete the node
            cursor = conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted node {node_id}")

        return deleted

    def find_nodes(
        self,
        node_type: str | None = None,
        entity_id: str | None = None,
        label_pattern: str | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Find nodes matching criteria.

        Args:
            node_type: Filter by node type
            entity_id: Filter by entity ID
            label_pattern: Filter by label pattern (LIKE)
            limit: Maximum number of results

        Returns:
            List of matching nodes
        """
        conditions = []
        params = []

        if node_type:
            conditions.append("node_type = ?")
            params.append(node_type)

        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)

        if label_pattern:
            conditions.append("label LIKE ?")
            params.append(label_pattern)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"SELECT * FROM nodes {where_clause} ORDER BY created_at {limit_clause}"

        rows = self.connection.fetch_all(sql, tuple(params) if params else None)
        return [GraphNode.from_row(row) for row in rows]

    # Edge operations
    def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
        weight: float = 1.0,
        edge_id: str | None = None,
    ) -> str:
        """Add a new edge to the graph.

        Args:
            from_node_id: Source node ID
            to_node_id: Target node ID
            edge_type: Type of relationship
            properties: Additional properties
            weight: Edge weight
            edge_id: Specific edge ID (generated if None)

        Returns:
            Edge ID
        """
        if edge_id is None:
            edge_id = str(uuid4())

        properties_json = json.dumps(properties) if properties else None

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO edges (id, from_node_id, to_node_id, edge_type,
                                 properties_json, weight)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (edge_id, from_node_id, to_node_id, edge_type, properties_json, weight),
            )

        logger.debug(
            f"Added edge {edge_id}: {from_node_id} -{edge_type}-> {to_node_id}"
        )
        return edge_id

    def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Get an edge by ID.

        Args:
            edge_id: Edge identifier

        Returns:
            GraphEdge instance or None if not found
        """
        row = self.connection.fetch_one("SELECT * FROM edges WHERE id = ?", (edge_id,))
        return GraphEdge.from_row(row) if row else None

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge.

        Args:
            edge_id: Edge identifier

        Returns:
            True if edge was deleted
        """
        with self.connection.transaction() as conn:
            cursor = conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted edge {edge_id}")

        return deleted

    def find_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
        limit: int | None = None,
    ) -> list[GraphEdge]:
        """Find edges matching criteria.

        Args:
            from_node_id: Source node ID filter
            to_node_id: Target node ID filter
            edge_type: Edge type filter
            limit: Maximum number of results

        Returns:
            List of matching edges
        """
        conditions = []
        params = []

        if from_node_id:
            conditions.append("from_node_id = ?")
            params.append(from_node_id)

        if to_node_id:
            conditions.append("to_node_id = ?")
            params.append(to_node_id)

        if edge_type:
            conditions.append("edge_type = ?")
            params.append(edge_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"SELECT * FROM edges {where_clause} ORDER BY created_at {limit_clause}"

        rows = self.connection.fetch_all(sql, tuple(params) if params else None)
        return [GraphEdge.from_row(row) for row in rows]

    # Graph traversal operations
    def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "out",
    ) -> list[GraphNode]:
        """Get neighboring nodes.

        Args:
            node_id: Source node ID
            edge_type: Filter by edge type
            direction: 'out' for outgoing, 'in' for incoming, 'both' for both

        Returns:
            List of neighboring nodes
        """
        conditions = []
        params = []

        if direction == "out":
            conditions.append("e.from_node_id = ?")
            join_condition = "n.id = e.to_node_id"
        elif direction == "in":
            conditions.append("e.to_node_id = ?")
            join_condition = "n.id = e.from_node_id"
        elif direction == "both":
            conditions.append("(e.from_node_id = ? OR e.to_node_id = ?)")
            join_condition = (
                "(n.id = e.to_node_id OR n.id = e.from_node_id) AND n.id != ?"
            )
            params.extend([node_id, node_id])  # Add twice for both conditions
        else:
            raise ValueError("Direction must be 'out', 'in', or 'both'")

        params.append(node_id)

        if edge_type:
            conditions.append("e.edge_type = ?")
            params.append(edge_type)

        # Adjust parameter order for 'both' direction
        if direction == "both":
            params = [node_id, node_id, node_id] + ([edge_type] if edge_type else [])

        where_clause = f"WHERE {' AND '.join(conditions)}"

        sql = f"""
      SELECT DISTINCT n.* FROM nodes n
      JOIN edges e ON {join_condition}
      {where_clause}
      ORDER BY n.created_at
      """

        rows = self.connection.fetch_all(sql, tuple(params) if params else None)
        return [GraphNode.from_row(row) for row in rows]

    def find_path(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 6,
        edge_type: str | None = None,
    ) -> list[str] | None:
        """Find shortest path between two nodes using BFS.

        Args:
            start_node_id: Starting node ID
            end_node_id: Target node ID
            max_depth: Maximum path depth
            edge_type: Filter by edge type

        Returns:
            List of node IDs representing the path, or None if no path found
        """
        if start_node_id == end_node_id:
            return [start_node_id]

        visited: set[str] = set()
        queue: list[tuple[str, list[str]]] = [(start_node_id, [start_node_id])]
        visited.add(start_node_id)

        while queue:
            current_node, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            neighbors = self.get_neighbors(current_node, edge_type, direction="out")

            for neighbor in neighbors:
                if neighbor.id == end_node_id:
                    return [*path, neighbor.id]

                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append((neighbor.id, [*path, neighbor.id]))

        return None

    def get_subgraph(
        self,
        center_node_id: str,
        radius: int = 2,
        edge_type: str | None = None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Get subgraph around a center node.

        Args:
            center_node_id: Center node ID
            radius: Number of hops from center
            edge_type: Filter by edge type

        Returns:
            Tuple of (nodes, edges) in the subgraph
        """
        nodes_in_subgraph: set[str] = {center_node_id}
        current_level = {center_node_id}

        # Expand outward from center node
        for _ in range(radius):
            next_level: set[str] = set()
            for node_id in current_level:
                neighbors = self.get_neighbors(node_id, edge_type, direction="both")
                for neighbor in neighbors:
                    if neighbor.id not in nodes_in_subgraph:
                        next_level.add(neighbor.id)
                        nodes_in_subgraph.add(neighbor.id)

            if not next_level:
                break
            current_level = next_level

        # Get all nodes in subgraph
        node_ids = list(nodes_in_subgraph)
        placeholders = ", ".join(["?"] * len(node_ids))
        nodes_sql = f"SELECT * FROM nodes WHERE id IN ({placeholders})"
        node_rows = self.connection.fetch_all(nodes_sql, tuple(node_ids))
        nodes = [GraphNode.from_row(row) for row in node_rows]

        # Get all edges between nodes in subgraph
        edge_conditions = []
        edge_params = []

        edge_conditions.append(f"from_node_id IN ({placeholders})")
        edge_conditions.append(f"to_node_id IN ({placeholders})")
        edge_params.extend(node_ids)
        edge_params.extend(node_ids)

        if edge_type:
            edge_conditions.append("edge_type = ?")
            edge_params.append(edge_type)

        edges_sql = f"SELECT * FROM edges WHERE {' AND '.join(edge_conditions)}"
        edge_rows = self.connection.fetch_all(edges_sql, tuple(edge_params))
        edges = [GraphEdge.from_row(row) for row in edge_rows]

        return nodes, edges

    def get_node_degree(self, node_id: str, direction: str = "both") -> int:
        """Get the degree (number of connections) of a node.

        Args:
            node_id: Node identifier
            direction: 'in', 'out', or 'both'

        Returns:
            Node degree
        """
        params: tuple[str] | tuple[str, str]
        if direction == "out":
            sql = "SELECT COUNT(*) as degree FROM edges WHERE from_node_id = ?"
            params = (node_id,)
        elif direction == "in":
            sql = "SELECT COUNT(*) as degree FROM edges WHERE to_node_id = ?"
            params = (node_id,)
        elif direction == "both":
            sql = (
                "SELECT COUNT(*) as degree FROM edges "
                "WHERE from_node_id = ? OR to_node_id = ?"
            )
            params = (node_id, node_id)
        else:
            raise ValueError("Direction must be 'in', 'out', or 'both'")

        row = self.connection.fetch_one(sql, params)
        return row["degree"] if row else 0

    def calculate_degree_centrality(
        self, node_id: str | None = None, normalized: bool = True
    ) -> dict[str, float] | float:
        """Calculate degree centrality for all nodes or a specific node.

        Degree centrality is the fraction of nodes a node is connected to.

        Args:
            node_id: Specific node ID to calculate centrality for (None for all nodes)
            normalized: Whether to normalize by (n-1) where n is total nodes

        Returns:
            Dictionary of {node_id: centrality} or single centrality value
        """
        # Get all nodes if calculating for all
        if node_id is None:
            rows = self.connection.fetch_all("SELECT id FROM nodes")
            all_node_ids = [row["id"] for row in rows]
        else:
            all_node_ids = [node_id]

        count_row = self.connection.fetch_one("SELECT COUNT(*) as count FROM nodes")
        total_nodes = count_row["count"] if count_row else 0
        # For bidirectional edge representation of undirected graphs,
        # max degree is 2*(n-1)
        max_degree = 2 * (total_nodes - 1) if total_nodes > 1 else 1

        centralities = {}
        for nid in all_node_ids:
            degree = self.get_node_degree(nid, direction="both")
            if normalized and max_degree > 0:
                centralities[nid] = degree / max_degree
            else:
                centralities[nid] = float(degree)

        return centralities if node_id is None else centralities[node_id]

    def calculate_betweenness_centrality(
        self, node_id: str | None = None, normalized: bool = True
    ) -> dict[str, float] | float:
        """Calculate betweenness centrality for all nodes or a specific node.

        Betweenness centrality measures how often a node lies on shortest paths
        between other nodes.

        Args:
            node_id: Specific node ID to calculate centrality for (None for all nodes)
            normalized: Whether to normalize by maximum possible betweenness

        Returns:
            Dictionary of {node_id: centrality} or single centrality value
        """
        # Get all nodes
        rows = self.connection.fetch_all("SELECT id FROM nodes")
        all_nodes = [row["id"] for row in rows]

        if not all_nodes:
            return {} if node_id is None else 0.0

        # Calculate for specific node or all nodes
        target_nodes = [node_id] if node_id else all_nodes
        betweenness = dict.fromkeys(target_nodes, 0.0)

        # For each pair of nodes, find shortest paths and count how many pass
        # through each node
        for s in all_nodes:
            # Single source shortest paths using BFS
            distances = {s: 0}
            predecessors = defaultdict(list)
            sigma = defaultdict(int)
            sigma[s] = 1
            queue = deque([s])

            # BFS to find shortest paths
            while queue:
                v = queue.popleft()
                neighbors = self.get_neighbors(v, direction="out")

                for neighbor_obj in neighbors:
                    w = neighbor_obj.id
                    # Path discovery
                    if w not in distances:
                        queue.append(w)
                        distances[w] = distances[v] + 1

                    # Path counting
                    if distances[w] == distances[v] + 1:
                        sigma[w] += sigma[v]
                        predecessors[w].append(v)

            # Accumulation phase
            delta: dict[str, float] = defaultdict(float)
            # Sort nodes by distance (furthest first)
            sorted_nodes = sorted(
                distances.keys(), key=lambda x: distances[x], reverse=True
            )

            for w in sorted_nodes:
                for v in predecessors[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])

            # Add to betweenness scores (excluding source node)
            for nid in target_nodes:
                if nid != s and nid in delta:
                    betweenness[nid] += delta[nid]

        # Normalize if requested
        if normalized:
            n = len(all_nodes)
            if n > 2:
                # For undirected graphs: 2/((n-1)(n-2))
                # For directed graphs: 1/((n-1)(n-2))
                # We'll use the undirected formula as screenplay graphs are
                # typically undirected
                norm_factor = 2.0 / ((n - 1) * (n - 2))
                for nid in betweenness:
                    betweenness[nid] *= norm_factor

        return betweenness if node_id is None else betweenness.get(node_id, 0.0)

    def calculate_closeness_centrality(
        self, node_id: str | None = None, normalized: bool = True
    ) -> dict[str, float] | float:
        """Calculate closeness centrality for all nodes or a specific node.

        Closeness centrality is the reciprocal of the sum of shortest path distances
        to all other nodes.

        Args:
            node_id: Specific node ID to calculate centrality for (None for all nodes)
            normalized: Whether to normalize by (n-1) where n is total nodes

        Returns:
            Dictionary of {node_id: centrality} or single centrality value
        """
        # Get all nodes
        rows = self.connection.fetch_all("SELECT id FROM nodes")
        all_nodes = [row["id"] for row in rows]

        if not all_nodes:
            return {} if node_id is None else 0.0

        target_nodes = [node_id] if node_id else all_nodes
        closeness = {}

        for source in target_nodes:
            # BFS to calculate shortest distances
            distances = {source: 0}
            queue = deque([source])
            visited = {source}

            while queue:
                current = queue.popleft()
                neighbors = self.get_neighbors(current, direction="both")

                for neighbor_obj in neighbors:
                    neighbor_id = neighbor_obj.id
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        distances[neighbor_id] = distances[current] + 1
                        queue.append(neighbor_id)

            # Calculate closeness centrality
            total_distance = sum(distances.values())
            reachable_nodes = len(distances) - 1  # Exclude the source node itself

            if total_distance > 0 and reachable_nodes > 0:
                if normalized:
                    # Normalize by (n-1) and multiply by reachable nodes
                    n = len(all_nodes)
                    closeness[source] = (reachable_nodes / total_distance) * (
                        reachable_nodes / (n - 1)
                    )
                else:
                    closeness[source] = reachable_nodes / total_distance
            else:
                closeness[source] = 0.0

        return closeness if node_id is None else closeness.get(node_id, 0.0)

    def calculate_eigenvector_centrality(
        self,
        node_id: str | None = None,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> dict[str, float] | float:
        """Calculate eigenvector centrality using power iteration method.

        Eigenvector centrality assigns relative scores based on the principle that
        connections to high-scoring nodes contribute more than connections to
        low-scoring nodes.

        Args:
            node_id: Specific node ID to calculate centrality for (None for all nodes)
            max_iterations: Maximum number of iterations for convergence
            tolerance: Convergence tolerance

        Returns:
            Dictionary of {node_id: centrality} or single centrality value
        """
        # Get all nodes
        rows = self.connection.fetch_all("SELECT id FROM nodes")
        all_nodes = [row["id"] for row in rows]

        if not all_nodes:
            return {} if node_id is None else 0.0

        n = len(all_nodes)
        node_to_index = {node: i for i, node in enumerate(all_nodes)}

        # Build adjacency matrix
        adjacency = [[0.0] * n for _ in range(n)]

        for i, node in enumerate(all_nodes):
            neighbors = self.get_neighbors(node, direction="both")
            for neighbor_obj in neighbors:
                j = node_to_index.get(neighbor_obj.id)
                if j is not None:
                    adjacency[i][j] = 1.0

        # Initialize eigenvector with equal values
        eigenvector = [1.0] * n

        # Power iteration
        for _iteration in range(max_iterations):
            new_eigenvector = [0.0] * n

            # Matrix-vector multiplication: A * eigenvector
            for i in range(n):
                for j in range(n):
                    new_eigenvector[i] += adjacency[i][j] * eigenvector[j]

            # Normalize the eigenvector
            norm = math.sqrt(sum(x * x for x in new_eigenvector))
            if norm > 0:
                new_eigenvector = [x / norm for x in new_eigenvector]

            # Check for convergence
            diff = sum(abs(new_eigenvector[i] - eigenvector[i]) for i in range(n))
            if diff < tolerance:
                break

            eigenvector = new_eigenvector

        # Create result dictionary
        centralities = {all_nodes[i]: eigenvector[i] for i in range(n)}

        return centralities if node_id is None else centralities.get(node_id, 0.0)

    def get_centrality_summary(self, node_id: str) -> dict[str, float]:
        """Get a summary of all centrality measures for a specific node.

        Args:
            node_id: Node identifier

        Returns:
            Dictionary with all centrality measures
        """
        degree_centrality = self.calculate_degree_centrality(node_id)
        betweenness_centrality = self.calculate_betweenness_centrality(node_id)
        closeness_centrality = self.calculate_closeness_centrality(node_id)
        eigenvector_centrality = self.calculate_eigenvector_centrality(node_id)

        return {
            "degree_centrality": (
                degree_centrality if isinstance(degree_centrality, float) else 0.0
            ),
            "betweenness_centrality": (
                betweenness_centrality
                if isinstance(betweenness_centrality, float)
                else 0.0
            ),
            "closeness_centrality": (
                closeness_centrality if isinstance(closeness_centrality, float) else 0.0
            ),
            "eigenvector_centrality": (
                eigenvector_centrality
                if isinstance(eigenvector_centrality, float)
                else 0.0
            ),
        }
