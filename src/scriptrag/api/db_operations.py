"""Database operations module for ScriptRAG API."""

import contextlib
from typing import Any
from uuid import UUID

from scriptrag import ScriptRAG
from scriptrag.config import ScriptRAGSettings, get_settings
from scriptrag.database.operations import GraphOperations, SceneOrderType
from scriptrag.models import Scene, Script


class DatabaseOperations:
    """Database operations handler for the API."""

    def __init__(self, config: ScriptRAGSettings | None = None):
        """Initialize database operations."""
        self.config = config or get_settings()
        self.scriptrag = ScriptRAG(config=self.config)
        self._graph_ops: GraphOperations | None = None

    async def initialize(self) -> None:
        """Initialize database connections."""
        await self.scriptrag.initialize()
        # Get graph operations if available
        if hasattr(self.scriptrag, "_graph_ops"):
            self._graph_ops = self.scriptrag._graph_ops

    async def cleanup(self) -> None:
        """Clean up database connections."""
        await self.scriptrag.cleanup()

    # Script operations
    async def list_scripts(self) -> list[Script]:
        """List all scripts."""
        return await self.scriptrag.list_scripts()

    async def get_script(self, script_id: str) -> Script | None:
        """Get a script by ID."""
        return await self.scriptrag.get_script(script_id)

    async def create_script(
        self,
        title: str,
        author: str | None = None,
        description: str | None = None,
        genre: str | None = None,
    ) -> Script:
        """Create a new script."""
        return await self.scriptrag.create_script(title, author, description, genre)

    async def update_script(
        self,
        script_id: str,
        title: str | None = None,
        author: str | None = None,
        description: str | None = None,
        genre: str | None = None,
    ) -> bool:
        """Update script metadata."""
        script = await self.get_script(script_id)
        if not script:
            return False

        # Update fields
        if title is not None:
            script.title = title
        if author is not None:
            script.author = author
        if description is not None:
            script.description = description
        if genre is not None:
            script.genre = genre

        # Save changes
        return await self.scriptrag.update_script(script)

    async def delete_script(self, script_id: str) -> bool:
        """Delete a script."""
        return await self.scriptrag.delete_script(script_id)

    # Scene operations
    async def list_scenes(self, script_id: str) -> list[Scene]:
        """List scenes for a script."""
        return await self.scriptrag.list_scenes(script_id)

    async def get_scene(self, scene_id: str) -> Scene | None:
        """Get a scene by ID."""
        return await self.scriptrag.get_scene(scene_id)

    async def create_scene(
        self,
        script_id: str,
        scene_number: int,
        heading: str,
        content: str | None = None,
    ) -> Scene:
        """Create a new scene."""
        return await self.scriptrag.create_scene(
            script_id, scene_number, heading, content
        )

    async def update_scene(
        self,
        scene_id: str,
        scene_number: int | None = None,
        heading: str | None = None,
        content: str | None = None,
    ) -> bool:
        """Update scene information."""
        scene = await self.get_scene(scene_id)
        if not scene:
            return False

        # Update fields
        if scene_number is not None:
            scene.script_order = scene_number
        if heading is not None:
            scene.heading = heading
        if content is not None:
            scene.description = content

        # Save changes
        return await self.scriptrag.update_scene(scene)

    async def delete_scene(self, scene_id: str) -> bool:
        """Delete a scene."""
        return await self.scriptrag.delete_scene(scene_id)

    # Character operations
    async def list_characters(self, script_id: str) -> list[Any]  # noqa: ARG002:
        """List characters in a script."""
        # This would need implementation in ScriptRAG
        return []

    async def get_character(self, character_id: str) -> Any  # noqa: ARG002 | None:
        """Get a character by ID."""
        # This would need implementation in ScriptRAG
        return None

    # Search operations
    async def search_scenes(
        self,
        script_id: str,
        query: str,
        search_type: str = "content",
        limit: int = 10,
    ) -> list[Scene]:
        """Search scenes in a script."""
        # This would need proper implementation
        all_scenes = await self.list_scenes(script_id)
        query_lower = query.lower()

        results = []
        for scene in all_scenes:
            if search_type == "content":
                if scene.description and query_lower in scene.description.lower():
                    results.append(scene)
            elif search_type == "heading":
                if query_lower in scene.heading.lower():
                    results.append(scene)
            elif search_type == "all":
                if query_lower in scene.heading.lower() or (
                    scene.description and query_lower in scene.description.lower()
                ):
                    results.append(scene)

            if len(results) >= limit:
                break

        return results

    # Graph operations
    async def build_knowledge_graph(self, script_id: str) -> dict[str, Any]:
        """Build knowledge graph for a script."""
        if not self._graph_ops:
            raise RuntimeError("Graph operations not available")

        # This would need proper implementation
        return {"status": "success", "nodes": 0, "edges": 0}

    async def get_character_graph(self, script_id: str) -> dict[str, Any]:
        """Get character relationship graph."""
        if not self._graph_ops:
            raise RuntimeError("Graph operations not available")

        # This would need proper implementation
        return {"nodes": [], "edges": []}

    async def get_scene_graph(self, script_id: str) -> dict[str, Any]:
        """Get scene dependency graph."""
        if not self._graph_ops:
            raise RuntimeError("Graph operations not available")

        # This would need proper implementation
        return {"nodes": [], "edges": []}

    # Analysis operations
    async def analyze_character_arcs(self, script_id: str) -> dict[str, Any]:
        """Analyze character arcs in the script."""
        # This would need proper implementation
        return {"characters": {}}

    async def get_scene_timeline(self, script_id: str) -> list[dict[str, Any]]:
        """Get temporal ordering of scenes."""
        scenes = await self.list_scenes(script_id)
        return [
            {
                "scene_id": str(scene.id),
                "heading": scene.heading,
                "order": scene.script_order,
                "temporal_order": scene.temporal_order,
            }
            for scene in scenes
        ]

    # Mentor operations
    async def get_mentor_feedback(
        self, script_id: str, mentor_type: str
    ) -> dict[str, Any]:
        """Get feedback from a specific mentor."""
        # This would need proper implementation
        return {"mentor": mentor_type, "feedback": []}

    # Import/Export operations
    async def import_fountain(self, content: str, title: str) -> Script:
        """Import a script from Fountain format."""
        # This would need proper implementation
        script = await self.create_script(title)
        # Parse fountain and create scenes...
        return script

    async def export_fountain(self, script_id: str) -> str:
        """Export a script to Fountain format."""
        script = await self.get_script(script_id)
        if not script:
            raise ValueError("Script not found")

        scenes = await self.list_scenes(script_id)

        # Build fountain format
        fountain = f"Title: {script.title}\n"
        if script.author:
            fountain += f"Author: {script.author}\n"
        fountain += "\n"

        for scene in sorted(scenes, key=lambda s: s.script_order):
            fountain += f"\n{scene.heading}\n\n"
            if scene.description:
                fountain += f"{scene.description}\n"

        return fountain

    # Embedding operations
    async def generate_scene_embeddings(self, script_id: str) -> int:
        """Generate embeddings for all scenes in a script."""
        if not self._graph_ops:
            raise RuntimeError("Graph operations not available")

        # This would need proper implementation
        return 0

    async def find_similar_scenes(
        self, scene_id: str, limit: int = 5
    ) -> list[tuple[Scene, float]]:
        """Find scenes similar to a given scene."""
        if not self._graph_ops:
            raise RuntimeError("Graph operations not available")

        # This would need proper implementation
        return []

    # Bible operations
    async def get_script_bible(self, script_id: str) -> dict[str, Any]:
        """Get the script bible."""
        # This would need proper implementation
        return {
            "characters": [],
            "locations": [],
            "themes": [],
            "style_guide": {},
        }

    async def update_script_bible(
        self, script_id: str, bible_data: dict[str, Any]
    ) -> bool:
        """Update the script bible."""
        # This would need proper implementation
        return True

    # Validation operations
    async def validate_continuity(self, script_id: str) -> dict[str, Any]:
        """Validate script continuity."""
        # This would need proper implementation
        return {"issues": [], "warnings": []}

    async def check_formatting(self, script_id: str) -> dict[str, Any]:
        """Check script formatting."""
        # This would need proper implementation
        return {"errors": [], "warnings": []}

    # New Phase 5 Operations

    async def reorder_scenes(
        self,
        script_id: str,
        scene_ids: list[str],
        order_type: str = "script",
    ) -> bool:
        """Reorder scenes based on specified criteria."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert order_type string to enum
        try:
            order_type_enum = SceneOrderType(order_type)
        except ValueError:
            # Log error - invalid order type
            logger.error(f"Invalid order type: {order_type}")
            return False

        return self._graph_ops.reorder_scenes(script_id, order_type_enum, scene_ids)

    async def infer_temporal_order(self, script_id: str) -> dict[str, int]:
        """Infer temporal (chronological) order of scenes."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # This would use the graph operations to analyze scene content
        # and infer temporal relationships
        scenes = await self.list_scenes(script_id)
        # For now, return script order as temporal order
        return {str(scene.id): scene.script_order for scene in scenes}

    async def get_scene_dependencies(
        self,
        scene_id: str,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get dependencies for a specific scene."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Use ordering.get_scene_dependencies which supports direction parameter
        # and already returns the dict format expected by the API
        return self._graph_ops.ordering.get_scene_dependencies(scene_id, direction)

    async def calculate_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order based on dependencies."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        return self._graph_ops.calculate_logical_order(script_id)

    async def validate_scene_ordering(self, script_id: str) -> dict[str, Any]:
        """Validate consistency across different ordering systems."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        return self._graph_ops.validate_scene_ordering(script_id)

    # Enhanced Scene Operations for Phase 5.2
    async def update_scene_with_graph_propagation(
        self,
        scene_id: str,
        scene_number: int | None = None,
        heading: str | None = None,
        content: str | None = None,
        location: str | None = None,
        time_of_day: str | None = None,
    ) -> bool:
        """Update scene with enhanced graph propagation."""
        # First update basic fields using existing method
        if scene_number is not None or heading is not None or content is not None:
            success = await self.update_scene(scene_id, scene_number, heading, content)
            if not success:
                return False

        # Graph operations are optional - if they fail, we still consider
        # the update successful since the database was updated
        if self._graph_ops:
            # Note: scene_id is the database UUID, not the graph node ID
            # The graph operations will fail if the scene doesn't have a graph node
            with contextlib.suppress(Exception):
                metadata = {}
                if heading is not None:
                    metadata["heading"] = heading
                if content is not None:
                    metadata["description"] = content
                if time_of_day is not None:
                    metadata["time_of_day"] = time_of_day
                if location is not None:
                    metadata["location"] = location
                if metadata:  # Only call if we have metadata to update
                    self._graph_ops.update_scene_metadata(scene_id, metadata)

        # Always return True if we got this far - the database update succeeded
        return True

    async def delete_scene_with_references(self, scene_id: str) -> bool:
        """Delete scene with reference maintenance."""
        # First delete from database
        await self.delete_scene(scene_id)

        # Then try to delete from graph if available
        if self._graph_ops:
            with contextlib.suppress(Exception):
                self._graph_ops.delete_scene_with_references(scene_id)

        return True

    async def inject_scene_at_position(
        self,
        script_id: str,
        scene_data: Any,  # SceneCreateRequest
        position: int,
    ) -> str | None:
        """Inject scene at specific position with full re-indexing."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert script_id to script_node_id
        # This assumes script_id is the same as script_node_id
        # In a real implementation, you might need to query for the script node
        from uuid import uuid4

        from scriptrag.models import Scene

        # Use the scene ID from scene_data if provided, otherwise generate new
        scene_id = getattr(scene_data, "id", None)
        if scene_id and isinstance(scene_id, str):
            # Convert string UUID to UUID object
            scene_uuid = UUID(scene_id)
        else:
            # Generate new UUID if not provided
            scene_uuid = uuid4()

        scene = Scene(
            id=scene_uuid,
            heading=scene_data.heading,
            description=scene_data.content,
            script_order=scene_data.scene_number,
            script_id=UUID(script_id),
        )

        return self._graph_ops.inject_scene_at_position(scene, script_id, position)

    async def update_scene_metadata(
        self,
        scene_id: str,
        heading: str | None = None,
        description: str | None = None,
        time_of_day: str | None = None,
        location: str | None = None,
    ) -> bool:
        """Update scene metadata with optional graph propagation."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        metadata = {}
        if heading is not None:
            metadata["heading"] = heading
        if description is not None:
            metadata["description"] = description
        if time_of_day is not None:
            metadata["time_of_day"] = time_of_day
        if location is not None:
            metadata["location"] = location
        # Note: propagate_to_graph is not supported in the new API

        return self._graph_ops.update_scene_metadata(scene_id, metadata)

    async def validate_story_continuity(self, script_id: str) -> dict[str, Any]:
        """Validate story continuity across all scenes."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert script_id to script_node_id if needed
        return self._graph_ops.validate_story_continuity(script_id)


# Create a singleton instance
_db_ops: DatabaseOperations | None = None


async def get_db_ops() -> DatabaseOperations:
    """Get database operations instance."""
    global _db_ops
    if _db_ops is None:
        _db_ops = DatabaseOperations()
        await _db_ops.initialize()
    return _db_ops


async def cleanup_db_ops() -> None:
    """Clean up database operations."""
    global _db_ops
    if _db_ops is not None:
        await _db_ops.cleanup()
        _db_ops = None


# Import logger after DatabaseOperations is defined to avoid circular imports
from scriptrag.config import get_logger

logger = get_logger(__name__)
