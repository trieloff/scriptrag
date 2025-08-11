"""MCP resource for script content."""

import json

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, truncate_content

logger = get_logger(__name__)


@mcp.resource("scriptrag://scripts/{script_id}")
async def get_script_resource(script_id: str) -> str:
    """Get full script content.

    Args:
        script_id: Script database ID

    Returns:
        Script content in Fountain format
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get the script
        script = await wrapper.run_sync(db_ops.get_script_by_id, int(script_id))
        if not script:
            return f"Script with ID {script_id} not found"

        # Return the script content
        content = getattr(script, "content", "")
        if not content:
            # If no full content, try to reconstruct from scenes
            scenes = await wrapper.run_sync(db_ops.get_scenes_by_script, int(script_id))
            if scenes:
                scene_contents = []
                for scene in scenes:
                    scene_contents.append(f"\n{scene.heading}\n")
                    if hasattr(scene, "content"):
                        scene_contents.append(scene.content)
                content = "\n".join(scene_contents)
            else:
                content = f"No content available for script '{script.title}'"

        # Truncate if too long
        content, was_truncated = truncate_content(content, max_length=10000)
        if was_truncated:
            logger.warning(f"Script {script_id} content was truncated")

        return content

    except Exception as e:
        logger.error(f"Failed to get script resource {script_id}", error=str(e))
        return f"Error retrieving script {script_id}: {e!s}"


@mcp.resource("scriptrag://scripts/{script_id}/metadata")
async def get_script_metadata(script_id: str) -> str:
    """Get script metadata in JSON format.

    Args:
        script_id: Script database ID

    Returns:
        Script metadata as JSON
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get the script
        script = await wrapper.run_sync(db_ops.get_script_by_id, int(script_id))
        if not script:
            return json.dumps({"error": f"Script with ID {script_id} not found"})

        # Get scenes and characters
        scenes = await wrapper.run_sync(db_ops.get_scenes_by_script, int(script_id))
        characters = await wrapper.run_sync(
            db_ops.get_characters_by_script, int(script_id)
        )

        metadata = {
            "script_id": script.id,
            "title": script.title,
            "file_path": script.file_path,
            "scene_count": len(scenes),
            "character_count": len(characters),
            "characters": [char.name for char in characters],
            "created_at": str(script.created_at),
            "updated_at": str(script.updated_at) if script.updated_at else None,
            "metadata": script.metadata,
        }

        return json.dumps(metadata, indent=2)

    except Exception as e:
        logger.error(f"Failed to get script metadata {script_id}", error=str(e))
        return json.dumps({"error": str(e)})
