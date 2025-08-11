"""MCP tool for listing scenes."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import SceneSummary
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import (
    AsyncAPIWrapper,
    format_error_response,
    parse_scene_heading,
)

logger = get_logger(__name__)


class ListScenesInput(BaseModel):
    """Input for listing scenes."""

    script_id: int | None = Field(None, description="Filter by script ID")
    character: str | None = Field(None, description="Filter by character presence")
    location: str | None = Field(None, description="Filter by scene location")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of scenes")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class ListScenesOutput(BaseModel):
    """Output from listing scenes."""

    success: bool
    scenes: list[SceneSummary]
    total_count: int
    has_more: bool
    message: str | None = None


@mcp.tool()
async def scriptrag_list_scenes(
    script_id: int | None = None,
    character: str | None = None,
    location: str | None = None,
    limit: int = 20,
    offset: int = 0,
    ctx: Context | None = None,
) -> ListScenesOutput:
    """List scenes from scripts with filtering options.

    Args:
        script_id: Filter by script ID
        character: Filter by character presence
        location: Filter by scene location
        limit: Maximum number of scenes (1-100)
        offset: Offset for pagination
        ctx: MCP context

    Returns:
        List of scenes matching criteria
    """
    try:
        # Validate inputs
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        if ctx:
            filters = []
            if script_id:
                filters.append(f"script_id={script_id}")
            if character:
                filters.append(f"character={character}")
            if location:
                filters.append(f"location={location}")
            filter_str = ", ".join(filters) if filters else "no filters"
            await ctx.info(
                f"Listing scenes ({filter_str}, limit={limit}, offset={offset})"
            )

        # Use Database Operations API
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get scenes based on filters
        if script_id:
            all_scenes = await wrapper.run_sync(db_ops.get_scenes_by_script, script_id)
        else:
            # Get all scenes from all scripts
            all_scenes = await wrapper.run_sync(db_ops.get_all_scenes)

        # Apply additional filters
        filtered_scenes = []
        for scene in all_scenes:
            # Filter by character if specified
            if character:
                scene_characters = getattr(scene, "characters", [])
                if character.upper() not in [c.upper() for c in scene_characters]:
                    continue

            # Filter by location if specified
            if location:
                scene_info = parse_scene_heading(scene.heading)
                scene_location = scene_info.get("location", "")
                if location.lower() not in scene_location.lower():
                    continue

            filtered_scenes.append(scene)

        # Apply pagination
        total_count = len(filtered_scenes)
        paginated_scenes = filtered_scenes[offset : offset + limit]

        # Convert to MCP models
        scene_summaries = []
        for scene in paginated_scenes:
            scene_info = parse_scene_heading(scene.heading)
            characters = getattr(scene, "characters", [])

            scene_summaries.append(
                SceneSummary(
                    scene_id=scene.id,
                    script_id=scene.script_id,
                    scene_number=scene.scene_number,
                    heading=scene.heading,
                    location=scene_info.get("location"),
                    time_of_day=scene_info.get("time_of_day"),
                    character_count=len(characters),
                    dialogue_count=getattr(scene, "dialogue_count", 0),
                )
            )

        has_more = (offset + limit) < total_count

        if ctx:
            await ctx.info(
                f"Found {len(scene_summaries)} scenes (total: {total_count})"
            )

        return ListScenesOutput(
            success=True,
            scenes=scene_summaries,
            total_count=total_count,
            has_more=has_more,
            message=f"Found {total_count} scenes",
        )

    except Exception as e:
        logger.error("Failed to list scenes", error=str(e))
        error_response = format_error_response(e, "scriptrag_list_scenes")
        return ListScenesOutput(
            success=False,
            scenes=[],
            total_count=0,
            has_more=False,
            message=error_response["message"],
        )
