"""MCP tool for getting scene details."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import DialogueLine, SceneDetail
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import (
    AsyncAPIWrapper,
    format_error_response,
    parse_scene_heading,
)

logger = get_logger(__name__)


class GetSceneInput(BaseModel):
    """Input for getting scene details."""

    scene_id: int = Field(..., description="Scene database ID")
    include_dialogue: bool = Field(True, description="Include dialogue breakdown")
    include_analysis: bool = Field(False, description="Include scene analysis results")


class GetSceneOutput(BaseModel):
    """Output from getting scene details."""

    success: bool
    scene: SceneDetail | None = None
    dialogue_lines: list[DialogueLine] = []
    action_lines: list[str] = []
    analysis_results: dict | None = None
    message: str | None = None


@mcp.tool()
async def scriptrag_get_scene(
    scene_id: int,
    include_dialogue: bool = True,
    include_analysis: bool = False,
    ctx: Context | None = None,
) -> GetSceneOutput:
    """Get detailed scene content and metadata.

    Args:
        scene_id: Scene database ID
        include_dialogue: Include dialogue breakdown
        include_analysis: Include scene analysis results
        ctx: MCP context

    Returns:
        Detailed scene information with optional dialogue and analysis
    """
    try:
        if ctx:
            await ctx.info(
                f"Getting scene {scene_id} (dialogue={include_dialogue}, analysis={include_analysis})"
            )

        # Use Database Operations API
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get the scene
        scene = await wrapper.run_sync(db_ops.get_scene_by_id, scene_id)
        if not scene:
            return GetSceneOutput(
                success=False,
                message=f"Scene with ID {scene_id} not found",
            )

        # Parse scene heading for location and time
        scene_info = parse_scene_heading(scene.heading)

        # Get characters from scene
        characters = getattr(scene, "characters", [])

        # Create scene detail
        scene_detail = SceneDetail(
            scene_id=scene.id,
            script_id=scene.script_id,
            scene_number=scene.scene_number,
            heading=scene.heading,
            location=scene_info.get("location"),
            time_of_day=scene_info.get("time_of_day"),
            content=scene.content if hasattr(scene, "content") else "",
            characters=characters,
            metadata=getattr(scene, "metadata", None),
        )

        # Extract dialogue and action lines if requested
        dialogue_lines = []
        action_lines = []

        if include_dialogue and hasattr(scene, "content"):
            # Parse the scene content to extract dialogue and action
            lines = scene.content.split("\n")
            current_character = None
            line_number = 0

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_number += 1

                # Check if it's a character name (usually uppercase)
                if (
                    line.isupper()
                    and not line.startswith("(")
                    and len(line.split()) <= 3
                ):
                    current_character = line
                elif current_character and not line.startswith("("):
                    # This is dialogue
                    dialogue_lines.append(
                        DialogueLine(
                            character=current_character,
                            text=line,
                            line_number=line_number,
                        )
                    )
                elif not line.isupper() and not line.startswith("("):
                    # This is likely action
                    action_lines.append(line)

        # Get analysis results if requested
        analysis_results = None
        if include_analysis:
            # Get any stored analysis results for this scene
            analysis_results = await wrapper.run_sync(
                db_ops.get_scene_analysis, scene_id
            )
            if not analysis_results:
                analysis_results = {
                    "message": "No analysis results available for this scene"
                }

        if ctx:
            dialogue_count = len(dialogue_lines)
            action_count = len(action_lines)
            await ctx.info(
                f"Retrieved scene {scene.scene_number} with {dialogue_count} dialogue lines and {action_count} action lines"
            )

        return GetSceneOutput(
            success=True,
            scene=scene_detail,
            dialogue_lines=dialogue_lines,
            action_lines=action_lines,
            analysis_results=analysis_results,
            message=f"Retrieved scene {scene.scene_number}: {scene.heading}",
        )

    except Exception as e:
        logger.error("Failed to get scene", error=str(e))
        error_response = format_error_response(e, "scriptrag_get_scene")
        return GetSceneOutput(success=False, message=error_response["message"])
