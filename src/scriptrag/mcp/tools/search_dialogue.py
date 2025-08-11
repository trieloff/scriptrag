"""MCP tool for searching dialogue."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.search import SearchAPI
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import DialogueSearchResult, SearchQueryInfo
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class SearchDialogueInput(BaseModel):
    """Input for searching dialogue."""

    query: str = Field(..., min_length=1, description="Dialogue text to search for")
    character: str | None = Field(None, description="Filter by character name")
    script_id: int | None = Field(None, description="Filter by script")
    fuzzy: bool = Field(False, description="Enable fuzzy matching")
    limit: int = Field(10, ge=1, le=50, description="Maximum results")


class SearchDialogueOutput(BaseModel):
    """Output from searching dialogue."""

    success: bool
    results: list[DialogueSearchResult]
    total_count: int
    query_info: SearchQueryInfo | None = None
    message: str | None = None


@mcp.tool()
async def scriptrag_search_dialogue(
    query: str,
    character: str | None = None,
    script_id: int | None = None,
    fuzzy: bool = False,
    limit: int = 10,
    ctx: Context | None = None,
) -> SearchDialogueOutput:
    """Search for dialogue content across scripts.

    Args:
        query: Dialogue text to search for
        character: Filter by character name
        script_id: Filter by script
        fuzzy: Enable fuzzy matching
        limit: Maximum results (1-50)
        ctx: MCP context

    Returns:
        Dialogue search results
    """
    try:
        # Validate inputs
        limit = max(1, min(50, limit))

        if ctx:
            filters = []
            if character:
                filters.append(f"character={character}")
            if script_id:
                filters.append(f"script_id={script_id}")
            if fuzzy:
                filters.append("fuzzy=true")
            filter_str = f" with {', '.join(filters)}" if filters else ""
            await ctx.info(f"Searching dialogue for '{query}'{filter_str}")

        # Use Search API
        settings = get_settings()
        search_api = SearchAPI(settings)
        wrapper = AsyncAPIWrapper()

        # Build search parameters
        search_params = {
            "query": query,
            "search_type": "dialogue",
            "limit": limit,
            "fuzzy": fuzzy,
        }

        if character:
            search_params["character_filter"] = character
        if script_id:
            search_params["script_id"] = script_id

        # Perform the search
        search_results = await wrapper.run_sync(search_api.search, **search_params)

        # Convert results to MCP models
        dialogue_results = []
        for result in search_results.get("results", []):
            dialogue_results.append(
                DialogueSearchResult(
                    scene_id=result.get("scene_id", 0),
                    script_id=result.get("script_id", 0),
                    scene_number=result.get("scene_number", 0),
                    character=result.get("character", ""),
                    dialogue=result.get("dialogue", ""),
                    match_score=result.get("score"),
                    context=result.get("context"),
                )
            )

        # Create query info
        query_info = SearchQueryInfo(
            query=query,
            search_type="dialogue",
            filters_applied={
                "character": character,
                "script_id": script_id,
                "fuzzy": fuzzy,
            }
            if any([character, script_id, fuzzy])
            else None,
        )

        total_count = len(dialogue_results)

        if ctx:
            await ctx.info(f"Found {total_count} dialogue matches")

        return SearchDialogueOutput(
            success=True,
            results=dialogue_results,
            total_count=total_count,
            query_info=query_info,
            message=f"Found {total_count} dialogue matches",
        )

    except Exception as e:
        logger.error("Failed to search dialogue", error=str(e))
        error_response = format_error_response(e, "scriptrag_search_dialogue")
        return SearchDialogueOutput(
            success=False,
            results=[],
            total_count=0,
            message=error_response["message"],
        )
