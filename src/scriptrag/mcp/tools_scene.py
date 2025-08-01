"""Scene-related MCP tools."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.graph import GraphDatabase, GraphNode


class SceneTools:
    """Tools for scene management."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize scene tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def search_scenes(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search for scenes."""
        script_id = args.get("script_id")
        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists and get full UUID
        script = self.server._validate_script_id(script_id)

        # Get search criteria
        query = args.get("query")
        location = args.get("location")
        characters = args.get("characters", [])
        limit = args.get("limit", 10)

        # Search scenes in database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Build search conditions
            conditions = []
            params = []

            # Base query to find scenes for this script
            base_query = """
                SELECT DISTINCT s.*, n.properties_json as properties
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes script_n ON script_n.id = e.from_node_id
                    AND script_n.entity_id = ? AND script_n.node_type = 'script'
                WHERE 1=1
            """
            params.append(str(script.id))  # Use full UUID instead of truncated ID

            # Add text search if query provided
            if query:
                conditions.append("(s.heading LIKE ? OR s.description LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])

            # Add location filter
            if location:
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM edges loc_e
                        JOIN nodes loc_n ON loc_n.id = loc_e.to_node_id
                        WHERE loc_e.from_node_id = n.id
                        AND loc_e.edge_type = 'AT_LOCATION'
                        AND UPPER(loc_n.label) LIKE UPPER(?)
                    )
                """)
                params.append(f"%{location}%")

            # Add character filter
            if characters:
                char_conditions = []
                for char_name in characters:
                    char_conditions.append("""
                        EXISTS (
                            SELECT 1 FROM edges char_e
                            JOIN nodes char_n ON char_n.id = char_e.from_node_id
                            WHERE char_e.to_node_id = n.id
                            AND char_e.edge_type = 'APPEARS_IN'
                            AND char_n.node_type = 'character'
                            AND UPPER(char_n.label) LIKE UPPER(?)
                        )
                    """)
                    params.append(f"%{char_name}%")

                if char_conditions:
                    conditions.append(f"({' OR '.join(char_conditions)})")

            # Combine conditions
            if conditions:
                base_query += " AND " + " AND ".join(conditions)

            # Add ordering and limit
            base_query += " ORDER BY s.script_order LIMIT ?"
            params.append(limit)

            # Execute query
            cursor = connection.execute(base_query, tuple(params))
            rows = cursor.fetchall()

            # Format results
            results = []
            for row in rows:
                scene_data = {
                    "scene_id": row["id"],
                    "heading": row["heading"],
                    "description": row["description"],
                    "script_order": row["script_order"],
                    "temporal_order": row["temporal_order"],
                    "logical_order": row["logical_order"],
                    "time_of_day": row["time_of_day"],
                }

                # Get characters in scene
                char_query = """
                    SELECT DISTINCT c.name
                    FROM characters c
                    JOIN nodes cn
                        ON cn.entity_id = c.id AND cn.node_type = 'character'
                    JOIN edges e
                        ON e.from_node_id = cn.id AND e.edge_type = 'APPEARS_IN'
                    JOIN nodes sn ON sn.id = e.to_node_id AND sn.entity_id = ?
                """
                char_cursor = connection.execute(char_query, (row["id"],))
                scene_data["characters"] = [r["name"] for r in char_cursor.fetchall()]

                # Get location
                loc_query = """
                    SELECT l.label, l.properties_json
                    FROM nodes l
                    JOIN edges e
                        ON e.to_node_id = l.id AND e.edge_type = 'AT_LOCATION'
                    JOIN nodes sn ON sn.id = e.from_node_id AND sn.entity_id = ?
                    LIMIT 1
                """
                loc_cursor = connection.execute(loc_query, (row["id"],))
                loc_row = loc_cursor.fetchone()
                if loc_row:
                    # Try to get name from properties, fall back to label
                    try:
                        props = json.loads(loc_row["properties_json"])
                        scene_data["location"] = props.get("name", loc_row["label"])
                    except (json.JSONDecodeError, KeyError, TypeError):
                        scene_data["location"] = loc_row["label"]
                else:
                    scene_data["location"] = None

                results.append(scene_data)

            return {
                "script_id": script_id,
                "results": results,
                "total_matches": len(results),
                "search_criteria": {
                    "query": query,
                    "location": location,
                    "characters": characters,
                },
            }

    async def get_scene_details(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get detailed information about a specific scene."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or not scene_id:
            raise ValueError("script_id and scene_id are required")

        # Validate script exists
        _ = self.server._validate_script_id(script_id)

        # Get scene details from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Get scene info
            scene_query = """
                SELECT s.*, n.properties_json
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                WHERE s.id = ?
            """
            cursor = connection.execute(scene_query, (scene_id,))
            scene_row = cursor.fetchone()

            if not scene_row:
                raise ValueError(f"Scene not found: {scene_id}")

            # Parse properties
            properties = {}
            if scene_row["properties_json"]:
                from contextlib import suppress

                with suppress(json.JSONDecodeError):
                    properties = json.loads(scene_row["properties_json"])

            # Get characters
            char_query = """
                SELECT c.name, c.id, cn.properties_json
                FROM characters c
                JOIN nodes cn ON cn.entity_id = c.id AND cn.node_type = 'character'
                JOIN edges e ON e.from_node_id = cn.id AND e.edge_type = 'APPEARS_IN'
                JOIN nodes sn ON sn.id = e.to_node_id AND sn.entity_id = ?
            """
            char_cursor = connection.execute(char_query, (scene_id,))
            characters = []
            for row in char_cursor.fetchall():
                char_data = {"name": row["name"], "id": row["id"]}
                if row["properties_json"]:
                    try:
                        char_props = json.loads(row["properties_json"])
                        char_data.update(char_props)
                    except json.JSONDecodeError:
                        pass
                characters.append(char_data)

            # Get location
            loc_query = """
                SELECT l.label, l.properties_json
                FROM nodes l
                JOIN edges e ON e.to_node_id = l.id AND e.edge_type = 'AT_LOCATION'
                JOIN nodes sn ON sn.id = e.from_node_id AND sn.entity_id = ?
                LIMIT 1
            """
            loc_cursor = connection.execute(loc_query, (scene_id,))
            loc_row = loc_cursor.fetchone()
            location = None
            if loc_row:
                try:
                    loc_props = json.loads(loc_row["properties_json"])
                    location = loc_props.get("name", loc_row["label"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    location = loc_row["label"]

            # Get connected scenes
            connected_query = """
                SELECT e.edge_type, s2.id, s2.heading, s2.script_order
                FROM edges e
                JOIN nodes n1 ON n1.id = e.from_node_id AND n1.entity_id = ?
                JOIN nodes n2 ON n2.id = e.to_node_id AND n2.node_type = 'scene'
                JOIN scenes s2 ON s2.id = n2.entity_id
                WHERE e.edge_type IN ('FOLLOWS', 'LEADS_TO')
                UNION
                SELECT e.edge_type, s2.id, s2.heading, s2.script_order
                FROM edges e
                JOIN nodes n1 ON n1.id = e.to_node_id AND n1.entity_id = ?
                JOIN nodes n2 ON n2.id = e.from_node_id AND n2.node_type = 'scene'
                JOIN scenes s2 ON s2.id = n2.entity_id
                WHERE e.edge_type IN ('FOLLOWS', 'LEADS_TO')
            """
            conn_cursor = connection.execute(connected_query, (scene_id, scene_id))
            connections = []
            for row in conn_cursor.fetchall():
                connections.append(
                    {
                        "type": row["edge_type"],
                        "scene_id": row["id"],
                        "heading": row["heading"],
                        "script_order": row["script_order"],
                    }
                )

            return {
                "script_id": script_id,
                "scene": {
                    "id": scene_row["id"],
                    "heading": scene_row["heading"],
                    "description": scene_row["description"],
                    "script_order": scene_row["script_order"],
                    "temporal_order": scene_row["temporal_order"],
                    "logical_order": scene_row["logical_order"],
                    "time_of_day": scene_row["time_of_day"],
                    "location": location,
                    "characters": characters,
                    "properties": properties,
                    "connections": connections,
                },
            }

    async def update_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Update scene information."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")
        updates = args.get("updates", {})

        if not script_id or not scene_id:
            raise ValueError("script_id and scene_id are required")

        # Validate script exists
        _ = self.server._validate_script_id(script_id)

        # Update scene in database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_db = GraphDatabase(connection)

            # Get the scene node
            scene_nodes = graph_db.find_nodes(node_type="scene", entity_id=scene_id)
            if not scene_nodes:
                raise ValueError(f"Scene not found: {scene_id}")

            scene_node = scene_nodes[0]

            # Update properties
            if "properties" in updates:
                # Merge with existing properties
                existing_props = scene_node.properties or {}
                existing_props.update(updates["properties"])
                scene_node.properties = existing_props
                graph_db.update_node(scene_node.id, properties=existing_props)

            # Update basic fields
            update_fields = []
            update_values = []
            for field in ["heading", "description", "time_of_day"]:
                if field in updates:
                    update_fields.append(f"{field} = ?")
                    update_values.append(updates[field])

            if update_fields:
                update_query = f"""
                    UPDATE scenes
                    SET {", ".join(update_fields)}
                    WHERE id = ?
                """
                update_values.append(scene_id)
                connection.execute(update_query, tuple(update_values))

            # Update location if provided
            if "location" in updates:
                # Remove existing location edge
                edges = graph_db.find_edges(
                    from_node_id=scene_node.id, edge_type="AT_LOCATION"
                )
                for edge in edges:
                    graph_db.delete_edge(edge.id)

                # Create new location node and edge
                location_node_id = graph_db.add_node(
                    node_type="location",
                    label=updates["location"],
                    properties={"name": updates["location"]},
                )

                graph_db.add_edge(
                    from_node_id=scene_node.id,
                    to_node_id=location_node_id,
                    edge_type="AT_LOCATION",
                )

            # Update order if provided
            order_fields = []
            order_values = []
            for order_type in ["script_order", "temporal_order", "logical_order"]:
                if order_type in updates:
                    order_fields.append(f"{order_type} = ?")
                    order_values.append(updates[order_type])

            if order_fields:
                order_query = f"""
                    UPDATE scenes
                    SET {", ".join(order_fields)}
                    WHERE id = ?
                """
                order_values.append(scene_id)
                connection.execute(order_query, tuple(order_values))

            # Transaction is committed automatically

            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "updated": True,
                "updates_applied": list(updates.keys()),
            }

    async def delete_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Delete a scene."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or not scene_id:
            raise ValueError("script_id and scene_id are required")

        # Validate script exists
        _ = self.server._validate_script_id(script_id)

        # Delete scene from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_db = GraphDatabase(connection)

            # Find scene node
            scene_nodes = graph_db.find_nodes(node_type="scene", entity_id=scene_id)
            if not scene_nodes:
                raise ValueError(f"Scene not found: {scene_id}")

            scene_node = scene_nodes[0]

            # Delete all edges connected to this scene
            edges = graph_db.find_edges(from_node_id=scene_node.id)
            edges.extend(graph_db.find_edges(to_node_id=scene_node.id))

            for edge in edges:
                graph_db.delete_edge(edge.id)

            # Delete the scene node
            graph_db.delete_node(scene_node.id)

            # Delete from scenes table
            connection.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))

            # Transaction is committed automatically

            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "deleted": True,
            }

    async def inject_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Inject a new scene into the script."""
        script_id = args.get("script_id")
        after_scene_id = args.get("after_scene_id")
        scene_data = args.get("scene", {})

        if not script_id or not scene_data:
            raise ValueError("script_id and scene data are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Create new scene in database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_db = GraphDatabase(connection)

            # Get script node
            script_nodes = graph_db.find_nodes(
                node_type="script", entity_id=str(script.id)
            )
            if not script_nodes:
                raise ValueError(f"Script not found in graph: {script_id}")

            _ = script_nodes[0]  # Validate script exists in graph

            # Determine order for new scene
            if after_scene_id:
                # Get the scene to insert after
                after_query = """
                    SELECT script_order, temporal_order, logical_order
                    FROM scenes WHERE id = ?
                """
                cursor = connection.execute(after_query, (after_scene_id,))
                after_row = cursor.fetchone()
                if not after_row:
                    raise ValueError(f"Scene not found: {after_scene_id}")

                # Get next scene if exists
                next_query = """
                    SELECT MIN(script_order) as next_order
                    FROM scenes
                    WHERE id IN (
                        SELECT s.id FROM scenes s
                        JOIN nodes n ON n.entity_id = s.id
                        JOIN edges e ON e.to_node_id = n.id
                        JOIN nodes sn ON sn.id = e.from_node_id
                        WHERE sn.entity_id = ? AND e.edge_type = 'HAS_SCENE'
                    )
                    AND script_order > ?
                """
                next_cursor = connection.execute(
                    next_query, (str(script.id), after_row["script_order"])
                )
                next_row = next_cursor.fetchone()

                if next_row and next_row["next_order"]:
                    # Insert between scenes
                    new_order = (after_row["script_order"] + next_row["next_order"]) / 2
                else:
                    # Insert at end
                    new_order = after_row["script_order"] + 1

                # Use similar logic for temporal and logical orders
                temporal_order = (
                    after_row["temporal_order"] + 0.5
                    if after_row["temporal_order"]
                    else None
                )
                logical_order = (
                    after_row["logical_order"] + 0.5
                    if after_row["logical_order"]
                    else None
                )
            else:
                # Insert at beginning
                new_order = 0.5
                temporal_order = 0.5
                logical_order = 0.5

            # Create scene record
            scene_id = str(uuid.uuid4())
            insert_query = """
                INSERT INTO scenes (
                    id, script_id, heading, description,
                    script_order, temporal_order, logical_order,
                    time_of_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            connection.execute(
                insert_query,
                (
                    scene_id,
                    str(script.id),
                    scene_data.get("heading", "NEW SCENE"),
                    scene_data.get("description", ""),
                    new_order,
                    temporal_order,
                    logical_order,
                    scene_data.get("time_of_day", "DAY"),
                ),
            )

            # Create scene node
            scene_node_id = graph_db.add_node(
                node_type="scene",
                entity_id=scene_id,
                label=scene_data.get("heading", "NEW SCENE"),
                properties=scene_data.get("properties", {}),
            )

            # Link to script
            graph_db.add_edge(
                from_node_id=str(script.id),
                to_node_id=scene_node_id,
                edge_type="HAS_SCENE",
            )

            # Add location if provided
            if "location" in scene_data:
                location_node_id = graph_db.add_node(
                    node_type="location",
                    label=scene_data["location"],
                    properties={"name": scene_data["location"]},
                )

                graph_db.add_edge(
                    from_node_id=scene_node_id,
                    to_node_id=location_node_id,
                    edge_type="AT_LOCATION",
                )

            # Add character relationships if provided
            if "characters" in scene_data:
                for char_name in scene_data["characters"]:
                    # Find or create character
                    char_nodes = graph_db.find_nodes(
                        node_type="character", label_pattern=char_name
                    )
                    if char_nodes:
                        char_node = char_nodes[0]
                    else:
                        # Create new character
                        char_id = str(uuid.uuid4())
                        connection.execute(
                            (
                                "INSERT INTO characters (id, script_id, name) "
                                "VALUES (?, ?, ?)"
                            ),
                            (char_id, str(script.id), char_name),
                        )
                        char_node_id = graph_db.add_node(
                            node_type="character",
                            entity_id=char_id,
                            label=char_name,
                        )
                        char_node = GraphNode(
                            node_id=char_node_id,
                            node_type="character",
                            entity_id=char_id,
                            label=char_name,
                        )

                    # Create appearance edge
                    graph_db.add_edge(
                        from_node_id=char_node.id,
                        to_node_id=scene_node_id,
                        edge_type="APPEARS_IN",
                    )

            # Transaction is committed automatically

            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "injected": True,
                "script_order": new_order,
                "after_scene_id": after_scene_id,
            }
