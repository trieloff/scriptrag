"""MCP resource for character information."""

import json

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper

logger = get_logger(__name__)


@mcp.resource("scriptrag://characters/{character_name}")
async def get_character_resource(character_name: str) -> str:
    """Get character information across all scripts.

    Args:
        character_name: Character name

    Returns:
        Character information as JSON
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        character_name = character_name.upper()

        # Get character data across all scripts
        character_data = await wrapper.run_sync(
            db_ops.get_character_by_name, character_name
        )

        if not character_data:
            return json.dumps({"error": f"Character '{character_name}' not found"})

        # Get all scenes with this character
        scenes = await wrapper.run_sync(
            db_ops.get_scenes_with_character, character_name
        )

        # Calculate statistics
        dialogue_lines = getattr(character_data, "dialogue_lines", [])
        word_counts = [len(line.split()) for line in dialogue_lines]

        character_info = {
            "name": character_name,
            "statistics": {
                "total_scenes": len(scenes),
                "total_dialogue_lines": len(dialogue_lines),
                "total_words": sum(word_counts) if word_counts else 0,
                "average_words_per_line": (
                    sum(word_counts) / len(word_counts) if word_counts else 0
                ),
            },
            "scene_appearances": [
                {
                    "scene_id": scene.id,
                    "script_id": scene.script_id,
                    "scene_number": scene.scene_number,
                    "heading": scene.heading,
                }
                for scene in scenes[:10]  # Limit to first 10 scenes
            ],
            "metadata": getattr(character_data, "metadata", None),
        }

        return json.dumps(character_info, indent=2)

    except Exception as e:
        logger.error(f"Failed to get character resource {character_name}", error=str(e))
        return json.dumps({"error": str(e)})


@mcp.resource("scriptrag://characters/{character_name}/script/{script_id}")
async def get_character_in_script(character_name: str, script_id: str) -> str:
    """Get character information for a specific script.

    Args:
        character_name: Character name
        script_id: Script database ID

    Returns:
        Character information as JSON
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        character_name = character_name.upper()

        # Get character data for specific script
        character_data = await wrapper.run_sync(
            db_ops.get_character_by_name, character_name, int(script_id)
        )

        if not character_data:
            return json.dumps(
                {
                    "error": f"Character '{character_name}' not found in script {script_id}"
                }
            )

        # Get scenes with this character in this script
        scenes = await wrapper.run_sync(
            db_ops.get_scenes_with_character, character_name, int(script_id)
        )

        # Get dialogue lines
        dialogue_lines = []
        for scene in scenes:
            if hasattr(scene, "content"):
                lines = scene.content.split("\n")
                current_character = None
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.upper() == character_name:
                        current_character = character_name
                    elif (
                        current_character == character_name
                        and line_stripped
                        and not line_stripped.startswith("(")
                    ):
                        dialogue_lines.append(
                            {
                                "scene_id": scene.id,
                                "scene_number": scene.scene_number,
                                "text": line_stripped,
                            }
                        )

        # Calculate statistics
        word_counts = [len(d["text"].split()) for d in dialogue_lines]

        character_info = {
            "name": character_name,
            "script_id": int(script_id),
            "statistics": {
                "scene_count": len(scenes),
                "dialogue_count": len(dialogue_lines),
                "total_words": sum(word_counts) if word_counts else 0,
                "average_words_per_line": (
                    sum(word_counts) / len(word_counts) if word_counts else 0
                ),
            },
            "scenes": [
                {
                    "scene_id": scene.id,
                    "scene_number": scene.scene_number,
                    "heading": scene.heading,
                }
                for scene in scenes
            ],
            "sample_dialogue": dialogue_lines[:5],  # First 5 lines as sample
            "metadata": getattr(character_data, "metadata", None),
        }

        return json.dumps(character_info, indent=2)

    except Exception as e:
        logger.error(
            f"Failed to get character {character_name} in script {script_id}",
            error=str(e),
        )
        return json.dumps({"error": str(e)})


@mcp.resource("scriptrag://characters/{character_name}/dialogue")
async def get_character_dialogue(character_name: str) -> str:
    """Get all dialogue for a character.

    Args:
        character_name: Character name

    Returns:
        Character dialogue as formatted text
    """
    try:
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        character_name = character_name.upper()

        # Get all scenes with this character
        scenes = await wrapper.run_sync(
            db_ops.get_scenes_with_character, character_name
        )

        if not scenes:
            return f"No dialogue found for character '{character_name}'"

        # Extract all dialogue
        dialogue_parts = [f"DIALOGUE FOR {character_name}\n{'=' * 40}\n"]

        for scene in scenes:
            if hasattr(scene, "content"):
                lines = scene.content.split("\n")
                current_character = None
                scene_dialogue = []

                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.upper() == character_name:
                        current_character = character_name
                    elif (
                        current_character == character_name
                        and line_stripped
                        and not line_stripped.startswith("(")
                    ):
                        scene_dialogue.append(line_stripped)

                if scene_dialogue:
                    dialogue_parts.append(
                        f"\nScene {scene.scene_number}: {scene.heading}"
                    )
                    dialogue_parts.append("-" * 40)
                    for line in scene_dialogue:
                        dialogue_parts.append(f"  {line}")

        return "\n".join(dialogue_parts)

    except Exception as e:
        logger.error(f"Failed to get dialogue for {character_name}", error=str(e))
        return f"Error retrieving dialogue for {character_name}: {e!s}"
