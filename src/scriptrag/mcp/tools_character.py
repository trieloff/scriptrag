"""Character-related MCP tools."""

import json
from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.graph import GraphDatabase


class CharacterTools:
    """Tools for character management."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize character tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def get_character_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get character information."""
        script_id = args.get("script_id")
        character_name = args.get("character_name")

        if not script_id or not character_name:
            raise ValueError("script_id and character_name are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Get character information from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Find character in this script using the actual script UUID
            char_query = """
                SELECT c.*, cn.id as node_id
                FROM characters c
                JOIN nodes cn
                    ON cn.entity_id = c.id AND cn.node_type = 'character'
                JOIN edges e
                    ON e.to_node_id = cn.id AND e.edge_type = 'HAS_CHARACTER'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                WHERE UPPER(c.name) LIKE UPPER(?)
                LIMIT 1
            """
            cursor = connection.execute(
                char_query,
                (str(script.id), f"%{character_name}%"),
            )
            char_row = cursor.fetchone()

            if not char_row:
                return {
                    "script_id": script_id,
                    "character_name": character_name,
                    "scenes_count": 0,
                    "dialogue_lines": 0,
                    "relationships": [],
                    "error": f"Character '{character_name}' not found in script",
                }

            character_id = char_row["id"]
            char_node_id = char_row["node_id"]

            # Get scene appearances
            scene_query = """
                SELECT COUNT(DISTINCT s.id) as scene_count
                FROM scenes s
                JOIN nodes sn
                    ON sn.entity_id = s.id AND sn.node_type = 'scene'
                JOIN edges e
                    ON e.to_node_id = sn.id AND e.edge_type = 'APPEARS_IN'
                WHERE e.from_node_id = ?
            """
            scene_cursor = connection.execute(scene_query, (char_node_id,))
            scene_count = scene_cursor.fetchone()["scene_count"]

            # Get dialogue count
            dialogue_query = """
                SELECT SUM(dialogue_count) as total_dialogue
                FROM characters
                WHERE id = ?
            """
            dialogue_cursor = connection.execute(dialogue_query, (character_id,))
            dialogue_count = dialogue_cursor.fetchone()["total_dialogue"] or 0

            # Get relationships
            rel_query = """
                SELECT DISTINCT
                    e.edge_type,
                    c2.name as related_character,
                    n2.properties_json
                FROM edges e
                JOIN nodes n1 ON n1.id = e.from_node_id AND n1.id = ?
                JOIN nodes n2 ON n2.id = e.to_node_id AND n2.node_type = 'character'
                JOIN characters c2 ON c2.id = n2.entity_id
                WHERE e.edge_type IN ('KNOWS', 'RELATED_TO', 'INTERACTS_WITH')
                UNION
                SELECT DISTINCT
                    e.edge_type,
                    c2.name as related_character,
                    n2.properties_json
                FROM edges e
                JOIN nodes n1 ON n1.id = e.to_node_id AND n1.id = ?
                JOIN nodes n2 ON n2.id = e.from_node_id AND n2.node_type = 'character'
                JOIN characters c2 ON c2.id = n2.entity_id
                WHERE e.edge_type IN ('KNOWS', 'RELATED_TO', 'INTERACTS_WITH')
            """
            rel_cursor = connection.execute(rel_query, (char_node_id, char_node_id))
            relationships = []
            for row in rel_cursor.fetchall():
                rel_data = {
                    "type": row["edge_type"],
                    "character": row["related_character"],
                }
                if row["properties_json"]:
                    try:
                        props = json.loads(row["properties_json"])
                        rel_data["properties"] = props
                    except json.JSONDecodeError:
                        pass
                relationships.append(rel_data)

            # Get character arc info if available
            arc_query = """
                SELECT
                    mentor_type,
                    analysis_timestamp,
                    result_json
                FROM mentor_analyses
                WHERE script_id = ?
                AND result_json LIKE ?
                ORDER BY analysis_timestamp DESC
                LIMIT 1
            """
            arc_cursor = connection.execute(
                arc_query,
                (str(script.id), f'%"{char_row["name"]}"%'),
            )
            arc_info = None
            arc_row = arc_cursor.fetchone()
            if arc_row:
                try:
                    result = json.loads(arc_row["result_json"])
                    # Extract character-specific arc info
                    if "character_arcs" in result:
                        for arc in result["character_arcs"]:
                            if arc.get("character") == char_row["name"]:
                                arc_info = {
                                    "mentor_type": arc_row["mentor_type"],
                                    "analysis_date": arc_row["analysis_timestamp"],
                                    "arc": arc,
                                }
                                break
                except json.JSONDecodeError:
                    pass

            # Get first and last appearance
            appearance_query = """
                SELECT
                    MIN(s.script_order) as first_appearance_order,
                    MAX(s.script_order) as last_appearance_order,
                    COUNT(DISTINCT s.id) as total_scenes
                FROM scenes s
                JOIN nodes sn ON sn.entity_id = s.id
                JOIN edges e ON e.to_node_id = sn.id
                WHERE e.from_node_id = ? AND e.edge_type = 'APPEARS_IN'
            """
            app_cursor = connection.execute(appearance_query, (char_node_id,))
            app_row = app_cursor.fetchone()

            # Get the actual scene headings for first/last appearance
            first_scene = None
            last_scene = None
            if app_row["first_appearance_order"] is not None:
                first_query = """
                    SELECT s.heading, s.id
                    FROM scenes s
                    JOIN nodes sn ON sn.entity_id = s.id
                    JOIN edges e ON e.to_node_id = sn.id
                    WHERE e.from_node_id = ? AND e.edge_type = 'APPEARS_IN'
                    AND s.script_order = ?
                """
                first_cursor = connection.execute(
                    first_query,
                    (char_node_id, app_row["first_appearance_order"]),
                )
                first_row = first_cursor.fetchone()
                if first_row:
                    first_scene = {
                        "id": first_row["id"],
                        "heading": first_row["heading"],
                        "order": app_row["first_appearance_order"],
                    }

                last_cursor = connection.execute(
                    first_query,
                    (char_node_id, app_row["last_appearance_order"]),
                )
                last_row = last_cursor.fetchone()
                if last_row:
                    last_scene = {
                        "id": last_row["id"],
                        "heading": last_row["heading"],
                        "order": app_row["last_appearance_order"],
                    }

            return {
                "script_id": script_id,
                "character": {
                    "name": char_row["name"],
                    "id": character_id,
                    "scenes_count": scene_count,
                    "dialogue_lines": int(dialogue_count),
                    "first_appearance": first_scene,
                    "last_appearance": last_scene,
                    "relationships": relationships,
                    "arc_info": arc_info,
                },
            }

    async def get_character_relationships(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get character relationships."""
        script_id = args.get("script_id")
        character_name = args.get("character_name")

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Get relationships from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            _ = GraphDatabase(connection)  # TODO: Use when graph queries needed

            if character_name:
                # Get relationships for specific character
                char_query = """
                    SELECT cn.id as node_id, c.name
                    FROM characters c
                    JOIN nodes cn ON cn.entity_id = c.id AND cn.node_type = 'character'
                    JOIN edges e ON (
                        e.to_node_id = cn.id AND e.edge_type = 'HAS_CHARACTER'
                    )
                    JOIN nodes sn ON sn.id = e.from_node_id
                        AND sn.entity_id = ? AND sn.node_type = 'script'
                    WHERE UPPER(c.name) LIKE UPPER(?)
                    LIMIT 1
                """
                cursor = connection.execute(
                    char_query,
                    (str(script.id), f"%{character_name}%"),
                )
                char_row = cursor.fetchone()

                if not char_row:
                    return {
                        "script_id": script_id,
                        "character": character_name,
                        "relationships": [],
                        "error": f"Character '{character_name}' not found",
                    }

                # Get all relationships for this character
                rel_query = """
                    SELECT DISTINCT
                        c1.name as character1,
                        c2.name as character2,
                        COUNT(DISTINCT s.id) as shared_scenes,
                        GROUP_CONCAT(DISTINCT s.heading, '|||') as scene_headings
                    FROM characters c1
                    JOIN nodes cn1 ON (
                        cn1.entity_id = c1.id AND cn1.node_type = 'character'
                    )
                    JOIN edges e1 ON (
                        e1.from_node_id = cn1.id AND e1.edge_type = 'APPEARS_IN'
                    )
                    JOIN nodes sn ON sn.id = e1.to_node_id AND sn.node_type = 'scene'
                    JOIN scenes s ON s.id = sn.entity_id
                    JOIN edges e2 ON (
                        e2.to_node_id = sn.id AND e2.edge_type = 'APPEARS_IN'
                    )
                    JOIN nodes cn2 ON (
                        cn2.id = e2.from_node_id AND cn2.node_type = 'character'
                    )
                    JOIN characters c2 ON c2.id = cn2.entity_id
                    WHERE c1.id != c2.id
                    AND cn1.id = ?
                    GROUP BY c1.name, c2.name
                    ORDER BY shared_scenes DESC
                """
                rel_cursor = connection.execute(rel_query, (char_row["node_id"],))

                relationships = []
                for row in rel_cursor.fetchall():
                    scene_list = (
                        row["scene_headings"].split("|||")
                        if row["scene_headings"]
                        else []
                    )
                    relationships.append(
                        {
                            "character1": row["character1"],
                            "character2": row["character2"],
                            "shared_scenes": row["shared_scenes"],
                            "scenes": scene_list[:5],  # Limit to first 5 scenes
                        }
                    )

                return {
                    "script_id": script_id,
                    "character": char_row["name"],
                    "relationships": relationships,
                }
            # Get all character relationships in script
            all_rel_query = """
                    SELECT DISTINCT
                        c1.name as character1,
                        c2.name as character2,
                        COUNT(DISTINCT s.id) as shared_scenes
                    FROM characters c1
                    JOIN nodes cn1 ON (
                        cn1.entity_id = c1.id AND cn1.node_type = 'character'
                    )
                    JOIN edges e1 ON (
                        e1.from_node_id = cn1.id AND e1.edge_type = 'APPEARS_IN'
                    )
                    JOIN nodes sn ON sn.id = e1.to_node_id AND sn.node_type = 'scene'
                    JOIN scenes s ON s.id = sn.entity_id AND s.script_id = ?
                    JOIN edges e2 ON (
                        e2.to_node_id = sn.id AND e2.edge_type = 'APPEARS_IN'
                    )
                    JOIN nodes cn2 ON (
                        cn2.id = e2.from_node_id AND cn2.node_type = 'character'
                    )
                    JOIN characters c2 ON c2.id = cn2.entity_id
                    WHERE c1.id < c2.id  -- Avoid duplicates
                    GROUP BY c1.name, c2.name
                    HAVING shared_scenes > 0
                    ORDER BY shared_scenes DESC
                    LIMIT 50
                """
            rel_cursor = connection.execute(all_rel_query, (str(script.id),))

            relationships = []
            for row in rel_cursor.fetchall():
                relationships.append(
                    {
                        "character1": row["character1"],
                        "character2": row["character2"],
                        "shared_scenes": row["shared_scenes"],
                    }
                )

            # Get character interaction graph data
            char_stats_query = """
                    SELECT
                        c.name,
                        COUNT(DISTINCT s.id) as scene_count,
                        c.dialogue_count
                    FROM characters c
                    JOIN nodes cn ON cn.entity_id = c.id AND cn.node_type = 'character'
                    JOIN edges e ON (
                        e.from_node_id = cn.id AND e.edge_type = 'APPEARS_IN'
                    )
                    JOIN nodes sn ON sn.id = e.to_node_id AND sn.node_type = 'scene'
                    JOIN scenes s ON s.id = sn.entity_id
                    WHERE c.script_id = ?
                    GROUP BY c.id, c.name, c.dialogue_count
                    ORDER BY scene_count DESC
                """
            stats_cursor = connection.execute(char_stats_query, (str(script.id),))

            character_stats = []
            for row in stats_cursor.fetchall():
                character_stats.append(
                    {
                        "name": row["name"],
                        "scene_count": row["scene_count"],
                        "dialogue_count": row["dialogue_count"] or 0,
                    }
                )

            return {
                "script_id": script_id,
                "relationships": relationships,
                "character_stats": character_stats,
                "total_relationships": len(relationships),
            }
