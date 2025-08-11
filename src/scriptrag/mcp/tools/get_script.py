"""MCP tool for getting script details."""

from pathlib import Path

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import SceneSummary, ScriptDetail
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class GetScriptInput(BaseModel):
    """Input for getting script details."""

    script_id: int | None = Field(None, description="Script database ID")
    title: str | None = Field(None, description="Script title")
    file_path: str | None = Field(None, description="Original file path")


class GetScriptOutput(BaseModel):
    """Output from getting script details."""

    success: bool
    script: ScriptDetail | None = None
    scenes: list[SceneSummary] = []
    character_count: int = 0
    total_scenes: int = 0
    message: str | None = None


@mcp.tool()
async def scriptrag_get_script(
    script_id: int | None = None,
    title: str | None = None,
    file_path: str | None = None,
    ctx: Context | None = None,
) -> GetScriptOutput:
    """Get detailed information about a specific script.

    Args:
        script_id: Script database ID
        title: Script title
        file_path: Original file path
        ctx: MCP context

    Returns:
        Detailed script information with scenes
    """
    try:
        # Validate that at least one identifier is provided
        if not any([script_id, title, file_path]):
            return GetScriptOutput(
                success=False,
                message="Must provide either script_id, title, or file_path",
            )

        if ctx:
            await ctx.info(f"Getting script details (id={script_id}, title={title})")

        # Use Database Operations API
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Find the script
        script_record = None
        if script_id:
            script_record = await wrapper.run_sync(db_ops.get_script_by_id, script_id)
        elif title:
            scripts = await wrapper.run_sync(db_ops.get_scripts_by_title, title)
            if scripts:
                script_record = scripts[0]
        elif file_path:
            path = Path(file_path)
            scripts = await wrapper.run_sync(db_ops.get_scripts_by_path, str(path))
            if scripts:
                script_record = scripts[0]

        if not script_record:
            return GetScriptOutput(
                success=False,
                message="Script not found with provided criteria",
            )

        # Convert to MCP model
        script_detail = ScriptDetail(
            script_id=script_record.id,
            title=script_record.title,
            file_path=script_record.file_path,
            content_hash=script_record.content_hash,
            metadata=script_record.metadata,
            created_at=str(script_record.created_at),
            updated_at=str(script_record.updated_at)
            if script_record.updated_at
            else None,
        )

        # Get scenes for this script
        scenes = await wrapper.run_sync(db_ops.get_scenes_by_script, script_record.id)
        scene_summaries = []
        character_set = set()

        for scene in scenes:
            # Parse characters from scene
            characters = scene.characters if hasattr(scene, "characters") else []
            character_set.update(characters)

            scene_summaries.append(
                SceneSummary(
                    scene_id=scene.id,
                    script_id=scene.script_id,
                    scene_number=scene.scene_number,
                    heading=scene.heading,
                    location=scene.location if hasattr(scene, "location") else None,
                    time_of_day=scene.time_of_day
                    if hasattr(scene, "time_of_day")
                    else None,
                    character_count=len(characters),
                    dialogue_count=getattr(scene, "dialogue_count", 0),
                )
            )

        if ctx:
            await ctx.info(
                f"Retrieved script '{script_record.title}' with {len(scenes)} scenes"
            )

        return GetScriptOutput(
            success=True,
            script=script_detail,
            scenes=scene_summaries,
            character_count=len(character_set),
            total_scenes=len(scenes),
            message=f"Retrieved script '{script_record.title}'",
        )

    except Exception as e:
        logger.error("Failed to get script", error=str(e))
        error_response = format_error_response(e, "scriptrag_get_script")
        return GetScriptOutput(success=False, message=error_response["message"])
