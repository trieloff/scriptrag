"""Script Bible-related MCP tools."""

from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.database.bible import ScriptBibleOperations
from scriptrag.database.connection import DatabaseConnection


class BibleTools:
    """Tools for Script Bible management."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize bible tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def create_series_bible(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a series bible."""
        script_id = args.get("script_id")
        title = args.get("title", "Series Bible")
        description = args.get("description", "")

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Create series bible
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_manager = ScriptBibleOperations(connection)

            bible_id = bible_manager.create_series_bible(
                script_id=str(script.id),
                title=title,
                description=description,
            )

            return {
                "script_id": script_id,
                "bible_id": bible_id,
                "title": title,
                "created": True,
            }

    async def create_character_profile(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a character profile."""
        script_id = args.get("script_id")
        character_name = args.get("character_name")
        profile_data = args.get("profile", {})

        if not script_id or not character_name:
            raise ValueError("script_id and character_name are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Create character profile
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_manager = ScriptBibleOperations(connection)

            # TODO: Need to get character_id from character_name
            # For now, use a placeholder implementation
            profile_id = bible_manager.create_character_profile(
                character_id="placeholder",  # TODO: Look up character ID
                script_id=str(script.id),
                **profile_data,
            )

            return {
                "script_id": script_id,
                "character_name": character_name,
                "profile_id": profile_id,
                "created": True,
            }

    async def add_world_element(self, args: dict[str, Any]) -> dict[str, Any]:
        """Add a world-building element."""
        script_id = args.get("script_id")
        element_type = args.get("element_type")
        name = args.get("name")
        description = args.get("description", "")
        properties = args.get("properties", {})

        if not script_id or not element_type or not name:
            raise ValueError("script_id, element_type, and name are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Add world element
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_manager = ScriptBibleOperations(connection)

            element_id = bible_manager.create_world_element(
                script_id=str(script.id),
                element_type=element_type,
                name=name,
                description=description,
                properties=properties,
            )

            return {
                "script_id": script_id,
                "element_id": element_id,
                "element_type": element_type,
                "name": name,
                "created": True,
            }

    async def create_timeline_event(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a timeline event."""
        script_id = args.get("script_id")
        event_name = args.get("event_name")
        event_data = args.get("event_data", {})
        scene_ids = args.get("scene_ids", [])

        if not script_id or not event_name:
            raise ValueError("script_id and event_name are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Create timeline event
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_manager = ScriptBibleOperations(connection)

            event_id = bible_manager.add_timeline_event(
                timeline_id="main",  # TODO: Look up proper timeline ID
                script_id=str(script.id),
                event_name=event_name,
                **event_data,
            )

            return {
                "script_id": script_id,
                "event_id": event_id,
                "event_name": event_name,
                "linked_scenes": len(scene_ids),
                "created": True,
            }

    async def add_character_knowledge(self, args: dict[str, Any]) -> dict[str, Any]:
        """Add character knowledge entry."""
        script_id = args.get("script_id")
        character_name = args.get("character_name")
        scene_id = args.get("scene_id")
        knowledge_type = args.get("knowledge_type")
        content = args.get("content")
        _ = args.get("metadata", {})  # TODO: Use metadata when needed

        if not all([script_id, character_name, scene_id, knowledge_type, content]):
            raise ValueError(
                "script_id, character_name, scene_id, knowledge_type, "
                "and content are required"
            )

        # Validate script exists
        if not script_id:
            raise ValueError("script_id is required")
        script = self.server._validate_script_id(script_id)

        # Add knowledge entry
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_manager = ScriptBibleOperations(connection)

            # Find character
            char_query = """
                SELECT id FROM characters
                WHERE script_id = ? AND UPPER(name) LIKE UPPER(?)
                LIMIT 1
            """
            cursor = connection.execute(
                char_query, (str(script.id), f"%{character_name}%")
            )
            char_row = cursor.fetchone()

            if not char_row:
                raise ValueError(f"Character not found: {character_name}")

            knowledge_id = bible_manager.add_character_knowledge(
                character_id=char_row["id"],
                script_id=str(script.id),
                knowledge_type=knowledge_type or "fact",
                knowledge_subject=content or "Unknown",
            )

            return {
                "script_id": script_id,
                "character_name": character_name,
                "knowledge_id": knowledge_id,
                "scene_id": scene_id,
                "knowledge_type": knowledge_type,
                "created": True,
            }
