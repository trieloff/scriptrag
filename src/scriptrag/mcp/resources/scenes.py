"""MCP resource for scene content."""

import json

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, parse_scene_heading

logger = get_logger(__name__)


@mcp.resource("scriptrag://scenes/{scene_id}")
async def get_scene_resource(scene_id: str) -> str:
    """Get individual scene content.

    Args:
        scene_id: Scene database ID

    Returns:
        Scene content in Fountain format
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get the scene
        scene = await wrapper.run_sync(db_ops.get_scene_by_id, int(scene_id))
        if not scene:
            return f"Scene with ID {scene_id} not found"

        # Format the scene content
        content_parts = [f"{scene.heading}\n"]
        if hasattr(scene, "content"):
            content_parts.append(scene.content)
        else:
            content_parts.append("(Scene content not available)")

        return "\n".join(content_parts)

    except Exception as e:
        logger.error(f"Failed to get scene resource {scene_id}", error=str(e))
        return f"Error retrieving scene {scene_id}: {e!s}"


@mcp.resource("scriptrag://scenes/{scene_id}/analysis")
async def get_scene_analysis(scene_id: str) -> str:
    """Get scene analysis data in JSON format.

    Args:
        scene_id: Scene database ID

    Returns:
        Scene analysis as JSON
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get the scene
        scene = await wrapper.run_sync(db_ops.get_scene_by_id, int(scene_id))
        if not scene:
            return json.dumps({"error": f"Scene with ID {scene_id} not found"})

        # Parse scene info
        scene_info = parse_scene_heading(scene.heading)

        # Extract dialogue and action statistics
        dialogue_count = 0
        action_count = 0
        characters = set()

        if hasattr(scene, "content"):
            lines = scene.content.split("\n")
            current_character = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if it's a character name
                if (
                    line.isupper()
                    and not line.startswith("(")
                    and len(line.split()) <= 3
                ):
                    current_character = line
                    characters.add(line)
                elif current_character and not line.startswith("("):
                    dialogue_count += 1
                elif not line.isupper() and not line.startswith("("):
                    action_count += 1

        analysis = {
            "scene_id": scene.id,
            "script_id": scene.script_id,
            "scene_number": scene.scene_number,
            "heading": scene.heading,
            "location": scene_info.get("location"),
            "time_of_day": scene_info.get("time_of_day"),
            "setting": scene_info.get("setting"),
            "statistics": {
                "dialogue_lines": dialogue_count,
                "action_lines": action_count,
                "character_count": len(characters),
                "characters": sorted(characters),
            },
            "metadata": getattr(scene, "metadata", None),
        }

        # Get any stored analysis results
        analysis_results = await wrapper.run_sync(
            db_ops.get_scene_analysis, int(scene_id)
        )
        if analysis_results:
            analysis["analysis_results"] = analysis_results

        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Failed to get scene analysis {scene_id}", error=str(e))
        return json.dumps({"error": str(e)})
