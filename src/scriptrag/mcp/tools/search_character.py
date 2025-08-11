"""MCP tool for searching character appearances."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.search import SearchAPI
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import CharacterAppearance, CharacterInfo
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class SearchCharacterInput(BaseModel):
    """Input for searching character appearances."""

    character_name: str = Field(..., description="Character name to search for")
    include_mentions: bool = Field(True, description="Include action line mentions")
    script_id: int | None = Field(None, description="Filter by script")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")


class SearchCharacterOutput(BaseModel):
    """Output from searching character appearances."""

    success: bool
    character: CharacterInfo | None = None
    appearances: list[CharacterAppearance]
    total_scenes: int
    total_lines: int
    message: str | None = None


@mcp.tool()
async def scriptrag_search_character(
    character_name: str,
    include_mentions: bool = True,
    script_id: int | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> SearchCharacterOutput:
    """Search for character appearances and mentions.

    Args:
        character_name: Character name to search for
        include_mentions: Include action line mentions
        script_id: Filter by script
        limit: Maximum results (1-100)
        ctx: MCP context

    Returns:
        Character appearances and statistics
    """
    try:
        # Validate inputs
        limit = max(1, min(100, limit))
        character_name = character_name.strip().upper()

        if ctx:
            filters = []
            if script_id:
                filters.append(f"script_id={script_id}")
            if include_mentions:
                filters.append("include_mentions=true")
            filter_str = f" with {', '.join(filters)}" if filters else ""
            await ctx.info(f"Searching for character '{character_name}'{filter_str}")

        # Use Search API
        settings = get_settings()
        search_api = SearchAPI(settings)
        wrapper = AsyncAPIWrapper()

        # Build search parameters
        search_params = {
            "query": character_name,
            "search_type": "character",
            "limit": limit,
            "include_mentions": include_mentions,
        }

        if script_id:
            search_params["script_id"] = script_id

        # Perform the search
        search_results = await wrapper.run_sync(search_api.search, **search_params)

        # Extract character info
        character_data = search_results.get("character_info", {})
        character_info = None
        if character_data:
            character_info = CharacterInfo(
                name=character_data.get("name", character_name),
                total_dialogue_lines=character_data.get("total_lines", 0),
                total_scenes=character_data.get("total_scenes", 0),
                first_appearance=character_data.get("first_appearance"),
                last_appearance=character_data.get("last_appearance"),
            )

        # Convert appearances to MCP models
        appearances = []
        total_lines = 0
        scene_ids = set()

        for result in search_results.get("appearances", []):
            scene_id = result.get("scene_id", 0)
            dialogue_count = result.get("dialogue_count", 0)

            appearances.append(
                CharacterAppearance(
                    scene_id=scene_id,
                    scene_number=result.get("scene_number", 0),
                    scene_heading=result.get("scene_heading", ""),
                    dialogue_count=dialogue_count,
                    is_speaking=dialogue_count > 0,
                )
            )

            scene_ids.add(scene_id)
            total_lines += dialogue_count

        total_scenes = len(scene_ids)

        if ctx:
            await ctx.info(
                f"Found {len(appearances)} appearances for '{character_name}' in {total_scenes} scenes"
            )

        return SearchCharacterOutput(
            success=True,
            character=character_info,
            appearances=appearances[:limit],  # Apply limit
            total_scenes=total_scenes,
            total_lines=total_lines,
            message=f"Found {len(appearances)} appearances in {total_scenes} scenes",
        )

    except Exception as e:
        logger.error("Failed to search character", error=str(e))
        error_response = format_error_response(e, "scriptrag_search_character")
        return SearchCharacterOutput(
            success=False,
            appearances=[],
            total_scenes=0,
            total_lines=0,
            message=error_response["message"],
        )
