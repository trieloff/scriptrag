"""MCP tool for listing characters."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import CharacterSummary, ScriptInfo
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class ListCharactersInput(BaseModel):
    """Input for listing characters."""

    script_id: int | None = Field(None, description="Filter by script")
    min_lines: int = Field(1, ge=1, description="Minimum dialogue lines")
    sort_by: str = Field(
        "name", description="Sort by: name, lines, scenes, or appearances"
    )
    limit: int = Field(50, ge=1, le=200, description="Maximum results")


class ListCharactersOutput(BaseModel):
    """Output from listing characters."""

    success: bool
    characters: list[CharacterSummary]
    total_count: int
    script_info: ScriptInfo | None = None
    message: str | None = None


@mcp.tool()
async def scriptrag_list_characters(
    script_id: int | None = None,
    min_lines: int = 1,
    sort_by: str = "name",
    limit: int = 50,
    ctx: Context | None = None,
) -> ListCharactersOutput:
    """List all characters with statistics.

    Args:
        script_id: Filter by script
        min_lines: Minimum dialogue lines (default: 1)
        sort_by: Sort by name, lines, scenes, or appearances
        limit: Maximum results (1-200)
        ctx: MCP context

    Returns:
        List of characters with statistics
    """
    try:
        # Validate inputs
        limit = max(1, min(200, limit))
        min_lines = max(1, min_lines)
        valid_sort_fields = ["name", "lines", "scenes", "appearances"]
        if sort_by not in valid_sort_fields:
            sort_by = "name"

        if ctx:
            filters = []
            if script_id:
                filters.append(f"script_id={script_id}")
            filters.append(f"min_lines={min_lines}")
            filter_str = ", ".join(filters)
            await ctx.info(f"Listing characters ({filter_str}, sort={sort_by})")

        # Use Database Operations API
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get characters based on filters
        if script_id:
            characters_data = await wrapper.run_sync(
                db_ops.get_characters_by_script, script_id
            )
            # Get script info
            script = await wrapper.run_sync(db_ops.get_script_by_id, script_id)
            script_info = (
                ScriptInfo(
                    script_id=script.id,
                    title=script.title,
                    total_scenes=getattr(script, "scene_count", 0),
                    total_characters=len(characters_data),
                )
                if script
                else None
            )
        else:
            characters_data = await wrapper.run_sync(db_ops.get_all_characters)
            script_info = None

        # Convert to character summaries with statistics
        character_summaries = []
        for char_data in characters_data:
            dialogue_count = getattr(char_data, "dialogue_count", 0)
            scene_count = getattr(char_data, "scene_count", 0)

            # Apply minimum lines filter
            if dialogue_count < min_lines:
                continue

            character_summaries.append(
                CharacterSummary(
                    name=char_data.name,
                    dialogue_count=dialogue_count,
                    scene_count=scene_count,
                    first_appearance_scene=getattr(char_data, "first_appearance", None),
                    last_appearance_scene=getattr(char_data, "last_appearance", None),
                )
            )

        # Sort characters based on sort_by parameter
        if sort_by == "lines":
            character_summaries.sort(key=lambda x: x.dialogue_count, reverse=True)
        elif sort_by == "scenes":
            character_summaries.sort(key=lambda x: x.scene_count, reverse=True)
        elif sort_by == "appearances":
            # Sort by total appearances (scenes)
            character_summaries.sort(key=lambda x: x.scene_count, reverse=True)
        else:  # name
            character_summaries.sort(key=lambda x: x.name)

        # Apply limit
        total_count = len(character_summaries)
        character_summaries = character_summaries[:limit]

        if ctx:
            await ctx.info(
                f"Found {len(character_summaries)} characters (total: {total_count})"
            )

        return ListCharactersOutput(
            success=True,
            characters=character_summaries,
            total_count=total_count,
            script_info=script_info,
            message=f"Found {total_count} characters",
        )

    except Exception as e:
        logger.error("Failed to list characters", error=str(e))
        error_response = format_error_response(e, "scriptrag_list_characters")
        return ListCharactersOutput(
            success=False,
            characters=[],
            total_count=0,
            message=error_response["message"],
        )
